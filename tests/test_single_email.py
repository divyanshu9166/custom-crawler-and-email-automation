"""Production defaults: one initial email, preserved history and no follow-up dispatch."""
import json
import time

import httpx
import pytest
from fastapi.testclient import TestClient

from outreach import email_writer
from outreach.campaigns import archive_followups, create_drafts, approve
from outreach.config import Settings
from outreach.app import create_app
from outreach.mail import send_one


def test_new_workspace_defaults_to_one_email():
    assert Settings(_env_file=None).followups_enabled is False


def test_expired_mailbox_check_is_not_presented_as_fresh(db, settings, prepared):
    db.execute('UPDATE contacts SET verified_at=?', (time.time()-(settings.verification_max_age_hours+1)*3600,))
    client = TestClient(create_app(settings), headers={'Authorization': 'Bearer '+settings.api_token})
    contact = client.get('/api/leads/'+str(prepared['lead_id'])).json()['contacts'][0]
    assert contact['verification'] == 'safe' and contact['verification_fresh'] is False


def test_archive_preserves_initial_edits_history_and_ai_origin(db, settings, prepared):
    cid = prepared['contact_id']
    before = db.all('SELECT * FROM messages WHERE contact_id=? ORDER BY step', (cid,))
    db.execute("UPDATE messages SET subject='Keep my edited initial subject' WHERE id=?", (before[0]['id'],))
    result = archive_followups(db, cid)
    assert result == {'archived': 3, 'retained_message_id': before[0]['id']}
    remaining = db.all('SELECT * FROM messages WHERE contact_id=?', (cid,))
    assert len(remaining) == 1 and remaining[0]['subject'] == 'Keep my edited initial subject'
    archived = json.loads(db.one("SELECT detail FROM events WHERE kind='followup_drafts_archived'")['detail'])
    assert archived['messages'] == before[1:]
    email_writer.assert_ai_origin(db, cid)
    assert archive_followups(db, cid)['archived'] == 0


@pytest.mark.parametrize('change', ['approved', 'scheduled', 'submitted', 'uncertain'])
def test_archive_never_resets_approved_or_submitted_history(db, settings, prepared, change):
    cid = prepared['contact_id']
    if change == 'approved':
        db.execute("UPDATE contacts SET status='active',reviewed_at=? WHERE id=?", (time.time(), cid))
    elif change == 'scheduled':
        db.execute('UPDATE messages SET due_at=? WHERE contact_id=? AND step=1', (time.time(), cid))
    elif change == 'submitted':
        db.execute("UPDATE messages SET state='sent',sent_at=? WHERE contact_id=? AND step=0", (time.time(), cid))
    else:
        db.execute("UPDATE messages SET state='uncertain' WHERE contact_id=? AND step=0", (cid,))
    before = db.all('SELECT * FROM messages')
    with pytest.raises(ValueError):
        archive_followups(db, cid)
    assert db.all('SELECT * FROM messages') == before
    assert not db.one("SELECT id FROM events WHERE kind='followup_drafts_archived'")


def test_real_writer_creates_one_initial_and_approval_dispatch_never_schedules_followups(db, settings, prepared, monkeypatch):
    settings.followups_enabled = False
    cid = prepared['contact_id']
    archive_followups(db, cid)
    source = db.one('SELECT * FROM evidence WHERE id=?', (prepared['evidence_id'],))
    lead = db.one('SELECT * FROM leads WHERE id=?', (prepared['lead_id'],))
    requests = []
    def handle(request):
        payload = json.loads(request.content)
        requests.append(payload)
        assert 'Write ONE' in payload['messages'][0]['content']
        assert payload['max_tokens'] == 1200
        value = {'messages': [{'step': 0, 'subject': 'An idea for '+lead['company'],
                  'body': 'I noticed '+lead['company']+' invites visitors to contact you for a consultation. Would a brief review of the existing enquiry journey be useful?',
                  'support': [{'evidence_id': source['id'], 'quote': 'Contact us for a consultation.'}]}]}
        return httpx.Response(200, json={'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(value)}}]})
    real_client = httpx.Client
    monkeypatch.setattr(email_writer.httpx, 'Client', lambda **kw: real_client(transport=httpx.MockTransport(handle), **kw))
    monkeypatch.setattr(email_writer, 'generate_sequence', REAL_GENERATE)
    settings.draft_api_key, settings.draft_model = 'fictional-key', 'fictional-model'
    create_drafts(db, settings, cid)
    assert len(requests) == 1
    rows = db.all('SELECT * FROM messages')
    assert len(rows) == 1 and rows[0]['step'] == 0 and rows[0]['due_at'] is None
    approve(db, settings, cid, 'Reviewed corporate business sourcing and applicable opt-out eligibility.', 'Founder responsible for the company website.')
    now = time.time()
    db.execute("UPDATE messages SET due_at=?", (now-1,))
    db.set('paused', 'false')
    db.set('imap_last_success', now)
    db.set('imap_caught_up', 'true')
    settings.send_hour_start, settings.send_hour_end = 0, 24
    monkeypatch.setattr('outreach.mail.eligible_now', lambda *a: True)
    submitted = []
    assert send_one(db, settings, now, sender=lambda *a: submitted.append(a)) == 'sent'
    assert len(submitted) == 1
    assert db.one('SELECT status FROM contacts WHERE id=?', (cid,))['status'] == 'closed'
    assert not db.one("SELECT id FROM messages WHERE state='queued'")


def test_legacy_followup_cannot_dispatch_when_followups_disabled(db, settings, active):
    now = time.time()
    settings.followups_enabled = False
    db.execute("UPDATE messages SET state='sent',sent_at=? WHERE step=0", (now-86400,))
    db.execute("UPDATE messages SET due_at=? WHERE step=1", (now-1,))
    db.set('paused', 'false')
    db.set('imap_last_success', now)
    db.set('imap_caught_up', 'true')
    settings.send_hour_start, settings.send_hour_end = 0, 24
    assert send_one(db, settings, now, sender=lambda *a: pytest.fail('Follow-up must never submit')) == 'idle'


def test_single_validator_rejects_multiple_alternatives(db, prepared):
    lead = db.one('SELECT * FROM leads WHERE id=?', (prepared['lead_id'],))
    contact = db.one('SELECT * FROM contacts WHERE id=?', (prepared['contact_id'],))
    with pytest.raises(ValueError, match='exactly 1'):
        email_writer.validate_output({'messages': [{}, {}]}, lead, contact, [])


REAL_GENERATE = email_writer.generate_sequence
