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


@pytest.mark.parametrize('mobile', [False, True])
def test_google_campaign_three_form_and_phone_only_workspace(settings, db, mobile):
    from outreach import google_business as maps
    from outreach.profiles import add_profile_lead
    settings.worker_enabled = settings.sending_enabled = settings.followups_enabled = False
    url = 'https://www.google.com/maps/place/Fictional+Bright+Plumbing'
    gid = maps.campaign(db)
    lid = add_profile_lead(db, 'Fictional Bright Plumbing', url, 'A', 'UK', campaign_id=gid)
    snap = maps.parse_listing(url, '<main role="main"><h1>Fictional Bright Plumbing</h1><button jsaction="category">Plumber</button><button aria-label="Address: 10 Fixture Street, Bristol, UK"></button><button aria-label="Phone: 0117 000 0000"></button></main>')
    db.execute('INSERT INTO crawls(lead_id,report,created_at) VALUES(?,?,?)', (lid, json.dumps({'signal': {'public_snapshot':snap}}), time.time()))
    db.execute("UPDATE leads SET website_status='not_found_in_search', status='review' WHERE id=?", (lid,))
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
            page.goto(settings.public_url+'/?prospect='+str(lid))
            summary = page.locator('.google-business-summary')
            expect(summary).to_contain_text('Plumber')
            expect(summary).to_contain_text('Bristol, UK')
            expect(summary).to_contain_text('Public phone: 0117 000 0000')
            expect(summary).to_contain_text('phone-only records do not generate guessed email addresses')
            page.wait_for_load_state('networkidle')
            path = Path('data/maps-ui')/('workspace-mobile.png' if mobile else 'workspace-desktop.png')
            path.parent.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(path), full_page=True)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            page.get_by_role('button', name='Find prospects', exact=True).first.click()
            form = page.locator('#google-business-form')
            form.locator('[name=query]').fill('Plumbers in Bristol UK')
            form.locator('[name=limit]').fill('10')
            form.get_by_role('button', name='Research Google businesses', exact=True).click()
            expect(page.locator('#notice')).to_contain_text('Campaign 3 Google business research queued')
            assert mutations == [('/api/discover', {'query': 'Plumbers in Bristol UK', 'country_hint':'UK', 'limit':10,
                'campaign':'A', 'profile_first':True, 'discovery_source':'google_maps'})]
            payload = json.loads(db.one("SELECT payload FROM jobs WHERE kind='discover'")['payload'])
            assert payload['campaign_id'] == gid
            form.locator('details > summary').click()
            form.locator('[name=interval_hours]').fill('24')
            form.get_by_role('button', name='Research Google businesses', exact=True).click()
            expect(page.locator('#notice')).to_contain_text('Campaign 3 Google business search scheduled')
            expect(page.locator('#schedules')).to_contain_text('Campaign 3 · Google Business Profiles')
            assert mutations[-1][0] == '/api/schedules'
            assert db.one('SELECT discovery_source FROM schedules')['discovery_source'] == 'google_maps'
            assert not db.one('SELECT 1 FROM contacts') and not db.one('SELECT 1 FROM send_attempts')
            assert not errors
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            page.wait_for_load_state('networkidle')
            page.screenshot(path=str(path.parent/('find-mobile.png' if mobile else 'find-desktop.png')), full_page=True)
        finally:
            browser.close()
