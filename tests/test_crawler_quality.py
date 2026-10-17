import asyncio
import json
import time
from urllib.robotparser import RobotFileParser

import httpx
import pytest

from outreach.browser import RenderSession, browser_environment
from outreach.research import add_lead, research_lead
from outreach.web import PublicWeb, extract_page, robots_request_delay
from outreach.worker import run


def test_published_obfuscated_and_structured_contacts():
    email = "founder@bright-demo.com"
    encoded = bytes([53] + [ord(c) ^ 53 for c in email]).hex()
    html = f'''<p>sales [at] bright-demo [dot] com</p><a data-cfemail="{encoded}">Email</a>
    <script type="application/ld+json">{{"@type":"Person","name":"Alex Doe",
    "jobTitle":"Founder","email":"founder@bright-demo.com"}}</script>
    <a href="mailto:hello%40bright-demo.com?subject=Hi">Hello</a>
    <script>const guessed = "hidden@bright-demo.com";</script>'''
    page = extract_page("https://bright-demo.com/", html)
    assert page["emails"] == ["founder@bright-demo.com", "hello@bright-demo.com", "sales@bright-demo.com"]
    founder = next(c for c in page["contacts"] if c["email"] == email)
    assert founder["name"] == "Alex Doe" and founder["role"] == "Founder"
    assert set(founder["methods"]) == {"cloudflare_obfuscation", "json_ld"}
    assert "hidden" not in page["text"]


def test_hash_router_links_are_distinct_from_section_anchors():
    from outreach.web import crawl_url, priority
    page = extract_page("https://bright-demo.com/", '<a href="#/contact">Contact route</a>'
                        '<a href="#pricing">Pricing section</a><a href="/about?utm_source=ad">About</a>')
    assert page["links"] == ["https://bright-demo.com/#/contact", "https://bright-demo.com/about"]
    assert crawl_url("https://bright-demo.com/#!/team") == "https://bright-demo.com/#!/team"
    assert priority("https://bright-demo.com/#/contact") == 0


async def test_redirect_aliases_capture_once_and_canonical_aliases_do_not_spend_budget(settings, monkeypatch):
    settings.browser_enabled = False
    settings.crawl_render_mode = "never"
    settings.crawl_delay_seconds = .1
    settings.crawl_max_pages = 3
    calls = []
    async def get(self, url, expected_domain=None):
        calls.append(url)
        if url.endswith("robots.txt"):
            return url, "User-agent: *\nAllow: /", 200
        if url.endswith("sitemap.xml"):
            return url, "", 404
        if url.endswith("/alias"):
            return "https://www.bright-demo.com/", "<p>Same homepage</p>", 200
        if url.endswith("/about"):
            return url, "<p>Company details</p>", 200
        return "https://www.bright-demo.com/", ('<p>Official homepage</p>'
            '<link rel="canonical" href="https://www.bright-demo.com/">'
            '<a href="https://www.bright-demo.com/">Home</a><a href="/alias">Alias</a><a href="/about">About</a>'), 200
    monkeypatch.setattr(PublicWeb, "get", get)
    crawler = PublicWeb(settings)
    pages = await crawler.crawl("https://bright-demo.com/")
    assert [page["url"] for page in pages] == ["https://www.bright-demo.com/", "https://www.bright-demo.com/about"]
    assert crawler.report["attempted"] == 3
    assert crawler.report["remaining"] == 0 and not crawler.report["budget_reached"]
    assert sum(url == "https://www.bright-demo.com/" for url in calls) == 0
    assert any(entry["reason"] == "duplicate_redirect" for entry in crawler.report["skipped"])


def test_browser_process_does_not_inherit_provider_secrets(monkeypatch):
    monkeypatch.setenv("SMTP_PASSWORD", "private")
    monkeypatch.setenv("OPENAI_API_KEY", "private")
    monkeypatch.setenv("ADMIN_PASSWORD", "private")
    monkeypatch.setenv("PATH", "runtime-path")
    environment = browser_environment()
    assert environment["PATH"] == "runtime-path"
    assert not any(key in environment for key in ("SMTP_PASSWORD", "OPENAI_API_KEY", "ADMIN_PASSWORD"))


