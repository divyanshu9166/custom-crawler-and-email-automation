import base64
import json
import sys
from types import SimpleNamespace

import pytest
from playwright.async_api import async_playwright

from scripts import check_platform_browser as diagnostic


@pytest.fixture
def probe(settings, monkeypatch):
    settings.platform_browser_enabled = True
    settings.sending_enabled = False
    settings.platform_browser_delay_seconds = 0
    state = {'result': {'state': 'fields_not_ready'}, 'denied': None, 'closed': False, 'evaluations': 0}
    class Page:
        async def evaluate(self, code, *args):
            state['evaluations'] += 1
            if code == diagnostic.DOM_STRUCTURE:
                return {'expected_route': True, 'first_h1_visible': False, 'visible_main_h1_count': 1}
            return state['result']
    class Session:
        last_access_issue = {}
        def __init__(self, configured):
            self.context = SimpleNamespace(on=lambda name, callback: state.update(failed_callback=callback))
        async def __aenter__(self):
            if state.get('error'):
                raise state['error']
            return self
        async def __aexit__(self, *args):
            state['closed'] = True
        async def navigate(self, target):
            for url in state.get('failed_urls', []):
                state['failed_callback'](SimpleNamespace(url=url))
            return Page(), state['denied']
    monkeypatch.setattr(diagnostic.platform_browser, 'BrowserSession', Session)
    return settings, state


async def test_company_diagnostic_explains_missing_fields_without_page_or_account_text(probe):
    settings, state = probe
    result = await diagnostic.check(settings, 'https://linkedin.com/company/fictional', attempts=1)
    assert result['state'] == 'fields_not_ready'
    assert result['structure']['first_h1_visible'] is False
    assert result['structure']['visible_main_h1_count'] == 1
    assert state['closed'] and state['evaluations'] == 2
    assert 'text' not in result and 'cookies' not in result


async def test_company_diagnostic_captured_result_only_reports_counts(probe):
    settings, state = probe
    state['result'] = {'state': 'captured', 'title': 'Fictional Studio',
                       'text': 'Visible company fixture', 'links': ['https://fixture.example/'],
                       'mailto': ['fixture@fixture.example'], 'private_fixture': 'DO-NOT-PRINT'}
    result = await diagnostic.check(settings, 'https://linkedin.com/company/fictional', attempts=1)
    assert result['link_count'] == 1 and result['mailto_count'] == 1
    assert state['closed'] and 'DO-NOT-PRINT' not in json.dumps(result)
    assert 'fixture@fixture.example' not in json.dumps(result)


@pytest.mark.parametrize('worker,sending', [(True, False), (False, True), (True, True)])
async def test_company_diagnostic_controls_prevent_browser_launch(probe, worker, sending):
    settings, state = probe
    settings.worker_enabled, settings.sending_enabled = worker, sending
    state['error'] = AssertionError('Must not launch')
    assert (await diagnostic.check(settings, 'https://linkedin.com/company/fictional'))['state'] == 'controls_not_off'


@pytest.mark.parametrize('code', [403, 429, 999])
async def test_company_diagnostic_denial_never_reads_error_document_or_retries(probe, code):
    settings, state = probe
    state['denied'] = code
    result = await diagnostic.check(settings, 'https://linkedin.com/company/fictional', attempts=1)
    assert result == {'state': 'http_error', 'http_status': code}
    assert state['closed'] and state['evaluations'] == 0
    state['error'] = AssertionError('Held browser must not relaunch')
    assert (await diagnostic.check(settings, 'https://linkedin.com/company/fictional'))['state'] == 'operator_attention'


async def test_company_diagnostic_login_stops_before_structure_inspection(probe):
    settings, state = probe
    state['result'] = {'state': 'login_or_challenge'}
    assert (await diagnostic.check(settings, 'https://linkedin.com/company/fictional'))['state'] == 'login_or_challenge'
    assert state['closed'] and state['evaluations'] == 1


async def test_company_diagnostic_profile_lock_only_reports_known_reason(probe):
    settings, state = probe
    state['error'] = RuntimeError('The profile appears to be in use by another Chromium process PRIVATE-LOG-FIXTURE')
    result = await diagnostic.check(settings, 'https://linkedin.com/company/fictional')
    assert result == {'state': 'browser_unavailable', 'error_type': 'RuntimeError', 'reason': 'profile_in_use'}
    assert 'PRIVATE-LOG-FIXTURE' not in json.dumps(result)


