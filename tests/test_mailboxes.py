"""Multiple sending mailboxes, per-mailbox limits, catch-all budget and bulk/automatic approval."""
import time

import pytest
from fastapi.testclient import TestClient

from outreach import mailboxes
from outreach.app import create_app
from outreach.campaign_manager import bulk
from outreach.campaigns import approve, maybe_auto_approve
from outreach.mail import interval_key_for, mailbox_key, send_one
from outreach.preferences import Preferences
from test_campaigns_mail import ready

SECOND = {'id': 'mb00000001', 'label': 'Second', 'sender_name': '', 'sender_email': 'two@sender.example.com',
          'smtp_host': 'smtp2.example.com', 'smtp_port': 587, 'smtp_security': 'starttls',
          'smtp_user': 'two@sender.example.com', 'smtp_password': 'second-secret', 'imap_host': 'imap2.example.com',
          'imap_port': 993, 'imap_user': 'two@sender.example.com', 'imap_password': 'second-secret',
          'imap_folder': 'INBOX', 'daily_limit': 5, 'hourly_limit': 5, 'enabled': True}
PREFIX = 'mailbox:mb00000001:'


def two_mailboxes(db, settings, now):
    settings.extra_mailboxes = [dict(SECOND)]
    db.set(PREFIX + 'imap_last_success', now)
    db.set(PREFIX + 'imap_caught_up', 'true')


def sender_log():
    used = []
    return used, lambda view, message, **_: used.append((view.sender_email, message['From']))


def test_views_expose_each_mailbox_with_its_own_limits_and_sender(settings):
    settings.extra_mailboxes = [dict(SECOND), {**SECOND, 'id': 'mb00000002', 'smtp_user': 'off@x.com', 'enabled': False}]
    views = mailboxes.views(settings)
    assert [v['id'] for v in views] == ['primary', 'mb00000001']
    second = views[1]
    assert second['daily_limit'] == 5 and second['view'].daily_send_limit == 5
    assert second['view'].sender_email == 'two@sender.example.com' and second['view'].sender_name == settings.sender_name
    assert second['view'].sender_company == settings.sender_company and second['prefix'] == PREFIX
    assert views[0]['key'] == mailbox_key(settings)


def test_send_uses_another_mailbox_when_the_primary_is_busy(db, settings, active):
    now = ready(db, active['contact_id'])
    two_mailboxes(db, settings, now)
    db.set(interval_key_for(mailbox_key(settings)), now - 10)  # Primary sent 10 seconds ago.
    used, sender = sender_log()
    assert send_one(db, settings, now, sender) == 'sent'
    assert used[0][0] == 'two@sender.example.com' and 'two@sender.example.com' in used[0][1]
    assert db.one('SELECT mailbox FROM send_attempts')['mailbox'] == 'two@sender.example.com'


def test_each_mailbox_stops_at_its_own_daily_limit(db, settings, active):
    now = ready(db, active['contact_id'])
    two_mailboxes(db, settings, now)
    settings.extra_mailboxes[0]['daily_limit'] = 1
    db.set(interval_key_for(mailbox_key(settings)), now - 10)
    msg = db.one('SELECT id FROM messages WHERE step=1')['id']
    db.execute("INSERT INTO send_attempts(message_id,mailbox,started_at,outcome) VALUES(?,?,?,'sent')", (msg, SECOND['smtp_user'], now - 60))
    assert send_one(db, settings, now, lambda *_, **__: pytest.fail('Both mailboxes are blocked')) == 'rate_limited'


def test_follow_up_stays_on_the_mailbox_that_sent_the_first_email(db, settings, active):
    now = ready(db, active['contact_id'])
    two_mailboxes(db, settings, now)
    db.set(interval_key_for(mailbox_key(settings)), now - 10)
    used, sender = sender_log()
    assert send_one(db, settings, now, sender) == 'sent'
    later = now + 4 * 86400  # The follow-up is due; the primary is idle and has sent less.
    db.execute('UPDATE contacts SET verified_at=? WHERE id=?', (later, active['contact_id']))
    for prefix in ('', PREFIX):
        db.set(prefix + 'imap_last_success', later)
    assert send_one(db, settings, later, sender) == 'sent'
    assert [u[0] for u in used] == ['two@sender.example.com'] * 2


def test_catch_all_is_held_when_disabled_and_sent_within_its_cap_when_enabled(db, settings, active):
    now = ready(db, active['contact_id'])
    db.execute("UPDATE contacts SET verification='catch_all' WHERE id=?", (active['contact_id'],))
    settings.catch_all_share = 0
    assert send_one(db, settings, now, lambda *_, **__: pytest.fail('Catch-all disabled')) == 'idle'
    assert db.one('SELECT status FROM contacts')['status'] == 'hold'
    db.execute("UPDATE contacts SET status='active' WHERE id=?", (active['contact_id'],))
    settings.catch_all_share = 20
    assert mailboxes.catch_all_cap(settings, {'daily_limit': settings.daily_send_limit}) == 4
    assert send_one(db, settings, now, lambda *_, **__: None) == 'sent'