async def test_browser_shutdown_stops_driver_even_when_browser_close_fails(settings):
    stopped = []
    class BrokenBrowser:
        async def close(self):
            raise RuntimeError("Controlled close failure")
    class Driver:
        async def stop(self):
            stopped.append(True)
    renderer = RenderSession(PublicWeb(settings))
    renderer.browser, renderer.playwright = BrokenBrowser(), Driver()
    with pytest.raises(RuntimeError, match="Controlled close"):
        await renderer.close()
    assert stopped == [True]


@pytest.mark.parametrize("directives,expected", [([], 0), (["Crawl-delay: 2"], 2), (["Request-rate: 2/10"], 5), (["Crawl-delay: 8", "Request-rate: 2/10"], 8)])
def test_declared_robots_pacing_distinguishes_assets_from_default_page_delay(directives, expected):
    parser = RobotFileParser()
    parser.parse(["User-agent: *", "Allow: /", *directives])
    assert robots_request_delay(parser, "OutreachResearchBot/0.1") == expected


async def test_public_fetch_shares_declared_pacing_across_pages_assets_and_www(settings, monkeypatch):
    from outreach import web
    async def ip(host):
        return "93.184.215.14"
    monkeypatch.setattr(web, "public_ip", ip)
    starts = []
    def handle(request):
        if request.url.path == "/robots.txt":
            text = "User-agent: *\nAllow: /\nRequest-rate: 1/1"
        else:
            starts.append((request.headers["host"], time.monotonic()))
            text = "Public fixture data"
        return httpx.Response(200, headers={"content-type": "text/plain"}, text=text)
    original = httpx.AsyncClient
    monkeypatch.setattr(web.httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(handle), **kwargs))
    fetcher = PublicWeb(settings)
    await fetcher.robots("https://bright-demo.com/")
    await asyncio.gather(fetcher.get("https://bright-demo.com/page"), fetcher.resource("https://www.bright-demo.com/asset.css"))
    assert len(starts) == 2 and starts[1][1] - starts[0][1] >= .95


async def test_real_browser_bounds_asset_parallelism_and_reuses_cookie_free_cache(settings, monkeypatch):
    settings.browser_resource_concurrency = 2
    settings.browser_settle_seconds = .1
    active, peak, assets = 0, 0, []
    async def resource(self, url, expected_domain=None, **kwargs):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        try:
            await asyncio.sleep(.04)
            if url.endswith("/"):
                body = ('<html><h1>Bounded fixture</h1>' + ''.join(f'<link rel="stylesheet" href="/asset-{i}.css">' for i in range(8)) + '</html>').encode()
                kind = "text/html"
            else:
                assets.append(url)
                body, kind = b"body {color:#123456}", "text/css"
            return {"url": url, "body": body, "status": 200, "headers": {"content-type": kind}, "encoding": "utf-8"}
        finally:
            active -= 1
    monkeypatch.setattr(PublicWeb, "resource", resource)
    renderer = RenderSession(PublicWeb(settings))
    robots = RobotFileParser()
    robots.parse(["User-agent: *", "Allow: /"])
    try:
        await renderer.start()
        for _ in range(2):
            result = await renderer.render("https://bright-demo.com/", "bright-demo.com", robots)
            assert "Bounded fixture" in result["html"] and not result["issues"]
    finally:
        await renderer.close()
    assert 1 < peak <= 2
    assert len(assets) == 8, "The second render must reuse cache instead of requesting the eight assets again"


async def test_real_browser_cancels_late_pending_requests_before_page_close(settings, monkeypatch, capsys):
    settings.browser_settle_seconds = .1
    started, cancelled = asyncio.Event(), asyncio.Event()
    async def resource(self, url, expected_domain=None, **kwargs):
        if url.endswith("/slow"):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()
        body = b'<html><h1>Late resource fixture</h1><script>setTimeout(()=>fetch("/slow"),800)</script></html>'
        return {"url": url, "body": body, "status": 200, "headers": {"content-type": "text/html"}, "encoding": "utf-8"}
    monkeypatch.setattr(PublicWeb, "resource", resource)
    renderer = RenderSession(PublicWeb(settings))
    robots = RobotFileParser()
    robots.parse(["User-agent: *", "Allow: /"])
    try:
        await renderer.start()
        result = await asyncio.wait_for(renderer.render("https://bright-demo.com/", "bright-demo.com", robots), 15)
    finally:
        await renderer.close()
    assert started.is_set() and cancelled.is_set()
    assert "Late resource fixture" in result["html"]
    assert any(issue["reason"] == "resource_requests_pending_at_snapshot" for issue in result["issues"])
    assert "TargetClosedError" not in capsys.readouterr().err


