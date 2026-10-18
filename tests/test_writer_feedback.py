"""Connection diagnosis is separate from AI copy quality; secrets stay private."""
import json
from pathlib import Path

import httpx
import pytest
from bs4 import BeautifulSoup
from fastapi.testclient import TestClient
from playwright.sync_api import sync_playwright, expect

from outreach import email_writer
from outreach.app import create_app
from outreach.preferences import Preferences

REAL_CLIENT = httpx.Client
ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('condition', ['stop', 'length', 'empty', 'timeout', '401', '404', '429'])
def test_connection_returns_distinct_persisted_verdicts_without_key_echo(db, settings, monkeypatch, condition):
    settings.draft_api_key = 'fictional-private-writer-key'
    settings.draft_model = 'deepseek-ai/deepseek-v4.1-flash'
    settings.draft_timeout_seconds = 90
    timeouts = []
    def handle(request):
        body = json.loads(request.content)
        assert body['max_tokens'] == 128 and body['model'] == settings.draft_model
        assert 'No prospect data' in body['messages'][1]['content']
        if condition == 'timeout':
            raise httpx.ReadTimeout(settings.draft_api_key, request=request)
        if condition.isdigit():
            return httpx.Response(int(condition), text=settings.draft_api_key)
        return httpx.Response(200, json={'choices': [{'finish_reason': 'length' if condition == 'length' else 'stop',
            'message': {'content': '' if condition in {'empty', 'length'} else 'OK', 'reasoning_content': 'private synthetic reasoning'}}]})
    def client(**kwargs):
        timeouts.append(kwargs['timeout'])
        return REAL_CLIENT(transport=httpx.MockTransport(handle), **kwargs)
    monkeypatch.setattr(email_writer.httpx, 'Client', client)
    api = TestClient(create_app(settings), headers={'Authorization': 'Bearer '+settings.api_token})
    result = api.post('/api/providers/writer/test')
    check = api.get('/api/settings').json()['writer_last_check']
    if condition in {'stop', 'length', 'empty'}:
        assert result.status_code == 200 and result.json()['connection_ok'] is True
        assert result.json()['ready'] is (condition == 'stop')
        assert check['state'] == ('ready' if condition == 'stop' else 'output_incomplete')
    else:
        assert result.status_code == 400 and check['state'] == 'failed'
        assert ('timed out' in check['note']) if condition == 'timeout' else f'HTTP {condition}' in check['note']
    assert timeouts == [60] and settings.draft_timeout_seconds == 90
    assert settings.draft_api_key not in result.text+json.dumps(check)
    assert 'private synthetic reasoning' not in result.text+json.dumps(check)
    assert not db.one('SELECT id FROM messages')


def test_saved_key_roundtrip_and_test_invalidation_are_independent(db, settings, monkeypatch):
    prefs = Preferences(settings)
    prefs.update_writer(db, {'draft_api_key': 'fictional-saved-secret', 'draft_model': 'fixture-model'})
    assert settings.draft_api_key not in json.dumps(prefs.public())
    restored = settings.model_copy(update={'draft_api_key': ''})
    Preferences(restored)
    assert restored.draft_api_key == settings.draft_api_key
    monkeypatch.setattr(email_writer, 'test_connection', lambda s: {'ready': True, 'connection_ok': True, 'note': 'Synthetic request passed.'})
    api = TestClient(create_app(settings), headers={'Authorization': 'Bearer '+settings.api_token})
    assert api.post('/api/providers/writer/test').json()['ready']
    assert api.get('/api/settings').json()['writer_last_check']['state'] == 'ready'
    prefs.update_writer(db, {'draft_model': 'new-fixture-model'})
    assert api.get('/api/settings').json()['writer_last_check'] is None


def test_settings_change_during_test_cannot_claim_current_configuration_ready(db, settings, monkeypatch):
    prefs = Preferences(settings)
    def check(frozen):
        prefs.update_writer(db, {'draft_model': 'replacement-model'})
        assert frozen.draft_model != settings.draft_model
        return {'ready': True, 'note': 'Old configuration worked.'}
    monkeypatch.setattr(email_writer, 'test_connection', check)
    api = TestClient(create_app(settings), headers={'Authorization': 'Bearer '+settings.api_token})
    result = api.post('/api/providers/writer/test')
    assert result.status_code == 400 and 'superseded' in result.text
    assert api.get('/api/settings').json()['writer_last_check'] is None


