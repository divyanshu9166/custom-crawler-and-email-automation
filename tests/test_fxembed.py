import asyncio
import time

import httpx
import pytest

from outreach import fxembed

URL = 'https://x.com/BrightFounder'


def payload(**changes):
    return {'code': 200, 'message': 'OK', 'user': {'type': 'profile', 'name': 'Alex Demo',
        'screen_name': 'BrightFounder', 'url': URL, 'protected': False,
        'description': 'Founder at Bright Demo. Business enquiries: alex@bright-demo.com',
        'location': 'London', **changes}}


def transport(monkeypatch, handler):
    client = httpx.AsyncClient
    monkeypatch.setattr(fxembed.httpx, 'AsyncClient', lambda **kwargs:
        client(transport=httpx.MockTransport(handler), **kwargs))


def test_only_bio_supplies_candidates_and_mirror_is_never_first_party_proof():
    data = payload()
    data['user']['location'] = 'unrelated@other-demo.com'
    result = fxembed.parse_profile(data, URL)
    assert result['published_email_candidates'] == ['alex@bright-demo.com']
    assert result['state'] == 'public_mirror_hint'
    assert not result['first_party_publication_verified'] and not result['source_freshness_verified']
    assert not result['current_employer_verified'] and not result['buyer_verified']


@pytest.mark.parametrize('address', ['alex(at)bright-demo(dot)com', 'alex[at]bright-demo[dot]com',
    'alex(AT)bright-demo[DOT]com'])
def test_explicit_bio_address_obfuscation_keeps_original_quote_and_business_context(address):
    bio = 'Founder. Business enquiries: '+address
    result = fxembed.parse_profile(payload(description=bio), URL)
    assert result['published_email_candidates'] == ['alex@bright-demo.com']
    publication = result['email_publications'][0]
    assert publication['publication_quote'] == address and publication['method'] == 'visible_obfuscation'
    route = result['candidate_routes'][0]
    assert route['purpose'] == 'business_enquiries' and not route['buyer_contact_verified']
    assert route['contexts'][0]['context_quote'] in bio


def test_normal_role_language_does_not_guess_an_email():
    result = fxembed.parse_profile(payload(description='Founder at Bright Demo dot com. DM for opportunities.'), URL)
    assert not result['published_email_candidates'] and not result['email_publications']


def test_obfuscation_offsets_stay_correct_for_multiple_different_addresses():
    bio = 'Business enquiries: alex(at)bright-demo(dot)com; Press: media@other-demo.com'
    result = fxembed.parse_profile(payload(description=bio), URL)
    assert len(result['email_publications']) == 2
    assert all(p['publication_quote'] in bio for p in result['email_publications'])
    assert [r['purpose'] for r in result['candidate_routes']] == ['business_enquiries', 'press_media']


def test_explicit_profile_website_is_only_a_reference_not_ownership_proof():
    result = fxembed.parse_profile(payload(website={'url':'https://bright-demo.com/contact'}), URL)
    assert result['published_website_hint'] == 'https://bright-demo.com/contact'
    assert result['website_ownership_verified'] is False and result['first_party_publication_verified'] is False


@pytest.mark.parametrize('website', ['javascript:alert(1)', 'http://127.0.0.1/', 'https://user:pass@bright-demo.com/'])
def test_private_or_credentialed_website_reference_is_not_retained(website):
    result = fxembed.parse_profile(payload(website={'url':website}), URL)
    assert result['published_website_hint'] == ''


@pytest.mark.parametrize('change,state', [
    ({'screen_name': 'OtherFounder'}, 'identity_mismatch'),
    ({'url': 'https://x.com/OtherFounder'}, 'identity_mismatch'),
    ({'url': 'https://fake-demo.com/BrightFounder'}, 'identity_mismatch'),
    ({'protected': True}, 'private_or_visibility_unknown'),
    ({'protected': None}, 'private_or_visibility_unknown'),
    ({'protected': 0}, 'private_or_visibility_unknown'),
    ({'type': 'post'}, 'invalid_contract'),
    ({'description': None}, 'invalid_contract'),
    ({'description': 'x' * 16001}, 'invalid_contract'),
])
def test_wrong_private_or_ambiguous_profile_cannot_produce_email(change, state):
    result = fxembed.parse_profile(payload(**change), URL)
    assert result['state'] == state and not result.get('published_email_candidates')


