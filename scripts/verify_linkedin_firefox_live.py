"""One ordinary guest Firefox profile control; no source holds changed."""
import asyncio
import json
import sys
import time
from pathlib import Path

from playwright.async_api import async_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from outreach.browser import browser_environment
from outreach.config import Settings
from outreach.db import DB
from outreach.professionals import parse_public_html, public_addresses
from verify_crawler_recovery_live import fingerprint


async def main():
    settings = Settings()
    db = DB(settings.database)
    assert db.get('paused') == 'true' and not settings.sending_enabled
    assert not db.one("SELECT 1 FROM jobs WHERE state IN ('pending','running')")
    before = fingerprint(db)
    url = 'https://www.linkedin.com/in/kara-webs-403722422'
    folder = Path('data/linkedin-firefox-check') / time.strftime('%Y%m%d-%H%M%S')
    folder.mkdir(parents=True, exist_ok=False)
    result = {'checked_at': time.time(), 'url': url, 'browser_engine': 'firefox',
        'scope': 'One previously observed public-profile route, ordinary empty guest browser; no identity spoofing, login, cookies, challenge handling or private contact panels.'}
    runtime = Path('data/tools/firefox-guest-1543/firefox.exe')
    launch = {'executable_path': str(runtime.resolve())} if runtime.exists() else {}
    result['task_owned_runtime_manifest_repair'] = bool(launch)
    async with async_playwright() as playwright:
        browser = await playwright.firefox.launch(headless=True, env=browser_environment(), **launch)
        context = await browser.new_context(accept_downloads=False, viewport={'width': 1440, 'height': 900})
        page = await context.new_page()
        responses = []
        def observe(response):
            if response.request.is_navigation_request() and response.frame == page.main_frame:
                responses.append(response)
        page.on('response', observe)
        try:
            await page.goto(url, wait_until='domcontentloaded', timeout=20000)
        except Exception as exc:
            result['navigation_error_type'] = type(exc).__name__
        if responses:
            response = responses[-1]
            result['http_status'] = response.status
            if response.status >= 400:
                result['state'] = 'source_denied' if response.status in (401, 403, 429, 999) else 'unavailable'
            elif '/in/kara-webs-403722422' not in page.url:
                result['state'] = 'redirect_or_login'
            else:
                data = parse_public_html(url, await page.content())
                result.update(state=data['state'], public_text_chars=len(data.get('text', '')),
                    profile_email_candidates=len(public_addresses(data.get('text', ''))))
        else:
            result['state'] = 'navigation_unavailable'
        await browser.close()
    assert fingerprint(db) == before and db.get('paused') == 'true'
    result.update(main_database_unchanged=True, contacts_imported=0, email_probes=0,
                  external_messages_sent=0, source_holds_changed=False)
    path = folder / 'report.json'
    path.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    Path('data/linkedin-firefox-check-latest.json').write_text(json.dumps({'report': str(path.resolve())}), encoding='utf-8')
    print(json.dumps(result), flush=True)
    print('Report: ' + str(path.resolve()), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
