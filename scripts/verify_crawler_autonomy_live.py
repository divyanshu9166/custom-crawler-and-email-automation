"""Multi-segment unattended research acceptance; no mailbox or verification lane."""
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from outreach.config import Settings
from outreach.crawl_resources import AdaptiveConcurrency
from outreach.db import DB
from outreach.research import add_lead, assert_contact_ownership, current_evidence
from outreach.worker import job_loop, monitor_resources
from verify_crawler_recovery_live import fingerprint


async def main():
    normal = DB(Settings().database)
    assert normal.get('paused') == 'true'
    assert normal.one("SELECT COUNT(*) n FROM jobs WHERE state IN ('pending','running')")['n'] == 0
    before = fingerprint(normal)
    root = Path('data/crawler-autonomy-live')/time.strftime('%Y%m%d-%H%M%S')
    root.mkdir(parents=True, exist_ok=False)
    settings = Settings(_env_file=None, data_dir=root, worker_enabled=False, sending_enabled=False,
        auto_visual_audit=False, auto_contact_research=False, crawl_max_pages=5,
        crawl_auto_max_passes=3, crawl_auto_max_pages=15, crawl_concurrency=2, job_timeout_seconds=180)
    db = DB(settings.database)
    samples = [('Bouquets For Days', 'https://www.bouquetsfordays.co.uk/', 'UK', 'Flowers'),
               ('Portland Coffee Roasters', 'https://www.portlandcoffeeroasters.com/', 'US', 'Coffee'),
               ('Dental Clinic London', 'https://www.dentalclinic.london/', 'UK', 'Dental services'),
               ('SmartRoof', 'https://smartroof.com/', 'US', 'Roofing services')]
    jobs = []
    for company, website, market, segment in samples:
        lid = add_lead(db, company, website, 'B' if segment in {'Flowers','Coffee'} else 'A', website)
        jobs.append((lid, db.enqueue('research', {'lead_id': lid}), market, segment))
    stop = asyncio.Event()
    gate = AdaptiveConcurrency(settings, db)
    workers = [asyncio.create_task(job_loop(db, settings, stop, {'research'}, admission=gate)) for _ in range(2)]
    workers.append(asyncio.create_task(monitor_resources(gate, stop)))
    started = time.monotonic()
    progress = []
    try:
        while time.monotonic()-started < 360:
            states = [db.one('SELECT state FROM jobs WHERE id=?', (jid,))['state'] for _, jid, _, _ in jobs]
            if all(s in {'done','failed'} for s in states):
                break
            if not progress or time.monotonic()-started-progress[-1]['elapsed'] >= 30:
                entry = {'elapsed': round(time.monotonic()-started, 1), 'states': states,
                         'saved_pages': db.one('SELECT COUNT(*) n FROM evidence')['n'],
                         'runtime': json.loads(db.get('crawler_runtime', '{}'))}
                progress.append(entry)
                print(json.dumps(entry), flush=True)
            await asyncio.sleep(1)
    finally:
        stop.set()
        await asyncio.gather(*workers)
    results = []
    for lid, jid, market, segment in jobs:
        lead = db.one('SELECT * FROM leads WHERE id=?', (lid,))
        row = db.one('SELECT report FROM crawls WHERE lead_id=? ORDER BY id DESC LIMIT 1', (lid,))
        report = json.loads(row['report']) if row else {}
        job = db.one('SELECT * FROM jobs WHERE id=?', (jid,))
        source_proofs = 0
        contacts = db.all('SELECT * FROM contacts WHERE lead_id=?', (lid,))
        for contact in contacts:
            try:
                assert_contact_ownership(db, contact, lead)
                source_proofs += 1
            except ValueError:
                pass
        candidates = db.one("SELECT COUNT(DISTINCT json_extract(detail,'$.email')) n FROM events WHERE kind='contact_candidate_found' AND json_extract(detail,'$.lead_id')=?", (lid,))['n']
        result = {'company': lead['company'], 'website': lead['website'], 'market_sample': market, 'segment': segment,
            'job_state': job['state'], 'job_error': job['error'], 'saved_pages': len(current_evidence(db, lid)),
            'crawl_status': report.get('status', 'not_run'), 'attempted': report.get('attempted', 0),
            'stored_contacts': len(contacts), 'current_publication_proofs': source_proofs,
            'other_domain_review_candidates': candidates, 'automation': report.get('automation', {}),
            'resume_passes': len(report.get('resume_history', [])), 'remaining': report.get('remaining'),
            'sitemap_retries': report.get('sitemap_retry_pending', 0), 'throttle': report.get('throttle', {})}
        results.append(result)
        print(json.dumps(result), flush=True)
    assert not db.one('SELECT 1 FROM messages')
    assert not db.one('SELECT 1 FROM contacts WHERE verified_at IS NOT NULL')
    assert not db.one("SELECT 1 FROM events WHERE kind='verification'")
    assert normal.get('paused') == 'true' and fingerprint(normal) == before
    output = {'checked_at': time.time(), 'results': results, 'progress': progress,
        'elapsed_seconds': round(time.monotonic()-started, 2), 'sending_disabled': True,
        'verification_lane_started': False, 'mail_lane_started': False, 'main_operational_database_unchanged': True,
        'limits': {'pages_per_pass': 5, 'max_passes': 3, 'max_page_attempts': 15, 'concurrency_ceiling': 2,
                   'overall_diagnostic_seconds': 360, 'render_mode': 'always'},
        'scope': 'Four known official sites; automatic continuation/resource admission acceptance, not vendor parity or discovery consistency'}
    path = root/'report.json'
    path.write_text(json.dumps(output, indent=2)+'\n', encoding='utf-8')
    Path('data/crawler-autonomy-live-latest.json').write_text(json.dumps({'report': str(path.resolve())}), encoding='utf-8')
    print('Report: '+str(path.resolve()), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
