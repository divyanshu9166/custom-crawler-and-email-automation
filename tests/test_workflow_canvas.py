import json
import time

from fastapi.testclient import TestClient
from outreach.app import create_app
from outreach.workflow import snapshot


def by_id(result):
    return {n['id']: n for n in result['nodes']}


def test_empty_workflow_does_not_fake_completed_steps(db, settings):
    result = snapshot(db, settings)
    nodes = by_id(result)
    assert result['next_node'] == 'discovery'
    assert nodes['discovery']['state'] == 'ready'
    assert nodes['verify']['metric'] == '0/0 fresh safe'
    assert nodes['send']['state'] == 'paused'
    assert all(a in nodes and b in nodes for a,b in result['edges'])


def test_review_running_failures_and_actual_approval_visible(db, settings, prepared):
    lid = prepared['lead_id']
    result = snapshot(db, settings, lid)
    assert by_id(result)['verify']['state'] == 'complete'
    assert by_id(result)['drafts']['state'] == 'review'
    assert by_id(result)['approval']['state'] == 'review'
    db.execute("UPDATE leads SET status='researching' WHERE id=?", (lid,))
    assert snapshot(db,settings,lid)['next_node'] == 'website'
    db.execute("UPDATE leads SET status='review' WHERE id=?", (lid,))
    db.execute("UPDATE contacts SET verification='unknown' WHERE id=?", (prepared['contact_id'],))
    jid = db.enqueue('verify', {'contact_id': prepared['contact_id']})
    db.execute("UPDATE jobs SET state='failed' WHERE id=?", (jid,))
    result = snapshot(db, settings, lid)
    assert by_id(result)['verify']['state'] == 'failed'
    assert result['next_node'] == 'qualify'
    assert by_id(result)['approval']['state'] == 'blocked'
    assert by_id(result)['send']['metric'] == '0 accepted by SMTP'
    research = db.enqueue('research', {'lead_id': lid})
    assert by_id(snapshot(db, settings, lid))['website']['state'] == 'queued'
    db.execute("UPDATE jobs SET state='done' WHERE id=?", (research,))
    # Retrying is queued, and success supersedes the older terminal failure.
    retry = db.enqueue('verify', {'contact_id': prepared['contact_id']})
    assert by_id(snapshot(db,settings,lid))['verify']['state'] == 'queued'
    db.execute("UPDATE jobs SET state='done' WHERE id=?", (retry,))
    db.execute("UPDATE contacts SET verification='safe',verified_at=?", (time.time(),))
    assert by_id(snapshot(db,settings,lid))['verify']['state'] == 'complete'


def test_profile_website_routing_and_unknown_verdict_not_complete(db,settings):
    from outreach.profiles import add_profile_lead
    lid = add_profile_lead(db,'Fictional profile','https://x.com/fictional_business','A','UK')
    db.execute("UPDATE leads SET status='profile_unavailable',website_status='website_found' WHERE id=?", (lid,))
    db.execute('INSERT INTO crawls(lead_id,report,created_at) VALUES(?,?,?)',(lid,json.dumps({'website_lead_id':42}),time.time()))
    result = snapshot(db,settings,lid)
    assert result['matched_website_lead_id'] == 42
    assert result['next_action'] == 'Open matched website prospect'
    assert by_id(result)['profile']['state'] == 'blocked'


def test_workflow_api_authenticated_and_selected_scope(settings,prepared):
    client = TestClient(create_app(settings))
    assert client.get('/api/workflow').status_code == 401
    client.headers['Authorization'] = 'Bearer '+settings.api_token
    response=client.get('/api/workflow',params={'lead_id':prepared['lead_id']})
    assert response.status_code==200 and response.json()['scope']=='Bright Demo'
    assert client.get('/api/workflow?lead_id=9999').status_code==400
    assert client.get('/api/workflow?lead_id=0').status_code==422
    assert settings.api_token not in response.text and settings.smtp_password not in json.dumps(response.json().get('secrets',{}))


def test_approval_cannot_combine_drafts_and_safe_result_from_different_businesses(db, settings, prepared):
    from outreach.research import add_lead, add_contact
    db.execute("UPDATE contacts SET verification='unknown' WHERE id=?", (prepared['contact_id'],))
    lid = add_lead(db, 'Other fictional company', 'https://other-demo.com', 'A', 'https://other-demo.com')
    cid = add_contact(db, lid, 'owner@other-demo.com', 'https://other-demo.com/contact')
    db.execute("UPDATE contacts SET verification='safe',verified_at=? WHERE id=?", (time.time(), cid))
    assert by_id(snapshot(db, settings))['approval']['state'] == 'blocked'


def test_manual_reply_is_not_proof_of_sequence_approval(db, settings, prepared):
    db.execute("UPDATE contacts SET status='replied' WHERE id=?", (prepared['contact_id'],))
    assert by_id(snapshot(db, settings))['approval']['metric'] == '0 activated contacts'


def test_failed_research_job_with_preserved_partial_evidence_is_visible(db, settings, prepared):
    db.execute("UPDATE leads SET status='review' WHERE id=?", (prepared['lead_id'],))
    jid = db.enqueue('research', {'lead_id': prepared['lead_id']})
    db.execute("UPDATE jobs SET state='failed' WHERE id=?", (jid,))
    assert by_id(snapshot(db, settings))['website']['state'] == 'failed'


def test_stale_inbox_catchup_flag_does_not_show_running_monitor(db, settings, active):
    db.execute("UPDATE messages SET state='sent',sent_at=? WHERE contact_id=? AND step=0", (time.time(), active['contact_id']))
    db.set('imap_caught_up', 'true')
    db.set('imap_last_success', time.time() - 600)
    assert by_id(snapshot(db, settings))['replies']['state'] == 'blocked'


def test_suppressed_safe_contact_cannot_show_verification_complete(db, settings, prepared):
    db.suppress('alex@bright-demo.com', 'Fictional audit opt-out')
    nodes = by_id(snapshot(db, settings))
    assert nodes['verify']['state'] == 'blocked'
    assert nodes['approval']['state'] == 'blocked'


def test_completed_client_journey_not_reported_as_unfinished_review(db, settings, prepared):
    # The lifecycle API enforces references; this fixture isolates map interpretation of its saved terminal state.
    db.execute("INSERT INTO sales(lead_id,stage,updated_at) VALUES(?,?,?)", (prepared['lead_id'], 'completed', time.time()))
    assert by_id(snapshot(db, settings))['sales']['state'] == 'complete'
