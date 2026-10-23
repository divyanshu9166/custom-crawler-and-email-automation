"""Named campaign reporting and bounded bulk controls. Never approves or sends mail."""
import csv
import io
import json
import sqlite3
import time
from datetime import datetime, timedelta, timezone


# Aggregate each relation before joining: multiple contacts/messages must not
# multiply prospect counts. Delivery outcomes are current contact states;
# SMTP acceptances remain cumulative, including subsequently deleted prospects.
METRICS = '''WITH contact_totals AS (
 SELECT lead_id,COUNT(*) contacts,
 SUM(delivery_state='BOUNCED') bounced,SUM(delivery_state='REPLIED') replied,
 SUM(delivery_state='UNSUBSCRIBED') unsubscribed,
 SUM(verification='safe') verified FROM contacts GROUP BY lead_id
), message_totals AS (
 SELECT c.lead_id,COUNT(*) messages,SUM(m.sent_at IS NOT NULL) sent,
 SUM(m.state='queued') queued,SUM(m.state='draft') drafts,
 SUM(m.state='failed') failed,SUM(m.state='uncertain') uncertain,
 SUM(m.state='sending') sending FROM messages m JOIN contacts c ON c.id=m.contact_id GROUP BY c.lead_id
), facts AS (
 SELECT l.*,g.name campaign_name,COALESCE(c.contacts,0) contacts,COALESCE(c.bounced,0) bounced,
 COALESCE(c.replied,0) replied,COALESCE(c.unsubscribed,0) unsubscribed,
 COALESCE(c.verified,0) verified,COALESCE(m.sent,0) sent,COALESCE(m.queued,0) queued,
 COALESCE(m.drafts,0) drafts,COALESCE(m.failed,0) failed,
 COALESCE(m.uncertain,0) uncertain,COALESCE(m.sending,0) sending,
 (SELECT group_concat(email,', ') FROM contacts WHERE lead_id=l.id) emails,
 (SELECT MAX(sent_at) FROM messages JOIN contacts ON contacts.id=messages.contact_id WHERE contacts.lead_id=l.id) last_sent_at
 FROM leads l LEFT JOIN campaign_groups g ON g.id=l.campaign_id LEFT JOIN contact_totals c ON c.lead_id=l.id LEFT JOIN message_totals m ON m.lead_id=l.id
) '''
COUNTERS = ('contacts', 'sent', 'bounced', 'replied', 'unsubscribed', 'queued', 'drafts', 'failed', 'uncertain', 'sending')


def assert_target(db, campaign_id, goal):
    if campaign_id is not None and not db.one('SELECT 1 FROM campaign_groups WHERE id=? AND goal=?', (campaign_id, goal)):
        raise ValueError('Choose a campaign matching the selected business goal A/B')