@pytest.mark.parametrize("terminal_abort_fails", [False, True])
async def test_terminal_route_error_settles_or_closes_without_orphan_callbacks(settings, monkeypatch, capsys, terminal_abort_fails):
    import gc
    from playwright.async_api import Route
    settings.browser_settle_seconds = .1
    async def resource(self, url, expected_domain=None, **kwargs):
        body = (b'<html><h1>Route failure fixture</h1><script>fetch("/broken")</script></html>'
                if url.endswith("/") else b"Fixture asset")
        return {"url": url, "body": body, "status": 200, "headers": {"content-type": "text/html"}, "encoding": "utf-8"}
    original = Route.fulfill
    async def fulfill(self, **kwargs):
        if self.request.url.endswith("/broken"):
            raise RuntimeError("Controlled terminal protocol failure")
        return await original(self, **kwargs)
    monkeypatch.setattr(PublicWeb, "resource", resource)
    monkeypatch.setattr(Route, "fulfill", fulfill)
    original_abort = Route.abort
    async def abort(self, **kwargs):
        if terminal_abort_fails and self.request.url.endswith("/broken"):
            raise RuntimeError("Controlled terminal abort failure")
        return await original_abort(self, **kwargs)
    monkeypatch.setattr(Route, "abort", abort)
    renderer = RenderSession(PublicWeb(settings))
    robots = RobotFileParser()
    robots.parse(["User-agent: *", "Allow: /"])
    loop = asyncio.get_running_loop()
    failures = []
    original_handler = loop.get_exception_handler()
    loop.set_exception_handler(lambda loop, context: failures.append(context))
    try:
        await renderer.start()
        result = await asyncio.wait_for(renderer.render("https://bright-demo.com/", "bright-demo.com", robots), 15)
        await renderer.close()
        gc.collect()
        await asyncio.sleep(.1)
    finally:
        loop.set_exception_handler(original_handler)
    if terminal_abort_fails:
        assert any(issue["reason"] == "render_target_closed_after_route_error" for issue in result["issues"])
    else:
        assert "Route failure fixture" in result["html"]
        assert any(issue["reason"] == "request_aborted_after_fulfill_error" for issue in result["issues"])
        assert not any(issue["reason"] == "render_target_closed_after_route_error" for issue in result["issues"])
    assert not failures
    assert "InvalidStateError" not in capsys.readouterr().err


async def test_unowned_abort_failure_closes_context_without_direct_network_fallback(settings, monkeypatch):
    import gc
    from playwright.async_api import Route
    settings.browser_settle_seconds = .1
    async def resource(self, url, expected_domain=None, **kwargs):
        return {"url": url, "body": b"<html><h1>Recovered mediated page</h1></html>", "status": 200,
                "headers": {"content-type": "text/html"}, "encoding": "utf-8"}
    monkeypatch.setattr(PublicWeb, "resource", resource)
    original = Route.abort
    async def abort(self, **kwargs):
        if self.request.url.endswith("/popup"):
            raise RuntimeError("Controlled unowned abort failure")
        return await original(self, **kwargs)
    monkeypatch.setattr(Route, "abort", abort)
    renderer = RenderSession(PublicWeb(settings))
    loop = asyncio.get_running_loop()
    failures = []
    original_handler = loop.get_exception_handler()
    loop.set_exception_handler(lambda loop, context: failures.append(context))
    try:
        await renderer.start()
        old_context = renderer.context
        tab = await renderer.context.new_page()
        with pytest.raises(Exception):
            await tab.goto("https://bright-demo.com/popup", timeout=5000)
        robots = RobotFileParser()
        robots.parse(["User-agent: *", "Allow: /"])
        result = await renderer.render("https://bright-demo.com/next", "bright-demo.com", robots)
        assert renderer.context is not old_context
        assert "Recovered mediated page" in result["html"]
        assert any(issue["reason"] == "browser_context_recreated_after_failure" for issue in result["issues"])
        await renderer.close()
        gc.collect()
        await asyncio.sleep(.1)
    finally:
        loop.set_exception_handler(original_handler)
    assert renderer.background_issues == [{"url": "https://bright-demo.com/popup", "reason": "unowned_route_target_unavailable"}]
    assert not failures


