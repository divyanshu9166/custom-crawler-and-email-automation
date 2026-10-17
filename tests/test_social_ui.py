"""Full dashboard JavaScript against an isolated real API, without external traffic."""
import hashlib
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright, expect

from outreach.app import create_app
from outreach import source_status

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('mobile', [False, True])
def test_dashboard_shows_saved_provider_outcomes_and_post_trigger_sources(settings, db, prepared, mobile):
    settings.worker_enabled = settings.sending_enabled = False
    settings.platform_browser_enabled = True
    lid = prepared['lead_id']
    profile = 'https://x.com/BrightDemo'
    text = 'FICTIONAL POST: Bright Demo launched a new store for UK customers.'
    post = {'url': profile+'/status/123456', 'author_url': profile, 'text': text,
            'sha256': hashlib.sha256(text.encode()).hexdigest(), 'observed_at': time.time(),
            'published_at': None}
    eid = db.execute('INSERT INTO evidence(lead_id,url,title,text,sha256,fetched_at) VALUES(?,?,?,?,?,?)',
                     (lid, post['url'], 'Fictional social post', text, post['sha256'], time.time()))
    db.event('social_post_capture', {'lead_id': lid, **post})
    db.event('social_capture', {'lead_id': lid, 'profile_url': profile, 'state': 'captured',
                              'observed_at': time.time(), 'posts': [post]})
    source_status.record(db, 'managed_browser:x.com', 'recent_posts', profile, {'state': 'captured'}, lead_id=lid)
    app = create_app(settings)
    client = TestClient(app, base_url=settings.public_url)
    client.headers['Authorization'] = 'Bearer '+settings.api_token
    errors, external = [], []
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch()
        context = browser.new_context(viewport={'width': 390 if mobile else 1440, 'height': 1000})
        def route(request):
            url = request.request.url
            if not url.startswith(settings.public_url+'/'):
                external.append(url)
                request.abort()
                return
            headers = {k: v for k, v in request.request.headers.items() if k in {'content-type', 'origin'}}
            response = client.request(request.request.method, url.removeprefix(settings.public_url),
                                      content=request.request.post_data_buffer, headers=headers)
            request.fulfill(status=response.status_code, body=response.content,
                            headers={'content-type': response.headers.get('content-type', 'text/plain')})
        context.route('**/*', route)
        page = context.new_page()
        page.on('pageerror', lambda error: errors.append(str(error)))
        try:
            page.goto(settings.public_url+'/')
            page.get_by_role('button', name='Find prospects', exact=True).first.click()
            expect(page.locator('#provider-source-status')).to_contain_text('managed_browser:x.com')
            expect(page.locator('#provider-source-status')).to_contain_text('captured')
            page.get_by_role('button', name='Pipeline', exact=True).click()
            page.locator(f'[data-lead="{lid}"]').click()
            page.locator('#social-posts summary').click()
            expect(page.locator('#social-posts')).to_contain_text(text)
            expect(page.locator('#social-posts')).to_contain_text('Publication date not established')
            expect(page.locator(f'[name=trigger_evidence_id] option[value="{eid}"]')).to_have_count(1)
            expect(page.locator(f'[name=evidence_id] option[value="{eid}"]')).to_have_count(0)
            page.get_by_role('button', name='Settings', exact=True).click()
            expect(page.locator('#research-settings-form')).to_be_visible()
            expect(page.locator('#runtime-settings-form [name=sending_enabled]')).not_to_be_checked()
            output = ROOT/'data'/'social-upgrade-ui'
            output.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(output/('mobile.png' if mobile else 'desktop.png')), full_page=True)
            assert not errors and not external
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            assert db.one('SELECT count(*) n FROM contacts')['n'] == 1
            assert not db.one("SELECT id FROM messages WHERE state='sent'")
        finally:
            context.close()
            browser.close()
