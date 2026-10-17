"""Bounded live compatibility smoke, not a vendor or unrestricted-coverage benchmark."""
import asyncio
import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from outreach.config import Settings
from outreach.db import DB
from outreach.research import add_lead, assert_contact_ownership, current_evidence, research_lead


def fingerprint(db):
    tables = ('leads', 'contacts', 'messages', 'crawls', 'evidence', 'suppression', 'jobs')
    rows = {table: db.all('SELECT * FROM '+table+' ORDER BY rowid') for table in tables}
    return hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()


async def main():
    normal = DB(Settings().database)
    assert normal.get('paused') == 'true'
    assert normal.one("SELECT COUNT(*) n FROM jobs WHERE state IN ('pending','running')")['n'] == 0
    before = fingerprint(normal)
    root = Path('data/crawler-recovery-live')/time.strftime('%Y%m%d-%H%M%S')
    root.mkdir(parents=True, exist_ok=False)
    settings = Settings(_env_file=None, data_dir=root, worker_enabled=False, sending_enabled=False,
                        auto_visual_audit=False, auto_contact_research=False, crawl_max_pages=6)
    db = DB(settings.database)
    results = []
    async def capture(company, website, market):
        lid = add_lead(db, company, website, 'B', website)
        started = time.monotonic()
        error = ''
        try:
            await asyncio.wait_for(research_lead(db, settings, lid), 120)
        except Exception as exc:
            error = type(exc).__name__
        lead = db.one('SELECT * FROM leads WHERE id=?', (lid,))
        row = db.one('SELECT report FROM crawls WHERE lead_id=? ORDER BY id DESC LIMIT 1', (lid,))
        report = json.loads(row['report']) if row else {}
        publication_checks = []
        for contact in db.all('SELECT * FROM contacts WHERE lead_id=?', (lid,)):
            try:
                assert_contact_ownership(db, contact, lead)
                publication_checks.append(True)
            except ValueError:
                publication_checks.append(False)
        result = {'company': company, 'website': website, 'market_sample': market,
                  'seconds': round(time.monotonic()-started, 2), 'error': error,
                  'saved_pages': len(current_evidence(db, lid)), 'crawl_status': report.get('status'),
                  'stored_contacts': len(publication_checks), 'current_publication_proofs': sum(publication_checks),
                  'remaining': report.get('remaining'), 'retry_pending': report.get('retry_pending', 0),
                  'document_reuses': sum(bool(p.get('document_reused')) for p in report.get('pages', []))}
        results.append(result)
        print(json.dumps(result), flush=True)
    await asyncio.gather(capture('Bouquets For Days', 'https://www.bouquetsfordays.co.uk/', 'UK'),
                         capture('Portland Coffee Roasters', 'https://www.portlandcoffeeroasters.com/', 'US'))
    assert not db.one('SELECT 1 FROM messages')
    assert not db.one('SELECT 1 FROM contacts WHERE verified_at IS NOT NULL')
    assert not db.one("SELECT 1 FROM events WHERE kind='verification'")
    assert normal.get('paused') == 'true' and fingerprint(normal) == before
    output = {'checked_at': time.time(), 'results': results, 'page_budget': settings.crawl_max_pages,
              'render_mode': settings.crawl_render_mode, 'deadline_per_site_seconds': 120,
              'email_probes': 0, 'external_mail_sent': 0, 'main_operational_database_unchanged': True,
              'scope': 'Two known official sites, post-change smoke; not a vendor or market-coverage benchmark'}
    path = root/'report.json'
    path.write_text(json.dumps(output, indent=2)+'\n', encoding='utf-8')
    Path('data/crawler-recovery-live-latest.json').write_text(json.dumps({'report': str(path.resolve())}), encoding='utf-8')
    print('Report: '+str(path.resolve()), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
