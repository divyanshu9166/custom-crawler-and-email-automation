import httpx
import pytest

from outreach import public_posts
from outreach.discovery import prospect_candidates, resolve_signal

POST = 'https://x.com/BrightDemo/status/123456789'


def payload(**changes):
    return {'version': '1.0', 'type': 'rich', 'provider_url': 'https://x.com', 'url': POST,
            'author_url': 'https://x.com/BrightDemo', 'author_name': 'Bright Studio',
            'html': '<blockquote class="twitter-tweet"><p>Business enquiries: hello@bright-demo.com <a href="https://bright-demo.com/contact">Contact</a></p><a href="'+POST+'">October 1, 2026</a></blockquote><script>alert(1)</script>',
            **changes}


def transport(monkeypatch, handler):
    client = httpx.AsyncClient
    monkeypatch.setattr(public_posts.httpx, 'AsyncClient', lambda **kwargs: client(transport=httpx.MockTransport(handler), **kwargs))


@pytest.mark.parametrize('url', ['https://notx.com/BrightDemo/status/123', 'https://x.com/i/status/123',
    'https://x.com/BrightDemo', 'https://x.com/search?q=test', 'http://127.0.0.1/BrightDemo/status/123',
    'https://x.com/BrightDemo/status/123/photo/1', 'https://x.com:444/BrightDemo/status/123'])
def test_only_specific_public_post_routes_are_eligible(url):
    with pytest.raises(ValueError):
        public_posts.x_post_url(url)


async def test_publication_api_has_no_sessions_scripts_or_contact_imports(settings, monkeypatch):
    requests = []
    def handle(request):
        requests.append(request)
        return httpx.Response(200, json=payload())
    transport(monkeypatch, handle)
    result = await public_posts.public_post_snapshot(settings, POST)
    assert result['state'] == 'captured'
    assert result['capture_method'] == 'official_public_oembed'
    assert result['profile_snapshot'] is False and result['identity_verified'] is False
    assert result['published_emails'] == ['hello@bright-demo.com']
    assert result['outgoing_websites'] == ['https://bright-demo.com/contact']
    assert 'alert' not in result['text']
    assert len(result['response_sha256']) == 64
    assert len(requests) == 1 and requests[0].url.host == 'publish.x.com'
    assert 'authorization' not in requests[0].headers and 'cookie' not in requests[0].headers
    assert requests[0].url.params['omit_script'] == 'true'


@pytest.mark.parametrize('change', [
    {'author_url':'https://x.com/OtherBusiness'}, {'url':'https://x.com/BrightDemo/status/999'},
    {'provider_url':'https://fake-publisher.com'}, {'type':'link'},
    {'html':'<script>hiddenData()</script>'}, {'html':'x'*65537},
    {'html':'<blockquote class="twitter-tweet"><p>A</p><p>B</p></blockquote>'},
])
async def test_ambiguous_or_wrong_publication_response_is_held(settings, monkeypatch, change):
    transport(monkeypatch, lambda _: httpx.Response(200, json=payload(**change)))
    assert (await public_posts.public_post_snapshot(settings, POST))['state'] == 'public_post_unavailable'


@pytest.mark.parametrize('code', [302,401,403,404,429,500])
async def test_denial_and_rate_limit_are_not_retried_or_followed(settings, monkeypatch, code):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(code, headers={'location':'https://x.com/login','retry-after':'60'})
    transport(monkeypatch, handler)
    result = await public_posts.public_post_snapshot(settings, POST)
    assert result['state'] == ('rate_limited' if code == 429 else 'public_post_unavailable')
    assert result['http_status'] == code and len(calls) == 1


async def test_response_cap_prevents_an_unbounded_payload(settings, monkeypatch):
    transport(monkeypatch, lambda _: httpx.Response(200, content=b'x'*(public_posts.MAX_RESPONSE+1),
                                                 headers={'content-type':'application/json'}))
    assert (await public_posts.public_post_snapshot(settings, POST))['state'] == 'public_post_unavailable'


async def test_post_mailto_is_preserved_when_the_link_label_does_not_spell_the_email(settings, monkeypatch):
    html = '<blockquote class="twitter-tweet"><p>Bright Studio UK enquiries: <a href="mailto:hello%40bright-demo.com?subject=Enquiry">Email our team</a></p><a href="'+POST+'">October 1, 2026</a></blockquote>'
    transport(monkeypatch,lambda _:httpx.Response(200,json=payload(html=html)))
    result = await public_posts.public_post_snapshot(settings,POST)
    assert result['published_emails'] == ['hello@bright-demo.com']
    assert result['published_email_links'] == ['hello@bright-demo.com']
    assert 'Published mailto links: hello@bright-demo.com' in result['text']
    assert result['profile_snapshot'] is False and result['identity_verified'] is False


async def test_visible_bracket_obfuscation_is_a_publication_candidate_not_a_guessed_address(settings, monkeypatch):
    html = '<blockquote class="twitter-tweet"><p>Business enquiries: hello [at] bright-demo [dot] com</p><a href="'+POST+'">October 1, 2026</a></blockquote>'
    transport(monkeypatch,lambda _:httpx.Response(200,json=payload(html=html)))
    result = await public_posts.public_post_snapshot(settings,POST)
    assert result['published_emails'] == ['hello@bright-demo.com'] and not result['published_email_links']
    assert 'hello [at] bright-demo [dot] com' in result['text']


