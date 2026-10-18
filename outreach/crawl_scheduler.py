"""Bounded, checkpoint-bound research continuation in the existing durable job."""
import json
import time

from .crawl_state import CHECKPOINT_WORK, continuation_wait
from .web import crawl_url


def reschedule(db, settings, job):
    if job['kind'] != 'research' or not settings.crawl_auto_continue:
        return False
    payload = json.loads(job['payload'])
    lid = payload.get('lead_id')
    with db.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        lead = con.execute('SELECT * FROM leads WHERE id=?', (lid,)).fetchone()
        if not lead or lead['lead_kind'] != 'website' or lead['status'] == 'qualified':
            return False
        if con.execute("SELECT 1 FROM contacts WHERE lead_id=? AND status IN ('active','replied','hold','closed')", (lid,)).fetchone():
            return False
        if con.execute('SELECT 1 FROM sales WHERE lead_id=? AND cold_email_hold=1', (lid,)).fetchone():
            return False
        row = con.execute('SELECT * FROM crawls WHERE lead_id=? ORDER BY id DESC LIMIT 1', (lid,)).fetchone()
        if not row or not time.time()-30*86400 <= row['created_at'] <= time.time()+60:
            return False
        if payload.get('crawl_id') and payload['crawl_id'] != row['id']:
            return False
        report = json.loads(row['report'])
        cp = report.get('checkpoint', {})
        if cp.get('website') != crawl_url(lead['website']):
            return False
        if not any(cp.get(k) for k in CHECKPOINT_WORK):
            if payload.get('auto_pass'):
                report['automation'] = {'state': 'finished', 'passes': payload['auto_pass']+1}
                con.execute('UPDATE crawls SET report=? WHERE id=?', (json.dumps(report), row['id']))
            return False
        passes = payload.get('auto_pass', 0)+1
        if passes >= settings.crawl_auto_max_passes or report.get('attempted', 0) >= settings.crawl_auto_max_pages:
            report['automation'] = {'state': 'budget_exhausted', 'passes': passes,
                                    'max_passes': settings.crawl_auto_max_passes,
                                    'max_attempts': settings.crawl_auto_max_pages}
            con.execute('UPDATE crawls SET report=? WHERE id=?', (json.dumps(report), row['id']))
            return False
        # A manual queued fresh/continuation request supersedes this automatic
        # cycle; two research jobs must not alternately invalidate each other.
        if con.execute("SELECT 1 FROM jobs WHERE id<>? AND kind='research' AND state IN ('pending','running') AND json_extract(payload,'$.lead_id')=?",
                       (job['id'], lid)).fetchone():
            return False
        due = time.time()+max(1, continuation_wait(cp))
        next_payload = {**payload, 'continuation': True, 'crawl_id': row['id'], 'auto_pass': passes}
        report['automation'] = {'state': 'scheduled', 'next_at': due, 'pass': passes+1,
                                'max_passes': settings.crawl_auto_max_passes,
                                'max_attempts': settings.crawl_auto_max_pages}
        con.execute('UPDATE crawls SET report=? WHERE id=?', (json.dumps(report), row['id']))
        con.execute("UPDATE jobs SET state='pending',payload=?,due_at=?,error='',attempts=0 WHERE id=?",
                    (json.dumps(next_payload, sort_keys=True), due, job['id']))
        return True


def stop_reviewed_cycle(db, payload):
    state = {'state': 'stopped_after_review', 'passes': payload.get('auto_pass', 0)}
    db.execute("UPDATE crawls SET report=json_set(report,'$.automation',json(?)) WHERE id=? AND id=(SELECT id FROM crawls WHERE lead_id=? ORDER BY id DESC LIMIT 1)",
               (json.dumps(state), payload.get('crawl_id'), payload['lead_id']))


def resumable_restart(db, job):
    """Recovered interrupted jobs use current evidence rather than refresh it."""
    payload = json.loads(job['payload'])
    if payload.get('continuation') or not job['attempts']:
        return payload
    row = db.one('SELECT * FROM crawls WHERE lead_id=? ORDER BY id DESC LIMIT 1', (payload.get('lead_id'),))
    if row:
        report = json.loads(row['report'])
        cp = report.get('checkpoint', {})
        if report.get('status') == 'interrupted' and cp.get('website') and any(cp.get(k) for k in CHECKPOINT_WORK):
            payload.update(continuation=True, crawl_id=row['id'])
            db.execute('UPDATE jobs SET payload=? WHERE id=?', (json.dumps(payload, sort_keys=True), job['id']))
    return payload


def schedule_final_audits(db, settings, payload):
    """Do expensive supplementary work once after the bounded research cycle."""
    from .research import assert_contact_ownership
    lead = db.one('SELECT * FROM leads WHERE id=?', (payload['lead_id'],))
    if not lead or lead['lead_kind'] != 'website' or lead['status'] != 'review':
        return
    row = db.one('SELECT * FROM crawls WHERE lead_id=? ORDER BY id DESC LIMIT 1', (lead['id'],))
    if not row or payload.get('crawl_id') and payload['crawl_id'] != row['id']:
        return
    if not db.one('SELECT 1 FROM evidence WHERE lead_id=? AND fetched_at>=?', (lead['id'], row['created_at'])):
        return
    if db.one("SELECT 1 FROM jobs WHERE kind='research' AND state IN ('pending','running') AND json_extract(payload,'$.lead_id')=?", (lead['id'],)):
        return
    contacts = db.all('SELECT * FROM contacts WHERE lead_id=?', (lead['id'],))
    if any(c['status'] in {'active','replied','hold','closed'} for c in contacts):
        return
    if settings.browser_enabled and settings.auto_visual_audit:
        db.enqueue('screenshot', {'lead_id': lead['id']})
    if settings.auto_performance_audit and settings.pagespeed_api_key:
        db.enqueue('performance', {'lead_id': lead['id']})
    if settings.auto_professional_research:
        db.enqueue('professional_research',{'lead_id':lead['id']})
    if settings.auto_contact_research:
        for contact in contacts:
            try:
                assert_contact_ownership(db, contact, lead)
                return
            except ValueError:
                pass
        db.enqueue('contact_research', {'lead_id': lead['id']})
