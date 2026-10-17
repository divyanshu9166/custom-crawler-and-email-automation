"""Recovery must add real source evidence while preserving access and send gates."""
import json
import time

import httpx
import pytest

from outreach import providers
from outreach.contact_recovery import research_contacts
from outreach.research import add_lead, fresh_evidence, research_lead, verify_contact
from outreach.web import PublicWeb


async def fixture_site(self, url, expected_domain=None):
    if url.endswith('/robots.txt'):
        return url, 'User-agent: *\nAllow: /', 200
    if url.endswith('/sitemap.xml'):
        return url, '', 404
    html = '<title>Recovery fixture</title><p>UK business information</p>'
    if url.endswith('/'):
        html += '<a href="/contact">Contact</a><a href="/services">Services</a><a href="/team">Team</a>'
    if url.endswith('/contact'):
        html += '<p>hello@bright-demo.com</p>'
    return url, html, 200


async def test_continue_crawl_preserves_current_pages_and_does_not_refetch_captured(db, settings, monkeypatch):
    settings.browser_enabled = False
    settings.crawl_delay_seconds = .001
    settings.crawl_max_pages = 2
    calls = []
    async def get(*args):
        calls.append(args[1])
        return await fixture_site(*args)
    monkeypatch.setattr(PublicWeb, 'get', get)
    lid = add_lead(db, 'Recovery fixture', 'https://bright-demo.com/', 'A', 'https://bright-demo.com/')
    await research_lead(db, settings, lid)
    first = fresh_evidence(db, lid)
    old_ids = {p['id'] for p in first}
    assert len(first) == 2
    row = db.one('SELECT * FROM crawls WHERE lead_id=?', (lid,))
    assert json.loads(row['report'])['checkpoint']['frontier']
    calls.clear()
    await research_lead(db, settings, lid, continuation=True)
    current = fresh_evidence(db, lid)
    assert len(current) == 4 and old_ids.issubset({p['id'] for p in current})
    assert not any(p['url'] in calls for p in first)
    assert db.one('SELECT COUNT(*) n FROM crawls')['n'] == 1
    final = json.loads(db.one('SELECT report FROM crawls')['report'])
    assert len(final['pages']) == 4 and final['attempted'] == 4
    assert final['resume_history'] and not final['checkpoint']['frontier']
    assert not db.all('SELECT * FROM messages')


async def test_seeded_contact_capture_honors_robots_without_following_catalog(settings, monkeypatch):
    settings.browser_enabled = False
    settings.crawl_delay_seconds = .001
    calls = []
    async def get(self, url, expected_domain=None):
        calls.append(url)
        if url.endswith('/robots.txt'):
            return url, 'User-agent: *\nDisallow: /\nAllow: /contact', 200
        assert url.endswith('/contact')
        return url, '<p>hello@bright-demo.com</p><a href="/private">Private</a>', 200
    monkeypatch.setattr(PublicWeb, 'get', get)
    crawler = PublicWeb(settings)
    pages = await crawler.crawl('https://bright-demo.com/', seed_urls=['https://bright-demo.com/contact',
                                'https://bright-demo.com/private', 'https://foreign-demo.com/contact'], follow_links=False)
    assert len(pages) == 1 and pages[0]['emails'] == ['hello@bright-demo.com']
    assert not any('foreign-demo' in u or u.endswith('/private') for u in calls)
    assert crawler.report['scope']['seeded_only'] is True


async def test_contact_recovery_corroborates_official_html_not_indexed_email(db, settings, prepared, monkeypatch):
    settings.browser_enabled = False
    settings.crawl_delay_seconds = .001
    settings.discovery_query_delay_seconds = .001
    async def search(*_, **__):
        return [{'url': 'https://bright-demo.com/contact', 'title': 'Contact team', 'snippet': 'guessed@bright-demo.com'},
                {'url': 'https://www.linkedin.com/company/bright-demo', 'title': 'Bright Demo', 'snippet': 'external@bright-demo.com'}]
    monkeypatch.setattr(providers, 'discover', search)
    monkeypatch.setattr(PublicWeb, 'get', fixture_site)
    before = len(fresh_evidence(db, prepared['lead_id']))
    result = await research_contacts(db, settings, prepared['lead_id'])
    addresses = {r['email'] for r in db.all('SELECT email FROM contacts')}
    assert result['state'] == 'partial' and result['pages_saved'] == 1
    assert 'hello@bright-demo.com' in addresses and 'guessed@bright-demo.com' not in addresses
    assert 'external@bright-demo.com' not in addresses
    assert len(fresh_evidence(db, prepared['lead_id'])) == before+1
    assert all(h['review_required'] for h in result['indexed_hints'])
    assert db.all('SELECT * FROM messages')  # Existing fictional drafts preserved, no send.
    assert not db.one("SELECT 1 FROM messages WHERE state IN ('sent','sending')")


