"""Eight recorded US/UK business profiles through the enabled community adapter.

Current independent company captures; no imports, probes, sends or native retries.
"""
import asyncio
import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from outreach.config import Settings
from outreach.db import DB
from outreach.fxembed import profile_hint
from outreach.discovery import public_snapshot, name_matches
from outreach.contact_recovery import contact_route
from outreach.web import domain_of
from verify_crawler_recovery_live import fingerprint

SAMPLE = [
    ('https://x.com/fetchroasters', 'US', 'coffee', 'B'),
    ('https://x.com/PDXcoffeeroast', 'US', 'coffee', 'B'),
    ('https://x.com/olderaleighroof', 'US', 'roofing', 'A'),
    ('https://x.com/roofingraleigh', 'US', 'roofing', 'A'),
    ('https://x.com/AliYoungBeauty', 'UK', 'beauty', 'B'),
    ('https://x.com/SnakeBrandUK', 'UK', 'beauty', 'B'),
    ('https://x.com/leedsdental', 'UK', 'dental', 'A'),
    ('https://x.com/SonriaUK', 'UK', 'dental', 'A'),
]


async def main():
    normal = DB(Settings().database)
    assert normal.get('paused') == 'true'
    assert not normal.one("SELECT 1 FROM jobs WHERE state IN ('pending','running')")
    before = fingerprint(normal)
    recorded = {}
    for row in normal.all("SELECT id,detail,created_at FROM events WHERE kind='prospect_signal' ORDER BY id DESC"):
        value = json.loads(row['detail'])
        recorded.setdefault(value.get('source_url'), {**value, 'event_id': row['id'], 'indexed_at': row['created_at']})
    assert all(url in recorded for url, *_ in SAMPLE), 'Actual recorded business signals required'
    folder = Path('data/fxembed-business-sample') / time.strftime('%Y%m%d-%H%M%S')
    folder.mkdir(parents=True, exist_ok=False)
    settings = Settings(_env_file=None, data_dir=folder, worker_enabled=False, sending_enabled=False,
        fxembed_profiles_enabled=True, browser_enabled=False, crawl_render_mode='never',
        crawl_http_retries=0, crawl_request_timeout_seconds=15)
    output = {'checked_at': time.time(), 'results': [],
        'scope': 'Eight previously indexed, unqualified US/UK business candidates, two per segment. This is known-profile transport/coverage testing, not fresh discovery, verified buyers or equivalent vendor recall.'}
    def save():
        (folder / 'report.json').write_text(json.dumps(output, indent=2) + '\n', encoding='utf-8')
    for url, market, segment, campaign in SAMPLE:
        signal = recorded[url]
        hint = await profile_hint(settings, url)
        result = {'profile_url': url, 'company': signal.get('company') or signal.get('source_title'),
            'market_hint': market, 'segment': segment, 'campaign_hint': campaign,
            'signal_event_id': signal['event_id'], 'signal_indexed_at': signal['indexed_at'],
            'website_hint': signal.get('website', ''), 'community_profile': hint, 'official_pages': [],
            'native_profile_requested': False, 'buyer_verified': False, 'country_verified': False}
        output['results'].append(result)
        save()
        print(json.dumps({'stage': 'profile', 'profile_url': url, 'market_hint': market,
            'state': hint['state'], 'bio_chars': len(hint.get('description', '')),
            'email_candidates': len(hint.get('published_email_candidates', []))}), flush=True)
        if hint.get('state') in ('source_denied', 'cooldown') or hint.get('provider_code') in (401, 403, 429, 999):
            output['stopped_after_provider_denial'] = True
            break
    for result in output['results']:
        seed = result['website_hint']
        if not seed:
            continue
        try:
            first = await public_snapshot(settings, seed)
            pages = [first]
            candidates = result['community_profile'].get('published_email_candidates', [])
            if candidates and first.get('state') == 'captured' and not all(e in first.get('text', '').lower() for e in candidates):
                routes = [u for u in first.get('public_links', []) if contact_route(u, domain_of(seed))]
                if routes:
                    await asyncio.sleep(2)
                    pages.append(await public_snapshot(settings, routes[0]))
            for page in pages:
                item = {k: page[k] for k in ('url', 'state', 'title', 'sha256', 'error_type', 'reason') if k in page}
                item.update(observed_at=time.time(), name_matches_profile_hint=False, matching_bio_email_candidates=[])
                if page.get('state') == 'captured':
                    item['name_matches_profile_hint'] = name_matches(result['community_profile'].get('name', ''),
                        page.get('title', '') + ' ' + page.get('text', '')[:1500])
                    published = set(page.get('published_emails', [])) | {r['email'] for r in page.get('review_candidates', [])}
                    item['matching_bio_email_candidates'] = [e for e in candidates if e in published and e in page['text'].lower()]
                    path = folder / (hashlib.sha256(page['url'].encode()).hexdigest()[:16] + '.json')
                    path.write_text(json.dumps(page, indent=2), encoding='utf-8')
                result['official_pages'].append(item)
        except Exception as exc:
            result['company_capture_error_type'] = type(exc).__name__
        print(json.dumps({'stage': 'company', 'profile_url': result['profile_url'],
            'page_states': [p['state'] for p in result['official_pages']],
            'matched_bio_email_candidates': sum(len(p['matching_bio_email_candidates']) for p in result['official_pages'])}), flush=True)
        save()
    assert fingerprint(normal) == before and normal.get('paused') == 'true'
    output.update(main_database_unchanged=True, contacts_imported=0, email_probes=0, external_messages_sent=0,
        summary={'sample_profiles': len(output['results']),
            'public_bios': sum(r['community_profile']['state'] == 'public_mirror_hint' for r in output['results']),
            'bio_email_candidates': sum(len(r['community_profile'].get('published_email_candidates', [])) for r in output['results']),
            'company_pages_captured': sum(p['state'] == 'captured' for r in output['results'] for p in r['official_pages']),
            'current_company_email_matches': sum(len(p['matching_bio_email_candidates']) for r in output['results'] for p in r['official_pages']),
            'verified_buyers': 0})
    save()
    Path('data/fxembed-business-sample-latest.json').write_text(json.dumps({'report': str((folder/'report.json').resolve())}), encoding='utf-8')
    print(json.dumps(output['summary']), flush=True)
    print('Report: ' + str((folder/'report.json').resolve()), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
