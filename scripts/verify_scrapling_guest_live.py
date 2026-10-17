"""One isolated public-document fetch with a reviewed optional audit dependency.

Run with .venv-audit after installing scrapling[fetchers]==0.4.15. No production
engine/session change, captcha solving, account login, private API or messages.
"""
import hashlib
import importlib.metadata
import json
import logging
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from outreach.config import Settings
from outreach.db import DB
from outreach.professionals import parse_public_html
from verify_crawler_recovery_live import fingerprint


def main():
    from scrapling.fetchers import StealthyFetcher
    from scrapling.engines.toolbelt.custom import log
    logging.getLogger(log.name).setLevel(logging.CRITICAL)
    settings = Settings()
    db = DB(settings.database)
    assert not settings.sending_enabled and db.get('paused') == 'true'
    assert not db.one("SELECT 1 FROM jobs WHERE state IN ('pending','running')")
    before = fingerprint(db)
    folder = Path('data/scrapling-guest-check') / time.strftime('%Y%m%d-%H%M%S')
    folder.mkdir(parents=True, exist_ok=False)
    url = 'https://www.linkedin.com/in/adam-frickleton-15936a13a'
    report = {'checked_at': time.time(), 'source_url': url,
        'library_version': importlib.metadata.version('scrapling'),
        'scope': 'One known public profile, no representative recall or recipient approval.',
        'captcha_solving': False, 'google_referer': False, 'real_chrome': True,
        'headless': True, 'proxy': False, 'initial_cookie_count': None,
        'private_api_requests': 0, 'blocked_requests': 0}

    def setup(page):
        report['initial_cookie_count'] = len(page.context.cookies())
        assert report['initial_cookie_count'] == 0
        def route(request_route):
            req = request_route.request
            parts = urlsplit(req.url)
            host = parts.hostname or ''
            allowed_host = host == 'www.linkedin.com' or host.endswith('.licdn.com')
            private = host == 'www.linkedin.com' and parts.path.startswith('/voyager/')
            if req.method != 'GET' or parts.scheme != 'https' or not allowed_host or private:
                report['blocked_requests'] += 1
                request_route.abort()
            else:
                request_route.continue_()
        page.route('**/*', route)

    started = time.monotonic()
    try:
        response = StealthyFetcher.fetch(url, headless=True, real_chrome=True,
            solve_cloudflare=False, google_search=False, timeout=20000,
            network_idle=False, load_dom=True, wait=0, page_setup=setup)
        body = response.body
        if isinstance(body, str):
            body = body.encode('utf-8')
        safe_url = urlsplit(response.url)._replace(query='', fragment='').geturl()
        report.update(http_status=response.status, final_url=safe_url,
            body_bytes=len(body), html_sha256=hashlib.sha256(body).hexdigest())
        if response.status != 200:
            report['state'] = 'http_unavailable'
        elif response.url.rstrip('/') != url.rstrip('/'):
            report['state'] = 'redirected_source_not_accepted'
        elif len(body) > 2_000_000:
            report['state'] = 'response_size_limit'
        else:
            parsed = parse_public_html(url, body.decode('utf-8', errors='replace'))
            report.update(state=parsed['state'], parsed_profile=parsed)
    except Exception as exc:
        report.update(state='fetch_unavailable', error_type=type(exc).__name__)
    report['elapsed_seconds'] = round(time.monotonic()-started, 2)
    assert fingerprint(db) == before and db.get('paused') == 'true'
    report.update(main_database_unchanged=True, contacts_imported=0,
        recipient_probes=0, messages_sent=0, production_holds_changed=False)
    (folder/'report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    Path('data/scrapling-guest-check-latest.json').write_text(
        json.dumps({'report': str((folder/'report.json').resolve())}), encoding='utf-8')
    print(json.dumps({k: report.get(k) for k in
        ['library_version', 'http_status', 'state', 'error_type', 'initial_cookie_count', 'elapsed_seconds', 'main_database_unchanged']}), flush=True)


if __name__ == '__main__':
    main()
