import asyncio
import json
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from playwright.async_api import async_playwright

from outreach import platform_browser
from outreach.discovery import prospect_candidates, public_snapshot, resolve_signal
from outreach.profiles import canonical_profile, source_allowed, add_profile_lead

ROOT=Path(__file__).resolve().parents[1]
HTML='''<nav>PRIVATE TEST ACCOUNT</nav><h1>Bright Studio</h1><a href="/company/bright/about/">About</a>
<p>Bright Studio is a UK consulting business.</p><dl><dt>Website</dt><dd><a href="https://bright-demo.com">Website</a></dd>
<dt>Industry</dt><dd>Business consulting</dd><dt>Email</dt><dd><a href="mailto:hello%40bright-demo.com">Business enquiries</a></dd></dl>
<aside>PRIVATE TEST MESSAGE</aside>'''


@pytest.fixture
def managed(settings,monkeypatch):
    settings.platform_browser_enabled=True
    settings.platform_browser_public_fallback=False
    settings.platform_browser_delay_seconds=0
    class FixtureSession:
        def __init__(self,s): self.settings=s
        async def __aenter__(self):
            self.p=await async_playwright().start()
            self.browser=await self.p.chromium.launch()
            self.context=await self.browser.new_context()
            await self.context.route('**/*',lambda route:route.fulfill(status=200,body=HTML,content_type='text/html'))
            return self
        async def navigate(self,url):
            page=await self.context.new_page()
            await page.goto(url)
            return page,None
        async def __aexit__(self,*args):
            await self.browser.close()
            await self.p.stop()
    monkeypatch.setattr(platform_browser,'BrowserSession',FixtureSession)
    return settings


async def test_managed_dom_capture_excludes_private_shell_and_has_no_api_calls(managed,monkeypatch):
    async def forbidden(*args,**kwargs): pytest.fail('No platform developer/publication/search API in managed mode')
    monkeypatch.setattr('outreach.providers.discover',forbidden)
    monkeypatch.setattr('outreach.public_posts.public_post_snapshot',forbidden)
    result=await public_snapshot(managed,'https://linkedin.com/company/bright',platform=True)
    assert result['state']=='captured' and result['capture_method']=='managed_browser_public_profile'
    assert 'UK consulting' in result['text'] and 'PRIVATE' not in result['text']
    assert result['published_emails']==['hello@bright-demo.com']
    assert result['outgoing_websites']==['https://bright-demo.com/']
    assert result['identity_verified'] is False
    signal=await resolve_signal(managed,{'url':'https://linkedin.com/company/bright','title':'Misleading indexed name'},'UK',['linkedin.com'])
    assert signal['company']=='Bright Studio' and signal['website']=='https://bright-demo.com/'
    assert signal['indexed_signal_only'] is False


@pytest.mark.parametrize('anchor,expected', [
    ('<a href="https://www.linkedin.com/safety/go/?url=https%3A%2F%2Fbright-demo.com%2Fcontact%3Ftracking%3Ddiscarded">Website</a>', ['https://bright-demo.com/contact']),
    ('<a href="https://www.linkedin.com/safety/go/">http://bright-demo.com</a>', ['http://bright-demo.com/']),
    ('<a href="https://www.linkedin.com/safety/go/?url=javascript%3Aalert%281%29">Website</a>', []),
    ('<a href="https://www.linkedin.com/safety/go/?url=https%3A%2F%2Fuser%3Asecret%40bright-demo.com">Website</a>', []),
    ('<a href="https://www.linkedin.com/safety/go/">https://bright-demo.com/…</a>', []),
    ('<a hidden href="https://www.linkedin.com/safety/go/?url=https%3A%2F%2Fbright-demo.com">Website</a>', []),
])
async def test_company_website_redirect_uses_only_explicit_visible_destinations(managed, monkeypatch, anchor, expected):
    html = HTML.replace('<a href="https://bright-demo.com">Website</a>', anchor)
    original = platform_browser.BrowserSession
    class RedirectFixture(original):
        async def __aenter__(self):
            await super().__aenter__()
            await self.context.unroute('**/*')
            await self.context.route('**/*', lambda route: route.fulfill(status=200, body=html, content_type='text/html; charset=utf-8'))
            return self
    monkeypatch.setattr(platform_browser, 'BrowserSession', RedirectFixture)
    result = await platform_browser.browser_snapshot(managed, 'https://www.linkedin.com/company/bright')
    assert result['state'] == 'captured' and result['outgoing_websites'] == expected
    assert all('/safety/go' not in link for link in result['public_links'])


