"""Measured audit inputs must reach the writer without inventing business pain."""
import json
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from outreach.app import create_app

from outreach import diagnostics, email_writer, preparation
from outreach.campaigns import create_drafts, archive_followups


REAL_GENERATE = email_writer.generate_sequence
REAL_CLIENT = httpx.Client


def performance(db, lid, **patch):
    report = {'lead_id': lid, 'url': 'https://bright-demo.com/', 'status': 'complete',
              'strategies': {'mobile': {'final_url': 'https://bright-demo.com/', 'score': 51,
                              'metrics': {'largest-contentful-paint': {'numericValue': 4800, 'numericUnit': 'millisecond'}}}},
              'errors': []}
    report.update(patch)
    db.event('performance', report)
    return report


@pytest.mark.parametrize('state', ['valid', 'failed', 'stale', 'wrong_target', 'old_cycle', 'bad_score', 'bad_final_url'])
def test_only_current_scoped_valid_measurements_become_observations(db, prepared, state):
    lid = prepared['lead_id']
    report = performance(db, lid)
    if state == 'failed':
        report.update(status='failed', strategies={}, errors=[{'reason': 'HTTP 429'}])
    elif state == 'wrong_target':
        report['url'] = 'https://another-demo.com/'
    elif state == 'bad_score':
        report['strategies']['mobile']['score'] = True
    elif state == 'bad_final_url':
        report['strategies']['mobile']['final_url'] = 'https://bright-demo.com/unrelated-page'
    db.execute("UPDATE events SET detail=? WHERE kind='performance'", (json.dumps(report),))
    if state == 'stale':
        db.execute("UPDATE events SET created_at=? WHERE kind='performance'", (time.time()-8*86400,))
    if state == 'old_cycle':
        db.execute('INSERT INTO crawls(lead_id,report,created_at) VALUES(?,?,?)', (lid, '{}', time.time()+1))
    value = diagnostics.snapshot(db, db.one('SELECT * FROM leads WHERE id=?', (lid,)))
    assert bool(value['observations']) is (state == 'valid')
    assert value['business_pain_confirmed'] is False
    if state == 'failed':
        assert value['reports'][0]['quota_limited'] is True
        assert value['reports'][0]['measurements'] == []
    if state == 'valid':
        assert value['observations'][0]['anchor'] == '51'
        assert value['reports'][0]['measurements'][0]['metrics']['largest-contentful-paint']['numericValue'] == 4800


@pytest.mark.parametrize('complete,url,overflow', [(True, True, True), (False, True, True), (True, False, True), (True, True, False)])
def test_partial_or_unscoped_render_never_proves_a_defect_or_missing_feature(db, prepared, complete, url, overflow):
    lid = prepared['lead_id']
    db.event('screenshot', {'lead_id': lid, **({'url': 'https://bright-demo.com/'} if url else {}),
        'complete': complete, 'issues': [] if complete else [{'reason': 'blocked_widget'}],
        'visual': {'viewport': {'width': 1440}, 'horizontalOverflow': overflow,
                   'forms': 0, 'fieldsWithoutExplicitLabels': 3, 'mobileCtas': []}})
    value = diagnostics.snapshot(db, db.one('SELECT * FROM leads WHERE id=?', (lid,)))
    assert bool(value['observations']) is (complete and url and overflow)
    assert 'missing' not in json.dumps(value['observations']).lower()


@pytest.mark.parametrize('kind', ['screenshot', 'performance'])
def test_preparation_and_direct_writer_wait_for_audit_jobs(db, settings, prepared, kind):
    cid, lid = prepared['contact_id'], prepared['lead_id']
    settings.draft_model, settings.draft_api_key = 'fictional-audit-model', 'fictional-fixture-key'
    db.execute('DELETE FROM messages')
    db.enqueue(kind, {'lead_id': lid})
    assert preparation.source_busy(db, lid)
    with pytest.raises(ValueError, match='wait|Wait'):
        preparation.queue(db, settings, lid)
    with pytest.raises(ValueError, match='wait|Wait'):
        create_drafts(db, settings, cid)


def test_real_assessment_receives_audits_as_separate_inputs(db, settings, prepared, monkeypatch):
    lid = prepared['lead_id']
    performance(db, lid)
    lead = db.one('SELECT * FROM leads WHERE id=?', (lid,))
    audit = diagnostics.snapshot(db, lead)
    packets = []
    def chat(*args, **kwargs):
        packets.append(json.loads(args[2]))
        return '{"ready":false,"reason":"No confirmed business impact"}'
    monkeypatch.setattr(email_writer, 'chat', chat)
    preparation._assessment(settings, lead, preparation._pages(db, lead), lambda: None, '', audit)
    assert packets[0]['audit_context'] == audit
    assert all('score' not in p['text'] for p in packets[0]['sources'])