@pytest.mark.parametrize('hidden', [
    '<span hidden>hidden@other-demo.com</span>',
    '<a aria-hidden="true" href="mailto:hidden@other-demo.com">Private</a>',
    '<span style="display:none">hidden@other-demo.com</span>',
    '<span style="visibility:hidden">hidden@other-demo.com</span>',
    '<script>"hidden@other-demo.com"</script>',
])
async def test_hidden_post_data_never_becomes_an_email_candidate(settings,monkeypatch,hidden):
    html = '<blockquote class="twitter-tweet"><p>Business hello@bright-demo.com '+hidden+'</p><a href="'+POST+'">Date</a></blockquote>'
    transport(monkeypatch,lambda _:httpx.Response(200,json=payload(html=html)))
    result = await public_posts.public_post_snapshot(settings,POST)
    assert result['published_emails'] == ['hello@bright-demo.com'] and 'hidden@' not in result['text']


async def test_other_html_and_unwanted_service_inboxes_are_not_outreach_candidates(settings,monkeypatch):
    html = '<p>timeline@other-demo.com</p><blockquote class="twitter-tweet"><p>Security: security@bright-demo.com Business: hello@bright-demo.com</p><a href="'+POST+'">Date</a></blockquote>'
    transport(monkeypatch,lambda _:httpx.Response(200,json=payload(html=html)))
    result = await public_posts.public_post_snapshot(settings,POST)
    assert result['published_emails'] == ['hello@bright-demo.com'] and 'timeline@' not in result['text']


async def test_current_public_post_can_resolve_company_without_fetching_protected_profile(settings, monkeypatch):
    transport(monkeypatch, lambda _: httpx.Response(200, json=payload()))
    from outreach.discovery import public_snapshot
    calls = []
    async def snapshot(s, url, platform=False):
        calls.append(url)
        if platform:
            return await public_snapshot(s, url, platform=True)
        assert url == 'https://bright-demo.com/contact'
        return {'state':'captured','url':url,'title':'Bright Studio','text':'Bright Studio services in London',
                'sha256':'current-source','organization_profile_links':['https://x.com/BrightDemo']}
    async def no_search(*args, **kwargs):
        pytest.fail('Current reciprocal link is sufficient for this candidate; no index lookup needed')
    monkeypatch.setattr('outreach.discovery.public_snapshot', snapshot)
    monkeypatch.setattr('outreach.providers.discover', no_search)
    result = await resolve_signal(settings, {'url':POST,'title':'An indexed post title','snippet':''}, 'UK', ['x.com'])
    assert result['website'] == 'https://bright-demo.com/'
    assert result['company'] == 'Bright Studio'
    assert result['access_path'] == 'official_public_post_api' and not result['profile_snapshot']
    assert not result['indexed_signal_only']
    assert calls == [POST,'https://bright-demo.com/contact']


async def test_discovery_accepts_public_posts_and_preserves_original_source(settings, monkeypatch):
    settings.discovery_platforms = 'x.com'
    settings.discovery_query_delay_seconds = .001
    async def search(*args, **kwargs):
        return [{'url':POST,'title':'Bright Studio UK consulting','snippet':'UK consulting'}]
    async def resolve(*args, **kwargs):
        return {'source_url':POST,'platform':'x.com','website':'https://bright-demo.com/',
                'company':'Bright Studio','state':'reciprocal_profile_link_candidate',
                'official_match_url':'https://bright-demo.com/contact'}
    monkeypatch.setattr('outreach.providers.discover', search)
    monkeypatch.setattr('outreach.discovery.resolve_signal', resolve)
    rows, report = await prospect_candidates(settings, 'UK consulting', 'UK', 5)
    assert rows[0]['source_url'] == POST and rows[0]['research_seed_url'].endswith('/contact')
    assert len(report['signals']) == 1


async def test_unavailable_post_does_not_guess_author_or_search_from_stale_index(settings, monkeypatch):
    transport(monkeypatch, lambda _: httpx.Response(404))
    result = await resolve_signal(settings, {'url':POST,'title':'Stale company','snippet':'hello@bright-demo.com'}, 'UK', ['x.com'])
    assert result['state'] == 'public_post_unavailable'
    assert not result['website'] and 'company' not in result


async def test_nested_hidden_post_elements_preserve_visible_publication(settings, monkeypatch):
    html = '<blockquote class="twitter-tweet"><p>Business hello@bright-demo.com <span style="display:none"><span style="color:red">hidden@other-demo.com</span></span></p><a href="'+POST+'">Date</a></blockquote>'
    transport(monkeypatch, lambda request: httpx.Response(200, json=payload(html=html)))
    result = await public_posts.public_post_snapshot(settings, POST)
    assert result['state'] == 'captured'
    assert result['published_emails'] == ['hello@bright-demo.com']
    assert 'hidden@other-demo.com' not in result['text']
