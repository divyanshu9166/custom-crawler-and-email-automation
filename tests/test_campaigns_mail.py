from datetime import datetime, timezone
from email.message import EmailMessage

import pytest

from outreach.campaigns import approve
from outreach.mail import send_one, record_inbound, eligible_now


def ready(db, cid):
    # Monday during the UK sending window; freshness is set relative to this simulated clock.
    now = datetime(2026, 10, 12, 12, tzinfo=timezone.utc).timestamp()
    db.execute("UPDATE contacts SET verified_at=? WHERE id=?", (now, cid))
    db.execute("UPDATE messages SET due_at=? WHERE contact_id=? AND step=0", (now - 1, cid))
    db.set("imap_last_success", now)
    db.set("imap_caught_up", "true")
    return now


def test_approval_requires_safe_and_one_contact_per_company(db, settings, prepared):
    cid = prepared["contact_id"]
    db.execute("UPDATE contacts SET verification='catch_all' WHERE id=?", (cid,))
    with pytest.raises(ValueError, match="safe Reacher"):
        approve(db, settings, cid, "Reviewed corporate business eligibility", "Founder owns the website")


def test_send_once_and_schedule_from_acceptance(db, settings, active):
    cid = active["contact_id"]
    now = ready(db, cid)
    sent = []
    assert send_one(db, settings, now, lambda s, m: sent.append(m)) == "sent"
    assert len(sent) == 1
    assert sent[0]["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
    assert settings.postal_address in sent[0].get_content()
    assert send_one(db, settings, now + 1, lambda s, m: sent.append(m)) == "rate_limited"
    follow = db.one("SELECT * FROM messages WHERE step=1")
    assert follow["due_at"] == now + 3 * 86400
    assert db.one("SELECT COUNT(*) n FROM messages WHERE state='sent'")["n"] == 1


def test_expired_verification_does_not_send(db, settings, active):
    now = ready(db, active["contact_id"])
    db.execute("UPDATE contacts SET verified_at=?", (now - 80 * 3600,))
    assert send_one(db, settings, now, lambda *_: pytest.fail("Must not send")) == "idle"
    assert db.one("SELECT kind FROM jobs")["kind"] == "verify"


def test_inbox_failure_stops_sending(db, settings, active):
    now = ready(db, active["contact_id"])
    db.set("imap_caught_up", "false")
    assert send_one(db, settings, now, lambda *_: pytest.fail("Must not send")) == "inbox_stale"


def test_uncertain_send_is_never_automatically_retried(db, settings, active):
    now = ready(db, active["contact_id"])
    def uncertain(*args):
        raise TimeoutError("Connection lost after DATA")
    assert send_one(db, settings, now, uncertain) == "uncertain"
    assert db.one("SELECT status FROM contacts")["status"] == "hold"
    assert db.one("SELECT state FROM messages WHERE step=0")["state"] == "uncertain"
    db.set("imap_last_success", now + 600)
    assert send_one(db, settings, now + 600, lambda *_: pytest.fail("Must not retry")) == "idle"


def test_crash_recovery(db, settings, active):
    db.execute("UPDATE messages SET state='sending' WHERE step=0")
    db.recover()
    assert db.one("SELECT state FROM messages WHERE step=0")["state"] == "uncertain"
    assert db.one("SELECT status FROM contacts")["status"] == "hold"


def inbound(db, text, automatic=False):
    msg = EmailMessage()
    msg["From"] = "Alex <alex@bright-demo.com>"
    msg["Subject"] = "Re: Website idea"
    msg["In-Reply-To"] = db.one("SELECT message_id FROM messages WHERE step=0")["message_id"]
    if automatic:
        msg["Auto-Submitted"] = "auto-replied"
    msg.set_content(text)
    return msg.as_bytes()


def test_reply_cancels_followups_and_is_idempotent(db, settings, active):
    raw = inbound(db, "Yes, please send the outline.\n\nOn Monday you wrote:\n> Reply unsubscribe to stop.")
    record_inbound(db, raw, "uid-1")
    record_inbound(db, raw, "uid-1")
    assert db.one("SELECT status FROM contacts")["status"] == "replied"
    assert db.one("SELECT COUNT(*) n FROM messages WHERE state='queued'")["n"] == 0
    assert db.one("SELECT COUNT(*) n FROM events WHERE external_id='uid-1'")["n"] == 1
    assert db.one("SELECT COUNT(*) n FROM suppression")["n"] == 0


def test_optout_global_suppression(db, settings, active):
    record_inbound(db, inbound(db, "No thanks, remove me."), "uid-2")
    assert db.one("SELECT status FROM contacts")["status"] == "suppressed"
    assert db.one("SELECT reason FROM suppression")["reason"] == "opt_out"


def test_out_of_office_pauses(db, settings, active):
    record_inbound(db, inbound(db, "I am away until next week", automatic=True), "uid-3")
    assert db.one("SELECT status FROM contacts")["status"] == "hold"


def test_permanent_dsn_suppresses(db, settings, active):
    raw = b'''From: postmaster@example.net\r
MIME-Version: 1.0\r
Content-Type: multipart/report; report-type=delivery-status; boundary="x"\r
\r
--x\r
Content-Type: text/plain\r
\r
Delivery failed\r
--x\r
Content-Type: message/delivery-status\r
\r
Reporting-MTA: dns; example.net\r
\r
Final-Recipient: rfc822; alex@bright-demo.com\r
Action: failed\r
Status: 5.1.1\r
\r
--x--\r
'''
    record_inbound(db, raw, "uid-dsn")
    assert db.one("SELECT status FROM contacts")["status"] == "suppressed"


def test_send_windows_weekend_and_dst(settings):
    assert eligible_now(settings, "Europe/London", datetime(2026, 10, 12, 12, tzinfo=timezone.utc).timestamp())
    assert not eligible_now(settings, "Europe/London", datetime(2026, 10, 10, 12, tzinfo=timezone.utc).timestamp())
    assert not eligible_now(settings, "America/New_York", datetime(2026, 10, 12, 10, tzinfo=timezone.utc).timestamp())


def test_suppression_overrides_approved_queue(db, settings, active):
    now = ready(db, active["contact_id"])
    db.suppress("alex@bright-demo.com", "requested")
    assert send_one(db, settings, now, lambda *_: pytest.fail("Must not send")) == "idle"


def test_daily_limit(db, settings, active):
    now = ready(db, active["contact_id"])
    settings.daily_send_limit = 1
    db.execute("UPDATE messages SET state='sent',sent_at=? WHERE step=3", (now - 100,))
    assert send_one(db, settings, now, lambda *_: pytest.fail("Must not send")) == "daily_limit"


def test_drafts_do_not_claim_completed_assets(db, settings, prepared):
    bodies = "\n".join(row["body"] for row in db.all("SELECT body FROM messages"))
    assert "30%" not in bodies
    assert "I have built" not in bodies
    assert "Test a clearer explanation" in bodies
