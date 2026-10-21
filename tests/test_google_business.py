"""Campaign 3 public Google business intake: visible evidence, no guessed websites/inboxes."""
import copy
import hashlib
import json

import pytest
from fastapi.testclient import TestClient

from outreach import google_business as maps, preparation, email_writer
from outreach.app import create_app
from outreach.profiles import canonical_profile, add_profile_lead
from outreach.research import discover_leads, research_lead

URL = 'https://www.google.com/maps/place/Bright+Plumbing/'
HTML = '''<title>Bright Plumbing - Google Maps</title><main role="main"><h1>Bright Plumbing</h1>
<button jsaction="pane.rating.category">Plumber</button>
<button data-item-id="address" aria-label="Address: 10 Fixture Street, Bristol, UK">Address</button>
<button data-item-id="phone:tel:01170000000" aria-label="Phone: 0117 000 0000">Phone</button>
<div data-item-id="description">Plumbing services. Message us with your plumbing requirements for a quote.</div>
<div data-review-id="fake"><p>Reviewer private-review@gmail.com</p><a href="https://reviewer.example/">Website</a></div>
<div hidden><a data-item-id="email" href="mailto:hidden@fixture.example">Email</a></div></main>'''


@pytest.mark.parametrize('url,expected', [
    ('https://google.com/maps?cid=00123', 'https://www.google.com/maps?cid=123'),
    ('https://www.google.com/maps/place/Bright/@1,2/data=!4m1!1s0xabc:0x7b?hl=en', 'https://www.google.com/maps/place/Bright/@1,2/data=!4m1!1s0xabc:0x7b'),
    ('https://www.google.com/maps/place/Bright?cid=123', 'https://www.google.com/maps/place/Bright?cid=123'),
    ('https://www.google.com/maps/place/Bright/?hl=en&entry=ttu', 'https://www.google.com/maps/place/Bright'),
])
def test_maps_listing_identity_deduplicates_current_public_links(url, expected):
    assert maps.listing_url(url) == expected
    assert canonical_profile(url) == expected


@pytest.mark.parametrize('url', ['https://google.com/maps/search/plumbers', 'https://google.com/maps',
                                 'https://google.com/maps?cid=0', 'https://google.com/maps?cid=bad',
                                 'https://notgoogle.com/maps/place/Bright', 'https://127.0.0.1/maps?cid=123',
                                 'https://google.com/search?q=plumbers', 'https://google.com/maps?q=plumbers'])
def test_search_home_and_arbitrary_query_are_never_business_identity(url):
    with pytest.raises(ValueError):
        maps.listing_url(url)


@pytest.mark.parametrize('variant,state', [('normal', 'captured'), ('closed', 'business_closed'), ('captcha', 'login_or_challenge'), ('consent', 'consent_or_challenge'), ('search', 'fields_not_ready'), ('empty', 'fields_not_ready')])
def test_only_primary_visible_listing_fields_are_business_evidence(variant, state):
    html = HTML
    if variant == 'closed':
        html = html.replace('</h1>', '</h1><span>Permanently closed</span>')
    elif variant == 'captcha':
        html = html.replace('Bright Plumbing - Google Maps', 'Unusual traffic')
    elif variant == 'consent':
        html = '<form action="https://consent.google.com/save"></form>'+html
    elif variant == 'search':
        html = '<main role="main"><div role="feed"><h1>Plumbers</h1></div></main>'
    elif variant == 'empty':
        html = '<main><h1>Google Maps</h1></main>'
    result = maps.parse_listing(URL, html)
    assert result['state'] == state
    if state == 'captured':
        assert result['name'] == 'Bright Plumbing' and result['public_phone'] == '0117 000 0000'
        assert result['address'].endswith('UK') and result['business_category'] == 'Plumber'
        assert result['website_field'] == 'not_observed' and result['absence_confirmed'] is False
        assert result['published_emails'] == [] and 'gmail.com' not in result['text'] and 'hidden@' not in result['text']
        assert result['sha256'] == hashlib.sha256(result['text'].encode()).hexdigest()


