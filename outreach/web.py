"""Bounded public-web access. Provider URLs are separately trusted administrator configuration."""
import asyncio
import hashlib
import heapq
import ipaddress
import json
import re
import socket
import time
import zlib
import xml.etree.ElementTree as ET
from contextlib import asynccontextmanager
from urllib.parse import parse_qsl, urlencode, unquote, urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup
from email_validator import validate_email, EmailNotValidError
from email.utils import parsedate_to_datetime
from .crawl_state import continuation_wait, current_errors, timestamp, transient_failure


BLOCKED_SOURCES = {"linkedin.com", "peopleperhour.com", "x.com", "twitter.com", "facebook.com"}
EMAIL_RE = r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"
SKIP_PATH = re.compile(r"\.(?:pdf|zip|png|jpe?g|gif|svg|webp|mp4|css|js|woff2?)(?:$|\?)", re.I)


def robots_request_delay(parser, user_agent):
    """Declared robots pacing applies to actual same-site requests, including assets."""
    rate = parser.request_rate(user_agent)
    interval = rate.seconds / rate.requests if rate and rate.requests > 0 else 0
    return max(parser.crawl_delay(user_agent) or 0, interval)


def retry_after_seconds(headers):
    value = headers.get('retry-after', '')
    try:
        seconds = float(value)
    except (ValueError, TypeError):
        try:
            seconds = parsedate_to_datetime(value).timestamp()-time.time()
        except (ValueError, TypeError, OverflowError):
            return 0
    # Do not schedule an infinite/NaN delay from an untrusted response header.
    import math
    return max(0, seconds) if math.isfinite(seconds) else 0


def sitemap_body(body, limit):
    """Bound file-level gzip expansion independently of HTTP Content-Encoding."""
    if not body.startswith(b'\x1f\x8b'):
        return body
    decoded = bytearray()
    try:
        while body:
            inflater = zlib.decompressobj(16 + zlib.MAX_WBITS)
            decoded.extend(inflater.decompress(body, limit + 1 - len(decoded)))
            if len(decoded) > limit or inflater.unconsumed_tail:
                raise ValueError('Decompressed sitemap exceeds configured size limit')
            if not inflater.eof:
                raise ValueError('Incomplete gzip sitemap')
            body = inflater.unused_data
            if body and not body.startswith(b'\x1f\x8b'):
                raise ValueError('Invalid trailing gzip sitemap data')
    except zlib.error as exc:
        raise ValueError('Invalid gzip sitemap') from exc
    return bytes(decoded)


def crawl_url(url):
    fragment = urlsplit(url).fragment
    parts = urlsplit(normalize_url(url))
    query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
             if not k.lower().startswith("utm_") and k.lower() not in {"fbclid", "gclid"}]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(sorted(query)),
                       fragment if fragment.startswith(("/", "!/")) else ""))


def priority(url):
    parts = urlsplit(url)
    path = unquote(parts.path + '/' + parts.fragment).lower()
    for score, pattern in enumerate([
        r'contact(?:us)?|team|our-team|meet-the-team|leadership|about(?:us)?|business-enquir(?:y|ies)|enquiries|inquiries|email|media-relations',
        r'services?|pricing|demo|book(?:ing)?|faq|support|help',
        r'products?|collections?|shop|case-stud(?:y|ies)|customers?',
        r'news(?:room)?|press|announcements?|blogs?',
    ]):
        if re.search(r'(?:^|[/#!])(?:'+pattern+r')(?:[-_/]|$)', path):
            return score
    return 4


def company_crawl_url(url, domain):
    url = crawl_url(url)
    if domain_of(url) != domain or SKIP_PATH.search(url):
        return ''
    if any(segment in urlsplit(url).path.lower().split('/')
           for segment in ('cart', 'checkout', 'logout', 'login', 'account', 'wp-admin',
                           'customer_authentication', 'authentication', 'signin', 'sign-in', 'signout', 'sign-out')):
        return ''
    return url


def domain_of(url):
    host = (urlsplit(url).hostname or "").lower().rstrip(".")
    return host.removeprefix("www.")


def normalize_url(url):
    parts = urlsplit(url.strip())
    if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
        raise ValueError("A public http(s) URL without credentials is required")
    if parts.port not in {None, 80, 443}:
        raise ValueError("Only standard web ports are supported")
    host = parts.hostname.encode("idna").decode().lower().rstrip(".")
    if host == "localhost" or "." not in host:
        raise ValueError("Local hosts are not allowed")
    try:
        address = ipaddress.ip_address(host)
        if not address.is_global:
            raise ValueError("Private and reserved addresses are not allowed")
    except ValueError as exc:
        if "not allowed" in str(exc):
            raise
    return urlunsplit((parts.scheme, host, parts.path or "/", parts.query, ""))


