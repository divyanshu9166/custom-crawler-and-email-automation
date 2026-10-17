import json
import pytest

from outreach.discovery import name_matches, prospect_candidates, public_snapshot, resolve_signal
from outreach.research import discover_leads
from outreach.web import PublicWeb


async def test_indexed_platform_resolves_to_official_website_not_platform_email(settings, monkeypatch):
    settings.discovery_query_delay_seconds = .1
    async def snapshot(s, url, platform=False):
        if platform:
            return {'state':'robots_denied','url':url}
        return {'state':'captured','url':url,'title':'Bright Studio','text':'Bright Studio UK consulting','sha256':'hash'}
    async def search(*args, **kwargs):
        return [{'url':'https://bright-demo.com/about','title':'Bright Studio | Website','snippet':''}]
    monkeypatch.setattr('outreach.discovery.public_snapshot', snapshot)
    monkeypatch.setattr('outreach.providers.discover', search)
    signal = await resolve_signal(settings, {'url':'https://linkedin.com/company/bright-studio','title':'Bright Studio | LinkedIn','snippet':'UK business'}, 'UK', ['linkedin.com'])
    assert signal['website']=='https://bright-demo.com/'
    assert signal['state']=='name_matched_website_candidate' and signal['indexed_signal_only']


async def test_ambiguous_and_individual_profiles_stay_unresolved(settings, monkeypatch):
    async def snapshot(*args, **kwargs):
        return {'state':'captured','outgoing_websites':['https://one.example.com/','https://two.example.org/']}
    monkeypatch.setattr('outreach.discovery.public_snapshot',snapshot)
    signal = await resolve_signal(settings, {'url':'https://clutch.co/profile/test','title':'Test Company'}, 'UK', ['clutch.co'])
    assert signal['state']=='ambiguous_websites' and not signal['website']
    async def denied(*args, **kwargs): return {'state':'robots_denied'}
    monkeypatch.setattr('outreach.discovery.public_snapshot',denied)
    signal = await resolve_signal(settings, {'url':'https://linkedin.com/in/person','title':'Person | LinkedIn'}, 'UK', ['linkedin.com'])
    assert not signal['website']


async def test_multi_platform_discovery_persists_signals_deduplicates_and_queues_research(db,settings,monkeypatch):
    settings.discovery_platforms='linkedin.com,x.com'
    settings.discovery_query_delay_seconds=.1
    calls=[]
    async def search(s,q,limit,include_platforms=False):
        calls.append(q)
        if 'site:' in q:
            return [{'url':'https://linkedin.com/company/bright','title':'Bright Studio','snippet':'UK design company'}]
        return [{'url':'https://bright-demo.com/about','title':'Bright Studio','snippet':'UK design company'}]
    async def resolve(*args):
        return {'source_url':'https://linkedin.com/company/bright','website':'https://bright-demo.com/','company':'Bright Studio','state':'linked_website_candidate','indexed_signal_only':True,'published_emails':['held@elsewhere.example']}
    monkeypatch.setattr('outreach.providers.discover',search)
    monkeypatch.setattr('outreach.discovery.resolve_signal',resolve)
    await discover_leads(db,settings,'UK design company','A','UK',10)
    assert len(calls)==4 and any('site:x.com' in q for q in calls)
    assert db.one('SELECT COUNT(*) n FROM leads')['n']==1
    assert db.one('SELECT COUNT(*) n FROM jobs WHERE kind="research"')['n']==1
    assert db.one('SELECT COUNT(*) n FROM contacts')['n']==0
    event=json.loads(db.one('SELECT detail FROM events WHERE kind="prospect_signal"')['detail'])
    assert event['lead_id'] and event['indexed_signal_only']


async def test_robots_denial_never_fetches_profile(settings,monkeypatch):
    class Robots:
        def can_fetch(self,*args):return False
    async def robots(*args):return Robots(),.1,'https://x.com/'
    async def forbidden(*args):raise AssertionError('Denied profile fetched')
    monkeypatch.setattr(PublicWeb,'robots',robots)
    monkeypatch.setattr(PublicWeb,'get',forbidden)
    assert (await public_snapshot(settings,'https://x.com/bright',platform=True))['state']=='robots_denied'
    with pytest.raises(ValueError,match='cannot perform'):
        await PublicWeb(settings,signal_only=True).crawl('https://x.com/bright')


async def test_failed_platform_queries_do_not_discard_successful_official_results(settings,monkeypatch):
    settings.discovery_platforms='x.com'
    settings.discovery_query_delay_seconds=.1
    async def search(s,q,*args,**kwargs):
        if 'site:' in q:
            raise TimeoutError()
        return [{'url':'https://bright-demo.com/','title':'Bright Studio'}]
    monkeypatch.setattr('outreach.providers.discover',search)
    rows,report=await prospect_candidates(settings,'UK studio','UK',1)
    assert len(rows)==1 and report['errors'][0]['error_type']=='TimeoutError'


