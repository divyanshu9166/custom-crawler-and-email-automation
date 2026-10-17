"""Known-profile recovery controls plus an unseeded free-index check.

No import, SMTP probe, send, login or source-hold change. Known controls measure
the current company-page path; they are not fresh LinkedIn discovery evidence.
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
from outreach.discovery import resolve_signal
from verify_crawler_recovery_live import fingerprint


SAMPLES = [
    ('Adam Frickleton', 'https://www.linkedin.com/in/adam-frickleton-15936a13a', 'https://mlaarchitects.co.uk/team/'),
    ('Rachel Rogerson', 'https://www.linkedin.com/in/rachel-rogerson-46925b55', 'https://norr.com/team/rachel-rogerson/'),
]


async def main(homepage_navigation=False):
    normal_settings = Settings()
    db = DB(normal_settings.database)
    assert not normal_settings.sending_enabled and db.get('paused') == 'true'
    assert not db.one("SELECT 1 FROM jobs WHERE state IN ('pending','running')")
    before = fingerprint(db)
    folder = Path('data/linkedin-official-recovery') / time.strftime('%Y%m%d-%H%M%S')
    folder.mkdir(parents=True, exist_ok=False)
    settings = normal_settings.model_copy(update={'data_dir': folder, 'sending_enabled': False,
        'worker_enabled': False, 'browser_enabled': False, 'platform_browser_enabled': False,
        'crawl_http_retries': 0, 'crawl_request_timeout_seconds': 15,
        'search_provider': 'searxng', 'serpapi_key': ''})
    output = {'checked_at': time.time(), 'controls': [],
        'scope': 'Two UK architectural businesses with known publicly linked staff profiles; not representative market coverage or mailbox/buyer verification.'}
    for name, profile, page in SAMPLES:
        if homepage_navigation:
            from outreach.discovery import official_root
            page = official_root(page)
        signal = await resolve_signal(settings, {'url': profile, 'title': name+' | LinkedIn',
            'snippet': 'Known current company team page: '+page}, 'UK', ['linkedin.com'])
        output['controls'].append({'input_origin': 'known_company_homepage_navigation_control' if homepage_navigation
            else 'known_official_staff_page_control', 'signal': signal})
        print(json.dumps({'name': name, 'state': signal['state'], 'native_state': signal['public_snapshot']['state'],
            'matched_people': len(signal.get('person_recovery', {}).get('matched_people', [])),
            'published_email_candidates': sum(len(p.get('email_publications', [])) for p in signal.get('person_recovery', {}).get('matched_people', []))}), flush=True)
        (folder/'report.json').write_text(json.dumps(output, indent=2)+'\n', encoding='utf-8')
    # Remove the official-site hint. The exact-profile search has to find its
    # own current company source. Count failure/engine restrictions as observed.
    name, profile, _ = SAMPLES[0]
    output['unseeded_index_control'] = await resolve_signal(settings,
        {'url': profile, 'title': name+' | LinkedIn', 'snippet': ''}, 'UK', ['linkedin.com'])
    assert db.get('paused') == 'true' and fingerprint(db) == before
    output.update(main_database_unchanged=True, contacts_imported=0, email_probes=0,
        external_messages_sent=0, native_access_recovered=False,
        summary={'known_controls': len(output['controls']),
            'company_matches': sum(bool(r['signal']['website']) for r in output['controls']),
            'published_email_candidates': sum(len(p.get('email_publications', [])) for r in output['controls']
                for p in r['signal'].get('person_recovery', {}).get('matched_people', [])),
            'unseeded_index_state': output['unseeded_index_control']['state']})
    path = folder/'report.json'
    path.write_text(json.dumps(output, indent=2)+'\n', encoding='utf-8')
    Path('data/linkedin-official-recovery-latest.json').write_text(json.dumps({'report': str(path.resolve())}), encoding='utf-8')
    print(json.dumps(output['summary']), flush=True)
    print('Report: '+str(path.resolve()), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--homepage-navigation', action='store_true')
    asyncio.run(main(parser.parse_args().homepage_navigation))
