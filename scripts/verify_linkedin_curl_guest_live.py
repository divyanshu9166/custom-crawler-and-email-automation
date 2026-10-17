"""One anonymous public-document TLS/header control; optional audit dependency."""
import importlib.metadata
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from outreach.config import Settings
from outreach.db import DB
from outreach.professionals import parse_public_html
from verify_crawler_recovery_live import fingerprint
from verify_linkedin_guest_headers_live import COMPLETE


def main():
    from curl_cffi import requests
    settings = Settings()
    db = DB(settings.database)
    assert not settings.sending_enabled and db.get('paused') == 'true'
    assert not db.one("SELECT 1 FROM jobs WHERE state IN ('pending','running')")
    before = fingerprint(db)
    url = 'https://www.linkedin.com/in/adam-frickleton-15936a13a'
    report = {'checked_at': time.time(), 'source_url': url,
        'library_version': importlib.metadata.version('curl_cffi'),
        'scope': 'One known public document, Chrome131 TLS and complete headers; no cookies, private API, proxy or redirect following.',
        'earlier_setup_error': 'A prior diagnostic passed trust_env to request rather than Session and raised TypeError before receiving any platform response.'}
    try:
        with requests.Session(trust_env=False, discard_cookies=True,
                retry=0, allow_redirects=False, impersonate='chrome131') as client:
            assert not list(client.cookies)
            response = client.get(url, headers=COMPLETE, timeout=20)
        report.update(http_status=response.status_code, body_bytes=len(response.content))
        if response.status_code != 200:
            report['state'] = 'http_unavailable'
        elif len(response.content) > 2_000_000:
            report['state'] = 'response_size_limit'
        else:
            parsed = parse_public_html(url, response.text)
            report.update(state=parsed['state'], parsed_profile=parsed)
    except Exception as exc:
        report.update(state='fetch_unavailable', error_type=type(exc).__name__)
    assert fingerprint(db) == before and db.get('paused') == 'true'
    report.update(main_database_unchanged=True, contacts_imported=0,
        recipient_probes=0, messages_sent=0, private_api_requests=0)
    Path('data/linkedin-curl-document-check-20261013.json').write_text(
        json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k: report.get(k) for k in
        ['library_version', 'http_status', 'state', 'error_type', 'main_database_unchanged']}), flush=True)


if __name__ == '__main__':
    main()