async def test_company_diagnostic_failed_requests_only_report_bounded_host_counts(probe):
    settings, state = probe
    state['failed_urls'] = ['https://licdn.com/private/path?token=PRIVATE-FIXTURE'] * 2
    state['failed_urls'] += [f'https://host{i}.example/private?token=PRIVATE-FIXTURE' for i in range(25)]
    result = await diagnostic.check(settings, 'https://linkedin.com/company/fictional', attempts=1)
    assert result['failed_request_hosts']['licdn.com'] == 2
    assert len(result['failed_request_hosts']) == 20
    assert 'PRIVATE-FIXTURE' not in json.dumps(result) and '/private' not in json.dumps(result)


def test_cli_decodes_supplied_repository_reader_for_current_container(settings, monkeypatch, capsys):
    reader = '() => ({state:"fields_not_ready"})'
    observed = []
    async def capture(configured, url, *, reader_override=None):
        observed.append(reader_override)
        return {'state': 'fields_not_ready', 'reader_source': 'supplied'}
    monkeypatch.setattr(diagnostic, 'Settings', lambda: settings)
    monkeypatch.setattr(diagnostic, 'check', capture)
    monkeypatch.setattr(sys, 'argv', ['check', '--reader-base64', base64.b64encode(reader.encode()).decode()])
    assert diagnostic.main() == 2
    assert observed == [reader] and json.loads(capsys.readouterr().out)['reader_source'] == 'supplied'


@pytest.mark.parametrize('encoded', ['not_base64!', 'a' * 100_001], ids=['invalid', 'oversized'])
def test_cli_rejects_invalid_or_unbounded_reader_before_launch(monkeypatch, encoded):
    monkeypatch.setattr(sys, 'argv', ['check', '--reader-base64', encoded])
    def forbidden():
        raise AssertionError('Invalid input must fail before configuration or browser access')
    monkeypatch.setattr(diagnostic, 'Settings', forbidden)
    with pytest.raises(SystemExit) as error:
        diagnostic.main()
    assert error.value.code == 2


async def test_structure_reader_reports_visible_company_fields_and_ignores_private_shell():
    url = 'https://www.linkedin.com/company/fictional/about/'
    html = '''<h1 hidden>PRIVATE HIDDEN HEADING</h1><nav><dl><dt>PRIVATE NAV LABEL</dt></dl></nav>
    <main><h1>Fictional Studio</h1><h2>Overview</h2><a href="/company/fictional/about/?token=PRIVATE-QUERY">About</a>
    <a href="/company/fictional/about/">PRIVATE FOLLOWER NAME follows this page</a>
    <article><h2>PRIVATE FEED HEADING</h2></article>
    <dl><dt>Industry</dt><dd>Fictional consulting</dd></dl>
    <div role="dialog"><dl><dt>PRIVATE DIALOG LABEL</dt></dl></div></main>'''
    async with async_playwright() as runtime:
        browser = await runtime.chromium.launch()
        try:
            page = await browser.new_page()
            await page.route('**/*', lambda route: route.fulfill(content_type='text/html', body=html))
            await page.goto(url)
            result = await page.evaluate(diagnostic.DOM_STRUCTURE, url)
            assert result['expected_route'] and not result['first_h1_visible']
            assert result['visible_main_h1_count'] == 1
            assert result['matching_about_link_count'] == 1
            assert result['definition_labels'] == ['Industry']
            assert result['visible_dialog_present']
            assert result['main_headings'] == [
                {'tag': 'H1', 'label': 'Fictional Studio', 'classes': ''},
                {'tag': 'H2', 'label': 'Overview', 'classes': ''},
            ]
            assert result['company_navigation'] == [
                {'label': 'About', 'path': '/company/fictional/about/'},
                {'label': '', 'path': '/company/fictional/about/'},
            ]
            assert 'PRIVATE' not in json.dumps(result)
            await page.goto('https://www.linkedin.com/login')
            assert await page.evaluate(diagnostic.DOM_STRUCTURE, url) == {'expected_route': False}
        finally:
            await browser.close()


async def test_structure_reader_explains_h2_only_layout_without_assuming_company_identity():
    url = 'https://www.linkedin.com/company/fictional/about/'
    html = '<main><h2>Overview</h2><h2>Sign in for more</h2><h2>Website</h2><h2>Industry</h2></main>'
    async with async_playwright() as runtime:
        browser = await runtime.chromium.launch()
        try:
            page = await browser.new_page()
            await page.route('**/*', lambda route: route.fulfill(content_type='text/html', body=html))
            await page.goto(url)
            result = await page.evaluate(diagnostic.DOM_STRUCTURE, url)
            assert result['visible_h1_count'] == 0
            assert result['visible_main_h2_count'] == 4
            assert result['definition_labels'] == [] and result['company_navigation'] == []
            assert [h['label'] for h in result['main_headings']] == ['Overview', 'Sign in for more', 'Website', 'Industry']
            assert [item['label'] for item in result['field_markers']] == ['Website', 'Industry']
        finally:
            await browser.close()
