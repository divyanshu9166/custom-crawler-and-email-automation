"""Controlled automatic qualification/drafting; never provider or delivery acceptance."""
import copy
import hashlib
import json
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from outreach import preparation, email_writer
from outreach.app import create_app
from outreach.research import add_lead, add_contact
from outreach.preferences import Preferences

REAL_CLIENT = httpx.Client
REAL_GENERATE = email_writer.generate_sequence


@pytest.fixture
def prospect(db, settings):
    settings.sending_enabled = False
    settings.draft_model = 'fictional-research-model'
    settings.draft_api_key = 'fictional-test-key'
    lid = add_lead(db, 'Bright Demo Ltd', 'https://bright-demo.com', 'A', 'https://bright-demo.com/')
    text = ('Bright Demo Ltd provides commercial cleaning across the UK. '
            'Request a quote for office cleaning. Our team discusses your cleaning schedule. '
            'Contact hello@bright-demo.com for business enquiries.')
    eid = db.execute('INSERT INTO evidence(lead_id,url,title,text,sha256,fetched_at) VALUES(?,?,?,?,?,?)',
                     (lid, 'https://bright-demo.com/', 'Bright Demo Ltd', text, hashlib.sha256(text.encode()).hexdigest(), time.time()))
    db.execute("UPDATE leads SET status='review' WHERE id=?", (lid,))
    cid = add_contact(db, lid, 'hello@bright-demo.com', 'https://bright-demo.com/')
    db.event('discovery', {'query': 'commercial cleaning UK', 'lead_ids': [lid]})
    # Qualification/writer protocol cases start with an actual controlled lab finding.
    db.event('performance', {'lead_id': lid, 'url': 'https://bright-demo.com/', 'status': 'complete',
        'strategies': {'mobile': {'final_url': 'https://bright-demo.com/', 'score': 51,
            'metrics': {'largest-contentful-paint': {'numericValue':4800,'numericUnit':'millisecond'}}}}, 'errors': []})
    return lid, cid, eid


def assessment(eid):
    return {'ready': True, 'review': {
        'company': 'Bright Demo Ltd', 'country': 'UK', 'country_source': 'https://bright-demo.com/',
        'country_quote': 'provides commercial cleaning across the UK.', 'timezone': 'Europe/London',
        'business_type': 'corporate', 'service': 'website_improvement', 'primary_goal': 'inquiries_bookings',
        'fit_notes': 'Commercial cleaning provider with a quote request; assess whether describing schedule options helps enquiries.',
        'evidence_id': eid, 'quote': 'Request a quote for office cleaning.',
        'observation': 'Your homepage invites visitors to request an office cleaning quote.',
        'suggestion': 'Explore a brief outline of cleaning schedule options next to the quote invitation; test usefulness with your team.'}}


@pytest.mark.parametrize('source', ['https://bright-demo.com', 'https://BRIGHT-DEMO.com/#contact', 'https://bright-demo.com/?utm_source=research'])
def test_country_source_uses_same_canonical_url_as_manual_review(db, prospect, source):
    lid, _, eid = prospect
    lead = db.one('SELECT * FROM leads WHERE id=?', (lid,))
    value = assessment(eid)
    value['review']['country_source'] = source
    value['review']['country_quote'] = '  provides commercial cleaning across the UK.  '
    result = preparation._validate_review(lead, value, preparation._pages(db, lead))
    assert result['country_source'] == 'https://bright-demo.com/'
    assert result['country_quote'] == 'provides commercial cleaning across the UK.'


@pytest.mark.parametrize('format', ['plain', 'fenced', 'prose', 'broken'])
def test_assessment_accepts_only_complete_json_with_optional_code_fence(db, settings, prospect, monkeypatch, format):
    lid, _, eid = prospect
    lead = db.one('SELECT * FROM leads WHERE id=?', (lid,))
    value = json.dumps(assessment(eid))
    output = {'plain': value, 'fenced': '```json\n'+value+'\n```',
              'prose': 'Here is a result: '+value, 'broken': value[:-2]}[format]
    calls = []
    def chat(*args, **kwargs):
        calls.append(True)
        return output
    monkeypatch.setattr(email_writer, 'chat', chat)
    if format in {'prose', 'broken'}:
        with pytest.raises(ValueError, match='invalid JSON'):
            preparation._assessment(settings, lead, preparation._pages(db, lead), lambda: None)
        assert len(calls) == 2
    else:
        assert preparation._assessment(settings, lead, preparation._pages(db, lead), lambda: None)['ready']
        assert len(calls) == 1
    assert not db.one('SELECT id FROM messages')