async def test_contact_recovery_no_official_url_holds_all_social_hints(db, settings, prepared, monkeypatch):
    settings.browser_enabled = False
    settings.crawl_delay_seconds = .001
    settings.discovery_query_delay_seconds = .001
    async def search(*_, **__):
        return [{'url': 'https://x.com/example_fixture', 'title': 'Example fixture', 'snippet': 'guessed@bright-demo.com'}]
    calls = []
    async def get(self, url, expected_domain=None):
        calls.append(url)
        assert 'x.com' not in url
        if url.endswith('/robots.txt'):
            return url, 'User-agent: *\nDisallow: /', 200
        pytest.fail('Denied homepage cannot be fetched')
    monkeypatch.setattr(providers, 'discover', search)
    monkeypatch.setattr(PublicWeb, 'get', get)
    result = await research_contacts(db, settings, prepared['lead_id'])
    assert result['state'] == 'held' and result['pages_saved'] == 0
    assert result['navigation_fallback'] and calls == ['https://bright-demo.com/robots.txt']
    assert db.one('SELECT COUNT(*) n FROM contacts')['n'] == 1


@pytest.mark.parametrize('index_failed', [False, True])
async def test_contact_recovery_uses_official_navigation_when_search_is_unavailable(db, settings, prepared, monkeypatch, index_failed):
    settings.browser_enabled = False
    settings.crawl_delay_seconds = .001
    settings.discovery_query_delay_seconds = .001
    settings.contact_research_max_pages = 2
    async def search(*_, **__):
        if index_failed:
            raise httpx.ConnectError('Unavailable search fixture')
        return []
    monkeypatch.setattr(providers, 'discover', search)
    monkeypatch.setattr(PublicWeb, 'get', fixture_site)
    result = await research_contacts(db, settings, prepared['lead_id'])
    assert result['navigation_fallback'] and result['state'] == 'partial'
    assert result['pages_saved'] == 2 and result['crawl']['budget_reached']
    assert result['crawl']['attempted'] == 2 and result['crawl']['sitemaps'] == []
    assert db.one("SELECT source_url,verification FROM contacts WHERE email='hello@bright-demo.com'") == {
        'source_url': 'https://bright-demo.com/contact', 'verification': 'unverified'}
    assert not db.one("SELECT 1 FROM messages WHERE state IN ('sent','sending')")


async def test_contact_recovery_refreshes_saved_contact_page_without_index_or_homepage_access(db, settings, prepared, monkeypatch):
    settings.browser_enabled = False
    settings.crawl_delay_seconds = .001
    settings.discovery_query_delay_seconds = .001
    lid = prepared['lead_id']
    db.execute('INSERT INTO evidence(lead_id,url,title,text,sha256,fetched_at) VALUES(?,?,?,?,?,?)',
               (lid, 'https://bright-demo.com/contact', 'Contact', 'No email in old capture', 'old', time.time()))
    calls = []
    async def search(*_, **__):
        return []
    async def get(self, url, expected_domain=None):
        calls.append(url)
        if url.endswith('/robots.txt'):
            return url, 'User-agent: *\nDisallow: /\nAllow: /contact', 200
        assert url.endswith('/contact')
        return await fixture_site(self, url, expected_domain)
    monkeypatch.setattr(providers, 'discover', search)
    monkeypatch.setattr(PublicWeb, 'get', get)
    result = await research_contacts(db, settings, lid)
    assert result['state'] == 'partial' and result['pages_saved'] == 1
    assert result['seed_sources'] == [{'url': 'https://bright-demo.com/contact', 'origins': ['saved_official_page']}]
    assert not result['navigation_fallback'] and db.one("SELECT 1 FROM contacts WHERE email='hello@bright-demo.com'")
    assert 'https://bright-demo.com/' not in calls


