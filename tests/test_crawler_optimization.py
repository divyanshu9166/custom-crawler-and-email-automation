import asyncio
import json
import time
from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import httpx
import pytest

from outreach.browser import RenderSession
from outreach.web import PublicWeb, extract_page


def response(url, status=200, headers=None, body=b'<h1>Public company</h1>'):
    return {'url': url, 'status': status, 'headers': headers or {'content-type': 'text/html'}, 'body': body, 'encoding': 'utf-8'}


async def test_home_and_contact_saved_before_optional_maps_and_map_errors_stay_partial(settings, monkeypatch):
    settings.browser_enabled = False
    settings.crawl_delay_seconds = .001
    calls, saved = [], []
    async def get(self, url, expected_domain=None):
        path = urlsplit(url).path
        calls.append(path)
        if path == '/robots.txt':
            return url, 'User-agent: *\nAllow: /\nSitemap: https://bright-demo.com/maps.xml', 200
        if path == '/maps.xml':
            assert saved == ['/', '/contact']
            raise httpx.ReadTimeout('Slow optional sitemap')
        if path == '/':
            return url, '<h1>Company</h1><a href="/contact">Contact</a>', 200
        return url, '<p>Email hello@bright-demo.com</p>', 200
    async def save(page, report):
        saved.append(urlsplit(page['url']).path)
        assert report['first_page_seconds'] >= 0
    monkeypatch.setattr(PublicWeb, 'get', get)
    crawler = PublicWeb(settings, on_page=save)
    pages = await crawler.crawl('https://bright-demo.com/')
    assert len(pages) == 2 and calls.index('/contact') < calls.index('/maps.xml')
    assert crawler.report['status'] == 'partial' and crawler.report['seconds'] >= 0


@pytest.mark.parametrize('status', [401, 403, 404, 410])
async def test_permanent_http_failure_not_hammered(settings, monkeypatch, status):
    calls = []
    async def resource(self, url, expected_domain=None, **kwargs):
        calls.append(url)
        return response(url, status)
    monkeypatch.setattr(PublicWeb, 'resource', resource)
    crawler = PublicWeb(settings)
    if status in {404, 410}:
        assert (await crawler.get('https://bright-demo.com/'))[2] == 404
    else:
        with pytest.raises(httpx.HTTPStatusError):
            await crawler.get('https://bright-demo.com/')
    assert len(calls) == 1 and not crawler.report.get('retried_requests')


async def test_transient_get_retry_preserves_usable_document(settings, monkeypatch):
    calls, waits = [], []
    async def resource(self, url, expected_domain=None, **kwargs):
        calls.append(url)
        return response(url, 503 if len(calls) == 1 else 200)
    async def sleep(delay):
        waits.append(delay)
    monkeypatch.setattr(PublicWeb, 'resource', resource)
    monkeypatch.setattr('outreach.web.asyncio.sleep', sleep)
    crawler = PublicWeb(settings)
    assert (await crawler.get('https://bright-demo.com/'))[2] == 200
    assert len(calls) == 2 and waits == [1]
    assert crawler.last_document['status'] == 200
    assert crawler.report['retried_requests'][0]['reason'] == 'http_503'


async def test_long_retry_after_is_not_ignored(settings, monkeypatch):
    calls = []
    async def resource(self, url, expected_domain=None, **kwargs):
        calls.append(url)
        return response(url, 429, {'content-type': 'text/html', 'retry-after': '120'})
    monkeypatch.setattr(PublicWeb, 'resource', resource)
    with pytest.raises(httpx.HTTPStatusError) as caught:
        await PublicWeb(settings).get('https://bright-demo.com/')
    assert caught.value.response.status_code == 429 and len(calls) == 1
    assert caught.value.response.headers['retry-after'] == '120'


async def test_no_page_transient_failure_remains_retryable(settings, monkeypatch):
    settings.browser_enabled = False
    settings.crawl_delay_seconds = .001
    settings.crawl_http_retries = 0
    async def resource(self, url, expected_domain=None, **kwargs):
        if url.endswith('/robots.txt'):
            return response(url, body=b'User-agent: *\nAllow: /')
        return response(url, 404 if url.endswith('/sitemap.xml') else 503)
    monkeypatch.setattr(PublicWeb, 'resource', resource)
    crawler = PublicWeb(settings)
    with pytest.raises(httpx.HTTPStatusError) as caught:
        await crawler.crawl('https://bright-demo.com/')
    assert caught.value.response.status_code == 503 and not crawler.report['pages']


async def test_worker_honors_retry_after_beyond_its_default_backoff(db, settings, monkeypatch):
    from outreach import worker
    async def research(*args):
        raise httpx.HTTPStatusError('Busy', request=httpx.Request('GET', 'https://bright-demo.com/'),
                                   response=httpx.Response(429, headers={'retry-after': '900'}))
    monkeypatch.setattr(worker, 'research_lead', research)
    jid = db.enqueue('research', {'lead_id': 1})
    started = time.time()
    await worker.execute_job(db, settings, db.claim({'research'}))
    assert db.one('SELECT due_at FROM jobs WHERE id=?', (jid,))['due_at'] >= started+900