@pytest.mark.parametrize('change', ['current', 'country_quote_removed', 'expired', 'unreviewed', 'unsafe_claim', 'changed_during_revalidation'])
def test_qualified_prospect_reuses_only_current_validated_review(db, settings, prospect, monkeypatch, change):
    from outreach.campaigns import review_lead
    lid, _, eid = prospect
    review_lead(db, lid, assessment(eid)['review'])
    before = db.one('SELECT findings FROM leads WHERE id=?', (lid,))['findings']
    if change == 'country_quote_removed':
        db.execute("UPDATE evidence SET text=replace(text,'across the UK','for businesses') WHERE id=?", (eid,))
    elif change == 'expired':
        db.execute('UPDATE evidence SET fetched_at=? WHERE id=?', (time.time()-31*86400, eid))
    elif change in {'unreviewed', 'unsafe_claim'}:
        finding = json.loads(before)
        if change == 'unreviewed':
            finding[0]['review_required'] = True
        else:
            finding[0]['observation'] = 'Your website has no form and is losing customers.'
        db.execute('UPDATE leads SET findings=? WHERE id=?', (json.dumps(finding), lid))
    calls = []
    def assess(*_args):
        calls.append(True)
        return {'ready': False, 'reason': 'Insufficient current evidence'}
    monkeypatch.setattr(preparation, '_assessment', assess)
    if change == 'changed_during_revalidation':
        original = preparation._saved_review
        def raced(db, lead, pages):
            result = original(db, lead, pages)
            db.execute('UPDATE leads SET fit_notes=? WHERE id=?', ('Newer operator review must be preserved.', lid))
            return result
        monkeypatch.setattr(preparation, '_saved_review', raced)
    if change in {'expired', 'changed_during_revalidation'}:
        with pytest.raises(ValueError):
            preparation.prepare(db, settings, lid)
    else:
        preparation.prepare(db, settings, lid)
    if change == 'current':
        assert not calls
        assert db.one('SELECT findings FROM leads WHERE id=?', (lid,))['findings'] == before
        assert preparation.latest(db, lid)['result']['qualification_basis'] == 'saved_review_revalidated'
        assert all(m['state'] == 'draft' and not m['due_at'] and not m['sent_at'] for m in db.all('SELECT * FROM messages'))
        assert db.one('SELECT COUNT(*) n FROM messages')['n'] == 4
    else:
        assert not db.one('SELECT id FROM messages')
        assert bool(calls) is (change in {'country_quote_removed', 'unreviewed', 'unsafe_claim'})
    assert settings.sending_enabled is False


def mock_assessment(monkeypatch, value):
    monkeypatch.setattr(preparation, '_assessment', lambda *a: copy.deepcopy(value))


@pytest.mark.parametrize('identity_source', ['current', 'stale', 'unrelated', 'outside_context'])
def test_page_budget_retains_only_current_visible_official_identity_source(db, settings, prospect, monkeypatch, identity_source):
    lid, _, eid = prospect
    db.execute("UPDATE evidence SET text=replace(text,'Bright Demo Ltd','Bright Demo') WHERE id=?", (eid,))
    for i in range(14):
        text = 'Commercial cleaning services across the UK.'
        db.execute('INSERT INTO evidence(lead_id,url,title,text,sha256,fetched_at) VALUES(?,?,?,?,?,?)',
                   (lid, f'https://bright-demo.com/services/cleaning-{i:02}/', 'Cleaning services', text,
                    hashlib.sha256(text.encode()).hexdigest(), time.time()))
    text = ('x' * 8100 if identity_source == 'outside_context' else '') + 'Bright Demo Ltd serves businesses across the UK.'
    url = 'https://unrelated.example/identity/' if identity_source == 'unrelated' else 'https://bright-demo.com/locations/london/'
    identity_id = db.execute('INSERT INTO evidence(lead_id,url,title,text,sha256,fetched_at) VALUES(?,?,?,?,?,?)',
                            (lid, url, 'Business address', text, hashlib.sha256(text.encode()).hexdigest(),
                             time.time() - (31 * 86400 if identity_source == 'stale' else 0)))
    lead = db.one('SELECT * FROM leads WHERE id=?', (lid,))
    selected = preparation._pages(db, lead)
    assert len(selected) == 12 and selected[0]['id'] == eid
    assert (identity_id in {p['id'] for p in selected}) is (identity_source == 'current')
    if identity_source == 'current':
        packets = []
        def assess(settings, instructions, packet, **kwargs):
            packets.append(json.loads(packet))
            return json.dumps(assessment(eid))
        monkeypatch.setattr(email_writer, 'chat', assess)
        result = preparation._assessment(settings, lead, selected, lambda: None)
        assert any('Bright Demo Ltd' in p['text'] for p in packets[0]['sources'])
        preparation._validate_review(lead, result, selected)
        preparation.prepare(db, settings, lid)
        assert preparation.latest(db, lid)['result']['state'] == 'drafts_ready'
        assert all(m['state'] == 'draft' and m['due_at'] is None and not m['sent_at'] for m in db.all('SELECT * FROM messages'))


