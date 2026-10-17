"""Real Chromium search UI fixtures; no live login, API or platform requests."""
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from playwright.async_api import async_playwright

from outreach import platform_browser

STATIC=Path(__file__).resolve().parents[1]/'outreach/static'


@pytest.fixture
def search_fixture(settings,monkeypatch):
    settings.platform_browser_delay_seconds=.02
    settings.platform_browser_search_steps=6
    settings.platform_browser_search_pages=3
    source={'html':''}
    class FixtureSession:
        def __init__(self,*args): pass
        async def __aenter__(self):
            self.runtime=await async_playwright().start()
            self.browser=await self.runtime.chromium.launch()
            self.context=await self.browser.new_context(viewport={'width':1440,'height':900})
            await self.context.route('**/*',lambda r:r.fulfill(status=200,body=source['html'],content_type='text/html'))
            return self
        async def navigate(self,url):
            page=await self.context.new_page()
            await page.goto(url)
            return page,None
        async def __aexit__(self,*args):
            await self.browser.close()
            await self.runtime.stop()
    monkeypatch.setattr(platform_browser,'BrowserSession',FixtureSession)
    return settings,source


def linkedin_html(extra_script=''):
    return '''<nav><button aria-label="Next">PRIVATE ACCOUNT NEXT</button></nav>
    <main><div class="search-results-container" id="results"></div>
    <div class="artdeco-pagination"><button aria-label="Next" id="next">Next</button></div></main>
    <script>
    let index=0;
    function show(){
      const name=['Alpha','Beta','Gamma','Delta'][index];
      document.getElementById('results').innerHTML='<div class="entity-result"><a href="/company/'+name.toLowerCase()+'">'+name+'</a><a href="/company/'+name.toLowerCase()+'/about">About</a> UK consulting <span aria-hidden="true">PRIVATE DATA</span><div role="dialog">PRIVATE DIALOG</div></div>';
    }
    document.getElementById('next').onclick=()=>{index++;show();};show();
    </script>'''+extra_script


async def test_linkedin_next_pages_are_bounded_deduplicated_and_have_safe_context(search_fixture):
    settings,source=search_fixture
    source['html']=linkedin_html()
    rows=await platform_browser.browser_discover(settings,'linkedin.com','UK consulting',10)
    assert [r['title'] for r in rows]==['Alpha','Beta','Gamma']
    assert all('UK consulting' in r['snippet'] and 'PRIVATE' not in r['snippet'] for r in rows)
    report=rows.provider_reports[0]
    assert report['next_page_actions']==2 and report['snapshots']==3
    assert report['duplicate_rows']==3 and report['stop_reason']=='page_budget'
    assert report['bounded'] and report['state']=='partial'


async def test_requested_limit_stops_before_any_next_action(search_fixture):
    settings,source=search_fixture
    source['html']=linkedin_html()
    rows=await platform_browser.browser_discover(settings,'linkedin.com','UK consulting',1)
    assert len(rows)==1
    assert rows.provider_reports[0]['next_page_actions']==0
    assert rows.provider_reports[0]['stop_reason']=='requested_limit'


async def test_step_budget_does_not_click_unobserved_next_page(search_fixture):
    settings,source=search_fixture
    settings.platform_browser_search_steps=1
    source['html']=linkedin_html()
    rows=await platform_browser.browser_discover(settings,'linkedin.com','UK consulting',10)
    assert len(rows)==1 and rows.provider_reports[0]['stop_reason']=='step_budget'
    assert rows.provider_reports[0]['next_page_actions']==0


async def test_x_scroll_retains_replaced_virtualized_cards_without_reading_timeline(search_fixture):
    settings,source=search_fixture
    source['html']='''<main id="results"><div data-testid="UserCell"><a href="/AlphaDemo">Alpha</a></div></main>
      <article>PRIVATE TIMELINE</article><div style="height:1600px"></div>
      <script>window.addEventListener('scroll',()=>{
        if(scrollY>0)document.getElementById('results').innerHTML='<div data-testid="UserCell"><a href="/BetaDemo">Beta</a><a href="/BetaDemo/status/123">Post</a></div>';
      });</script>'''
    rows=await platform_browser.browser_discover(settings,'x.com','UK consulting',2)
    assert [r['title'] for r in rows]==['Alpha','Beta'], rows.provider_reports
    assert rows.provider_reports[0]['scroll_actions']>=1
    assert rows.provider_reports[0]['rejected_rows']>=1
    assert all('PRIVATE' not in r['snippet'] for r in rows)


async def test_stagnant_x_results_stop_after_two_no_new_snapshots(search_fixture):
    settings,source=search_fixture
    source['html']='<main><div data-testid="UserCell"><a href="/AlphaDemo">Alpha</a></div></main>'
    rows=await platform_browser.browser_discover(settings,'x.com','UK consulting',10)
    assert len(rows)==1
    assert rows.provider_reports[0]['snapshots']==3
    assert rows.provider_reports[0]['stop_reason']=='no_new_results'


async def test_authentication_transition_stops_next_actions_preserves_partial_rows_and_hold(search_fixture):
    settings,source=search_fixture
    source['html']=linkedin_html('''<script>document.getElementById('next').onclick=()=>{
      history.replaceState(null,'','/checkpoint/challenge');document.title='Security check';
    };</script>''')
    rows=await platform_browser.browser_discover(settings,'linkedin.com','UK consulting',10)
    assert len(rows)==1 and rows.engine_issues==[['linkedin.com','login_or_challenge']]
    assert rows.provider_reports[0]['stop_reason']=='login_or_challenge'
    assert platform_browser.hold(settings,'linkedin.com')['reason']=='login_or_challenge'
    held=await platform_browser.browser_discover(settings,'linkedin.com','UK consulting',10)
    assert not held


