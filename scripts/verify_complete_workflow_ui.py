"""Inspect every node on the normal development server without changing operational data."""
import hashlib
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from playwright.sync_api import sync_playwright, expect
from outreach.config import Settings
from outreach.db import DB
from outreach.preferences import Preferences
from outreach.research import assert_contact_ownership


def main():
    root = Path(__file__).resolve().parents[1]
    settings = Settings()
    db = DB(settings.database)
    tables = ['leads', 'contacts', 'messages', 'jobs', 'crawls', 'evidence', 'sales', 'activities',
              'deliverables', 'proposals', 'suppression', 'tasks', 'financial_entries', 'client_plans', 'schedules']
    before = {table: db.all('SELECT * FROM '+table+' ORDER BY rowid') for table in tables}
    private = [root/'.env', Preferences(settings).path]
    hashes = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in private if p.exists()}
    errors = []
    base = 'http://127.0.0.1:8000'
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={'width': 1440, 'height': 1000},
                                      extra_http_headers={'Authorization': 'Bearer '+settings.api_token})
        page = context.new_page()
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.goto(base)
        expect(page.locator('.flow-node')).to_have_count(17)
        page.locator('#flow-detail').select_option('detail')
        expect(page.locator('.flow-node')).to_have_count(35)
        expect(page.locator('.flow-path')).to_have_count(46)
        response = context.request.get(base+'/api/workflow?detail=true')
        assert response.status == 200
        state = response.json()
        assert state['sending_paused'] is True
        assert len(state['nodes']) == 35 and len(state['edges']) == 46
        inspected = []
        for node in state['nodes']:
            page.locator('#flow-stage').select_option(node['id'])
            expect(page.locator('#flow-node-title')).to_contain_text(node['id']+' · ')
            expect(page.locator('#flow-node-info')).to_contain_text(node['mode'])
            inspected.append(node['id'])
        page.locator('#flow-stage').select_option('H')
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        page.screenshot(path=str(root/'docs/screenshots/complete-workflow-normal-desktop.png'), full_page=True)
        page.set_viewport_size({'width': 390, 'height': 844})
        expect(page.locator('.flow-node')).to_have_count(35)
        assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        viewport = page.locator('#flow-viewport').bounding_box()
        inspector = page.locator('#flow-inspector').bounding_box()
        assert inspector['y'] >= viewport['y']+viewport['height']-1
        page.screenshot(path=str(root/'docs/screenshots/complete-workflow-normal-mobile.png'), full_page=True)
        for lead in before['leads']:
            page.locator('#flow-prospect').select_option(str(lead['id']))
            expect(page.locator('.flow-node')).to_have_count(35)
            response = context.request.get(base+f"/api/workflow?detail=true&lead_id={lead['id']}")
            assert response.status == 200 and response.json()['lead_id'] == lead['id']
        page.locator('#flow-detail').select_option('overview')
        expect(page.locator('.flow-node')).to_have_count(11)
        publication_status = []
        offer_prefills = []
        page.get_by_role('button', name='Pipeline', exact=True).click()
        for lead in before['leads']:
            response = context.request.get(base+f"/api/leads/{lead['id']}")
            assert response.status == 200
            data = response.json()
            contacts = data['contacts']
            page.locator(f"[data-lead='{lead['id']}']").click()
            finding = (json.loads(lead['findings']) or [{}])[0]
            if not lead['service'] and finding.get('review_required') is True and finding.get('proposal_method') == 'explicit_public_signal':
                current = next((p for p in data['offer_proposals'] if p['service'] == finding.get('service')),
                               next(iter(data['offer_proposals']), {}))
                expect(page.locator('#review-form [name="quote"]')).to_have_value(current.get('quote', ''))
                offer_prefills.append(lead['id'])
            for contact in contacts:
                try:
                    assert_contact_ownership(db, contact, lead)
                    eligible = True
                except ValueError:
                    eligible = False
                assert contact['source_eligible'] is eligible
                button = page.locator(f"[data-verify='{contact['id']}']")
                if eligible:
                    expect(button).to_be_enabled()
                else:
                    expect(button).to_be_disabled()
                    expect(page.get_by_text(contact['source_issue'], exact=True)).to_be_visible()
                publication_status.append({'contact_id': contact['id'], 'source_eligible': eligible})
        assert not errors, errors
        browser.close()
    assert {table: db.all('SELECT * FROM '+table+' ORDER BY rowid') for table in tables} == before
    assert {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in private if p.exists()} == hashes
    result = {'checked_at': time.time(), 'normal_candidates': len(before['leads']),
              'normal_contacts': len(before['contacts']), 'normal_messages': len(before['messages']),
              'qualified_candidates': sum(lead['status']=='qualified' for lead in before['leads']),
              'all_35_nodes_inspected': inspected, 'connections': 46, 'overview_stages': 11,
              'per_prospect_maps': len(before['leads']), 'real_records_unchanged': True,
              'private_configuration_unchanged': True, 'sending_paused': True,
              'contact_source_status': publication_status, 'verification_buttons_checked': True,
              'current_automatic_offer_prefills_inspected': offer_prefills,
              'read_only_browser': True, 'desktop_mobile': True, 'js_errors': 0, 'overflow': False}
    (root/'data/complete-workflow-normal-check.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
