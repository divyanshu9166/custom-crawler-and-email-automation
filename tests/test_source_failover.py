import json
import time

import pytest
from fastapi.testclient import TestClient

from outreach.app import create_app
from outreach.contact_recovery import official_contact_seeds, research_contacts
from outreach.discovery import prospect_candidates, resolve_signal
from outreach.providers import SearchRows
from outreach.research import add_lead
from outreach.research_status import snapshot
from outreach.web import PublicWeb, priority


@pytest.mark.parametrize('profile_state',['operator_attention','browser_unavailable','captured'])
async def test_managed_missing_or_blocked_profile_recovers_only_from_independent_current_identity(settings,monkeypatch,profile_state):
    settings.platform_browser_enabled=True
    settings.search_provider='serpapi'
    settings.serpapi_key='fictional-must-not-be-used'
    settings.discovery_query_delay_seconds=.001
    calls=[]
    async def capture(s,url,platform=False):
        calls.append((url,platform))
        if platform:
            return {'state':profile_state,'title':'Bright Studio','text':'UK consultants',
                    'capture_method':'managed_browser_public_profile','outgoing_websites':[]}
        return {'state':'captured','url':url,'title':'Bright Studio','text':'Bright Studio UK consulting',
                'sha256':'current-hash','organization_profile_links':['https://linkedin.com/company/bright']}
    async def search(s,q,*args,**kwargs):
        assert s.search_provider=='searxng' and not s.serpapi_key
        return [{'url':'https://bright-demo.com/contact','title':'Bright Studio'}]
    monkeypatch.setattr('outreach.discovery.public_snapshot',capture)
    monkeypatch.setattr('outreach.providers.discover',search)
    result=await resolve_signal(settings,{'url':'https://linkedin.com/company/bright','title':'Bright Studio'},'UK',['linkedin.com'])
    assert result['website']=='https://bright-demo.com/'
    assert result['source_failover']['profile_state']==profile_state
    assert result['source_failover']['platform_access_recovered'] is False
    assert result['public_snapshot']['state']==profile_state and result['access_path']=='independent_public_sources'
    assert len([c for c in calls if c[1]])==1


async def test_failed_fallback_and_email_domain_hint_never_establish_website_absence(settings,monkeypatch):
    settings.platform_browser_enabled=True
    settings.discovery_query_delay_seconds=.001
    async def capture(*args,**kwargs):
        return {'state':'operator_attention','capture_method':'managed_browser_public_profile'}
    async def search(*args,**kwargs):return SearchRows([],[['fixture-engine','timeout']])
    monkeypatch.setattr('outreach.discovery.public_snapshot',capture)
    monkeypatch.setattr('outreach.providers.discover',search)
    result=await resolve_signal(settings,{'url':'https://x.com/BrightDemo','title':'Bright Studio','snippet':'hidden@bright-demo.com'},'UK',['x.com'])
    assert not result['website'] and not result['indexed_website_hints']
    assert not result['website_search']['completed'] and result['website_search']['engine_issues']
    assert result['public_snapshot']['state']=='operator_attention'


async def test_held_browser_search_still_discovers_public_websites_and_filters_irrelevant_results(settings,monkeypatch):
    settings.platform_browser_enabled=True
    settings.discovery_platforms=''
    settings.discovery_query_delay_seconds=.001
    async def held(*args,**kwargs):return SearchRows([],[['platform','operator_attention']])
    async def search(s,*args,**kwargs):
        assert s.search_provider=='searxng'
        return [{'url':'https://bright-demo.com/contact','title':'UK dental clinic'},
                {'url':'https://other-demo.com/','title':'Coffee shop'}]
    monkeypatch.setattr('outreach.platform_browser.browser_discover',held)
    monkeypatch.setattr('outreach.providers.discover',search)
    rows,report=await prospect_candidates(settings,'dental clinic','UK',5)
    assert len(rows)==1 and rows[0]['url']=='https://bright-demo.com/'
    assert report['skipped'][0]['reason']=='no_query_term_in_indexed_result'
    assert len(report['engine_reports'])==3 and report['engine_reports'][0]['engine_issues']


