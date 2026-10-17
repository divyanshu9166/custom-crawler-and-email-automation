"""Actual Chromium parsing of the h2/p/div format observed on the user's VPS."""
import json
from pathlib import Path

import pytest
from playwright.async_api import async_playwright

from outreach import platform_browser


READER = (Path(__file__).resolve().parents[1] / 'outreach/static/platform-reader.js').read_text(encoding='utf-8')
URL = 'https://www.linkedin.com/company/bright/about/'


def row(label, value):
    return f'<div class="random-row"><div class="random-label"><p>{label}</p></div><div class="random-value">{value}</div></div>'


def modern(fields=None, company='Bright Studio'):
    if fields is None:
        fields = row('Website', '<a href="https://bright-demo.com/?tracking=ignore">Visit website</a>')
        fields += row('Industry', '<p>Business consulting</p>')
        fields += row('Email', '<p>Public enquiries: <a href="mailto:hello@bright-demo.com">Email</a></p>')
        fields += row('Headquarters', '<p>London, UK</p>')
    return f'''<nav><h1>PRIVATE ACCOUNT HEADING</h1></nav><h1 hidden>PRIVATE HIDDEN HEADING</h1>
    <main><header><h2>{company}</h2><p>PRIVATE FOLLOWER NAME follows this page</p></header>
    <section><h2>Overview</h2><p>Bright Studio is a UK consulting business.</p>{fields}</section>
    <section><h2>Interested in working with us in the future?</h2><p>PRIVATE CAREER TEXT</p></section>
    <section><h2>Locations</h2>{row('Email', '<a href="mailto:outside@private-demo.com">Outside</a>')}</section>
    <article><h2>PRIVATE POST HEADING</h2>{row('Website', '<a href="https://private-demo.com/">Outside</a>')}</article></main>'''


@pytest.fixture
async def read():
    async with async_playwright() as runtime:
        browser = await runtime.chromium.launch()
        async def evaluate(html, url=URL):
            page = await browser.new_page()
            try:
                await page.route('**/*', lambda route: route.fulfill(content_type='text/html', body=html))
                await page.goto(url)
                return await page.evaluate(READER)
            finally:
                await page.close()
        yield evaluate
        await browser.close()


async def test_observed_h2_overview_and_paragraph_rows_capture_only_company_fields(read):
    result = await read(modern())
    assert result['state'] == 'captured' and result['layout'] == 'linkedin_overview_rows'
    assert result['title'] == 'Bright Studio'
    assert result['links'] == ['https://bright-demo.com/']
    assert result['mailto'] == ['hello@bright-demo.com']
    assert 'UK consulting' in result['text'] and 'London, UK' in result['text']
    assert 'PRIVATE' not in json.dumps(result) and 'private-demo.com' not in json.dumps(result)


async def test_modern_field_labels_allow_nested_spans_and_do_not_depend_on_hashed_classes(read):
    html = modern().replace('<p>Website</p>', '<p><span>Website</span></p>').replace('random-', 'changed-')
    result = await read(html)
    assert result['state'] == 'captured' and result['links'] == ['https://bright-demo.com/']


async def test_website_and_email_link_labels_can_repeat_the_field_name(read):
    fields = row('Website', '<a href="https://bright-demo.com">Website</a>')
    fields += row('Industry', '<p>Consulting</p>') + row('Email', '<a href="mailto:hello@bright-demo.com">Email</a>')
    result = await read(modern(fields))
    assert result['state'] == 'captured'
    assert result['links'] == ['https://bright-demo.com/'] and result['mailto'] == ['hello@bright-demo.com']


async def test_modern_rows_exclude_dialog_and_hidden_emails(read):
    private = '<div role="dialog"><a href="mailto:private@private-demo.com">PRIVATE DIALOG</a></div><span hidden>PRIVATE HIDDEN</span>'
    html = modern().replace('Email</a></p>', 'Email</a>' + private + '</p>')
    result = await read(html)
    assert result['state'] == 'captured' and result['mailto'] == ['hello@bright-demo.com']
    assert 'PRIVATE' not in json.dumps(result)


@pytest.mark.parametrize('html', [
    '<main><h2>Overview</h2><h2>Sign in for more</h2><p>Website</p><p>Industry</p></main>',
    modern(row('Website', '<a href="https://bright-demo.com">Website</a>')),
    modern(row('Email', '<a href="mailto:hello@bright-demo.com">Email</a>') + row('Phone', '<p>12345</p>')),
    modern().replace('<h2>Overview</h2>', '<h2>Other section</h2>'),
    modern().replace('<h2>Bright Studio</h2>', ''),
])
async def test_generic_headings_or_incomplete_rows_do_not_establish_company_capture(read, html):
    result = await read(html)
    assert result['state'] == 'fields_not_ready'
    assert 'text' not in result and 'mailto' not in result


async def test_conflicting_duplicate_field_values_stay_ambiguous(read):
    fields = row('Website', '<a href="https://bright-demo.com">Website</a>')
    fields += row('Website', '<a href="https://other-demo.com">Website</a>') + row('Industry', '<p>Consulting</p>')
    result = await read(modern(fields))
    assert result['state'] == 'fields_not_ready' and result['reason'] == 'ambiguous_company_field_rows'


async def test_legacy_definition_list_with_hidden_first_heading_still_captures(read):
    html = '''<h1 hidden>PRIVATE HEADING</h1><main><h1>Bright Studio</h1>
    <nav><a href="/company/bright/about/">About</a></nav><p>Bright is a UK business.</p>
    <dl><dt>Website</dt><dd><a href="https://bright-demo.com">Website</a></dd>
    <dt>Industry</dt><dd>Consulting</dd></dl></main>'''
    result = await read(html)
    assert result['state'] == 'captured' and result['layout'] == 'linkedin_definition_list'
    assert result['title'] == 'Bright Studio' and result['links'] == ['https://bright-demo.com/']


async def test_modern_page_with_visible_login_prompt_stops_before_extraction(read):
    result = await read('<input type="password">' + modern())
    assert result == {'state': 'login_or_challenge'}


async def test_modern_layout_does_not_enable_private_or_unrelated_routes(read):
    result = await read(modern(), 'https://www.linkedin.com/company/bright/people/')
    assert result['state'] == 'unsupported_route'


async def test_modern_capture_flows_through_existing_snapshot_source_filters(settings, monkeypatch):
    settings.platform_browser_delay_seconds = 0
    class FixtureSession:
        def __init__(self, configured):
            pass
        async def __aenter__(self):
            self.runtime = await async_playwright().start()
            self.browser = await self.runtime.chromium.launch()
            self.context = await self.browser.new_context()
            await self.context.route('**/*', lambda route: route.fulfill(content_type='text/html', body=modern()))
            return self
        async def navigate(self, url):
            page = await self.context.new_page()
            await page.goto(url)
            return page, None
        async def __aexit__(self, *args):
            await self.browser.close()
            await self.runtime.stop()
    monkeypatch.setattr(platform_browser, 'BrowserSession', FixtureSession)
    result = await platform_browser.browser_snapshot(settings, URL)
    assert result['state'] == 'captured' and result['title'] == 'Bright Studio'
    assert result['outgoing_websites'] == ['https://bright-demo.com/']
    assert result['published_emails'] == ['hello@bright-demo.com']
    assert result['identity_verified'] is False and len(result['sha256']) == 64
    assert 'PRIVATE' not in result['text']
