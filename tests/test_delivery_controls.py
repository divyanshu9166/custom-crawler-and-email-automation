"""Delivery/stop semantics, mailbox budgets and retries; no external delivery."""
import json
import smtplib
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from outreach.app import create_app
from outreach.db import DB, SCHEMA
from outreach.mail import mailbox_key, mailbox_usage, mark_sent, record_inbound, send_one, smtp_send
from test_campaigns_mail import inbound, ready
from test_third_workflow import dsn


def state(db):
    return db.one('SELECT delivery_state FROM contacts ORDER BY id')['delivery_state']


@pytest.mark.parametrize('kind,expected', [('reply', 'REPLIED'), ('opt_out', 'UNSUBSCRIBED'), ('bounce', 'BOUNCED')])
def test_sent_then_stop_cancels_all_pending_and_survives_restart(db, settings, active, kind, expected):
    now = ready(db, active['contact_id'])
    assert send_one(db, settings, now, lambda *_: None) == 'sent'
    assert state(db) == 'SENT'
    raw = dsn('5.1.1', 'failed') if kind == 'bounce' else inbound(db, 'Please unsubscribe me' if kind == 'opt_out' else 'Please send the details')
    record_inbound(db, raw, 'stop')
    assert state(db) == expected
    assert not db.one("SELECT 1 FROM messages WHERE state IN ('draft','queued')")
    reopened = DB(settings.database)
    assert state(reopened) == expected
    reopened.set('imap_last_success', now + 3600)
    assert send_one(reopened, settings, now + 3600, lambda *_: pytest.fail('Stopped contact must not send')) == 'idle'


def test_delayed_acceptance_record_never_erases_stop(db, settings, active):
    row = db.one('SELECT * FROM messages WHERE step=0')
    record_inbound(db, inbound(db, 'Please unsubscribe me'), 'stop-during-send')
    mark_sent(db, row, ready(db, active['contact_id']), followups_enabled=True)
    assert state(db) == 'UNSUBSCRIBED'
    assert not db.one("SELECT 1 FROM messages WHERE state='queued'")
    # A later DSN or reply cannot remove the stronger opt-out state.
    record_inbound(db, dsn('5.1.1', 'failed'), 'later-bounce')
    record_inbound(db, inbound(db, 'Thanks'), 'later-reply')
    assert state(db) == 'UNSUBSCRIBED'


def test_same_inbound_copied_to_another_uid_is_not_processed_twice(db, active):
    raw = inbound(db, 'Yes, send details')
    record_inbound(db, raw, 'folder-a:1')
    record_inbound(db, raw, 'folder-b:8')
    assert db.one("SELECT COUNT(*) n FROM events WHERE kind='reply'")['n'] == 1
    assert db.one('SELECT COUNT(*) n FROM tasks')['n'] == 1


@pytest.mark.parametrize('text', ['Please stop.', 'Please remove my email from your list', 'I want to opt out', "Don't contact me again"])
def test_explicit_do_not_contact_wording_is_globally_suppressed(db, active, text):
    record_inbound(db, inbound(db, text), 'stop-wording')
    assert state(db) == 'UNSUBSCRIBED'
    assert db.one('SELECT COUNT(*) n FROM suppression')['n'] == 1


def test_subject_only_optout_is_not_mistaken_for_normal_reply(db, active):
    from email.message import EmailMessage
    msg = EmailMessage()
    msg['From'] = 'alex@bright-demo.com'
    msg['Subject'] = 'Unsubscribe'
    msg.set_content('')
    record_inbound(db, msg.as_bytes(), 'subject-only')
    assert state(db) == 'UNSUBSCRIBED'


def test_dsn_with_original_recipient_fallback_stops_contact(db, active):
    record_inbound(db, dsn('5.1.1', 'failed').replace(b'Final-Recipient:', b'Original-Recipient:'), 'original-dsn')
    assert state(db) == 'BOUNCED'


