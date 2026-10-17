"""Frozen architecture buyer sample or explicit same-row replay; no mail/probes."""
import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from outreach.config import Settings
from outreach.db import DB
from outreach.discovery import company_title, indexed_market_exclusion, resolve_signal
from outreach.people import indexed_person_name
from outreach.professionals import professional_target
from outreach.providers import discover
from verify_crawler_recovery_live import fingerprint


COHORTS = [('UK', 'site:linkedin.com/in/ architecture director UK'),
           ('US', 'site:linkedin.com/in/ architect director United States')]


async def main(replay):
    normal = Settings()
    db = DB(normal.database)
    assert not normal.sending_enabled and db.get('paused') == 'true'
    assert not db.one("SELECT 1 FROM jobs WHERE state IN ('pending','running')")
    before = fingerprint(db)
    folder = Path('data/architecture-buyer-replay' if replay else 'data/architecture-buyer-contact') / time.strftime('%Y%m%d-%H%M%S')
    folder.mkdir(parents=True, exist_ok=False)
    settings = normal.model_copy(update={'data_dir': folder, 'worker_enabled': False,
        'sending_enabled': False, 'platform_browser_enabled': False,
        'search_provider': 'searxng', 'serpapi_key': ''})
    report = {'scope': 'First two eligible roots per fixed UK/US architecture query. No replacement profiles; market/roles/emails remain unqualified.',
        'same_row_replay': bool(replay), 'cohorts': [], 'results': [], 'qualified_buyers': 0}
    if replay:
        original = json.loads(replay.read_text(encoding='utf-8'))
        report.update(replayed_report=str(replay.resolve()), cohorts=original['cohorts'])
    else:
        for market, query in COHORTS:
            rows = await discover(settings.model_copy(update={'search_language': 'en-GB' if market == 'UK' else 'en-US'}), query, 10, include_platforms=True)
            selected = []
            for row in rows:
                try:
                    platform, _ = professional_target(row['url'])
                    name = indexed_person_name(company_title(row.get('title', '')))
                    if platform == 'linkedin.com' and name and not indexed_market_exclusion(row, market):
                        selected.append(row)
                except ValueError:
                    pass
            report['cohorts'].append({'market': market, 'query': query, 'rows': list(rows), 'selected': selected[:2],
                'engine_issues': rows.engine_issues, 'providers': rows.provider_reports})
            await asyncio.sleep(settings.discovery_query_delay_seconds)
    for cohort in report['cohorts']:
        if cohort['market'] not in {'US', 'UK'} or len(cohort['selected']) > 2:
            raise ValueError('Invalid frozen cohort')
        for row in cohort['selected']:
            if professional_target(row['url'])[0] != 'linkedin.com':
                raise ValueError('Frozen LinkedIn profile required')
            print(json.dumps({'stage': 'resolving', 'market_hint': cohort['market'], 'profile': row['url']}), flush=True)
            try:
                signal = await asyncio.wait_for(resolve_signal(settings.model_copy(update={
                    'search_language': 'en-GB' if cohort['market'] == 'UK' else 'en-US'}), row, cohort['market'], ['linkedin.com']), 240)
            except Exception as exc:
                signal = {'state': 'diagnostic_unavailable', 'error_type': type(exc).__name__}
            emails = sorted({e['email'] for p in signal.get('person_recovery', {}).get('matched_people', []) for e in p.get('email_publications', [])})
            report['results'].append({'market_hint': cohort['market'], 'row': row, 'signal': signal,
                'distinct_person_email_candidates': emails})
            print(json.dumps({'state': signal['state'], 'person_email_candidates': len(emails),
                'leaf_pages': len(signal.get('person_recovery', {}).get('pages', []))}), flush=True)
            (folder/'report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
            await asyncio.sleep(settings.discovery_query_delay_seconds)
    assert fingerprint(db) == before and db.get('paused') == 'true'
    report.update(main_database_unchanged=True, contacts_imported=0, recipient_probes=0,
        external_messages_sent=0, finished_at=time.time())
    (folder/'report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    name = 'architecture-buyer-replay-latest.json' if replay else 'architecture-buyer-contact-latest.json'
    (Path('data')/name).write_text(json.dumps({'report': str((folder/'report.json').resolve())}), encoding='utf-8')
    print('Frozen sample finished; operational data unchanged, no probes or messages.', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--replay-report', type=Path, help='Replay these frozen selected rows; not new discovery')
    asyncio.run(main(parser.parse_args().replay_report))