async def test_page_creation_failure_is_reported_and_next_page_can_render(settings, monkeypatch):
    settings.browser_settle_seconds = .1
    async def resource(self, url, expected_domain=None, **kwargs):
        return {"url": url, "body": b"<html><h1>Second page remains accessible</h1></html>", "status": 200,
                "headers": {"content-type": "text/html"}, "encoding": "utf-8"}
    monkeypatch.setattr(PublicWeb, "resource", resource)
    renderer = RenderSession(PublicWeb(settings))
    robots = RobotFileParser()
    robots.parse(["User-agent: *", "Allow: /"])
    try:
        await renderer.start()
        original = renderer.context.new_page
        attempts = 0
        async def new_page():
            nonlocal attempts
            attempts += 1
            if attempts == 1:
                raise RuntimeError("Controlled page creation failure")
            return await original()
        monkeypatch.setattr(renderer.context, "new_page", new_page)
        result = await renderer.render("https://bright-demo.com/first", "bright-demo.com", robots)
        assert not result["html"]
        assert result["issues"] == [{"url": "https://bright-demo.com/first", "reason": "render_start_failed", "error_type": "RuntimeError"}]
        result = await renderer.render("https://bright-demo.com/second", "bright-demo.com", robots)
        assert "Second page remains accessible" in result["html"]
    finally:
        await renderer.close()


async def test_confirmed_closed_context_recovers_even_if_cleanup_task_failed(settings, monkeypatch):
    settings.browser_settle_seconds = .1
    async def resource(self, url, expected_domain=None, **kwargs):
        return {"url": url, "body": b"<html><h1>Recovered after cleanup failure</h1></html>", "status": 200,
                "headers": {"content-type": "text/html"}, "encoding": "utf-8"}
    monkeypatch.setattr(PublicWeb, "resource", resource)
    renderer = RenderSession(PublicWeb(settings))
    robots = RobotFileParser()
    robots.parse(["User-agent: *", "Allow: /"])
    try:
        await renderer.start()
        old = renderer.context
        async def cleanup():
            try:
                await old.unroute_all(behavior="ignoreErrors")
                raise RuntimeError("Controlled late cleanup failure")
            finally:
                await old.close()
        renderer.context_invalid = True
        renderer.context_close_task = asyncio.create_task(cleanup())
        result = await renderer.render("https://bright-demo.com/next", "bright-demo.com", robots)
        assert "Recovered after cleanup failure" in result["html"]
        assert renderer.context is not old
        assert any(i["reason"] == "browser_context_cleanup_failed" for i in result["issues"])
        assert any(i["reason"] == "browser_context_recreated_after_failure" for i in result["issues"])
    finally:
        await renderer.close()


async def test_failed_cleanup_without_confirmed_context_close_does_not_render(settings, monkeypatch):
    async def unexpected_resource(*args, **kwargs):
        pytest.fail("A context with unresolved shutdown must not start another page")
    monkeypatch.setattr(PublicWeb, "resource", unexpected_resource)
    renderer = RenderSession(PublicWeb(settings))
    robots = RobotFileParser()
    robots.parse(["User-agent: *", "Allow: /"])
    try:
        await renderer.start()
        old = renderer.context
        async def cleanup():
            raise RuntimeError("Controlled failure before context closure")
        renderer.context_invalid = True
        renderer.context_close_task = asyncio.create_task(cleanup())
        result = await renderer.render("https://bright-demo.com/next", "bright-demo.com", robots)
        assert not result["html"]
        assert renderer.context is old
        assert not renderer.context_closed
        assert [issue["reason"] for issue in result["issues"]] == [
            "browser_context_cleanup_failed", "render_start_failed"]
    finally:
        await renderer.close()


