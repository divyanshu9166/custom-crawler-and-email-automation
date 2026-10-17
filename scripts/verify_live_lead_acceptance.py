"""Real, isolated US/UK acquisition acceptance; never runs a sender or verifier.

Two website-search waves use the real discovery/import pipeline. Restricted
sources are exercised separately so their failures cannot hide website yield.
The crawler keeps the production page/depth/render budgets. Wall-clock limits
are explicitly reported as incomplete diagnostics, never successful coverage.
"""
import asyncio
import hashlib
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from outreach.config import Settings
from outreach.db import DB
from outreach.discovery import resolve_signal, platform_of
from outreach.profiles import canonical_profile, add_profile_lead, PROFILE_PLATFORMS
from outreach.providers import discover
from outreach.research import discover_leads, research_lead, current_evidence, assert_contact_ownership
from outreach.research_status import snapshot

SEGMENTS = [
    ('UK', 'A', 'dental', 'independent dental clinic Manchester UK contact'),
    ('UK', 'A', 'florist', 'independent wedding florist Bristol UK contact'),
    ('US', 'A', 'dental', 'independent dental practice Austin Texas US contact'),
    ('US', 'A', 'roofing', 'local roofing company Denver Colorado US contact'),
    ('UK', 'B', 'skincare', 'independent skincare brand UK online shop contact'),
    ('UK', 'B', 'coffee', 'specialty coffee roaster UK online shop contact'),
    ('US', 'B', 'skincare', 'independent skincare brand US online shop contact'),
    ('US', 'B', 'coffee', 'specialty coffee roaster US online shop contact'),
]
PROFILE_SEARCHES = [
    ('UK', 'A', 'site:linkedin.com/company/ florist Bristol UK'),
    ('US', 'B', 'site:x.com coffee roaster United States'),
    ('UK', 'A', 'site:peopleperhour.com website development UK business'),
    ('UK', 'A', 'site:facebook.com "Bristol" "florist" "gmail.com"'),
    ('UK', 'A', 'site:instagram.com "UK" "home baker" "gmail.com"'),
    ('US', 'A', 'site:bbb.org "Texas" "plumber" "email"'),
]


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')


def fingerprint(db):
    return {table: hashlib.sha256(json.dumps(db.all(f'SELECT * FROM {table} ORDER BY id'), sort_keys=True).encode()).hexdigest()
            for table in ('leads', 'contacts', 'messages', 'jobs', 'events', 'crawls', 'evidence')}