def test_multi_recipient_dsn_applies_each_recipient_status(db, active):
    db.execute("INSERT INTO contacts(lead_id,email,source_url,unsubscribe_token,created_at,status) VALUES(?,?,?,?,?,?)",
               (active['lead_id'], 'other@bright-demo.com', 'https://bright-demo.com', 'other-token', 1, 'active'))
    raw = dsn('5.1.1', 'failed').replace(b'\r\n--x--', b'\r\nFinal-Recipient: rfc822; other@bright-demo.com\r\nAction: delayed\r\nStatus: 4.2.0\r\n\r\n--x--')
    # A DSN recipient block is separated by a blank line.
    raw = raw.replace(b'\r\nFinal-Recipient: rfc822; other', b'\r\n\r\nFinal-Recipient: rfc822; other')
    record_inbound(db, raw, 'multi-dsn')
    assert state(db) == 'BOUNCED'
    other = db.one("SELECT * FROM contacts WHERE email='other@bright-demo.com'")
    assert other['status'] == 'hold' and other['delivery_state'] == ''
    assert db.one('SELECT COUNT(*) n FROM suppression')['n'] == 1


def test_recipient_temporary_failures_retry_three_times_with_same_message_id(db, settings, active):
    now = ready(db, active['contact_id'])
    ids = []
    def refuse(_settings, message):
        ids.append(message['Message-ID'])
        raise smtplib.SMTPRecipientsRefused({'alex@bright-demo.com': (451, b'try later')})
    for attempt in range(3):
        db.set('imap_last_success', now)
        assert send_one(db, settings, now, refuse) == 'failed'
        row = db.one('SELECT * FROM messages WHERE step=0')
        if attempt < 2:
            assert row['state'] == 'queued'
            assert row['due_at'] == now + 3600 * 2 ** attempt
            now = row['due_at']
        else:
            assert row['state'] == 'failed'
    assert len(set(ids)) == 1
    assert db.one('SELECT status FROM contacts')['status'] == 'hold'
    assert db.one('SELECT COUNT(*) n FROM send_attempts')['n'] == 3
    assert db.one("SELECT COUNT(*) n FROM events WHERE kind='send_retry_exhausted'")['n'] == 1


def test_temporary_data_refusal_then_acceptance_has_one_accepted_attempt(db, settings, active):
    now = ready(db, active['contact_id'])
    def refuse(*_):
        raise smtplib.SMTPDataError(451, b'Temporary local fixture error')
    assert send_one(db, settings, now, refuse) == 'rejected'
    now += 3600
    db.set('imap_last_success', now)
    assert send_one(db, settings, now, lambda *_: None) == 'sent'
    assert [r['outcome'] for r in db.all('SELECT outcome FROM send_attempts ORDER BY id')] == ['rejected', 'sent']
    with db.connect() as con:
        assert mailbox_usage(con, settings.sender_email.lower(), now - 86400) == 1


def test_permanent_sender_rejection_holds_without_suppressing_recipient(db, settings, active):
    def refuse(*_):
        raise smtplib.SMTPSenderRefused(550, b'Sender policy failure', 'sender@demo.com')
    assert send_one(db, settings, ready(db, active['contact_id']), refuse) == 'rejected'
    assert db.one('SELECT status FROM contacts')['status'] == 'hold'
    assert not db.one('SELECT 1 FROM suppression')
    assert db.one('SELECT smtp_code FROM send_attempts')['smtp_code'] == 550


def test_uncertain_attempt_uses_budget_and_can_never_be_reclaimed(db, settings, active):
    now = ready(db, active['contact_id'])
    def fail(*_):
        raise TimeoutError('Unknown DATA outcome')
    assert send_one(db, settings, now, fail) == 'uncertain'
    with db.connect() as con:
        assert mailbox_usage(con, settings.sender_email.lower(), now - 86400) == 1
    # Even an accidental queue/status reset cannot resend an uncertain message.
    db.execute("UPDATE contacts SET status='active'")
    db.execute("UPDATE messages SET state='queued' WHERE step=0")
    db.set('imap_last_success', now + 1000)
    assert send_one(db, settings, now + 1000, lambda *_: pytest.fail('Duplicate')) == 'idle'


