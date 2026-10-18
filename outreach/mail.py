import email
import hashlib
import imaplib
import re
import smtplib
import ssl
import time
from datetime import datetime, timezone
from email.message import EmailMessage
from email.policy import default
from email.utils import formataddr, format_datetime, getaddresses
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from .sales import assert_outreach_open, ensure_sales
from .research import assert_contact_ownership
from .sequence import Reader, assert_approved


class BeforeSubmissionError(Exception):
    """Connection/TLS/login failed before any MAIL/RCPT/DATA submission was attempted."""


def eligible_now(settings, tz, now):
    local = datetime.fromtimestamp(now, ZoneInfo(tz))
    return local.weekday() < 5 and settings.send_hour_start <= local.hour < settings.send_hour_end


def build_message(settings, contact, row, previous=None):
    message = EmailMessage()
    message["From"] = formataddr((settings.sender_name, settings.sender_email))
    message["To"] = contact["email"]
    message["Subject"] = row["subject"]
    message["Date"] = format_datetime(datetime.now(timezone.utc))
    message["Message-ID"] = row["message_id"]
    message["Reply-To"] = settings.sender_email
    if previous:
        message["In-Reply-To"] = previous["message_id"]
        message["References"] = previous["message_id"]
    url = settings.public_url.rstrip("/") + "/unsubscribe/" + contact["unsubscribe_token"]
    message["List-Unsubscribe"] = f"<{url}>"
    message["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    footer = (f"\n\n{settings.sender_name}\n{settings.sender_company}\n{settings.sender_website}\n"
              f"{settings.postal_address}\n\nBusiness inquiry about our services. "
              f"To stop these emails, reply 'unsubscribe' or visit {url}")
    message.set_content(row["body"] + footer)
    return message


def smtp_send(settings, message):
    if settings.smtp_security not in {"ssl", "starttls"}:
        raise ValueError("TLS is required")
    smtp = None
    try:
        try:
            context = ssl.create_default_context()
            if settings.smtp_security == "ssl":
                smtp = smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=30, context=context)
            else:
                smtp = smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30)
            smtp.ehlo()
            if settings.smtp_security == "starttls":
                smtp.starttls(context=context)
                smtp.ehlo()
            smtp.login(settings.smtp_user, settings.smtp_password)
        except Exception as exc:
            raise BeforeSubmissionError(type(exc).__name__) from exc
        refused = smtp.send_message(message)
        if refused:
            raise smtplib.SMTPRecipientsRefused(refused)
        # A successful DATA response establishes server acceptance, not inbox placement.
    finally:
        # A QUIT failure after DATA must not turn an accepted message into an uncertain send.
        if smtp:
            try:
                smtp.quit()
            except Exception:
                try:
                    smtp.close()
                except Exception:
                    pass  # Cleanup cannot overwrite a confirmed DATA result or the original failure.


def due_candidates(db, now):
    # Keyset pagination keeps memory bounded without starving eligible timezones behind older rows.
    due, message_id = -1.0, 0
    while True:
        rows = db.all("SELECT m.*,c.email,c.verified_at,c.verification,l.timezone FROM messages m JOIN contacts c ON c.id=m.contact_id JOIN leads l ON l.id=c.lead_id WHERE m.state='queued' AND m.due_at<=? AND c.status='active' AND (m.due_at>? OR (m.due_at=? AND m.id>?)) ORDER BY m.due_at,m.id LIMIT 100", (now, due, due, message_id))
        if not rows:
            return
        yield from rows
        due, message_id = rows[-1]["due_at"], rows[-1]["id"]


