"""Controlled bulk profile acquisition/preparation, without delivery or real platforms."""
import copy
import hashlib
import json
import time

import pytest
from fastapi.testclient import TestClient

from outreach import email_writer, preparation
from outreach.app import create_app
from outreach.profiles import add_profile_lead, personal_business_snapshot
from outreach.research import research_lead, discover_leads

PROFILE = 'https://x.com/fictionalbright'
TEXT = ('Bright Studio. We offer UK consulting services. Call us to arrange a consultation. '
        'We sell our own handmade products through business messages. Business email: bright-fixture@gmail.com')


@pytest.fixture
async def profile(db, settings, monkeypatch):
    settings.sending_enabled = False
    settings.followups_enabled = False
    settings.draft_api_key = 'fictional-key'
    settings.draft_model = 'fictional-profile-writer'
    snapshot = {'state': 'captured', 'url': PROFILE, 'title': 'Bright Studio', 'text': TEXT,
                'capture_method': 'public_html', 'published_emails': ['bright-fixture@gmail.com'],
                'sha256': hashlib.sha256(TEXT.encode()).hexdigest()}
    signal = {'company': 'Bright Studio', 'source_url': PROFILE, 'platform': 'x.com', 'website': '',
              'state': 'no_company_match', 'public_snapshot': snapshot,
              'website_search': {'completed': True, 'queries': [{'query': 'Bright Studio official website UK', 'engine_issues': []}], 'engine_issues': [], 'errors': []}}
    async def resolve(*_args):
        return copy.deepcopy(signal)
    monkeypatch.setattr('outreach.profiles.resolve_signal', resolve)
    monkeypatch.setattr('outreach.discovery.resolve_signal', resolve)
    lid = add_profile_lead(db, 'Bright Studio', PROFILE, 'A', 'UK')
    await research_lead(db, settings, lid)
    return lid, signal


def assessment(db, lid, campaign='A'):
    page = db.one('SELECT * FROM evidence WHERE lead_id=?', (lid,))
    value = {'ready': True, 'review': {'company': 'Bright Studio', 'country': 'UK', 'timezone': 'Europe/London',
        'country_source': PROFILE, 'country_quote': 'We offer UK consulting services.', 'business_type': 'other',
        'service': 'website_build' if campaign == 'A' else 'store_launch',
        'primary_goal': 'inquiries_bookings' if campaign == 'A' else 'd2c_growth',
        'fit_notes': 'Business publishes its consulting and order process; explore a focused launch concept.',
        'evidence_id': page['id'], 'quote': 'Call us to arrange a consultation.',
        'profile_activity_quote': 'We offer UK consulting services.',
        'observation': 'Your profile invites customers to arrange a consultation by phone.',
        'suggestion': 'Build one services page with a consultation request form for your team to review.',
        'selling_stage': 'starting_ecommerce', 'commerce_evidence_id': page['id'],
        'commerce_quote': 'We sell our own handmade products through business messages.',
        'd2c_fit_notes': 'Owned handmade consumer products ordered through business messages support discussing a store launch.'}}
    if campaign == 'B':
        value['review'].update(quote=value['review']['commerce_quote'], profile_activity_quote=value['review']['commerce_quote'],
                               observation='Your profile describes selling your own handmade products through business messages.',
                               suggestion='Build a small product catalogue with clear delivery information and an order request route.')
    return value


