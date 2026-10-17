"""Compare the same four previously discovered websites, without any email probes."""
import asyncio
import json
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from outreach.config import Settings
from outreach.db import DB
from outreach.research import add_lead, current_evidence, research_lead
from outreach.research_status import snapshot
meta = json.loads(Path('data/first-workflow-live-latest.json').read_text(encoding='utf-8'))
old = DB(Path(meta['database']))
root = Path('data/crawler-optimization-live')/time.strftime('%Y%m%d-%H%M%S')
root.mkdir(parents=True, exist_ok=False)
s = Settings(_env_file=None, data_dir=root, worker_enabled=False, sending_enabled=False, auto_visual_audit=False)
db = DB(s.database)
rows = old.all('SELECT * FROM leads ORDER BY id')
results = []
async def check(source):
    lid = add_lead(db, source['company'], source['website'], source['campaign'], source['source_url'])
    started = time.monotonic()
    error = ''
    try:
        await asyncio.wait_for(research_lead(db, s, lid), 180)
    except Exception as exc:
        error = type(exc).__name__
    crawl = db.one('SELECT report FROM crawls WHERE lead_id=? ORDER BY id DESC LIMIT 1', (lid,))
    report = json.loads(crawl['report']) if crawl else {}
    baseline = old.one('SELECT report FROM crawls WHERE lead_id=? ORDER BY id DESC LIMIT 1', (source['id'],))
    before = json.loads(baseline['report']) if baseline else {}
    result = {'website': source['website'], 'lead_id': lid, 'seconds': round(time.monotonic()-started, 3),
              'error': error, 'before_pages_at_180s': len(before.get('pages', [])),
              'after_pages_at_180s': len(current_evidence(db, lid)), 'first_page_seconds': report.get('first_page_seconds'),
              'http_document_reuses': sum(p.get('document_reused', False) for p in report.get('pages', [])),
              'status': report.get('status'), 'errors': report.get('errors', []),
              'retried_requests': report.get('retried_requests', []), 'activity': report.get('activity'),
              'contacts': db.all('SELECT email,source_url,verification FROM contacts WHERE lead_id=?', (lid,))}
    results.append(result)
    print(json.dumps({k:v for k,v in result.items() if k not in {'errors','contacts','activity','retried_requests'}}, indent=2), flush=True)
async def main():
    print('Live comparison directory:', root, flush=True)
    for offset in range(0,len(rows),2):
        await asyncio.gather(*(check(row) for row in rows[offset:offset+2]))
    assert db.one('SELECT count(*) n FROM messages')['n'] == 0
    assert db.one('SELECT count(*) n FROM contacts WHERE verified_at IS NOT NULL')['n'] == 0
    assert db.one("SELECT count(*) n FROM events WHERE kind='verification'")['n'] == 0
    output = {'live': True, 'same_sites_same_180_second_deadline': True, 'page_budget': s.crawl_max_pages,
              'render_mode': s.crawl_render_mode, 'results': results, 'readout': snapshot(db),
              'email_probes': 0, 'external_mail_sent': 0, 'worker_enabled': False}
    path = root/'report.json'
    path.write_text(json.dumps(output,indent=2),encoding='utf-8')
    Path('data/crawler-optimization-live-latest.json').write_text(json.dumps({'report':str(path.resolve()),'database':str(db.path.resolve())}),encoding='utf-8')
    print('Report:',path,flush=True)
asyncio.run(main())
