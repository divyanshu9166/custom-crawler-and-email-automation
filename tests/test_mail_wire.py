"""Real SMTP/IMAP clients on trusted loopback TLS fixtures; never deliver mail externally."""
import email
import ssl
from datetime import datetime, timezone
from email.message import EmailMessage
from email.policy import default

import pytest

from mail_servers import make_certificate, mail_server
from test_campaigns_mail import ready
from outreach.mail import smtp_send, send_one, poll_inbox, record_inbound


@pytest.fixture
def tls(tmp_path, monkeypatch):
    ca, server_context = make_certificate(tmp_path)
    original = ssl.create_default_context
    monkeypatch.setattr("outreach.mail.ssl.create_default_context", lambda: original(cafile=str(ca)))
    return server_context


def configure_smtp(settings, server, mode):
    settings.smtp_host, settings.smtp_port = server.server_address
    settings.smtp_security = mode


@pytest.mark.parametrize("mode", ["starttls", "ssl"])
def test_real_tls_send_and_imap_optout_stop_sequence(db, settings, active, tls, mode):
    now = ready(db, active["contact_id"])
    with mail_server(tls, mode=mode) as smtp:
        configure_smtp(settings, smtp, mode)
        assert send_one(db, settings, now, smtp_send) == "sent"
        assert smtp.authenticated and smtp.commands.count("DATA") == 1
        delivered = email.message_from_bytes(smtp.messages[0], policy=default)
        assert delivered["To"] == "alex@bright-demo.com"
        assert delivered["Message-ID"] == db.one("SELECT message_id FROM messages WHERE step=0")["message_id"]
        assert delivered["List-Unsubscribe-Post"] == "List-Unsubscribe=One-Click"
        assert settings.postal_address in delivered.get_content()
    reply = EmailMessage()
    reply["From"] = "alex@bright-demo.com"
    reply["To"] = settings.sender_email
    reply["In-Reply-To"] = delivered["Message-ID"]
    reply["Subject"] = "Please remove me"
    reply.set_content('<div>Please unsubscribe me.</div><blockquote>Your previous message.</blockquote>', subtype="html")
    with mail_server(tls, protocol="imap", inbound=reply.as_bytes()) as imap:
        settings.imap_host, settings.imap_port = imap.server_address
        assert poll_inbox(db, settings)
        assert poll_inbox(db, settings)
        assert imap.authenticated
        assert "EXAMINE" in imap.commands
    assert db.one("SELECT status FROM contacts")["status"] == "suppressed"
    assert db.one("SELECT COUNT(*) n FROM messages WHERE state='queued'")["n"] == 0
    assert db.one("SELECT COUNT(*) n FROM events WHERE kind='opt_out'")["n"] == 1


@pytest.mark.parametrize("delayed", [False, True])
def test_four_touch_tls_sequence_respects_actual_acceptance_and_stops(db, settings, active, tls, delayed):
    # Simulated calendar and fresh verification/inbox state; SMTP stays on loopback.
    dates = [(10, 12), (10, 20), (10, 26), (11, 2)] if delayed else [(10, 12), (10, 15), (10, 20), (10, 26)]
    first = ready(db, active["contact_id"])
    assert first == datetime(2026, 10, 12, 12, tzinfo=timezone.utc).timestamp()
    accepted = []
    with mail_server(tls) as smtp:
        configure_smtp(settings, smtp, "starttls")
        for step, (month, day) in enumerate(dates):
            now = datetime(2026, month, day, 12, tzinfo=timezone.utc).timestamp()
            db.execute("UPDATE contacts SET verified_at=? WHERE id=?", (now, active["contact_id"]))
            db.set("imap_last_success", now)
            if step:
                due = db.one("SELECT due_at FROM messages WHERE step=?", (step,))["due_at"]
                assert due == accepted[-1] + (3, 5, 6)[step - 1] * 86400
                assert now >= due
                db.set("imap_last_success", due - 1)
                assert send_one(db, settings, due - 1, smtp_send) == "idle"
                db.set("imap_last_success", now)
            assert send_one(db, settings, now, smtp_send) == "sent"
            accepted.append(now)
            assert len(smtp.messages) == step + 1
            delivered = email.message_from_bytes(smtp.messages[-1], policy=default)
            stored = db.one("SELECT * FROM messages WHERE step=?", (step,))
            assert delivered["Message-ID"] == stored["message_id"] and stored["sent_at"] == now
            assert settings.postal_address in delivered.get_content()
            if step:
                previous = db.one("SELECT message_id FROM messages WHERE step=?", (step - 1,))["message_id"]
                assert delivered["In-Reply-To"] == previous and delivered["References"] == previous
            later = now + settings.min_send_interval_seconds + 1
            db.set("imap_last_success", later)
            assert send_one(db, settings, later, smtp_send) == "idle"
            assert len(smtp.messages) == step + 1  # Overdue steps never fire together.
        assert smtp.commands.count("DATA") == 4
    assert db.one("SELECT status FROM contacts")["status"] == "closed"
    assert db.one("SELECT COUNT(*) n FROM messages WHERE state='sent'")["n"] == 4
    assert db.one("SELECT COUNT(*) n FROM messages WHERE state='queued'")["n"] == 0