@pytest.mark.parametrize('campaign', ['A', 'B'])
async def test_automatic_profile_qualification_contact_and_one_unscheduled_email(db, settings, monkeypatch, profile, campaign):
    lid, _ = profile
    db.execute('UPDATE leads SET campaign=?,campaign_id=(SELECT id FROM campaign_groups WHERE goal=? AND is_default=1) WHERE id=?', (campaign, campaign, lid))
    value = assessment(db, lid, campaign)
    calls = []
    def chat(_settings, instructions, packet, **kwargs):
        kwargs['before_request']()
        calls.append((instructions, json.loads(packet)))
        return json.dumps(value)
    monkeypatch.setattr(email_writer, 'chat', chat)
    preparation.prepare(db, settings, lid)
    lead = db.one('SELECT * FROM leads WHERE id=?', (lid,))
    contact = db.one('SELECT * FROM contacts WHERE lead_id=?', (lid,))
    assert lead['status'] == 'qualified' and lead['website'] == ''
    assert json.loads(lead['profile_review'])['method'] == 'research_ai_profile'
    assert contact['email'] == 'bright-fixture@gmail.com' and contact['verification'] != 'safe'
    messages = db.all('SELECT * FROM messages WHERE contact_id=?', (contact['id'],))
    assert len(messages) == 1 and messages[0]['state'] == 'draft'
    assert messages[0]['sent_at'] is None and messages[0]['due_at'] is None
    assert not db.one("SELECT 1 FROM jobs WHERE kind='verify'")
    assert not db.one('SELECT 1 FROM send_attempts')
    assert preparation.latest(db, lid)['result']['state'] == 'drafts_ready'
    assert 'Website absence is unconfirmed' in calls[0][0]
    assert '[contact omitted]' in calls[0][1]['sources'][0]['text']
    assert settings.sending_enabled is False
    before = messages[:]
    preparation.prepare(db, settings, lid)
    assert db.all('SELECT * FROM messages WHERE contact_id=?', (contact['id'],)) == before
    assert len(calls) == 1


@pytest.mark.parametrize('problem', ['ambiguous', 'failed_search', 'engine_issue', 'mirror', 'identity', 'stale', 'source_changed', 'not_business', 'unlabelled_email', 'suppressed', 'shared_inbox'])
async def test_unsupported_profile_is_held_before_any_ai_call(db, settings, monkeypatch, profile, problem):
    lid, signal = profile
    crawl = db.one('SELECT * FROM crawls WHERE lead_id=?', (lid,))
    report = json.loads(crawl['report'])
    snap = report['signal']['public_snapshot']
    if problem == 'ambiguous':
        db.execute("UPDATE leads SET website_status='ambiguous' WHERE id=?", (lid,))
    elif problem == 'failed_search':
        report['signal']['website_search']['completed'] = False
    elif problem == 'engine_issue':
        report['signal']['website_search']['queries'][0]['engine_issues'] = [{'error': 'timeout'}]
    elif problem == 'mirror':
        snap['capture_method'] = 'community_mirror'
    elif problem == 'identity':
        snap['title'] = 'Another Business'
    elif problem == 'stale':
        db.execute('UPDATE crawls SET created_at=? WHERE id=?', (time.time()-31*86400, crawl['id']))
    elif problem == 'source_changed':
        db.execute("UPDATE evidence SET text=text||'changed',sha256='changed' WHERE lead_id=?", (lid,))
    elif problem in {'not_business', 'unlabelled_email'}:
        text = 'Bright Studio. UK music fan. bright-fixture@gmail.com' if problem == 'not_business' else TEXT.replace('Business email:', 'Personal contact:')
        snap['text'] = text
        digest = hashlib.sha256(text.encode()).hexdigest()
        db.execute('UPDATE evidence SET text=?,sha256=? WHERE lead_id=?', (text, digest, lid))
        events = db.all("SELECT * FROM events WHERE kind='contact_candidate_found'")
        for event in events:
            detail = json.loads(event['detail'])
            detail['evidence_sha256'] = digest
            db.execute('UPDATE events SET detail=? WHERE id=?', (json.dumps(detail), event['id']))
    elif problem == 'suppressed':
        db.execute('INSERT INTO suppression(email,reason,created_at) VALUES(?,?,?)', ('bright-fixture@gmail.com', 'opt-out', time.time()))
    elif problem == 'shared_inbox':
        from outreach.research import add_lead
        other = add_lead(db, 'Other Business', 'https://other-demo.com', 'A', 'https://other-demo.com/')
        db.execute('INSERT INTO contacts(lead_id,email,source_url,created_at,unsubscribe_token) VALUES(?,?,?,?,?)', (other, 'bright-fixture@gmail.com', 'https://other-demo.com/', time.time(), 'fictional-token'))
    db.execute('UPDATE crawls SET report=? WHERE id=?', (json.dumps(report), crawl['id']))
    def forbidden(*_args, **_kwargs):
        raise AssertionError('Unsupported source triggered an AI request')
    monkeypatch.setattr(email_writer, 'chat', forbidden)
    with pytest.raises(ValueError):
        preparation.prepare(db, settings, lid)
    assert preparation.latest(db, lid)['result']['state'] == 'needs_attention'
    assert not db.one('SELECT 1 FROM messages')
    assert not db.one('SELECT 1 FROM contacts WHERE lead_id=?', (lid,))


