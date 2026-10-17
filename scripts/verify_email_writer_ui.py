"""Read-only normal preview plus clearly simulated writer UI states. No mail/API calls."""
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from playwright.sync_api import sync_playwright, expect
from outreach.config import Settings
from outreach.db import DB


def main():
    root = Path(__file__).resolve().parents[1]
    settings = Settings()
    db = DB(settings.database)
    tables = ['leads', 'contacts', 'messages', 'jobs', 'crawls', 'evidence', 'suppression']
    before = {t: db.all('SELECT * FROM '+t+' ORDER BY rowid') for t in tables}
    private_settings = settings.data_dir/'workspace-settings.json'
    config_before = private_settings.read_bytes() if private_settings.exists() else None
    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={'width': 1440, 'height': 1000},
                                      extra_http_headers={'Authorization': 'Bearer '+settings.api_token})
        page = context.new_page()
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto('http://127.0.0.1:8000')
        expect(page.locator('#flow-update')).to_contain_text('Updated')
        # Existing operational template copy must be visibly held, not rewritten with fixtures.
        legacy = next(c for c in before['contacts'] if any(m['contact_id'] == c['id'] for m in before['messages']))
        page.locator('#flow-prospect').select_option(str(legacy['lead_id']))
        page.locator('#flow-detail').select_option('overview')
        expect(page.locator('.flow-node').filter(has_text='legacy sequences')).to_have_count(1)
        page.locator('#flow-open-data').click()
        expect(page.locator('#detail')).to_contain_text('Legacy template drafts')
        expect(page.locator(f"[data-draft='{legacy['id']}']")).to_be_disabled()
        assert page.locator('[data-approve]').count() == 0
        expect(page.locator('#detail')).to_contain_text('No template fallback')
        page.screenshot(path=str(root/'docs/screenshots/email-writer-legacy-hold.png'), full_page=True)

        # Controlled UI response only: display valid origin/configuration state without a provider call.
        def simulated_writer(route):
            response = route.fetch()
            data = response.json()
            data['email_writer'] = {'configured': True, 'model': 'fictional-ui-model', 'note': 'SIMULATED UI: writer configured'}
            for contact in data['contacts']:
                contact.update(ai_drafts=True, source_eligible=True, status='new',
                               draft_origin={'method': 'research_ai', 'model': 'fictional-ui-model'})
            route.fulfill(response=response, json=data)
        page.route(f"**/api/leads/{legacy['lead_id']}", simulated_writer)
        page.get_by_role('button', name='Workflow', exact=True).click()
        page.locator('#flow-open-data').click()
        expect(page.locator('#detail')).to_contain_text('Research-based AI drafts · fictional-ui-model')
        expect(page.locator(f"[data-draft='{legacy['id']}']")).to_be_enabled()
        expect(page.locator('[data-approve]')).to_be_visible()
        page.unroute(f"**/api/leads/{legacy['lead_id']}", simulated_writer)

        page.get_by_role('button', name='Settings', exact=True).click()
        form = page.locator('#writer-settings-form')
        expect(form).to_be_visible()
        expect(form.locator('[name=draft_api_url]')).to_have_value('https://integrate.api.nvidia.com/v1')
        expect(form.locator('[name=draft_api_key]')).to_have_value('')
        assert form.locator('[name=draft_api_key]').get_attribute('type') == 'password'
        expect(form).to_contain_text('no template fallback')
        page.screenshot(path=str(root/'docs/screenshots/email-writer-settings.png'), full_page=True)
        page.set_viewport_size({'width': 390, 'height': 844})
        expect(form).to_be_visible()
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        assert not errors, errors
        status = context.request.get('http://127.0.0.1:8000/api/status').json()
        assert not status['sending_enabled'] and status['paused']
        browser.close()
    assert {t: db.all('SELECT * FROM '+t+' ORDER BY rowid') for t in tables} == before
    assert (private_settings.read_bytes() if private_settings.exists() else None) == config_before
    result = {'checked_at': time.time(), 'legacy_drafts_held': True, 'writer_not_configured_visible': True,
              'simulated_ai_origin_and_review_state': True, 'settings_key_masked_and_empty': True,
              'desktop_mobile': True, 'operational_data_and_settings_unchanged': True,
              'provider_calls': 0, 'external_messages_sent': 0, 'sending_disabled_and_paused': True, 'js_errors': errors}
    (root/'data/research-email-writing-ui-check.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