@pytest.mark.parametrize('key,enabled', [(False, True), (True, False), (True, True)])
def test_automatic_pagespeed_is_bounded_to_configured_final_research_cycle(db, settings, prepared, key, enabled):
    from outreach.crawl_scheduler import schedule_final_audits
    lid = prepared['lead_id']
    settings.pagespeed_api_key = 'fictional-fixture-key' if key else ''
    settings.auto_performance_audit = enabled
    db.execute("UPDATE leads SET status='review' WHERE id=?", (lid,))
    db.execute('INSERT INTO crawls(lead_id,report,created_at) VALUES(?,?,?)', (lid, '{}', time.time()-10))
    schedule_final_audits(db, settings, {'lead_id': lid})
    schedule_final_audits(db, settings, {'lead_id': lid})
    assert len(db.all("SELECT id FROM jobs WHERE kind='performance'")) == int(key and enabled)


def test_latest_failed_audit_supersedes_old_success_without_borrowing_old_score(db, prepared):
    lid = prepared['lead_id']
    performance(db, lid)
    performance(db, lid, status='failed', strategies={}, errors=[{'reason': 'HTTP 429'}])
    value = diagnostics.snapshot(db, db.one('SELECT * FROM leads WHERE id=?', (lid,)))
    assert value['observations'] == [] and value['reports'][0]['measurements'] == []


@pytest.mark.parametrize('mode', ['valid', 'omit_ref', 'invent_ref', 'no_qualifier', 'wrong_unit', 'audit_changes'])
def test_real_writer_uses_scoped_observation_and_guards_draft_provenance(db, settings, prepared, monkeypatch, mode):
    settings.followups_enabled = False
    settings.draft_model, settings.draft_api_key = 'fictional-audit-model', 'fictional-fixture-key'
    cid, lid = prepared['contact_id'], prepared['lead_id']
    archive_followups(db, cid)
    original = db.all('SELECT * FROM messages')
    performance(db, lid)
    calls = []
    def respond(request):
        packet = json.loads(json.loads(request.content)['messages'][1]['content'])
        calls.append(packet)
        observation = packet['audit_context']['observations'][0]
        assert observation['fact'] == 'mobile Lighthouse lab performance score: 51/100.'
        refs = [] if mode == 'omit_ref' else ['performance:999:mobile'] if mode == 'invent_ref' else [observation['ref']]
        body = ('I saw Bright Demo scored 51/100 in our mobile Lighthouse lab test. '
                'Would reviewing the measured loading opportunities alongside your consultation journey be useful?')
        if mode == 'no_qualifier':
            body = 'Bright Demo has a score of 51/100. Would an outline be useful?'
        if mode == 'wrong_unit':
            body = 'Our mobile lab test says Bright Demo takes 51 seconds to load. Would reviewing this be useful?'
        if mode == 'audit_changes':
            performance(db, lid, status='failed', strategies={}, errors=[{'reason': 'HTTP 429'}])
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps({'messages': [
            {'step': 0, 'subject': 'Bright Demo mobile loading', 'body': body, 'diagnostic_refs': refs,
             'support': [{'evidence_id': prepared['evidence_id'], 'quote': 'Contact us for a consultation.'}]}]})}}]})
    monkeypatch.setattr(email_writer, 'generate_sequence', REAL_GENERATE)
    monkeypatch.setattr(email_writer.httpx, 'Client', lambda **kw: REAL_CLIENT(transport=httpx.MockTransport(respond), **kw))
    if mode != 'valid':
        with pytest.raises(ValueError):
            create_drafts(db, settings, cid)
        assert db.all('SELECT * FROM messages') == original
        assert len(calls) <= 2
    else:
        create_drafts(db, settings, cid)
        email_writer.assert_ai_origin(db, cid)
        origin = json.loads(db.one("SELECT detail FROM events WHERE kind='drafts_created' ORDER BY id DESC LIMIT 1")['detail'])
        assert origin['diagnostic_refs'] == [[origin['audit_context']['observations'][0]['ref']]]
        assert len(db.all('SELECT * FROM messages')) == 1
        performance(db, lid, status='failed', strategies={}, errors=[{'reason': 'HTTP 429'}])
        with pytest.raises(ValueError, match='Audit evidence changed'):
            email_writer.assert_ai_origin(db, cid)
        client = TestClient(create_app(settings), headers={'Authorization': 'Bearer '+settings.api_token})
        contact = client.get(f'/api/leads/{lid}').json()['contacts'][0]
        assert contact['ai_drafts'] is False
        assert 'Audit evidence changed' in contact['ai_draft_issue']
        assert 'template' not in contact['ai_draft_issue']