def test_primary_website_and_explicit_email_are_extracted_without_reviews():
    html = HTML.replace('</h1>', '</h1><a data-item-id="authority" href="https://bright-fixture.com/contact">Website</a><a data-item-id="email" href="mailto:business@bright-fixture.com">Email</a>')
    result = maps.parse_listing(URL, html)
    assert result['outgoing_websites'] == ['https://bright-fixture.com/']
    assert result['published_emails'] == ['business@bright-fixture.com']
    assert 'Business email: business@bright-fixture.com' in result['text']


def test_nested_hidden_listing_fields_are_removed_without_losing_current_capture():
    html = HTML.replace('</h1>', '</h1><div style="display: none"><a style="color:red" data-item-id="email" href="mailto:private@fixture.example">Email</a></div>')
    result = maps.parse_listing(URL, html)
    assert result['state'] == 'captured' and result['published_emails'] == []
    assert 'private@fixture' not in result['text']


def test_search_result_cards_are_scoped_and_bounded():
    html = '<a href="'+URL+'">Navigation</a><main><div role="feed">'+''.join('<a aria-label="Business '+str(i)+'" href="'+URL.replace('Bright+Plumbing', 'Business+'+str(i))+'">Open</a>' for i in range(4))+'</div></main>'
    rows, state = maps.parse_search('https://www.google.com/maps/search/plumbers', html, 2)
    assert not state and len(rows) == 2 and rows[0]['title'] == 'Business 0'


@pytest.fixture
async def listing(db, settings, monkeypatch):
    settings.sending_enabled = settings.followups_enabled = False
    settings.draft_model, settings.draft_api_key = 'fictional-model', 'fictional-key'
    snapshot = maps.parse_listing(URL, HTML)
    signal = {'company': 'Bright Plumbing', 'source_url': maps.listing_url(URL), 'platform': 'google.com',
              'website': '', 'state': 'no_company_match', 'public_snapshot': snapshot,
              'website_search': {'completed': True, 'queries': [{'query': 'Bright Plumbing official website Bristol', 'engine_issues': []}], 'errors': [], 'engine_issues': []}}
    async def resolve(*args):
        return copy.deepcopy(signal)
    monkeypatch.setattr('outreach.profiles.resolve_signal', resolve)
    monkeypatch.setattr('outreach.discovery.resolve_signal', resolve)
    gid = maps.campaign(db)
    lid = add_profile_lead(db, 'Bright Plumbing', URL, 'A', 'UK', campaign_id=gid)
    await research_lead(db, settings, lid)
    return lid, signal


async def test_phone_only_is_saved_but_never_guessed_as_email(db, settings, monkeypatch, listing):
    lid, _ = listing
    monkeypatch.setattr(email_writer, 'chat', lambda *a, **kw: pytest.fail('No-email listing called the AI writer'))
    with pytest.raises(ValueError, match='Public business phone saved'):
        preparation.prepare(db, settings, lid)
    assert not db.one('SELECT 1 FROM contacts') and not db.one('SELECT 1 FROM messages')
    assert 'Phone: 0117 000 0000' in db.one('SELECT text FROM evidence')['text']


async def test_found_site_on_refresh_excludes_launch_without_creating_website_target(db, settings, listing):
    lid, signal = listing
    signal.update(website='https://bright-fixture.com/', state='linked_website_candidate')
    await research_lead(db, settings, lid)
    assert db.one('SELECT website_status FROM leads WHERE id=?', (lid,))['website_status'] == 'website_found'
    assert db.one('SELECT count(*) n FROM leads')['n'] == 1
    assert 'campaign_exclusion' in json.loads(db.one('SELECT report FROM crawls ORDER BY id DESC')['report'])
    assert not db.one("SELECT 1 FROM jobs WHERE kind='research'")


