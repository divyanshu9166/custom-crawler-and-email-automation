"""Read-only status for one explicitly tracked background job."""
import json


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