@pytest.mark.parametrize('outcome', ['corrected', 'still_invalid', 'hold', 'network_error', 'changed_source'])
def test_assessment_correction_is_bounded_and_validated_before_writes(db, settings, prospect, monkeypatch, outcome):
    lid, _, eid = prospect
    lead = db.one('SELECT * FROM leads WHERE id=?', (lid,))
    packets = []
    invalid = assessment(eid)
    invalid['review']['country_quote'] = 'We are ... a UK business'
    invalid['review']['observation'] = 'Your website has no chatbot.'
    def chat(settings, instructions, packet, **kwargs):
        kwargs['before_request']()
        packets.append(json.loads(packet))
        if outcome == 'network_error':
            raise ValueError('AI provider response timed out; key validity is not established.')
        value = (invalid if len(packets) == 1 or outcome == 'still_invalid' else
                 {'ready': False, 'reason': 'Insufficient support'} if outcome == 'hold' else assessment(eid))
        return json.dumps(value)
    monkeypatch.setattr(email_writer, 'chat', chat)
    def current():
        if outcome == 'changed_source' and packets:
            raise ValueError('Research changed during preparation')
    pages = preparation._pages(db, lead)
    if outcome in {'still_invalid', 'network_error', 'changed_source'}:
        with pytest.raises(ValueError):
            preparation._assessment(settings, lead, pages, current)
    else:
        value = preparation._assessment(settings, lead, pages, current)
        assert value['ready'] is (outcome == 'corrected')
    assert len(packets) == (1 if outcome in {'network_error', 'changed_source'} else 2)
    if len(packets) == 2:
        assert 'Country needs' in packets[1]['validation_feedback']['error']
        assert 'observation' not in packets[1]['validation_feedback']
    assert db.one('SELECT status FROM leads WHERE id=?', (lid,))['status'] == 'review'
    assert not db.one('SELECT id FROM messages')


def test_prepare_runs_real_writer_contract_and_leaves_all_messages_unsent(db, settings, prospect, monkeypatch):
    lid, cid, eid = prospect
    requests = []
    def handle(request):
        payload = json.loads(request.content)
        requests.append(payload)
        assert 'hello@bright-demo.com' not in request.content.decode()
        if len(requests) == 1:
            packet = json.loads(payload['messages'][1]['content'])
            assert packet['target_query'] == 'commercial cleaning UK'
            value = assessment(eid)
        else:
            observation = json.loads(payload['messages'][1]['content'])['audit_context']['observations'][0]
            value = {'messages': [{'step': i, 'subject': f'Bright Demo Ltd quote idea {i}',
                      'body': f'Bright Demo Ltd scored 51/100 in our mobile Lighthouse lab test. One idea {i}: profile the measured loading bottleneck before optimising it. Would reviewing this finding be useful?',
                      'diagnostic_refs': [observation['ref']] if i == 0 else [],
                      'support': [{'evidence_id': eid, 'quote': 'Request a quote for office cleaning.'}]} for i in range(4)]}
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(value)}}]})
    monkeypatch.setattr(email_writer, 'generate_sequence', REAL_GENERATE)
    monkeypatch.setattr(email_writer.httpx, 'Client', lambda **kw: REAL_CLIENT(transport=httpx.MockTransport(handle), **kw))
    preparation.prepare(db, settings, lid)
    assert len(requests) == 2
    lead = db.one('SELECT * FROM leads WHERE id=?', (lid,))
    finding = json.loads(lead['findings'])[0]
    assert lead['status'] == 'qualified' and finding['qualification_method'] == 'research_ai'
    assert finding['final_message_review_required'] is True
    assert len(db.all('SELECT * FROM messages')) == 4
    assert all(m['state'] == 'draft' and m['due_at'] is None and not m['sent_at'] for m in db.all('SELECT * FROM messages'))
    assert db.one('SELECT status FROM contacts WHERE id=?', (cid,))['status'] == 'new'
    assert preparation.latest(db, lid)['result']['state'] == 'drafts_ready'
    assert not db.one("SELECT id FROM events WHERE kind='sequence_approved'")
    assert settings.sending_enabled is False