def test_google_mode_queues_in_named_campaign_three_and_persists_schedule(settings, db):
    client = TestClient(create_app(settings), headers={'Authorization': 'Bearer '+settings.api_token})
    request = {'query': 'plumbers Bristol UK', 'campaign': 'A', 'country_hint': 'UK', 'limit': 10, 'discovery_source': 'google_maps'}
    assert client.post('/api/discover', json=request).status_code == 200
    group = db.one('SELECT * FROM campaign_groups WHERE name=?', (maps.CAMPAIGN_NAME,))
    assert group['goal'] == 'A' and group['is_default'] == 0
    payload = json.loads(db.one("SELECT payload FROM jobs WHERE kind='discover'")['payload'])
    assert payload['campaign_id'] == group['id'] and payload['profile_first'] is True
    assert client.post('/api/schedules', json={**request, 'interval_hours': 24}).status_code == 200
    assert db.one('SELECT discovery_source,campaign_id FROM schedules') == {'discovery_source': 'google_maps', 'campaign_id': group['id']}
    assert client.post('/api/discover', json={**request, 'campaign': 'B'}).status_code == 400
    assert len(db.all('SELECT * FROM campaign_groups')) == 3


async def test_maps_batch_excludes_known_sites_and_ambiguous_or_blocked_sources(db, settings, monkeypatch):
    async def page(*a):
        return {'state': 'fields_not_ready', 'url': 'https://www.google.com/maps/search/plumbers'}
    async def index(*a, **kw):
        return [{'url': URL.replace('Bright+Plumbing', str(i)), 'title': 'Business '+str(i)} for i in range(4)]
    async def resolve(s, row, *a):
        idx=int(row['title'].split()[-1])
        return {'source_url': row['url'], 'platform': 'google.com', 'company': row['title'],
                'website': 'https://found-fixture.com/' if idx == 0 else '',
                'state': 'ambiguous_search_matches' if idx == 1 else 'no_company_match',
                'public_snapshot': {'state': 'fields_not_ready' if idx == 2 else 'captured'},
                'website_search': {'completed': True}}
    monkeypatch.setattr(maps, 'page', page)
    monkeypatch.setattr('outreach.providers.discover', index)
    monkeypatch.setattr('outreach.discovery.resolve_signal', resolve)
    await discover_leads(db, settings, 'plumbers Bristol', 'A', 'UK', 10, discovery_source='google_maps')
    leads = db.all('SELECT * FROM leads')
    assert [lead['company'] for lead in leads] == ['Business 1','Business 3']
    assert leads[0]['campaign_id'] == maps.campaign(db)
    report = json.loads(db.one("SELECT detail FROM events WHERE kind='discovery'")['detail'])['report']
    assert {r['reason'] for r in report['skipped']} == {'official_website_found','fields_not_ready'}
    assert not db.one('SELECT 1 FROM contacts') and not db.one('SELECT 1 FROM send_attempts')

async def test_google_profile_with_published_email_prepares_only_a_website_launch(db, settings, monkeypatch, listing):
    lid, signal = listing
    signal['public_snapshot'] = maps.parse_listing(URL, HTML.replace('</h1>', '</h1><a data-item-id="email" href="mailto:business@bright-fixture.com">Email</a>'))
    await research_lead(db, settings, lid)
    page = db.one('SELECT * FROM evidence WHERE lead_id=?', (lid,))
    value = {'ready': True, 'review': {'company': 'Bright Plumbing', 'country': 'UK', 'country_source': page['url'],
             'country_quote': 'Address: 10 Fixture Street, Bristol, UK', 'timezone': 'Europe/London', 'business_type': 'other',
             'service': 'website_build', 'primary_goal': 'inquiries_bookings', 'fit_notes': 'A plumbing business publishes its quote request process; explore a focused services website.',
             'evidence_id': page['id'], 'quote': 'Plumbing services. Message us with your plumbing requirements for a quote.',
             'profile_activity_quote': 'Business category: Plumber', 'observation': 'Your listing invites plumbing enquiries with project requirements.',
             'suggestion': 'Build a focused plumbing services website with a quote request form for service and location details.'}}
    calls=[]
    def chat(*args, **kw):
        calls.append(args[1])
        kw['before_request']()
        return json.dumps(value)
    monkeypatch.setattr(email_writer, 'chat', chat)
    preparation.prepare(db, settings, lid)
    assert 'primary service must be website_build' in calls[0]
    assert db.one('SELECT service FROM leads')['service'] == 'website_build'
    assert db.one('SELECT COUNT(*) n FROM messages')['n'] == 1
    assert db.one('SELECT state,due_at,sent_at FROM messages') == {'state':'draft','due_at':None,'sent_at':None}
    assert not db.one('SELECT 1 FROM send_attempts')
    value['review']['service']='ai_calling_agent'
    with pytest.raises(ValueError, match='website_build'):
        preparation._validate_review(db.one('SELECT * FROM leads WHERE id=?',(lid,)), value, [page])