async def test_reciprocal_profile_link_disambiguates_official_brand_from_reseller(settings,monkeypatch):
    settings.discovery_query_delay_seconds=.1
    async def snapshot(s,url,platform=False):
        if platform:
            return {'state':'robots_denied'}
        return {'state':'captured','title':'Bright Studio','text':'Bright Studio design','sha256':'hash',
                'public_links':['https://uk.linkedin.com/company/bright/'] if 'bright-demo' in url else []}
    async def search(*args,**kwargs):
        return [{'url':'https://reseller.example.org/','title':'Bright Studio services'},
                {'url':'https://bright-demo.com/','title':'Bright Studio'}]
    monkeypatch.setattr('outreach.discovery.public_snapshot',snapshot)
    monkeypatch.setattr('outreach.providers.discover',search)
    result=await resolve_signal(settings,{'url':'https://www.linkedin.com/company/bright','title':'Bright Studio - LinkedIn'},'UK',['linkedin.com'])
    assert result['state']=='reciprocal_profile_link_candidate' and result['website']=='https://bright-demo.com/'


async def test_generic_country_results_are_not_imported_as_clients(settings,monkeypatch):
    settings.discovery_platforms=''
    async def search(*args,**kwargs):
        return [{'url':'https://www.gov.uk/','title':'Welcome to GOV.UK','snippet':'United Kingdom government'},
                {'url':'https://bright-demo.com/','title':'Bright Studio skincare shop','snippet':'UK skincare'}]
    monkeypatch.setattr('outreach.providers.discover',search)
    rows,report=await prospect_candidates(settings,'UK skincare brand contact','UK',10)
    assert len(rows)==1 and 'bright-demo' in rows[0]['url']
    assert report['skipped'][0]['reason']=='no_query_term_in_indexed_result'


def test_short_brand_acronym_is_not_discarded():
    assert name_matches('AA Skincare','AA Skincare Natural Products')
    assert not name_matches('AA Skincare','Acne and Aging Skincare Products')


async def test_exact_regional_brand_domain_remains_an_unverified_candidate(settings,monkeypatch):
    settings.discovery_query_delay_seconds=.1
    async def snapshot(s,url,platform=False):
        if platform:
            return {'state':'robots_denied'}
        return {'state':'captured','title':'Bright Studio','text':'Bright Studio design','sha256':'hash','public_links':[]}
    async def search(*args,**kwargs):
        return [{'url':'https://brightstudio.com/','title':'Bright Studio'},
                {'url':'https://brightstudio.co.uk/','title':'Bright Studio'}]
    monkeypatch.setattr('outreach.discovery.public_snapshot',snapshot)
    monkeypatch.setattr('outreach.providers.discover',search)
    result=await resolve_signal(settings,{'url':'https://linkedin.com/company/bright','title':'Bright Studio UK - LinkedIn'},'UK',['linkedin.com'])
    assert result['state']=='exact_brand_domain_candidate' and result['website']=='https://brightstudio.co.uk/'
    assert result['indexed_signal_only'] and 'not verified' in result['match_note']


async def test_late_cancellation_retains_discovered_candidate_and_unresolved_platform_signal(db,settings,monkeypatch):
    import asyncio
    settings.discovery_platforms='x.com,linkedin.com'
    settings.discovery_query_delay_seconds=.1
    async def search(s,q,*args,**kwargs):
        if 'linkedin' in q:
            raise asyncio.CancelledError()
        if 'site:' in q:
            return [{'url':'https://x.com/bright','title':'Bright Studio','snippet':'UK design company'}]
        return [{'url':'https://bright-demo.com/','title':'Bright Studio','snippet':'UK design company'}]
    async def resolve(*args):
        return {'source_url':'https://x.com/bright','platform':'x.com','state':'ambiguous_search_matches','website':''}
    monkeypatch.setattr('outreach.providers.discover',search)
    monkeypatch.setattr('outreach.discovery.resolve_signal',resolve)
    with pytest.raises(asyncio.CancelledError):
        await discover_leads(db,settings,'UK design company','A','UK',1)
    assert db.one('SELECT COUNT(*) n FROM leads')['n']==1
    assert db.one('SELECT COUNT(*) n FROM jobs WHERE kind="research"')['n']==1
    assert db.one('SELECT COUNT(*) n FROM events WHERE kind="prospect_signal"')['n']==1


@pytest.mark.parametrize('country,expected,language',[('US','United States','en-US'),('UK','United Kingdom','en-GB')])
async def test_market_selection_scopes_search_and_locale(settings,monkeypatch,country,expected,language):
    settings.discovery_platforms=''
    calls=[]
    async def search(s,q,*args,**kwargs):
        calls.append((q,s.search_language))
        return []
    monkeypatch.setattr('outreach.providers.discover',search)
    await prospect_candidates(settings,'Roofing contractors',country,1)
    assert calls==[('Roofing contractors '+expected,language)]