@pytest.mark.parametrize("behavior,expected,state", [
    ("bad_login", "not_submitted", "queued"),
    ("data_reject", "rejected", "queued"),
    ("recipient_delay", "failed", "queued"),
    ("drop_after_data", "uncertain", "uncertain"),
    ("quit_disconnect", "sent", "sent"),
])
def test_real_smtp_failure_stages_and_duplicate_protection(db, settings, active, tls, behavior, expected, state):
    now = ready(db, active["contact_id"])
    with mail_server(tls, behavior=behavior) as server:
        configure_smtp(settings, server, "starttls")
        assert send_one(db, settings, now, smtp_send) == expected
        assert db.one("SELECT state FROM messages WHERE step=0")["state"] == state
        data_attempts = server.commands.count("DATA")
        assert send_one(db, settings, now + 1000, smtp_send) != "sent"
        assert server.commands.count("DATA") == data_attempts
        if behavior == "bad_login":
            assert db.get("paused") == "true" and "DATA" not in server.commands
        if behavior == "drop_after_data":
            assert len(server.messages) == 1  # Accepted by fixture, response lost: never retry.


def test_html_positive_reply_does_not_inherit_quoted_unsubscribe(db, active):
    reply = EmailMessage()
    reply["From"] = "alex@bright-demo.com"
    reply.set_content('<p>Yes, please send the outline.</p><div class="gmail_quote">Reply unsubscribe to stop.</div>', subtype="html")
    record_inbound(db, reply.as_bytes(), "html-positive")
    assert db.one("SELECT status FROM contacts")["status"] == "replied"
    assert db.one("SELECT COUNT(*) n FROM suppression")["n"] == 0


@pytest.mark.parametrize("protocol", ["smtp", "imap"])
def test_untrusted_tls_fails_before_authentication(db, settings, active, tmp_path, monkeypatch, protocol):
    _, context = make_certificate(tmp_path)
    # Empty trust store intentionally excludes the fixture CA; production uses system trust.
    monkeypatch.setattr("outreach.mail.ssl.create_default_context",
                        lambda: ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT))
    with mail_server(context, protocol=protocol) as server:
        if protocol == "smtp":
            configure_smtp(settings, server, "starttls")
            assert send_one(db, settings, ready(db, active["contact_id"]), smtp_send) == "not_submitted"
            assert db.get("paused") == "true"
            assert db.one("SELECT state FROM messages WHERE step=0")["state"] == "queued"
            assert "DATA" not in server.commands
        else:
            settings.imap_host, settings.imap_port = server.server_address
            assert not poll_inbox(db, settings)
            assert db.get("imap_caught_up") == "false"
        assert not server.authenticated


def test_demo_database_never_submits_even_with_live_settings(db, settings, active):
    db.set("demo", "true")
    def forbidden(*args):
        raise AssertionError("Demo must not connect to a provider")
    assert send_one(db, settings, ready(db, active["contact_id"]), forbidden) == "demo"
    assert db.one("SELECT state FROM messages WHERE step=0")["state"] == "queued"
