"""Compare ordinary Chromium networking with the managed request allowlist.

No login, spoofed identities, proxy rotation, recipient probes or data imports.
Only allowlisted response metadata is saved; never cookies or request headers.
"""
import asyncio
import hashlib
import json
import os
import sys
import time
from pathlib import Path

from playwright.async_api import async_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from outreach.browser import browser_environment
from outreach.config import Settings
from outreach.db import DB
from outreach.platform_browser import BrowserSession
from verify_crawler_recovery_live import fingerprint

SAFE_HEADERS = {'server', 'via', 'content-type', 'retry-after',
                'x-mitmproxy-blocked-reason', 'x-cache', 'x-cache-status'}


async def capture(context, url):
    page = await context.new_page()
    responses = []
    page.on('response', lambda response: responses.append(response)
            if response.request.is_navigation_request() and response.frame == page.main_frame else None)
    row = {'url': url, 'observed_at': time.time()}
    try:
        await page.goto(url, wait_until='domcontentloaded', timeout=20000)
    except Exception as exc:
        row['navigation_error_type'] = type(exc).__name__
    if responses:
        response = responses[-1]
        row['http_status'] = response.status
        headers = await response.all_headers()
        row['headers'] = {k: v[:200] for k, v in headers.items() if k.lower() in SAFE_HEADERS}
        try:
            security = await response.security_details()
            row['tls'] = {key: security[key] for key in ('issuer', 'subjectName', 'protocol') if key in (security or {})}
        except Exception:
            row['tls'] = {}
        # Analyze a bounded denial body without publishing identifiers/body text.
        if response.status >= 400:
            try:
                body = await response.body()
                row['denial_body_bytes'] = len(body)
                row['denial_body_sha256'] = hashlib.sha256(body).hexdigest()
                lower = body[:32768].decode('utf-8', errors='replace').lower()
                row['denial_markers'] = [marker for marker in
                    ('robots_denied', 'request denied', 'access denied', 'forbidden',
                     'proxy', 'captcha', 'unusual traffic', 'rate limit') if marker in lower]
            except Exception as exc:
                row['body_error_type'] = type(exc).__name__
    await page.close()
    return row


async def main():
    db = DB(Settings().database)
    assert db.get('paused') == 'true'
    assert not db.one("SELECT 1 FROM jobs WHERE state IN ('pending','running')")
    before = fingerprint(db)
    folder = Path('data/platform-access-diagnosis') / time.strftime('%Y%m%d-%H%M%S')
    folder.mkdir(parents=True, exist_ok=False)
    settings = Settings(_env_file=None, data_dir=folder, worker_enabled=False,
        sending_enabled=False, platform_browser_headless=True,
        platform_browser_timeout_seconds=20)
    urls = ['https://www.linkedin.com/in/kara-webs-403722422', 'https://x.com/ssbmGooms']
    report = {'checked_at': time.time(), 'proxy_environment_variables_present':
        [name for name in ('HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'NO_PROXY') if os.environ.get(name)],
        'browser_proxy_environment_passed': False, 'ordinary_guest': [], 'managed_allowlist': []}
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True, chromium_sandbox=True,
            env=browser_environment())
        context = await browser.new_context(viewport={'width': 1440, 'height': 900},
            accept_downloads=False, service_workers='block')
        for url in urls:
            row = await capture(context, url)
            report['ordinary_guest'].append(row)
            print(json.dumps({'mode': 'ordinary_guest', **row}), flush=True)
            await asyncio.sleep(2)
        await browser.close()
    async with BrowserSession(settings) as session:
        for url in urls:
            row = await capture(session.context, url)
            report['managed_allowlist'].append(row)
            print(json.dumps({'mode': 'managed_allowlist', **row}), flush=True)
            await asyncio.sleep(2)
    assert fingerprint(db) == before and db.get('paused') == 'true'
    report.update(main_database_unchanged=True, external_messages_sent=0, email_probes=0,
                  contacts_imported=0, request_budget=4)
    path = folder / 'report.json'
    path.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    Path('data/platform-access-diagnosis-latest.json').write_text(
        json.dumps({'report': str(path.resolve())}), encoding='utf-8')
    print('Report: ' + str(path.resolve()), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