async def test_contact_recovery_uses_checkpoint_contact_route_and_skips_unsafe_index_routes(db, settings, prepared, monkeypatch):
    settings.browser_enabled = False
    settings.crawl_delay_seconds = .001
    settings.discovery_query_delay_seconds = .001
    lid = prepared['lead_id']
    checkpoint = {'website': 'https://bright-demo.com/', 'frontier': [
        {'url': url, 'depth': 1} for url in ['https://bright-demo.com/contact',
            'https://bright-demo.com/account/contact', 'https://foreign-demo.com/contact']]}
    report = {'status': 'partial', 'checkpoint': checkpoint}
    db.execute('INSERT INTO crawls(lead_id,report,created_at) VALUES(?,?,?)', (lid, json.dumps(report), time.time()-1))
    async def search(*_, **__):
        return [{'url': 'https://bright-demo.com/checkout/contact', 'snippet': '', 'title': 'Contact'},
                {'url': 'https://bright-demo.com/contact', 'snippet': 'guessed@bright-demo.com', 'title': 'Contact'}]
    monkeypatch.setattr(providers, 'discover', search)
    monkeypatch.setattr(PublicWeb, 'get', fixture_site)
    result = await research_contacts(db, settings, lid)
    assert result['pages_saved'] == 1 and result['seed_sources'] == [{
        'url': 'https://bright-demo.com/contact', 'origins': ['saved_official_navigation', 'search_index']}]
    assert not db.one("SELECT 1 FROM contacts WHERE email='guessed@bright-demo.com'")


async def test_legacy_partial_crawl_adopts_only_fresh_official_links(db, settings, prepared, monkeypatch):
    settings.browser_enabled = False
    settings.crawl_delay_seconds = .001
    settings.discovery_query_delay_seconds = .001
    lid = prepared['lead_id']
    original = {'status': 'partial', 'pages': [{'url': 'https://bright-demo.com/'}], 'errors': [], 'skipped': [], 'sitemaps': []}
    db.execute('INSERT INTO crawls(lead_id,report,created_at) VALUES(?,?,?)', (lid, json.dumps(original), time.time()-2))
    async def search(*_, **__):
        return [{'url': 'https://bright-demo.com/contact', 'title': 'Contact', 'snippet': ''}]
    async def get(self, url, expected_domain=None):
        if url.endswith('/robots.txt'):
            return await fixture_site(self, url, expected_domain)
        return url, '<p>Public company team</p><a href="/team">Team</a><a href="/checkout">Checkout</a><a href="https://foreign-demo.com/">Foreign</a>', 200
    monkeypatch.setattr(providers, 'discover', search)
    monkeypatch.setattr(PublicWeb, 'get', get)
    assert (await research_contacts(db, settings, lid))['pages_saved'] == 1
    report = json.loads(db.one('SELECT report FROM crawls')['report'])
    assert report['checkpoint']['frontier'] == [{'url': 'https://bright-demo.com/team', 'depth': 1}]
    assert report['checkpoint']['origin'].startswith('Newly captured official')
    assert len(fresh_evidence(db, lid)) == 2 and report['status'] == 'partial'


@pytest.mark.parametrize('irrelevant_route', ['blogs/about-skincare', 'blogs/news/meet-the-team',
                                           'products/contact-lenses', 'collections/team-shirts'])
async def test_contact_fallback_does_not_refresh_editorial_or_catalog_urls_as_contact_pages(db, settings, prepared, monkeypatch, irrelevant_route):
    settings.browser_enabled = False
    settings.crawl_delay_seconds = .001
    settings.discovery_query_delay_seconds = .001
    settings.contact_research_max_pages = 2
    url = 'https://bright-demo.com/'+irrelevant_route
    db.execute('INSERT INTO evidence(lead_id,url,title,text,sha256,fetched_at) VALUES(?,?,?,?,?,?)',
               (prepared['lead_id'], url, 'Editorial fixture', 'Not a contact route', 'old', time.time()))
    calls = []
    async def get(*args):
        calls.append(args[1])
        return await fixture_site(*args)
    async def search(*_, **__):
        return []
    monkeypatch.setattr(providers, 'discover', search)
    monkeypatch.setattr(PublicWeb, 'get', get)
    result = await research_contacts(db, settings, prepared['lead_id'])
    assert result['navigation_fallback'] and url not in calls
    assert db.one("SELECT 1 FROM contacts WHERE email='hello@bright-demo.com'")


