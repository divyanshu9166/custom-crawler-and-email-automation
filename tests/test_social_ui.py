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
@pytest.mark.parametrize('failed_source', [None, 'source-status', 'source-coverage'])
def test_dashboard_shows_saved_provider_outcomes_and_post_trigger_sources(settings, db, prepared, mobile, failed_source):
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
            if failed_source and url == settings.public_url+'/api/'+failed_source:
                request.fulfill(status=503, json={'detail': 'Fictional diagnostics failure'})
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
            page.get_by_role('button', name='Pipeline', exact=True).click()
            expect(page.locator(f'[data-lead="{lid}"]')).to_contain_text('Bright Demo')
            page.locator('#filter').fill('NO MATCHING BUSINESS')
            expect(page.locator('#leads')).to_contain_text('No prospects match these filters')
            page.locator('#filter').fill('')
            page.get_by_role('button', name='Find prospects', exact=True).first.click()
            page.locator('.discovery-advanced > summary').click()
            if failed_source == 'source-status':
                expect(page.locator('#provider-source-status')).to_contain_text('Fictional diagnostics failure')
            else:
                expect(page.locator('#provider-source-status')).to_contain_text('managed_browser:x.com')
                expect(page.locator('#provider-source-status')).to_contain_text('captured')
            if failed_source == 'source-coverage':
                expect(page.locator('#discovery-source-coverage')).to_contain_text('Fictional diagnostics failure')
            page.get_by_role('button', name='Pipeline', exact=True).click()
            page.locator(f'[data-lead="{lid}"]').click()
            page.locator('#advanced-research > summary').click()
            page.locator('#people-tools-group > summary').click()
            page.locator('#social-posts summary').click()
            expect(page.locator('#social-posts')).to_contain_text(text)
            expect(page.locator('#social-posts')).to_contain_text('Publication date not established')
            expect(page.locator(f'[name=trigger_evidence_id] option[value="{eid}"]')).to_have_count(1)
            expect(page.locator(f'[name=evidence_id] option[value="{eid}"]')).to_have_count(0)
            page.get_by_role('button', name='Settings', exact=True).click()
            page.locator('#research-settings-form-details > summary').click()
            expect(page.locator('#research-settings-form')).to_be_visible()
            expect(page.locator('#runtime-settings-form [name=sending_enabled]')).not_to_be_checked()
            output = ROOT/'data'/'social-upgrade-ui'
            output.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(output/(('mobile' if mobile else 'desktop')+'-'+(failed_source or 'healthy')+'.png')), full_page=True)
            assert not errors and not external
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            assert db.one('SELECT count(*) n FROM contacts')['n'] == 1
            assert not db.one("SELECT id FROM messages WHERE state='sent'")
        finally:
            context.close()
            browser.close()


@pytest.mark.parametrize('mobile', [False, True])
def test_search_queues_job_and_pipeline_polls_background_results_without_erasing_edits(settings, db, mobile):
    from outreach.research import add_lead
    settings.worker_enabled = settings.sending_enabled = False
    client = TestClient(create_app(settings), base_url=settings.public_url)
    client.headers['Authorization'] = 'Bearer '+settings.api_token
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch()
        context = browser.new_context(viewport={'width': 390 if mobile else 1440, 'height': 1000})
        requests = []
        def route(request):
            url = request.request.url
            assert url.startswith(settings.public_url+'/')
            path = url.removeprefix(settings.public_url)
            requests.append((request.request.method, path))
            headers = {k: v for k, v in request.request.headers.items() if k in {'content-type', 'origin'}}
            response = client.request(request.request.method, path, content=request.request.post_data_buffer, headers=headers)
            request.fulfill(status=response.status_code, body=response.content,
                            headers={'content-type': response.headers.get('content-type', 'text/plain')})
        context.route('**/*', route)
        page = context.new_page()
        page.set_default_timeout(5000)
        try:
            page.clock.install()
            page.goto(settings.public_url+'/')
            page.get_by_role('button', name='Find prospects', exact=True).first.click()
            expect(page.locator('#search-form')).to_be_visible()
            assert not db.one('SELECT id FROM jobs')
            page.locator('#search-form [name=query]').fill('commercial cleaning companies London UK')
            page.locator('#search-form [name=limit]').fill('3')
            page.locator('#search-form button[type=submit]').click()
            expect(page.locator('#notice')).to_contain_text('Search queued')
            job = db.one("SELECT * FROM jobs WHERE kind='discover'")
            assert job and job['state'] == 'pending'
            page.get_by_role('button', name='Operations', exact=True).click()
            expect(page.locator('#jobs')).to_contain_text('discover')
            expect(page.locator('#jobs')).to_contain_text('pending')
            page.get_by_role('button', name='Pipeline', exact=True).click()
            expect(page.locator('#leads')).to_contain_text('No prospects yet')
            lid = add_lead(db, 'Background Demo', 'https://background-demo.com', 'A', 'https://background-demo.com')
            page.clock.fast_forward(15001)
            page.locator(f'[data-lead="{lid}"]').click()
            page.locator('#advanced-research > summary').click()
            page.locator('#qualification-tools-group > summary').click()
            page.get_by_text('02 · Advanced: edit qualification & offer manually', exact=True).click()
            form = page.locator('#review-form [name=observation]')
            form.fill('Unsaved operator observation stays intact.')
            db.execute("UPDATE leads SET company='Updated Background Demo' WHERE id=?", (lid,))
            before = len(requests)
            page.clock.fast_forward(15001)
            expect(page.locator(f'[data-lead="{lid}"]')).to_contain_text('Updated Background Demo')
            expect(form).to_have_value('Unsaved operator observation stays intact.')
            assert all(method == 'GET' for method, _ in requests[before:])
            assert not any(path.startswith('/api/source-') for _, path in requests[before:])
            assert not db.one("SELECT id FROM messages WHERE state='sent'")
        finally:
            context.close()
            browser.close()