def test_identity_key_deduplicates_observed_listing_and_cid_reference(db):
    full='https://www.google.com/maps/place/Fixture/data=!1s0xabc:0x7b'
    cid='https://www.google.com/maps?cid=123'
    assert maps.listing_key(full) == maps.listing_key(cid)
    gid=maps.campaign(db)
    first=add_profile_lead(db,'Bright Plumbing',full,'A','UK',campaign_id=gid)
    assert add_profile_lead(db,'Bright Plumbing',cid,'A','UK',campaign_id=gid)==first
    from outreach.profiles import source_allowed
    assert source_allowed(db.one('SELECT * FROM leads WHERE id=?',(first,)),cid)
    assert db.one('SELECT profile_url FROM leads')['profile_url']==full


@pytest.mark.parametrize('denied', ['robots_denied','login_or_challenge','consent_or_challenge','http_429','source_unavailable'])
async def test_google_denial_stops_the_run_without_listing_or_index_retries(settings, monkeypatch, denied):
    async def page(*a):
        return {'state':denied,'url':'https://www.google.com/maps/search/plumbers'}
    async def forbidden(*a,**kw):
        pytest.fail('Denied Google source was retried through another request')
    monkeypatch.setattr(maps,'page',page)
    monkeypatch.setattr('outreach.providers.discover',forbidden)
    monkeypatch.setattr('outreach.discovery.resolve_signal',forbidden)
    rows,report=await maps.prospect_candidates(settings,'plumbers Bristol','UK',10)
    assert rows==[] and report['stop_reason']==denied


def test_schema_seven_migration_preserves_records_and_defaults_to_mixed(db, prepared):
    from outreach.db import DB
    before=db.all('SELECT * FROM messages')
    db.execute('ALTER TABLE schedules DROP COLUMN discovery_source')
    db.execute('PRAGMA user_version=7')
    reopened=DB(db.path)
    assert reopened.one('PRAGMA user_version')['user_version']==8
    assert reopened.all('SELECT * FROM messages')==before


def test_invalid_target_does_not_create_a_campaign(db):
    wrong = db.one("SELECT id FROM campaign_groups WHERE goal='A'")['id']
    with pytest.raises(ValueError, match='Campaign 3'):
        maps.campaign(db, wrong)
    assert not db.one('SELECT 1 FROM campaign_groups WHERE name=?', (maps.CAMPAIGN_NAME,))


def test_search_aliases_share_one_business_budget():
    full = 'https://www.google.com/maps/place/Fixture/data=!1s0xabc:0x7b'
    alias = 'https://www.google.com/maps/place/Fixture/data=!1s0xabc%3A0x7b'
    html = '<div role="feed">'+''.join(f'<a aria-label="Fixture" href="{u}"></a>' for u in (full, alias, 'https://www.google.com/maps?cid=123'))+'</div>'
    rows, state = maps.parse_search('https://www.google.com/maps/search/plumbers', html, 10)
    assert not state and rows == [{'url': full, 'title': 'Fixture', 'snippet': ''}]


