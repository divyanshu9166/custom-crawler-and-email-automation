"""Paired known-source snapshot controls; not fresh buyer discovery or native access."""
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from outreach.config import Settings
from outreach.db import DB
from outreach.discovery import public_snapshot, profile_key
from verify_crawler_recovery_live import fingerprint


CONTROLS = [
    ('known_linked_staff', 'https://mlaarchitects.co.uk/team/', 'https://www.linkedin.com/in/adam-frickleton-15936a13a'),
    ('known_linked_staff', 'https://norr.com/team/rachel-rogerson/', 'https://www.linkedin.com/in/rachel-rogerson-46925b55'),
    ('previous_unmatched_staff', 'https://dentalhouseliverpool.co.uk/our-team/dr-stuart-garton/', 'https://www.linkedin.com/in/stuart-garton'),
]


async def main():
    normal = Settings()
    db = DB(normal.database)
    assert not normal.sending_enabled and db.get('paused') == 'true'
    assert not db.one("SELECT 1 FROM jobs WHERE state IN ('pending','running')")
    before = fingerprint(db)
    folder = Path('data/official-snapshot-rendering') / time.strftime('%Y%m%d-%H%M%S')
    folder.mkdir(parents=True, exist_ok=False)
    settings = normal.model_copy(update={'data_dir': folder, 'worker_enabled': False,
        'sending_enabled': False, 'platform_browser_enabled': False, 'crawl_http_retries': 0})
    report = {'scope': 'Three fixed previously observed official pages, paired never/always rendering. Known controls, not fresh discovery, buyer approval or native LinkedIn extraction.',
        'started_at': time.time(), 'controls': [], 'qualified_buyers': 0}
    for sample, url, profile in CONTROLS:
        control = {'sample_kind': sample, 'source_url': url, 'known_profile_hint': profile, 'captures': []}
        report['controls'].append(control)
        for mode in ('never', 'always'):
            try:
                snapshot = await asyncio.wait_for(public_snapshot(settings.model_copy(update={'crawl_render_mode': mode}), url), 180)
            except Exception as exc:
                snapshot = {'state': 'diagnostic_unavailable', 'error_type': type(exc).__name__}
            versions = [snapshot]
            if isinstance(snapshot.get('http_snapshot'), dict):
                versions.append(snapshot['http_snapshot'])
            matched = [{**p, 'source_sha256': version['sha256'],
                'source_capture_method': version.get('capture_method', 'rendered_dom' if snapshot.get('rendered') else 'public_html')}
                for version in versions for p in version.get('named_people', []) if any(
                    profile_key(link) == profile_key(profile) for link in p.get('professional_links', []))]
            capture = {'mode': mode, 'snapshot': snapshot, 'exact_profile_staff_matches': matched,
                'matched_person_email_candidates': sorted({e['email'] for p in matched for e in p.get('email_publications', [])})}
            control['captures'].append(capture)
            print(json.dumps({'source_url': url, 'mode': mode, 'state': snapshot['state'],
                'rendered': snapshot.get('rendered', False), 'render_issue_count': len(snapshot.get('render_issues', [])),
                'exact_profile_matches': len(matched), 'person_email_candidates': len(capture['matched_person_email_candidates'])}), flush=True)
            (folder/'report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
        await asyncio.sleep(settings.discovery_query_delay_seconds)
    assert fingerprint(db) == before and db.get('paused') == 'true'
    report.update(finished_at=time.time(), main_database_unchanged=True, contacts_imported=0,
        recipient_probes=0, external_messages_sent=0, native_platform_requests=0)
    (folder/'report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    Path('data/official-snapshot-rendering-latest.json').write_text(
        json.dumps({'report': str((folder/'report.json').resolve())}), encoding='utf-8')
    print('Paired known-source controls finished; operational data unchanged and no probes or messages.', flush=True)


if __name__ == '__main__':
    asyncio.run(main())
