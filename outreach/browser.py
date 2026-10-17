"""Render real public pages while mediating all network requests through PublicWeb."""
import asyncio
import hashlib
import json
import os
import time

from .web import PublicWeb, normalize_url, crawl_url, domain_of


class RouteCompletionError(Exception):
    """Propagate a failed terminal operation so Playwright can finish its handler."""


def browser_environment():
    allowed = {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "TMPDIR", "HOME", "USERPROFILE",
               "LOCALAPPDATA", "APPDATA", "LANG", "LC_ALL", "TZ", "DISPLAY", "XAUTHORITY", "XDG_RUNTIME_DIR"}
    return {key: value for key, value in os.environ.items() if key.upper() in allowed}


class RenderSession:
    def __init__(self, web):
        self.web, self.settings = web, web.settings
        self.playwright = self.browser = self.context = None
        self.cache = {}
        self.cache_bytes = 0
        self.resource_slots = asyncio.Semaphore(self.settings.browser_resource_concurrency)
        self.background_issues = []
        self.context_invalid = False
        self.context_closed = False
        self.context_close_task = None

    async def start(self):
        from playwright.async_api import async_playwright
        self.playwright = await async_playwright().start()
        # Chromium cannot connect directly even if a route were accidentally missed.
        self.browser = await self.playwright.chromium.launch(headless=True, chromium_sandbox=True,
            env=browser_environment(), args=[
            "--host-resolver-rules=MAP * ~NOTFOUND", "--disable-quic", "--disable-background-networking",
        ])
        await self.new_context()

    async def new_context(self):
        context = await self.browser.new_context(viewport={"width": 1440, "height": 900},
            service_workers="block", accept_downloads=False, user_agent=self.settings.crawler_user_agent)
        self.context = context
        self.context_invalid = False
        self.context_closed = False
        self.context_close_task = None
        def closed(_):
            if self.context is context:
                self.context_invalid = True
                self.context_closed = True
        context.on("close", closed)
        close_task = None
        # Page routes take precedence; unowned popup/background requests never escape mediation.
        async def deny_unowned(route):
            try:
                await route.abort()
            except Exception as exc:
                self.background_issues.append({"url": route.request.url, "reason": "unowned_route_target_unavailable"})
                # A failed terminal abort must not leave an unresolved handler or
                # fall through into direct browser networking. Close this context.
                nonlocal close_task
                if close_task is None:
                    async def close_failed_context():
                        try:
                            await context.unroute_all(behavior="ignoreErrors")
                        finally:
                            await context.close()
                    close_task = asyncio.create_task(close_failed_context())
                if self.context is context:
                    self.context_invalid = True
                    self.context_close_task = close_task
                await asyncio.shield(close_task)
                raise RouteCompletionError("Unowned route could not be aborted") from exc
        await context.route("**/*", deny_unowned)
        await context.route_web_socket("**/*", lambda ws: ws.close())

    async def close(self):
        try:
            if self.context_close_task:
                await asyncio.gather(self.context_close_task, return_exceptions=True)
            if self.browser:
                await self.browser.close()
        finally:
            if self.playwright:
                await self.playwright.stop()

    async def render(self, url, domain, robots, screenshot_paths=None, document=None):
        startup_issues = []
        try:
            if self.context_invalid:
                if self.context_close_task:
                    try:
                        await asyncio.shield(self.context_close_task)
                    except Exception as exc:
                        startup_issues.append({"url": url, "reason": "browser_context_cleanup_failed",
                                               "error_type": type(exc).__name__})
                        # Cleanup can fail after Chromium has already closed
                        # the context. Consume that failure only when its close
                        # event confirms there are no old requests left alive.
                        if not self.context_closed:
                            raise
                await self.new_context()
                startup_issues.append({"url": url, "reason": "browser_context_recreated_after_failure"})
            page = await self.context.new_page()
        except Exception as exc:
            return {"url": url, "html": "", "issues": startup_issues + [
                {"url": url, "reason": "render_start_failed", "error_type": type(exc).__name__}],
                "visual": {}, "resource_bytes": 0}
        issues, visual, used_bytes = [], {}, 0
        issues.extend(startup_issues)
        background_start = len(self.background_issues)
        guards = set()
        fetches = set()
        critical_fetches = set()
        critical_changed = asyncio.Event()
        document_reused = False
        closing = False
        protocol_halted = False
        routing_failure_lock = asyncio.Lock()
        async def complete_route(route, operation, **kwargs):
            # The site's own AbortController/navigation can invalidate a route.
            # Consume that protocol error once, without attempting a second abort.
            try:
                await getattr(route, operation)(**kwargs)
            except Exception as exc:
                nonlocal closing, protocol_halted
                issues.append({"url": route.request.url, "reason": "route_target_unavailable"})
                if operation == "fulfill":
                    # A malformed/cancelled asset response may still have a
                    # live route. One terminal abort settles it without losing
                    # the useful page DOM. Never continue/fallback to networking.
                    try:
                        await route.abort()
                    except Exception:
                        pass
                    else:
                        issues.append({"url": route.request.url, "reason": "request_aborted_after_fulfill_error"})
                        return
                # Swallowing an unsettled terminal error leaves Playwright waiting for a
                # terminal handling result forever. Fail this page closed, mark
                # in-flight handlers to consume errors, then propagate the failure.
                # No fallback/continue can bypass the mediated network policy.
                closing = True
                async with routing_failure_lock:
                    if not protocol_halted:
                        await page.unroute_all(behavior="ignoreErrors")
                        await page.close()
                        protocol_halted = True
                        issues.append({"url": url, "reason": "render_target_closed_after_route_error"})
                raise RouteCompletionError("Terminal route operation failed") from exc

        async def fetch_resource(resource_url, request, headers):
            async with self.resource_slots:
                return await self.web.resource(resource_url, domain if request.is_navigation_request() else None,
                    headers=headers, max_bytes=self.settings.browser_resource_bytes, redirects=False)

        async def guard(route):
            nonlocal used_bytes, document_reused
            current = asyncio.current_task()
            guards.add(current)
            request = route.request
            resource_url = request.url
            try:
                if closing:
                    await complete_route(route, "abort")
                    return
                normalize_url(resource_url)
                if request.method not in {"GET", "HEAD"}:
                    raise ValueError("mutating_or_post_request_requires_review")
                same_site = domain_of(resource_url) == domain
                if request.is_navigation_request() and not same_site:
                    raise ValueError("external_document_navigation")
                if same_site:
                    if not robots.can_fetch(self.settings.crawler_user_agent, resource_url):
                        raise ValueError("robots")
                # Cache only cookie-free public scripts/styles/fonts/images, never documents or API data.
                headers = await request.all_headers()
                key = resource_url if request.resource_type in {"script", "stylesheet", "font", "image"} and not headers.get("cookie") else None
                result = self.cache.get(key) if key else None
                if (document and not document_reused and request.method == 'GET' and request.resource_type == 'document'
                        and request.frame == page.main_frame
                        and normalize_url(resource_url) == normalize_url(document['url']) and document['status'] == 200):
                    # This response already passed PublicWeb's DNS pinning,
                    # redirect, size and HTTP checks for this page. Only the
                    # matching initial document is reused; scripts/API calls
                    # still go through the guarded public fetch lane.
                    result = document
                    document_reused = True
                if result is None:
                    if closing:
                        await complete_route(route, "abort")
                        return
                    task = asyncio.create_task(fetch_resource(resource_url, request, headers))
                    fetches.add(task)
                    if request.resource_type in {'document', 'script', 'stylesheet', 'xhr', 'fetch'}:
                        critical_fetches.add(task)
                        critical_changed.set()
                    try:
                        result = await task
                    finally:
                        fetches.discard(task)
                        if task in critical_fetches:
                            critical_fetches.discard(task)
                            critical_changed.set()
                    if key and result["status"] == 200 and not result["headers"].get("set-cookie") and self.cache_bytes + len(result["body"]) < self.settings.browser_page_bytes:
                        self.cache[key] = result
                        self.cache_bytes += len(result["body"])
                used_bytes += len(result["body"])
                if used_bytes > self.settings.browser_page_bytes:
                    raise ValueError("page_resource_budget_exceeded")
                if result["status"] >= 400:
                    issues.append({"url": resource_url, "reason": f"http_{result['status']}"})
                await complete_route(route, "fulfill", status=result["status"], headers=result["headers"], body=result["body"])
            except RouteCompletionError:
                raise
            except asyncio.CancelledError:
                if not closing:
                    raise
                await complete_route(route, "abort")
            except Exception as exc:
                reason = str(exc) if isinstance(exc, ValueError) else type(exc).__name__
                issues.append({"url": resource_url, "reason": reason[:160]})
                await complete_route(route, "abort")
            finally:
                guards.discard(current)
        await page.route("**/*", guard)
        page.on("pageerror", lambda error: issues.append({"url": url, "reason": "javascript_error"}))
        html, final = "", url
        try:
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            except Exception as exc:
                # A slow asset must not discard an already-loaded same-site
                # document. The final URL check below still rejects navigation
                # outside this company, and the crawl rejects challenge pages.
                issues.append({'url': url, 'reason': 'navigation_incomplete', 'error_type': type(exc).__name__})
            if screenshot_paths:
                try:
                    await page.wait_for_load_state("networkidle", timeout=10000)
                except Exception:
                    issues.append({"url": url, "reason": "network_did_not_settle_within_10s"})
            else:
                # Preserve the 10s content-load allowance for scripts/CSS/API
                # requests; background images/fonts needn't delay text research.
                deadline = time.monotonic()+10
                while time.monotonic() < deadline:
                    critical_changed.clear()
                    try:
                        await asyncio.wait_for(critical_changed.wait(), min(.5, deadline-time.monotonic()))
                    except TimeoutError:
                        if not critical_fetches:
                            break
                if critical_fetches:
                    issues.append({'url': url, 'reason': 'content_requests_did_not_settle_within_10s',
                                   'count': len(critical_fetches)})
            # Bounded stabilization works even when a site's analytics never reaches networkidle.
            await page.wait_for_timeout(self.settings.browser_settle_seconds * 1000)
            for _ in range(4):
                await page.evaluate("window.scrollBy(0, window.innerHeight)")
                await page.wait_for_timeout(250)
            await page.evaluate("window.scrollTo(0, 0)")
            await page.wait_for_timeout(500)
            final = crawl_url(page.url)
            if domain_of(final) != domain:
                raise ValueError("external_document_navigation")
            # Snapshot visible content and open shadow roots without modifying the actual page.
            html = await page.evaluate("""() => {
                const copy=document.documentElement.cloneNode(true);
                function clean(original, cloned) {
                    const originals=[...original.children], clones=[...cloned.children];
                    for(let i=0;i<originals.length;i++) {
                        const el=originals[i], out=clones[i];
                        if(!out) continue;
                        if(el.tagName !== 'SCRIPT' && el.tagName !== 'STYLE') {
                            const style=getComputedStyle(el);
                            if(style.display==='none' || style.visibility==='hidden' || el.hidden) {
                                out.remove(); continue;
                            }
                        }
                        clean(el,out);
                        if(el.shadowRoot) {
                            const shadow=document.createElement('div');
                            for(const child of el.shadowRoot.childNodes) shadow.appendChild(child.cloneNode(true));
                            clean(el.shadowRoot,shadow); out.appendChild(shadow);
                        }
                    }
                }
                clean(document.body,copy.querySelector('body'));
                return '<!DOCTYPE html>'+copy.outerHTML;
            }""")
            visual = await page.evaluate("""() => ({
                viewport: {width: innerWidth, height: innerHeight},
                horizontalOverflow: document.documentElement.scrollWidth > innerWidth + 1,
                title: document.title,
                forms: document.forms.length,
                fieldsWithoutExplicitLabels: [...document.querySelectorAll('input,textarea,select')].filter(el =>
                    !['hidden','submit','button','reset'].includes(el.type) && !el.labels?.length &&
                    !el.getAttribute('aria-label') && !el.getAttribute('aria-labelledby')).length,
                ctas: [...document.querySelectorAll('a,button')].filter(el => {
                    const r=el.getBoundingClientRect(); return r.width>0 && r.height>0 &&
                    /book|demo|contact|inquir|enquir|buy|shop|start|sign up|get started/i.test(el.innerText);
                }).slice(0,100).map(el => ({text: el.innerText.trim().slice(0,150),
                    href: el.getAttribute('href') || '', top: Math.round(el.getBoundingClientRect().top)}))
            })""")
            if screenshot_paths:
                for label, path in screenshot_paths.items():
                    if label == "mobile":
                        await page.set_viewport_size({"width": 390, "height": 844})
                        await page.wait_for_timeout(750)
                        visual["mobileHorizontalOverflow"] = await page.evaluate("document.documentElement.scrollWidth > innerWidth + 1")
                        visual["mobileCtas"] = await page.evaluate("""() => [...document.querySelectorAll('a,button')]
                            .filter(el => {const r=el.getBoundingClientRect();return r.width>0 && r.height>0 &&
                                /book|demo|contact|inquir|enquir|buy|shop|start|sign up|get started/i.test(el.innerText);})
                            .slice(0,100).map(el=>({text:el.innerText.trim().slice(0,150),
                                top:Math.round(el.getBoundingClientRect().top),
                                aboveFold:el.getBoundingClientRect().top>=0 && el.getBoundingClientRect().bottom<=innerHeight}))""")
                    await page.screenshot(path=str(path), full_page=True, timeout=20000)
        except Exception as exc:
            issues.append({"url": url, "reason": str(exc)[:160] if isinstance(exc, ValueError) else type(exc).__name__})
        finally:
            # Pending assets may still be in HTTP/robots pacing when the page
            # finishes. Cancel those owned requests before closing its target.
            closing = True
            pending = list(fetches)
            if pending:
                issues.append({"url": url, "reason": "resource_requests_pending_at_snapshot", "count": len(pending)})
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            # Let callbacks finish their single abort/fulfill; cancelling the
            # callbacks themselves can fall through to a second context handler.
            try:
                await asyncio.wait_for(page.unroute_all(behavior="wait"), timeout=10)
            except Exception as exc:
                issues.append({"url": url, "reason": "routing_cleanup_failed", "error_type": type(exc).__name__})
            finally:
                try:
                    await page.close()
                except Exception as exc:
                    issues.append({"url": url, "reason": "page_close_failed", "error_type": type(exc).__name__})
            issues.extend(self.background_issues[background_start:])
        return {"url": final, "html": html, "issues": issues[:200], "visual": visual, "resource_bytes": used_bytes,
                'document_reused': document_reused}