@pytest.mark.parametrize('problem', ['country', 'activity', 'invented_claim', 'identity', 'cancelled', 'source_race', 'settings_race'])
async def test_profile_model_errors_and_races_never_create_contacts_or_copy(db, settings, monkeypatch, profile, problem):
    lid, _ = profile
    value = assessment(db, lid)
    if problem == 'country':
        value['review']['country_quote'] = 'UK based company, invented'
    elif problem == 'activity':
        value['review']['profile_activity_quote'] = 'We offer services that were never published.'
    elif problem == 'invented_claim':
        value['review']['observation'] = 'Your business has no website and is losing customers.'
    elif problem == 'identity':
        value['review']['company'] = 'Other Studio'
    def chat(*_args, **kwargs):
        kwargs['before_request']()
        if problem == 'source_race':
            db.execute("UPDATE evidence SET text='changed',sha256='changed' WHERE lead_id=?", (lid,))
        elif problem == 'settings_race':
            settings.draft_model = 'newer-model'
        return json.dumps(value)
    monkeypatch.setattr(email_writer, 'chat', chat)
    with pytest.raises(ValueError):
        preparation.prepare(db, settings, lid, cancelled=lambda: problem == 'cancelled')
    assert not db.one('SELECT 1 FROM contacts WHERE lead_id=?', (lid,))
    assert not db.one('SELECT 1 FROM messages')


@pytest.mark.parametrize('headline,expected', [('Independent consultant', True), ('Self-employed photographer', True), ('I provide cleaning services', True), ('Software engineer at Big Company', False), ('Founder at Big Company', False), ('Previously self-employed photographer', False), ('Retired independent consultant', False)])
def test_personal_profile_needs_explicit_current_self_selling(headline, expected):
    assert personal_business_snapshot({'state': 'captured', 'headline': headline, 'text': 'Professional profile'}) is expected
    assert not personal_business_snapshot({'state': 'blocked', 'headline': headline})


async def test_profile_first_search_and_named_campaign_need_no_business_entry(db, settings, monkeypatch, profile):
    lid, _ = profile
    db.execute('DELETE FROM evidence WHERE lead_id=?', (lid,))
    db.execute('DELETE FROM crawls WHERE lead_id=?', (lid,))
    db.execute('DELETE FROM leads WHERE id=?', (lid,))
    settings.discovery_platforms = 'x.com'
    settings.discovery_query_delay_seconds = .1
    queries = []
    async def search(_settings, query, *_args, **kwargs):
        queries.append(query)
        return [{'url': 'https://unrelated-demo.com/', 'title': 'Other business', 'snippet': 'UK consulting'},
                {'url': PROFILE, 'title': 'Bright Studio', 'snippet': 'UK consulting services'}]
    monkeypatch.setattr('outreach.providers.discover', search)
    gid = db.execute('INSERT INTO campaign_groups(name,goal,created_at,updated_at) VALUES(?,?,?,?)', ('UK consultants batch', 'A', time.time(), time.time()))
    await discover_leads(db, settings, 'consulting', 'A', 'UK', 5, campaign_id=gid, profile_first=True)
    await discover_leads(db, settings, 'consulting', 'A', 'UK', 5, campaign_id=gid, profile_first=True)
    leads = db.all('SELECT * FROM leads')
    assert len(leads) == 1 and leads[0]['profile_url'] == PROFILE and leads[0]['campaign_id'] == gid
    assert all(q.startswith('site:x.com ') for q in queries)
    assert db.one("SELECT count(*) n FROM jobs WHERE kind='research'")['n'] == 1
    assert not db.one('SELECT 1 FROM contacts')


async def test_auto_schedule_and_bulk_endpoint_accept_profile_without_manual_contact(db, settings, monkeypatch, profile):
    lid, _ = profile
    settings.auto_prepare_enabled = False
    preparation.maybe_schedule(db, settings, lid)
    assert not db.one("SELECT 1 FROM jobs WHERE kind='prepare'")
    client = TestClient(create_app(settings))
    client.headers['Authorization'] = 'Bearer '+settings.api_token
    result = client.post('/api/preparation/batch', json={'limit': 25})
    assert result.status_code == 200
    assert db.one("SELECT 1 FROM jobs WHERE kind='prepare' AND json_extract(payload,'$.lead_id')=?", (lid,))


