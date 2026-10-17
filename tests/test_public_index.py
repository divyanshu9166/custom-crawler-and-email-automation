import asyncio
import json
import time

import httpx
import pytest

from outreach import providers, public_index, professionals
from outreach.discovery import indexed_exclusion, company_title, official_root


@pytest.mark.parametrize('row,expected', [
    ({'url': 'https://linkedin.com/in/alex', 'title': 'Bright Demo Founder'}, True),
    ({'url': 'https://linkedin.com/in/alex', 'title': 'Other Company Founder'}, False),
    ({'url': 'https://notlinkedin.com/in/alex', 'title': 'Bright Demo Founder'}, False),
    ({'url': 'https://linkedin.com/company/bright', 'title': 'Bright Demo Founder'}, False),
    ({'url': 'https://uk.linkedin.com/in/alex', 'snippet': 'Bright Demo marketing'}, True),
])
def test_ignored_search_operators_do_not_admit_wrong_company_or_route(row, expected):
    assert providers.indexed_constraints('site:linkedin.com/in/ "Bright Demo"', row) is expected


@pytest.mark.parametrize('query,url,expected', [
    ('"Alex Doe" -site:linkedin.com', 'https://bright-demo.com/team', True),
    ('"Alex Doe" -site:linkedin.com', 'https://uk.linkedin.com/in/alex', False),
    ('"Alex Doe" -site:linkedin.com', 'https://notlinkedin.com/team', True),
    ('"Alex Doe" -site:linkedin.com -site:x.com -site:twitter.com', 'https://bright-demo.com/team', True),
    ('"Alex Doe" -site:linkedin.com -site:x.com -site:twitter.com', 'https://x.com/alex', False),
    ('"Alex Doe" site:bright-demo.com -site:linkedin.com', 'https://bright-demo.com/team', True),
    ('"Alex Doe" site:bright-demo.com -site:linkedin.com', 'https://other-demo.com/team', False),
    ('"Alex Doe" -site:linkedin.com/in/', 'https://linkedin.com/company/bright', True),
    ('"Alex Doe" (site:bright-demo.com OR site:other-demo.com)', 'https://other-demo.com/team', True),
    ('"Alex Doe" (site:bright-demo.com OR site:other-demo.com)', 'https://unrelated-demo.com/team', False),
])
def test_negative_site_operator_excludes_its_host_without_requiring_it(query, url, expected):
    assert providers.indexed_constraints(query, {'url': url, 'title': 'Alex Doe, Director'}) is expected


async def test_realistic_negative_site_search_keeps_company_page_and_rejects_platform(settings, monkeypatch):
    async def search(*args, **kw):
        return providers.SearchRows([{'url': 'https://bright-demo.com/team', 'title': 'Alex Doe, Director'},
                                    {'url': 'https://linkedin.com/in/alex', 'title': 'Alex Doe, Director'}])
    monkeypatch.setattr(providers, '_discover_once', search)
    rows = await providers.discover(settings, '"Alex Doe" -site:linkedin.com', include_platforms=True)
    assert [r['url'] for r in rows] == ['https://bright-demo.com/team']
    assert rows.provider_reports[0]['rejected_constraints'] == 1


async def test_partial_default_search_merges_alternate_engines_and_records_provenance(settings, monkeypatch):
    settings.search_fallback_engines = 'yahoo,mojeek'
    settings._discovery_state['next'] = {'searxng:yahoo,mojeek': 0}
    calls = []
    async def search(s, q, limit, include, engines):
        calls.append(engines)
        return providers.SearchRows([{'url': 'https://bright-demo.com/', 'title': 'Bright Demo', 'engines': [engines or 'default']}],
                                    [['google', 'denied']] if not engines else [])
    monkeypatch.setattr(providers, '_discover_once', search)
    rows = await providers.discover(settings, '"Bright Demo"')
    assert calls == ['', 'yahoo,mojeek'] and len(rows) == 1
    assert rows.engine_issues == [['google', 'denied']]
    assert len(rows.provider_reports) == 2
    again = await providers.discover(settings, '"Bright Demo"')
    assert calls == ['', 'yahoo,mojeek'] and all(r['cached'] for r in again.provider_reports)
    again[0]['title'] = 'changed'
    assert (await providers.discover(settings, '"Bright Demo"'))[0]['title'] == 'Bright Demo'