async def test_automatic_contact_research_queued_after_full_research(db, settings, monkeypatch):
    settings.auto_contact_research = True
    settings.browser_enabled = False
    settings.crawl_delay_seconds = .001
    settings.crawl_max_pages = 1
    monkeypatch.setattr(PublicWeb, 'get', fixture_site)
    lid = add_lead(db, 'Recovery fixture', 'https://bright-demo.com/', 'A', 'https://bright-demo.com/')
    await research_lead(db, settings, lid)
    assert db.one("SELECT payload FROM jobs WHERE kind='contact_research'")['payload'] == json.dumps({'lead_id': lid}, sort_keys=True)


def test_contact_research_serializes_with_other_same_company_browser_work(db):
    db.enqueue('research', {'lead_id': 1})
    assert db.claim({'research'})
    db.enqueue('contact_research', {'lead_id': 1})
    other = db.enqueue('contact_research', {'lead_id': 2})
    assert db.claim({'contact_research'})['id'] == other


def test_contact_research_running_visible_on_both_maps(db, settings, prepared):
    from outreach.workflow import snapshot
    from outreach.workflow_detail import detailed_snapshot
    db.enqueue('contact_research', {'lead_id': prepared['lead_id']})
    db.claim({'contact_research'})
    overview = snapshot(db, settings, prepared['lead_id'])
    detail = detailed_snapshot(db, settings, prepared['lead_id'])
    assert next(n for n in overview['nodes'] if n['id'] == 'website')['state'] == 'running'
    assert next(n for n in detail['nodes'] if n['id'] == 'E')['state'] == 'running'


@pytest.mark.parametrize('status,body', [(404, {}), (403, {}), (200, {'input': 'wrong', 'is_reachable': 'invalid'}), (400, {})])
async def test_wrong_verifier_never_receives_real_recipient(db, settings, prepared, monkeypatch, status, body):
    submitted = []
    def handler(request):
        submitted.append(json.loads(request.content)['to_email'])
        return httpx.Response(status, json=body)
    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))
    async def dns(_):
        return {'mx_records': ['mx.fixture.example'], 'mailbox_exists': None, 'safe': False}
    monkeypatch.setattr(providers, 'dns_precheck', dns)
    db.set('last_verification_attempt', time.time()-100)
    with pytest.raises(providers.VerificationUnavailable):
        await verify_contact(db, settings, prepared['contact_id'])
    contact = db.one('SELECT * FROM contacts WHERE id=?', (prepared['contact_id'],))
    raw = json.loads(contact['verification_raw'])
    assert submitted == ['invalid-address-without-at-sign']
    assert contact['verification'] == 'unknown' and raw['provider_status']['dns_precheck']['safe'] is False


@pytest.mark.parametrize('status', [200, 400, 422])
async def test_reacher_invalid_syntax_contract_recognized(settings, monkeypatch, status):
    original = httpx.AsyncClient
    def handler(request):
        return httpx.Response(status, json={'input': 'invalid-address-without-at-sign', 'is_reachable': 'invalid'})
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: original(transport=httpx.MockTransport(handler), **kwargs))
    assert (await providers.reacher_readiness(settings))['ready'] is True


def test_recovery_api_requires_auth_and_rejects_missing_checkpoint(settings, prepared, db):
    from fastapi.testclient import TestClient
    from outreach.app import create_app
    client = TestClient(create_app(settings))
    assert client.get('/api/providers/reacher').status_code == 401
    headers = {'Authorization': 'Bearer '+settings.api_token}
    assert client.post(f"/api/leads/{prepared['lead_id']}/continue-research", headers=headers).status_code == 400
    result = client.post(f"/api/leads/{prepared['lead_id']}/contact-research", headers=headers)
    assert result.status_code == 200 and db.one("SELECT 1 FROM jobs WHERE kind='contact_research'")


@pytest.mark.parametrize('mode', ['null_mx', 'nxdomain', 'timeout'])
async def test_dns_fallback_never_establishes_mailbox_exists(monkeypatch, mode):
    import dns.asyncresolver
    import dns.exception
    from types import SimpleNamespace
    class Resolver:
        async def resolve(self, *_, **__):
            if mode == 'nxdomain':
                raise dns.asyncresolver.NXDOMAIN()
            if mode == 'timeout':
                raise dns.exception.Timeout()
            return [SimpleNamespace(exchange='.')]
    monkeypatch.setattr(dns.asyncresolver, 'Resolver', Resolver)
    result = await providers.dns_precheck('hello@bright-demo.com')
    assert result['safe'] is False and result['mailbox_exists'] is None
