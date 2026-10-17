from email.message import EmailMessage

from outreach.mail import smtp_send, poll_inbox


def test_smtp_tls_auth_and_quit_failure_after_acceptance(settings, monkeypatch):
    calls = []
    class SMTP:
        def __init__(self, host, port, timeout):
            calls.append((host, port, timeout))
        def ehlo(self):
            calls.append("ehlo")
        def starttls(self, context):
            calls.append("tls")
        def login(self, user, password):
            calls.append("login")
        def send_message(self, message):
            calls.append("accepted")
            return {}
        def quit(self):
            raise TimeoutError("QUIT failed after acceptance")
        def close(self):
            calls.append("closed")
    monkeypatch.setattr("outreach.mail.smtplib.SMTP", SMTP)
    msg = EmailMessage()
    msg["From"] = settings.sender_email
    msg["To"] = "alex@bright-demo.com"
    msg.set_content("Test only; no network transport")
    smtp_send(settings, msg)
    assert calls.index("tls") < calls.index("login") < calls.index("accepted")
    assert calls[-1] == "closed"


def test_imap_bounded_read_and_reply_stop(db, settings, active, monkeypatch):
    msg = EmailMessage()
    msg["From"] = "alex@bright-demo.com"
    msg["Subject"] = "Please send the outline"
    msg.set_content("Interested; please tell me more.")
    class IMAP:
        def __init__(self, *args, **kwargs):
            pass
        def login(self, user, password):
            return "OK", []
        def select(self, folder, readonly):
            assert readonly is True
            return "OK", [b"1"]
        def response(self, name):
            return name, [b"123"]
        def uid(self, operation, *args):
            if operation == "search":
                return "OK", [b"1"]
            assert args[-1] == "(BODY.PEEK[]<0.65536>)"
            return "OK", [(b"1 BODY", msg.as_bytes()), b")"]
        def logout(self):
            pass
    monkeypatch.setattr("outreach.mail.imaplib.IMAP4_SSL", IMAP)
    assert poll_inbox(db, settings)
    assert db.get("imap_caught_up") == "true"
    assert db.get("imap_last_uid") == "1"
    assert db.one("SELECT status FROM contacts")["status"] == "replied"
    assert poll_inbox(db, settings)  # repeated UID is not replayed
    assert db.one("SELECT COUNT(*) n FROM events WHERE kind='reply'")["n"] == 1


def test_imap_login_failure_invalidates_readiness(db, settings, monkeypatch):
    db.set("imap_caught_up", "true")
    class IMAP:
        def __init__(self, *args, **kwargs):
            raise ConnectionError("No connection")
    monkeypatch.setattr("outreach.mail.imaplib.IMAP4_SSL", IMAP)
    assert poll_inbox(db, settings) is False
    assert db.get("imap_caught_up") == "false"


def test_unsafe_reverification_holds_instead_of_looping(db, settings, active):
    from test_campaigns_mail import ready
    from outreach.mail import send_one
    now = ready(db, active["contact_id"])
    db.execute("UPDATE contacts SET verification='unknown'")
    assert send_one(db, settings, now) == "idle"
    assert db.one("SELECT status FROM contacts")["status"] == "hold"
    assert db.one("SELECT COUNT(*) n FROM jobs")["n"] == 0


def test_resume_requires_fresh_result_and_cannot_override_optout(db, settings, active):
    import time
    import pytest
    from outreach.campaigns import resume_contact
    cid = active["contact_id"]
    db.execute("UPDATE contacts SET status='hold'")
    resume_contact(db, settings, cid, "Reviewed the vacation reply and confirmed a suitable future date", time.time() + 3600)
    assert db.one("SELECT status FROM contacts")["status"] == "active"
    db.suppress("alex@bright-demo.com", "unsubscribe")
    with pytest.raises(ValueError):
        resume_contact(db, settings, cid, "Cannot resume an opted-out contact for any reason", time.time() + 3600)