async def test_browser_discovery_integrates_into_existing_pipeline_without_searx(managed,monkeypatch):
    seen=[]
    async def discover(s,p,q,limit):
        seen.append(p)
        return [{'url':'https://linkedin.com/company/bright','title':'Bright'}] if p=='linkedin.com' else []
    async def forbidden(*args,**kwargs): pytest.fail('Managed discovery must not fall back to external/index APIs')
    monkeypatch.setattr(platform_browser,'browser_discover',discover)
    monkeypatch.setattr('outreach.providers.discover',forbidden)
    rows,report=await prospect_candidates(managed,'UK business consulting','UK',5)
    assert seen==['linkedin.com','x.com'] and rows[0]['title']=='Bright Studio'
    assert rows[0]['url']=='https://bright-demo.com/' and not report['errors']


async def test_login_hold_stops_other_calls_until_operator_resets_session(settings,monkeypatch):
    settings._platform_browser_holds['linkedin.com']='login_or_challenge'
    class Forbidden:
        def __init__(self,*args): pytest.fail('Held browser must not relaunch or brute-force access')
    monkeypatch.setattr(platform_browser,'BrowserSession',Forbidden)
    snap=await platform_browser.browser_snapshot(settings,'https://linkedin.com/company/bright')
    assert snap['state']=='operator_attention'
    rows=await platform_browser.browser_discover(settings,'linkedin.com','UK consultants')
    assert not rows and rows.engine_issues


@pytest.mark.parametrize('url',['https://linkedin.com/in/person','https://x.com/name/status/123',
    'https://linkedin.com/company/bright/people','https://localhost/company/bright','https://x.com/messages',
    'https://peopleperhour.com/freelancer/test'])
def test_only_business_profile_capture_routes_supported(url):
    with pytest.raises(ValueError):
        platform_browser.profile_target(url)


def test_about_evidence_stays_attached_to_same_company_not_other_profile(db):
    lid=add_profile_lead(db,'Bright','https://linkedin.com/company/bright/about','A','UK')
    lead=db.one('SELECT * FROM leads WHERE id=?',(lid,))
    assert canonical_profile(lead['profile_url'])=='https://linkedin.com/company/bright'
    assert source_allowed(lead,'https://www.linkedin.com/company/bright/about/')
    assert not source_allowed(lead,'https://linkedin.com/company/other/about/')


async def test_owned_persistent_profile_survives_restart_without_exporting_cookies(settings):
    settings.platform_browser_headless=True
    async with platform_browser.BrowserSession(settings) as first:
        await first.context.add_cookies([{'name':'SYNTHETIC_TEST_AUTH','value':'fictional-only','domain':'.x.com','path':'/','expires':time.time()+600,'secure':True}])
    async with platform_browser.BrowserSession(settings) as second:
        cookies=await second.context.cookies('https://x.com')
        assert any(c['name']=='SYNTHETIC_TEST_AUTH' for c in cookies)
    assert (settings.data_dir/'platform-browser/profile').exists()


@pytest.mark.parametrize('url',['http://127.0.0.1/admin','https://attacker.test/','https://linkedin.com/messaging',
    'https://linkedin.com/company/bright/people','https://x.com/messages','https://x.com/settings',
    'https://linkedin.com:bad/company/bright','https://linkedin.com/search/results/companies/private',
    'https://linkedin.com/search/results/companies-unrelated','https://linkedin.com/login-unrelated'])
