"""Real Chromium desktop/mobile profile-first batch submission; no provider calls."""
import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import expect, sync_playwright
from outreach.app import create_app


@pytest.mark.parametrize('mobile', [False, True])
def test_one_search_submits_profile_batch_and_recurring_mode(settings, db, mobile):
    settings.worker_enabled = settings.sending_enabled = settings.followups_enabled = False
    gid = db.execute('INSERT INTO campaign_groups(name,goal,created_at,updated_at) VALUES(?,?,?,?)',
                     ('Independent UK services', 'A', time.time(), time.time()))
    client = TestClient(create_app(settings), base_url=settings.public_url,
                        headers={'Authorization': 'Bearer '+settings.api_token})
    errors, mutations = [], []
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch()
        context = browser.new_context(viewport={'width': 390 if mobile else 1440, 'height': 1000})
        def route(r):
            assert r.request.url.startswith(settings.public_url+'/')
            path = r.request.url.removeprefix(settings.public_url)
            if r.request.method not in {'GET', 'HEAD'}:
                mutations.append((path, json.loads(r.request.post_data)))
            response = client.request(r.request.method, path, content=r.request.post_data_buffer,
                                      headers={k: v for k, v in r.request.headers.items() if k in {'content-type', 'origin'}})
            r.fulfill(status=response.status_code, body=response.content,
                      headers={'content-type': response.headers.get('content-type', 'text/plain')})
        context.route('**/*', route)
        page = context.new_page()
        page.on('pageerror', lambda e: errors.append(str(e)))
        try:
            page.goto(settings.public_url+'/')
            page.get_by_role('button', name='Find prospects', exact=True).first.click()
            form = page.locator('#search-form')
            form.locator('[name=query]').fill('Independent consultants London UK')
            form.locator('[name=profile_first]').select_option('true')
            form.locator('[name=limit]').fill('10')
            form.locator('[name=campaign_id]').select_option(str(gid))
            form.get_by_role('button', name='Start research', exact=True).click()
            expect(page.locator('#notice')).to_contain_text('Search queued')
            assert mutations == [('/api/discover', {'query': 'Independent consultants London UK', 'profile_first': True,
                'campaign': 'A', 'country_hint': 'UK', 'limit': 10, 'campaign_id': gid})]
            assert not db.one('SELECT 1 FROM contacts')
            form.locator('details > summary').click()
            form.locator('[name=interval_hours]').fill('24')
            form.get_by_role('button', name='Start research', exact=True).click()
            expect(page.locator('#notice')).to_contain_text('Recurring research scheduled')
            expect(page.locator('#schedules')).to_contain_text('business profiles first')
            assert mutations[-1][0] == '/api/schedules' and mutations[-1][1]['profile_first'] is True
            assert db.one('SELECT profile_first FROM schedules')['profile_first'] == 1
            assert not errors
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            path = Path('data/profile-auto-ui')/('mobile.png' if mobile else 'desktop.png')
            path.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(path), full_page=True)
        finally:
            browser.close()