async def test_browser_cleanup_failure_preserves_rendered_evidence(settings, monkeypatch):
    settings.browser_settle_seconds = .1
    async def resource(self, url, expected_domain=None, **kwargs):
        return {"url": url, "body": b"<html><h1>Evidence survives cleanup</h1></html>", "status": 200,
                "headers": {"content-type": "text/html"}, "encoding": "utf-8"}
    monkeypatch.setattr(PublicWeb, "resource", resource)
    renderer = RenderSession(PublicWeb(settings))
    robots = RobotFileParser()
    robots.parse(["User-agent: *", "Allow: /"])
    try:
        await renderer.start()
        original = renderer.context.new_page
        async def new_page():
            page = await original()
            async def failed_cleanup(**kwargs):
                raise RuntimeError("Controlled cleanup failure")
            monkeypatch.setattr(page, "unroute_all", failed_cleanup)
            return page
        monkeypatch.setattr(renderer.context, "new_page", new_page)
        result = await renderer.render("https://bright-demo.com/", "bright-demo.com", robots)
        assert "Evidence survives cleanup" in result["html"]
        assert any(issue["reason"] == "routing_cleanup_failed" for issue in result["issues"])
    finally:
        await renderer.close()


async def test_sitemap_index_prioritizes_contacts_and_preserves_partial_pages(settings, monkeypatch):
    settings.browser_enabled = False
    settings.crawl_delay_seconds = .001
    settings.crawl_max_pages = 3
    calls = []
    docs = {
        "/robots.txt": "User-agent: *\nDisallow: /private\nSitemap: https://bright-demo.com/index.xml",
        "/index.xml": '<sitemapindex><sitemap><loc>https://bright-demo.com/pages.xml</loc></sitemap></sitemapindex>',
        "/pages.xml": '<urlset>' + ''.join(f'<url><loc>https://bright-demo.com/{p}</loc></url>'
                                           for p in ['blog/old', 'contact', 'team', 'private']) + '</urlset>',
        "/": '<h1>Company</h1><a href="/contact?utm_source=ad">Contact</a>',
        "/team": '<p>Team: founder@bright-demo.com</p>',
    }
    async def get(self, url, expected_domain=None):
        from urllib.parse import urlsplit
        path = urlsplit(url).path
        calls.append(path)
        if path == "/contact":
            raise httpx.ReadTimeout("temporary upstream failure")
        return url, docs.get(path, ""), 200 if path in docs else 404
    monkeypatch.setattr(PublicWeb, "get", get)
    crawler = PublicWeb(settings)
    pages = await crawler.crawl("https://bright-demo.com/")
    assert [p["url"] for p in pages] == ["https://bright-demo.com/", "https://bright-demo.com/team"]
    assert "/private" not in calls and "/blog/old" not in calls
    assert calls.count("/contact") == 1
    assert crawler.report["status"] == "partial"
    assert len(crawler.report["sitemaps"]) == 2
    assert any(e.get("reason") == "ReadTimeout" for e in crawler.report["errors"])