@pytest.mark.parametrize('problem', ['invented_quote', 'country_hint', 'country_other_source', 'company', 'corporate', 'goal', 'absence', 'chatbot', 'helpdesk', 'whatsapp_permission', 'campaign_b', 'us_timezone'])
def test_unsupported_assessments_stay_held_without_drafts(db, settings, prospect, monkeypatch, problem):
    lid, _, eid = prospect
    value = assessment(eid)
    r = value['review']
    if problem == 'invented_quote':
        r['quote'] = 'Missing quote form loses enquiries.'
    elif problem == 'country_hint':
        r['country_quote'] = 'Request a quote for office cleaning.'
    elif problem == 'country_other_source':
        r['country_source'] = 'https://unrelated.example/'
    elif problem == 'company':
        r['company'] = 'A different business'
    elif problem == 'corporate':
        db.execute("UPDATE evidence SET text=replace(text,'Ltd','Studio') WHERE id=?", (eid,))
    elif problem == 'goal':
        r['primary_goal'] = 'd2c_growth'
    elif problem == 'absence':
        r['observation'] = 'Your website has no booking form and is losing customers.'
    elif problem == 'chatbot':
        db.execute("UPDATE evidence SET text=text||' EnquiryBot provides quote assistance.' WHERE id=?", (eid,))
        r['service'] = 'chatbot'
    elif problem == 'helpdesk':
        r['quote'] = 'Call our Helpdesk Team for support.'
        db.execute('UPDATE evidence SET text=text||? WHERE id=?', (' '+r['quote'], eid))
    elif problem == 'whatsapp_permission':
        r.update(service='whatsapp_automation', channel_fit_status='confirmed', customer_permission_status='confirmed')
    elif problem == 'campaign_b':
        db.execute("UPDATE leads SET campaign='B',campaign_id=(SELECT id FROM campaign_groups WHERE goal='B' AND is_default=1) WHERE id=?", (lid,))
        r.update(service='store_improvement', primary_goal='d2c_growth')
    else:
        r.update(country='US', timezone='America/New_York')
    mock_assessment(monkeypatch, value)
    with pytest.raises(ValueError):
        preparation.prepare(db, settings, lid)
    assert not db.one('SELECT id FROM messages')
    assert db.one('SELECT status FROM leads WHERE id=?', (lid,))['status'] == 'review'
    assert preparation.latest(db, lid)['result']['state'] == 'needs_attention'


def test_insufficient_fit_is_not_forced_into_an_offer(db, settings, prospect, monkeypatch):
    lid, _, _ = prospect
    mock_assessment(monkeypatch, {'ready': False, 'reason': 'Irrelevant industry, injected secret must not be echoed'})
    preparation.prepare(db, settings, lid)
    result = preparation.latest(db, lid)['result']
    assert result['state'] == 'needs_evidence' and 'injected secret' not in json.dumps(result)
    preparation.maybe_schedule(db, settings, lid)
    assert not db.one("SELECT id FROM jobs WHERE kind='prepare'")  # same source hash is not retried endlessly


