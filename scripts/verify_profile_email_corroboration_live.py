"""Corroborate saved community bio candidates using current published company pages.

No additional community profile calls or contact imports/probes/messages.
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
from outreach.discovery import public_snapshot
from outreach.contact_recovery import contact_route
from outreach.web import domain_of
from verify_crawler_recovery_live import fingerprint


async def main():
    normal = DB(Settings().database)
    assert normal.get('paused') == 'true'
    assert not normal.one("SELECT 1 FROM jobs WHERE state IN ('pending','running')")
    before = fingerprint(normal)
    pointer = json.loads(Path('data/fxembed-profile-check-latest.json').read_text(encoding='utf-8'))
    saved = json.loads(Path(pointer['report']).read_text(encoding='utf-8'))
    folder = Path('data/profile-email-corroboration') / time.strftime('%Y%m%d-%H%M%S')
    folder.mkdir(parents=True, exist_ok=False)
    settings = Settings(_env_file=None, data_dir=folder, worker_enabled=False, sending_enabled=False,
        fxembed_profiles_enabled=False, browser_enabled=False, crawl_render_mode='never',
        crawl_http_retries=0, crawl_request_timeout_seconds=20)
    output = {'checked_at': time.time(), 'mirror_report': pointer['report'], 'results': [],
              'scope': 'Current official publication checks for the two saved email candidates; no new profile lookup or mailbox/buyer/outreach verification.'}
    inputs = [
        ('https://x.com/ssbmGooms', 'http://goomscustomcontrollers.com/', 'Explicit store URL in the saved public bio'),
        ('https://x.com/musicplaza_la', 'https://www.musicplaza.com/apps/help-center',
         'Observed official-page search result https://www.musicplaza.com/apps/help-center'),
    ]
    for profile, seed, origin in inputs:
        source = next(row for row in saved['results'] if row['profile_url'] == profile)
        result = {'profile_url': profile, 'company_seed': seed, 'seed_origin': origin,
                  'source_observed_at': source['observed_at'], 'pages': [],
                  'native_profile_access_restored': False, 'buyer_verified': False}
        candidates = source['published_email_candidates']
        pages = []
        first = await public_snapshot(settings, seed)
        pages.append(first)
        # One additional route only when it was actually observed in navigation.
        if first.get('state') == 'captured' and not all(email.lower() in first.get('text', '').lower() for email in candidates):
            observed = [link for link in first.get('public_links', []) if contact_route(link, domain_of(seed))]
            if observed:
                await asyncio.sleep(2)
                pages.append(await public_snapshot(settings, observed[0]))
        for page in pages:
            entry = {key: page[key] for key in ('url', 'state', 'title', 'sha256', 'error_type', 'reason', 'http_status') if key in page}
            entry['observed_at'] = time.time()
            entry['matched_bio_email_count'] = sum(
                email in page.get('published_emails', []) or any(email == item.get('email') for item in page.get('review_candidates', []))
                for email in candidates) if page.get('state') == 'captured' else 0
            result['pages'].append(entry)
            if page.get('state') == 'captured':
                path = folder / (hashlib.sha256(page['url'].encode()).hexdigest()[:16] + '.json')
                path.write_text(json.dumps(page, indent=2), encoding='utf-8')
        result['candidate_publication'] = []
        for email in candidates:
            match = next((page for page in pages if page.get('state') == 'captured' and email.lower() in page.get('text', '').lower()
                and (email in page.get('published_emails', []) or any(email == c.get('email') for c in page.get('review_candidates', [])))), None)
            item = {'email': email, 'current_official_publication_matched': bool(match),
                    'mailbox_existence_verified': False, 'buyer_verified': False}
            if match:
                start = match['text'].lower().find(email.lower())
                item.update(source_url=match['url'], source_sha256=match['sha256'],
                    context_quote=match['text'][max(0, start-140):start+len(email)+120])
            result['candidate_publication'].append(item)
        output['results'].append(result)
        print(json.dumps({k: v for k, v in result.items() if k != 'candidate_publication'}), flush=True)
    assert fingerprint(normal) == before and normal.get('paused') == 'true'
    output.update(main_database_unchanged=True, community_profile_requests=0, contacts_imported=0,
                  email_probes=0, external_messages_sent=0)
    path = folder / 'report.json'
    path.write_text(json.dumps(output, indent=2) + '\n', encoding='utf-8')
    Path('data/profile-email-corroboration-latest.json').write_text(json.dumps({'report': str(path.resolve())}), encoding='utf-8')
    print('Report: ' + str(path.resolve()), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
