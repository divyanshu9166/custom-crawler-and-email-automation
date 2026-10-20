"""Desktop/mobile UI against an isolated API; external traffic is blocked."""
import json
import time
import hashlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright, expect

from outreach.app import create_app
from outreach import preparation, email_writer
from outreach.research import add_lead, add_contact


@pytest.mark.parametrize('mobile', [False, True])
@pytest.mark.parametrize('editing', [False, True])
def test_one_click_preparation_shows_drafts_or_preserves_unsaved_edits(settings, db, monkeypatch, mobile, editing):
    settings.worker_enabled = settings.sending_enabled = settings.followups_enabled = False
    settings.draft_api_key, settings.draft_model = 'fictional-key', 'fictional-model'
    text = 'Bright Demo Ltd provides commercial cleaning across the UK. Request a quote for office cleaning. Business contact hello@bright-demo.com.'
    lid = add_lead(db, 'Bright Demo Ltd', 'https://bright-demo.com', 'A', 'https://bright-demo.com')
    eid = db.execute('INSERT INTO evidence(lead_id,url,title,text,sha256,fetched_at) VALUES(?,?,?,?,?,?)',
                     (lid, 'https://bright-demo.com/', 'Bright Demo Ltd', text, hashlib.sha256(text.encode()).hexdigest(), time.time()))
    db.execute("UPDATE leads SET status='review' WHERE id=?", (lid,))
    add_contact(db, lid, 'hello@bright-demo.com', 'https://bright-demo.com/')
    db.event('performance', {'lead_id': lid, 'url': 'https://bright-demo.com/', 'status': 'complete',
        'errors': [], 'strategies': {'mobile': {'score': 51, 'final_url': 'https://bright-demo.com/',
            'metrics': {'largest-contentful-paint': {'numericValue':4800,'numericUnit':'millisecond'}}}}})
    review = {'company': 'Bright Demo Ltd', 'country': 'UK', 'country_source': 'https://bright-demo.com/',
              'country_quote': 'provides commercial cleaning across the UK.', 'timezone': 'Europe/London',
              'business_type': 'corporate', 'service': 'website_improvement', 'primary_goal': 'inquiries_bookings',
              'fit_notes': 'A UK commercial cleaner with an office-cleaning quote invitation.', 'evidence_id': eid,
              'quote': 'Request a quote for office cleaning.', 'observation': 'The homepage invites office-cleaning quote requests.',
              'suggestion': 'Explore outlining cleaning schedule options next to this invitation; assess usefulness before changing it.'}
    monkeypatch.setattr(preparation, '_assessment', lambda *a: {'ready': True, 'review': review})
    db.event('preparation', {'lead_id': lid, 'state': 'needs_attention', 'reason': 'Fictional earlier provider failure'})
    monkeypatch.setattr(email_writer, 'test_connection', lambda s: {'ready': True, 'note': 'Synthetic chat request passed.'})
    client = TestClient(create_app(settings), base_url=settings.public_url)
    client.headers['Authorization'] = 'Bearer '+settings.api_token
    errors, external, calls = [], [], []
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch()
        context = browser.new_context(viewport={'width': 390 if mobile else 1440, 'height': 1000})
        def route(r):
            url = r.request.url
            if not url.startswith(settings.public_url+'/'):
                external.append(url)
                r.abort()
                return
            path = url.removeprefix(settings.public_url)
            calls.append((r.request.method, path))
            response = client.request(r.request.method, path, content=r.request.post_data_buffer,
                headers={k: v for k, v in r.request.headers.items() if k in {'content-type', 'origin'}})
            r.fulfill(status=response.status_code, body=response.content,
                      headers={'content-type': response.headers.get('content-type', 'text/plain')})
        context.route('**/*', route)
        page = context.new_page()
        page.on('pageerror', lambda e: errors.append(str(e)))
        try:
            page.clock.install()
            page.goto(settings.public_url+'/')
            page.get_by_role('button', name='Pipeline', exact=True).click()
            page.locator(f'[data-lead="{lid}"]').click()
            expect(page.locator('#review-form')).not_to_be_visible()
            page.get_by_role('button', name='Create email', exact=True).click()
            expect(page.locator('#notice')).to_contain_text('Preparation queued')
            expect(page.locator('#prepare-emails')).to_be_disabled()
            expect(page.get_by_role('region', name='Email preparation')).to_contain_text('Previous attempt: needs attention')
            expect(page.get_by_role('region', name='Email preparation')).to_contain_text('Fictional earlier provider failure')
            if editing:
                page.locator('#advanced-research > summary').click()
                page.locator('#qualification-tools-group > summary').click()
                page.get_by_text('02 · Advanced: edit qualification & offer manually', exact=True).click()
                page.locator('#review-form [name=fit_notes]').fill('Keep this unsaved operator edit.')
            preparation.prepare(db, settings, lid)
            db.execute("UPDATE jobs SET state='done' WHERE kind='prepare'")
            page.clock.fast_forward(5000)
            if editing:
                expect(page.locator('#review-form [name=fit_notes]')).to_have_value('Keep this unsaved operator edit.')
                expect(page.locator('#notice')).to_contain_text('Your edits are preserved')
            else:
                expect(page.locator('[aria-label="Research conclusion"]')).to_contain_text('What we found & how we can help')
                expect(page.locator('[data-edit]')).to_have_count(1)
                expect(page.locator('[data-edit]').first.locator('[name=body]')).not_to_have_value('')
                page.get_by_role('link', name='Review email').click()
                output = Path(__file__).resolve().parents[1] / 'data' / 'preparation-ui'
                output.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(output / ('mobile.png' if mobile else 'desktop.png')))
            page.get_by_role('button', name='Settings', exact=True).click()
            expect(page.locator('[name=auto_prepare_enabled]')).to_be_checked()
            page.get_by_role('button', name='Use NVIDIA Nemotron settings', exact=True).click()
            expect(page.locator('[name=draft_api_url]')).to_have_value('https://integrate.api.nvidia.com/v1')
            expect(page.locator('[name=draft_model]')).to_have_value('nvidia/nemotron-3-ultra-550b-a55b')
            assert settings.draft_model == 'fictional-model'  # filling a preset does not save or call it
            page.get_by_role('button', name='Save AI writer settings', exact=True).click()
            expect(page.locator('#writer-settings-result')).to_contain_text('AI writer settings saved')
            page.get_by_role('button', name='Test AI connection', exact=True).click()
            expect(page.locator('#writer-test-result')).to_contain_text('Synthetic chat request passed')
            assert ('POST', '/api/providers/writer/test') in calls
            page.get_by_role('button', name='Pipeline', exact=True).click()
            page.locator('.list-tools > summary').click()
            page.get_by_role('button', name='Prepare pending emails', exact=True).click()
            expect(page.locator('#notice')).to_contain_text('0 preparation jobs queued; 1 prospects need attention')
            page.get_by_text('Latest batch result', exact=True).click()
            expect(page.locator('#preparation-batch-results')).to_contain_text('already has messages')
            assert not errors and not external
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            assert all(m['state'] == 'draft' and m['due_at'] is None for m in db.all('SELECT * FROM messages'))
            assert not settings.sending_enabled
            assert json.loads(db.one("SELECT detail FROM events WHERE kind='preparation' ORDER BY id DESC")['detail'])['review_required']
        finally:
            context.close()
            browser.close()