def test_http_200_provider_error_does_not_publish_error_document_email():
    result = fxembed.parse_profile({'code': 404, 'message': 'contact admin@other-demo.com',
                                   'user': payload()['user']}, URL)
    assert result['state'] == 'provider_error' and 'published_email_candidates' not in result


@pytest.mark.parametrize('bio,purpose', [
    ('Customer support email: alex@bright-demo.com', 'customer_support'),
    ('Order inquiries: alex@bright-demo.com', 'customer_support'),
    ('Business enquiries: alex@bright-demo.com', 'business_enquiries'),
    ('Partnerships: alex@bright-demo.com', 'partnerships'),
    ('Founder at Bright Demo, alex@bright-demo.com', 'unknown'),
    ('Support: alex@bright-demo.com; Business enquiries: alex@bright-demo.com', 'multiple_purposes'),
])
def test_email_context_does_not_invent_a_buyer_route(bio, purpose):
    result = fxembed.parse_profile(payload(description=bio), URL)
    route = result['candidate_routes'][0]
    assert route['purpose'] == purpose and not route['buyer_contact_verified']
    assert all(item['context_quote'] in bio for item in route['contexts'])


async def test_default_disabled_makes_no_request(settings, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail('Community API was not enabled')
    monkeypatch.setattr(fxembed.httpx, 'AsyncClient', forbidden)
    assert (await fxembed.profile_hint(settings, URL))['state'] == 'disabled'


async def test_fixed_source_no_credentials_coalesced_capture(settings, monkeypatch):
    settings.fxembed_profiles_enabled = True
    seen = []
    def handle(request):
        seen.append(request)
        assert request.url.host == 'api.fxtwitter.com'
        assert request.url.path == '/2/profile/brightfounder'
        assert 'authorization' not in request.headers and 'cookie' not in request.headers
        return httpx.Response(200, json=payload())
    transport(monkeypatch, handle)
    first, second = await asyncio.gather(fxembed.profile_hint(settings, URL), fxembed.profile_hint(settings, URL))
    assert len(seen) == 1 and first['published_email_candidates'] == second['published_email_candidates']
    assert second['cached'] and first['retrieved_at'] == second['retrieved_at']


async def test_rate_limit_holds_other_profiles_without_retries(settings, monkeypatch):
    settings.fxembed_profiles_enabled = True
    seen = []
    def handle(request):
        seen.append(request)
        return httpx.Response(429, headers={'retry-after': '7200'})
    transport(monkeypatch, handle)
    result = await fxembed.profile_hint(settings, URL)
    other = await fxembed.profile_hint(settings, 'https://x.com/OtherFounder')
    assert result['http_status'] == 429 and other['state'] == 'cooldown'
    assert other['retry_at'] > time.time() + 7000 and len(seen) == 1


async def test_missing_profile_does_not_hold_provider(settings, monkeypatch):
    settings.fxembed_profiles_enabled = True
    transport(monkeypatch, lambda request: httpx.Response(404))
    assert (await fxembed.profile_hint(settings, URL))['state'] == 'not_found'
    assert not settings._discovery_state.get('holds', {}).get('fxembed_profiles')


async def test_provider_error_code_rate_limit_stops_other_profiles(settings, monkeypatch):
    settings.fxembed_profiles_enabled = True
    seen = []
    def handle(request):
        seen.append(request)
        return httpx.Response(200, json={'code': 429, 'message': 'limited'})
    transport(monkeypatch, handle)
    assert (await fxembed.profile_hint(settings, URL))['provider_code'] == 429
    assert (await fxembed.profile_hint(settings, 'https://x.com/OtherFounder'))['state'] == 'cooldown'
    assert len(seen) == 1


async def test_oversized_body_is_not_a_profile(settings, monkeypatch):
    settings.fxembed_profiles_enabled = True
    transport(monkeypatch, lambda request: httpx.Response(200, content=b'x' * (fxembed.MAX_BYTES + 1),
                                                       headers={'content-type': 'application/json'}))
    result = await fxembed.profile_hint(settings, URL)
    assert result['state'] == 'unavailable' and result['error_type'] == 'ValueError'


async def test_pipeline_preserves_native_denial_and_keeps_mirror_out_of_contact_evidence(db, settings, prepared, monkeypatch):
    from outreach import professionals
    settings.fxembed_profiles_enabled = True
    async def denied(*args):
        return {'state': 'operator_attention', 'http_status': 403, 'observed_at': time.time()}
    async def mirror(*args):
        return fxembed.parse_profile(payload(), URL)
    monkeypatch.setattr(professionals, 'profile_snapshot', denied)
    monkeypatch.setattr(fxembed, 'profile_hint', mirror)
    before = {table: db.all('SELECT * FROM ' + table) for table in ('contacts', 'evidence', 'jobs', 'messages')}
    report = await professionals.research_professionals(db, settings, prepared['lead_id'], URL)
    assert report['state'] == 'held' and report['captures'][0]['access_issue']['http_status'] == 403
    assert report['community_profile_hints'][0]['published_email_candidates'] == ['alex@bright-demo.com']
    assert not professionals.captures(db, prepared['lead_id'])[0]['published_emails']
    assert {table: db.all('SELECT * FROM ' + table) for table in before} == before


async def test_initial_discovery_researches_mirror_without_a_resolved_website(settings, monkeypatch):
    from outreach.discovery import resolve_signal
    from outreach.providers import SearchRows
    settings.fxembed_profiles_enabled = True
    settings.discovery_query_delay_seconds = 0
    async def native(*args, **kwargs):
        return {'state': 'robots_denied', 'url': URL}
    async def mirror(*args):
        return fxembed.parse_profile(payload(description='Business enquiries: alex@bright-demo.com'), URL)
    async def no_results(*args, **kwargs):
        return SearchRows([])
    monkeypatch.setattr('outreach.discovery.public_snapshot', native)
    monkeypatch.setattr(fxembed, 'profile_hint', mirror)
    monkeypatch.setattr('outreach.providers.discover', no_results)
    result = await resolve_signal(settings, {'url': URL, 'title': 'Bright Demo (@BrightFounder)', 'snippet': ''}, 'UK', ['x.com'])
    assert not result['website'] and result['public_snapshot']['state'] == 'robots_denied'
    assert result['community_profile_hint']['published_email_candidates'] == ['alex@bright-demo.com']
    assert result['community_source_is_first_party'] is False and result['indexed_signal_only']
    assert result['indexed_email_candidates'] == []


async def test_mirror_website_hint_requires_current_official_reciprocal_proof(settings, monkeypatch):
    from outreach.discovery import resolve_signal
    settings.fxembed_profiles_enabled = True
    async def source(config, url, **kwargs):
        if url == URL:
            return {'state': 'robots_denied', 'url': url}
        return {'state': 'captured', 'url': url, 'title': 'Bright Demo', 'text': 'Bright Demo UK',
                'sha256': 'current-company-hash', 'public_links': [URL], 'organization_profile_links': []}
    async def mirror(*args):
        return fxembed.parse_profile(payload(description='Our store: https://bright-demo.com/'), URL)
    async def forbidden(*args, **kwargs):
        pytest.fail('Observed reciprocal company source should resolve before index search')
    monkeypatch.setattr('outreach.discovery.public_snapshot', source)
    monkeypatch.setattr(fxembed, 'profile_hint', mirror)
    monkeypatch.setattr('outreach.providers.discover', forbidden)
    result = await resolve_signal(settings, {'url': URL, 'title': 'Bright Demo', 'snippet': ''}, 'UK', ['x.com'])
    assert result['state'] == 'reciprocal_profile_link_candidate'
    assert result['official_snapshot_sha256'] == 'current-company-hash'
    assert result['public_snapshot']['state'] == 'robots_denied'
