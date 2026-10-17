"""Public profile/name inputs to current company contacts, without a company URL.

This is a resolution control, not representative discovery, native-profile
access, buyer qualification, mailbox verification or permission to send.
"""
import asyncio
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from outreach.config import Settings
from outreach.db import DB
from outreach.discovery import resolve_signal
from verify_crawler_recovery_live import fingerprint


CONTROLS = [
    ('Adam Frickleton', 'https://www.linkedin.com/in/adam-frickleton-15936a13a'),
    ('Rachel Rogerson', 'https://www.linkedin.com/in/rachel-rogerson-46925b55'),
]


async def main():
    normal = Settings()
    db = DB(normal.database)
    assert not normal.sending_enabled and db.get('paused') == 'true'
    assert not db.one("SELECT 1 FROM jobs WHERE state IN ('pending','running')")
    before = fingerprint(db)
    folder = Path('data/linkedin-unseeded-check') / time.strftime('%Y%m%d-%H%M%S')
    folder.mkdir(parents=True, exist_ok=False)
    settings = normal.model_copy(update={'data_dir': folder, 'sending_enabled': False,
        'worker_enabled': False, 'browser_enabled': False, 'platform_browser_enabled': False,
        'crawl_http_retries': 0, 'crawl_request_timeout_seconds': 15, 'search_provider': 'searxng', 'serpapi_key': ''})
    report = {'checked_at': time.time(), 'results': [],
        'scope': 'Two known UK profile/name inputs with company URL omitted. Not representative recall, native LinkedIn access, qualified buyers or mailbox existence.'}
    for name, url in CONTROLS:
        result = await resolve_signal(settings, {'url': url, 'title': name+' | LinkedIn', 'snippet': ''}, 'UK', ['linkedin.com'])
        report['results'].append(result)
        print(json.dumps({'name': name, 'state': result['state'], 'website': result['website'],
            'email_candidates': sum(len(p.get('email_publications', [])) for p in result.get('person_recovery', {}).get('matched_people', []))}), flush=True)
        (folder/'report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    assert before == fingerprint(db) and db.get('paused') == 'true'
    report.update(main_database_unchanged=True, contacts_imported=0, email_probes=0, external_messages_sent=0)
    (folder/'report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    Path('data/linkedin-unseeded-check-latest.json').write_text(json.dumps({'report': str((folder/'report.json').resolve())}), encoding='utf-8')


if __name__ == '__main__':
    asyncio.run(main())
