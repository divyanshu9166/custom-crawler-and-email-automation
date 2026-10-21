"""Read-only status for one explicitly tracked background job."""
import json
import re
import time

from .preparation import SOURCE_JOBS


def source_jobs(db, lead_ids):
    """One current job per source kind, preferring unfinished work over history."""
    if not lead_ids:
        return {}
    rows = db.all(f"""SELECT * FROM (
        SELECT id,kind,state,error,due_at,started_at,created_at,
          (CASE WHEN json_valid(payload) THEN json_extract(payload,'$.lead_id') END) lead_id,
          ROW_NUMBER() OVER (PARTITION BY (CASE WHEN json_valid(payload) THEN json_extract(payload,'$.lead_id') END),kind
            ORDER BY CASE state WHEN 'running' THEN 0 WHEN 'pending' THEN 1 ELSE 2 END,id DESC) position
        FROM jobs WHERE kind IN ({','.join('?' for _ in SOURCE_JOBS)})
          AND (CASE WHEN json_valid(payload) THEN json_extract(payload,'$.lead_id') END) IN ({','.join('?' for _ in lead_ids)})
        ) WHERE position=1 ORDER BY CASE state WHEN 'running' THEN 0 WHEN 'pending' THEN 1 ELSE 2 END,
          CASE kind WHEN 'research' THEN 0 ELSE 1 END,id DESC""", (*SOURCE_JOBS, *lead_ids))
    grouped = {}
    for row in rows:
        row.pop('position')
        grouped.setdefault(row['lead_id'], []).append(row)
    return grouped


def source_job(rows):
    return next((r for r in rows if r['state'] in {'pending', 'running'}),
                next((r for r in rows if r['kind'] == 'research'), None))


def lead_activity(db, settings, lead):
    """Compact saved progress for the selected workspace; no provider calls or writes."""
    rows = source_jobs(db, [lead['id']]).get(lead['id'], [])
    active = [r for r in rows if r['state'] in {'pending', 'running'}]
    capture = next((r for r in rows if r['kind'] == 'screenshot'), None)
    research = next((r for r in rows if r['kind'] == 'research'), None)
    event = db.one("SELECT detail,created_at FROM events WHERE kind='screenshot' AND json_extract(detail,'$.lead_id')=? ORDER BY id DESC LIMIT 1", (lead['id'],))
    files, captured_at, report_state = {}, None, 'not_run'
    if event:
        report = json.loads(event['detail'])
        captured_at = event['created_at']
        crawl = db.one('SELECT created_at FROM crawls WHERE lead_id=? ORDER BY id DESC LIMIT 1', (lead['id'],))
        report_state = 'complete' if report.get('complete') is True and not report.get('issues') else 'partial'
        if not 0 <= time.time()-captured_at <= 7*86400 or (crawl and min(captured_at, report.get('requested_at', captured_at)) < crawl['created_at']):
            report_state = 'stale'
        from .web import crawl_url
        try:
            if crawl_url(report.get('url', '')) != crawl_url(lead['website']):
                report_state = 'target_unverified'
        except ValueError:
            report_state = 'target_unverified'
        for device, name in report.get('files', {}).items():
            if (device in {'desktop', 'mobile'} and isinstance(name, str)
                    and re.fullmatch(rf"lead-{lead['id']}-\d+-[a-f0-9]{{6}}-(?:mobile|desktop)\.png", name)
                    and (settings.data_dir/'screenshots'/name).is_file()):
                files[device] = name
        if not files:
            report_state = 'unavailable'
    state = report_state
    if lead.get('lead_kind') == 'profile' or not lead.get('website'):
        state = 'not_applicable'
    elif capture and capture['state'] in {'pending', 'running'}:
        state = capture['state']
    elif research and research['state'] in {'pending', 'running'} and settings.browser_enabled and settings.auto_visual_audit:
        state = 'waiting_for_research'
    elif capture and capture['state'] in {'failed', 'cancelled'}:
        state = capture['state']
    elif not files and not (settings.browser_enabled and settings.auto_visual_audit):
        state = 'disabled'
    count = db.one('SELECT COUNT(*) n FROM evidence WHERE lead_id=?', (lead['id'],))['n']
    contacts = db.one('SELECT COUNT(*) n FROM contacts WHERE lead_id=?', (lead['id'],))['n']
    return {'job': source_job(rows), 'active_jobs': active, 'worker_enabled': settings.worker_enabled,
            'auto_prepare_enabled': settings.auto_prepare_enabled, 'lead_status': lead['status'],
            'saved_pages': count, 'contacts': contacts,
            'screenshots': {'state': state, 'report_state': report_state, 'files': files,
                            'captured_at': captured_at, 'error': capture['error'] if capture else ''}}


def job_status(db, settings, job_id):
    row = db.one('SELECT * FROM jobs WHERE id=?', (job_id,))
    if not row:
        return None
    payload = json.loads(row['payload'])
    result = {key: row[key] for key in ('id', 'kind', 'state', 'attempts', 'due_at', 'started_at', 'created_at', 'error')}
    result.update(worker_enabled=settings.worker_enabled, lead_id=payload.get('lead_id'),
                  query=payload.get('query', '')[:160])
    if row['kind'] == 'discover':
        event = db.one("""SELECT kind,detail FROM events
            WHERE kind IN ('discovery_started','discovery_progress','discovery')
            AND (CASE WHEN json_valid(detail) THEN json_extract(detail,'$.job_id') END)=?
            ORDER BY id DESC LIMIT 1""", (job_id,))
        if event:
            detail = json.loads(event['detail'])
            result['progress'] = {k: detail[k] for k in ('stage', 'company', 'retained', 'candidate_domains', 'signals') if k in detail}
            if event['kind'] == 'discovery':
                result['saved_prospects'] = len(set(detail.get('lead_ids', [])))
                result['note'] = 'Search finished. Saved prospects may still have detailed research or audits queued.'
    return result