def summary(db):
    now = time.time()
    today = datetime.fromtimestamp(now, timezone.utc).date()
    days = [(today - timedelta(days=n)).isoformat() for n in range(13, -1, -1)]
    since = datetime.combine(today - timedelta(days=13), datetime.min.time(), timezone.utc).timestamp()
    with db.connect() as con:
        con.execute('BEGIN')
        fields = ','.join(f'COALESCE(SUM(f.{name}),0) AS {name}' for name in COUNTERS)
        rows = [dict(r) for r in con.execute(METRICS + f'''SELECT g.*,
            COUNT(f.id) prospects,COALESCE(SUM(f.deleted_at IS NULL AND f.id IS NOT NULL),0) active_prospects,
            COALESCE(SUM(f.deleted_at IS NOT NULL),0) deleted,{fields}
            FROM campaign_groups g LEFT JOIN facts f ON f.campaign_id=g.id GROUP BY g.id ORDER BY g.id''')]
        jobs = {r['campaign_id']: dict(r) for r in con.execute('''SELECT COALESCE(json_extract(j.payload,'$.campaign_id'),
            (SELECT campaign_id FROM leads WHERE id=json_extract(j.payload,'$.lead_id')),
            (SELECT l.campaign_id FROM contacts c JOIN leads l ON l.id=c.lead_id WHERE c.id=json_extract(j.payload,'$.contact_id')),
            (SELECT id FROM campaign_groups WHERE goal=json_extract(j.payload,'$.campaign') AND is_default=1)) campaign_id,
            SUM(j.state='pending') pending_jobs,SUM(j.state='running') running_jobs,SUM(j.state='failed') failed_jobs
            FROM jobs j GROUP BY campaign_id''')}
        for row in rows:
            for key in ('pending_jobs', 'running_jobs', 'failed_jobs'):
                row[key] = jobs.get(row['id'], {}).get(key, 0)
        # Use recorded timestamps, never inferred delivery or fabricated demo data.
        accepted = list(con.execute('''SELECT l.campaign_id,date(m.sent_at,'unixepoch') day,COUNT(*) n
            FROM messages m JOIN contacts c ON c.id=m.contact_id JOIN leads l ON l.id=c.lead_id
            WHERE m.sent_at>=? AND m.sent_at<=? GROUP BY l.campaign_id,day''', (since, now)))
        outcomes = list(con.execute('''SELECT l.campaign_id,date(e.created_at,'unixepoch') day,e.kind,COUNT(*) n
            FROM events e JOIN contacts c ON c.id=e.contact_id JOIN leads l ON l.id=c.lead_id
            WHERE e.kind IN ('reply','bounce','opt_out') AND e.created_at>=? AND e.created_at<=?
            GROUP BY l.campaign_id,day,e.kind''', (since, now)))
        recent = [dict(r) for r in con.execute('''SELECT e.id,e.kind,e.created_at,l.id lead_id,
            l.company,l.campaign_id,g.name campaign_name FROM events e
            JOIN contacts c ON c.id=e.contact_id JOIN leads l ON l.id=c.lead_id
            JOIN campaign_groups g ON g.id=l.campaign_id
            WHERE e.kind IN ('sent','reply','bounce','opt_out','send_uncertain','send_rejected')
            AND e.created_at<=? ORDER BY e.created_at DESC,e.id DESC LIMIT 6''', (now,))]
        campaign_activity = {}
        for item in con.execute('''WITH ranked AS (
            SELECT e.id,e.kind,e.created_at,l.id lead_id,l.company,l.campaign_id,
            ROW_NUMBER() OVER (PARTITION BY l.campaign_id ORDER BY e.created_at DESC,e.id DESC) position
            FROM events e JOIN contacts c ON c.id=e.contact_id JOIN leads l ON l.id=c.lead_id
            WHERE e.kind IN ('sent','reply','bounce','opt_out','send_uncertain','send_rejected')
            AND e.created_at<=?) SELECT id,kind,created_at,lead_id,company,campaign_id FROM ranked
            WHERE position<=6 ORDER BY created_at DESC,id DESC''', (now,)):
            campaign_activity.setdefault(item['campaign_id'], []).append(dict(item))
        def trend(campaign_id=None):
            points = {day: {'date': day, 'sent': 0, 'replies': 0, 'bounces': 0, 'unsubscribes': 0} for day in days}
            for item in accepted:
                if campaign_id is None or item['campaign_id'] == campaign_id:
                    points[item['day']]['sent'] += item['n']
            for item in outcomes:
                if campaign_id is None or item['campaign_id'] == campaign_id:
                    key = {'reply': 'replies', 'bounce': 'bounces', 'opt_out': 'unsubscribes'}[item['kind']]
                    points[item['day']][key] += item['n']
            return list(points.values())
        for row in rows:
            row['trend'] = trend(row['id'])
            # Bound each campaign independently so a busy campaign cannot hide another.
            row['activity'] = campaign_activity.get(row['id'], [])
        totals = {key: sum(r[key] for r in rows) for key in (*COUNTERS, 'prospects', 'active_prospects', 'deleted')}
        for key in ('pending_jobs', 'running_jobs', 'failed_jobs'):
            totals[key] = sum(r[key] for r in rows)
        return {'campaigns': rows, 'totals': totals,
                'generated_at': now,
                'analytics': {'days': 14, 'timezone': 'UTC', 'series': trend(), 'activity': recent[:6]},
                'note': 'Sent counts SMTP-accepted messages, not inbox placement. Bounce/reply/unsubscribe count current contact outcomes. Deleted is a separate prospect flag; history stays included.'}