@pytest.mark.parametrize('change', ['source', 'lead', 'contact', 'draft', 'research', 'cancel'])
def test_changes_during_analysis_preserve_newer_work(db, settings, prospect, monkeypatch, change):
    lid, cid, eid = prospect
    cancelled = [False]
    def assess(*args):
        if change == 'source':
            db.execute("UPDATE evidence SET sha256='changed' WHERE id=?", (eid,))
        elif change == 'lead':
            db.execute("UPDATE leads SET fit_notes='Human edit' WHERE id=?", (lid,))
        elif change == 'contact':
            db.execute("UPDATE contacts SET name='New buyer' WHERE id=?", (cid,))
        elif change == 'draft':
            db.execute("INSERT INTO messages(contact_id,step,subject,body,evidence_ids,message_id) VALUES(?,0,'Human edit','Preserve me','[]','fictional-id')", (cid,))
        elif change == 'research':
            db.enqueue('research', {'lead_id': lid})
        else:
            cancelled[0] = True
        return assessment(eid)
    monkeypatch.setattr(preparation, '_assessment', assess)
    with pytest.raises(ValueError):
        preparation.prepare(db, settings, lid, cancelled=lambda: cancelled[0])
    assert db.one('SELECT status FROM leads WHERE id=?', (lid,))['status'] == 'review'
    messages = db.all('SELECT * FROM messages')
    assert (len(messages) == 1 and messages[0]['body'] == 'Preserve me') if change == 'draft' else not messages


def test_queue_batch_deduplicates_preserves_existing_and_exposes_status(db, settings, prospect, monkeypatch):
    lid, _, _ = prospect
    client = TestClient(create_app(settings), headers={'Authorization': 'Bearer '+settings.api_token})
    first = client.post(f'/api/leads/{lid}/prepare')
    assert first.status_code == 200
    assert client.post(f'/api/leads/{lid}/prepare').json() == first.json()
    assert len(client.post('/api/preparation/batch').json()['queued']) == 1
    assert client.get(f'/api/leads/{lid}/preparation').json()['job']['state'] == 'pending'
    assert client.get(f'/api/leads/{lid}').json()['preparation']['job']['state'] == 'pending'
    assert len(db.all("SELECT id FROM jobs WHERE kind='prepare'")) == 1
    assert not settings.sending_enabled
    mock_assessment(monkeypatch, assessment(prospect[2]))
    preparation.prepare(db, settings, lid)
    assert client.post(f'/api/leads/{lid}/prepare').status_code == 400
    result = client.post('/api/preparation/batch').json()
    assert not result['queued'] and len(result['skipped']) == 1


def test_same_lead_preparation_serializes_with_crawls(db, settings, prospect):
    lid, _, _ = prospect
    job = preparation.queue(db, settings, lid)
    assert db.claim({'prepare'})['id'] == job
    db.enqueue('research', {'lead_id': lid})
    assert db.claim({'research'}) is None
    db.execute("UPDATE jobs SET state='done' WHERE id=?", (job,))
    assert db.claim({'research'}) is not None


def test_auto_scheduler_waits_for_research_and_settings_persist(db, settings, prospect):
    lid, _, _ = prospect
    prefs = Preferences(settings)
    prefs.update_research(db, {'auto_prepare_enabled': False})
    preparation.maybe_schedule(db, settings, lid)
    assert not db.one("SELECT id FROM jobs WHERE kind='prepare'")
    prefs.update_research(db, {'auto_prepare_enabled': True})
    work = db.enqueue('social_research', {'lead_id': lid})
    preparation.maybe_schedule(db, settings, lid)
    assert not db.one("SELECT id FROM jobs WHERE kind='prepare'")
    db.execute("UPDATE jobs SET state='done' WHERE id=?", (work,))
    preparation.maybe_schedule(db, settings, lid)
    assert db.one("SELECT id FROM jobs WHERE kind='prepare'")
    assert prefs.public()['auto_prepare_enabled'] is True


@pytest.mark.parametrize('base', ['https://integrate.api.nvidia.com', 'https://integrate.api.nvidia.com/v1/',
                                 'https://integrate.api.nvidia.com/v1/chat/completions'])
def test_nvidia_url_forms_are_normalized_without_duplicate_suffix(base):
    assert email_writer.completion_url(base) == 'https://integrate.api.nvidia.com/v1/chat/completions'


