"""Sending mailboxes: the primary mailbox from Settings plus optional extra mailboxes.

Each mailbox is exposed as a Settings copy with its own sender/SMTP/IMAP fields and
daily/hourly limits, so the existing mail functions work per mailbox unchanged.
"""
import time

FIELDS = ('label', 'sender_name', 'sender_email', 'smtp_host', 'smtp_port', 'smtp_security', 'smtp_user',
          'smtp_password', 'imap_host', 'imap_port', 'imap_user', 'imap_password', 'imap_folder',
          'daily_limit', 'hourly_limit', 'enabled')
SECRETS = {'smtp_password', 'imap_password'}
REQUIRED = ('sender_email', 'smtp_host', 'smtp_user', 'smtp_password', 'imap_host', 'imap_user', 'imap_password')
CATCH_ALL_WINDOW = 14 * 86400
CATCH_ALL_MIN_SAMPLE, CATCH_ALL_MAX_BOUNCE = 10, 0.05


def primary(settings):
    return {'id': 'primary', 'label': 'Primary mailbox', 'enabled': True,
            'daily_limit': settings.daily_send_limit, 'hourly_limit': settings.hourly_send_limit,
            **{k: getattr(settings, k) for k in FIELDS if k not in {'label', 'enabled', 'daily_limit', 'hourly_limit'}}}


def configured(box):
    return all(box.get(k) for k in REQUIRED)


def views(settings, *, include_disabled=False):
    """Configured mailboxes in a stable order, primary first."""
    from .mail import mailbox_key
    result = []
    for box in [primary(settings), *settings.extra_mailboxes]:
        if not configured(box) or not (box.get('enabled', True) or include_disabled):
            continue
        update = {k: box[k] for k in FIELDS if k in box and k not in {'label', 'enabled', 'daily_limit', 'hourly_limit'}}
        update['sender_name'] = box.get('sender_name') or settings.sender_name
        update.update(daily_send_limit=int(box['daily_limit']), hourly_send_limit=int(box['hourly_limit']))
        view = settings.model_copy(update=update)
        result.append({'id': box['id'], 'label': box.get('label') or box['sender_email'], 'enabled': box.get('enabled', True),
                       'key': mailbox_key(view), 'prefix': '' if box['id'] == 'primary' else f"mailbox:{box['id']}:",
                       'daily_limit': int(box['daily_limit']), 'hourly_limit': int(box['hourly_limit']), 'view': view})
    return result


def catch_all_cap(settings, box):
    """Separate per-mailbox daily budget for catch-all recipients; 0 when disabled."""
    return max(1, box['daily_limit'] * settings.catch_all_share // 100) if settings.catch_all_share else 0


def catch_all_usage(con, key, since):
    return con.execute("""SELECT COUNT(*) FROM send_attempts a JOIN messages m ON m.id=a.message_id
        JOIN contacts c ON c.id=m.contact_id WHERE a.mailbox=? AND a.started_at>=?
        AND a.outcome IN ('sending','sent','uncertain') AND c.verification='catch_all'""", (key, since)).fetchone()[0]


def catch_all_open(con, settings, now=None):
    """Catch-all sending pauses itself when recent catch-all sends bounce too often."""
    if not settings.catch_all_share:
        return False
    since = (time.time() if now is None else now) - CATCH_ALL_WINDOW
    sent, bounced = con.execute("""SELECT COUNT(DISTINCT c.id), COUNT(DISTINCT CASE WHEN c.delivery_state='BOUNCED' THEN c.id END)
        FROM messages m JOIN contacts c ON c.id=m.contact_id
        WHERE m.sent_at>=? AND c.verification='catch_all'""", (since,)).fetchone()
    return not (sent >= CATCH_ALL_MIN_SAMPLE and bounced / sent > CATCH_ALL_MAX_BOUNCE)


def sendable(settings, verdict):
    """Mailbox verdicts that may be approved and sent."""
    return verdict == 'safe' or (verdict == 'catch_all' and settings.catch_all_share > 0)


def public(settings, db=None):
    """Mailbox list for the dashboard: no passwords, plus recent usage when a database is given."""
    from .mail import mailbox_key
    now = time.time()
    rows = []
    for box in [primary(settings), *settings.extra_mailboxes]:
        item = {k: box.get(k) for k in FIELDS if k not in SECRETS}
        item.update(id=box['id'], primary=box['id'] == 'primary', configured=configured(box),
                    smtp_password_configured=bool(box.get('smtp_password')),
                    imap_password_configured=bool(box.get('imap_password')))
        if db is not None and configured(box):
            key = mailbox_key(settings.model_copy(update={'smtp_user': box['smtp_user'], 'sender_email': box['sender_email']}))
            prefix = '' if box['id'] == 'primary' else f"mailbox:{box['id']}:"
            from .mail import mailbox_usage
            with db.connect() as con:
                item.update(used_24h=mailbox_usage(con, key, now - 86400), used_1h=mailbox_usage(con, key, now - 3600),
                            catch_all_24h=catch_all_usage(con, key, now - 86400),
                            catch_all_cap=catch_all_cap(settings, {'daily_limit': int(box['daily_limit'])}))
            item.update(inbox_current=db.get(prefix + 'imap_caught_up') == 'true'
                        and now - float(db.get(prefix + 'imap_last_success', '0') or 0) <= 180,
                        inbox_error=db.get(prefix + 'imap_error'))
        rows.append(item)
    return rows