def test_catch_all_cap_and_bounce_guard(db, settings, active):
    settings.catch_all_share = 20
    assert mailboxes.catch_all_cap(settings, {'daily_limit': 3}) == 1  # Never zero while enabled.
    now = time.time()
    lead = active['lead_id']
    with db.connect() as con:
        for i in range(10):
            cid = con.execute("""INSERT INTO contacts(lead_id,email,source_url,unsubscribe_token,created_at,verification,delivery_state)
                VALUES(?,?,?,?,?,'catch_all',?)""", (lead, f'c{i}@bright-demo.com', 'https://bright-demo.com/', f'tok{i}', now,
                                                    'BOUNCED' if i == 0 else 'SENT')).lastrowid
            con.execute("""INSERT INTO messages(contact_id,step,subject,body,evidence_ids,state,sent_at,message_id)
                VALUES(?,0,'s','b','[]','sent',?,?)""", (cid, now, f'<m{i}@x>'))
        assert not mailboxes.catch_all_open(con, settings, now)  # 1 of 10 bounced: above 5%.
        con.execute("UPDATE contacts SET delivery_state='SENT' WHERE email='c0@bright-demo.com'")
        assert mailboxes.catch_all_open(con, settings, now)


def test_approval_accepts_catch_all_only_while_catch_all_sending_is_enabled(db, settings, prepared):
    cid = prepared['contact_id']
    db.execute("UPDATE contacts SET verification='catch_all' WHERE id=?", (cid,))
    with pytest.raises(ValueError, match='safe Reacher'):
        approve(db, settings, cid, 'Reviewed corporate business eligibility', 'Founder owns the website')
    settings.catch_all_share = 20
    approve(db, settings, cid, 'Reviewed corporate business eligibility', 'Founder owns the website')
    assert db.one('SELECT status FROM contacts WHERE id=?', (cid,))['status'] == 'active'


def test_mailbox_settings_hide_passwords_keep_blank_ones_and_reject_duplicates(db, settings):
    prefs = Preferences(settings)
    fields = {k: v for k, v in SECOND.items() if k != 'id'}
    saved = prefs.update_mailbox(db, 'new', dict(fields))
    box = next(m for m in saved['mailboxes'] if not m['primary'])
    assert 'smtp_password' not in box and box['smtp_password_configured'] and box['daily_limit'] == 5
    assert db.get('paused') == 'true'
    prefs.update_mailbox(db, box['id'], {'daily_limit': 40, 'smtp_password': ''})
    assert settings.extra_mailboxes[0]['daily_limit'] == 40 and settings.extra_mailboxes[0]['smtp_password'] == 'second-secret'
    with pytest.raises(ValueError, match='already configured'):
        prefs.update_mailbox(db, 'new', dict(fields))
    with pytest.raises(ValueError, match='between 1 and 500'):
        prefs.update_mailbox(db, box['id'], {'daily_limit': 900})
    assert Preferences(settings).saved['extra_mailboxes'][0]['daily_limit'] == 40  # Persisted privately.
    prefs.remove_mailbox(db, box['id'])
    assert settings.extra_mailboxes == []


def test_mailbox_api_requires_auth_and_never_returns_passwords(settings):
    client = TestClient(create_app(settings))
    body = {k: v for k, v in SECOND.items() if k != 'id'}
    assert client.put('/api/settings/mailboxes/new', json=body).status_code == 401
    headers = {'Authorization': 'Bearer ' + settings.api_token}
    response = client.put('/api/settings/mailboxes/new', json=body, headers=headers)
    assert response.status_code == 200 and 'second-secret' not in response.text
    delivery = client.get('/api/delivery', headers=headers).json()
    assert {m['id'] for m in delivery['mailboxes']} >= {'primary'} and 'second-secret' not in str(delivery)
    assert client.put('/api/settings/mailboxes/../x', json=body, headers=headers).status_code == 404


def test_bulk_approve_queues_prepared_emails_and_reports_the_rest(db, settings, prepared):
    result = bulk(db, settings, [prepared['lead_id']], 'approve')
    assert result['succeeded'] == 1 and 'queued' in result['note']
    assert db.one('SELECT status FROM contacts')['status'] == 'active'
    assert db.one("SELECT state FROM messages WHERE step=0")['state'] == 'queued'
    assert db.one("SELECT 1 FROM events WHERE kind='bulk_approved'")
    again = bulk(db, settings, [prepared['lead_id']], 'approve')
    assert again['succeeded'] == 0 and again['results'][0]['reason'] == 'No prepared email to approve'


def test_auto_approve_only_when_enabled_and_records_why_it_skipped(db, settings, prepared):
    cid = prepared['contact_id']
    assert maybe_auto_approve(db, settings, cid) is False
    settings.auto_approve_enabled = True
    db.execute("UPDATE contacts SET verification='unknown' WHERE id=?", (cid,))
    assert maybe_auto_approve(db, settings, cid) is False
    assert db.one("SELECT 1 FROM events WHERE kind='auto_approve_skipped'")
    db.execute("UPDATE contacts SET verification='safe' WHERE id=?", (cid,))
    assert maybe_auto_approve(db, settings, cid) is True
    assert db.one('SELECT status FROM contacts WHERE id=?', (cid,))['status'] == 'active'