async def test_browser_network_blocks_external_and_private_navigation(settings,url):
    page=SimpleNamespace(main_frame=None)
    frame=SimpleNamespace(page=page)
    page.main_frame=frame
    calls=[]
    class Route:
        request=SimpleNamespace(url=url,frame=frame,is_navigation_request=lambda:True)
        async def abort(self):calls.append('abort')
        async def continue_(self):calls.append('continue')
    await platform_browser.BrowserSession(settings).route(Route())
    assert calls==['abort']


@pytest.mark.parametrize('kind', ['professional', 'company', 'search'])
async def test_visible_dialogs_and_aria_hidden_contacts_are_excluded_from_managed_readers(kind):
    private = '<div role="dialog"><a href="mailto:private@private-demo.com">private@private-demo.com</a><a href="/company/private">Private company</a></div>'
    hidden = '<span aria-hidden="true"><a href="mailto:hidden@private-demo.com">hidden@private-demo.com</a><a href="/company/hidden">Hidden company</a></span>'
    if kind == 'professional':
        url = 'https://www.linkedin.com/in/alex-demo'
        html = '<main><section><h1>Alex Demo</h1><div class="text-body-medium">Founder at Bright Studio'+hidden+'</div>'+private+'<a href="mailto:public@bright-demo.com">Business enquiries</a></section></main>'
        filename = 'professional-reader.js'
    elif kind == 'company':
        url = 'https://www.linkedin.com/company/bright/about/'
        html = HTML.replace('Business enquiries</a>', 'Business enquiries</a>'+private+hidden)
        filename = 'platform-reader.js'
    else:
        url = 'https://www.linkedin.com/search/results/companies/?keywords=UK'
        html = '<main><div class="search-results-container"><div class="entity-result"><a href="/company/bright">Bright Studio</a>'+private+hidden+'</div></div></main>'
        filename = 'platform-search-reader.js'
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        try:
            page = await browser.new_page()
            await page.route('**/*', lambda route: route.fulfill(status=200, body=html, content_type='text/html'))
            await page.goto(url)
            result = await page.evaluate((ROOT/'outreach/static'/filename).read_text(encoding='utf-8'))
        finally:
            await browser.close()
    assert result['state'] == 'captured'
    assert 'private-demo.com' not in json.dumps(result)
    if kind == 'search':
        assert [row['title'] for row in result['rows']] == ['Bright Studio']
    else:
        assert len(result['mailto']) == 1


def test_setup_and_runtime_share_local_profile_and_gui_is_loopback_only():
    base=yaml.safe_load((ROOT/'compose.yaml').read_text())
    service=base['services']['browser-setup']
    assert service['ports']==['127.0.0.1:6080:6080']
    assert service['volumes']==['app_data:/data']
    overlay=yaml.safe_load((ROOT/'compose.platform-browser.yaml').read_text())
    assert overlay['services']['app']['environment']['PLATFORM_BROWSER_HEADLESS']=='false'
    assert overlay['services']['app']['command'][0]=='xvfb-run'
    assert not overlay['services']['app'].get('ports')
    assert json.loads(json.dumps(overlay))


async def test_current_x_div_bio_preserves_only_visible_business_email_and_location(managed,monkeypatch):
    html='''<nav>PRIVATE TEST ACCOUNT</nav><div><div><h1>Bright Studio</h1></div>
    <div class="whitespace-pre-wrap">UK consulting. Business enquiries hello@bright-demo.com.</div>
    <div><a href="https://t.co/opaque">bright-demo.com</a><a href="/BrightDemo/about">Joined</a></div></div>
    <article>PRIVATE TEST POST <a href="/BrightDemo/status/123">Date</a></article>'''
    original=platform_browser.BrowserSession
    class XFixture(original):
        async def __aenter__(self):
            await super().__aenter__()
            await self.context.unroute('**/*')
            await self.context.route('**/*',lambda r:r.fulfill(status=200,body=html,content_type='text/html'))
            return self
    monkeypatch.setattr(platform_browser,'BrowserSession',XFixture)
    result=await platform_browser.browser_snapshot(managed,'https://x.com/BrightDemo')
    assert result['state']=='captured' and 'UK consulting' in result['text']
    assert result['published_emails']==['hello@bright-demo.com'] and 'PRIVATE' not in result['text']


