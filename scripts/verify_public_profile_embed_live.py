"""Check the normally rendered official profile embed, not a hidden platform API."""
import asyncio
import json
import sys
import time
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from outreach.browser import browser_environment
from outreach.config import Settings
from outreach.db import DB
from outreach.public_posts import ENDPOINT, MAX_RESPONSE, x_author_key
from outreach.platform_access import retry_seconds
from verify_crawler_recovery_live import fingerprint


async def main():
    db = DB(Settings().database)
    before = fingerprint(db)
    assert db.get('paused') == 'true'
    assert not db.one("SELECT 1 FROM jobs WHERE state IN ('pending','running')")
    folder = Path('data/public-profile-embed') / time.strftime('%Y%m%d-%H%M%S')
    folder.mkdir(parents=True, exist_ok=False)
    output = {'checked_at': time.time(), 'results': [],
              'scope': 'Actual published profile embeds in an isolated ordinary guest browser; no hidden API access, sign-in or challenge handling.'}
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True, chromium_sandbox=True, env=browser_environment())
        for target in ['https://x.com/ssbmGooms', 'https://x.com/SonriaUK']:
            row = {'profile_url': target, 'responses': [], 'observed_at': time.time()}
            context = await browser.new_context(service_workers='block', accept_downloads=False)
            async def route(request):
                parts = urlsplit(request.request.url)
                host = parts.hostname or ''
                if parts.scheme == 'https' and not parts.username and not parts.password and not parts.port and any(
                    host == root or host.endswith('.' + root) for root in ('twitter.com', 'x.com', 'twimg.com')
                ):
                    await request.continue_()
                else:
                    await request.abort()
            await context.route('**/*', route)
            await context.route_web_socket('**/*', lambda socket: socket.close())
            try:
                async with httpx.AsyncClient(timeout=15, trust_env=False, follow_redirects=False) as client:
                    async with client.stream('GET', ENDPOINT, params={'url': target, 'dnt': 'true'}) as response:
                        row['publication_status'] = response.status_code
                        if response.status_code != 200:
                            raise ValueError('Publication endpoint unavailable')
                        body = bytearray()
                        async for chunk in response.aiter_bytes(chunk_size=8192):
                            body.extend(chunk)
                            if len(body) > MAX_RESPONSE:
                                raise ValueError('Publishing response exceeds budget')
                payload = json.loads(body)
                assert payload['type'] == 'rich' and payload['version'] == '1.0'
                markup = BeautifulSoup(payload['html'], 'html.parser')
                anchor = markup.select_one('a.twitter-timeline')
                assert anchor and x_author_key(anchor['href']) == x_author_key(target)
                scripts = markup.find_all('script')
                assert all(script.get('src') in ('https://platform.twitter.com/widgets.js',
                    'https://platform.x.com/widgets.js') for script in scripts)
                # Render exactly the published widget. No reconstruction of an
                # undocumented request or parsing of hidden serialized user data.
                page = await context.new_page()
                def observe(response):
                    parts = urlsplit(response.url)
                    if len(row['responses']) < 40:
                        metadata = {'host': parts.hostname, 'path': parts.path[:160], 'status': response.status}
                        if response.status == 429:
                            metadata['retry_after_seconds'] = retry_seconds(response.headers.get('retry-after'))
                        row['responses'].append(metadata)
                page.on('response', observe)
                await page.set_content(payload['html'], wait_until='domcontentloaded', timeout=15000)
                await asyncio.sleep(12)
                row['frames'] = []
                for frame in page.frames[:5]:
                    frame_result = {'host': urlsplit(frame.url).hostname, 'visible_text_chars': 0}
                    try:
                        text = await frame.locator('body').inner_text(timeout=2000)
                        frame_result['visible_text_chars'] = len(text)
                        frame_result['empty_timeline'] = any(value in text.lower() for value in
                            ('nothing to see here', 'tweets by', 'posts by', 'something went wrong'))
                        frame_result['profile_bio_elements'] = await frame.locator('[data-testid="UserDescription"]').count()
                    except Exception as exc:
                        frame_result['error_type'] = type(exc).__name__
                    row['frames'].append(frame_result)
                row['biography_extraction_proven'] = False
                row['profile_email_extraction_proven'] = False
            except Exception as exc:
                row['error_type'] = type(exc).__name__
            finally:
                await context.close()
            output['results'].append(row)
            print(json.dumps(row), flush=True)
            if any(response['status'] in (401, 403, 429, 999) for response in row['responses']):
                output['stopped_after_source_denial'] = True
                break
        await browser.close()
    assert fingerprint(db) == before and db.get('paused') == 'true'
    output.update(main_database_unchanged=True, contacts_imported=0, email_probes=0, external_messages_sent=0)
    path = folder / 'report.json'
    path.write_text(json.dumps(output, indent=2) + '\n', encoding='utf-8')
    Path('data/public-profile-embed-latest.json').write_text(json.dumps({'report': str(path.resolve())}), encoding='utf-8')
    print('Report: ' + str(path.resolve()), flush=True)


if __name__ == '__main__':
    asyncio.run(main())
