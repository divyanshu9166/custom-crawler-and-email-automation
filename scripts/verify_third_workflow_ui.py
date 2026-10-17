"""Actual Chromium approval/revision controls; isolated fictional data, sending off."""
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
from unittest.mock import patch
import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from playwright.sync_api import sync_playwright, expect
from demo import seed
from outreach.campaigns import approve, create_drafts
from outreach.config import Settings
from outreach.db import DB


def main():
    root = Path(__file__).resolve().parents[1]
    errors = []
    with tempfile.TemporaryDirectory(prefix='third-workflow-ui-') as temp:
        seed(Path(temp))
        db = DB(Path(temp)/'outreach.db')
        db.execute("UPDATE contacts SET verification='safe',verified_at=?", (time.time(),))
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        base = f'http://127.0.0.1:{port}'
        identity = {'sender_name': 'FICTIONAL Test Sender', 'sender_company': 'FICTIONAL Studio',
                    'sender_email': 'fixture@sender.example', 'sender_website': 'https://sender.example/',
                    'postal_address': 'FICTIONAL isolated test address'}
        settings = Settings(_env_file=None, data_dir=Path(temp), public_url=base, **identity)
        # Controlled provider output exercises the actual writer, not demo template approval.
        # This isolated fixture establishes UI state transitions, not live model quality.
        settings.draft_api_key = 'fictional-local-ui-key'
        settings.draft_model = 'fictional-ui-provider'
        lead = db.one('SELECT * FROM leads WHERE id=1')
        finding = json.loads(lead['findings'])[0]
        bodies = [f"{lead['company']}: {finding['observation']} {finding['suggestion']} Would an outline be useful?",
                  'A short explanation of the first enquiry step could give visitors more context. Would you like to explore that section?',
                  'We could start with a small outline around your published enquiry invitation, then review it together. Is that useful?',
                  'I will leave the enquiry-page idea with you. If it becomes relevant, we can discuss a suitable next step.']
        fixture = {'messages': [{'step': i, 'subject': f'FICTIONAL UI enquiry idea {i+1}', 'body': body,
                                'support': [{'evidence_id': finding['evidence_id'], 'quote': finding['quote']}]}
                               for i, body in enumerate(bodies)]}
        real_client = httpx.Client
        def controlled_client(**kw):
            return real_client(transport=httpx.MockTransport(lambda _: httpx.Response(200, json={
                'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(fixture)}}]})), **kw)
        with patch('outreach.email_writer.httpx.Client', controlled_client):
            create_drafts(db, settings, 1)
        approve(db, settings, 1, 'FICTIONAL eligibility record for isolated UI testing only', 'FICTIONAL founder owns the website')
        token = secrets.token_urlsafe(36)
        env = {**os.environ, 'DATA_DIR': temp, 'PUBLIC_URL': base, 'WORKER_ENABLED': 'false',
               'SENDING_ENABLED': 'false', 'API_TOKEN': token, 'ADMIN_PASSWORD': secrets.token_urlsafe(32),
               **{k.upper(): v for k, v in identity.items()}}
        process = subprocess.Popen([sys.executable, '-m', 'uvicorn', 'outreach.app:create_app', '--factory',
                                    '--host', '127.0.0.1', '--port', str(port), '--no-access-log'],
                                   cwd=root, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        try:
            for _ in range(60):
                try:
                    urllib.request.urlopen(base+'/health', timeout=1)
                    break
                except OSError:
                    time.sleep(.2)
            else:
                raise RuntimeError('Isolated server did not start')
            with sync_playwright() as p:
                browser = p.chromium.launch()
                context = browser.new_context(viewport={'width': 1440, 'height': 1000},
                                              extra_http_headers={'Authorization': 'Bearer '+token})
                page = context.new_page()
                page.on('pageerror', lambda e: errors.append(str(e)))
                page.goto(base)
                page.get_by_role('button', name='Pipeline', exact=True).click()
                page.locator('[data-lead="1"]').click()
                page.get_by_text('Return unsent pilot to review', exact=True).click()
                form = page.locator('[data-revise-sequence="1"]')
                form.locator('[name="note"]').fill('FICTIONAL: revise the initial pilot before any submission')
                form.locator('input[type="checkbox"]').check()
                page.locator('.contact').screenshot(path=str(root/'docs/screenshots/third-workflow-revision-desktop.png'))
                page.get_by_role('button', name='Return to draft review', exact=True).click()
                expect(page.locator('#notice')).to_contain_text('Approval revoked')
                assert db.one('SELECT status FROM contacts')['status'] == 'new'
                assert db.one("SELECT COUNT(*) n FROM messages WHERE state='draft'")['n'] == 4
                draft = page.locator('[data-edit]').first
                original = draft.locator('[name="body"]').input_value()
                draft.locator('[name="body"]').fill(original+'\n\nFICTIONAL: outline the first consultation before testing changes.')
                draft.get_by_role('button', name='Save draft', exact=True).click()
                expect(page.locator('#notice')).to_contain_text('Draft saved')
                form = page.locator('[data-approve="1"]')
                form.locator('[name="eligibility_basis"]').fill('FICTIONAL eligibility record and contact history reviewed for this isolated test')
                form.locator('[name="contact_relevance"]').fill('FICTIONAL founder owns the reviewed website journey')
                form.locator('input[type="checkbox"]').check()
                form.get_by_role('button', name='Approve sequence', exact=True).click()
                expect(page.locator('#notice')).to_contain_text('Sequence approved')
                assert db.one("SELECT COUNT(*) n FROM messages WHERE state='queued'")['n'] == 4
                assert json.loads(db.one("SELECT detail FROM events WHERE kind='sequence_approved' ORDER BY id DESC")['detail'])['review_snapshot']
                page.set_viewport_size({'width': 390, 'height': 844})
                page.get_by_text('Return unsent pilot to review', exact=True).click()
                assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
                page.locator('.contact').screenshot(path=str(root/'docs/screenshots/third-workflow-revision-mobile.png'))
                page.locator('#sales-workflow > summary').click()
                page.get_by_text('Qualify and advance the opportunity', exact=True).click()
                expect(page.locator('#sales-form [name="baseline_notes"]')).to_be_visible()
                assert not errors, errors
                browser.close()
            assert db.one("SELECT COUNT(*) n FROM messages WHERE state IN ('sent','sending','uncertain')")['n'] == 0
            assert db.one('SELECT COUNT(*) n FROM jobs')['n'] == 0
            result = {'isolated_fictional_data': True, 'sending_enabled': False, 'actual_chromium_forms': True,
                      'approval_revision_and_copy_edit': True, 'new_approval_snapshot': True,
                      'baseline_field_visible': True, 'desktop_mobile': True, 'overflow': False,
                      'js_errors': len(errors), 'messages_submitted': 0, 'provider_jobs': 0}
            (root/'data/third-workflow-ui-check.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
            print(json.dumps(result))
        finally:
            process.terminate()
            process.wait(timeout=10)


if __name__ == '__main__':
    main()
