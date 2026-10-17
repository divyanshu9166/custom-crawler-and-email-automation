"""Exercise real official-page recovery with a controlled unavailable search index.

Uses isolated copies of existing candidate evidence. This is neither new lead
discovery nor buyer/country qualification; no verifier, sender or worker runs.
"""
import asyncio
import hashlib
import json
from pathlib import Path
import sys
import time
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from outreach.config import Settings
from outreach.contact_recovery import research_contacts
from outreach.db import DB
from outreach.research import add_lead, fresh_evidence, assert_contact_ownership


def counters(db):
    return {table: db.one(f'SELECT COUNT(*) n FROM {table}')['n']
            for table in ('leads', 'contacts', 'evidence', 'crawls', 'messages', 'jobs')}


async def main():
    root = Path(__file__).resolve().parents[1]
    output = root/'data/contact-fallback-live'/time.strftime('%Y%m%d-%H%M%S')
    output.mkdir(parents=True, exist_ok=False)
    hashes = {name: hashlib.sha256((root/name).read_bytes()).hexdigest()
              for name in ('outreach/contact_recovery.py', 'outreach/web.py', 'outreach/research.py')}
    normal = DB(Settings().database)
    before = counters(normal)
    assert normal.get('paused') == 'true' and before['messages'] == 0
    settings = Settings(_env_file=None, data_dir=output, worker_enabled=False, sending_enabled=False,
                        auto_contact_research=False, auto_visual_audit=False)
    db = DB(settings.database)
    results = []
    async def index_unavailable(*_, **__):
        return []
    for domain in ('skindays.com', 'smartroof.com'):
        source = normal.one('SELECT * FROM leads WHERE domain=?', (domain,))
        if not source:
            raise ValueError('Expected existing pilot candidate missing')
        lid = add_lead(db, source['company'], source['website'], source['campaign'], source['source_url'])
        row = normal.one('SELECT report,created_at FROM crawls WHERE lead_id=? ORDER BY id DESC LIMIT 1', (source['id'],))
        db.execute('INSERT INTO crawls(lead_id,report,created_at) VALUES(?,?,?)', (lid, row['report'], row['created_at']))
        for page in fresh_evidence(normal, source['id']):
            db.execute('INSERT INTO evidence(lead_id,url,title,text,sha256,fetched_at) VALUES(?,?,?,?,?,?)',
                       (lid, page['url'], page['title'], page['text'], page['sha256'], page['fetched_at']))
        print(json.dumps({'domain': domain, 'stage': 'real_official_capture',
                          'index_condition': 'controlled_empty_result', 'sending_enabled': False}), flush=True)
        started = time.time()
        with patch('outreach.providers.discover', index_unavailable):
            try:
                report = await asyncio.wait_for(research_contacts(db, settings, lid), 240)
            except TimeoutError:
                report = {'state': 'held', 'error_type': 'TimeoutError', 'pages_saved': None}
        contacts = db.all('SELECT * FROM contacts WHERE lead_id=?', (lid,))
        lead = db.one('SELECT * FROM leads WHERE id=?', (lid,))
        for contact in contacts:
            try:
                assert_contact_ownership(db, contact, lead)
                contact['source_eligible'] = True
                contact['source_issue'] = ''
            except ValueError as exc:
                contact['source_eligible'] = False
                contact['source_issue'] = str(exc)
        contacts = [{k: c[k] for k in ('email','source_url','verification','source_eligible','source_issue')} for c in contacts]
        result = {'domain': domain, 'campaign': source['campaign'], 'seconds': round(time.time()-started, 3),
                  'report': report, 'published_contacts': contacts,
                  'new_to_isolated_database_only': True, 'new_discovery': False,
                  'mailbox_verified': False, 'buyer_relevance_reviewed': False,
                  'refreshed_sources': [{'url': p['url'], 'sha256': p['sha256']} for p in fresh_evidence(db, lid)
                                        if p['fetched_at'] >= started]}
        results.append(result)
        (output/'results.json').write_text(json.dumps(results, indent=2)+'\n', encoding='utf-8')
        print(json.dumps({'domain': domain, 'state': report['state'], 'pages_saved': report['pages_saved'],
                          'published_contact_count': len(contacts)}), flush=True)
    assert counters(normal) == before and normal.get('paused') == 'true'
    assert db.one('SELECT COUNT(*) n FROM messages')['n'] == 0
    assert not db.one("SELECT 1 FROM jobs WHERE kind!='verify'")
    result = {'checked_at': time.time(), 'live_official_page_requests': True,
              'search_index_condition': 'Controlled empty results; no real discovery queries executed',
              'scope': 'Existing candidate recovery on real websites in isolation; not new prospect yield or qualified buyer acceptance',
              'results': results, 'normal_database_counters_unchanged': True,
              'sending_enabled': False, 'external_messages_sent': 0, 'verification_jobs_executed': 0,
              'source_hashes': hashes,
              'limits': ['Published contacts are candidates, not confirmed decision-makers.',
                         'No private social platform email access established.',
                         'Reacher backend remains unavailable; no mailbox existence verdict established.']}
    (output/'result.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    (root/'data/contact-fallback-latest.json').write_text(json.dumps({'result': str(output/'result.json')})+'\n', encoding='utf-8')
    (root/'docs/contact-fallback-live-check.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'normal_database_unchanged': True, 'messages_sent': 0, 'result': str(output/'result.json')}), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
