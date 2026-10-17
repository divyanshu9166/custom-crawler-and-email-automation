"""Restricted profiles never become access/e-mail proof through an index hint."""
import json
from urllib.parse import urlsplit

import pytest
from bs4 import BeautifulSoup

from outreach.discovery import brand_domain_candidate, name_matches, profile_key, public_snapshot, resolve_signal
from outreach.profile_resolution import organization_links, website_hints
from outreach.research import add_lead, research_lead
from outreach.web import PublicWeb


def test_explicit_urls_preserve_public_paths_but_email_domains_are_not_guessed():
    assert website_hints({'snippet': 'Contact sales@bright-demo.com or hello@other.co.uk'}) == []
    assert website_hints({'snippet': 'Visit https://bright-demo.com/contact. Or www.bright-demo.com/contact'}) == ['https://bright-demo.com/contact']
    assert not website_hints({'snippet': 'https://localhost/contact https://linkedin.com/company/bright https://bright-demo.com/account'})


def test_linkedin_suffix_spoof_does_not_match_locale_alias():
    assert profile_key('https://notlinkedin.com/company/bright') != profile_key('https://linkedin.com/company/bright')
    assert profile_key('https://uk.linkedin.com/company/bright/') == profile_key('https://www.linkedin.com/company/bright')


def test_accented_brand_names_still_require_every_identity_token():
    assert name_matches('Fonte Coffee', 'Font\u00e9 Coffee in Seattle')
    assert not name_matches('Fonte Coffee', 'Other Coffee in Seattle')


def test_only_own_organization_profile_links_are_used():
    body = '<script type="application/ld+json">'+json.dumps([
        {'@type': ['Organization'], 'url': 'https://bright-demo.com/', 'sameAs': ['https://linkedin.com/company/bright']},
        {'@type': 'Organization', 'url': 'https://foreign-demo.com/', 'sameAs': 'https://x.com/wrong'},
        {'@type': 'Person', 'sameAs': 'https://x.com/person'}])+'</script>'
    assert organization_links(BeautifulSoup(body, 'html.parser'), 'https://bright-demo.com/contact') == ['https://linkedin.com/company/bright']


def test_directory_entity_without_own_homepage_url_is_not_site_ownership():
    body = '<script type="application/ld+json">'+json.dumps({'@type': 'LocalBusiness',
        'name': 'Bright Studio', 'sameAs': 'https://linkedin.com/company/bright'})+'</script>'
    assert not organization_links(BeautifulSoup(body, 'html.parser'), 'https://directory-demo.com/business/bright')


def test_brand_subdomain_is_a_candidate_but_other_brand_label_is_not():
    assert brand_domain_candidate('MZ SKIN', 'https://try.mzskin.com/')
    assert brand_domain_candidate('Bright Studio', 'https://shop.brightstudio.co.uk/')
    assert not brand_domain_candidate('MZ SKIN', 'https://mzskinbeauty.shop/')


async def test_directory_leaf_backlink_does_not_compete_with_business_homepage(settings, monkeypatch):
    settings.discovery_query_delay_seconds = .001
    async def search(*_, **__):
        return [{'url': 'https://bright-demo.com/', 'title': 'Bright Studio'},
                {'url': 'https://directory-demo.com/business/bright', 'title': 'Bright Studio listing'}]
    async def snapshot(s, url, platform=False):
        if platform:
            return {'state': 'robots_denied'}
        directory_home = url == 'https://directory-demo.com/'
        return {'state': 'captured', 'url': url, 'title': 'Business Directory' if directory_home else 'Bright Studio',
                'text': 'Find businesses' if directory_home else 'Bright Studio in London', 'sha256': 'hash',
                'public_links': [] if directory_home else ['https://linkedin.com/company/bright']}
    monkeypatch.setattr('outreach.providers.discover', search)
    monkeypatch.setattr('outreach.discovery.public_snapshot', snapshot)
    result = await resolve_signal(settings, {'url': 'https://linkedin.com/company/bright', 'title': 'Bright Studio'}, 'UK', ['linkedin.com'])
    assert result['website'] == 'https://bright-demo.com/'
    assert result['state'] == 'reciprocal_profile_link_candidate'


async def test_blocked_profile_can_resolve_explicit_contact_hint_without_search_api(settings, monkeypatch):
    async def snapshot(s, url, platform=False):
        if platform:
            return {'state': 'robots_denied', 'url': url}
        assert url == 'https://bright-demo.com/contact'
        return {'state': 'captured', 'url': url, 'title': 'Bright Studio', 'text': 'Bright Studio in London',
                'sha256': 'hash', 'organization_profile_links': ['https://linkedin.com/company/bright']}
    async def no_search(*_, **__):
        pytest.fail('Corroborated explicit domain does not require another search API')
    monkeypatch.setattr('outreach.discovery.public_snapshot', snapshot)
    monkeypatch.setattr('outreach.providers.discover', no_search)
    result = await resolve_signal(settings, {'url': 'https://linkedin.com/company/bright', 'title': 'Bright Studio',
                                   'snippet': 'Visit https://bright-demo.com/contact'}, 'UK', ['linkedin.com'])
    assert result['website'] == 'https://bright-demo.com/'
    assert result['official_match_url'].endswith('/contact')
    assert result['public_snapshot']['state'] == 'robots_denied'
    assert result['indexed_signal_only'] and result['access_path'] == 'independent_public_sources'