async def test_unrelated_http_success_triggers_fallback_instead_of_fake_lead_yield(settings, monkeypatch):
    settings.search_fallback_engines = 'yahoo'
    calls = []
    async def search(s, q, limit, include, engines):
        calls.append(engines)
        return providers.SearchRows([{'url': 'https://example.com/', 'title': 'Dictionary'}] if not engines else
                                   [{'url': 'https://bright-demo.com/', 'title': 'UK dental clinic'}])
    monkeypatch.setattr(providers, '_discover_once', search)
    rows = await providers.discover(settings, 'UK dental clinics')
    assert calls == ['', 'yahoo'] and len(rows) == 1
    assert rows.provider_reports[0]['rejected_constraints'] == 1


async def test_primary_transport_failure_does_not_disable_separate_engine_group(settings, monkeypatch):
    settings.search_fallback_engines = 'yahoo'
    async def search(s, q, limit, include, engines):
        if not engines:
            raise httpx.ConnectError('offline')
        return providers.SearchRows([{'url': 'https://bright-demo.com/', 'title': 'Bright Demo'}])
    monkeypatch.setattr(providers, '_discover_once', search)
    result = await providers.discover(settings, '"Bright Demo"')
    assert len(result) == 1 and result.provider_reports[0]['state'] == 'unavailable'


async def test_rate_limit_cooldown_shared_across_queries_and_no_challenge_retry(settings):
    count = 0
    async def fail():
        nonlocal count
        count += 1
        response = httpx.Response(429, headers={'retry-after': '600'}, request=httpx.Request('GET', 'https://index.commoncrawl.org/'))
        response.raise_for_status()
    a = await public_index.cached_lookup(settings, 'a', 'service', fail, 900)
    b = await public_index.cached_lookup(settings.model_copy(), 'b', 'service', fail, 900)
    assert count == 1 and a['http_status'] == 429 and b['state'] == 'cooldown'
    assert b['retry_at'] > time.time() + 590


async def test_concurrent_identical_index_requests_are_coalesced(settings):
    count = 0
    async def fetch():
        nonlocal count
        count += 1
        await asyncio.sleep(0)
        return {'state': 'available', 'rows': [{'url': 'https://bright-demo.com/contact'}]}
    a, b = await asyncio.gather(*(public_index.cached_lookup(settings, 'same', 'cc', fetch, 900) for _ in range(2)))
    assert count == 1 and a['cached'] is False and b['cached'] is True


async def test_archive_domain_hints_are_filtered_cached_and_never_email_publication(settings, monkeypatch):
    settings.commoncrawl_hints_enabled = True
    calls = []
    async def get(url, params=None, maximum=1_000_000):
        calls.append((url, params))
        if url.endswith('collinfo.json'):
            return json.dumps([{'id': 'https://evil.example'}, {'id': 'CC-MAIN-2026-39'}]).encode()
        assert params['page'] == '0' and params['pageSize'] == '1'
        values = [{'url': u, 'timestamp': '20260907122447', 'status': '200', 'email': 'archive@bright-demo.com'} for u in
                  ['https://bright-demo.com/contact', 'https://bright-demo.com/about', 'https://evil.example/contact',
                   'https://bright-demo.com/cart', 'https://bright-demo.com/products/contact-lenses',
                   'https://private.bright-demo.com/team', 'http://127.0.0.1/contact']]
        return '\n'.join(json.dumps(r) for r in values).encode()
    monkeypatch.setattr(public_index, 'bounded_get', get)
    hints = await public_index.commoncrawl_routes(settings, 'https://bright-demo.com/')
    assert {h['url'] for h in hints['rows']} == {'https://bright-demo.com/contact', 'https://bright-demo.com/about'}
    assert not any(h['current_publication'] for h in hints['rows']) and 'archive@' not in json.dumps(hints)
    assert (await public_index.commoncrawl_routes(settings, 'https://bright-demo.com/'))['cached']
    assert len(calls) == 2


