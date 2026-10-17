"""Bounded audit of a public-document header claim; no authenticated API calls.

Does not load repo code, cookies, login sessions, proxies, or production holds.
Two independent GETs of one already observed public profile compare sparse and
complete document headers. A login/challenge/denial is never profile evidence.
"""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from outreach.config import Settings
from outreach.db import DB
from outreach.professionals import parse_public_html, professional_target
from verify_crawler_recovery_live import fingerprint


AGENT = ('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
         'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36')
COMPLETE = {
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
    'accept-language': 'en-US,en;q=0.9',
    'sec-ch-ua': '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"',
    'sec-ch-ua-mobile': '?0', 'sec-ch-ua-platform': '"macOS"',
    'sec-fetch-dest': 'document', 'sec-fetch-mode': 'navigate',
    'sec-fetch-site': 'none', 'sec-fetch-user': '?1',
    'upgrade-insecure-requests': '1', 'user-agent': AGENT,
}
RECIPE = 'https://github.com/ManavvGarg/linkedin-profile-api/blob/5775de51aeaa035668d212df8bc4641fa33a31a2/app/session.py'


def fetch(url, headers):
    with httpx.Client(timeout=20, trust_env=False, follow_redirects=False, headers=headers) as client:
        with client.stream('GET', url) as response:
            result = {'http_status': response.status_code, 'url': url,
                'request_header_names': sorted(response.request.headers),
                'cookie_sent': 'cookie' in response.request.headers,
                'authorization_sent': 'authorization' in response.request.headers}
            assert not result['cookie_sent'] and not result['authorization_sent']
            if response.status_code != 200:
                result['state'] = 'redirect' if response.is_redirect else 'http_unavailable'
                return result
            body = bytearray()
            for chunk in response.iter_bytes():
                body.extend(chunk)
                if len(body) > 2_000_000:
                    return {**result, 'state': 'response_size_limit'}
            result.update(body_bytes=len(body), html_sha256=hashlib.sha256(body).hexdigest())
            parsed = parse_public_html(url, body.decode('utf-8', errors='replace'))
            result.update(state=parsed['state'], parsed_profile=parsed)
            return result


def main(url):
    platform, url = professional_target(url)
    assert platform == 'linkedin.com'
    settings = Settings()
    db = DB(settings.database)
    assert not settings.sending_enabled and db.get('paused') == 'true'
    assert not db.one("SELECT 1 FROM jobs WHERE state IN ('pending','running')")
    before = fingerprint(db)
    folder = Path('data/linkedin-guest-header-check') / time.strftime('%Y%m%d-%H%M%S')
    folder.mkdir(parents=True, exist_ok=False)
    report = {'recipe': RECIPE, 'profile': url, 'checked_at': time.time(),
        'scope': 'One known public profile, two document-header controls, not representative coverage or email/identity approval.',
        'controls': []}
    for label, headers in [('sparse', {'user-agent': AGENT}), ('complete_document', COMPLETE)]:
        try:
            value = fetch(url, headers)
        except Exception as exc:
            value = {'state': 'network_unavailable', 'error_type': type(exc).__name__}
        report['controls'].append({'variant': label, **value})
        (folder/'report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
        print(json.dumps({'variant': label, 'http_status': value.get('http_status'), 'state': value['state']}), flush=True)
        if label == 'sparse':
            time.sleep(5)  # Two fixed audit variants only, no loop/retry/proxy.
    assert fingerprint(db) == before and db.get('paused') == 'true'
    report.update(main_database_unchanged=True, contacts_imported=0, recipient_probes=0,
        messages_sent=0, private_api_requests=0, production_holds_changed=False)
    (folder/'report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    Path('data/linkedin-guest-header-check-latest.json').write_text(
        json.dumps({'report': str((folder/'report.json').resolve())}), encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--url', default='https://www.linkedin.com/in/adam-frickleton-15936a13a')
    main(parser.parse_args().url)