def where(campaign_id=None, state='all', market='', search='', deleted='active'):
    clauses, args = [], []
    if campaign_id:
        clauses.append('campaign_id=?')
        args.append(campaign_id)
    if deleted != 'all':
        clauses.append('deleted_at IS ' + ('NOT NULL' if deleted == 'deleted' else 'NULL'))
    if market:
        clauses.append('country=?')
        args.append(market)
    if search.strip():
        clauses.append("(company LIKE ? ESCAPE '\\' OR domain LIKE ? ESCAPE '\\' OR emails LIKE ? ESCAPE '\\')")
        term = '%' + search.strip().replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_') + '%'
        args.extend([term] * 3)
    filters = {'sent': 'sent>0', 'bounced': 'bounced>0', 'replied': 'replied>0', 'unsubscribed': 'unsubscribed>0',
               'queued': 'queued>0', 'drafts': 'drafts>0', 'attention': "failed>0 OR uncertain>0 OR status='research_failed'",
               'no_contact': 'contacts=0'}
    if state != 'all':
        if state not in filters:
            raise ValueError('Unsupported campaign outcome filter')
        clauses.append('(' + filters[state] + ')')
    return (' WHERE ' + ' AND '.join(clauses) if clauses else ''), args


def prospects(db, *, campaign_id=None, state='all', market='', search='', deleted='active', limit=50, offset=0):
    clause, args = where(campaign_id, state, market, search, deleted)
    with db.connect() as con:
        con.execute('BEGIN')
        total = con.execute(METRICS + 'SELECT COUNT(*) FROM facts' + clause, args).fetchone()[0]
        rows = [dict(r) for r in con.execute(METRICS + '''SELECT id,company,domain,campaign,campaign_id,campaign_name,country,status,
            deleted_at,delete_reason,emails,last_sent_at,contacts,sent,bounced,replied,unsubscribed,queued,drafts,failed,uncertain,sending
            FROM facts''' + clause + ' ORDER BY id DESC LIMIT ? OFFSET ?', [*args, limit, offset])]
        return {'rows': rows, 'total': total, 'limit': limit, 'offset': offset}


def create(db, name, goal):
    name = name.strip()
    if len(name) < 3 or len(name) > 100 or goal not in {'A', 'B'}:
        raise ValueError('Use a campaign name of 3–100 characters and goal A or B')
    now = time.time()
    try:
        return db.execute('INSERT INTO campaign_groups(name,goal,created_at,updated_at) VALUES(?,?,?,?)', (name, goal, now, now))
    except sqlite3.IntegrityError as exc:
        raise ValueError('A campaign with this name already exists') from exc


def set_state(db, campaign_id, state):
    if state not in {'active', 'paused'}:
        raise ValueError('Choose active or paused')
    with db.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        if not con.execute('SELECT 1 FROM campaign_groups WHERE id=?', (campaign_id,)).fetchone():
            raise ValueError('Campaign not found')
        con.execute('UPDATE campaign_groups SET state=?,updated_at=? WHERE id=?', (state, time.time(), campaign_id))
        con.execute('INSERT INTO events(kind,detail,created_at) VALUES(?,?,?)',
                    ('campaign_state_changed', json.dumps({'campaign_id': campaign_id, 'state': state}), time.time()))
    return {'state': state, 'note': 'Global sending controls, limits and individual approval still apply. Already submitted mail cannot be recalled.'}