async def test_http_denial_holds_platform_without_reading_body(settings,monkeypatch):
    class Denied:
        def __init__(self,*args): pass
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def navigate(self,*args):return None,429
    settings.platform_browser_delay_seconds=0
    monkeypatch.setattr(platform_browser,'BrowserSession',Denied)
    result=await platform_browser.browser_snapshot(settings,'https://linkedin.com/company/bright')
    assert result['state']=='operator_attention' and result['http_status']==429
    assert settings._platform_browser_holds['linkedin.com']=='http_429'


@pytest.mark.parametrize('platform,html,expected',[
    ('linkedin.com','''<main><a href="/company/irrelevant">Account shortcut</a>
      <div class="search-results-container"><div class="entity-result">
      <a href="/company/bright">Bright Studio</a><a href="/company/bright/about">About</a>
      <a href="/in/person">Employee</a></div></div></main>''','https://www.linkedin.com/company/bright'),
    ('x.com','''<main><a href="/Unrelated">Account shortcut</a><div data-testid="UserCell">
      <a href="/BrightDemo">Bright Studio</a><a href="/BrightDemo">@BrightDemo</a>
      <a href="/BrightDemo/status/123">Post</a></div></main>''','https://x.com/BrightDemo'),
    ('linkedin.com','<title>Sign in</title><input type="password">',None),
])
async def test_rendered_search_cards_exclude_navigation_and_stop_for_login(managed,monkeypatch,platform,html,expected):
    original=platform_browser.BrowserSession
    class SearchFixture(original):
        async def __aenter__(self):
            await super().__aenter__()
            await self.context.unroute('**/*')
            await self.context.route('**/*',lambda r:r.fulfill(status=200,body=html,content_type='text/html'))
            return self
    monkeypatch.setattr(platform_browser,'BrowserSession',SearchFixture)
    rows=await platform_browser.browser_discover(managed,platform,'UK business consulting')
    if expected:
        assert len(rows)==1 and rows[0]['url']==expected and rows[0]['title']=='Bright Studio'
    else:
        assert not rows and managed._platform_browser_holds[platform]=='login_or_challenge'


async def test_queued_calls_recheck_platform_hold_before_launch(settings,monkeypatch):
    launches=[]
    class Denied:
        def __init__(self,*args): launches.append(True)
        async def __aenter__(self):return self
        async def __aexit__(self,*args):pass
        async def navigate(self,*args):
            await asyncio.sleep(.01)
            return None,429
    settings.platform_browser_delay_seconds=0
    monkeypatch.setattr(platform_browser,'BrowserSession',Denied)
    rows=await asyncio.gather(*(platform_browser.browser_discover(settings,'x.com','UK businesses') for _ in range(2)))
    assert not any(rows) and len(launches)==1


@pytest.mark.parametrize('code,state,held',[(999,'operator_attention',True),(403,'operator_attention',True),
    (429,'operator_attention',True),(404,'not_found',False),(500,'public_profile_unavailable',False),
    (503,'public_profile_unavailable',False)])
