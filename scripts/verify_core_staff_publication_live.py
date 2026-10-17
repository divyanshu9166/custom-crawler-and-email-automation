"""Known official-source control through real website/professional research.

Uses a separate database with no worker. Verification jobs may be queued, but
are never executed. No operational recipient imports, probes or messages.
"""
import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from outreach.config import Settings
from outreach.db import DB
from outreach.discovery import official_root
from outreach.professionals import research_professionals
from outreach.research import add_lead, company_publication, research_lead
from outreach.web import domain_of
from verify_crawler_recovery_live import fingerprint


async def main(url):
    official_root(url)
    normal = Settings()
    main_db = DB(normal.database)
    assert not normal.sending_enabled and main_db.get('paused') == 'true'
    assert not main_db.one("SELECT 1 FROM jobs WHERE state IN ('pending','running')")
    before = fingerprint(main_db)
    folder = Path('data/core-staff-publication-control') / time.strftime('%Y%m%d-%H%M%S')
    folder.mkdir(parents=True, exist_ok=False)
    settings = normal.model_copy(update={'data_dir': folder, 'worker_enabled': False,
        'sending_enabled': False, 'platform_browser_enabled': False, 'crawl_max_pages': 1,
        'crawl_max_depth': 0, 'crawl_max_sitemaps': 0, 'auto_visual_audit': False,
        'auto_contact_research': False, 'auto_professional_research': False,
        'professional_max_profiles': 1, 'professional_max_queries': 1,
        'professional_refresh_official_links': False, 'commoncrawl_hints_enabled': False})
    db = DB(settings.database)
    lid = add_lead(db, domain_of(url), url, 'A', url)
    await asyncio.wait_for(research_lead(db, settings, lid), 180)
    lead = db.one('SELECT * FROM leads WHERE id=?', (lid,))
    contacts = db.all('SELECT * FROM contacts')
    report = {'scope': 'One known operator-supplied official page, current real research_lead and automatic professional research. Not fresh prospect discovery, buyer approval or native LinkedIn extraction.',
        'source_url': url, 'contacts': [{k: v for k, v in c.items() if k in
            {'email', 'name', 'role', 'verification', 'status', 'source_url'}} for c in contacts],
        'saved_publication_checks': [{'email': c['email'], 'current_proof': bool(company_publication(db, c, lead))} for c in contacts],
        'crawl': json.loads(db.one('SELECT report FROM crawls ORDER BY id DESC LIMIT 1')['report']),
        'evidence': db.all('SELECT url,title,sha256,text FROM evidence'),
        'isolated_verify_jobs': len(db.all("SELECT id FROM jobs WHERE kind='verify'"))}
    (folder/'report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    report['professional_report'] = await asyncio.wait_for(research_professionals(db, settings, lid), 90)
    assert fingerprint(main_db) == before and main_db.get('paused') == 'true'
    assert not db.all('SELECT * FROM messages')
    report.update(main_database_unchanged=True, operational_contacts_imported=0,
        recipient_probes=0, external_messages_sent=0, finished_at=time.time())
    (folder/'report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    Path('data/core-staff-publication-control-latest.json').write_text(
        json.dumps({'report': str((folder/'report.json').resolve())}), encoding='utf-8')
    print(json.dumps({'isolated_contacts': len(contacts), 'named_contacts': sum(bool(c['name']) for c in contacts),
        'current_proofs': sum(p['current_proof'] for p in report['saved_publication_checks']),
        'native_capture_state': report['professional_report']['state'],
        'operational_contacts_imported': 0, 'recipient_probes': 0, 'external_messages_sent': 0}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='https://mlaarchitects.co.uk/team/')
    asyncio.run(main(parser.parse_args().url))