@pytest.mark.parametrize('outcome', ['sending', 'sent', 'uncertain'])
def test_hourly_limit_counts_reservations_and_uncertainty(db, settings, active, outcome):
    now = ready(db, active['contact_id'])
    mid = db.one('SELECT id FROM messages WHERE step=3')['id']
    db.execute('INSERT INTO send_attempts(message_id,mailbox,started_at,outcome) VALUES(?,?,?,?)',
               (mid, settings.sender_email.lower(), now - 200, outcome))
    settings.hourly_send_limit = 1
    assert send_one(db, settings, now, lambda *_: pytest.fail('Quota')) == 'hourly_limit'
    with db.connect() as con:
        assert mailbox_usage(con, 'another@demo.com', now - 3600) == 0


def test_daily_budget_does_not_reset_at_midnight(db, settings, active):
    now = ready(db, active['contact_id'])
    mid = db.one('SELECT id FROM messages WHERE step=3')['id']
    db.execute('INSERT INTO send_attempts(message_id,mailbox,started_at,outcome) VALUES(?,?,?,?)',
               (mid, settings.sender_email.lower(), now - 23 * 3600, 'sent'))
    settings.daily_send_limit = 1
    assert send_one(db, settings, now, lambda *_: pytest.fail('Quota')) == 'daily_limit'


def test_sender_aliases_share_authenticated_mailbox_budget(settings):
    settings.smtp_user = ' Primary@sender.example.com '
    assert mailbox_key(settings) == 'primary@sender.example.com'
    settings.sender_email = 'alias@sender.example.com'
    settings.smtp_host = 'replacement-smtp.example.com'
    assert mailbox_key(settings) == 'primary@sender.example.com'


@pytest.mark.parametrize('outcome', ['sent', 'not_sent'])
def test_manual_reconciliation_updates_ledger_without_reviving_optout(db, settings, active, outcome):
    now = ready(db, active['contact_id'])
    def uncertain(*_):
        raise TimeoutError()
    send_one(db, settings, now, uncertain)
    record_inbound(db, inbound(db, 'unsubscribe'), 'stop-before-reconciliation')
    client = TestClient(create_app(settings), headers={'Authorization': 'Bearer ' + settings.api_token})
    mid = db.one('SELECT id FROM messages WHERE step=0')['id']
    result = client.post(f'/api/messages/{mid}/reconcile', json={'outcome': outcome, 'evidence': 'Checked provider submission logs and confirmed the result.'})
    assert result.status_code == 200
    assert state(db) == 'UNSUBSCRIBED'
    assert db.one('SELECT outcome FROM send_attempts')['outcome'] == ('sent' if outcome == 'sent' else 'confirmed_not_sent')
    assert not db.one("SELECT 1 FROM messages WHERE state IN ('draft','queued')")


def test_failed_initial_cannot_be_skipped_when_resuming(db, settings, active):
    import time
    from outreach.campaigns import resume_contact
    db.execute("UPDATE messages SET state='failed' WHERE step=0")
    db.execute("UPDATE contacts SET status='hold'")
    with pytest.raises(ValueError, match='failed message'):
        resume_contact(db, settings, active['contact_id'], 'Reviewed failed delivery and attempted to resume', time.time() + 3600)


def test_quick_tunnel_cannot_create_expiring_live_unsubscribe_links(settings):
    settings.public_url = 'https://temporary-example.trycloudflare.com'
    assert any('stable domain' in gap for gap in settings.sending_gaps())
    settings.public_url = 'https://mail.example.com'
    assert not settings.sending_gaps()


def test_two_senders_cannot_submit_same_queue_item(db, settings, active):
    now = ready(db, active['contact_id'])
    sent = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: send_one(db, settings, now, lambda _s, m: sent.append(m['Message-ID'])), range(2)))
    assert results.count('sent') == 1 and len(sent) == 1
    assert db.one('SELECT COUNT(*) n FROM send_attempts')['n'] == 1


