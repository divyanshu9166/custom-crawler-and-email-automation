"""Bounded fresh buyer-role profile coverage; no imports, probes or messages.

Samples are fixed before search and never replaced after extraction failure.
Search-market/role hints and community bios do not approve buyers or ownership.
"""
import asyncio
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from outreach.config import Settings
from outreach.db import DB
from outreach.discovery import company_title, resolve_signal, relaxed_profile_query
from outreach.fxembed import profile_hint
from outreach.people import ROLE, indexed_person_name
from outreach.professionals import professional_target
from outreach.providers import discover
from verify_crawler_recovery_live import fingerprint
import re


COHORTS = [
    ('UK', 'linkedin.com', 'site:linkedin.com/in/ "dental" "owner" "United Kingdom"'),
    ('US', 'linkedin.com', 'site:linkedin.com/in/ "skincare" "founder" "United States"'),
    ('UK', 'x.com', 'site:x.com "skincare" "founder" "UK"'),
    ('US', 'x.com', 'site:x.com "ecommerce" "founder" "USA"'),
]


async def main(relaxed=False):
    normal = Settings()
    db = DB(normal.database)
    assert not normal.sending_enabled and db.get('paused') == 'true'
    assert not db.one("SELECT 1 FROM jobs WHERE state IN ('pending','running')")
    assert normal.fxembed_profiles_enabled, 'Approved community source must already be enabled'
    before = fingerprint(db)
    group = 'profile-buyer-relaxed' if relaxed else 'profile-buyer-coverage'
    folder = Path('data') / group / time.strftime('%Y%m%d-%H%M%S')
    folder.mkdir(parents=True, exist_ok=False)
    settings = normal.model_copy(update={'data_dir': folder, 'worker_enabled': False,
        'sending_enabled': False, 'platform_browser_enabled': False,
        'search_provider': 'searxng', 'serpapi_key': '', 'crawl_http_retries': 0,
        'crawl_request_timeout_seconds': 15})
    report = {'started_at': time.time(), 'scope': 'Fresh fixed sector/role queries, first two eligible profiles each. No operator names or company URLs; no replacement profiles. Market and buyer fit are unverified.',
        'cohorts': [], 'results': [], 'qualified_buyers': 0,
        'official_browser_enabled': settings.browser_enabled, 'relaxed_query_pass': relaxed}
    seen = set()
    mirror_held = False
    for market, platform, query in COHORTS:
        settings = settings.model_copy(update={'search_language': 'en-US' if market == 'US' else 'en-GB'})
        original_query = query
        if relaxed:
            query = relaxed_profile_query(query, market)
            assert query, 'Fixed cohort must have a supported bounded fallback'
        cohort = {'market_hint': market, 'platform': platform, 'query': query,
            'original_query': original_query, 'search_market_constraint_relaxed': relaxed,
            'slots': 2, 'selected': [], 'skipped': []}
        report['cohorts'].append(cohort)
        print(json.dumps({'stage': 'query_started', 'query': query}), flush=True)
        try:
            rows = await discover(settings, query, 10, include_platforms=True)
            cohort.update(indexed_rows=rows, engine_issues=getattr(rows, 'engine_issues', []),
                providers=getattr(rows, 'provider_reports', []))
        except Exception as exc:
            cohort['error_type'] = type(exc).__name__
            rows = []
        (folder/'report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
        print(json.dumps({'stage': 'query_finished', 'query': query, 'rows': len(rows)}), flush=True)
        for row in rows:
            if len(cohort['selected']) == 2:
                break
            try:
                found_platform, url = professional_target(row['url'])
                if found_platform != platform or url in seen:
                    raise ValueError('wrong platform or duplicate')
                if platform == 'linkedin.com' and not indexed_person_name(company_title(row.get('title', ''))):
                    raise ValueError('missing usable name hint')
            except ValueError:
                cohort['skipped'].append({'url': row['url'], 'reason': 'not_an_eligible_distinct_profile'})
                continue
            seen.add(url)
            cohort['selected'].append(url)
            result = {'market_hint': market, 'query': query, 'indexed_row': row,
                'profile_url': url, 'platform': platform}
            if platform == 'linkedin.com':
                value = await resolve_signal(settings, row, market, ['linkedin.com'])
                result.update(signal=value,
                    exact_person_match=value.get('state') == 'official_staff_profile_candidate',
                    official_person_email_candidates=[e['email'] for p in value.get('person_recovery', {}).get('matched_people', [])
                        for e in p.get('email_publications', [])])
            else:
                value = {'state': 'skipped_after_provider_denial'} if mirror_held else await profile_hint(settings, url)
                mirror_held = mirror_held or value['state'] in {'source_denied', 'cooldown'}
                result.update(community_profile=value,
                    public_bio_role_hint=bool(re.search(ROLE, value.get('description', ''), re.I)),
                    community_bio_email_candidates=value.get('published_email_candidates', []))
            report['results'].append(result)
            print(json.dumps({'profile': url, 'state': value['state'],
                'official_person_emails': result.get('official_person_email_candidates', []),
                'community_bio_emails': result.get('community_bio_email_candidates', [])}), flush=True)
            (folder/'report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
        await asyncio.sleep(settings.discovery_query_delay_seconds)
    assert fingerprint(db) == before and db.get('paused') == 'true'
    report.update(finished_at=time.time(), main_database_unchanged=True,
        contacts_imported=0, email_probes=0, external_messages_sent=0,
        summary={'planned_slots': 8, 'selected_profiles': len(report['results']),
            'exact_linkedin_person_matches': sum(r.get('exact_person_match', False) for r in report['results']),
            'official_person_emails': sum(len(r.get('official_person_email_candidates', [])) for r in report['results']),
            'community_bio_emails': sum(len(r.get('community_bio_email_candidates', [])) for r in report['results']),
            'qualified_buyers': 0})
    (folder/'report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    (Path('data')/(group+'-latest.json')).write_text(json.dumps({'report': str((folder/'report.json').resolve())}), encoding='utf-8')
    print(json.dumps(report['summary']), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--relaxed', action='store_true', help='Separate bounded less restrictive query pass; preserves the original report')
    asyncio.run(main(parser.parse_args().relaxed))
