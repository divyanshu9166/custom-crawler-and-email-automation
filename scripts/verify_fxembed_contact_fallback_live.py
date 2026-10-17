"""Observed contact-route follow-up for the fixed eight-profile sample.

Reuse saved bios/homepages without changing their dates or repeating API calls.
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
from outreach.contact_recovery import contact_route
from outreach.discovery import public_snapshot
from outreach.web import domain_of, priority
from verify_crawler_recovery_live import fingerprint


async def main():
    normal = DB(Settings().database)
    assert normal.get('paused') == 'true'
    assert not normal.one("SELECT 1 FROM jobs WHERE state IN ('pending','running')")
    before = fingerprint(normal)
    pointer = json.loads(Path('data/fxembed-business-sample-latest.json').read_text(encoding='utf-8'))
    source = json.loads(Path(pointer['report']).read_text(encoding='utf-8'))
    source_folder = Path(pointer['report']).parent
    saved = [json.loads(path.read_text(encoding='utf-8')) for path in source_folder.glob('*.json') if path.name != 'report.json']
    folder = Path('data/fxembed-contact-fallback') / time.strftime('%Y%m%d-%H%M%S')
    folder.mkdir(parents=True, exist_ok=False)
    settings = Settings(_env_file=None, data_dir=folder, worker_enabled=False, sending_enabled=False,
        fxembed_profiles_enabled=False, browser_enabled=False, crawl_render_mode='never',
        crawl_http_retries=0, crawl_request_timeout_seconds=15)
    output = {'checked_at': time.time(), 'source_sample_report': pointer['report'], 'results': [],
              'scope': 'Same eight candidates, saved current homepages plus at most one actually observed contact route each. No new profile lookup, buyer/mailbox verification, import or outreach.'}
    for row in source['results']:
        root = next((p for p in saved if p.get('url') == row['official_pages'][0].get('url')), {})
        routes = [link for link in root.get('public_links', []) if contact_route(link, domain_of(row['website_hint']))]
        pages = [(root, row['official_pages'][0]['observed_at'], True)]
        if not root.get('published_emails') and routes:
            url = sorted(set(routes), key=lambda u: (priority(u), u))[0]
            page = await public_snapshot(settings, url)
            pages.append((page, time.time(), False))
            if page.get('state') == 'captured':
                (folder / (hashlib.sha256(page['url'].encode()).hexdigest()[:16] + '.json')).write_text(json.dumps(page, indent=2), encoding='utf-8')
        result = {'company': row['company'], 'market_hint': row['market_hint'], 'segment': row['segment'],
                  'profile_url': row['profile_url'], 'pages': [], 'candidate_publications': [], 'buyer_verified': False}
        seen = set()
        for page, observed, reused in pages:
            result['pages'].append({**{k: page[k] for k in ('url', 'state', 'error_type', 'sha256') if k in page},
                                   'observed_at': observed, 'reused_saved_capture': reused})
            if page.get('state') != 'captured':
                continue
            addresses = [(email, 'company_domain_publication') for email in page.get('published_emails', [])]
            addresses.extend((c['email'], 'other_domain_requires_ownership_review') for c in page.get('review_candidates', []))
            for email, kind in addresses:
                if email in seen or email not in page.get('text', '').lower():
                    continue
                seen.add(email)
                start = page['text'].lower().find(email)
                result['candidate_publications'].append({'email': email, 'kind': kind, 'source_url': page['url'],
                    'source_sha256': page['sha256'], 'source_observed_at': observed,
                    'context_quote': page['text'][max(0, start-80):start+len(email)+100],
                    'buyer_verified': False, 'mailbox_existence_verified': False})
        output['results'].append(result)
        print(json.dumps({'company': result['company'], 'page_states': [p['state'] for p in result['pages']],
                          'official_email_candidates': len(result['candidate_publications'])}), flush=True)
    assert fingerprint(normal) == before and normal.get('paused') == 'true'
    output.update(community_profile_requests=0, main_database_unchanged=True, contacts_imported=0,
        email_probes=0, external_messages_sent=0,
        summary={'sample_companies': len(output['results']),
            'companies_with_official_email_candidates': sum(bool(r['candidate_publications']) for r in output['results']),
            'official_email_candidates': sum(len(r['candidate_publications']) for r in output['results']),
            'new_contact_page_captures': sum(p.get('state') == 'captured' and not p['reused_saved_capture'] for r in output['results'] for p in r['pages']),
            'verified_buyers': 0})
    path = folder / 'report.json'
    path.write_text(json.dumps(output, indent=2) + '\n', encoding='utf-8')
    Path('data/fxembed-contact-fallback-latest.json').write_text(json.dumps({'report': str(path.resolve())}), encoding='utf-8')
    print(json.dumps(output['summary']), flush=True)
    print('Report: ' + str(path.resolve()), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