async def test_real_chromium_executes_spa_and_public_cdn_assets(settings, monkeypatch, tmp_path):
    settings.browser_settle_seconds = .1
    calls = []
    resources = {
        "https://bright-demo.com/": ("text/html", '''<html><title>SPA fixture</title><div id="app"></div>
        <div hidden>trap@bright-demo.com</div><contact-card></contact-card>
        <link rel="stylesheet" href="https://cdn.example.com/site.css">
        <script src="https://cdn.example.com/site.js"></script></html>'''),
        "https://cdn.example.com/site.css": ("text/css", "body { color: rgb(12,34,56); }"),
        "https://cdn.example.com/site.js": ("text/javascript", '''fetch('https://cdn.example.com/content.json')
          .then(r=>r.json()).then(d=>{document.querySelector('#app').innerHTML=
          '<h1>'+d.title+'</h1><a href="mailto:alex@bright-demo.com">Email Alex</a><a href="/team">Team</a>';});
          fetch('http://127.0.0.1/private').catch(()=>{});
          fetch('https://bright-demo.com/submit', {method:'POST',body:'no'}).catch(()=>{});
          customElements.define('contact-card', class extends HTMLElement {
            connectedCallback(){this.attachShadow({mode:'open'}).innerHTML='<p>support@bright-demo.com</p>';}
          });'''),
        "https://cdn.example.com/content.json": ("application/json", '{"title":"Rendered consulting services"}'),
    }
    async def resource(self, url, expected_domain=None, **kwargs):
        calls.append(url)
        kind, body = resources[url]
        return {"url": url, "body": body.encode(), "status": 200, "headers": {
            "content-type": kind, "access-control-allow-origin": "*"}, "encoding": "utf-8"}
    monkeypatch.setattr(PublicWeb, "resource", resource)
    web = PublicWeb(settings)
    renderer = RenderSession(web)
    robots = RobotFileParser()
    robots.parse(["User-agent: *", "Allow: /"])
    paths = {label: tmp_path / f"{label}.png" for label in ("desktop", "mobile")}
    try:
        await renderer.start()
        result = await renderer.render("https://bright-demo.com/", "bright-demo.com", robots, screenshot_paths=paths)
    finally:
        await renderer.close()
    page = extract_page(result["url"], result["html"])
    assert "Rendered consulting services" in page["text"], result
    assert page["emails"] == ["alex@bright-demo.com", "support@bright-demo.com"]
    assert "trap@" not in page["text"]
    assert "https://bright-demo.com/team" in page["links"]
    assert set(calls) == set(resources)
    assert any(i["reason"] == "mutating_or_post_request_requires_review" for i in result["issues"])
    assert any("not allowed" in i["reason"] for i in result["issues"])
    assert all(path.stat().st_size > 1000 for path in paths.values())
    assert result["visual"]["viewport"]["width"] == 1440
    assert result["visual"]["mobileHorizontalOverflow"] is False


async def test_crawl_report_and_contact_identity_are_persisted(db, settings, monkeypatch):
    lid = add_lead(db, "Bright", "https://bright-demo.com", "A", "https://bright-demo.com")
    async def crawl(self, website):
        self.report.update(status="partial", remaining=2, errors=[{"reason": "not_found"}])
        return [extract_page(website, '<script type="application/ld+json">'
                             '{"@type":"Person","email":"alex@bright-demo.com","name":"Alex","jobTitle":"Founder"}'
                             '</script><h1>Public business</h1>')]
    monkeypatch.setattr(PublicWeb, "crawl", crawl)
    await research_lead(db, settings, lid)
    assert json.loads(db.one("SELECT report FROM crawls")["report"])["status"] == "partial"
    assert "partial" in db.one("SELECT research_notes FROM leads")["research_notes"]
    contact = db.one("SELECT * FROM contacts")
    assert contact["name"] == "Alex" and contact["role"] == "Founder"
    assert db.one("SELECT kind FROM jobs WHERE kind='screenshot'") is not None


async def test_late_crawl_failure_preserves_evidence_and_records_failure(db, settings, monkeypatch):
    lid = add_lead(db, "Bright", "https://bright-demo.com", "A", "https://bright-demo.com")
    async def crawl(self, website):
        page = extract_page(website, '<p>Published contact alex@bright-demo.com</p>')
        await self.on_page(page, self.report)
        raise httpx.ReadTimeout("upstream unavailable")
    monkeypatch.setattr(PublicWeb, "crawl", crawl)
    with pytest.raises(httpx.ReadTimeout):
        await research_lead(db, settings, lid)
    assert db.one("SELECT text FROM evidence")["text"] == "Published contact alex@bright-demo.com"
    assert db.one("SELECT email FROM contacts")["email"] == "alex@bright-demo.com"
    assert json.loads(db.one("SELECT report FROM crawls")["report"])["status"] == "failed"
    assert db.one("SELECT status FROM leads")["status"] == "review"


