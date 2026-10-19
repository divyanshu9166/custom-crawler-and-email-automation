"""The routine workspace shows one email and keeps technical controls out of the way."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import expect, sync_playwright

from outreach.app import create_app
from outreach.campaigns import archive_followups


@pytest.mark.parametrize('mobile', [False, True])
@pytest.mark.parametrize('legacy', [False, True])
def test_focused_workspace_one_editor_and_safe_archive(settings, db, prepared, mobile, legacy):
    settings.worker_enabled = settings.sending_enabled = settings.followups_enabled = False
    if not legacy:
        archive_followups(db, prepared['contact_id'])
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
                mutations.append((r.request.method, path))
            response = client.request(r.request.method, path, content=r.request.post_data_buffer,
                                      headers={k: v for k, v in r.request.headers.items() if k in {'content-type', 'origin'}})
            r.fulfill(status=response.status_code, body=response.content,
                      headers={'content-type': response.headers.get('content-type', 'text/plain')})
        context.route('**/*', route)
        page = context.new_page()
        page.on('pageerror', lambda e: errors.append(str(e)))
        try:
            page.goto(settings.public_url+'/')
            expect(page.locator('#pipeline')).to_be_visible()
            expect(page.locator('#detail h2')).to_have_text('Bright Demo')
            assert 'prospect='+str(prepared['lead_id']) in page.url
            expect(page.locator('[data-edit]')).to_have_count(1)
            expect(page.locator('[data-edit]')).to_be_visible()
            expect(page.locator('#advanced-research')).not_to_have_attribute('open', '')
            expect(page.locator('#review-form')).not_to_be_visible()
            expect(page.locator('#research-again')).not_to_be_visible()
            expect(page.locator('header #resume')).to_have_count(0)
            expect(page.locator('#detail')).to_contain_text('Your email is ready to review')
            expect(page.locator('.offer-evidence-basis')).to_contain_text('Exploratory opportunity')
            expect(page.locator('[aria-label="Proof of value preview"]')).to_contain_text('Draft for review')
            page.locator('.proof-preview summary').click()
            expect(page.frame_locator('.proof-preview iframe').locator('body')).to_contain_text('No form was submitted')
            assert page.locator('.proof-preview iframe').get_attribute('sandbox') == ''
            page.locator('.proof-preview summary').click()
            expect(page.locator('.message')).not_to_contain_text('Scheduled after previous touch')
            expect(page.get_by_role('link', name='Review email', exact=True)).to_be_visible()
            assert mutations == []
            if legacy:
                page.locator('.legacy-emails summary').click()
                page.get_by_role('button', name='Keep initial email only', exact=True).click()
                expect(page.locator('#notice')).to_contain_text('Old follow-ups archived')
                expect(page.locator('.legacy-emails')).to_have_count(0)
                assert len(db.all('SELECT * FROM messages')) == 1
            page.locator('[data-edit] [name=subject]').fill('My reviewed personal subject')
            page.get_by_role('button', name='Save draft', exact=True).click()
            expect(page.locator('#notice')).to_have_text('Draft saved.')
            assert db.one('SELECT subject FROM messages WHERE step=0')['subject'] == 'My reviewed personal subject'
            assert all('/approve' not in path and '/resume' not in path for _, path in mutations)
            expect(page.locator('[data-source-text]').first).to_have_text('')
            page.locator('#advanced-research > summary').click()
            page.locator('.saved-sources > summary').click()
            page.locator('[data-evidence-id] > summary').first.click()
            expect(page.locator('[data-source-text]').first).to_contain_text('UK consulting services')
            page.locator('#advanced-research > summary').click()
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            output = Path(__file__).resolve().parents[1] / 'data' / 'workspace-ui'
            output.mkdir(parents=True, exist_ok=True)
            page.evaluate('window.scrollTo(0,0)')
            page.screenshot(path=str(output / ('mobile.png' if mobile else 'desktop.png')), full_page=True)
            page.get_by_role('button', name='Find prospects', exact=True).click()
            page.locator('#lead-form [name=company]').fill('New Demo')
            page.locator('#lead-form [name=website]').fill('https://new-demo.example/')
            page.get_by_role('button', name='Add & research', exact=True).click()
            expect(page.locator('#notice')).to_contain_text('Company queued for research')
            assert db.one("SELECT source_url FROM leads WHERE company='New Demo'")['source_url'] == 'https://new-demo.example/'
            assert errors == []
            assert settings.sending_enabled is False
        finally:
            context.close()
            browser.close()