def send_one(db, settings, now=None, sender=smtp_send):
    now = time.time() if now is None else now
    if db.get("demo") == "true":
        return "demo"
    if not settings.sending_enabled or settings.sending_gaps() or db.get("paused", "true") != "false":
        return "disabled"
    if now - float(db.get("imap_last_success", "0")) > 180 or db.get("imap_caught_up") != "true":
        return "inbox_stale"
    if now - float(db.get("last_send_attempt", "0")) < settings.min_send_interval_seconds:
        return "rate_limited"
    day_start = datetime.fromtimestamp(now, timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    count = db.one("SELECT COUNT(*) n FROM messages WHERE sent_at>=?", (day_start,))["n"]
    if count >= settings.daily_send_limit:
        return "daily_limit"
    for row in due_candidates(db, now):
        if row['step'] > 0 and not settings.followups_enabled:
            continue
        if not eligible_now(settings, row["timezone"], now):
            continue
        if row["verification"] != "safe":
            db.execute("UPDATE contacts SET status='hold' WHERE id=? AND status='active'", (row["contact_id"],))
            continue
        if not row["verified_at"] or now - row["verified_at"] > settings.verification_max_age_hours * 3600:
            db.enqueue("verify", {"contact_id": row["contact_id"]})
            continue
        with db.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            contact = con.execute("SELECT * FROM contacts WHERE id=?", (row["contact_id"],)).fetchone()
            # Claim under one write lock: another sender cannot consume the same quota/interval.
            values = dict(con.execute('SELECT key,value FROM settings'))
            if not settings.sending_enabled or settings.sending_gaps() or values.get('paused', 'true') != 'false':
                return 'disabled'
            if now-float(values.get('imap_last_success', '0')) > 180 or values.get('imap_caught_up') != 'true':
                return 'inbox_stale'
            if now-float(values.get('last_send_attempt', '0')) < settings.min_send_interval_seconds:
                return 'rate_limited'
            reserved = con.execute("SELECT COUNT(*) FROM messages WHERE sent_at>=? OR state='sending'", (day_start,)).fetchone()[0]
            if reserved >= settings.daily_send_limit:
                return 'daily_limit'
            if contact['verification'] != 'safe':
                con.execute("UPDATE contacts SET status='hold' WHERE id=? AND status='active'", (contact['id'],))
                continue
            if not contact['verified_at'] or now-contact['verified_at'] > settings.verification_max_age_hours*3600:
                continue
            try:
                lead = con.execute("SELECT * FROM leads WHERE id=?", (contact["lead_id"],)).fetchone()
                assert_contact_ownership(Reader(con), dict(contact), dict(lead))
            except ValueError as exc:
                con.execute("UPDATE contacts SET status='hold' WHERE id=? AND status='active'", (contact["id"],))
                con.execute("INSERT INTO events(kind,contact_id,detail,created_at) VALUES(?,?,?,?)",
                            ("contact_ownership_hold", contact["id"], '{"reason":"Review current official-source inbox ownership before outreach"}', now))
                # Publication/ownership is part of the frozen approval context.
                # Preserve both the source-specific hold and the sequence audit.
                con.execute("INSERT INTO events(kind,contact_id,detail,created_at) VALUES(?,?,?,?)",
                            ('sequence_context_hold', contact['id'], __import__('json').dumps({'reason': str(exc)}), now))
                continue
            try:
                assert_outreach_open(con, contact["lead_id"])
            except ValueError:
                continue
            if contact["status"] != "active" or con.execute("SELECT 1 FROM suppression WHERE email=?", (contact["email"],)).fetchone():
                continue
            try:
                assert_approved(con, settings, dict(lead), dict(contact))
            except ValueError as exc:
                con.execute("UPDATE contacts SET status='hold' WHERE id=? AND status='active'", (contact['id'],))
                con.execute('INSERT INTO events(kind,contact_id,detail,created_at) VALUES(?,?,?,?)',
                            ('sequence_context_hold', contact['id'], __import__('json').dumps({'reason': str(exc)}), now))
                continue
            row = dict(con.execute('SELECT * FROM messages WHERE id=?', (row['id'],)).fetchone())
            if not row['due_at'] or row['due_at'] > now or not eligible_now(settings, lead['timezone'], now):
                continue
            changed = con.execute("UPDATE messages SET state='sending' WHERE id=? AND state='queued'", (row["id"],)).rowcount
            if not changed:
                continue
            contact = dict(contact)
            con.execute("INSERT INTO settings(key,value) VALUES('last_send_attempt',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(now),))
        previous = db.one("SELECT message_id FROM messages WHERE contact_id=? AND state='sent' ORDER BY step DESC LIMIT 1", (contact["id"],))
        try:
            try:
                message = build_message(settings, contact, row, previous)
            except Exception as exc:
                raise BeforeSubmissionError("MessageBuild" + type(exc).__name__) from exc
            sender(settings, message)
        except BeforeSubmissionError as exc:
            record_nonacceptance(db, row, "Not submitted: " + str(exc))
            db.set("paused", "true")
            db.event("send_not_submitted", {"message": row["id"], "error": str(exc),
                                            "sending_paused": True}, contact["id"])
            return "not_submitted"
        except smtplib.SMTPRecipientsRefused as exc:
            permanent = all(int(detail[0]) >= 500 for detail in exc.recipients.values())
            record_nonacceptance(db, row, 'SMTP recipient refused; server did not accept the message', permanent)
            if permanent:
                db.suppress(contact["email"], "SMTP permanent recipient rejection")
            else:
                db.execute("UPDATE contacts SET status='hold' WHERE id=? AND status='active'", (contact["id"],))
            return "failed"
        except (smtplib.SMTPSenderRefused, smtplib.SMTPDataError) as exc:
            # An explicit negative SMTP response proves non-acceptance. Do not label it uncertain.
            record_nonacceptance(db, row, f'SMTP rejection {exc.smtp_code}; not accepted')
            db.execute("UPDATE contacts SET status='hold' WHERE id=? AND status='active'", (contact["id"],))
            db.event("send_rejected", {"message": row["id"], "code": exc.smtp_code,
                                       "error": type(exc).__name__}, contact["id"])
            return "rejected"
        except Exception as exc:
            db.execute("UPDATE messages SET state='uncertain',error=? WHERE id=?", (type(exc).__name__, row["id"]))
            db.execute("UPDATE contacts SET status='hold' WHERE id=? AND status='active'", (contact["id"],))
            db.event("send_uncertain", {"message": row["id"], "error": type(exc).__name__}, contact["id"])
            return "uncertain"
        mark_sent(db, row, now, followups_enabled=settings.followups_enabled)
        return "sent"
    return "idle"


def record_nonacceptance(db, row, error, permanent=False):
    with db.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        contact = con.execute('SELECT * FROM contacts WHERE id=?', (row['contact_id'],)).fetchone()
        held = con.execute('SELECT cold_email_hold FROM sales WHERE lead_id=?', (contact['lead_id'],)).fetchone()
        stopped = contact['status'] not in {'active', 'hold'} or bool(held and held[0])
        con.execute('UPDATE messages SET state=?,error=? WHERE id=?',
                    ('failed' if permanent else 'cancelled' if stopped else 'queued', error, row['id']))


def mark_sent(db, row, now, *, followups_enabled=False):
    # 0, 3, 8, 14 days from the first actual send; delayed steps retain minimum spacing.
    gaps = [3, 5, 6]
    with db.connect() as con:
        con.execute("UPDATE messages SET state='sent',sent_at=?,error='' WHERE id=?", (now, row["id"]))
        if followups_enabled and row["step"] < 3:
            con.execute("UPDATE messages SET due_at=? WHERE contact_id=? AND step=? AND state='queued'",
                        (now + gaps[row["step"]] * 86400, row["contact_id"], row["step"] + 1))
        else:
            con.execute("UPDATE contacts SET status='closed' WHERE id=? AND status='active'", (row["contact_id"],))
    db.event("sent", {"message": row["id"], "step": row["step"]}, row["contact_id"])


def message_text(message):
    plain, html = [], []
    for part in message.walk():
        if part.get_content_type() in {"text/plain", "text/html"} and part.get_content_disposition() != "attachment":
            try:
                content = part.get_content()
                if part.get_content_type() == "text/plain":
                    plain.append(content)
                else:
                    soup = BeautifulSoup(content, "html.parser")
                    for node in soup.select("script,style,blockquote,.gmail_quote,.yahoo_quoted"):
                        node.decompose()
                    html.append(soup.get_text("\n", strip=True))
            except (LookupError, UnicodeError):
                pass
    return "\n".join(plain if any(text.strip() for text in plain) else html)[:12000]


def record_inbound(db, raw, external_id):
    if db.one("SELECT id FROM events WHERE external_id=?", (external_id,)):
        return
    msg = email.message_from_bytes(raw, policy=default)
    senders = [address.lower() for _, address in getaddresses(msg.get_all("From", []))]
    refs = re.findall(r"<[^<>\s]+>", " ".join(msg.get_all("In-Reply-To", []) + msg.get_all("References", [])))
    contact = None
    for ref in refs:
        contact = db.one("SELECT c.* FROM contacts c JOIN messages m ON m.contact_id=c.id WHERE m.message_id=?", (ref,))
        if contact:
            break
    if not contact:
        for sender in senders:
            contact = db.one("SELECT * FROM contacts WHERE email=?", (sender,))
            if contact:
                break
    # Parse DSN recipients and status. Only permanent failures suppress; delay notices pause.
    dsn_contact, dsn_permanent, dsn_positive = None, False, False
    if msg.get_content_type() == "multipart/report":
        for part in msg.walk():
            if part.get_content_type() == "message/delivery-status":
                for block in part.get_payload() or []:
                    recipient = str(block.get("Final-Recipient", "")).split(";")[-1].strip().lower()
                    matched = db.one("SELECT * FROM contacts WHERE email=?", (recipient,))
                    if matched:
                        dsn_contact = matched
                        dsn_permanent = str(block.get("Status", "")).startswith("5.")
                        dsn_positive = (str(block.get('Status', '')).startswith('2.')
                                        and str(block.get('Action', '')).lower() in {'delivered', 'relayed', 'expanded'})
                        break
    if dsn_contact:
        contact = dsn_contact
    if not contact:
        db.event("inbound_unmatched", {"uid": external_id}, external_id=external_id)
        return
    text = message_text(msg)
    # Ignore quoted original/footer when detecting opt-out language.
    first = re.split(r"(?im)^\s*(?:On .+wrote:|From:|>+|--\s*$)", text)[0][:2000]
    opted_out = bool(re.search(r"\b(unsubscribe|remove me|no thanks|not interested|stop emailing|do not contact)\b", first, re.I))
    automatic = str(msg.get("Auto-Submitted", "no")).lower() != "no" or bool(msg.get("X-Autoreply"))
    kind = "bounce" if dsn_permanent else "delivery_notice" if dsn_positive else "delivery_delay" if dsn_contact else "auto_reply" if automatic else "opt_out" if opted_out else "reply"
    with db.connect() as con:
        con.execute("BEGIN IMMEDIATE")
        if con.execute("SELECT 1 FROM events WHERE external_id=?", (external_id,)).fetchone():
            return
        if kind in {"bounce", "opt_out"}:
            db.suppress(contact["email"], kind, con)
        elif kind != 'delivery_notice':
            if kind in {"auto_reply", "delivery_delay"}:
                con.execute("UPDATE contacts SET status='hold' WHERE id=? AND status='active'", (contact["id"],))
            else:
                con.execute("UPDATE contacts SET status='replied' WHERE id=? AND status<>'suppressed'", (contact["id"],))
            con.execute("UPDATE messages SET state='cancelled' WHERE contact_id=? AND state='queued'", (contact["id"],))
        if kind in {"reply", "opt_out", "bounce"}:
            ensure_sales(con, contact["lead_id"])
            con.execute("UPDATE sales SET stage=CASE WHEN stage='new' THEN 'contacted' ELSE stage END,cold_email_hold=1,version=version+1,updated_at=? WHERE lead_id=?", (time.time(), contact["lead_id"]))
            if kind == "reply":
                con.execute("INSERT INTO tasks(lead_id,kind,title,due_at,created_at) VALUES(?,?,?,?,?)",
                            (contact["lead_id"], "followup", "Review reply and deliver the promised next step", time.time() + 86400, time.time()))
        con.execute("INSERT INTO events(external_id,kind,contact_id,detail,created_at) VALUES(?,?,?,?,?)",
                    (external_id, kind, contact["id"], __import__('json').dumps({"subject": str(msg.get('Subject', ''))[:250], "text": text}), time.time()))


def poll_inbox(db, settings):
    if not settings.imap_host or not settings.imap_user or not settings.imap_password:
        return False
    client = None
    try:
        client = imaplib.IMAP4_SSL(settings.imap_host, settings.imap_port, ssl_context=ssl.create_default_context(), timeout=30)
        client.login(settings.imap_user, settings.imap_password)
        typ, _ = client.select(settings.imap_folder, readonly=True)
        if typ != "OK":
            raise ValueError("Cannot select inbox")
        _, validity_raw = client.response("UIDVALIDITY")
        validity = (validity_raw[0] or b"").decode()
        if not validity:
            raise ValueError("Missing IMAP UIDVALIDITY")
        identity = hashlib.sha256(f"{settings.imap_host}|{settings.imap_user}|{settings.imap_folder}".encode()).hexdigest()[:20]
        if db.get("imap_identity") != identity:
            db.set("imap_last_uid", 0)
            db.set("imap_caught_up", "false")
            db.set("imap_identity", identity)
        old = db.get("imap_uidvalidity")
        if old and old != validity:
            db.set("imap_last_uid", 0)
            db.set("imap_caught_up", "false")
        db.set("imap_uidvalidity", validity)
        last = int(db.get("imap_last_uid", "0"))
        typ, data = client.uid("search", None, "UID", f"{last + 1}:*")
        if typ != "OK":
            raise ValueError("IMAP search failed")
        ids = sorted(int(x) for x in (data[0] or b"").split() if int(x) > last)
        for uid in ids[:100]:
            # Read a bounded prefix; headers/thread IDs and typical reply/DSN text fit here.
            # Large attachments must not fill the small VPS's memory.
            typ, fetched = client.uid("fetch", str(uid), "(BODY.PEEK[]<0.65536>)")
            if typ != "OK":
                raise ValueError("IMAP fetch failed")
            payloads = [item[1] for item in fetched if isinstance(item, tuple)]
            if not payloads:
                raise ValueError("Missing message payload")
            record_inbound(db, b"".join(payloads), f"imap:{identity}:{validity}:{uid}")
            db.set("imap_last_uid", uid)
        db.set("imap_caught_up", "true" if len(ids) <= 100 else "false")
        db.set("imap_last_success", time.time())
        db.set("imap_error", "")
        return True
    except Exception as exc:
        db.set("imap_caught_up", "false")
        db.set("imap_error", type(exc).__name__)
        return False
    finally:
        if client:
            try:
                client.logout()
            except Exception:
                pass
