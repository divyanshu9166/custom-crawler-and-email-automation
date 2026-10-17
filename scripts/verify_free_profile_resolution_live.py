"""Real free-public profile resolution and source capture, without API access or mail."""
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from outreach.config import Settings
from outreach.db import DB
from outreach.discovery import resolve_signal
from outreach.research import add_lead, assert_contact_ownership, current_evidence, research_lead
from verify_crawler_recovery_live import fingerprint


async def main():
    normal = DB(Settings().database)
    assert normal.get('paused') == 'true'
    assert normal.one("SELECT COUNT(*) n FROM jobs WHERE state IN ('pending','running')")['n'] == 0
    before = fingerprint(normal)
    selected = {'https://x.com/SonriaUK': 'UK',
                'https://www.linkedin.com/company/fonte-coffee-roaster': 'US',
                'https://www.linkedin.com/company/mz-skin-ltd.': 'UK'}
    seeds = {}
    for event in normal.all("SELECT detail,created_at FROM events WHERE kind='prospect_signal' ORDER BY id"):
        value = json.loads(event['detail'])
        if value.get('source_url') in selected:
            seeds[value['source_url']] = {'row': {'url': value['source_url'], 'title': value.get('source_title', ''),
                                                'snippet': value.get('indexed_snippet', '')},
                                         'indexed_at': event['created_at']}
    assert set(seeds) == set(selected), 'Known public discovery signals are required; no fictional inputs'
    root = Path('data/free-profile-resolution-live')/time.strftime('%Y%m%d-%H%M%S')
    root.mkdir(parents=True, exist_ok=False)
    settings = Settings(_env_file=None, data_dir=root, worker_enabled=False, sending_enabled=False,
                        auto_visual_audit=False, auto_contact_research=False, crawl_max_pages=6,
                        search_provider='searxng', serpapi_key='', openai_api_key='', openai_model='',
                        draft_api_key='', draft_model='')
    db = DB(settings.database)
    gate, results = asyncio.Semaphore(2), []
    async def capture(url, market):
        async with gate:
            started, error, signal = time.monotonic(), '', {}
            try:
                signal = await asyncio.wait_for(resolve_signal(settings, seeds[url]['row'], market, ['linkedin.com', 'x.com']), 160)
            except Exception as exc:
                error = type(exc).__name__
            result = {'profile_url': url, 'market_sample': market, 'indexed_signal_at': seeds[url]['indexed_at'],
                      'profile_capture': signal.get('public_snapshot', {}).get('state', 'not_run'),
                      'resolution_state': signal.get('state', 'interrupted'), 'website': signal.get('website', ''),
                      'official_match_url': signal.get('official_match_url', ''), 'error': error,
                      'resolution_candidates': signal.get('resolution_candidates', []),
                      'search_errors': signal.get('website_search', {}).get('errors', []),
                      'search_engine_issues': signal.get('website_search', {}).get('engine_issues', []),
                      'new_searches': len(signal.get('website_search', {}).get('queries', [])), 'saved_pages': 0,
                      'company_domain_contacts': 0, 'current_publication_proofs': 0, 'other_domain_candidates': 0}
            if signal.get('website'):
                lid = add_lead(db, signal.get('company') or seeds[url]['row']['title'], signal['website'], 'A', url)
                match = signal.get('official_match_url')
                try:
                    await asyncio.wait_for(research_lead(db, settings, lid, seed_urls=[match] if match else None), 120)
                except Exception as exc:
                    result['research_error'] = type(exc).__name__
                lead = db.one('SELECT * FROM leads WHERE id=?', (lid,))
                contacts = db.all('SELECT * FROM contacts WHERE lead_id=?', (lid,))
                for contact in contacts:
                    try:
                        assert_contact_ownership(db, contact, lead)
                        result['current_publication_proofs'] += 1
                    except ValueError:
                        pass
                result['company_domain_contacts'] = len(contacts)
                result['saved_pages'] = len(current_evidence(db, lid))
                result['other_domain_candidates'] = db.one("SELECT COUNT(DISTINCT json_extract(detail,'$.email')) n FROM events WHERE kind='contact_candidate_found' AND json_extract(detail,'$.lead_id')=?", (lid,))['n']
                row = db.one('SELECT report FROM crawls WHERE lead_id=? ORDER BY id DESC LIMIT 1', (lid,))
                result['crawl_status'] = json.loads(row['report']).get('status') if row else 'not_run'
            result['elapsed'] = round(time.monotonic()-started, 2)
            results.append(result)
            print(json.dumps(result), flush=True)
    await asyncio.gather(*(capture(url, market) for url, market in selected.items()))
    assert not db.one('SELECT 1 FROM messages')
    assert not db.one('SELECT 1 FROM contacts WHERE verified_at IS NOT NULL')
    assert not db.one("SELECT 1 FROM events WHERE kind='verification'")
    assert fingerprint(normal) == before and normal.get('paused') == 'true'
    output = {'checked_at': time.time(), 'results': results, 'main_operational_database_unchanged': True,
              'paid_apis_used': False, 'email_probes': 0, 'external_mail_sent': 0,
              'scope': 'Three real previously indexed business profiles; current public sources rechecked. Not fresh discovery, access bypass, unpublished data or vendor parity.'}
    path = root/'report.json'
    path.write_text(json.dumps(output, indent=2)+'\n', encoding='utf-8')
    Path('data/free-profile-resolution-live-latest.json').write_text(json.dumps({'report': str(path.resolve())}), encoding='utf-8')
    print('Report: '+str(path.resolve()), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