def test_review_cannot_race_with_running_research(db, prepared):
    from outreach.campaigns import review_lead
    db.execute("UPDATE leads SET status='researching' WHERE id=?", (prepared["lead_id"],))
    with pytest.raises(ValueError, match="still running"):
        review_lead(db, prepared["lead_id"], {})


async def test_approval_during_research_start_preserves_activated_evidence(db, settings, prepared, monkeypatch):
    from outreach.campaigns import approve
    original_one = db.one
    activated = False
    def raced(sql, params=()):
        nonlocal activated
        row = original_one(sql, params)
        if not activated and sql == "SELECT id FROM contacts WHERE lead_id=? AND status IN ('active','replied','hold','closed')":
            activated = True
            approve(db, settings, prepared["contact_id"], "Fixture corporate outreach eligibility independently reviewed.", "Fixture founder owns this website.")
        return row
    monkeypatch.setattr(db, "one", raced)
    async def crawl(self, website):
        pytest.fail("Approval won the race; research must not overwrite its evidence")
    monkeypatch.setattr(PublicWeb, "crawl", crawl)
    with pytest.raises(ValueError, match="Existing outreach history"):
        await research_lead(db, settings, prepared["lead_id"])
    assert activated
    assert db.one("SELECT status FROM contacts WHERE id=?", (prepared["contact_id"],))["status"] == "active"
    assert db.one("SELECT status FROM leads WHERE id=?", (prepared["lead_id"],))["status"] == "qualified"
    assert db.one("SELECT sha256 FROM evidence WHERE id=?", (prepared["evidence_id"],))["sha256"] == "abc"
    assert not db.one("SELECT id FROM crawls WHERE lead_id=?", (prepared["lead_id"],))


async def test_catalog_does_not_starve_announcement_research(settings, monkeypatch):
    settings.browser_enabled = False
    settings.crawl_delay_seconds = .001
    settings.crawl_max_pages = 8
    urls = [f"https://bright-demo.com/product/{i}" for i in range(20)]
    urls.append("https://bright-demo.com/news/new-launch")
    async def get(self, url, expected_domain=None):
        if url.endswith("robots.txt"):
            return url, "User-agent: *\nAllow: /", 200
        if url.endswith("sitemap.xml"):
            return url, '<urlset>' + ''.join(f'<url><loc>{u}</loc></url>' for u in urls) + '</urlset>', 200
        return url, '<h1>Public business content</h1>', 200
    monkeypatch.setattr(PublicWeb, "get", get)
    pages = await PublicWeb(settings).crawl("https://bright-demo.com/")
    assert any(p["url"].endswith("/news/new-launch") for p in pages)


async def test_worker_monitors_inbox_during_long_research_and_recovers_shutdown(db, settings, monkeypatch):
    from outreach import worker
    lid = add_lead(db, "Bright", "https://bright-demo.com", "A", "https://bright-demo.com")
    jid = db.enqueue("research", {"lead_id": lid})
    started, stop = asyncio.Event(), asyncio.Event()
    polled, sends = [], []
    async def execute(*args):
        started.set()
        await asyncio.sleep(60)
    monkeypatch.setattr(worker, "execute_job", execute)
    monkeypatch.setattr(worker, "poll_inbox", lambda *a: polled.append(True))
    monkeypatch.setattr(worker, "send_one", lambda *a: sends.append(True))
    task = asyncio.create_task(run(db, settings, stop))
    await asyncio.wait_for(started.wait(), timeout=3)
    for _ in range(30):
        if len(sends) >= 2:
            break
        await asyncio.sleep(.1)
    assert polled and len(sends) >= 2
    stop.set()
    await asyncio.wait_for(task, timeout=3)
    assert db.one("SELECT state FROM jobs WHERE id=?", (jid,))["state"] == "pending"


def test_parallel_crawl_claims_never_share_one_lead(db):
    db.enqueue("research", {"lead_id": 1})
    first = db.enqueue("screenshot", {"lead_id": 1})
    second = db.enqueue("research", {"lead_id": 2})
    assert db.claim({"research", "screenshot"})["id"] == first
    assert db.claim({"research", "screenshot"})["id"] == second
    assert db.claim({"research", "screenshot"}) is None
