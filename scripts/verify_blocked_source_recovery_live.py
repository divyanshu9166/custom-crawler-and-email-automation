"""Continue a recorded business signal after observed host-level access denials.

Known-company recovery, not a fresh-discovery or personal-email benchmark.
"""
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from outreach.config import Settings
from outreach.db import DB
from outreach.discovery import public_snapshot, resolve_signal
from outreach.platform_access import record_hold, access_status
from verify_crawler_recovery_live import fingerprint


async def main():
    normal = DB(Settings().database)
    assert normal.get('paused') == 'true'
    assert not normal.one("SELECT 1 FROM jobs WHERE state IN ('pending','running')")
    before = fingerprint(normal)
    pointer = json.loads(Path('data/platform-access-diagnosis-latest.json').read_text())
    diagnosed = json.loads(Path(pointer['report']).read_text())
    folder = Path('data/blocked-source-recovery') / time.strftime('%Y%m%d-%H%M%S')
    folder.mkdir(parents=True, exist_ok=False)
    settings = Settings(_env_file=None, data_dir=folder, worker_enabled=False, sending_enabled=False,
        platform_browser_enabled=True, platform_browser_public_fallback=True,
        search_provider='searxng', serpapi_key='', browser_enabled=False, crawl_render_mode='never',
        auto_contact_research=False, auto_professional_research=False, auto_visual_audit=False)
    for row in diagnosed['managed_allowlist']:
        platform = 'linkedin.com' if 'linkedin.com' in row['url'] else 'x.com'
        assert row['http_status'] in (403, 999)
        record_hold(settings, platform, 'http_' + str(row['http_status']), {'http_status': row['http_status']})
    row = None
    for event in normal.all("SELECT detail FROM events WHERE kind='prospect_signal' ORDER BY id DESC"):
        signal = json.loads(event['detail'])
        if signal.get('source_url') == 'https://x.com/SonriaUK':
            row = {'url': signal['source_url'], 'title': signal.get('source_title', ''),
                   'snippet': signal.get('indexed_snippet', '')}
            break
    assert row, 'Use a recorded actual business signal'
    output = {'checked_at': time.time(), 'host_denial_diagnostic': pointer['report'],
              'source_url': row['url'], 'holds': access_status(settings),
              'scope': 'Known recorded business; host-level denial reuse and independent current company-source recovery.'}
    async def recovery():
        signal = await resolve_signal(settings, row, 'UK', ['linkedin.com', 'x.com'])
        output['signal'] = signal
        print(json.dumps({'resolution_state': signal.get('state'), 'website_candidate': signal.get('website'),
                          'profile_state': signal.get('public_snapshot', {}).get('state')}), flush=True)
        if signal.get('website'):
            page = await public_snapshot(settings, signal.get('official_match_url') or signal['website'])
            output['current_company_capture'] = {k: page[k] for k in ('url', 'state', 'sha256') if k in page}
            output['current_company_capture']['published_email_candidates'] = len(page.get('published_emails', []))
    try:
        await asyncio.wait_for(recovery(), timeout=150)
    except Exception as exc:
        output['error_type'] = type(exc).__name__
    assert fingerprint(normal) == before and normal.get('paused') == 'true'
    output.update(main_database_unchanged=True, external_messages_sent=0, email_probes=0,
                  contacts_imported=0, personal_profile_email_extraction_proven=False)
    path = folder / 'report.json'
    path.write_text(json.dumps(output, indent=2) + '\n', encoding='utf-8')
    Path('data/blocked-source-recovery-latest.json').write_text(json.dumps({'report': str(path.resolve())}), encoding='utf-8')
    print('Report: ' + str(path.resolve()), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