def test_archive_retains_only_initial_audit_references_in_active_provenance(db, prepared):
    row = db.one("SELECT id,detail FROM events WHERE kind='drafts_created' ORDER BY id DESC LIMIT 1")
    origin = json.loads(row['detail'])
    origin['diagnostic_refs'] = [['initial'], ['second'], ['third'], ['fourth']]
    db.execute('UPDATE events SET detail=? WHERE id=?', (json.dumps(origin), row['id']))
    archive_followups(db, prepared['contact_id'])
    saved = json.loads(db.one("SELECT detail FROM events WHERE kind='drafts_created' ORDER BY id DESC LIMIT 1")['detail'])
    assert saved['diagnostic_refs'] == [['initial']]


def test_writer_does_not_launder_unverified_review_summaries_into_source_context(db, prepared):
    lead = db.one('SELECT * FROM leads WHERE id=?', (prepared['lead_id'],))
    finding = json.loads(lead['findings'])[0]
    lead.update(fit_notes='UNVERIFIED_TRIAL: the London page offers a three-month trial.',
                research_notes='UNVERIFIED_LOSS: quote abandonments increased by 40%.')
    finding['observation'] = 'UNVERIFIED_OBSERVATION: the chatbot breaks on mobile.'
    finding['trigger'] = {'evidence_id': prepared['evidence_id'], 'quote': finding['quote'], 'description':'UNVERIFIED_TRIGGER: a new product launched yesterday.'}
    pages = db.all('SELECT * FROM evidence')
    packet = email_writer.research_packet(lead, finding, pages)
    text = json.dumps(packet)
    assert 'UNVERIFIED_' not in text
    assert packet['reviewed_finding']['quote'] == finding['quote']
    assert packet['reviewed_finding']['suggestion_status'].startswith('Proposed')


def test_internal_research_labels_cannot_reach_the_email(db, prepared):
    lead = db.one('SELECT * FROM leads WHERE id=?', (prepared['lead_id'],))
    contact = db.one('SELECT * FROM contacts WHERE id=?', (prepared['contact_id'],))
    pages = db.all('SELECT * FROM evidence')
    value = {'messages':[{'step':0,'subject':'An idea for Bright Demo',
        'body':'The reviewed finding suggests testing the Bright Demo enquiry flow. Would this be useful?',
        'support':[{'evidence_id':prepared['evidence_id'],'quote':'Contact us for a consultation.'}]}]}
    with pytest.raises(ValueError, match='internal research labels'):
        email_writer.validate_output(value,lead,contact,pages)


def test_bounded_writer_correction_explicitly_supplies_allowed_empty_audit_refs(db, settings, prepared, monkeypatch):
    settings.followups_enabled = False
    settings.draft_model, settings.draft_api_key = 'fictional-audit-model', 'fictional-fixture-key'
    cid, lid = prepared['contact_id'], prepared['lead_id']
    archive_followups(db, cid)
    performance(db, lid, status='failed', strategies={}, errors=[{'reason':'HTTP 429'}])
    calls = []
    def respond(request):
        packet = json.loads(json.loads(request.content)['messages'][1]['content'])
        calls.append(packet)
        refs = ['performance:999:mobile'] if len(calls)==1 else []
        if len(calls)==2:
            assert packet['validation_feedback']['allowed_diagnostic_refs'] == []
            assert 'diagnostic_refs: []' in packet['validation_feedback']['diagnostic_reference_rule']
        return httpx.Response(200,json={'choices':[{'finish_reason':'stop','message':{'content':json.dumps({'messages':[
            {'step':0,'subject':'Bright Demo consultation journey','body':'I noticed Bright Demo invites visitors to contact you for a consultation. Would exploring a clearer outline of that first conversation be useful?',
             'diagnostic_refs':refs,'support':[{'evidence_id':prepared['evidence_id'],'quote':'Contact us for a consultation.'}]}]})}}]})
    monkeypatch.setattr(email_writer,'generate_sequence',REAL_GENERATE)
    monkeypatch.setattr(email_writer.httpx,'Client',lambda **kw:REAL_CLIENT(transport=httpx.MockTransport(respond),**kw))
    create_drafts(db,settings,cid)
    assert len(calls)==2 and len(db.all('SELECT * FROM messages'))==1
    assert db.one('SELECT state,due_at,sent_at FROM messages')=={'state':'draft','due_at':None,'sent_at':None}
