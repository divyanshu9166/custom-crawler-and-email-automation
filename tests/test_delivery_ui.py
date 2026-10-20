"""The delivery view exposes stop controls without opening advanced details by default."""
import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import expect, sync_playwright

from outreach.app import create_app


@pytest.mark.parametrize('mobile', [False, True])
def test_delivery_summary_queue_and_suppression_form(settings, db, active, mobile):
    settings.sending_enabled = False
    client = TestClient(create_app(settings), base_url=settings.public_url,
                        headers={'Authorization': 'Bearer ' + settings.api_token})
    errors = []
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch()
        context = browser.new_context(viewport={'width': 390 if mobile else 1440, 'height': 1000})
        def route(r):
            assert r.request.url.startswith(settings.public_url + '/')
            response = client.request(r.request.method, r.request.url.removeprefix(settings.public_url),
                                      content=r.request.post_data_buffer,
                                      headers={k: v for k, v in r.request.headers.items() if k in {'content-type', 'origin'}})
            r.fulfill(status=response.status_code, body=response.content,
                      headers={'content-type': response.headers.get('content-type', 'text/plain')})
        context.route('**/*', route)
        page = context.new_page()
        page.on('pageerror', lambda e: errors.append(str(e)))
        try:
            page.goto(settings.public_url + '/')
            page.locator('nav [data-view=operations]').click()
            view = page.locator('#delivery-status')
            expect(view).to_contain_text('UNSUBSCRIBED: 0')
            expect(view.locator('details[open]')).to_have_count(0)
            view.locator('summary').filter(has_text='Sending queue').click()
            expect(view).to_contain_text('alex@bright-demo.com')
            view.locator('summary').filter(has_text='Suppression list').click()
            form = page.locator('#suppress-address')
            form.locator('[name=email]').fill('alex@bright-demo.com')
            form.locator('[name=reason]').fill('Do not contact <script>window.deliveryInjected=true</script>')
            form.get_by_role('button', name='Do not contact', exact=True).click()
            expect(view).to_contain_text('UNSUBSCRIBED: 1')
            view.locator('summary').filter(has_text='Suppression list').click()
            expect(view).to_contain_text('Do not contact <script>')
            assert not page.evaluate('Boolean(window.deliveryInjected)')
            assert not errors
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            assert db.one("SELECT COUNT(*) n FROM messages WHERE state='queued'")['n'] == 0
        finally:
            browser.close()
