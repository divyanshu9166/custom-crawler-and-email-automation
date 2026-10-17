"""Recover transient contact failures without losing sources or ignoring cooldowns."""
import asyncio
import gzip
import json
import time
from urllib.parse import urlsplit

import httpx
import pytest

from outreach.crawl_state import continuation_wait, current_errors
from outreach.research import add_lead, research_checkpoint, research_lead
from outreach.research_status import snapshot
from outreach.web import PublicWeb, company_crawl_url, sitemap_body


def fail(url, code=503, headers=None):
    return httpx.HTTPStatusError('Temporary failure', request=httpx.Request('GET', url),
                                response=httpx.Response(code, headers=headers))


def setup(settings):
    settings.browser_enabled = False
    settings.crawl_render_mode = 'never'
    settings.crawl_delay_seconds = .001
    settings.crawl_max_sitemaps = 0
    settings.crawl_max_pages = 10


async def test_failed_contact_is_durable_and_recovered_without_refetching_evidence(db, settings, monkeypatch):
    setup(settings)
    calls, broken = [], True
    async def get(self, url, expected_domain=None):
        calls.append(url)
        path = urlsplit(url).path
        if path == '/robots.txt':
            return url, 'User-agent: *\nAllow: /', 200
        if path == '/contact' and broken:
            raise fail(url)
        return url, ('<p>London company</p><a href="/contact">Contact</a>' if path == '/' else
                     '<p>London team hello@bright-demo.com</p>'), 200
    monkeypatch.setattr(PublicWeb, 'get', get)
    lid = add_lead(db, 'Bright', 'https://bright-demo.com/', 'A', 'https://bright-demo.com/')
    await research_lead(db, settings, lid)
    evidence = db.one('SELECT * FROM evidence')
    first = db.one('SELECT * FROM crawls')
    report = json.loads(first['report'])
    assert report['remaining'] == report['retry_pending'] == 1
    assert report['checkpoint']['retry_urls'][0]['failures'] == 1
    assert not report['checkpoint']['frontier'] and not report['checkpoint']['inflight']
    # An otherwise exhausted crawl cannot busy-loop the failed contact URL.
    with pytest.raises(ValueError, match='cooldown'):
        research_checkpoint(db, lid)
    report['checkpoint']['retry_urls'][0]['not_before'] = 0
    db.execute('UPDATE crawls SET report=?', (json.dumps(report),))
    calls.clear()
    broken = False
    await research_lead(db, settings, lid, continuation=True)
    final = json.loads(db.one('SELECT report FROM crawls')['report'])
    assert calls == ['https://bright-demo.com/robots.txt', 'https://bright-demo.com/contact']
    assert db.one('SELECT id FROM evidence WHERE url=?', (evidence['url'],))['id'] == evidence['id']
    assert db.one('SELECT COUNT(*) n FROM evidence')['n'] == 2
    assert db.one('SELECT COUNT(*) n FROM crawls')['n'] == 1
    assert db.one('SELECT COUNT(*) n FROM contacts')['n'] == 1
    assert final['status'] == 'complete' and not final['checkpoint']['retry_urls']
    assert len(final['errors']) == 1 and not current_errors(final)
    status = snapshot(db, lid)['leads'][0]
    assert status['crawl_issues'] == 0 and status['resolved_crawl_issues'] == 1
    assert not db.all('SELECT * FROM messages')


@pytest.mark.parametrize('code', [403, 404, 410])
async def test_permanent_failure_is_not_automatically_retried(settings, monkeypatch, code):
    setup(settings)
    async def get(self, url, expected_domain=None):
        if url.endswith('/robots.txt'):
            return url, 'User-agent: *\nAllow: /', 200
        if url.endswith('/contact'):
            if code in {404, 410}:
                return url, '', 404
            raise fail(url, code)
        return url, '<p>Company</p><a href="/contact">Contact</a>', 200
    monkeypatch.setattr(PublicWeb, 'get', get)
    crawler = PublicWeb(settings)
    await crawler.crawl('https://bright-demo.com/')
    assert not crawler.report['checkpoint']['retry_urls']
    assert crawler.report['status'] == 'partial'


