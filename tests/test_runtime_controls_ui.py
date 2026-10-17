"""Chromium exercises the actual Settings form with isolated routed API responses."""
import json
from pathlib import Path

import pytest
from bs4 import BeautifulSoup
from playwright.sync_api import expect, sync_playwright

from outreach.preferences import Preferences


ROOT = Path(__file__).resolve().parents[1]
ORIGIN = 'https://outreach.example.com'


@pytest.fixture(scope='module')
def browser():
    with sync_playwright() as runtime:
        instance = runtime.chromium.launch()
        yield instance
        instance.close()


@pytest.mark.parametrize('mobile', [False, True])
def test_research_controls_save_reload_and_preserve_sending_off(browser, settings, mobile):
    settings.sending_enabled = False
    state = {**Preferences(settings).public(), 'paused': True, 'demo': False}
    writes, errors = [], []
    soup = BeautifulSoup((ROOT/'outreach/static/index.html').read_text(encoding='utf-8'), 'html.parser')
    section = soup.select_one('#settings')
    del section['hidden']
    html = '<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/static/style.css"><main>'+str(section)+'</main><script src="/static/settings.js"></script>'
    context = browser.new_context(viewport={'width': 390 if mobile else 1440, 'height': 1000})
    def route(request):
        path = request.request.url.removeprefix(ORIGIN)
        if path == '/api/settings/research':
            value = request.request.post_data_json
            writes.append(value)
            state.update(value)
            request.fulfill(json=state)
        elif path == '/api/settings':
            request.fulfill(json=state)
        elif path.startswith('/static/'):
            filename = path.removeprefix('/static/')
            request.fulfill(content_type='text/css' if filename.endswith('.css') else 'text/javascript',
                            body=(ROOT/'outreach/static'/filename).read_text(encoding='utf-8'))
        else:
            request.fulfill(content_type='text/html', body=html)
    context.route('**/*', route)
    page = context.new_page()
    page.on('pageerror', lambda error: errors.append(str(error)))
    def load():
        page.goto(ORIGIN)
        page.evaluate('''async () => {
          WorkbenchSettings.init({esc:value=>String(value),notice:()=>{},refresh:async()=>{},
            api:async (url,method='GET',body)=>{const r=await fetch(url,{method,headers:{'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined});return r.json();}});
          await WorkbenchSettings.load();
        }''')
    try:
        load()
        form = page.locator('#research-settings-form')
        expect(form.locator('[name=linkedin_contact_info_enabled]')).not_to_be_checked()
        form.locator('[name=linkedin_contact_info_enabled]').check()
        form.locator('[name=social_posts_max_posts]').fill('2')
        form.locator('[name=social_posts_max_profiles]').fill('1')
        form.get_by_role('button', name='Save research controls').click()
        expect(page.locator('#research-settings-result')).to_contain_text('Sending is paused')
        assert writes[0]['linkedin_contact_info_enabled'] is True
        assert writes[0]['social_posts_max_posts'] == 2 and writes[0]['social_posts_max_profiles'] == 1
        assert 'sending_enabled' not in writes[0] and not state['sending_enabled']
        load()
        expect(form.locator('[name=linkedin_contact_info_enabled]')).to_be_checked()
        expect(form.locator('[name=social_posts_max_posts]')).to_have_value('2')
        expect(page.locator('#runtime-settings-form [name=sending_enabled]')).not_to_be_checked()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        assert not errors
    finally:
        context.close()


@pytest.mark.parametrize('mobile', [False, True])
def test_controls_save_boolean_flags_show_failures_and_reload(browser, settings, mobile):
    settings.sending_enabled = False
    state = {**Preferences(settings).public(), 'paused': True, 'demo': False}
    writes, errors = [], []
    reject = {'value': False}
    soup = BeautifulSoup((ROOT / 'outreach/static/index.html').read_text(encoding='utf-8'), 'html.parser')
    section = soup.select_one('#settings')
    del section['hidden']
    html = '<!doctype html><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="stylesheet" href="/static/style.css"><main>' + str(section) + '</main><script src="/static/settings.js"></script>'
    context = browser.new_context(viewport={'width': 390 if mobile else 1440, 'height': 900})
    def respond(route):
        path = route.request.url.removeprefix(ORIGIN)
        if path == '/api/settings/runtime':
            writes.append(route.request.post_data_json)
            if reject['value']:
                route.fulfill(status=503, json={'detail': 'Settings storage unavailable'})
            else:
                state.update(writes[-1], paused=True)
                route.fulfill(json=state)
        elif path == '/api/settings':
            route.fulfill(json=state)
        elif path.startswith('/static/'):
            filename = path.removeprefix('/static/')
            route.fulfill(content_type='text/css' if filename.endswith('.css') else 'text/javascript',
                          body=(ROOT / 'outreach/static' / filename).read_text(encoding='utf-8'))
        else:
            route.fulfill(content_type='text/html', body=html)
    context.route('**/*', respond)
    page = context.new_page()
    page.on('pageerror', lambda error: errors.append(str(error)))
    def load():
        page.goto(ORIGIN)
        page.evaluate('''async () => {
          WorkbenchSettings.init({esc: value=>String(value),notice:()=>{},refresh:async()=>{},
            api:async (url,method='GET',body)=>{
              const response=await fetch(url,{method,headers:{'Content-Type':'application/json'},body:body?JSON.stringify(body):undefined});
              const data=await response.json();if(!response.ok)throw new Error(data.detail);return data;
            }});
          await WorkbenchSettings.load();
        }''')
    try:
        load()
        form = page.locator('#runtime-settings-form')
        worker = form.locator('[name=worker_enabled]')
        sending = form.locator('[name=sending_enabled]')
        expect(worker).not_to_be_checked()
        expect(sending).not_to_be_checked()
        worker.check()
        form.get_by_role('button', name='Save automation controls').click()
        expect(page.locator('#runtime-settings-result')).to_contain_text('controls saved')
        assert writes == [{'worker_enabled': True, 'sending_enabled': False}]
        load()
        expect(worker).to_be_checked()
        expect(sending).not_to_be_checked()
        sending.check()
        form.get_by_role('button', name='Save automation controls').click()
        for label in ['Worker ON', 'Sending ON', 'paused']:
            expect(page.locator('#runtime-summary')).to_contain_text(label)
        reject['value'] = True
        worker.uncheck()
        form.get_by_role('button', name='Save automation controls').click()
        expect(page.locator('#runtime-settings-result')).to_contain_text('storage unavailable')
        expect(form.get_by_role('button', name='Save automation controls')).to_be_enabled()
        assert state['worker_enabled'] is True and state['paused'] is True
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        assert errors == []
        assert all(type(value) is bool for patch in writes for value in patch.values())
        assert 'password' not in json.dumps(writes)
    finally:
        context.close()