def test_search_focus_is_saved_with_recurring_campaign_and_legacy_default(settings):
    from outreach.db import DB
    client = TestClient(create_app(settings))
    client.headers['Authorization'] = 'Bearer '+settings.api_token
    request = {'query': 'independent consultants', 'campaign': 'A', 'country_hint': 'UK', 'limit': 5, 'interval_hours': 24, 'profile_first': True}
    response = client.post('/api/schedules', json=request)
    assert response.status_code == 200
    db = DB(settings.database)
    schedule = db.one('SELECT * FROM schedules')
    assert schedule['profile_first'] == 1
    request.pop('interval_hours')
    response = client.post('/api/discover', json=request)
    assert response.status_code == 200
    assert json.loads(db.one("SELECT payload FROM jobs WHERE kind='discover'")['payload'])['profile_first'] is True
    request.pop('profile_first')
    request['query'] = 'normal website search'
    assert client.post('/api/discover', json=request).status_code == 200
    job = db.one("SELECT payload FROM jobs WHERE kind='discover' ORDER BY id DESC LIMIT 1")
    assert 'profile_first' not in json.loads(job['payload'])

REAL_GENERATE = email_writer.generate_sequence


@pytest.mark.parametrize('copy_state', ['valid', 'unqualified_absence', 'no_uncertainty', 'invented_source'])
async def test_real_profile_writer_validation_preserves_uncertainty_and_current_support(db, settings, monkeypatch, profile, copy_state):
    lid, _ = profile
    value = assessment(db, lid)
    source_id = value['review']['evidence_id']
    body = ('Bright Studio invites customers to call for a consultation. I could not find a dedicated website in our search; '
            'please correct me if I missed it. We could build a services page with a consultation request form, '
            'giving customers a place to describe the help they need. If useful, an optional AI calling agent could collect enquiry details and hand them to your team. Would a one-page concept be useful?')
    if copy_state == 'unqualified_absence':
        body = 'Bright Studio, you have no website. '+body
    elif copy_state == 'no_uncertainty':
        body = 'Bright Studio invites customers to call for a consultation. We could build a services page and consultation request form. Would a one-page concept be useful?'
    requests = []
    def chat(_settings, instructions, packet, **kwargs):
        kwargs['before_request']()
        requests.append(instructions)
        if 'Assess one US/UK prospect' in instructions:
            return json.dumps(value)
        assert 'bounded profile/search check' in instructions
        return json.dumps({'messages': [{'step': 0, 'subject': 'A services page for Bright Studio', 'body': body,
                     'support': [{'evidence_id': source_id, 'quote': 'Invented business claim' if copy_state == 'invented_source' else value['review']['quote']}]}]})
    monkeypatch.setattr(email_writer, 'generate_sequence', REAL_GENERATE)
    monkeypatch.setattr(email_writer, 'chat', chat)
    if copy_state == 'valid':
        preparation.prepare(db, settings, lid)
        assert len(requests) == 2
        assert db.one('SELECT count(*) n FROM messages')['n'] == 1
    else:
        with pytest.raises(ValueError):
            preparation.prepare(db, settings, lid)
        assert not db.one('SELECT 1 FROM messages')
    assert not db.one('SELECT 1 FROM send_attempts')


async def test_auto_enabled_schedules_a_profile_without_per_prospect_review(db, settings, profile):
    lid, _ = profile
    settings.auto_prepare_enabled = True
    preparation.maybe_schedule(db, settings, lid)
    preparation.maybe_schedule(db, settings, lid)
    assert db.one("SELECT count(*) n FROM jobs WHERE kind='prepare'")['n'] == 1
    assert not db.one('SELECT 1 FROM contacts')