async def test_reverse_profile_query_recovers_missed_brand_title(settings, monkeypatch):
    settings.discovery_query_delay_seconds = .001
    queries = []
    async def search(s, q, *_, **__):
        queries.append(q)
        if '-site:linkedin.com' in q:
            return [{'url': 'https://bright-demo.com/contact', 'title': 'Contact',
                     'snippet': 'https://linkedin.com/company/bright'}]
        return []
    async def snapshot(s, url, platform=False):
        if platform:
            return {'state': 'robots_denied'}
        return {'state': 'captured', 'url': url, 'title': 'Bright Studio', 'text': 'Bright Studio in London',
                'sha256': 'hash', 'organization_profile_links': ['https://linkedin.com/company/bright']}
    monkeypatch.setattr('outreach.providers.discover', search)
    monkeypatch.setattr('outreach.discovery.public_snapshot', snapshot)
    result = await resolve_signal(settings, {'url': 'https://linkedin.com/company/bright', 'title': 'Bright Studio'}, 'UK', ['linkedin.com'])
    assert len(queries) == 3 and result['website'] == 'https://bright-demo.com/'
    assert result['official_match_url'] == 'https://bright-demo.com/contact'


async def test_email_hint_and_unavailable_queries_remain_unresolved(settings, monkeypatch):
    settings.discovery_query_delay_seconds = .001
    async def search(*_, **__):
        raise TimeoutError()
    async def snapshot(*_, **__):
        return {'state': 'robots_denied'}
    monkeypatch.setattr('outreach.providers.discover', search)
    monkeypatch.setattr('outreach.discovery.public_snapshot', snapshot)
    result = await resolve_signal(settings, {'url': 'https://x.com/bright', 'title': 'Bright Studio',
                                   'snippet': 'Email hidden@bright-demo.com'}, 'UK', ['x.com'])
    assert not result['website'] and not result['indexed_website_hints']
    assert result['indexed_email_candidates'] == ['hidden@bright-demo.com']
    assert not result['website_search']['completed'] and len(result['website_search']['errors']) == 3


async def test_wrong_company_backlink_is_not_identity_match(settings, monkeypatch):
    settings.discovery_query_delay_seconds = .001
    async def search(*_, **__):
        return []
    async def snapshot(s, url, platform=False):
        return {'state': 'robots_denied'} if platform else {'state': 'captured', 'url': url,
            'title': 'Other Studio', 'text': 'Other Studio agency', 'sha256': 'hash',
            'public_links': ['https://x.com/bright']}
    monkeypatch.setattr('outreach.providers.discover', search)
    monkeypatch.setattr('outreach.discovery.public_snapshot', snapshot)
    result = await resolve_signal(settings, {'url': 'https://x.com/bright', 'title': 'Bright Studio',
                                   'snippet': 'https://other-demo.com/'}, 'UK', ['x.com'])
    assert not result['website']


async def test_partial_search_engines_do_not_establish_website_absence(settings, monkeypatch):
    from outreach.providers import SearchRows
    settings.discovery_query_delay_seconds = .001
    async def search(*_, **__):
        return SearchRows([], [{'engine': 'example', 'reason': 'unavailable'}])
    async def snapshot(*_, **__):
        return {'state': 'robots_denied'}
    monkeypatch.setattr('outreach.providers.discover', search)
    monkeypatch.setattr('outreach.discovery.public_snapshot', snapshot)
    result = await resolve_signal(settings, {'url': 'https://x.com/bright', 'title': 'Bright Studio'}, 'UK', ['x.com'])
    assert not result['website_search']['completed'] and result['website_search']['engine_issues']


async def test_seeded_official_contact_can_work_when_homepage_is_denied(db, settings, monkeypatch):
    settings.browser_enabled = False
    settings.crawl_render_mode = 'never'
    settings.crawl_delay_seconds = .001
    settings.crawl_max_sitemaps = 0
    calls = []
    async def get(self, url, expected_domain=None):
        calls.append(urlsplit(url).path)
        if url.endswith('/robots.txt'):
            return url, 'User-agent: *\nDisallow: /\nAllow: /contact', 200
        assert url.endswith('/contact')
        return url, '<title>Bright Studio</title><p>London business hello@bright-demo.com</p>', 200
    monkeypatch.setattr(PublicWeb, 'get', get)
    lid = add_lead(db, 'Bright Studio', 'https://bright-demo.com/', 'A', 'https://linkedin.com/company/bright')
    await research_lead(db, settings, lid, seed_urls=['https://bright-demo.com/contact', 'https://foreign-demo.com/contact'])
    assert '/' not in calls and '/contact' in calls
    assert db.one('SELECT COUNT(*) n FROM contacts')['n'] == 1
    assert db.one('SELECT source_url FROM contacts')['source_url'] == 'https://bright-demo.com/contact'
    assert json.loads(db.one('SELECT report FROM crawls')['report'])['status'] == 'partial'
    assert not db.all('SELECT * FROM messages')


async def test_dynamic_official_snapshot_renders_but_denied_profile_does_not(settings, monkeypatch):
    from outreach import browser
    class Robots:
        def can_fetch(self, *_):
            return True
    async def robots(*_):
        return Robots(), 0, 'https://bright-demo.com/'
    async def get(self, url, expected_domain=None):
        return url, '<title>Bright Studio</title><div id="app"></div>', 200
    started = []
    class Renderer:
        def __init__(self, web):
            pass
        async def start(self):
            started.append(True)
        async def render(self, url, *_args, **_kwargs):
            return {'url': url, 'html': '<title>Bright Studio</title><p>Bright Studio London services</p>', 'issues': []}
        async def close(self):
            pass
    monkeypatch.setattr(PublicWeb, 'robots', robots)
    monkeypatch.setattr(PublicWeb, 'get', get)
    monkeypatch.setattr(browser, 'RenderSession', Renderer)
    result = await public_snapshot(settings, 'https://bright-demo.com/')
    assert result['rendered'] and 'London services' in result['text']
    await public_snapshot(settings, 'https://x.com/bright', platform=True)
    assert len(started) == 1  # No alternate browser for platform restrictions.
