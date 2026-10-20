"""Campaign manager is the initial dashboard; bulk work remains bounded and unsent."""
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import expect, sync_playwright

from outreach.app import create_app


@pytest.mark.parametrize('mobile', [False, True])
def test_named_campaign_bulk_move_delete_restore_and_pause(settings, db, prepared, mobile):
    settings.sending_enabled = False
    api = TestClient(create_app(settings), base_url=settings.public_url,
                     headers={'Authorization': 'Bearer ' + settings.api_token})
    errors, requests = [], []
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch()
        context = browser.new_context(viewport={'width': 390 if mobile else 1440, 'height': 1000})
        def route(r):
            assert r.request.url.startswith(settings.public_url + '/')
            requests.append((r.request.method, r.request.url))
            response = api.request(r.request.method, r.request.url.removeprefix(settings.public_url),
                                   content=r.request.post_data_buffer,
                                   headers={k: v for k, v in r.request.headers.items() if k in {'content-type', 'origin'}})
            r.fulfill(status=response.status_code, body=response.content,
                      headers={'content-type': response.headers.get('content-type', 'text/plain')})
        context.route('**/*', route)
        page = context.new_page()
        page.on('pageerror', lambda e: errors.append(str(e)))
        try:
            page.goto(settings.public_url + '/')
            expect(page.locator('#campaigns')).to_be_visible()
            expect(page.locator('#campaign-rows')).to_contain_text('Bright Demo')
            assert not any(url.endswith('/api/leads') for _, url in requests)
            output = Path('data/campaign-dashboard-ui')
            output.mkdir(parents=True, exist_ok=True)
            page.evaluate('window.scrollTo(0,0)')
            page.screenshot(path=str(output / ('initial-mobile.png' if mobile else 'initial-desktop.png')), full_page=True)
            page.locator('#campaign-new').click()
            form = page.locator('#campaign-create-form')
            form.locator('[name=name]').fill('UK <script>window.campaignInjected=true</script>')
            form.get_by_role('button', name='Create campaign', exact=True).click()
            expect(page.locator('#campaign-list-status')).to_contain_text('No prospects')
            target = db.one("SELECT id FROM campaign_groups WHERE is_default=0")['id']
            page.locator('#campaign-filter').select_option('')
            expect(page.locator('#campaign-rows')).to_contain_text('Bright Demo')
            page.locator('#campaign-select-page').check()
            page.locator('#campaign-bulk-action').select_option('assign')
            page.locator('#bulk-campaign').select_option(str(target))
            page.locator('#campaign-bulk-run').click()
            expect(page.locator('#campaign-bulk-results')).to_contain_text('1 of 1 updated')
            page.locator(f'[data-campaign-toggle="{target}"]').click()
            expect(page.locator(f'[data-campaign-toggle="{target}"]')).to_contain_text('Resume campaign')
            page.locator('#campaign-select-page').check()
            page.locator('#campaign-bulk-action').select_option('delete')
            page.locator('#bulk-reason').fill('Synthetic deletion for UI test')
            page.locator('#bulk-confirm').check()
            page.locator('#campaign-bulk-run').click()
            expect(page.locator('#campaign-list-status')).to_contain_text('No prospects')
            page.locator('#campaign-deleted').select_option('deleted')
            expect(page.locator('#campaign-rows')).to_contain_text('DELETED')
            page.locator('#campaign-select-page').check()
            page.locator('#campaign-bulk-action').select_option('restore')
            page.locator('#campaign-bulk-run').click()
            expect(page.locator('#campaign-list-status')).to_contain_text('No prospects')
            assert db.one('SELECT status FROM contacts')['status'] == 'hold'
            assert not db.one("SELECT 1 FROM messages WHERE state='queued'")
            assert settings.sending_enabled is False
            assert not page.evaluate('Boolean(window.campaignInjected)')
            assert not errors
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            output = Path('data/campaign-dashboard-ui')
            output.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(output / ('mobile.png' if mobile else 'desktop.png')), full_page=True)
            page.locator('#campaign-new').click()
            form.locator('[name=name]').fill('Synthetic D2C batch')
            form.locator('[name=goal]').select_option('B')
            form.get_by_role('button', name='Create campaign', exact=True).click()
            expect(page.locator('#campaign-list-status')).to_contain_text('No prospects')
            store = db.one("SELECT id FROM campaign_groups WHERE goal='B' AND is_default=0")['id']
            page.locator(f'[data-campaign-find="{store}"]').click()
            expect(page.locator('#discovery')).to_be_visible()
            expect(page.locator('#search-form [name=campaign]')).to_have_value('B')
            expect(page.locator('#search-form [name=campaign_id]')).to_have_value(str(store))
            with db.connect() as con:
                con.executemany("INSERT INTO leads(domain,website,company,campaign,source_url,created_at,updated_at) VALUES(?,?,?,'A','https://example.org',1,1)",
                                ((f'bulk-{n}.com', f'https://bulk-{n}.com', f'Synthetic bulk record {n}') for n in range(510)))
            assert prepared['lead_id'] not in {r['id'] for r in api.get('/api/leads').json()}
            page.goto(settings.public_url + '/?prospect=' + str(prepared['lead_id']))
            expect(page.locator('#pipeline')).to_be_visible()
            expect(page.locator('#detail')).to_contain_text('Bright Demo', timeout=15000)
            assert not errors
        finally:
            browser.close()
