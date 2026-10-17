"""Run real search/worker research in the normal dashboard; never approve or send."""
import hashlib
import json
import argparse
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from outreach.config import Settings
from outreach.db import DB
from outreach.research import fresh_evidence, contact_candidates


SEGMENTS = [
    ('A', 'UK', 'dental practice Leeds UK book appointment'),
    ('A', 'US', 'roofing contractor Raleigh North Carolina contact'),
    ('B', 'UK', 'independent skincare brand UK shop'),
    ('B', 'US', 'coffee roaster Portland Oregon shop'),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--resume', type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    settings = Settings()
    db = DB(settings.database)
    output = args.resume or root/'data/no-send-pilot'/time.strftime('%Y%m%d-%H%M%S')
    if not args.resume:
        output.mkdir(parents=True, exist_ok=False)
    before_leads = {row['id'] for row in db.all('SELECT id FROM leads')}
    before_job = db.one('SELECT COALESCE(MAX(id),0) n FROM jobs')['n']
    private = [root/'.env', settings.data_dir/'workspace-settings.json']
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in private if p.exists()}
    if args.resume:
        baseline = json.loads((output/'baseline.json').read_text())
        before_leads, before_job, hashes = set(baseline['lead_ids']), baseline['last_job'], baseline['private_hashes']
    else:
        (output/'baseline.json').write_text(json.dumps({'lead_ids': sorted(before_leads), 'last_job': before_job, 'private_hashes': hashes}, indent=2), encoding='utf-8')
    with httpx.Client(base_url='http://127.0.0.1:8000', headers={'Authorization': 'Bearer '+settings.api_token}, timeout=15) as client:
        status = client.get('/api/status').raise_for_status().json()
        assert status['sending_enabled'] is False and status['demo'] is False
        client.post('/api/pause').raise_for_status()
        assert client.get('/api/status').json()['paused'] is True
        discovery = json.loads((output/'submitted.json').read_text()) if args.resume else []
        if not args.resume:
            for campaign, market, query in SEGMENTS:
                value = {'campaign': campaign, 'country_hint': market, 'query': query, 'limit': 1}
                response = client.post('/api/discover', json=value).raise_for_status().json()
                discovery.append({**value, 'job_id': response['job_id']})
        (output/'submitted.json').write_text(json.dumps(discovery, indent=2)+'\n', encoding='utf-8')
        (root/'data/no-send-pilot-latest.json').write_text(json.dumps({'directory': str(output), 'submitted': discovery}, indent=2)+'\n', encoding='utf-8')
        print(json.dumps({'directory': str(output), 'submitted_jobs': [r['job_id'] for r in discovery], 'sending_disabled': True}), flush=True)
        started, last_print = time.time(), 0
        while True:
            status = client.get('/api/status').raise_for_status().json()
            assert status['sending_enabled'] is False and status['paused'] is True
            jobs = db.all('SELECT id,kind,state,attempts,error,payload FROM jobs WHERE id>? ORDER BY id', (before_job,))
            new_leads = db.all('SELECT id,company,status,lead_kind,campaign FROM leads WHERE id NOT IN ('+
                               ','.join('?' for _ in before_leads)+')', tuple(before_leads)) if before_leads else db.all('SELECT id,company,status,lead_kind,campaign FROM leads')
            progress = {'elapsed_seconds': round(time.time()-started),
                        'jobs': [{k:j[k] for k in ['id','kind','state','attempts','error']} for j in jobs],
                        'new_leads': new_leads,
                        'pages_saved': db.one('SELECT COUNT(*) n FROM evidence')['n'],
                        'contacts': db.one('SELECT COUNT(*) n FROM contacts')['n']}
            (output/'progress.json').write_text(json.dumps(progress, indent=2)+'\n', encoding='utf-8')
            if time.time()-last_print >= 20:
                print(json.dumps(progress), flush=True)
                last_print = time.time()
            if jobs and all(j['state'] in {'done', 'failed'} for j in jobs):
                break
            if time.time()-started > 2400:
                progress['audit_wait_limit_reached'] = True
                print('Pilot monitor reached wait limit; inspect persisted job progress rather than treating a running crawl as complete.', flush=True)
                break
            time.sleep(3)
        assert not db.one("SELECT 1 FROM messages WHERE state IN ('sent','sending','uncertain')")
        assert {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in private if p.exists()} == hashes
        leads = []
        for lead in db.all('SELECT * FROM leads ORDER BY id'):
            if lead['id'] in before_leads:
                continue
            crawl = db.one('SELECT report,created_at FROM crawls WHERE lead_id=? ORDER BY id DESC LIMIT 1', (lead['id'],))
            pages = fresh_evidence(db, lead['id'])
            leads.append({'id': lead['id'], 'company': lead['company'], 'website': lead['website'],
                          'campaign': lead['campaign'], 'source_url': lead['source_url'], 'lead_kind': lead['lead_kind'],
                          'website_status': lead['website_status'], 'status': lead['status'],
                          'findings': json.loads(lead['findings']), 'research_notes': lead['research_notes'],
                          'crawl': json.loads(crawl['report']) if crawl else None,
                          'pages': [{k:p[k] for k in ['id','url','title','sha256','fetched_at']} for p in pages],
                          'contacts': db.all('SELECT id,email,name,role,status,source_url,verification FROM contacts WHERE lead_id=?', (lead['id'],)),
                          'published_candidates': contact_candidates(db, lead['id'])})
        result = {'live': True, 'fixtures': False, 'normal_dashboard': True, 'checked_at': time.time(),
                  'external_messages_sent': 0, 'sending_enabled': False, 'paused': True,
                  'private_configuration_unchanged': True, 'segments': discovery, 'progress': progress,
                  'new_leads': leads, 'configured_pages_per_site': settings.crawl_max_pages,
                  'render_mode': settings.crawl_render_mode,
                  'note': 'Published email extraction does not establish inbox existence. Country/buyer/offer qualification must use saved evidence; no approval or external sending occurs.'}
        (output/'report.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
        (root/'data/no-send-pilot-latest.json').write_text(json.dumps({'report': str(output/'report.json'), 'directory': str(output)}, indent=2)+'\n', encoding='utf-8')
        print(json.dumps({'report': str(output/'report.json'), 'new_leads': len(leads),
                          'current_pages': sum(len(row['pages']) for row in leads),
                          'extracted_contacts': sum(len(row['contacts']) for row in leads),
                          'external_messages_sent': 0}), flush=True)


if __name__ == '__main__':
    main()
