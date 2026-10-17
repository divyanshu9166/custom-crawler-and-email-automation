"""Third business workflow: approval, delivery/stop branches and client records."""
import json
import time

import pytest
from fastapi.testclient import TestClient

from outreach.app import create_app
from outreach.campaigns import approve, resume_contact
from outreach.mail import BeforeSubmissionError, record_inbound, send_one
from outreach.offers import selected_offer
from test_campaigns_mail import inbound, ready
from test_sales import proposal_payload, sales_payload


@pytest.mark.parametrize('change', ['expired', 'recrawl', 'quote'])
def test_third_approval_rejects_changed_campaign_a_sources(db, settings, prepared, change):
    if change == 'expired':
        db.execute('UPDATE evidence SET fetched_at=?', (time.time()-31*86400,))
    elif change == 'recrawl':
        db.execute('INSERT INTO crawls(lead_id,report,created_at) VALUES(?,?,?)',
                   (prepared['lead_id'], '{}', time.time()+1))
    else:
        db.execute("UPDATE evidence SET text='Page replaced with unrelated content',sha256='changed'")
    with pytest.raises(ValueError, match='current'):
        approve(db, settings, prepared['contact_id'], 'Reviewed business eligibility and recipient history',
                'Founder owns the reviewed company website')
    assert db.one('SELECT status FROM contacts')['status'] == 'new'
    assert db.one("SELECT COUNT(*) n FROM messages WHERE state='queued'")['n'] == 0


@pytest.mark.parametrize('change', ['source_hash', 'expired', 'recrawl', 'body', 'recipient', 'country', 'sender', 'legacy'])
def test_third_send_holds_changed_approval_context(db, settings, active, change):
    now = ready(db, active['contact_id'])
    if change == 'source_hash':
        db.execute("UPDATE evidence SET sha256='changed-after-approval'")
    elif change == 'expired':
        db.execute('UPDATE evidence SET fetched_at=?', (time.time()-31*86400,))
    elif change == 'recrawl':
        db.execute('INSERT INTO crawls(lead_id,report,created_at) VALUES(?,?,?)', (active['lead_id'], '{}', time.time()+1))
    elif change == 'body':
        db.execute("UPDATE messages SET body='Unreviewed edited claim after approval' WHERE step=0")
    elif change == 'recipient':
        db.execute("UPDATE contacts SET email='someoneelse@bright-demo.com'")
    elif change == 'country':
        db.execute("UPDATE leads SET country='US'")
    elif change == 'sender':
        settings.postal_address = 'Changed identity after message review'
    else:
        db.execute("UPDATE events SET detail=? WHERE kind='sequence_approved'", (json.dumps({'basis': 'Legacy without proof'}),))
    assert send_one(db, settings, now, lambda *_: pytest.fail('Changed context must never submit SMTP')) == 'idle'
    assert db.one('SELECT status FROM contacts')['status'] == 'hold'
    assert db.one("SELECT COUNT(*) n FROM events WHERE kind='sequence_context_hold'")['n'] == 1


@pytest.mark.parametrize('change', ['verification', 'quota', 'rate', 'pause', 'inbox'])
def test_third_claim_rechecks_readiness_after_candidate_read(db, settings, active, monkeypatch, change):
    import outreach.mail as mail
    now = ready(db, active['contact_id'])
    original = mail.due_candidates
    def candidates(database, instant):
        for row in original(database, instant):
            if change == 'verification':
                db.execute("UPDATE contacts SET verification='invalid'")
            elif change == 'quota':
                settings.daily_send_limit = 1
                db.execute("UPDATE messages SET state='sent',sent_at=? WHERE step=3", (now-1,))
            elif change == 'rate':
                db.set('last_send_attempt', now)
            elif change == 'pause':
                db.set('paused', 'true')
            else:
                db.set('imap_caught_up', 'false')
            yield row
    monkeypatch.setattr(mail, 'due_candidates', candidates)
    assert send_one(db, settings, now, lambda *_: pytest.fail('Readiness changed before claim')) != 'sent'
    assert db.one("SELECT state FROM messages WHERE step=0")['state'] == 'queued'


@pytest.mark.parametrize('stop', ['reply', 'opt_out'])
def test_third_before_submission_failure_keeps_concurrent_stop_cancelled(db, settings, active, stop):
    now = ready(db, active['contact_id'])
    def failed_login(*_):
        record_inbound(db, inbound(db, 'Please send the audit' if stop == 'reply' else 'Please unsubscribe me'), 'concurrent-stop')
        raise BeforeSubmissionError('Fixture login failed')
    assert send_one(db, settings, now, failed_login) == 'not_submitted'
    assert db.one("SELECT state FROM messages WHERE step=0")['state'] == 'cancelled'
    assert db.one('SELECT status FROM contacts')['status'] == ('replied' if stop == 'reply' else 'suppressed')