@pytest.mark.parametrize('problem', ['unsafe_finish_reason', 'server_deadline'])
def test_diagnostics_do_not_echo_untrusted_metadata_or_leave_running_state(db, settings, monkeypatch, problem):
    settings.draft_api_key, settings.draft_model = 'fictional-private-check-key', 'fictional-model'
    if problem == 'unsafe_finish_reason':
        def client(**kwargs):
            return REAL_CLIENT(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={
                'choices': [{'finish_reason': settings.draft_api_key, 'message': {'content': '', 'reasoning_content': settings.draft_api_key}}]})), **kwargs)
        monkeypatch.setattr(email_writer.httpx, 'Client', client)
    else:
        def timed_out(s):
            raise TimeoutError()
        monkeypatch.setattr(email_writer, 'test_connection', timed_out)
    api = TestClient(create_app(settings), headers={'Authorization': 'Bearer '+settings.api_token})
    result = api.post('/api/providers/writer/test')
    saved = api.get('/api/settings').json()['writer_last_check']
    assert settings.draft_api_key not in result.text+json.dumps(saved)
    if problem == 'unsafe_finish_reason':
        assert result.status_code == 200 and result.json()['finish_reason'] == 'unknown'
        assert saved['state'] == 'output_incomplete'
    else:
        assert result.status_code == 400 and '65 seconds' in result.text
        assert saved['state'] == 'failed'


@pytest.mark.parametrize('mobile', [False, True])
@pytest.mark.parametrize('outcome', ['ready', 'failure', 'timeout'])
def test_pending_check_is_visible_counts_time_and_always_unblocks(settings, mobile, outcome):
    settings.draft_api_key, settings.draft_model = 'fictional-check-key', 'deepseek-ai/deepseek-v4.1-flash'
    public = {**Preferences(settings).public(), 'writer_last_check': None}
    soup = BeautifulSoup((ROOT/'outreach/static/index.html').read_text(encoding='utf-8'), 'html.parser')
    section = soup.select_one('#settings')
    del section['hidden']
    html = '<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/static/style.css"><main>'+str(section)+'</main><script src="/static/settings.js"></script>'
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch()
        context = browser.new_context(viewport={'width': 390 if mobile else 1440, 'height': 1000})
        def route(r):
            path = r.request.url.removeprefix('https://feedback.example')
            if path.startswith('/static/'):
                f = ROOT/'outreach/static'/path.removeprefix('/static/')
                r.fulfill(content_type='text/css' if f.suffix == '.css' else 'text/javascript', body=f.read_text(encoding='utf-8'))
            else:
                r.fulfill(content_type='text/html', body=html)
        context.route('**/*', route)
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        try:
            page.clock.install(time='2026-10-18T06:00:00Z')
            page.clock.pause_at('2026-10-18T06:01:00Z')
            page.goto('https://feedback.example/')
            page.evaluate('''async s=>{window.calls=0;WorkbenchSettings.init({esc:x=>String(x),notice:()=>{},refresh:async()=>{},api:async path=>{
              if(path==='/api/settings')return s;
              if(path==='/api/providers/writer/test'){window.calls++;return new Promise((resolve,reject)=>{window.finishTest=resolve;window.failTest=reject;});}
              throw new Error('Unexpected request');}});await WorkbenchSettings.load();}''', public)
            test = page.get_by_role('button', name='Test AI connection', exact=True)
            page.locator('[name=draft_model]').fill('unsaved-fixture-model')
            test.click()
            expect(page.locator('#writer-test-result')).to_contain_text('Unsaved AI settings')
            assert page.evaluate('window.calls') == 0
            page.locator('[name=draft_model]').fill(settings.draft_model)
            test.click()
            result = page.locator('#writer-test-result')
            expect(result).to_be_in_viewport()
            expect(result).to_contain_text('0s elapsed')
            expect(page.locator('#writer-test')).to_be_disabled()
            expect(page.locator('#writer-test')).to_contain_text('Testing')
            expect(page.get_by_role('button', name='Save AI writer settings', exact=True)).to_be_disabled()
            page.clock.fast_forward(2000)
            expect(result).to_contain_text('2s elapsed')
            if outcome == 'ready':
                page.evaluate("window.finishTest({ready:true,note:'Synthetic connection passed.'})")
                expect(result).to_contain_text('Synthetic connection passed')
            elif outcome == 'failure':
                page.evaluate("window.failTest(new Error('AI writing endpoint returned HTTP 401'))")
                expect(result).to_contain_text('HTTP 401')
            else:
                page.clock.fast_forward(75001)
                expect(result).to_contain_text('exceeded 75 seconds')
                page.evaluate("window.finishTest({ready:true,note:'Late response must not replace timeout.'})")
                expect(result).not_to_contain_text('Late response')
            expect(page.get_by_role('button', name='Test AI connection', exact=True)).to_be_enabled()
            expect(page.get_by_role('button', name='Save AI writer settings', exact=True)).to_be_enabled()
            assert page.evaluate('window.calls') == 1 and not errors
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth')
        finally:
            context.close()
            browser.close()
