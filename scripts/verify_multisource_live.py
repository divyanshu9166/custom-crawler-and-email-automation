"""Real public discovery and company-contact recovery in an isolated no-send database."""
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from outreach.config import Settings
from outreach.db import DB
from outreach.discovery import prospect_candidates
from outreach.contact_recovery import research_contacts
from outreach.professionals import research_professionals
from outreach.research import add_lead, fresh_evidence, assert_contact_ownership
from verify_crawler_recovery_live import fingerprint


async def main():
    normal = DB(Settings().database)
    assert normal.get('paused') == 'true'
    assert not normal.one("SELECT 1 FROM jobs WHERE state IN ('pending','running')")
    before = fingerprint(normal)
    folder = Path('data/multisource-live') / time.strftime('%Y%m%d-%H%M%S')
    folder.mkdir(parents=True, exist_ok=False)
    settings = Settings(_env_file=None, data_dir=folder, worker_enabled=False, sending_enabled=False,
        browser_enabled=False, crawl_render_mode='never', crawl_max_sitemaps=0, contact_research_max_pages=2,
        platform_browser_enabled=False, auto_contact_research=False, auto_professional_research=False,
        auto_visual_audit=False, professional_max_profiles=2, serpapi_key='', openai_api_key='', draft_api_key='')
    db = DB(settings.database)
    output = {'checked_at': time.time(), 'discovery': [], 'company_checks': [],
              'scope': 'Four market queries and two previously known companies. Index candidates are unqualified. Not a vendor-parity or exhaustive platform benchmark.'}
    for query in ['UK Bristol independent florists', 'US Portland coffee roasters',
                  'UK London dental clinics', 'US Austin roofing companies']:
        rows, discovery = await prospect_candidates(settings.model_copy(update={'discovery_platforms': ''}),
            query, 'UK' if query.startswith('UK') else 'US', 5)
        item = {'query': query, 'candidate_count': len(rows), 'candidate_urls': [r['url'] for r in rows],
                'engine_reports': discovery['engine_reports'], 'skipped': discovery['skipped'],
                'errors': discovery['errors'], 'signals': discovery['signals']}
        output['discovery'].append(item)
        print(json.dumps(item), flush=True)
    for real_id in [12, 11]:
        real = normal.one('SELECT * FROM leads WHERE id=?', (real_id,))
        assert real and real['lead_kind'] == 'website'
        pages = fresh_evidence(normal, real_id)
        assert pages
        lid = add_lead(db, real['company'], real['website'], real['campaign'], real['source_url'])
        db.execute('UPDATE leads SET country=?,research_notes=? WHERE id=?', (real['country'], real['research_notes'], lid))
        for page in pages:
            db.execute('INSERT INTO evidence(lead_id,url,title,text,sha256,fetched_at) VALUES(?,?,?,?,?,?)',
                (lid, page['url'], page['title'], page['text'], page['sha256'], page['fetched_at']))
        item = {'company': real['company'], 'website': real['website'], 'reused_prior_company_pages': len(pages)}
        try:
            report = await asyncio.wait_for(research_contacts(db, settings, lid), 180)
            # Do not export newly captured personal/company email strings in the
            # shareable report. Raw evidence stays in the isolated local DB.
            item['contact_recovery'] = {k: report[k] for k in ['state', 'pages_saved', 'queries', 'url_index', 'seed_sources']}
        except Exception as exc:
            item['contact_recovery'] = {'state': 'incomplete', 'error_type': type(exc).__name__}
        proof = 0
        for contact in db.all('SELECT * FROM contacts WHERE lead_id=?', (lid,)):
            assert_contact_ownership(db, contact, db.one('SELECT * FROM leads WHERE id=?', (lid,)))
            proof += 1
        item['currently_sourced_company_contacts'] = proof
        if real_id == 12:
            try:
                report = await asyncio.wait_for(research_professionals(db, settings, lid), 240)
                item['professional_research'] = report
            except Exception as exc:
                item['professional_research'] = {'state': 'incomplete', 'error_type': type(exc).__name__}
        output['company_checks'].append(item)
        print(json.dumps(item), flush=True)
    assert not db.one('SELECT 1 FROM messages')
    assert not db.one('SELECT 1 FROM contacts WHERE verified_at IS NOT NULL')
    assert not db.one("SELECT 1 FROM events WHERE kind='verification'")
    assert normal.get('paused') == 'true' and fingerprint(normal) == before
    output.update(email_probes=0, external_messages_sent=0, paid_keys_used=False,
                  main_operational_database_unchanged=True, finished_at=time.time())
    path = folder / 'report.json'
    path.write_text(json.dumps(output, indent=2) + '\n', encoding='utf-8')
    Path('data/multisource-live-latest.json').write_text(json.dumps({'report': str(path.resolve())}), encoding='utf-8')
    print('Report: ' + str(path.resolve()), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
