"""Real Chromium checkpoint continuation on a public practice site; never a prospect or mail test."""
import asyncio
import hashlib
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from outreach.config import Settings
from outreach.db import DB
from outreach.research import add_lead, fresh_evidence, research_lead


async def main():
    root = Path(__file__).resolve().parents[1]
    output = root/'data/recovery-live'/time.strftime('continuation-%Y%m%d-%H%M%S')
    output.mkdir(parents=True, exist_ok=False)
    settings = Settings(data_dir=output, sending_enabled=False, worker_enabled=False,
                        auto_contact_research=False, auto_visual_audit=False, crawl_max_pages=2,
                        browser_enabled=True, crawl_render_mode='always', openai_api_key='', openai_model='')
    db = DB(settings.database)
    lid = add_lead(db, 'Public practice site; not a prospect', 'https://quotes.toscrape.com/js/', 'A', 'https://quotes.toscrape.com/js/')
    await research_lead(db, settings, lid)
    first = fresh_evidence(db, lid)
    report1 = json.loads(db.one('SELECT report FROM crawls')['report'])
    assert len(first) == 2 and report1['checkpoint']['frontier']
    await research_lead(db, settings, lid, continuation=True)
    final = fresh_evidence(db, lid)
    report2 = json.loads(db.one('SELECT report FROM crawls')['report'])
    assert len(final) == 4 and {p['id'] for p in first}.issubset({p['id'] for p in final})
    assert len({p['url'] for p in report2['pages']}) == 4
    assert all(p['rendered'] for p in report2['pages'])
    assert db.one('SELECT COUNT(*) n FROM crawls')['n'] == 1
    assert not db.one('SELECT 1 FROM messages')
    result = {'live': True, 'practice_site': True, 'business_prospect': False, 'checked_at': time.time(),
              'first_pass_pages': 2, 'second_pass_new_pages': 2, 'total_current_pages': 4,
              'rendered_pages': 4, 'original_evidence_preserved': True, 'duplicate_captures': 0,
              'scope': 'Two diagnostic passes; production default stays 30 pages per pass. This is checkpoint/rendering proof, not full coverage or campaign performance.',
              'first_report': report1, 'continued_report': report2, 'messages_sent': 0,
              'pages': [{'url': p['url'], 'sha256': p['sha256']} for p in final],
              'source_hash': hashlib.sha256((root/'outreach/web.py').read_bytes()).hexdigest()}
    (output/'result.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    (root/'data/recovery-live/continuation-latest.json').write_text(json.dumps({'result': str(output/'result.json')}), encoding='utf-8')
    print(json.dumps({k: v for k, v in result.items() if k not in {'first_report', 'continued_report', 'pages'}}), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