async def test_continuation_retries_exhaust_bounded_attempts(settings, monkeypatch):
    setup(settings)
    calls = []
    async def get(self, url, expected_domain=None):
        if url.endswith('/robots.txt'):
            return url, 'User-agent: *\nAllow: /', 200
        if url.endswith('/contact'):
            calls.append(url)
            raise httpx.ReadTimeout('temporary')
        return url, '<p>Company</p><a href="/contact">Contact</a>', 200
    monkeypatch.setattr(PublicWeb, 'get', get)
    crawler = PublicWeb(settings)
    await crawler.crawl('https://bright-demo.com/')
    for _ in range(settings.crawl_resume_max_retries):
        report = json.loads(json.dumps(crawler.report))
        report['checkpoint']['retry_urls'][0]['not_before'] = 0
        crawler = PublicWeb(settings)
        await crawler.crawl('https://bright-demo.com/', continuation=report)
    assert len(calls) == 3
    assert crawler.report['errors'][-1]['retry_exhausted']
    assert not crawler.report['checkpoint']['retry_urls']


@pytest.mark.parametrize('where', ['robots', 'contact', 'sitemap'])
async def test_origin_cooldown_stops_other_requests_and_blocks_resume(settings, monkeypatch, where):
    setup(settings)
    settings.crawl_max_sitemaps = 2
    calls = []
    async def get(self, url, expected_domain=None):
        path = urlsplit(url).path
        calls.append(path)
        if path == '/robots.txt':
            if where == 'robots':
                raise fail(url, 429, {'Retry-After': '120'})
            return url, 'User-agent: *\nAllow: /', 200
        if (path == '/contact' and where == 'contact') or (path == '/sitemap.xml' and where == 'sitemap'):
            raise fail(url, 429, {'Retry-After': '120'})
        if path == '/sitemap.xml':
            return url, '', 404
        return url, '<p>Company</p><a href="/contact">Contact</a><a href="/services">Services</a>', 200
    monkeypatch.setattr(PublicWeb, 'get', get)
    crawler = PublicWeb(settings)
    if where == 'robots':
        with pytest.raises(httpx.HTTPStatusError):
            await crawler.crawl('https://bright-demo.com/')
    else:
        await crawler.crawl('https://bright-demo.com/')
        assert '/services' not in calls
    assert continuation_wait(crawler.report['checkpoint']) > 115
    calls.clear()
    with pytest.raises(ValueError, match='cooldown'):
        await PublicWeb(settings).crawl('https://bright-demo.com/', continuation=crawler.report)
    assert not calls


async def test_cancelled_inflight_page_is_persisted_and_recovered(db, settings, monkeypatch):
    setup(settings)
    interrupted = True
    async def get(self, url, expected_domain=None):
        if url.endswith('/robots.txt'):
            return url, 'User-agent: *\nAllow: /', 200
        if url.endswith('/contact') and interrupted:
            saved = json.loads(db.one('SELECT report FROM crawls')['report'])
            assert saved['checkpoint']['inflight']['url'] == url
            raise asyncio.CancelledError()
        return url, '<p>Company</p><a href="/contact">Contact</a>', 200
    monkeypatch.setattr(PublicWeb, 'get', get)
    lid = add_lead(db, 'Bright', 'https://bright-demo.com/', 'A', 'https://bright-demo.com/')
    with pytest.raises(asyncio.CancelledError):
        await research_lead(db, settings, lid)
    _, report = research_checkpoint(db, lid)
    assert report['checkpoint']['inflight']['url'].endswith('/contact')
    interrupted = False
    await research_lead(db, settings, lid, continuation=True)
    assert db.one('SELECT COUNT(*) n FROM evidence')['n'] == 2
    final = json.loads(db.one('SELECT report FROM crawls')['report'])
    assert not final['checkpoint']['inflight'] and final['status'] == 'complete'