def bulk(db, settings, lead_ids, action, reason='', campaign_id=None):
    ids = list(dict.fromkeys(lead_ids))
    if not ids or len(ids) > 200:
        raise ValueError('Select between 1 and 200 prospects')
    if action not in {'assign', 'delete', 'restore', 'prepare', 'approve'}:
        raise ValueError('Unsupported bulk action')
    if action == 'delete' and len(reason.strip()) < 3:
        raise ValueError('Give a deletion reason')
    results = []
    # Each row is independently committed and reported; a single blocked contact
    # cannot silently roll back an entire operator batch.
    for lead_id in ids:
        try:
            with db.connect() as con:
                con.execute('BEGIN IMMEDIATE')
                lead = con.execute('SELECT * FROM leads WHERE id=?', (lead_id,)).fetchone()
                if not lead:
                    raise ValueError('Prospect not found')
                if action == 'assign':
                    target = con.execute('SELECT * FROM campaign_groups WHERE id=?', (campaign_id,)).fetchone()
                    if not target or target['goal'] != lead['campaign']:
                        raise ValueError('Target campaign must have the same business goal A/B')
                    if lead['deleted_at']:
                        raise ValueError('Restore the prospect before moving it')
                    if con.execute("""SELECT 1 FROM contacts c WHERE c.lead_id=? AND
                        (c.reviewed_at IS NOT NULL OR c.delivery_state<>'' OR c.status<>'new'
                         OR EXISTS(SELECT 1 FROM messages m WHERE m.contact_id=c.id AND (m.state<>'draft' OR m.sent_at IS NOT NULL)))""", (lead_id,)).fetchone():
                        raise ValueError('Outreach history or approval freezes campaign attribution; this prospect cannot move')
                    if con.execute("SELECT 1 FROM events e JOIN contacts c ON c.id=e.contact_id WHERE c.lead_id=? AND e.kind='sequence_approved'", (lead_id,)).fetchone():
                        raise ValueError('Previous approval freezes campaign attribution')
                    con.execute('UPDATE leads SET campaign_id=? WHERE id=?', (campaign_id, lead_id))
                elif action == 'delete':
                    con.execute('UPDATE leads SET deleted_at=COALESCE(deleted_at,?),delete_reason=? WHERE id=?', (time.time(), reason.strip(), lead_id))
                    con.execute("UPDATE contacts SET status='deleted' WHERE lead_id=? AND status IN ('new','active','hold')", (lead_id,))
                    con.execute("UPDATE messages SET state='cancelled' WHERE contact_id IN (SELECT id FROM contacts WHERE lead_id=?) AND state IN ('draft','queued')", (lead_id,))
                    con.execute("""UPDATE jobs SET state='cancelled',error='Prospect deleted; pending work cancelled' WHERE state='pending'
                        AND (json_extract(payload,'$.lead_id')=? OR json_extract(payload,'$.contact_id') IN (SELECT id FROM contacts WHERE lead_id=?))""", (lead_id, lead_id))
                elif action == 'restore':
                    con.execute("UPDATE leads SET deleted_at=NULL,delete_reason='' WHERE id=?", (lead_id,))
                    con.execute("UPDATE contacts SET status='hold' WHERE lead_id=? AND status='deleted'", (lead_id,))
                else:
                    if lead['deleted_at']:
                        raise ValueError('Deleted prospects cannot prepare or approve email')
                if action not in {'prepare', 'approve'}:
                    con.execute('INSERT INTO events(kind,detail,created_at) VALUES(?,?,?)',
                                ('campaign_bulk_' + action, json.dumps({'lead_id': lead_id, 'campaign_id': campaign_id, 'reason': reason}), time.time()))
            if action == 'approve':
                from .campaigns import approve_ready
                contacts = db.all("""SELECT DISTINCT c.id FROM contacts c JOIN messages m ON m.contact_id=c.id
                    WHERE c.lead_id=? AND c.status='new' AND m.state='draft' ORDER BY c.id""", (lead_id,))
                if not contacts:
                    raise ValueError('No prepared email to approve')
                approve_ready(db, settings, contacts[0]['id'])
                results.append({'lead_id': lead_id, 'ok': True, 'contact_id': contacts[0]['id']})
            elif action == 'prepare':
                from .preparation import queue
                job_id = queue(db, settings, lead_id)
                results.append({'lead_id': lead_id, 'ok': True, 'job_id': job_id})
            else:
                results.append({'lead_id': lead_id, 'ok': True})
        except ValueError as exc:
            results.append({'lead_id': lead_id, 'ok': False, 'reason': str(exc)})
    note = ('Approved emails are queued; they send only while Sending is ON and resumed, within each mailbox limit.'
            if action == 'approve' else 'No emails sent. Deletion preserves history and suppression; restore never resumes sending automatically.')
    return {'results': results, 'succeeded': sum(r['ok'] for r in results), 'note': note}


def export_csv(db, **filters):
    clause, args = where(**filters)
    # Export all matches using an independent snapshot and cursor; never the
    # dashboard's paginated subset. Each chunk is bounded for the small VPS.
    columns = ['id', 'company', 'campaign_id', 'campaign_name', 'campaign', 'country', 'emails', 'status', 'sent', 'bounced', 'replied',
               'unsubscribed', 'queued', 'failed', 'uncertain', 'deleted_at', 'delete_reason']
    with db.connect() as con:
        con.execute('BEGIN')
        cursor = con.execute(METRICS + 'SELECT ' + ','.join(columns) + ' FROM facts' + clause + ' ORDER BY id DESC', args)
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(columns)
        yield out.getvalue()
        while rows := cursor.fetchmany(200):
            out.seek(0)
            out.truncate(0)
            for row in rows:
                writer.writerow(["'" + str(value) if str(value or '').startswith(('=', '+', '-', '@', '\t', '\r')) else value for value in row])
            yield out.getvalue()