async def test_recurring_worker_preserves_profile_first_mode_and_campaign(db, settings, monkeypatch):
    import asyncio
    from outreach import worker
    settings.worker_enabled = True
    gid = db.one("SELECT id FROM campaign_groups WHERE goal='A'")['id']
    db.execute('INSERT INTO schedules(query,campaign,country_hint,result_limit,interval_hours,next_run,campaign_id,profile_first) VALUES(?,?,?,?,?,?,?,?)',
               ('UK consulting', 'A', 'UK', 10, 24, time.time()-1, gid, 1))
    stop = asyncio.Event()
    received = []
    async def execute(_db, _settings, job):
        received.append(json.loads(job['payload']))
        stop.set()
    monkeypatch.setattr(worker, 'execute_job', execute)
    await asyncio.wait_for(worker.job_loop(db, settings, stop, {'discover'}, schedules=True), timeout=3)
    assert received == [{'query': 'UK consulting', 'campaign': 'A', 'country_hint': 'UK', 'limit': 10, 'campaign_id': gid, 'profile_first': True}]
    assert db.one('SELECT next_run FROM schedules')['next_run'] > time.time()+23*3600


def test_schema_six_schedule_migration_preserves_existing_drafts_and_suppression(db, prepared):
    from outreach.db import DB
    before = db.all('SELECT * FROM messages')
    db.execute('INSERT INTO suppression(email,reason,created_at) VALUES(?,?,?)', ('suppressed@fictional-demo.com', 'opt-out', time.time()))
    db.execute('ALTER TABLE schedules DROP COLUMN profile_first')
    db.execute('PRAGMA user_version=6')
    reopened = DB(db.path)
    assert reopened.one('PRAGMA user_version')['user_version'] == 8
    assert reopened.all('SELECT * FROM messages') == before
    assert reopened.one('SELECT reason FROM suppression')['reason'] == 'opt-out'
    assert not reopened.all('PRAGMA foreign_key_check')


async def test_personal_employee_cannot_auto_qualify_as_a_business(db, settings, monkeypatch, profile):
    lid, _ = profile
    url = 'https://www.linkedin.com/in/fictional-consultant'
    db.execute('UPDATE leads SET profile_url=? WHERE id=?', (url, lid))
    db.execute('UPDATE evidence SET url=? WHERE lead_id=?', (url, lid))
    crawl = db.one('SELECT * FROM crawls WHERE lead_id=?', (lid,))
    report = json.loads(crawl['report'])
    report['signal']['public_snapshot'].update(url=url, headline='Employee at Other Company')
    db.execute('UPDATE crawls SET report=? WHERE id=?', (json.dumps(report), crawl['id']))
    monkeypatch.setattr(email_writer, 'chat', lambda *a, **kw: pytest.fail('Employee profile triggered AI'))
    with pytest.raises(ValueError, match='self-employed'):
        preparation.prepare(db, settings, lid)

@pytest.mark.parametrize('disclosure,accepted', [
    ('I could not find a dedicated website in our search; please correct me if I missed it.', True),
    ('I did not spot a dedicated site linked from the profile; please correct me if I missed it.', True),
    ('No dedicated website was found in the profile and search check; please correct me if I missed it.', True),
    ('A dedicated website was not found in our search; please correct me if I missed it.', True),
    ('You have no website.', False), ('Your business has no site.', False),
    ('You do not have a website, although I could not find a website in search.', False)])
async def test_profile_writer_accepts_search_uncertainty_but_never_absolute_absence(db, settings, monkeypatch, profile, disclosure, accepted):
    lid, _ = profile
    value = assessment(db, lid)
    monkeypatch.setattr(email_writer, 'chat', lambda *a, **kw: json.dumps(value))
    preparation.prepare(db, settings, lid)
    lead = db.one('SELECT * FROM leads WHERE id=?', (lid,))
    contact = db.one('SELECT * FROM contacts WHERE lead_id=?', (lid,))
    pages = preparation._pages(db, lead)
    finding = json.loads(lead['findings'])[0]
    body = ('Bright Studio invites customers to arrange a consultation. '+disclosure+
            ' We could build a services page with a consultation form. An optional AI calling agent could collect requirements and hand them to your team. Would a concept be useful?')
    output = {'messages': [{'step': 0, 'subject': 'A services page for Bright Studio', 'body': body,
                            'support': [{'evidence_id': pages[0]['id'], 'quote': value['review']['quote']}]}]}
    if accepted:
        assert len(email_writer.validate_output(output, lead, contact, pages, finding=finding)) == 1
    else:
        with pytest.raises(ValueError, match='website.*absence'):
            email_writer.validate_output(output, lead, contact, pages, finding=finding)