def test_customer_login_flow_does_not_consume_company_research_budget():
    root = 'https://bright-demo.com'
    assert not company_crawl_url(root+'/customer_authentication/redirect?locale=en', 'bright-demo.com')
    assert not company_crawl_url(root+'/signin', 'bright-demo.com')
    assert company_crawl_url(root+'/customer-stories', 'bright-demo.com') == root+'/customer-stories'


async def test_wrong_checkpoint_never_requests_robots(settings, monkeypatch):
    setup(settings)
    async def get(*_):
        pytest.fail('Mismatched checkpoint must fail before network access')
    monkeypatch.setattr(PublicWeb, 'get', get)
    with pytest.raises(ValueError, match='matching'):
        await PublicWeb(settings).crawl('https://bright-demo.com/', continuation={'checkpoint': {'website': 'https://other-demo.com/'}})


def test_corrupt_gzip_crc_is_not_accepted_as_evidence():
    body = bytearray(gzip.compress(b'<urlset/>'))
    body[-8] ^= 255
    with pytest.raises(ValueError, match='Invalid gzip'):
        sitemap_body(bytes(body), 5000)


def test_retry_wait_is_per_url_unless_whole_origin_cooled():
    future = time.time()+300
    retry = {'url': 'https://bright-demo.com/contact', 'not_before': future}
    assert continuation_wait({'retry_urls': [retry]}) > 295
    assert continuation_wait({'retry_urls': [retry], 'frontier': [{'url': 'other'}]}) == 0
    assert continuation_wait({'domain_not_before': future, 'frontier': [{'url': 'other'}]}) > 295
    assert continuation_wait({'domain_not_before': 'nan'}) == 0


@pytest.mark.parametrize('members', [1, 2])
def test_file_gzip_is_bounded_and_supports_concatenated_members(members):
    raw = b'<urlset><url><loc>https://bright-demo.com/contact</loc></url></urlset>'
    body = gzip.compress(raw)*members
    assert sitemap_body(body, 5000) == raw*members
    with pytest.raises(ValueError, match='size limit'):
        sitemap_body(body, 20)
    with pytest.raises(ValueError, match='Incomplete|Invalid'):
        sitemap_body(body[:-4], 5000)
    with pytest.raises(ValueError, match='trailing'):
        sitemap_body(body+b'garbage', 5000)


@pytest.mark.parametrize('compressed', [True, False])
async def test_gzip_sitemap_links_reach_contacts_even_if_http_already_decoded(settings, monkeypatch, compressed):
    setup(settings)
    settings.crawl_max_sitemaps = 2
    xml = b'<urlset><url><loc>https://bright-demo.com/contact</loc></url></urlset>'
    async def resource(self, url, expected_domain=None):
        path = urlsplit(url).path
        if path == '/robots.txt':
            body, mime = b'User-agent: *\nAllow: /\nSitemap: https://bright-demo.com/site.xml.gz', 'text/plain'
        elif path == '/site.xml.gz':
            body, mime = gzip.compress(xml) if compressed else xml, 'application/gzip'
        else:
            body, mime = b'<p>Company hello@bright-demo.com</p>', 'text/html'
        return {'url': url, 'body': body, 'headers': {'content-type': mime}, 'status': 200, 'encoding': 'utf-8'}
    monkeypatch.setattr(PublicWeb, 'resource', resource)
    crawler = PublicWeb(settings)
    pages = await crawler.crawl('https://bright-demo.com/')
    assert {p['url'] for p in pages} == {'https://bright-demo.com/', 'https://bright-demo.com/contact'}
    assert crawler.report['sitemaps'][0]['urls'] == 1
