"""Fresh public-index discovery of professional X bios, without recipient imports."""
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from outreach.config import Settings
from outreach.db import DB
from outreach.fxembed import profile_hint
from outreach.providers import discover
from outreach.professionals import professional_target
from verify_crawler_recovery_live import fingerprint


async def main():
    normal = Settings()
    db = DB(normal.database)
    assert not normal.sending_enabled and db.get('paused') == 'true'
    assert not db.one("SELECT 1 FROM jobs WHERE state IN ('pending','running')")
    before = fingerprint(db)
    folder = Path('data/fxembed-personal-discovery') / time.strftime('%Y%m%d-%H%M%S')
    folder.mkdir(parents=True, exist_ok=False)
    settings = normal.model_copy(update={'data_dir': folder, 'worker_enabled': False,
        'sending_enabled': False, 'fxembed_profiles_enabled': True, 'search_provider': 'searxng',
        'serpapi_key': '', 'crawl_request_timeout_seconds': 15})
    report = {'scope': 'Fresh professional-profile public-index discovery, maximum two profiles per market query. Country, services/buyer fit and current first-party publication are unqualified.',
        'queries': [], 'results': [], 'skipped': []}
    seen = set()
    for market, query in [('UK', 'site:x.com "business enquiries" UK'),
                          ('US', 'site:x.com "business inquiries" USA')]:
        rows = await discover(settings, query, 10, include_platforms=True)
        report['queries'].append({'query': query, 'results': len(rows),
            'engine_issues': rows.engine_issues, 'providers': rows.provider_reports})
        count = 0
        for row in rows:
            try:
                platform, url = professional_target(row['url'])
                if platform != 'x.com':
                    raise ValueError('X root required')
            except ValueError:
                report['skipped'].append({'url': row['url'], 'reason': 'not_a_public_profile_root'})
                continue
            if url in seen or count >= 2:
                continue
            seen.add(url)
            count += 1
            profile = await profile_hint(settings, url)
            report['results'].append({'market_query_hint': market, 'indexed_row': row, 'profile': profile})
            print(json.dumps({'market_query_hint': market, 'profile': url, 'state': profile['state'],
                'email_candidates': profile.get('published_email_candidates', [])}), flush=True)
            (folder/'report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
            if profile['state'] in {'source_denied', 'cooldown'}:
                report['stopped_after_source_denial'] = True
                break
        if report.get('stopped_after_source_denial'):
            break
    assert fingerprint(db) == before and db.get('paused') == 'true'
    report.update(checked_at=time.time(), main_database_unchanged=True, contacts_imported=0,
        email_probes=0, external_messages_sent=0, native_profile_requests=0,
        summary={'profiles_tested': len(report['results']),
            'public_bios': sum(r['profile']['state'] == 'public_mirror_hint' for r in report['results']),
            'profiles_with_candidates': sum(bool(r['profile'].get('published_email_candidates')) for r in report['results']),
            'unique_candidates': len({e for r in report['results'] for e in r['profile'].get('published_email_candidates', [])}),
            'qualified_buyers': 0})
    (folder/'report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    Path('data/fxembed-personal-discovery-latest.json').write_text(json.dumps({'report': str((folder/'report.json').resolve())}), encoding='utf-8')
    print(json.dumps(report['summary']), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
