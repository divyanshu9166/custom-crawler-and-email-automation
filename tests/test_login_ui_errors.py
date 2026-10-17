"""Real Chromium sign-in UI checks with local routed responses; no real credentials."""
import json
from pathlib import Path

import pytest
from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
ORIGIN = 'https://outreach.example.com'


@pytest.fixture(scope='module')
def browser():
    with sync_playwright() as runtime:
        instance = runtime.chromium.launch()
        yield instance
        instance.close()


def sign_in(browser, status, content_type, body, *, abort=False):
    context = browser.new_context()
    page = context.new_page()
    calls = {'login': 0, 'root': 0}

    def respond(route):
        path = route.request.url.removeprefix(ORIGIN)
        if path == '/api/login':
            calls['login'] += 1
            if abort:
                route.abort('connectionfailed')
            else:
                route.fulfill(status=status, content_type=content_type, body=body)
        elif path == '/static/login.js':
            route.fulfill(content_type='text/javascript', body=(ROOT/'outreach/static/login.js').read_text())
        elif path == '/':
            calls['root'] += 1
            html = '<h1>Fixture dashboard</h1>' if calls['root'] > 1 else (ROOT/'outreach/static/login.html').read_text()
            route.fulfill(content_type='text/html', body=html)
        else:
            route.fulfill(content_type='text/css', body='')

    context.route('**/*', respond)
    page.goto(ORIGIN)
    page.locator('[name=username]').fill('fixture-admin')
    page.locator('[name=password]').fill('fixture-ui-login-value')
    page.get_by_role('button', name='Sign in', exact=True).click()
    return context, page, calls


@pytest.mark.parametrize('status,content_type,body,expected', [
    (502, 'text/html', '<!DOCTYPE html><script>window.injected=true</script>Gateway unavailable', 'HTTP 502'),
    (530, 'application/json', '{"status":530,"detail":"Tunnel unavailable"}', 'HTTP 530'),
    (200, 'text/html', '<!DOCTYPE html><h1>Proxy login</h1>', 'unexpected page (HTTP 200)'),
    (200, 'application/json', '<!DOCTYPE html>Invalid JSON response', 'invalid response (HTTP 200)'),
    (401, 'application/json', '{"detail":"Username or password is incorrect"}', 'Username or password is incorrect'),
    (403, 'application/json', '{"detail":"Use the configured workspace URL to sign in"}', 'configured workspace URL'),
    (429, 'application/json', '{"detail":"Too many sign-in attempts; wait one minute"}', 'wait one minute'),
    (422, 'application/json', '{"detail":[{"loc":["body","username"],"msg":"Field required"}]}', 'HTTP 422'),
    (200, 'application/json', '{"signed_in":false}', 'server did not confirm sign-in'),
])
def test_failed_sign_in_keeps_form_usable_and_does_not_retry_or_navigate(browser, status, content_type, body, expected):
    context, page, calls = sign_in(browser, status, content_type, body)
    try:
        expect(page.locator('#login-error')).to_contain_text(expected)
        expect(page.get_by_role('button', name='Sign in', exact=True)).to_be_enabled()
        assert 'Unexpected token' not in page.locator('#login-error').inner_text()
        assert page.evaluate('window.injected') is None
        assert calls == {'login': 1, 'root': 1}
    finally:
        context.close()


def test_network_failure_is_readable_and_does_not_automatically_resubmit_credentials(browser):
    context, page, calls = sign_in(browser, 0, '', '', abort=True)
    try:
        expect(page.locator('#login-error')).to_contain_text('Cannot reach the sign-in service')
        expect(page.get_by_role('button', name='Sign in', exact=True)).to_be_enabled()
        assert calls == {'login': 1, 'root': 1}
    finally:
        context.close()


def test_only_confirmed_json_sign_in_navigates_to_dashboard(browser):
    context, page, calls = sign_in(browser, 200, 'application/json', json.dumps({'signed_in': True}))
    try:
        expect(page.get_by_role('heading', name='Fixture dashboard')).to_be_visible()
        assert calls == {'login': 1, 'root': 2}
    finally:
        context.close()