def normalize_email(value):
    try:
        return validate_email(value.strip(), check_deliverability=False).normalized.lower()
    except EmailNotValidError as exc:
        raise ValueError("Invalid email syntax") from exc


async def public_ip(host):
    records = await asyncio.get_running_loop().getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    addresses = sorted({r[4][0] for r in records})
    if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):
        raise ValueError("DNS resolves to private/reserved infrastructure")
    return addresses[0]


class PublicWeb:
    def __init__(self, settings, on_page=None, signal_only=False, on_checkpoint=None):
        self.settings = settings
        self.on_page = on_page
        self.signal_only = signal_only
        self.on_checkpoint = on_checkpoint
        self.clients = None
        self.last_document = None
        self.request_delays, self.request_locks, self.request_times = {}, {}, {}
        self.adaptive_delays = {}
        self.report = {"status": "running", "pages": [], "errors": [], "skipped": [], "sitemaps": []}

    async def pace_request(self, url):
        # Share declared site limits across HTTP pages, browser assets, redirects
        # and successive renders. Cache hits never reach this network gate.
        domain = domain_of(url)
        interval = self.request_delays.get(domain, 0)
        if interval:
            lock = self.request_locks.setdefault(domain, asyncio.Lock())
            async with lock:
                await asyncio.sleep(max(0, interval - (time.monotonic() - self.request_times.get(domain, 0))))
                self.request_times[domain] = time.monotonic()

    @asynccontextmanager
    async def connection(self, host):
        if self.clients is not None:
            if host not in self.clients:
                self.clients[host] = httpx.AsyncClient(timeout=25, trust_env=False,
                    limits=httpx.Limits(max_connections=8, max_keepalive_connections=4))
            yield self.clients[host]
        else:
            async with httpx.AsyncClient(timeout=25, trust_env=False) as client:
                yield client

    async def resource(self, url, expected_domain=None, headers=None, max_bytes=None, redirects=True):
        """Fetch through a checked/pinned destination, including browser CDN resources."""
        url = normalize_url(url)
        for _ in range(6):
            host = urlsplit(url).hostname
            if not self.signal_only and any(domain_of(url) == d or domain_of(url).endswith("." + d) for d in BLOCKED_SOURCES):
                raise ValueError("This platform is signal-only; use an official company website")
            if expected_domain and domain_of(url) != expected_domain:
                raise ValueError("Cross-domain redirect requires separate review")
            ip = await asyncio.wait_for(public_ip(host), timeout=self.settings.crawl_request_timeout_seconds)
            # Pin the TCP destination to the checked public address (prevents DNS rebinding).
            target = httpx.URL(url).copy_with(host=ip)
            request_headers = {k: v for k, v in (headers or {}).items()
                               if k.lower() not in {"host", "accept-encoding", "connection", "content-length"}}
            request_headers.update({"Host": host, "User-Agent": self.settings.crawler_user_agent})
            async with self.connection(host) as client:
                await self.pace_request(url)
                network_started = time.monotonic()
                # httpx read timeouts alone allow a trickling body to run forever.
                # Keep declared robots pacing outside the network/body deadline.
                async with asyncio.timeout(self.settings.crawl_request_timeout_seconds), client.stream(
                        "GET", target, headers=request_headers, extensions={"sni_hostname": host}) as response:
                    latency = time.monotonic()-network_started
                    if response.is_redirect and redirects:
                        url = normalize_url(urljoin(url, response.headers["location"]))
                        continue
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > (max_bytes or self.settings.max_page_bytes):
                            raise ValueError("Resource exceeds configured size limit")
                    # aiter_bytes has already decompressed the response.
                    response_headers = {k: v for k, v in response.headers.items()
                                        if k.lower() not in {"content-encoding", "content-length", "transfer-encoding", "connection"}}
                    return {"url": url, "body": bytes(body), "status": response.status_code,
                            'latency_seconds': latency,
                            "headers": response_headers, "encoding": response.encoding or "utf-8"}
        raise ValueError("Too many redirects")

    async def get(self, url, expected_domain=None):
        self.last_document = None
        result = None
        for attempt in range(self.settings.crawl_http_retries + 1):
            retry_reason, wait = '', min(2 ** attempt, self.settings.crawl_retry_max_wait_seconds)
            try:
                result = await self.resource(url, expected_domain)
                if self.settings.crawl_adaptive_pacing and result.get('latency_seconds') is not None:
                    host = domain_of(url)
                    old = self.adaptive_delays.get(host, self.settings.crawl_delay_seconds)
                    target = max(self.settings.crawl_delay_seconds,
                                 min(self.settings.crawl_adaptive_max_delay_seconds, result['latency_seconds']))
                    updated = (old+target)/2
                    if result['status'] != 200:
                        updated = max(old, updated)
                    self.adaptive_delays[host] = updated
                    self.report.setdefault('throttle', {})[host] = {'delay_seconds': round(updated, 3),
                        'last_latency_seconds': round(result['latency_seconds'], 3), 'last_status': result['status']}
                if result['status'] in {408, 429, 500, 502, 503, 504}:
                    retry_reason = f"http_{result['status']}"
                    wait = max(wait, retry_after_seconds(result['headers']))
                else:
                    break
            except (httpx.TransportError, TimeoutError, OSError) as exc:
                if attempt >= self.settings.crawl_http_retries:
                    raise
                retry_reason = type(exc).__name__
            if attempt >= self.settings.crawl_http_retries or wait > self.settings.crawl_retry_max_wait_seconds:
                break
            self.report.setdefault('retried_requests', []).append({'url': url, 'reason': retry_reason,
                                                                  'retry': attempt+1, 'wait_seconds': wait})
            await asyncio.sleep(wait)
        if result is None:
            raise RuntimeError('No public response available')
        if result["status"] in {404, 410}:
            return result["url"], "", 404
        if result["status"] >= 400:
            raise httpx.HTTPStatusError(f"HTTP {result['status']}", request=httpx.Request("GET", url),
                                       response=httpx.Response(result["status"], headers=result['headers']))
        compressed_map = (urlsplit(result['url']).path.lower().endswith(('.xml.gz', '.xml.gzip')) or
                          any(t in result['headers'].get('content-type', '').lower()
                              for t in ('application/gzip', 'application/x-gzip')))
        if compressed_map:
            result['body'] = sitemap_body(result['body'], self.settings.max_page_bytes)
        if not compressed_map and not any(t in result["headers"].get("content-type", "")
                   for t in ["text/", "application/xhtml", "application/xml", "application/json"]):
            raise ValueError("Expected a text/html or sitemap page")
        if any(t in result['headers'].get('content-type', '') for t in ('text/html', 'application/xhtml')):
            self.last_document = result
        return result["url"], result["body"].decode(result["encoding"], errors="replace"), result["status"]

    async def robots(self, website):
        root = urlunsplit((*urlsplit(website)[:2], "/", "", ""))
        _, robots, status = await self.get(urljoin(root, "robots.txt"), domain_of(website))
        parser = RobotFileParser()
        parser.parse(robots.splitlines() if status != 404 else [])
        self.request_delays[domain_of(website)] = robots_request_delay(parser, self.settings.crawler_user_agent)
        delay = max(self.settings.crawl_delay_seconds,
                    robots_request_delay(parser, self.settings.crawler_user_agent))
        return parser, delay, root

    async def crawl(self, website, *, seed_urls=None, follow_links=True, continuation=None):
        if self.signal_only:
            raise ValueError("Signal snapshots cannot perform a company crawl")
        # Separate pools per real hostname: two hosts sharing a pinned IP must not reuse SNI/TLS sessions.
        self.clients = {}
        try:
            return await self._crawl(website, seed_urls=seed_urls, follow_links=follow_links, continuation=continuation)
        finally:
            await asyncio.gather(*(client.aclose() for client in self.clients.values()))
            self.clients = None

    async def _crawl(self, website, *, seed_urls=None, follow_links=True, continuation=None):
        started = time.monotonic()
        website = crawl_url(website)
        domain = domain_of(website)
        if continuation:
            if continuation.get('checkpoint', {}).get('website') != website:
                raise ValueError('No matching crawl checkpoint; refresh this older capture first')
            self.report = json.loads(json.dumps(continuation))
            if self.settings.crawl_adaptive_pacing:
                self.adaptive_delays = {d: max(self.settings.crawl_delay_seconds,
                    min(self.settings.crawl_adaptive_max_delay_seconds, timestamp(v.get('delay_seconds'))))
                    for d, v in self.report.get('throttle', {}).items()}
        if continuation_wait((continuation or {}).get('checkpoint', {})):
            raise ValueError('Crawl cooldown is active; continue after the saved retry time')
        def activity(stage, url):
            self.report['activity'] = {'stage': stage, 'url': url, 'started_at': time.time()}
        activity('robots', website)
        try:
            parser, delay, root = await self.robots(website)
        except httpx.HTTPStatusError as exc:
            wait = retry_after_seconds(exc.response.headers)
            if exc.response.status_code in {429, 503} and wait:
                cp = self.report.setdefault('checkpoint', {
                    'website': website, 'frontier': [{'url': website, 'depth': 0}]})
                cp['domain_not_before'] = time.time()+wait
                if self.on_checkpoint:
                    self.on_checkpoint(self.report)
            raise
        if not seed_urls and not continuation and not parser.can_fetch(self.settings.crawler_user_agent, website):
            raise ValueError("No accessible homepage: robots denies research")
        pending, known, seen, pages, depth_limited = [], set(), set(), [], set()
        captured, attempted = set(), 0
        retryable_failure = None
        serial = 0
        category_counts = {}
        retry_urls, retry_sitemaps, inflight, sitemap_inflight, domain_not_before = {}, {}, None, None, 0
        def queue(url, depth):
            nonlocal serial
            try:
                url = company_crawl_url(url, domain)
            except ValueError:
                return
            if not url or url in known or url in seen or len(known) >= 10000:
                return
            known.add(url)
            serial += 1
            heapq.heappush(pending, (-1 if url == website else priority(url), depth, serial, url))
        previous_attempts = 0
        if continuation:
            checkpoint = continuation.get('checkpoint', {})
            if checkpoint.get('website') != website:
                raise ValueError('No matching crawl checkpoint; refresh this older capture first')
            self.report.setdefault('resume_history', []).append({'at': time.time(), 'previous_status': self.report['status'],
                                                               'previous_pages': len(self.report['pages'])})
            self.report['status'] = 'running'
            previous_attempts = self.report.get('attempted', len(self.report['pages']))
            # Restore only validated company URLs. Pages already captured stay
            # current and are never counted/fetched a second time in this pass.
            captured = {crawl_url(p['url']) for p in self.report['pages'] if domain_of(p['url']) == domain}
            seen = {crawl_url(u) for u in checkpoint.get('seen', []) if domain_of(u) == domain} | captured
            domain_not_before = timestamp(checkpoint.get('domain_not_before'))
            for entry in checkpoint.get('retry_urls', [])[:10000]:
                try:
                    url = company_crawl_url(entry['url'], domain)
                    depth, failures = int(entry['depth']), int(entry['failures'])
                except (ValueError, TypeError, KeyError):
                    continue
                if url and url not in captured and 0 <= depth <= self.settings.crawl_max_depth and 1 <= failures <= self.settings.crawl_resume_max_retries:
                    retry_urls[url] = {'url': url, 'depth': depth, 'failures': failures,
                                       'not_before': timestamp(entry.get('not_before'))}
                    if retry_urls[url]['not_before'] <= time.time():
                        seen.discard(url)
                        queue(url, depth)
            interrupted = checkpoint.get('inflight')
            if interrupted:
                try:
                    url = company_crawl_url(interrupted['url'], domain)
                    depth = int(interrupted['depth'])
                except (ValueError, TypeError, KeyError):
                    url, depth = '', -1
                if url and url not in captured and 0 <= depth <= self.settings.crawl_max_depth:
                    seen.discard(url)
                    queue(url, depth)
            for entry in checkpoint.get('frontier', []):
                if 0 <= entry['depth'] <= self.settings.crawl_max_depth:
                    queue(entry['url'], entry['depth'])
            sitemap_queue = list(checkpoint.get('sitemap_queue', []))
            sitemap_seen = set(checkpoint.get('sitemap_seen', []))
            for entry in checkpoint.get('retry_sitemaps', [])[:10000]:
                try:
                    url, failures = normalize_url(entry['url']), int(entry['failures'])
                except (ValueError, TypeError, KeyError):
                    continue
                if self.settings.crawl_max_sitemaps and domain_of(url) == domain and 1 <= failures <= self.settings.crawl_resume_max_retries:
                    retry_sitemaps[url] = {'url': url, 'failures': failures, 'not_before': timestamp(entry.get('not_before'))}
                    if retry_sitemaps[url]['not_before'] <= time.time():
                        sitemap_seen.discard(url)
                        if url not in sitemap_queue:
                            sitemap_queue.insert(0, url)
            if checkpoint.get('sitemap_inflight') and self.settings.crawl_max_sitemaps:
                try:
                    url = normalize_url(checkpoint['sitemap_inflight'])
                except ValueError:
                    url = ''
                if url and domain_of(url) == domain:
                    sitemap_seen.discard(url)
                    if url not in sitemap_queue:
                        sitemap_queue.insert(0, url)
            depth_limited = set(checkpoint.get('depth_limited', []))
        else:
            for url in seed_urls or [website]:
                queue(url, 0)
            sitemap_queue = (parser.site_maps() or [urljoin(root, "sitemap.xml")]) if follow_links else []
            sitemap_seen = set()
        def checkpoint_now():
            self.report.update(attempted=previous_attempts+attempted, pass_attempted=attempted)
            self.report['checkpoint'] = {'website': website,
                'frontier': [{'url': u, 'depth': d} for _, d, _, u in sorted(pending) if u not in seen],
                'seen': sorted(seen), 'sitemap_queue': sitemap_queue[:10000] if self.settings.crawl_max_sitemaps else [],
                'sitemap_seen': sorted(sitemap_seen), 'depth_limited': sorted(depth_limited)[:10000],
                'retry_urls': list(retry_urls.values()), 'inflight': inflight,
                'retry_sitemaps': list(retry_sitemaps.values()), 'sitemap_inflight': sitemap_inflight,
                'domain_not_before': domain_not_before}
            if self.on_checkpoint:
                self.on_checkpoint(self.report)
        checkpoint_now()
        last_request = time.monotonic()
        async def paced():
            nonlocal last_request
            interval = max(delay, self.adaptive_delays.get(domain, 0))
            await asyncio.sleep(max(0, interval - (time.monotonic() - last_request)))
            last_request = time.monotonic()
        sitemap_attempts = 0
        async def expand_sitemap():
            nonlocal sitemap_attempts, domain_not_before, sitemap_inflight
            sitemap = sitemap_queue.pop(0)
            if sitemap in sitemap_seen or domain_of(sitemap) != domain:
                return
            sitemap_seen.add(sitemap)
            if not parser.can_fetch(self.settings.crawler_user_agent, sitemap):
                retry_sitemaps.pop(sitemap, None)
                self.report['skipped'].append({'url': sitemap, 'reason': 'robots', 'kind': 'sitemap'})
                return
            sitemap_attempts += 1
            sitemap_inflight = sitemap
            checkpoint_now()
            try:
                activity('sitemap', sitemap)
                await paced()
                _, xml, code = await self.get(sitemap, domain)
                if code == 404:
                    retry_sitemaps.pop(sitemap, None)
                    for skipped in self.report['skipped']:
                        if skipped.get('url') == sitemap and skipped.get('retryable'):
                            skipped['resolved_at'] = time.time()
                    return
                tree = ET.fromstring(xml)
                retry_sitemaps.pop(sitemap, None)
                for skipped in self.report['skipped']:
                    if skipped.get('url') == sitemap and skipped.get('retryable'):
                        skipped['resolved_at'] = time.time()
                locations = [node.text.strip() for node in tree.iter()
                             if node.tag.rsplit("}", 1)[-1] == "loc" and node.text]
                self.report["sitemaps"].append({"url": sitemap, "urls": len(locations)})
                if tree.tag.rsplit("}", 1)[-1] == "sitemapindex":
                    sitemap_queue.extend(locations[:1000])
                    # Contact/company pages before large blog archives; the same
                    # sitemap budget remains available for deep research.
                    sitemap_queue.sort(key=lambda u: (0 if re.search(r'page|contact|product|collection', urlsplit(u).path, re.I) else 1))
                else:
                    for item in locations:
                        queue(item, 1)
            except (ValueError, httpx.HTTPError, ET.ParseError, OSError) as exc:
                recoverable = transient_failure(exc)
                self.report["skipped"].append({"url": sitemap, "reason": type(exc).__name__, "kind": "sitemap", 'retryable': recoverable,
                                               'http_status': exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None})
                if recoverable:
                    failures = retry_sitemaps.get(sitemap, {}).get('failures', 0)+1
                    wait = max(min(30*2**min(failures-1, 10), 3600),
                               retry_after_seconds(exc.response.headers) if isinstance(exc, httpx.HTTPStatusError) else 0)
                    if failures <= self.settings.crawl_resume_max_retries:
                        retry_sitemaps[sitemap] = {'url': sitemap, 'failures': failures, 'not_before': time.time()+wait}
                    else:
                        retry_sitemaps.pop(sitemap, None)
                        self.report['skipped'][-1]['retry_exhausted'] = True
                else:
                    retry_sitemaps.pop(sitemap, None)
                if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in {429, 503}:
                    wait = retry_after_seconds(exc.response.headers)
                    if wait:
                        domain_not_before = max(domain_not_before, time.time()+wait)
            finally:
                import sys
                if not isinstance(sys.exception(), asyncio.CancelledError):
                    sitemap_inflight = None
                checkpoint_now()
        renderer = None
        if self.settings.browser_enabled and self.settings.crawl_render_mode != "never":
            from .browser import RenderSession
            renderer = RenderSession(self)
            try:
                await renderer.start()
            except Exception as exc:
                await renderer.close()
                renderer = None
                self.report["errors"].append({"url": website, "stage": "browser_start", "reason": type(exc).__name__})
        try:
            while (pending or (sitemap_queue and sitemap_attempts < self.settings.crawl_max_sitemaps)) and attempted < self.settings.crawl_max_pages:
                # Persist homepage/contact evidence before optional discovery
                # work, then interleave map expansion with page captures.
                if sitemap_queue and sitemap_attempts < self.settings.crawl_max_sitemaps and (attempted >= 2 or not pending):
                    await expand_sitemap()
                if domain_not_before > time.time():
                    break
                if not pending:
                    continue
                _, depth, _, url = heapq.heappop(pending)
                if url in seen:
                    continue
                if not parser.can_fetch(self.settings.crawler_user_agent, url):
                    retry_urls.pop(url, None)
                    self.report["skipped"].append({"url": url, "reason": "robots"})
                    continue
                category = priority(url)
                # Reserve research depth for announcements as well as catalog/service pages.
                # A large product catalog cannot consume the entire budget before news is inspected.
                soft_quota = max(2, self.settings.crawl_max_pages // 5)
                if category_counts.get(category, 0) >= soft_quota and pending:
                    unsaturated = next((entry for entry in pending
                                        if category_counts.get(priority(entry[3]), 0) < soft_quota), None)
                    if unsaturated:
                        heapq.heappush(pending, (category + 10, depth, serial + 1, url))
                        serial += 1
                        continue
                seen.add(url)
                attempted += 1
                category_counts[category] = category_counts.get(category, 0) + 1
                inflight = {'url': url, 'depth': depth}
                checkpoint_now()
                try:
                    activity('http', url)
                    page_started = time.monotonic()
                    await paced()
                    final, html, code = await self.get(url, domain)
                    document = self.last_document
                    http_seconds = time.monotonic()-page_started
                    if urlsplit(url).fragment:
                        final = crawl_url(final + "#" + urlsplit(url).fragment)
                    if code == 404:
                        self.report["errors"].append({"url": url, "reason": "not_found"})
                        continue
                    final = crawl_url(final)
                    seen.add(final)
                    if final in captured:
                        retry_urls.pop(url, None)
                        self.report["skipped"].append({"url": url, "reason": "duplicate_redirect", "target": final})
                        continue
                    page = extract_page(final, html)
                    page["rendered"] = False
                    dynamic = len(page["text"]) < 500 or bool(re.search(
                        r'id=[\"\'](?:root|app|__next)[\"\']|__NEXT_DATA__|ng-version|type=[\"\']module', html, re.I))
                    should_render = self.settings.crawl_render_mode != 'never' and (
                        self.settings.crawl_render_mode == "always" or dynamic or priority(url) == 0)
                    if renderer and should_render:
                        activity('render', final)
                        render_started = time.monotonic()
                        await paced()
                        rendered = await renderer.render(final, domain, parser, document=document)
                        if rendered["html"]:
                            from .source_versions import retain_http_publications
                            page = retain_http_publications(extract_page(rendered['url'], rendered['html']), page)
                            page["rendered"] = True
                            page["visual"] = rendered["visual"]
                        page['render_seconds'] = round(time.monotonic()-render_started, 3)
                        page['document_reused'] = rendered.get('document_reused', False)
                        if rendered["issues"]:
                            self.report["errors"].append({"url": url, "stage": "render", "issues": rendered["issues"]})
                    elif should_render:
                        self.report["errors"].append({"url": url, "stage": "render", "reason": "renderer_unavailable_or_disabled"})
                    if not page["text"]:
                        self.report["errors"].append({"url": url, "reason": "empty_content"})
                        continue
                    if re.search(r"just a moment|access denied|verify you are human|checking your browser|captcha|attention required.*cloudflare",
                                 page["title"], re.I):
                        self.report["errors"].append({"url": url, "reason": "access_challenge_requires_manual_review"})
                        continue
                    page_url = crawl_url(page["url"])
                    seen.add(page_url)
                    if page_url in captured:
                        retry_urls.pop(url, None)
                        self.report["skipped"].append({"url": url, "reason": "duplicate_rendered_url", "target": page_url})
                        continue
                    captured.add(page_url)
                    retry_urls.pop(url, None)
                    for error in self.report['errors']:
                        if error.get('url') == url and error.get('retryable'):
                            error['resolved_at'] = time.time()
                    pages.append(page)
                    self.report.setdefault('first_page_seconds', round(time.monotonic()-started, 3))
                    self.report["pages"].append({"url": page["url"], "rendered": page["rendered"],
                                                  "emails": len(page["emails"]), "text_chars": len(page["text"]),
                                                  "contacts": page.get("contacts", []),
                                                  "review_candidates": page.get("review_candidates", []),
                                                  "visual": page.get("visual", {})})
                    self.report['pages'][-1].update(http_seconds=round(http_seconds, 3),
                                                    render_seconds=page.get('render_seconds', 0),
                                                    document_reused=page.get('document_reused', False))
                    from .professionals import sourced_profile_links
                    self.report['pages'][-1].update(sha256=page['sha256'],professional_links=sourced_profile_links(page),
                                                 named_people=page.get('named_people', []),
                                                 http_publication_retained=page.get('http_publication_retained', False),
                                                 http_navigation_retained=page.get('http_navigation_retained', False),
                                                 http_navigation_links=page.get('http_navigation_links', []),
                                                 capture_sources=page.get('capture_sources', []))
                    if page.get("canonical") and domain_of(page["canonical"]) == domain:
                        seen.add(crawl_url(page["canonical"]))
                    if follow_links and depth < self.settings.crawl_max_depth:
                        for link in page["links"]:
                            queue(link, depth + 1)
                    elif follow_links:
                        depth_limited.update(link for link in page["links"]
                                             if domain_of(link) == domain and link not in known and not SKIP_PATH.search(link))
                    if self.on_page:
                        activity('save', page_url)
                        await self.on_page(page, self.report)
                except (ValueError, httpx.HTTPError, OSError) as exc:
                    recoverable = transient_failure(exc)
                    error = {"url": url, "stage": "fetch", "reason": type(exc).__name__, 'retryable': recoverable,
                             'http_status': exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None}
                    self.report['errors'].append(error)
                    if recoverable:
                        retryable_failure = exc
                        failures = retry_urls.get(url, {}).get('failures', 0)+1
                        wait = max(min(30 * 2**min(failures-1, 10), 3600),
                                   retry_after_seconds(exc.response.headers) if isinstance(exc, httpx.HTTPStatusError) else 0)
                        if failures <= self.settings.crawl_resume_max_retries:
                            retry_urls[url] = {'url': url, 'depth': depth, 'failures': failures,
                                               'not_before': time.time()+wait}
                        else:
                            retry_urls.pop(url, None)
                            error['retry_exhausted'] = True
                        if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in {429, 503}:
                            origin_wait = retry_after_seconds(exc.response.headers)
                            if origin_wait:
                                domain_not_before = max(domain_not_before, time.time()+origin_wait)
                    else:
                        retry_urls.pop(url, None)
                finally:
                    # Cancellation keeps this request recoverable. Evidence save
                    # happens before clearing the durable in-flight marker.
                    import sys
                    if not isinstance(sys.exception(), asyncio.CancelledError):
                        inflight = None
                    checkpoint_now()
                if domain_not_before > time.time():
                    break
        finally:
            if renderer:
                await renderer.close()
        remaining = len({entry[3] for entry in pending if entry[3] not in seen} | set(retry_urls))
        maps_remaining = len({s for s in sitemap_queue if s not in sitemap_seen and domain_of(s) == domain} | set(retry_sitemaps)) if self.settings.crawl_max_sitemaps else 0
        map_failures = any(s.get('kind') == 'sitemap' and not s.get('resolved_at') for s in self.report['skipped'])
        checkpoint_now()
        policy_skips = any(s.get('reason') == 'robots' for s in self.report['skipped'])
        self.report.update({"status": "partial" if current_errors(self.report) or remaining or depth_limited or maps_remaining or map_failures or policy_skips else "complete",
                            "attempted": previous_attempts + attempted, 'pass_attempted': attempted, "remaining": remaining,
                            'sitemaps_remaining': maps_remaining, 'seconds': round(time.monotonic()-started, 3),
                            "depth_limited_urls": len(depth_limited),
                            "scope": {"domain": domain, "max_pages": self.settings.crawl_max_pages,
                                      "max_depth": self.settings.crawl_max_depth, "render_mode": self.settings.crawl_render_mode,
                                      'seeded_only': not follow_links},
                            "retry_pending": len(retry_urls), 'sitemap_retry_pending': len(retry_sitemaps), 'domain_not_before': domain_not_before,
                            "budget_reached": any(e[3] not in seen for e in pending) or bool(depth_limited) or bool(maps_remaining), "finished_at": time.time()})
        if not pages and not captured:
            if retryable_failure:
                # Preserve the temporary provider failure for the worker's
                # bounded retry lane instead of converting it into a terminal
                # "no pages" error. Permanent denials still require review.
                raise retryable_failure
            raise ValueError("No accessible pages; robots or missing content may prevent research")
        return pages


def outreach_email_allowed(email):
    """Dedicated privacy/security/automated inboxes are not sales outreach routes."""
    local = email.split('@', 1)[0].split('+', 1)[0].lower()
    compact = re.sub(r'[-._]', '', local)
    return (not compact.startswith(('noreply', 'privacy', 'abuse', 'dataprotection'))
            and compact not in {'dpo', 'gdpr', 'postmaster', 'security', 'compliance', 'dmca'})


def extract_page(url, html):
    from .people import people_from_html
    named_people = people_from_html(url, html)
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else domain_of(url)
    links, contacts, review_candidates, structured = [], {}, {}, []
    def candidate(value, method, name="", role=""):
        value = unquote(str(value)).removeprefix("mailto:").split("?")[0].strip(" .,;:")
        try:
            email = normalize_email(value)
            host = email.split("@")[1]
            if not outreach_email_allowed(email):
                return
            same_domain = host == domain_of(url) or host.endswith("." + domain_of(url))
            target = contacts if same_domain else review_candidates
            entry = target.setdefault(email, {"email": email, "name": "", "role": "",
                                                 "source_url": url, "methods": []})
            if not same_domain:
                entry.update(review_required=True, reason="Different email domain: company ownership and relevance are unconfirmed")
            if method not in entry["methods"]:
                entry["methods"].append(method)
            if name and not entry["name"]:
                entry["name"] = str(name)[:150]
            if role and not entry["role"]:
                entry["role"] = str(role)[:150]
        except ValueError:
            pass
    def walk(item):
        if isinstance(item, list):
            for child in item:
                walk(child)
        elif isinstance(item, dict):
            kind = item.get("@type", "")
            is_person = kind == "Person" or isinstance(kind, list) and "Person" in kind
            if isinstance(item.get("email"), str):
                candidate(item["email"], "json_ld", item.get("name", "") if is_person else "",
                          item.get("jobTitle", "") if is_person else "")
            for key in ("name", "jobTitle", "description", "address", "datePublished", "headline"):
                if isinstance(item.get(key), str):
                    structured.append(f"{key}: {item[key]}")
            for child in item.values():
                if isinstance(child, (dict, list)):
                    walk(child)
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            walk(json.loads(script.string or script.get_text()))
        except (ValueError, TypeError, RecursionError):
            pass
    for node in soup.select("[data-cfemail]"):
        try:
            encoded = bytes.fromhex(node["data-cfemail"])
            candidate(bytes(b ^ encoded[0] for b in encoded[1:]).decode(), "cloudflare_obfuscation")
        except (ValueError, IndexError, UnicodeError):
            pass
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        if href.lower().startswith("mailto:"):
            for address in unquote(href[7:]).split("?")[0].split(","):
                candidate(address, "mailto")
        elif href.startswith(("#/", "#!/")) or not href.lower().startswith(("#", "javascript:", "tel:", "data:")):
            try:
                links.append(crawl_url(urljoin(url, href)))
            except ValueError:
                pass
    canonical = soup.find("link", rel="canonical", href=True)
    canonical_url = ""
    if canonical:
        try:
            canonical_url = crawl_url(urljoin(url, canonical["href"]))
        except ValueError:
            pass
    for node in soup(["script", "style", "noscript", "svg"]):
        node.decompose()
    text = soup.get_text(" ", strip=True)
    for address in re.findall(EMAIL_RE, text):
        candidate(address, "visible_text")
    deobfuscated = re.sub(r"\s*\[at\]\s*|\s*\(at\)\s*", "@", text, flags=re.I)
    deobfuscated = re.sub(r"\s*\[dot\]\s*|\s*\(dot\)\s*", ".", deobfuscated, flags=re.I)
    for address in re.findall(EMAIL_RE, deobfuscated):
        candidate(address, "visible_obfuscation")
    if structured:
        text += "\nStructured public metadata: " + " | ".join(dict.fromkeys(structured))[:6000]
    person_metadata = [p['quote'] for p in named_people if p['method'] == 'official_json_ld_person']
    if person_metadata:
        text += "\nNamed-person public metadata: " + " | ".join(dict.fromkeys(person_metadata))[:14000]
    for email, entry in (contacts | review_candidates).items():
        associations = [p for p in named_people if any(v['email'] == email for v in p.get('email_publications', []))]
        entry['named_associations'] = associations
        # A shared staff/office inbox cannot identify an individual recipient.
        if len({p['name'] for p in associations}) > 1:
            entry.update(name='', role='')
        elif associations and not entry['name']:
            entry.update(name=associations[0]['name'], role=associations[0]['role'])
    return {"url": url, "title": title[:250], "text": text[:48000], "emails": sorted(contacts),
            "contacts": list(contacts.values()), "review_candidates": list(review_candidates.values()), "canonical": canonical_url,
            "links": list(dict.fromkeys(links)), "sha256": hashlib.sha256(html.encode()).hexdigest(),
            "named_people": named_people}
