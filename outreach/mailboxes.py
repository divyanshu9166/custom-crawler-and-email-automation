"""Sending mailboxes: the primary mailbox from Settings plus optional extra mailboxes.

Each mailbox is exposed as a Settings copy with its own sender/SMTP/IMAP fields and
daily/hourly limits, so the existing mail functions work per mailbox unchanged.

An alias shares a login with another mailbox: it sends From a different address but uses
that login's limits, minimum gap and inbox. A mailbox only sends once SPF/DKIM/DMARC is
confirmed for its sender domain, and an optional cap limits each domain's daily total.
"""
import time

FIELDS = ('label', 'sender_name', 'sender_email', 'smtp_host', 'smtp_port', 'smtp_security', 'smtp_user',
          'smtp_password', 'imap_host', 'imap_port', 'imap_user', 'imap_password', 'imap_folder',
          'daily_limit', 'hourly_limit', 'enabled', 'alias', 'domain_auth_confirmed')
SECRETS = {'smtp_password', 'imap_password'}
REQUIRED = ('sender_email', 'smtp_host', 'smtp_user', 'smtp_password', 'imap_host', 'imap_user', 'imap_password')
LOCAL = {'label', 'enabled', 'daily_limit', 'hourly_limit', 'alias', 'domain_auth_confirmed'}
CATCH_ALL_WINDOW = 14 * 86400
CATCH_ALL_MIN_SAMPLE, CATCH_ALL_MAX_BOUNCE = 10, 0.05
ACTIVE = "('sending','sent','uncertain')"


def domain_of(email):
    return email.rsplit('@', 1)[-1].strip().lower() if '@' in (email or '') else ''


def primary(settings):
    return {'id': 'primary', 'label': 'Primary mailbox', 'enabled': True, 'alias': False,
            'domain_auth_confirmed': settings.domain_auth_confirmed,
            'daily_limit': settings.daily_send_limit, 'hourly_limit': settings.hourly_send_limit,
            **{k: getattr(settings, k) for k in FIELDS if k not in LOCAL}}


def configured(box):
    return all(box.get(k) for k in REQUIRED)


def login_key(settings, box):
    from .mail import mailbox_key
    return mailbox_key(settings.model_copy(update={'smtp_user': box.get('smtp_user', ''),
                                                   'sender_email': box.get('sender_email', '')}))


def confirmed_domains(settings):
    """Domains whose SPF/DKIM/DMARC the operator has confirmed on any mailbox."""
    boxes = [primary(settings), *settings.extra_mailboxes]
    return {domain_of(b.get('sender_email')) for b in boxes if b.get('domain_auth_confirmed') and b.get('sender_email')}


def views(settings, *, include_disabled=False):
    """Configured mailboxes in a stable order, primary first."""
    from .mail import mailbox_key
    boxes = [b for b in [primary(settings), *settings.extra_mailboxes] if configured(b)]
    owners = {}
    for box in boxes:
        if not box.get('alias'):
            owners.setdefault(login_key(settings, box), box)
    domains = confirmed_domains(settings)
    result = []
    for box in boxes:
        if not (box.get('enabled', True) or include_disabled):
            continue
        key = login_key(settings, box)
        owner = owners.get(key)
        if not owner or (box.get('alias') and (owner is box or not (owner.get('enabled', True) or include_disabled))):
            continue  # An alias needs an existing, enabled mailbox with the same login.
        limits = owner if box.get('alias') else box
        update = {k: box[k] for k in FIELDS if k in box and k not in LOCAL}
        update['sender_name'] = box.get('sender_name') or settings.sender_name
        update.update(daily_send_limit=int(limits['daily_limit']), hourly_send_limit=int(limits['hourly_limit']))
        view = settings.model_copy(update=update)
        result.append({'id': box['id'], 'label': box.get('label') or box['sender_email'], 'enabled': box.get('enabled', True),
                       'key': mailbox_key(view), 'sender': box['sender_email'].strip().lower(),
                       'domain': domain_of(box['sender_email']), 'alias': bool(box.get('alias')),
                       'auth_confirmed': domain_of(box['sender_email']) in domains,
                       'prefix': '' if owner['id'] == 'primary' else f"mailbox:{owner['id']}:",
                       'daily_limit': int(limits['daily_limit']), 'hourly_limit': int(limits['hourly_limit']), 'view': view})
    return result


def domain_usage(con, domain, since):
    """Sends from any address on this domain (aliases and separate mailboxes together)."""
    return con.execute(f"""SELECT COUNT(*) FROM send_attempts WHERE started_at>=? AND outcome IN {ACTIVE}
        AND lower(CASE WHEN sender<>'' THEN sender ELSE mailbox END) LIKE ?""", (since, '%@' + domain)).fetchone()[0]


def sender_usage(con, sender, since):
    return con.execute(f"SELECT COUNT(*) FROM send_attempts WHERE sender=? AND started_at>=? AND outcome IN {ACTIVE}",
                       (sender, since)).fetchone()[0]


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
    """Mailbox and domain lists for the dashboard: no passwords, plus usage when a database is given."""
    from .mail import mailbox_usage
    now = time.time()
    domains = confirmed_domains(settings)
    live = {v['id']: v for v in views(settings, include_disabled=True)}
    rows = []
    for box in [primary(settings), *settings.extra_mailboxes]:
        item = {k: box.get(k) for k in FIELDS if k not in SECRETS}
        view = live.get(box['id'])
        item.update(id=box['id'], primary=box['id'] == 'primary', configured=configured(box),
                    domain=domain_of(box.get('sender_email')), domain_confirmed=domain_of(box.get('sender_email')) in domains,
                    smtp_password_configured=bool(box.get('smtp_password')),
                    imap_password_configured=bool(box.get('imap_password')),
                    sending=bool(view and view['enabled'] and view['auth_confirmed']))
        if view:
            item.update(daily_limit=view['daily_limit'], hourly_limit=view['hourly_limit'])
        if db is not None and view:
            with db.connect() as con:
                item.update(used_24h=mailbox_usage(con, view['key'], now - 86400), used_1h=mailbox_usage(con, view['key'], now - 3600),
                            sent_from_address_24h=sender_usage(con, view['sender'], now - 86400),
                            catch_all_24h=catch_all_usage(con, view['key'], now - 86400),
                            catch_all_cap=catch_all_cap(settings, view))
            item.update(inbox_current=db.get(view['prefix'] + 'imap_caught_up') == 'true'
                        and now - float(db.get(view['prefix'] + 'imap_last_success', '0') or 0) <= 180,
                        inbox_error=db.get(view['prefix'] + 'imap_error'))
        rows.append(item)
    return rows


def public_domains(settings, db=None):
    """One row per sender domain: authentication, optional daily cap and usage."""
    now = time.time()
    rows = {}
    for box in [primary(settings), *settings.extra_mailboxes]:
        domain = domain_of(box.get('sender_email'))
        if domain:
            rows.setdefault(domain, {'domain': domain, 'mailboxes': 0, 'daily_cap': settings.domain_daily_caps.get(domain, 0),
                                     'auth_confirmed': domain in confirmed_domains(settings)})['mailboxes'] += 1
    if db is not None:
        with db.connect() as con:
            for row in rows.values():
                row['used_24h'] = domain_usage(con, row['domain'], now - 86400)
    return list(rows.values())
