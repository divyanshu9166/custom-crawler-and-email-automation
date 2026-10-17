"""Exercise offer selection and value artifacts in isolated fictional Chromium UI."""
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from playwright.sync_api import sync_playwright, expect
from outreach.db import DB
from outreach.research import add_lead


def main():
    root = Path(__file__).resolve().parents[1]
    pictures = root/'docs/screenshots'
    errors = []
    with tempfile.TemporaryDirectory(prefix='second-workflow-check-') as temp:
        db = DB(Path(temp)/'outreach.db')
        texts = {
            'A': 'Fictional consulting business based in London UK. Book a consultation. Frequently asked questions about booking.',
            'B': 'Fictional brand based in London UK. We sell our own consumer products online. Our online store is launching soon. Add to cart. Frequently asked questions. How do I place an order? Subscribe to our WhatsApp updates.',
        }
        ids = {}
        for campaign, text in texts.items():
            website = f'https://fictional-offer-{campaign.lower()}.example/'
            lid = add_lead(db, 'FICTIONAL Campaign '+campaign, website, campaign, website)
            eid = db.execute('INSERT INTO evidence(lead_id,url,title,text,sha256,fetched_at) VALUES(?,?,?,?,?,?)',
                             (lid, website, 'Fictional public source '+campaign, text, 'fixture-'+campaign, time.time()))
            db.execute("UPDATE leads SET status='review' WHERE id=?", (lid,))
            ids[campaign] = (lid, eid)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        url = f'http://127.0.0.1:{port}'
        token = secrets.token_urlsafe(36)
        env = {**os.environ, 'DATA_DIR': temp, 'WORKER_ENABLED': 'false', 'SENDING_ENABLED': 'false',
               'API_TOKEN': token, 'PUBLIC_URL': url, 'ADMIN_PASSWORD': secrets.token_urlsafe(32)}
        process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'outreach.app:create_app', '--factory',
                                    '--host', '127.0.0.1', '--port', str(port), '--no-access-log'], cwd=root, env=env,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        try:
            for _ in range(60):
                try:
                    urllib.request.urlopen(url+'/health', timeout=1)
                    break
                except OSError:
                    time.sleep(.2)
            else:
                raise RuntimeError('Isolated UI server did not start')
            with sync_playwright() as p:
                browser = p.chromium.launch()
                context = browser.new_context(viewport={'width': 1440, 'height': 1000}, extra_http_headers={'Authorization': 'Bearer '+token})
                page = context.new_page()
                page.on('pageerror', lambda e: errors.append(str(e)))
                page.goto(url)
                page.get_by_role('button', name='Pipeline', exact=True).click()
                for campaign, service in [('A', 'chatbot'), ('B', 'whatsapp_automation')]:
                    lid, eid = ids[campaign]
                    page.locator(f'[data-lead="{lid}"]').click()
                    form = page.locator('#review-form')
                    expect(form).to_be_visible()
                    expect(page.locator('.offer-node-list > div')).to_have_count(15)
                    if campaign == 'B':
                        expect(page.locator('#offer-proposals button')).to_have_count(5)
                    button = page.locator('#offer-proposals button').filter(has_text=service.replace('_', ' '))
                    button.click()
                    expect(form.locator('[name="service"]')).to_have_value(service)
                    idea = next(f for f in context.request.get(url+f'/api/leads/{lid}').json()['offer_proposals'] if f['service'] == service)
                    expect(form.locator('[name="quote"]')).to_have_value(idea['quote'])
                    expect(form.locator('[name="suggestion"]')).to_have_value(idea['suggestion'])
                    form.locator('[name="country_quote"]').fill('based in London UK')
                    form.locator('[name="fit_notes"]').fill('Fictional business and source relevance reviewed for this isolated UI test.')
                    if campaign == 'B':
                        form.locator('[name="selling_stage"]').select_option('selling_online')
                        form.locator('[name="commerce_quote"]').fill('We sell our own consumer products online.')
                        form.locator('[name="d2c_fit_notes"]').fill('Fictional owned consumer products and direct selling process reviewed.')
                        form.locator('[name="channel_fit_notes"]').fill('Fictional planning only: customer fit and permission remain unknown, qualify before a pilot.')
                        expect(page.locator('#whatsapp-review')).to_be_visible()
                    else:
                        expect(page.locator('#whatsapp-review')).to_be_hidden()
                    page.get_by_role('button', name='Save qualification', exact=True).click()
                    expect(page.locator('#notice')).to_contain_text('Company qualified')
                    page.locator('#sales-workflow > summary').click()
                    page.get_by_text('Prepare a promised audit, concept or demo', exact=True).click()
                    artifact = page.locator('#artifact-form')
                    artifact.locator('[name="kind"]').select_option('faq_demo' if campaign == 'A' else 'whatsapp_flow')
                    artifact.locator('[name="title"]').fill('FICTIONAL reviewed value outline '+campaign)
                    if campaign == 'A':
                        artifact.locator('[name="faq_question"]').fill('How does the published consultation work?')
                        artifact.locator('[name="faq_quote"]').fill('Book a consultation.')
                    artifact.locator('input[type="checkbox"]').check()
                    page.get_by_role('button', name='Create value artifact', exact=True).click()
                    expect(page.locator('#notice')).to_contain_text('Value artifact created')
                    data = context.request.get(url+f'/api/leads/{lid}').json()
                    aid = data['deliverables'][0]['id']
                    downloaded = context.request.get(url+f'/api/artifacts/{aid}/download').text()
                    assert 'Qualification-first outline' in downloaded if campaign == 'B' else 'not a live AI assistant' in downloaded
                    page.locator('#sales-workflow > summary').click()
                    page.get_by_text('Prepare a promised audit, concept or demo', exact=True).click()
                    review = page.locator(f'[data-artifact-review="{aid}"]')
                    review.locator('input[type="checkbox"]').check()
                    review.get_by_role('button', name='Approve artifact', exact=True).click()
                    expect(page.locator('#notice')).to_contain_text('Artifact reviewed')
                    final = context.request.get(url+f'/api/leads/{lid}').json()
                    assert final['offer_workflow']['reviewed_current_artifact_ids'] == [aid]
                    if campaign == 'B':
                        page.locator('details > summary').filter(has_text='02 · Qualify company').click()
                        form = page.locator('#review-form')
                        form.locator('[name="channel_fit_status"]').select_option('confirmed')
                        form.locator('[name="customer_permission_status"]').select_option('confirmed')
                        form.locator('[name="channel_fit_notes"]').fill('FICTIONAL operator review: customer channel and permission setup confirmed only in this test fixture.')
                        page.get_by_role('button', name='Save qualification', exact=True).click()
                        expect(page.locator('#notice')).to_contain_text('Company qualified')
                        changed = context.request.get(url+f'/api/leads/{lid}').json()
                        assert changed['offer_workflow']['reviewed_current_artifact_ids'] == []
                        assert {n['id']: n['state'] for n in changed['offer_workflow']['nodes']}['whatsapp_fit'] == 'confirmed'
                        assert not changed['deliverables'][0]['current_for_review']
                    page.locator('.offer-review').scroll_into_view_if_needed()
                    page.locator('.offer-review').screenshot(path=str(pictures/f'second-workflow-{campaign.lower()}-desktop.png'))
                    page.set_viewport_size({'width': 390, 'height': 844})
                    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                    page.locator('.offer-review').scroll_into_view_if_needed()
                    page.locator('.offer-review').screenshot(path=str(pictures/f'second-workflow-{campaign.lower()}-mobile.png'))
                    page.set_viewport_size({'width': 1440, 'height': 1000})
                # Legacy automatic suggestions are history, not a form default
                # when today's proposal guard rejects their source.
                for usable in (True, False):
                    website = f'https://fictional-quality-{usable}.example/'
                    lid = add_lead(db, 'FICTIONAL quality '+str(usable), website, 'A', website)
                    privacy_quote = 'For example when sending a customer support inquiry.'
                    eid = db.execute('INSERT INTO evidence(lead_id,url,title,text,sha256,fetched_at) VALUES(?,?,?,?,?,?)',
                                     (lid, website+'privacy-policy', 'Privacy Policy', privacy_quote, 'fictional-privacy', time.time()))
                    legacy = {'evidence_id': eid, 'quote': privacy_quote, 'observation': 'An old automatic support suggestion.',
                              'suggestion': 'An old automatic chatbot suggestion.', 'service': 'chatbot',
                              'review_required': True, 'proposal_method': 'explicit_public_signal'}
                    db.execute("UPDATE leads SET status='review',findings=? WHERE id=?", (json.dumps([legacy]), lid))
                    if usable:
                        db.execute('INSERT INTO evidence(lead_id,url,title,text,sha256,fetched_at) VALUES(?,?,?,?,?,?)',
                                   (lid, website, 'Fictional booking source', 'Book a consultation with our team to discuss your project.', 'fictional-booking', time.time()))
                    before = db.all('SELECT * FROM leads WHERE id=?', (lid,))
                    page.reload()
                    page.get_by_role('button', name='Pipeline', exact=True).click()
                    page.locator(f'[data-lead="{lid}"]').click()
                    current = context.request.get(url+f'/api/leads/{lid}').json()
                    if usable:
                        expect(page.locator('#review-form [name="quote"]')).to_have_value(current['offer_proposals'][0]['quote'])
                        expect(page.locator('#review-form [name="service"]')).to_have_value('website_improvement')
                    else:
                        assert current['offer_proposals'] == []
                        expect(page.locator('#review-form [name="quote"]')).to_have_value('')
                    assert db.all('SELECT * FROM leads WHERE id=?', (lid,)) == before
                assert not errors, errors
                browser.close()
            assert db.one('SELECT count(*) n FROM messages')['n'] == 0
            assert db.one('SELECT count(*) n FROM contacts')['n'] == 0
            assert db.one('SELECT count(*) n FROM jobs')['n'] == 0
            report = {'fictional_isolated_fixture': True, 'nodes_checked': 15, 'campaign_a_secondary_offer': 'chatbot',
                      'campaign_b_five_sourced_choices': True, 'campaign_b_selected_offer': 'whatsapp_automation',
                      'unknown_and_confirmed_channel_routes': True, 'actual_form_submission_and_artifact_review': True,
                      'changed_context_invalidates_artifact': True, 'legacy_automatic_suggestion_prefill_rechecked': True,
                      'invalid_source_prefill_cleared_without_record_mutation': True,
                      'desktop_mobile': True, 'overflow': False,
                      'js_errors': len(errors), 'email_probes': 0, 'external_messages': 0, 'checked_at': time.time()}
            (root/'data/second-workflow-ui-check.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
            print(json.dumps(report))
        finally:
            process.terminate()
            process.wait(timeout=15)


if __name__ == '__main__':
    main()