@pytest.mark.parametrize('status', [200, 401, 404, 429])
def test_synthetic_writer_check_has_no_prospect_data_and_redacts_provider_errors(db, settings, prospect, monkeypatch, status):
    def handle(request):
        assert 'Bright Demo' not in request.content.decode() and 'bright-demo.com' not in request.content.decode()
        assert json.loads(request.content)['max_tokens'] == 128
        return httpx.Response(status, json={'choices': [{'finish_reason': 'stop', 'message': {'content': 'OK'}}], 'error': settings.draft_api_key})
    monkeypatch.setattr(email_writer.httpx, 'Client', lambda **kw: REAL_CLIENT(transport=httpx.MockTransport(handle), **kw))
    client = TestClient(create_app(settings), headers={'Authorization': 'Bearer '+settings.api_token})
    result = client.post('/api/providers/writer/test')
    assert result.status_code == (200 if status == 200 else 400)
    assert settings.draft_api_key not in result.text
    if status == 404:
        assert 'exact model ID/account access' in result.text
    assert not db.one('SELECT id FROM messages')


async def test_worker_executes_preparation_and_keeps_monitoring_lane_separate(db, settings, prospect, monkeypatch):
    from outreach.worker import execute_job
    lid, _, eid = prospect
    mock_assessment(monkeypatch, assessment(eid))
    preparation.queue(db, settings, lid)
    job = db.claim({'prepare'})
    await execute_job(db, settings, job)
    assert db.one('SELECT state FROM jobs WHERE id=?', (job['id'],))['state'] == 'done'
    assert preparation.latest(db, lid)['result']['state'] == 'drafts_ready'
    assert not settings.sending_enabled


async def test_finished_research_automatically_queues_one_preparation(db, settings, prospect, monkeypatch):
    from outreach import worker
    lid, _, _ = prospect
    async def researched(*args, **kwargs):
        return  # fixture already contains the current captured source and published inbox
    monkeypatch.setattr(worker, 'research_lead', researched)
    db.enqueue('research', {'lead_id': lid})
    await worker.execute_job(db, settings, db.claim({'research'}))
    assert len(db.all("SELECT id FROM jobs WHERE kind='prepare' AND state='pending'")) == 1
    preparation.maybe_schedule(db, settings, lid)
    assert len(db.all("SELECT id FROM jobs WHERE kind='prepare'")) == 1
    assert not settings.sending_enabled


def test_automatic_writing_preserves_existing_human_drafts(db, settings, prepared, monkeypatch):
    from outreach.campaigns import create_drafts
    before = db.all('SELECT * FROM messages')
    monkeypatch.setattr(email_writer, 'generate_sequence', lambda *a, **k: pytest.fail('Existing copy must be preserved before provider call'))
    with pytest.raises(ValueError, match='existing copy preserved'):
        create_drafts(db, settings, prepared['contact_id'], preserve_existing=True)
    assert db.all('SELECT * FROM messages') == before


def test_no_contact_and_profile_only_are_exceptions_not_guessed(db, settings, prospect, monkeypatch):
    lid, cid, _ = prospect
    monkeypatch.setattr(preparation, '_assessment', lambda *a: pytest.fail('No usable contact: no model request'))
    db.execute("UPDATE contacts SET role='Recruitment' WHERE id=?", (cid,))
    with pytest.raises(ValueError, match='No current published business contact'):
        preparation.prepare(db, settings, lid)
    db.execute("UPDATE leads SET lead_kind='profile' WHERE id=?", (lid,))
    with pytest.raises(ValueError, match='Profile-only'):
        preparation.prepare(db, settings, lid)
    assert not db.one('SELECT id FROM messages')


def test_batch_cursor_reaches_prospects_beyond_the_first_hundred(db, settings, prospect):
    lid, _, _ = prospect
    for i in range(100):
        other = add_lead(db, f'Fictional business {i}', f'https://demo-{i}.example', 'A', f'https://demo-{i}.example')
        db.execute("UPDATE leads SET status='review' WHERE id=?", (other,))
    client = TestClient(create_app(settings), headers={'Authorization': 'Bearer '+settings.api_token})
    first = client.post('/api/preparation/batch').json()
    assert first['next_after_id'] > lid
    second = client.post('/api/preparation/batch?after_id='+str(first['next_after_id'])).json()
    assert second['next_after_id'] == 0 and len(second['skipped']) == 1
    assert second['skipped'][0]['lead_id'] > first['next_after_id']