async def screenshot(db, settings, lead_id):
    if not settings.browser_enabled:
        raise ValueError("Browser rendering is disabled in configuration")
    lead = db.one("SELECT * FROM leads WHERE id=?", (lead_id,))
    if not lead:
        raise ValueError("Lead not found")
    if lead.get("lead_kind") == "profile":
        raise ValueError("Website visual audit needs an official company website")
    url = crawl_url(lead["website"])
    web = PublicWeb(settings)
    robots, _, _ = await web.robots(url)
    if not robots.can_fetch(settings.crawler_user_agent, url):
        raise ValueError("Robots denies screenshots of this page")
    folder = settings.data_dir / "screenshots"
    folder.mkdir(parents=True, exist_ok=True)
    stamp = f"lead-{lead_id}-{int(time.time())}-{hashlib.sha256(url.encode()).hexdigest()[:6]}"
    paths = {label: folder / f"{stamp}-{label}.png" for label in ("desktop", "mobile")}
    renderer = RenderSession(web)
    try:
        await renderer.start()
        result = await renderer.render(url, domain_of(url), robots, screenshot_paths=paths)
    finally:
        await renderer.close()
    files = {label: path.name for label, path in paths.items() if path.exists()}
    db.event("screenshot", {"lead_id": lead_id, "files": files, "visual": result["visual"],
                            "issues": result["issues"], "complete": not result["issues"]})
    db.execute("UPDATE leads SET research_notes=research_notes || ? WHERE id=?",
               ("\nScreenshots: " + json.dumps(files) + "; render issues: " + str(len(result["issues"])), lead_id))
    if not files:
        raise ValueError("No screenshot captured; inspect screenshot event for rendering issues")