def test_source_metrics_deduplicate_latest_signal_and_exclude_index_email_and_stale_capture(db):
    lid=add_lead(db,'Bright Studio','https://bright-demo.com/','A','https://x.com/BrightDemo')
    base={'lead_id':lid,'platform':'x.com','source_url':'https://x.com/BrightDemo','country_hint':'UK',
          'website':'https://bright-demo.com/','source_failover':{'used':True},
          'indexed_snippet':'unpublished@bright-demo.com','public_snapshot':{'state':'operator_attention'}}
    db.event('prospect_signal',{**base,'public_snapshot':{'state':'captured','text':'old@bright-demo.com','published_emails':['old@bright-demo.com']}})
    db.event('prospect_signal',base)
    db.event('prospect_signal',{**base,'source_url':'https://x.com/OtherDemo','website':'',
        'public_snapshot':{'state':'captured','observed_at':time.time()-31*86400,'text':'stale@bright-demo.com','published_emails':['stale@bright-demo.com']}})
    result=snapshot(db,lid)['source_coverage']['rows'][0]
    assert result['signals']==result['unavailable']==2 and result['captured']==0
    assert result['website_candidates']==result['failover_candidates']==1
    assert result['published_email_candidates']==0


def test_source_metrics_count_current_published_business_candidates_only(db,prepared):
    db.event('prospect_signal',{'lead_id':prepared['lead_id'],'source_url':'https://linkedin.com/company/bright',
        'platform':'linkedin.com','public_snapshot':{'state':'captured','observed_at':time.time(),
          'text':'hello@bright-demo.com privacy@bright-demo.com',
          'published_emails':['hello@bright-demo.com','hello@bright-demo.com','privacy@bright-demo.com','not-present@bright-demo.com']}})
    result=snapshot(db,prepared['lead_id'])['source_coverage']['rows'][0]
    assert result['captured']==1 and result['published_email_candidates']==1


def test_source_coverage_api_is_authenticated_scoped_and_readonly(settings,db,prepared):
    before=db.all('SELECT * FROM events')
    with TestClient(create_app(settings)) as client:
        assert client.get('/api/source-coverage').status_code==401
        headers={'Authorization':'Bearer '+settings.api_token}
        assert client.get('/api/source-coverage',headers=headers).json()['rows']==[]
        assert client.get('/api/source-coverage?lead_id=999',headers=headers).status_code==400
    assert db.all('SELECT * FROM events')==before


@pytest.mark.parametrize('path,score',[('/business-enquiries',0),('/media-relations',0),
    ('/contact-us',0),('/press/contact',0),('/newsroom',3),('/storybook',4),('/contactless-payments',4)])
def test_contact_priority_is_route_based_not_arbitrary_substrings(path,score):
    assert priority('https://bright-demo.com'+path)==score


def test_new_contact_routes_are_sourced_not_guessed(db,prepared):
    lid=prepared['lead_id']
    report={'checkpoint':{'website':'https://bright-demo.com/','frontier':[
        {'url':'https://bright-demo.com/business-enquiries','depth':1},
        {'url':'https://bright-demo.com/media-relations','depth':1},
        {'url':'https://foreign-demo.com/contact','depth':1}]}}
    db.execute('INSERT INTO crawls(lead_id,report,created_at) VALUES(?,?,?)',(lid,json.dumps(report),time.time()-1))
    lead=db.one('SELECT * FROM leads WHERE id=?',(lid,))
    assert set(official_contact_seeds(db,lead))=={'https://bright-demo.com/business-enquiries','https://bright-demo.com/media-relations'}