async def test_trickling_body_has_total_deadline_not_only_per_chunk_timeout(settings, monkeypatch):
    settings.crawl_request_timeout_seconds = .05
    settings.crawl_http_retries = 0
    closed = []
    class Body(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'<h1>Never finished'
            await asyncio.sleep(10)
        async def aclose(self):
            closed.append(True)
    async def ip(host):
        return '93.184.215.14'
    def handle(request):
        return httpx.Response(200, headers={'content-type': 'text/html'}, stream=Body())
    original = httpx.AsyncClient
    monkeypatch.setattr('outreach.web.public_ip', ip)
    monkeypatch.setattr('outreach.web.httpx.AsyncClient', lambda **kwargs: original(transport=httpx.MockTransport(handle), **kwargs))
    started = time.monotonic()
    with pytest.raises(TimeoutError):
        await PublicWeb(settings).get('https://bright-demo.com/')
    assert time.monotonic()-started < 1 and closed


async def test_challenge_page_is_not_evidence_or_contact(settings, monkeypatch):
    settings.browser_enabled = False
    settings.crawl_delay_seconds = .001
    saved = []
    async def get(self, url, expected_domain=None):
        if url.endswith('/robots.txt'):
            return url, 'User-agent: *\nAllow: /', 200
        if url.endswith('/sitemap.xml'):
            return url, '', 404
        return url, '<title>Verify you are human</title><p>trap@bright-demo.com</p>', 200
    async def save(page, report):
        saved.append(page)
    monkeypatch.setattr(PublicWeb, 'get', get)
    crawler = PublicWeb(settings, on_page=save)
    with pytest.raises(ValueError, match='No accessible pages'):
        await crawler.crawl('https://bright-demo.com/')
    assert not saved and not crawler.report['pages']
    assert any(e['reason'] == 'access_challenge_requires_manual_review' for e in crawler.report['errors'])


@pytest.mark.parametrize('status,state', [(403, 'failed'), (503, 'pending')])
async def test_worker_distinguishes_permanent_and_temporary_failures(db, settings, monkeypatch, status, state):
    from outreach import worker
    async def research(*args):
        raise httpx.HTTPStatusError('Blocked', request=httpx.Request('GET', 'https://bright-demo.com/'), response=httpx.Response(status))
    monkeypatch.setattr(worker, 'research_lead', research)
    jid = db.enqueue('research', {'lead_id': 1})
    job = db.claim({'research'})
    await worker.execute_job(db, settings, job)
    assert db.one('SELECT state FROM jobs WHERE id=?', (jid,))['state'] == state
    assert json.loads(db.one("SELECT detail FROM events WHERE kind='job_failed'")['detail'])['will_retry'] == (state == 'pending')


async def test_seeded_document_executes_slow_content_without_waiting_for_background_image(settings, monkeypatch):
    settings.browser_settle_seconds = .1
    calls = []
    url = 'https://bright-demo.com/'
    document = response(url, body=b'<title>Public SPA</title><div id="app"></div><img src="/slow.jpg"><script>fetch("/data").then(r=>r.text()).then(t=>document.querySelector("#app").innerHTML=t)</script>')
    async def resource(self, url, expected_domain=None, **kwargs):
        calls.append(url)
        if url.endswith('/slow.jpg'):
            await asyncio.sleep(20)
        if url.endswith('/data'):
            await asyncio.sleep(1.1)
            return response(url, body=b'<p>Published email alex@bright-demo.com</p>')
        raise AssertionError('Initial document must not be fetched twice')
    monkeypatch.setattr(PublicWeb, 'resource', resource)
    robots = RobotFileParser()
    robots.parse(['User-agent: *', 'Allow: /'])
    renderer = RenderSession(PublicWeb(settings))
    started = time.monotonic()
    try:
        await renderer.start()
        result = await renderer.render(url, 'bright-demo.com', robots, document=document)
    finally:
        await renderer.close()
    assert result['document_reused'] and url not in calls
    assert extract_page(result['url'], result['html'])['emails'] == ['alex@bright-demo.com']
    assert time.monotonic()-started < 10
    assert any(i['reason'] == 'resource_requests_pending_at_snapshot' for i in result['issues'])


async def test_wrong_url_document_is_not_reused(settings, monkeypatch):
    settings.browser_settle_seconds = .1
    calls = []
    async def resource(self, url, expected_domain=None, **kwargs):
        calls.append(url)
        return response(url, body=b'<title>Correct site</title><p>Correct content</p>')
    monkeypatch.setattr(PublicWeb, 'resource', resource)
    robots = RobotFileParser()
    robots.parse(['User-agent: *', 'Allow: /'])
    renderer = RenderSession(PublicWeb(settings))
    try:
        await renderer.start()
        result = await renderer.render('https://bright-demo.com/', 'bright-demo.com', robots,
                                       document=response('https://wrong.example.com/', body=b'<h1>Wrong company</h1>'))
    finally:
        await renderer.close()
    assert not result['document_reused'] and 'https://bright-demo.com/' in calls
    assert 'Correct content' in result['html'] and 'Wrong company' not in result['html']