async def test_real_chromium_http_errors_are_preserved_and_never_parsed_as_public_profiles(settings,monkeypatch,code,state,held):
    original=platform_browser.BrowserSession
    class StatusFixture(original):
        async def __aenter__(self):
            self.p=await async_playwright().start()
            self.browser=await self.p.chromium.launch()
            self.context=await self.browser.new_context()
            await self.context.route('**/*',lambda r:r.fulfill(status=code,content_type='text/html',
                body='<main><h1>Error document</h1><p>not-a-public-profile@bright-demo.com</p></main>'))
            return self
        async def __aexit__(self,*args):
            await self.browser.close()
            await self.p.stop()
    monkeypatch.setattr(platform_browser,'BrowserSession',StatusFixture)
    settings.platform_browser_delay_seconds=0
    result=await platform_browser.browser_professional_snapshot(settings,'https://linkedin.com/in/alex-demo')
    assert result['state']==state and result['http_status']==code
    assert bool(settings._platform_browser_holds.get('linkedin.com')) is held
    assert not result.get('text') and not result.get('published_emails')


@pytest.mark.parametrize('target,current,expected', [
    ('https://www.linkedin.com/in/alex-demo', 'https://www.linkedin.com/checkpoint/challenge', True),
    ('https://www.linkedin.com/company/bright/about/', 'https://www.linkedin.com/authwall', True),
    ('https://x.com/BrightDemo', 'https://x.com/i/flow/login', True),
    ('https://www.linkedin.com/in/alex-demo', 'https://evil-linkedin.com/checkpoint/challenge', False),
    ('https://www.linkedin.com/in/alex-demo', 'https://www.linkedin.com/in/alex-demo', False),
    ('https://www.linkedin.com/in/alex-demo', 'https://www.linkedin.com/login-unrelated', False),
    ('https://www.linkedin.com/in/alex-demo', 'https://x.com/i/flow/login', False),
    ('https://x.com/BrightDemo', 'https://x.com:8443/i/flow/login', False),
])
def test_navigation_login_transition_requires_same_platform_auth_route(target,current,expected):
    assert platform_browser.login_transition(target,current) is expected


async def test_navigation_timeout_on_checkpoint_records_durable_hold_and_stops_next_search(settings,monkeypatch):
    from playwright.async_api import TimeoutError as BrowserTimeout
    launches=[]
    class Page:
        url='https://www.linkedin.com/checkpoint/challenge'
        def on(self,*args): pass
        def remove_listener(self,*args): pass
        async def goto(self,*args,**kwargs):
            raise BrowserTimeout('PRIVATE_TOKEN_MUST_NOT_BE_LOGGED')
        async def evaluate(self,*args): pytest.fail('Challenge documents must not be read as profile evidence')
    class Context:
        async def new_page(self): return Page()
    class Session(platform_browser.BrowserSession):
        async def __aenter__(self):
            launches.append(True)
            self.context=Context()
            return self
        async def __aexit__(self,*args): pass
    monkeypatch.setattr(platform_browser,'BrowserSession',Session)
    settings.platform_browser_delay_seconds=0
    result=await platform_browser.browser_professional_snapshot(settings,'https://linkedin.com/in/alex-demo')
    assert result['state']=='operator_attention' and result['reason']=='login_or_challenge'
    assert 'PRIVATE_TOKEN' not in json.dumps(result) and not result.get('published_emails')
    rows=await platform_browser.browser_discover(settings,'linkedin.com','UK architecture studios')
    assert not rows and rows.engine_issues and len(launches)==1
    settings._platform_browser_holds.clear()
    assert platform_browser.hold(settings,'linkedin.com')['reason']=='login_or_challenge'


async def test_search_browser_startup_failure_is_a_diagnostic_source_error(settings,monkeypatch):
    class Unavailable:
        def __init__(self,*args): pass
        async def __aenter__(self): raise RuntimeError('PRIVATE_PROFILE_PATH_MUST_NOT_BE_LOGGED')
        async def __aexit__(self,*args): pass
    monkeypatch.setattr(platform_browser,'BrowserSession',Unavailable)
    rows=await platform_browser.browser_discover(settings,'linkedin.com','UK architecture studios')
    assert not rows and rows.engine_issues==[['linkedin.com','browser_unavailable:RuntimeError']]
    assert not platform_browser.hold(settings,'linkedin.com')