async def test_contact_recovery_obeys_saved_origin_cooldown_before_any_search_or_fetch(db,settings,prepared,monkeypatch):
    lid=prepared['lead_id']
    report={'checkpoint':{'domain_not_before':time.time()+300}}
    db.execute('INSERT INTO crawls(lead_id,report,created_at) VALUES(?,?,?)',(lid,json.dumps(report),time.time()-1))
    async def forbidden(*args,**kwargs):pytest.fail('No network request during origin cooldown')
    monkeypatch.setattr('outreach.providers.discover',forbidden)
    monkeypatch.setattr(PublicWeb,'get',forbidden)
    with pytest.raises(ValueError,match='cooldown'):
        await research_contacts(db,settings,lid)


async def test_contact_recovery_reconciles_failed_url_without_losing_saved_pages_or_other_work(db,settings,prepared,monkeypatch):
    lid=prepared['lead_id']
    settings.browser_enabled=False
    settings.crawl_render_mode='never'
    settings.crawl_delay_seconds=.001
    settings.discovery_query_delay_seconds=.001
    root='https://bright-demo.com/'
    contact=root+'contact'
    other=root+'services'
    report={'status':'partial','pages':[{'url':root}],'errors':[{'url':contact,'retryable':True}],
      'checkpoint':{'website':root,'frontier':[], 'retry_urls':[
        {'url':contact,'depth':1,'failures':1,'not_before':0},
        {'url':other,'depth':1,'failures':1,'not_before':time.time()+100}], 'inflight':{'url':contact,'depth':1}}}
    db.execute('INSERT INTO crawls(lead_id,report,created_at) VALUES(?,?,?)',(lid,json.dumps(report),time.time()-1))
    before=db.one('SELECT * FROM evidence WHERE id=?',(prepared['evidence_id'],))
    async def search(*args,**kwargs):return [{'url':contact,'title':'Contact'}]
    async def get(self,url,*args):
        return (url,'User-agent: *\nAllow: /',200) if url.endswith('/robots.txt') else (url,'<p>Bright Demo UK consulting hello@bright-demo.com</p>',200)
    monkeypatch.setattr('outreach.providers.discover',search)
    monkeypatch.setattr(PublicWeb,'get',get)
    result=await research_contacts(db,settings,lid)
    saved=json.loads(db.one('SELECT report FROM crawls')['report'])
    assert result['pages_saved']==1 and saved['errors'][0]['resolved_at']
    assert saved['retry_pending']==saved['remaining']==1 and saved['checkpoint']['retry_urls'][0]['url']==other
    assert saved['checkpoint']['inflight'] is None and len(saved['pages'])==2
    assert db.one('SELECT * FROM evidence WHERE id=?',(prepared['evidence_id'],))==before
    assert not db.one("SELECT 1 FROM messages WHERE state='sent'")


async def test_contact_recovery_keeps_url_backoff_even_if_search_rediscovers_the_route(db,settings,prepared,monkeypatch):
    lid=prepared['lead_id']
    contact='https://bright-demo.com/contact'
    report={'checkpoint':{'website':'https://bright-demo.com/','frontier':[],
        'retry_urls':[{'url':contact,'depth':1,'failures':1,'not_before':time.time()+300}]}}
    # Keep the fixture's evidence inside this crawl regardless of how long
    # review/draft setup takes on a busy machine. This test checks URL cooldown.
    fetched = db.one('SELECT fetched_at FROM evidence WHERE id=?', (prepared['evidence_id'],))['fetched_at']
    db.execute('INSERT INTO crawls(lead_id,report,created_at) VALUES(?,?,?)',(lid,json.dumps(report),fetched-1))
    settings.discovery_query_delay_seconds=.001
    async def search(*args,**kwargs):return [{'url':contact,'title':'Contact'}]
    async def forbidden(*args,**kwargs):pytest.fail('Recovered search hint must not reset URL cooldown')
    monkeypatch.setattr('outreach.providers.discover',search)
    monkeypatch.setattr(PublicWeb,'get',forbidden)
    result=await research_contacts(db,settings,lid)
    assert result['state']=='held' and result['pages_saved']==0
    assert result['deferred_retry_urls']==[contact]