def dsn(status, action):
    return (f'From: postmaster@example.net\r\nMIME-Version: 1.0\r\n'
            f'Content-Type: multipart/report; report-type=delivery-status; boundary="x"\r\n\r\n'
            f'--x\r\nContent-Type: message/delivery-status\r\n\r\nReporting-MTA: dns; example.net\r\n\r\n'
            f'Final-Recipient: rfc822; alex@bright-demo.com\r\nAction: {action}\r\nStatus: {status}\r\n\r\n--x--\r\n').encode()


@pytest.mark.parametrize('status,action,kind,contact_state', [
    ('2.0.0', 'delivered', 'delivery_notice', 'active'),
    ('2.0.0', 'relayed', 'delivery_notice', 'active'),
    ('4.2.0', 'delayed', 'delivery_delay', 'hold'),
    ('5.1.1', 'failed', 'bounce', 'suppressed'),
    ('', 'unknown', 'delivery_delay', 'hold'),
])
def test_third_delivery_status_does_not_treat_positive_notice_as_delay(db, active, status, action, kind, contact_state):
    record_inbound(db, dsn(status, action), 'fixture-dsn')
    assert db.one("SELECT kind FROM events WHERE external_id='fixture-dsn'")['kind'] == kind
    assert db.one('SELECT status FROM contacts')['status'] == contact_state


def test_third_resume_rejects_changed_source_before_scheduling(db, settings, active):
    db.execute("UPDATE contacts SET status='hold'")
    db.execute("UPDATE evidence SET sha256='new-source'")
    with pytest.raises(ValueError, match='context|source'):
        resume_contact(db, settings, active['contact_id'], 'Reviewed vacation date and remaining follow-up messages', time.time()+86400)
    assert db.one('SELECT status FROM contacts')['status'] == 'hold'


def test_third_call_and_proposal_require_recorded_baseline_or_measurement_plan(db, settings, prepared):
    client = TestClient(create_app(settings), headers={'Authorization': 'Bearer '+settings.api_token})
    lid = prepared['lead_id']
    assert client.post(f'/api/leads/{lid}/activity', json={'channel': 'meeting', 'kind': 'reply',
                                                       'note': 'Fictional client discussed the booking need.'}).status_code == 200
    value = sales_payload(client, lid, 'call_booked')
    value.pop('baseline_notes', None)
    result = client.put(f'/api/leads/{lid}/sales', json=value)
    assert result.status_code == 400 and 'baseline' in result.json()['detail']
    value['baseline_notes'] = 'Unknown baseline; client will measure qualified inquiries for two weeks before the pilot.'
    assert client.put(f'/api/leads/{lid}/sales', json=value).status_code == 200
    pid = client.post(f'/api/leads/{lid}/proposals', json=proposal_payload()).json()['id']
    assert 'Unknown baseline' in client.get(f'/api/proposals/{pid}/download').text


def test_third_unsent_revision_preserves_copy_history_and_requires_new_approval(db, settings, active):
    client = TestClient(create_app(settings), headers={'Authorization': 'Bearer '+settings.api_token})
    cid = active['contact_id']
    before = db.all('SELECT * FROM messages ORDER BY step')
    url = f'/api/contacts/{cid}/revise'
    assert client.post(url, json={'note': 'Review recipient and pilot copy before the first send'}).status_code == 422
    assert client.post(url, json={'note': 'Review recipient and pilot copy before the first send',
                                  'reviewed_pending_messages': True}).status_code == 200
    assert db.one('SELECT status,reviewed_at FROM contacts') == {'status': 'new', 'reviewed_at': None}
    after = db.all('SELECT * FROM messages ORDER BY step')
    assert [m['message_id'] for m in before] == [m['message_id'] for m in after]
    assert all(m['state'] == 'draft' and m['due_at'] is None for m in after)
    event = db.one("SELECT detail FROM events WHERE kind='sequence_returned_to_review'")
    assert json.loads(event['detail'])['previous_messages'] == before
    db.execute("UPDATE messages SET body=body || '\nReviewed useful extra context.' WHERE step=0")
    approve(db, settings, cid, 'Reviewed eligibility and shared history after pilot revision', 'Founder owns the website journey')
    assert send_one(db, settings, ready(db, cid), lambda *_: None) == 'sent'


@pytest.mark.parametrize('state', ['sent', 'sending', 'uncertain', 'failed'])
def test_third_revision_cannot_erase_submission_or_uncertainty(db, settings, active, state):
    from outreach.campaigns import revise_unsent_sequence
    db.execute('UPDATE messages SET state=? WHERE step=0', (state,))
    with pytest.raises(ValueError, match='Submitted'):
        revise_unsent_sequence(db, active['contact_id'], 'Inspect provider logs before any further email is considered')
    assert db.one('SELECT state FROM messages WHERE step=0')['state'] == state


