"""Discovery boundaries and optional-source failures must preserve useful research."""
import json

import pytest

from outreach import discovery, professionals
from outreach.profiles import canonical_profile


@pytest.mark.parametrize('path', [
    'Dazzle%20Office%20Cleaning%20Company%20London',
    'business.name', 'a' * 16, 'intent', 'tos', 'privacy', 'share', 'hashtag',
])
def test_invalid_x_routes_never_enter_business_or_professional_research(path):
    for host in ('x.com', 'twitter.com'):
        with pytest.raises(ValueError):
            canonical_profile(f'https://{host}/{path}')
        with pytest.raises(ValueError):
            professionals.professional_target(f'https://{host}/{path}')


@pytest.mark.parametrize('handle', ['p', 'Valid_Handle_15', 'a' * 15])
def test_valid_x_handles_keep_their_exact_identity(handle):
    assert canonical_profile('https://twitter.com/' + handle) == 'https://twitter.com/' + handle
    assert professionals.professional_target('https://twitter.com/' + handle)[1] == 'https://x.com/' + handle


async def test_malformed_observed_x_link_does_not_abort_other_profile_captures(db, settings, prepared, monkeypatch):
    lid = prepared['lead_id']
    page = db.one('SELECT * FROM evidence WHERE id=?', (prepared['evidence_id'],))
    valid = 'https://www.linkedin.com/in/alex-demo'
    invalid = 'https://x.com/Dazzle%20Office%20Cleaning%20Company%20London'
    db.execute('INSERT INTO crawls(lead_id,report,created_at) VALUES(?,?,?)',
        (lid, json.dumps({'pages': [{'url': page['url'], 'sha256': page['sha256'],
                                   'professional_links': [invalid, valid]}]}), page['fetched_at'] - 1))
    settings.platform_browser_enabled = True
    settings.platform_browser_public_fallback = False
    settings.linkedin_people_search_enabled = False
    settings.social_posts_enabled = False
    settings.fxembed_profiles_enabled = True
    visited = []

    async def snapshot(s, target):
        visited.append(target)
        if target == valid:
            return {'state': 'captured', 'url': target, 'title': 'Alex Demo', 'text': 'Founder at Bright Demo'}
        return {'state': 'browser_unavailable'}

    monkeypatch.setattr(professionals, 'profile_snapshot', snapshot)
    report = await professionals.research_professionals(db, settings, lid)
    assert visited == [valid]
    assert report['state'] == 'captured'
    assert len(report['captures']) == 1
    assert db.one("SELECT 1 FROM events WHERE kind='professional_research'")


async def test_optional_community_failure_is_reported_without_losing_native_capture(db, settings, prepared, monkeypatch):
    settings.fxembed_profiles_enabled = True

    async def denied(*args):
        return {'state': 'operator_attention', 'http_status': 403}

    async def unavailable(*args):
        raise ValueError('adapter response error containing private provider details')

    monkeypatch.setattr(professionals, 'profile_snapshot', denied)
    monkeypatch.setattr('outreach.fxembed.profile_hint', unavailable)
    report = await professionals.research_professionals(db, settings, prepared['lead_id'], 'https://x.com/BrightDemo')
    assert report['captures'][0]['state'] == 'operator_attention'
    hint = report['community_profile_hints'][0]
    assert hint['state'] == 'unavailable' and hint['error_type'] == 'ValueError'
    assert 'private provider details' not in json.dumps(report)
    assert db.one("SELECT 1 FROM events WHERE kind='professional_research'")


@pytest.mark.parametrize('configured,expected', [('x.com', ['x.com']), ('twitter.com', ['x.com']),
    ('linkedin.com', ['linkedin.com']), ('', [])])
async def test_managed_discovery_respects_selected_platforms(settings, monkeypatch, configured, expected):
    settings.discovery_platforms = configured
    settings.platform_browser_enabled = True
    settings.platform_browser_public_fallback = False
    settings.discovery_query_delay_seconds = 0
    called = []

    async def search(s, platform, *args):
        called.append(platform)
        return []

    monkeypatch.setattr('outreach.platform_browser.browser_discover', search)
    await discovery.prospect_candidates(settings, 'cleaning UK', 'UK', 3)
    assert called == expected


@pytest.mark.parametrize('platform,urls', [
    ('linkedin.com', ('https://www.linkedin.com/company/bright-demo',
                     'https://uk.linkedin.com/company/bright-demo/about/',
                     'https://linkedin.com/company/another-demo')),
    ('x.com', ('https://x.com/BrightDemo', 'https://twitter.com/brightdemo/', 'https://x.com/AnotherDemo')),
    ('x.com', ('https://x.com/BrightDemo/status/123', 'https://twitter.com/brightdemo/status/123',
               'https://x.com/BrightDemo/status/456')),
])
async def test_profile_aliases_do_not_consume_signal_budget_twice(settings, monkeypatch, platform, urls):
    settings.discovery_platforms = platform
    settings.discovery_max_signals = 2
    settings.discovery_query_delay_seconds = 0
    seen = []

    async def search(*args, **kwargs):
        return [{'url': url, 'title': 'UK cleaning company'} for url in urls]

    async def resolve(s, row, *args):
        seen.append(row['url'])
        return {'source_url': row['url'], 'state': 'no_company_match', 'website': ''}

    monkeypatch.setattr('outreach.providers.discover', search)
    monkeypatch.setattr(discovery, 'resolve_signal', resolve)
    _, report = await discovery.prospect_candidates(settings, 'cleaning UK', 'UK', 3)
    assert seen == [urls[0], urls[2]]
    assert len(report['signals']) == 2


async def test_linked_website_uses_captured_listing_business_name(settings, monkeypatch):
    async def snapshot(*args, **kwargs):
        return {'state': 'captured', 'capture_method': 'google_business_visible_listing',
                'title': 'Bright Demo Cleaning', 'outgoing_websites': ['https://bright-demo.com/']}

    monkeypatch.setattr(discovery, 'public_snapshot', snapshot)
    signal = await discovery.resolve_signal(settings,
        {'url': 'https://www.google.com/maps/place/Bright+Demo', 'title': 'Google Maps'}, 'UK', ['google.com'])
    assert signal['company'] == 'Bright Demo Cleaning'
    assert signal['website'] == 'https://bright-demo.com/'
