"""Current-code live discovery/profile retry; no outreach, probes, or fixtures."""
import asyncio
import hashlib
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from outreach.config import Settings
from outreach.db import DB
from outreach.discovery import resolve_signal, platform_of, query_relevant
from outreach.profiles import PROFILE_PLATFORMS, canonical_profile, add_profile_lead
from outreach.providers import discover
from outreach.research import discover_leads, research_lead, current_evidence
from verify_live_lead_acceptance import SEGMENTS, PROFILE_SEARCHES, fingerprint, write


async def main():
    root = Path(__file__).resolve().parents[1]
    primary = json.loads((root/'data/live-lead-acceptance-latest.json').read_text(encoding='utf-8'))
    discovery_only = '--discovery-only' in sys.argv
    output = Path(primary['report']).parent/('current-sources-final' if discovery_only else 'current-sources')
    output.mkdir(exist_ok=discovery_only)
    if discovery_only and (output/'report.json').exists():
        (output/'report.previous.json').write_bytes((output/'report.json').read_bytes())
    normal = DB(Settings().database)
    assert normal.get('paused') == 'true'
    before = fingerprint(normal)
    settings = Settings(_env_file=None, data_dir=output, sending_enabled=False, worker_enabled=False,
                        discovery_platforms='', auto_visual_audit=False, auto_contact_research=False)
    db = DB(settings.database)
    db.set('paused', 'true')
    report = {'started_at': time.time(), 'live': True, 'fixtures': False, 'database': str(settings.database),
              'website_discovery_only': True, 'platform_research_separate': True, 'waves': [], 'profiles': [],
              'source_hashes_at_start': {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((root/'outreach').glob('*.py'))}}
    gate = asyncio.Semaphore(2)
    def save():
        report['updated_at'] = time.time()
        write(output/'report.json', report)

    async def search(wave, segment):
        market, campaign, industry, query = segment
        async with gate:
            started = time.time()
            last = db.one('SELECT max(id) id FROM events')['id'] or 0
            error = ''
            try:
                await asyncio.wait_for(discover_leads(db, settings, query, campaign, market, 2), 150)
            except Exception as exc:
                error = type(exc).__name__+': '+str(exc)
            events = [json.loads(e['detail']) for e in db.all("SELECT detail FROM events WHERE id>? AND kind IN ('discovery','discovery_interrupted')", (last,))
                      if json.loads(e['detail']).get('base_query') == query]
            event = events[-1] if events else {}
            ids = event.get('lead_ids', [])
            result = {'wave': wave, 'market': market, 'campaign': campaign, 'segment': industry, 'query': query,
                      'seconds': round(time.time()-started, 2), 'error': error, 'lead_ids': ids,
                      'companies': [db.one('SELECT id,company,domain,website,source_url FROM leads WHERE id=?', (lid,)) for lid in ids],
                      'discovery_report': event.get('report', {})}
            report['waves'].append(result)
            save()
            print(json.dumps({'stage': 'current_discovery', 'wave': wave, 'market': market, 'segment': industry,
                              'companies': [c['domain'] for c in result['companies']], 'error': error}), flush=True)
    for wave in (1, 2):
        await asyncio.gather(*(search(wave, segment) for segment in SEGMENTS))

    async def profile(market, campaign, query):
        async with gate:
            s = settings.model_copy(update={'search_language': 'en-US' if market == 'US' else 'en-GB'})
            result = {'query': query, 'market': market, 'campaign': campaign, 'checked': []}
            try:
                rows = await discover(s, query, 20, include_platforms=True)
                result['indexed_results'] = list(rows)
                result['engine_issues'] = rows.engine_issues
                required_platform = query.split('site:')[1].split()[0].split('/')[0]
                valid = []
                for row in rows:
                    try:
                        canonical_profile(row['url'])
                        if platform_of(row['url']) == required_platform and query_relevant(query, row):
                            valid.append(row)
                    except ValueError:
                        continue
                for row in valid[:2]:
                    record = {'source_url': row['url']}
                    try:
                        signal = await asyncio.wait_for(resolve_signal(s, row, market, PROFILE_PLATFORMS), 150)
                        record['signal'] = signal
                        lid = add_profile_lead(db, signal.get('company') or row['title'], row['url'], campaign, market)
                        await asyncio.wait_for(research_lead(db, s, lid), 150)
                        record['profile'] = db.one('SELECT id,company,website_status,status FROM leads WHERE id=?', (lid,))
                        record['pages'] = current_evidence(db, lid)
                        record['published_candidates'] = [json.loads(e['detail']) for e in db.all("SELECT detail FROM events WHERE kind='contact_candidate_found'")
                                                          if json.loads(e['detail']).get('lead_id') == lid]
                    except Exception as exc:
                        record['error'] = type(exc).__name__+': '+str(exc)
                    result['checked'].append(record)
            except Exception as exc:
                result['error'] = type(exc).__name__+': '+str(exc)
            report['profiles'].append(result)
            save()
            print(json.dumps({'stage': 'current_profile', 'query': query, 'indexed': len(result.get('indexed_results', [])),
                              'checked': [(c['source_url'], c.get('signal', {}).get('public_snapshot', {}).get('state'),
                                           c.get('profile', {}).get('website_status'), len(c.get('published_candidates', []))) for c in result['checked']]}), flush=True)

    if not discovery_only:
        await asyncio.gather(*(profile(*args) for args in PROFILE_SEARCHES))
    report['normal_database_unchanged'] = before == fingerprint(normal)
    report['finished_at'] = time.time()
    report['isolated_messages'] = db.one('SELECT count(*) n FROM messages')['n']
    report['isolated_verified_contacts'] = db.one('SELECT count(*) n FROM contacts WHERE verified_at IS NOT NULL')['n']
    assert report['normal_database_unchanged'] and normal.get('paused') == 'true'
    assert report['isolated_messages'] == report['isolated_verified_contacts'] == 0
    save()
    print(json.dumps({'stage': 'finished', 'report': str(output/'report.json'), 'normal_database_unchanged': True}), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
