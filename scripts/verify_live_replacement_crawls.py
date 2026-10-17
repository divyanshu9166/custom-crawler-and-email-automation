"""Capture the corrected US roofing/coffee candidates with normal crawl budgets."""
import asyncio
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from outreach.config import Settings
from outreach.db import DB
from outreach.research import research_lead, current_evidence, assert_contact_ownership
from verify_live_lead_acceptance import write, fingerprint


async def main():
    root = Path(__file__).resolve().parents[1]
    main_report = Path(json.loads((root/'data/live-lead-acceptance-latest.json').read_text(encoding='utf-8'))['report'])
    output = main_report.parent/'current-sources-final'
    source = json.loads((output/'report.json').read_text(encoding='utf-8'))
    settings = Settings(_env_file=None, data_dir=output, sending_enabled=False, worker_enabled=False,
                        auto_visual_audit=False, auto_contact_research=False)
    db = DB(settings.database)
    normal = DB(Settings().database)
    assert normal.get('paused') == 'true'
    before = fingerprint(normal)
    report = {'started_at': time.time(), 'live': True, 'fixtures': False,
              'crawl_max_pages': settings.crawl_max_pages, 'crawl_max_depth': settings.crawl_max_depth,
              'render_mode': settings.crawl_render_mode, 'wall_clock_limit_seconds': 360, 'crawls': []}
    selected = [c['lead_ids'][0] for c in source['waves'] if c['wave'] == 1 and c['market'] == 'US' and c['segment'] in {'roofing', 'coffee'} and c['lead_ids']]
    async def capture(lid):
        started = time.time()
        error = ''
        try:
            await asyncio.wait_for(research_lead(db, settings, lid), 360)
        except Exception as exc:
            error = type(exc).__name__+': '+str(exc)
        lead = db.one('SELECT * FROM leads WHERE id=?', (lid,))
        pages = current_evidence(db, lid)
        contacts = []
        for contact in db.all('SELECT * FROM contacts WHERE lead_id=?', (lid,)):
            try:
                assert_contact_ownership(db, contact, lead)
                guard = True
            except ValueError:
                guard = False
            contacts.append({'email': contact['email'], 'source_url': contact['source_url'], 'publication_guard': guard,
                             'verification': contact['verification']})
        crawl = db.one('SELECT report FROM crawls WHERE lead_id=? ORDER BY id DESC LIMIT 1', (lid,))
        report['crawls'].append({'lead_id': lid, 'domain': lead['domain'], 'company': lead['company'], 'seconds': round(time.time()-started, 2),
                                 'error': error, 'crawl_report': json.loads(crawl['report']), 'contacts': contacts, 'pages': pages})
        write(output/'replacement-crawls.json', report)
        print(json.dumps({'stage': 'replacement_crawl', 'domain': lead['domain'], 'pages': len(pages), 'contacts': len(contacts), 'error': error}), flush=True)
    await asyncio.gather(*(capture(lid) for lid in selected))
    report['normal_database_unchanged'] = before == fingerprint(normal)
    report['finished_at'] = time.time()
    assert report['normal_database_unchanged'] and normal.get('paused') == 'true'
    assert not db.one('SELECT 1 FROM messages') and not db.one('SELECT 1 FROM contacts WHERE verified_at IS NOT NULL')
    write(output/'replacement-crawls.json', report)


if __name__ == '__main__':
    asyncio.run(main())