@pytest.mark.parametrize('text,automatic', [('Please send the proposed audit', False),
                                           ('What does your proposal include?', False),
                                           ('Please follow up next month', False),
                                           ('I am away until next week', True)])
def test_third_all_reply_branches_stop_followups_without_inventing_interest(db, settings, active, text, automatic):
    record_inbound(db, inbound(db, text, automatic), 'third-reply')
    assert db.one('SELECT status FROM contacts')['status'] == ('hold' if automatic else 'replied')
    assert db.one("SELECT COUNT(*) n FROM messages WHERE state='queued'")['n'] == 0
    sales = db.one('SELECT * FROM sales')
    assert (sales is None) if automatic else (sales['stage'] == 'contacted' and sales['cold_email_hold'])
    if not automatic:
        assert db.one("SELECT COUNT(*) n FROM tasks WHERE kind='followup'")['n'] == 1


def test_third_normalized_country_url_does_not_reject_current_homepage(db, settings, prepared):
    db.execute("UPDATE evidence SET url='https://bright-demo.com'")
    lead = db.one('SELECT * FROM leads WHERE id=?', (prepared['lead_id'],))
    assert selected_offer(db, lead) == 'website_improvement'
    approve(db, settings, prepared['contact_id'], 'Reviewed eligibility and the exact homepage country quote', 'Founder owns the reviewed website')


def test_third_proposal_review_cannot_approve_changed_client_context(db, settings, prepared):
    client = TestClient(create_app(settings), headers={'Authorization': 'Bearer '+settings.api_token})
    lid = prepared['lead_id']
    client.post(f'/api/leads/{lid}/activity', json={'channel': 'meeting', 'kind': 'reply', 'note': 'Fictional client confirmed the initial booking requirement.'})
    client.put(f'/api/leads/{lid}/sales', json=sales_payload(client, lid))
    pid = client.post(f'/api/leads/{lid}/proposals', json=proposal_payload()).json()['id']
    changed = sales_payload(client, lid)
    changed['confirmed_problem'] = 'Client corrected the need: support questions rather than bookings.'
    assert client.put(f'/api/leads/{lid}/sales', json=changed).status_code == 200
    result = client.post(f'/api/proposals/{pid}/approve', json={'reviewed_scope_and_terms': True})
    assert result.status_code == 400 and 'context' in result.json()['detail']
    assert db.one('SELECT state FROM proposals WHERE id=?', (pid,))['state'] == 'draft'
    replacement = client.post(f'/api/leads/{lid}/proposals', json=proposal_payload()).json()['id']
    assert replacement != pid
    assert client.post(f'/api/proposals/{replacement}/approve', json={'reviewed_scope_and_terms': True}).status_code == 200


def test_third_completion_cannot_leave_delivery_work_open(db, settings, prepared):
    from outreach.sales import create_task
    client = TestClient(create_app(settings), headers={'Authorization': 'Bearer '+settings.api_token})
    lid = prepared['lead_id']
    client.post(f'/api/leads/{lid}/activity', json={'channel': 'meeting', 'kind': 'reply', 'note': 'Fictional client confirmed a scoped pilot.'})
    client.put(f'/api/leads/{lid}/sales', json=sales_payload(client, lid))
    pid = client.post(f'/api/leads/{lid}/proposals', json=proposal_payload()).json()['id']
    client.post(f'/api/proposals/{pid}/approve', json={'reviewed_scope_and_terms': True})
    client.post(f'/api/proposals/{pid}/sent', json={'actually_delivered': True, 'reference': 'Fictional actual proposal delivery reference'})
    task = create_task(db, lid, {'kind': 'delivery', 'title': 'Implement and review the agreed pilot booking page', 'due_at': time.time()+86400})
    value = {**sales_payload(client, lid, 'completed'), 'proposal_id': pid,
             'agreement_reference': 'Fictional signed pilot agreement', 'payment_reference': 'Fictional actual initial payment',
             'acceptance_reference': 'Fictional client acceptance reference', 'outcome_notes': 'Outcome is inconclusive; no measured lift claimed.'}
    result = client.put(f'/api/leads/{lid}/sales', json=value)
    assert result.status_code == 400 and 'delivery tasks' in result.json()['detail']
    assert client.put(f'/api/tasks/{task}', json={'state': 'done', 'outcome': 'Fictional client reviewed and accepted the pilot page.'}).status_code == 200
    value['version'] = client.get(f'/api/leads/{lid}').json()['sales']['version']
    assert client.put(f'/api/leads/{lid}/sales', json=value).status_code == 200
