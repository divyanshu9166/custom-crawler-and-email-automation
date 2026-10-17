"""Read-only browser checks with intercepted recovery states; never starts a crawl."""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from playwright.sync_api import expect, sync_playwright
from outreach.config import Settings
from outreach.db import DB


def main():
    settings = Settings()
    db = DB(settings.database)
    tables = ('leads', 'contacts', 'evidence', 'crawls', 'messages', 'jobs', 'suppression')
    before = {t: db.all('SELECT * FROM '+t+' ORDER BY rowid') for t in tables}
    lead = next(r for r in before['leads'] if r['company'] == 'Bouquets For Days')
    future = time.time()+300
    case = {'checkpoint': {'website': lead['website'], 'retry_urls': [
        {'url': lead['website']+'contact', 'depth': 1, 'failures': 1, 'not_before': future}],
        'frontier': [], 'sitemap_queue': []}}
    errors = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={'width': 1440, 'height': 1000},
                                      extra_http_headers={'Authorization': 'Bearer '+settings.api_token})
        page = context.new_page()
        page.on('pageerror', lambda e: errors.append(str(e)))
        def detail(route):
            response = route.fetch()
            data = response.json()
            data['crawl']['report'] = json.dumps(case)
            route.fulfill(response=response, json=data)
        def status(route):
            response = route.fetch()
            data = response.json()
            for item in data['leads']:
                if item['id'] == lead['id']:
                    item.update(retry_pending=1, domain_not_before=future,
                                resolved_crawl_issues=1, crawl_issues=1,
                                automation={'state': 'scheduled', 'pass': 2, 'max_passes': 4})
            route.fulfill(response=response, json=data)
        page.route('**/api/leads/'+str(lead['id']), detail)
        page.route('**/api/research-status*', status)
        def runtime(route):
            response = route.fetch()
            data = response.json()
            data['activity'].update(worker_fresh=True, crawler_runtime={
                'active': 1, 'desired': 2, 'maximum': 2, 'reason': 'headroom_available', 'at': time.time()})
            route.fulfill(response=response, json=data)
        page.route('**/api/workflow*', runtime)
        page.goto('http://127.0.0.1:8000/')
        expect(page.locator('#flow-update')).to_contain_text('Updated')
        page.locator('#flow-prospect').select_option(str(lead['id']))
        expect(page.locator('#flow-scope')).to_contain_text(lead['company'])
        expect(page.locator('#flow-research-leads')).to_contain_text('pages awaiting retry')
        expect(page.locator('#flow-research-leads')).to_contain_text('Site cooldown until')
        expect(page.locator('#flow-research-leads')).to_contain_text('previous issues resolved')
        expect(page.locator('#flow-research-leads')).to_contain_text('Automatic crawl: scheduled')
        expect(page.locator('#flow-worker')).to_contain_text('Crawl slots 1/2 (max 2)')
        page.locator('#flow-open-data').click()
        expect(page.locator('#continue-research')).to_be_disabled()
        expect(page.locator('#detail')).to_contain_text('Continue available after')
        # Expired per-page wait permits continuation without touching the server.
        case['checkpoint']['retry_urls'][0]['not_before'] = 0
        page.get_by_role('button', name='Workflow', exact=True).click()
        page.locator('#flow-open-data').click()
        expect(page.locator('#continue-research')).to_be_enabled()
        # Origin cooldown overrides an otherwise runnable frontier.
        case['checkpoint'].update(domain_not_before=future, frontier=[{'url': lead['website']+'about', 'depth': 1}])
        page.get_by_role('button', name='Workflow', exact=True).click()
        page.locator('#flow-open-data').click()
        expect(page.locator('#continue-research')).to_be_disabled()
        page.set_viewport_size({'width': 390, 'height': 844})
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        assert not errors, errors
        status_data = context.request.get('http://127.0.0.1:8000/api/status').json()
        assert not status_data['sending_enabled'] and status_data['paused']
        browser.close()
    assert {t: db.all('SELECT * FROM '+t+' ORDER BY rowid') for t in tables} == before
    result = {'checked_at': time.time(), 'retry_only_wait': True, 'due_retry_enabled': True,
              'origin_cooldown_overrides_frontier': True, 'recovery_metrics_visible': True,
              'automatic_pass_and_adaptive_slots_visible': True,
              'mobile_overflow': False, 'js_errors': errors, 'operational_data_unchanged': True,
              'sending_disabled': True, 'scope': 'Intercepted UI recovery states; no crawl, probe or send'}
    Path('data/crawler-recovery-ui-check.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