async def main():
    root = Path(__file__).resolve().parents[1]
    output = root/'data/live-lead-acceptance'/time.strftime('%Y%m%d-%H%M%S')
    output.mkdir(parents=True, exist_ok=False)
    normal = DB(Settings().database)
    assert normal.get('paused') == 'true', 'Normal sending must remain paused'
    assert not normal.one("SELECT 1 FROM jobs WHERE state IN ('pending','running')"), 'Wait for normal jobs first'
    before = fingerprint(normal)
    settings = Settings(_env_file=None, data_dir=output, worker_enabled=False, sending_enabled=False,
                        discovery_platforms='', auto_visual_audit=False, auto_contact_research=False)
    db = DB(settings.database)
    db.set('paused', 'true')
    report = {'started_at': time.time(), 'live': True, 'fixtures': False,
              'scope': 'Two real website-discovery waves, eight market/campaign/segment cells; separate real platform/profile probes',
              'settings': {'worker_enabled': False, 'sending_enabled': False, 'discovery_platforms': '',
                           'crawl_max_pages': settings.crawl_max_pages, 'crawl_max_depth': settings.crawl_max_depth,
                           'crawl_render_mode': settings.crawl_render_mode, 'crawl_delay_seconds': settings.crawl_delay_seconds,
                           'crawl_wall_clock_limit_seconds': 360, 'discovery_limit_per_cell': 2},
              'database': str(settings.database.resolve()), 'waves': [], 'crawls': [], 'profiles': [], 'recovery': []}
    write(root/'data/live-lead-acceptance-latest.json', {'report': str((output/'report.json').resolve()), 'database': report['database']})
    gate = asyncio.Semaphore(2)

    def save():
        report['updated_at'] = time.time()
        write(output/'report.json', report)

    async def search_cell(wave, segment):
        market, campaign, industry, query = segment
        async with gate:
            started = time.time()
            last = db.one('SELECT max(id) id FROM events')['id'] or 0
            error = ''
            try:
                await asyncio.wait_for(discover_leads(db, settings, query, campaign, market, 2), 150)
            except (Exception, asyncio.CancelledError) as exc:
                error = type(exc).__name__+': '+str(exc)
            terminal = [json.loads(e['detail']) for e in db.all("SELECT detail FROM events WHERE id>? AND kind IN ('discovery','discovery_interrupted')", (last,))
                        if json.loads(e['detail']).get('base_query') == query]
            detail = terminal[-1] if terminal else {}
            ids = detail.get('lead_ids', [])
            result = {'wave': wave, 'market': market, 'campaign': campaign, 'segment': industry, 'query': query,
                      'seconds': round(time.time()-started, 2), 'error': error, 'lead_ids': ids,
                      'companies': [db.one('SELECT id,company,domain,website,source_url FROM leads WHERE id=?', (lid,)) for lid in ids],
                      'discovery_report': detail.get('report', {})}
            report['waves'].append(result)
            save()
            print(json.dumps({'stage': 'discovery', 'wave': wave, 'market': market, 'segment': industry, 'ids': ids, 'error': error}), flush=True)

    for wave in (1, 2):
        await asyncio.gather(*(search_cell(wave, segment) for segment in SEGMENTS))
    selected = []
    for cell in sorted(report['waves'], key=lambda c: (c['wave'], c['market'], c['campaign'], c['segment'])):
        if cell['wave'] == 1 and cell['lead_ids']:
            lid = cell['lead_ids'][0]
            if lid not in selected:
                selected.append(lid)

    async def capture(lid, continuation=False):
        async with gate:
            started = time.time()
            old = {e['id']: e['sha256'] for e in current_evidence(db, lid)}
            error = ''
            try:
                await asyncio.wait_for(research_lead(db, settings, lid, continuation=continuation), 360)
            except Exception as exc:
                error = type(exc).__name__+': '+str(exc)
            pages = current_evidence(db, lid)
            row = db.one('SELECT report FROM crawls WHERE lead_id=? ORDER BY id DESC LIMIT 1', (lid,))
            crawl = json.loads(row['report']) if row else {}
            contacts = db.all('SELECT * FROM contacts WHERE lead_id=?', (lid,))
            candidate_events = [json.loads(e['detail']) for e in db.all("SELECT detail FROM events WHERE kind='contact_candidate_found'")
                                if json.loads(e['detail']).get('lead_id') == lid]
            sourced = []
            for contact in contacts:
                try:
                    assert_contact_ownership(db, contact, db.one('SELECT * FROM leads WHERE id=?', (lid,)))
                    ownership_guard = True
                except ValueError:
                    ownership_guard = False
                sourced.append({'id': contact['id'], 'email': contact['email'], 'source_url': contact['source_url'],
                                'publication_guard': ownership_guard, 'verification': contact['verification']})
            result = {'lead_id': lid, 'continuation': continuation, 'seconds': round(time.time()-started, 2), 'error': error,
                      'company': db.one('SELECT company,domain,website,campaign FROM leads WHERE id=?', (lid,)),
                      'crawl_report': crawl, 'contacts': sourced, 'review_candidates': candidate_events,
                      'pages': [{'id': e['id'], 'url': e['url'], 'title': e['title'], 'sha256': e['sha256'],
                                 'fetched_at': e['fetched_at'], 'text': e['text']} for e in pages],
                      'old_evidence_preserved': all(any(e['id'] == eid and e['sha256'] == digest for e in pages) for eid, digest in old.items())}
            report['recovery' if continuation else 'crawls'].append(result)
            save()
            print(json.dumps({'stage': 'continuation' if continuation else 'crawl', 'lead_id': lid, 'domain': result['company']['domain'],
                              'pages': len(pages), 'contacts': len(contacts), 'state': crawl.get('status'), 'error': error}), flush=True)

    await asyncio.gather(*(capture(lid) for lid in selected))
    # A real business checkpoint, rather than a practice crawling site.
    resumable = [c for c in report['crawls'] if c['crawl_report'].get('checkpoint', {}).get('frontier')]
    if resumable:
        await capture(resumable[0]['lead_id'], continuation=True)

    async def profile_search(market, campaign, query):
        async with gate:
            result = {'market': market, 'campaign': campaign, 'query': query, 'results': [], 'engine_issues': []}
            language_settings = settings.model_copy(update={'search_language': 'en-US' if market == 'US' else 'en-GB'})
            try:
                rows = await discover(language_settings, query, 10, include_platforms=True)
                result['indexed_results'] = list(rows)
                result['engine_issues'] = getattr(rows, 'engine_issues', [])
                valid = []
                for row in rows:
                    try:
                        canonical_profile(row['url'])
                        valid.append(row)
                    except ValueError:
                        continue
                for row in valid[:2]:
                    started = time.time()
                    try:
                        signal = await asyncio.wait_for(resolve_signal(language_settings, row, market, PROFILE_PLATFORMS), 150)
                        # Exercise the actual profile-first persistence path, including
                        # the independent fresh public snapshot and website lookup.
                        lid = add_profile_lead(db, signal.get('company') or row['title'], row['url'], campaign, market)
                        await asyncio.wait_for(research_lead(db, language_settings, lid), 150)
                        lead = db.one('SELECT id,company,website_status,status FROM leads WHERE id=?', (lid,))
                        candidates = [json.loads(e['detail']) for e in db.all("SELECT detail FROM events WHERE kind='contact_candidate_found'")
                                      if json.loads(e['detail']).get('lead_id') == lid]
                        result['results'].append({'source_url': row['url'], 'platform': platform_of(row['url']), 'signal': signal,
                                                  'profile_lead': lead, 'published_contact_candidates': candidates,
                                                  'pages': current_evidence(db, lid), 'seconds': round(time.time()-started, 2)})
                    except Exception as exc:
                        result['results'].append({'source_url': row['url'], 'error': type(exc).__name__+': '+str(exc)})
            except Exception as exc:
                result['error'] = type(exc).__name__+': '+str(exc)
            report['profiles'].append(result)
            save()
            print(json.dumps({'stage': 'profile', 'query': query, 'indexed': len(result.get('indexed_results', [])), 'checked': len(result['results'])}), flush=True)

    await asyncio.gather(*(profile_search(*args) for args in PROFILE_SEARCHES))
    report['snapshot'] = snapshot(db)
    report['finished_at'] = time.time()
    report['normal_database_unchanged'] = before == fingerprint(normal)
    report['sending_paused'] = normal.get('paused') == 'true'
    report['isolated_messages'] = db.one('SELECT count(*) n FROM messages')['n']
    report['isolated_verified_contacts'] = db.one('SELECT count(*) n FROM contacts WHERE verified_at IS NOT NULL')['n']
    report['source_hashes'] = {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((root/'outreach').glob('*.py'))}
    assert report['normal_database_unchanged'] and report['sending_paused']
    assert report['isolated_messages'] == report['isolated_verified_contacts'] == 0
    save()
    print(json.dumps({'stage': 'finished', 'report': str(output/'report.json'), 'counts': report['snapshot']['counts'],
                      'normal_database_unchanged': report['normal_database_unchanged']}), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