@pytest.mark.parametrize('stop', ['reply', 'opt_out', 'pause'])
def test_stop_during_smtp_login_prevents_data_submission(db, settings, active, monkeypatch, stop):
    now = ready(db, active['contact_id'])
    class SMTP:
        def __init__(self, *args, **kwargs):
            pass
        def ehlo(self):
            pass
        def starttls(self, **kwargs):
            pass
        def login(self, *args):
            if stop == 'pause':
                db.set('paused', 'true')
            else:
                record_inbound(db, inbound(db, 'unsubscribe' if stop == 'opt_out' else 'Interested'), 'during-login')
        def send_message(self, *_):
            pytest.fail('DATA must not be submitted after a stop')
        def quit(self):
            pass
    monkeypatch.setattr('outreach.mail.smtplib.SMTP', SMTP)
    assert send_one(db, settings, now, smtp_send) == 'cancelled'
    assert db.one('SELECT outcome FROM send_attempts')['outcome'] == 'cancelled'


def test_unsubscribe_one_click_is_public_idempotent_and_scanner_safe(db, settings, active):
    client = TestClient(create_app(settings))
    token = db.one('SELECT unsubscribe_token FROM contacts')['unsubscribe_token']
    url = '/unsubscribe/' + token
    assert client.get(url).status_code == 200 and state(db) == ''
    for _ in range(2):
        response = client.post(url, data={'List-Unsubscribe': 'One-Click'}, follow_redirects=False)
        assert response.status_code == 200 and not response.headers.get('location')
    assert state(db) == 'UNSUBSCRIBED'
    assert db.one("SELECT COUNT(*) n FROM events WHERE kind='opt_out'")['n'] == 1
    assert client.post('/unsubscribe/unknown').status_code == 404


def test_delivery_api_auth_and_suppression_of_future_imports(db, settings, active):
    anonymous = TestClient(create_app(settings))
    assert anonymous.get('/api/delivery').status_code == 401
    client = TestClient(create_app(settings), headers={'Authorization': 'Bearer ' + settings.api_token})
    assert client.post('/api/suppression', json={'email': ' Future@bright-demo.com ', 'reason': 'Do not contact'}).status_code == 200
    assert db.one("SELECT 1 FROM suppression WHERE email='future@bright-demo.com'")
    from outreach.research import add_contact
    cid = add_contact(db, active['lead_id'], 'future@bright-demo.com', 'https://bright-demo.com/')
    assert db.one('SELECT delivery_state FROM contacts WHERE id=?', (cid,))['delivery_state'] == 'UNSUBSCRIBED'
    response = client.get('/api/delivery').json()
    assert response['suppressed_count'] == 1 and response['suppression'][0]['reason'] == 'Do not contact'
    assert 'unsubscribe_token' not in json.dumps(response)
    assert client.get('/api/delivery?limit=101').status_code == 422


def test_additive_migration_preserves_sent_rows_and_backfills_state(tmp_path):
    path = tmp_path / 'old.db'
    with sqlite3.connect(path) as con:
        con.executescript(SCHEMA)
        con.execute("INSERT INTO leads(domain,website,company,campaign,source_url,created_at,updated_at) VALUES('demo.com','https://demo.com','Demo','A','https://demo.com',1,1)")
        con.execute("INSERT INTO contacts(lead_id,email,source_url,unsubscribe_token,created_at) VALUES(1,'a@demo.com','https://demo.com','old-token',1)")
        con.execute("INSERT INTO messages(contact_id,step,subject,body,evidence_ids,state,sent_at,message_id) VALUES(1,0,'Existing','Preserve','[]','sent',100,'<old@demo.com>')")
        con.execute('PRAGMA user_version=4')
    upgraded = DB(path)
    assert state(upgraded) == 'SENT'
    assert upgraded.one('SELECT body FROM messages')['body'] == 'Preserve'
    upgraded.suppress('a@demo.com', 'Do not contact')
    assert state(DB(path)) == 'UNSUBSCRIBED'
