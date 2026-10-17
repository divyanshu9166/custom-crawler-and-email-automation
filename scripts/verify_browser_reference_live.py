"""Replay an actual browser business reference into isolated website research.

Input must be an operator-observed BrowserReferenceInput JSON file, not a
fabricated platform capture. This script never controls a platform browser.
"""
import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from outreach.app import BrowserReferenceInput
from outreach.browser_references import save_reference
from outreach.config import Settings
from outreach.db import DB
from outreach.research import current_evidence, research_lead
from verify_crawler_recovery_live import fingerprint


async def main(input_path):
    value = BrowserReferenceInput.model_validate_json(input_path.read_text(encoding='utf-8')).model_dump()
    normal = DB(Settings().database)
    assert normal.get('paused') == 'true'
    assert not normal.one("SELECT 1 FROM jobs WHERE state IN ('pending','running')")
    before = fingerprint(normal)
    root = Path('data/browser-reference-live')/time.strftime('%Y%m%d-%H%M%S')
    root.mkdir(parents=True, exist_ok=False)
    settings = Settings(_env_file=None, data_dir=root, worker_enabled=False, sending_enabled=False,
                        auto_visual_audit=False, auto_contact_research=False, crawl_max_pages=6,
                        search_provider='searxng', serpapi_key='', openai_api_key='', openai_model='',
                        draft_api_key='', draft_model='')
    db = DB(settings.database)
    db.set('paused', 'true')
    result = save_reference(db, **value)
    job = db.claim(kinds={'research'})
    assert job and job['id'] == result['job_id']
    error = ''
    try:
        await asyncio.wait_for(research_lead(db, settings, result['id'],
                                          seed_urls=json.loads(job['payload'])['seed_urls']), 120)
    except Exception as exc:
        error = type(exc).__name__
    db.execute('UPDATE jobs SET state=?,error=? WHERE id=?',
               ('failed' if error else 'done', error, job['id']))
    crawl = db.one('SELECT report FROM crawls ORDER BY id DESC LIMIT 1')
    report = {'reference': value, 'server_profile_fetched': False, 'review_required': True,
              'saved_pages': len(current_evidence(db, result['id'])),
              'contacts': db.one('SELECT COUNT(*) n FROM contacts')['n'],
              'other_domain_candidates': db.one("SELECT COUNT(*) n FROM events WHERE kind='contact_candidate_found'")['n'],
              'crawl': json.loads(crawl['report']) if crawl else None, 'research_error': error,
              'email_probes_performed': 0, 'messages_sent': 0,
              'pending_verification_jobs_not_run': db.one("SELECT COUNT(*) n FROM jobs WHERE kind='verify' AND state='pending'")['n'],
              'main_database_unchanged': fingerprint(normal) == before}
    assert report['main_database_unchanged']
    assert not db.one('SELECT 1 FROM messages')
    destination = root/'report.json'
    destination.write_text(json.dumps(report, indent=2), encoding='utf-8')
    Path('data/browser-reference-live-latest.json').write_text(json.dumps({'report': str(destination)}), encoding='utf-8')
    print(json.dumps({k: v for k, v in report.items() if k not in {'reference', 'crawl'}}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('input', type=Path)
    asyncio.run(main(parser.parse_args().input))