async def test_changed_search_query_cannot_add_results_under_original_query(search_fixture):
    settings,source=search_fixture
    source['html']=linkedin_html('''<script>document.getElementById('next').onclick=()=>{
      history.replaceState(null,'','?keywords=DifferentCompany');index++;show();
    };</script>''')
    rows=await platform_browser.browser_discover(settings,'linkedin.com','UK consulting',10)
    assert len(rows)==1 and rows.provider_reports[0]['stop_reason']=='redirect_identity_mismatch'
    assert not platform_browser.hold(settings,'linkedin.com')


async def test_http_429_during_pagination_holds_platform_without_error_body_rows(search_fixture,monkeypatch):
    settings,source=search_fixture
    source['html']=linkedin_html('''<script>document.getElementById('next').onclick=()=>{
      location.href='/search/results/companies/?keywords=UK%20consulting&page=2';
    };</script>''')
    original=platform_browser.BrowserSession
    class Limited(original):
        async def __aenter__(self):
            await super().__aenter__()
            await self.context.route('**/*page=2',lambda r:r.fulfill(status=429,
                headers={'retry-after':'600'},body='<main>trap@other-demo.com</main>'))
            return self
    monkeypatch.setattr(platform_browser,'BrowserSession',Limited)
    rows=await platform_browser.browser_discover(settings,'linkedin.com','UK consulting',10)
    assert len(rows)==1 and rows.provider_reports[0]['stop_reason']=='http_429'
    assert rows.engine_issues==[['linkedin.com','http_429']]
    assert platform_browser.hold(settings,'linkedin.com')['reason']=='http_429'


@pytest.mark.parametrize('current,expected', [
    ('https://www.linkedin.com/search/results/companies/?keywords=UK+consulting&page=2',True),
    ('https://evil-linkedin.com/search/results/companies/?keywords=UK+consulting',False),
    ('https://www.linkedin.com/search/results/people/?keywords=UK+consulting',False),
    ('https://www.linkedin.com/search/results/companies/?keywords=Other',False),
])
def test_pagination_retains_original_search_identity(current,expected):
    assert platform_browser.search_identity_matches(platform_browser.search_target('linkedin.com','UK consulting'),current) is expected


async def test_deadline_returns_collected_rows_and_closes_session_without_new_platform_hold(settings,monkeypatch):
    settings.platform_browser_delay_seconds=0
    settings.platform_browser_search_timeout_seconds=.025
    closed=[]
    target=platform_browser.search_target('linkedin.com','UK consulting')
    class Page:
        url=target
        def on(self,*args): pass
        def remove_listener(self,*args): pass
        async def bring_to_front(self): pass
        async def evaluate(self,script,arg=None):
            return {'action':'next_page'} if arg else {'state':'captured','rows':[
                {'url':'https://linkedin.com/company/alpha','title':'Alpha','snippet':'UK consulting'}]}
    class Session:
        def __init__(self,*args): pass
        async def __aenter__(self): return self
        async def __aexit__(self,*args): closed.append(True)
        async def navigate(self,*args): return Page(),None
    monkeypatch.setattr(platform_browser,'BrowserSession',Session)
    rows=await platform_browser.browser_discover(settings,'linkedin.com','UK consulting',10)
    assert len(rows)==1 and rows.provider_reports[0]['stop_reason']=='deadline'
    assert rows.engine_issues==[['linkedin.com','search_deadline']] and closed==[True]
    assert not platform_browser.hold(settings,'linkedin.com')


async def test_workflow_shows_saved_bounded_search_counts_even_without_engine_error(settings,db):
    from fastapi.testclient import TestClient
    from outreach.app import create_app
    settings.sending_enabled=False
    db.event('discovery',{'query':'Fictional UK consulting','campaign':'A','country_hint':'UK','lead_ids':[],
        'report':{'engine_reports':[{'query':'browser search','engine_issues':[],'providers':[
            {'provider':'managed_browser:linkedin.com','bounded':True,'state':'partial',
             'snapshots':3,'scroll_actions':1,'next_page_actions':2,'unique_results':3,'stop_reason':'page_budget'}]}]}})
    errors=[]
    with TestClient(create_app(settings),base_url=settings.public_url,
                    headers={'Authorization':'Bearer '+settings.api_token}) as client:
        async with async_playwright() as runtime:
            browser=await runtime.chromium.launch()
            try:
                page=await browser.new_page()
                page.on('pageerror',lambda e:errors.append(str(e)))
                async def route(request):
                    parts=urlsplit(request.request.url)
                    assert request.request.method=='GET'
                    if parts.hostname!='outreach.example.com':
                        await request.abort()
                        return
                    response=client.get(parts.path+('?' + parts.query if parts.query else ''))
                    await request.fulfill(status=response.status_code,body=response.content,
                        headers={'content-type':response.headers.get('content-type','text/plain')})
                await page.route('**/*',route)
                await page.goto(settings.public_url)
                await page.get_by_text('Recent search runs and limitations',exact=True).click()
                await page.locator('#flow-research-runs').get_by_text('LinkedIn search',exact=False).wait_for()
                text=await page.locator('#flow-research-runs').inner_text()
                assert '3 distinct profiles' in text and '2 page advances' in text and 'page budget' in text
                assert 'Search coverage / limitations' in text and not errors
                await page.set_viewport_size({'width':390,'height':844})
                assert await page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                assert not db.all('SELECT * FROM jobs') and not db.all('SELECT * FROM messages')
            finally:
                await browser.close()