@pytest.mark.parametrize('country_label', ['United States', 'U.S.'])
def test_us_country_and_named_location_select_timezone_without_defaulting(db, settings, prospect, monkeypatch, country_label):
    lid, _, eid = prospect
    quote = 'commercial cleaning in New York, '+country_label
    page = db.one('SELECT text FROM evidence WHERE id=?', (eid,))['text']
    text = page.replace('commercial cleaning across the UK', quote)
    db.execute('UPDATE evidence SET text=?,sha256=? WHERE id=?', (text, hashlib.sha256(text.encode()).hexdigest(), eid))
    value = assessment(eid)
    value['review'].update(country='US', country_quote=quote, timezone='America/New_York')
    mock_assessment(monkeypatch, value)
    preparation.prepare(db, settings, lid)
    lead = db.one('SELECT * FROM leads WHERE id=?', (lid,))
    assert lead['country'] == 'US' and lead['timezone'] == 'America/New_York'
    assert preparation.latest(db, lid)['result']['state'] == 'drafts_ready'

def test_country_candidates_are_verbatim_and_exclude_domain_and_email_hints():
    text = 'Business enquiries hello@fixture.co.uk. Visit https://fixture.co.uk/. We provide commercial cleaning across the UK. Our team operates nationwide with local service teams.'
    pages=[{'id':1,'url':'https://fixture.co.uk/','text':text},
           {'id':2,'url':'https://fixture.co.uk/about','text':'Commercial cleaning specialists in Bristol and UK Operating since 2006.'}]
    rows=preparation.country_candidates(pages)
    assert rows
    for row in rows:
        page=next(p for p in pages if p['id']==row['evidence_id'])
        assert row['quote'] in page['text'] and row['source_url']==page['url']
        assert '@' not in row['quote'] and 'https://' not in row['quote']
    assert not preparation.country_candidates([{'id':3,'url':'https://fixture.co.uk/','text':'Email hello@fixture.co.uk or visit https://fixture.co.uk/'}])


def test_assessment_supplies_exact_country_candidates_without_inventing_corporate_identity(db,settings,prospect,monkeypatch):
    lid,_,_=prospect
    lead=db.one('SELECT * FROM leads WHERE id=?',(lid,))
    lead['company']='Office Cleaning – Expert Cleaners'
    pages=preparation._pages(db,lead)
    def chat(settings,instructions,packet,**kwargs):
        value=json.loads(packet)
        assert value['country_evidence_candidates']
        assert value['corporate_name_supported'] is False
        assert 'registered-office' in instructions
        for row in value['country_evidence_candidates']:
            assert row['quote'] in next(p for p in pages if p['id']==row['evidence_id'])['text']
        return json.dumps({'ready':False,'reason':'controlled hold'})
    monkeypatch.setattr(email_writer,'chat',chat)
    assert not preparation._assessment(settings,lead,pages,lambda:None)['ready']

def test_assessment_resolves_explicit_source_references_before_normal_validation(db,settings,prospect,monkeypatch):
    lid,_,eid=prospect
    lead=db.one('SELECT * FROM leads WHERE id=?',(lid,))
    def chat(settings,instructions,packet,**kwargs):
        data=json.loads(packet)
        result=assessment(eid)
        for key in ('country_source','country_quote','evidence_id','quote'):
            del result['review'][key]
        result['source_selection']={'country':data['country_evidence_candidates'][0]['ref'],
                                    'opportunity':data['opportunity_evidence_candidates'][0]['ref']}
        return json.dumps(result)
    monkeypatch.setattr(email_writer,'chat',chat)
    result=preparation._assessment(settings,lead,preparation._pages(db,lead),lambda:None)
    assert result['ready'] and result['review']['evidence_id']==eid
    page=db.one('SELECT text FROM evidence WHERE id=?',(eid,))
    assert result['review']['quote'] in page['text'] and result['review']['country_quote'] in page['text']
    assert not db.one('SELECT id FROM messages')


@pytest.mark.parametrize('selection,review',[
    ({'country':'c0','opportunity':'performance:3757:mobile'},{}),
    ({'country':[], 'opportunity':'q0'},{}),
    ({'country':'c0','opportunity':'q0'},{'quote':'Invented business statement'}),
])
def test_source_reference_binding_rejects_unknown_audit_refs_or_conflicting_quotes(selection,review):
    c=[{'ref':'c0','source_url':'https://bright-demo.com/','quote':'Cleaning across the UK.','evidence_id':1}]
    o=[{**c[0],'ref':'q0'}]
    with pytest.raises(ValueError):
        preparation.bind_source_selection({'review':review,'source_selection':selection},c,o)