async def test_missing_archive_domain_is_not_a_global_service_failure(settings, monkeypatch):
    settings.commoncrawl_hints_enabled = True
    async def get(url, params=None, maximum=1_000_000):
        if url.endswith('collinfo.json'):
            return b'[{"id":"CC-MAIN-2026-39"}]'
        httpx.Response(404, request=httpx.Request('GET', url)).raise_for_status()
    monkeypatch.setattr(public_index, 'bounded_get', get)
    result = await public_index.commoncrawl_routes(settings, 'https://bright-demo.com/')
    assert result['state'] == 'available' and not result['rows'] and not settings._discovery_state['holds']


@pytest.mark.parametrize('status,body', [(302, b''), (200, b'x' * 101)])
async def test_index_transport_rejects_redirects_and_oversized_decoded_body(monkeypatch, status, body):
    original = httpx.AsyncClient
    monkeypatch.setattr(public_index.httpx, 'AsyncClient', lambda **kw: original(
        transport=httpx.MockTransport(lambda r: httpx.Response(status, content=body, headers={'location':'https://evil.example/'})), **kw))
    with pytest.raises((ValueError, httpx.HTTPStatusError)):
        await public_index.bounded_get('https://index.commoncrawl.org/collinfo.json', maximum=100)


async def test_person_company_mismatch_is_rejected_even_from_adapter_override(db, settings, prepared, monkeypatch):
    async def search(*args, **kw):
        return [{'url': 'https://linkedin.com/in/other', 'title': 'Other Company CEO'}]
    async def fail(*args, **kw):
        pytest.fail('Unrelated professional must not be fetched')
    settings.discovery_query_delay_seconds = 0.001
    monkeypatch.setattr(providers, 'discover', search)
    monkeypatch.setattr(professionals, 'profile_snapshot', fail)
    result = await professionals.research_professionals(db, settings, prepared['lead_id'])
    assert not result['captures'] and all(q['rejected_company_mismatch'] == 1 for q in result['queries'])
    assert not db.one("SELECT 1 FROM jobs WHERE kind='verify'")


async def test_current_official_navigation_fills_profile_budget_without_index_or_email_import(db, settings, prepared, monkeypatch):
    from outreach import discovery
    settings.professional_refresh_official_links = True
    settings.professional_max_profiles = 1
    async def page(s, url):
        return {'state': 'captured', 'url': url, 'sha256': 'current',
                'public_links': ['https://linkedin.com/in/alex'], 'published_emails': ['business@bright-demo.com']}
    async def profile(s, url):
        return {'state': 'robots_denied', 'url': url}
    async def forbidden(*args, **kw):
        pytest.fail('Observed official profile fills budget')
    monkeypatch.setattr(discovery, 'public_snapshot', page)
    monkeypatch.setattr(professionals, 'profile_snapshot', profile)
    monkeypatch.setattr(providers, 'discover', forbidden)
    result = await professionals.research_professionals(db, settings, prepared['lead_id'])
    assert result['captures'][0]['state'] == 'robots_denied'
    assert result['official_link_refresh'][0]['professional_links'] == ['https://www.linkedin.com/in/alex']
    assert not result['queries'] and not db.one("SELECT 1 FROM contacts WHERE email='business@bright-demo.com'")


@pytest.mark.parametrize('title,snippet', [
    ('34 Best Austin Roofers', 'Residential roof inspections'),
    ('20 Best Austin Roofing Companies', 'Replacement costs'),
    ('Best Portland Coffee Roasters As Told By a Coffee Snob', 'Coffee shops'),
    ('Dental Clinics in London', 'Our directory includes 480 verified listings in London'),
])
def test_live_editorial_and_directory_results_cannot_be_company_candidates(title, snippet):
    assert indexed_exclusion({'url': 'https://listing-demo.com/', 'title': title, 'snippet': snippet})


@pytest.mark.parametrize('host', ['angi.com', 'treatwell.co.uk', 'dentaly.org', 'roastlocal.com'])
def test_observed_listing_hosts_are_not_imported_as_official_company_domains(host):
    with pytest.raises(ValueError):
        official_root('https://' + host + '/listing')


def test_query_name_uses_published_brand_segment_instead_of_order_call_to_action():
    assert company_title('Order Coffee Online | Portland Coffee Roasters') == 'Portland Coffee Roasters'
    assert company_title('Heart Coffee Roasters') == 'Heart Coffee Roasters'
    assert not indexed_exclusion({'url': 'https://roofer-demo.com/', 'title': 'Top Roofers in Austin, TX'})
