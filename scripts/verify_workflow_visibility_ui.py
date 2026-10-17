"""Read-only live preview and simulated activity/failure UI checks."""
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
    errors = []
    base = 'http://127.0.0.1:8000'
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={'width': 1440, 'height': 1000},
                                      extra_http_headers={'Authorization': 'Bearer '+settings.api_token})
        page = context.new_page()
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(base)
        expect(page.locator('#flow-update')).to_contain_text('Updated')
        expect(page.locator('#flow-execution')).to_have_text('No jobs running or queued in this scope')
        for mode, count in [('research', 17), ('overview', 11), ('detail', 35)]:
            page.locator('#flow-detail').select_option(mode)
            expect(page.locator('.flow-node')).to_have_count(count)
            expect(page.locator('#flow-data-counts')).to_contain_text('Stored contacts')
        lead = next(row for row in before['leads'] if row['company'] == 'Bouquets For Days')
        page.locator('#flow-prospect').select_option(str(lead['id']))
        expect(page.locator('#flow-scope')).to_contain_text(lead['company'])
        expect(page.locator('#flow-activity-note')).to_contain_text('Selected prospect work only')
        page.locator('#flow-issues-summary').click()
        expect(page.locator('[data-issue-node]').first).to_be_visible()
        issue = page.locator('[data-issue-node]').first
        node_id = issue.get_attribute('data-issue-node')
        issue.click()
        expect(page.locator('#flow-node-title')).to_contain_text(node_id+' · ')
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.evaluate('window.scrollTo(0,0)')
        page.screenshot(path=str(root/'docs/screenshots/workflow-visibility-desktop.png'), full_page=True)
        page.locator('#flow-open-data').click()
        expect(page.locator('#detail h2').first).to_have_text(lead['company'])
        expect(page.locator('#detail')).to_contain_text('Check original evidence')
        page.get_by_role('button', name='Workflow', exact=True).click()
        page.set_viewport_size({'width': 390, 'height': 844})
        expect(page.locator('#flow-open-data')).to_be_visible()
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.evaluate('window.scrollTo(0,0)')
        page.screenshot(path=str(root/'docs/screenshots/workflow-visibility-mobile.png'), full_page=True)

        # UI-only intercepted response: no jobs or contacts are created.
        def activity(route):
            response = route.fetch()
            data = response.json()
            data['activity'].update(running=1, queued=1, sending=0, worker_fresh=False,
                                    jobs=[{'id': 9876, 'kind': 'research', 'state': 'running',
                                           'company': '<img src=x onerror=alert(1)>',
                                           'started_at': time.time(), 'due_at': time.time()}])
            route.fulfill(response=response, json=data)
        page.route('**/api/workflow?*', activity)
        page.locator('#flow-refresh').click()
        expect(page.locator('#flow-execution')).to_contain_text('1 running jobs')
        expect(page.locator('#flow-worker')).to_contain_text('stale or unavailable')
        expect(page.locator('#flow-active-jobs')).to_contain_text('<img src=x onerror=alert(1)>')
        assert page.locator('#flow-active-jobs img').count() == 0
        page.unroute('**/api/workflow?*', activity)
        page.route('**/api/workflow?*', lambda r: r.fulfill(status=503, json={'detail': 'Simulated UI refresh failure'}))
        page.locator('#flow-refresh').click()
        expect(page.locator('#flow-update')).to_contain_text('displayed data may be outdated')
        page.unroute('**/api/workflow?*')
        page.locator('#flow-refresh').click()
        expect(page.locator('#flow-execution')).to_have_text('No jobs running or queued in this scope')
        expect(page.locator('#flow-update')).to_contain_text('Updated')
        assert not errors, errors
        status = context.request.get(base+'/api/status').json()
        assert not status['sending_enabled'] and status['paused']
        browser.close()
    assert {t: db.all('SELECT * FROM '+t+' ORDER BY rowid') for t in tables} == before
    result = {'checked_at': time.time(), 'desktop_mobile': True, 'maps': [17, 11, 35],
              'selected_data_navigation': True, 'review_gate_navigation': True,
              'simulated_activity_and_stale_worker': True, 'simulated_refresh_failure_recovery': True,
              'html_escaped': True, 'operational_data_unchanged': True, 'sending_disabled': True,
              'js_errors': errors, 'horizontal_overflow': False}
    (root/'data/workflow-visibility-ui-check.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