async def test_recurring_google_job_retains_campaign_three_and_discovery_source(db, settings, monkeypatch):
    import asyncio
    import time
    from outreach import worker
    settings.worker_enabled = True
    gid = maps.campaign(db)
    db.execute('INSERT INTO schedules(query,campaign,country_hint,result_limit,interval_hours,next_run,campaign_id,profile_first,discovery_source) VALUES(?,?,?,?,?,?,?,?,?)',
               ('UK plumbers Bristol', 'A', 'UK', 10, 24, time.time()-1, gid, 1, 'google_maps'))
    stop, received = asyncio.Event(), []
    async def execute(_db, _settings, job):
        received.append(json.loads(job['payload']))
        stop.set()
    monkeypatch.setattr(worker, 'execute_job', execute)
    await asyncio.wait_for(worker.job_loop(db, settings, stop, {'discover'}, schedules=True), timeout=3)
    assert received == [{'query': 'UK plumbers Bristol', 'campaign': 'A', 'country_hint': 'UK', 'limit': 10,
                         'campaign_id': gid, 'profile_first': True, 'discovery_source': 'google_maps'}]
    assert db.one('SELECT next_run FROM schedules')['next_run'] > time.time()+23*3600


@pytest.mark.parametrize('website', [False, True])
async def test_real_resolver_uses_current_google_capture_and_independent_lookup(settings, monkeypatch, website):
    from outreach.discovery import resolve_signal
    settings.discovery_query_delay_seconds = 0
    html = HTML.replace('</h1>', '</h1><a data-item-id="authority" href="https://bright-fixture.com/">Website</a>') if website else HTML
    async def current_page(_settings, url):
        return {'state': 'captured', 'url': url, 'html': html}
    queries = []
    async def independent_search(_settings, query, limit, **kw):
        queries.append(query)
        return []
    monkeypatch.setattr(maps, 'page', current_page)
    monkeypatch.setattr('outreach.providers.discover', independent_search)
    result = await resolve_signal(settings, {'url': URL, 'title': 'Outdated generic Maps title', 'snippet': ''}, 'UK', ['google.com'])
    assert result['public_snapshot']['title'] == 'Bright Plumbing'
    if website:
        assert result['website'] == 'https://bright-fixture.com/' and result['state'] == 'linked_website_candidate'
        assert not queries
    else:
        assert result['company'] == 'Bright Plumbing' and result['state'] == 'no_company_match'
        assert result['website_search']['completed'] and len(queries) >= 1
        assert not result['website']
        assert 'Bright Plumbing' in queries[0] and 'Bright Plumbing' in queries[-1]
        assert all('Outdated generic' not in query for query in queries)


def test_google_website_launch_rule_does_not_override_existing_campaign_b(settings, monkeypatch):
    text = ('Bright Plumbing. UK business. We sell our own handmade products through business messages. '
            'Business email: business@bright-fixture.com')
    quote = 'We sell our own handmade products through business messages.'
    lead = {'company': 'Bright Plumbing', 'campaign': 'B', 'lead_kind': 'profile',
            'profile_url': URL, 'website_status': 'website_not_found'}
    page = {'id': 1, 'url': URL, 'text': text, 'title': 'Bright Plumbing', 'fetched_at': 1, 'sha256': 'fixture'}
    value = {'ready': True, 'review': {'company': 'Bright Plumbing', 'country': 'UK', 'timezone': 'Europe/London',
        'country_source': URL, 'country_quote': 'UK business.', 'business_type': 'other',
        'service': 'store_launch', 'primary_goal': 'd2c_growth', 'fit_notes': 'An owned handmade product business sells through messages.',
        'evidence_id': 1, 'quote': quote, 'profile_activity_quote': quote,
        'observation': 'Your profile describes selling your own handmade products through business messages.',
        'suggestion': 'Build a small product catalogue with delivery information and an order request route.',
        'selling_stage': 'starting_ecommerce', 'commerce_evidence_id': 1, 'commerce_quote': quote,
        'd2c_fit_notes': 'Owned handmade consumer products ordered through messages support discussing a store launch.'}}
    def chat(_settings, instructions, packet, **kwargs):
        assert 'primary service must be website_build' not in instructions
        return json.dumps(value)
    monkeypatch.setattr(email_writer, 'chat', chat)
    result = preparation._assessment(settings, lead, [page], lambda: None)
    assert preparation._validate_review(lead, result, [page])['service'] == 'store_launch'
