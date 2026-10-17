import pytest

from outreach.discovery import public_snapshot
from outreach.web import PublicWeb


@pytest.mark.parametrize('mode,browser_enabled,long_document,expected', [
    ('always', True, True, True), ('always', True, False, True),
    ('auto', True, True, False), ('auto', True, False, True),
    ('never', True, False, False), ('always', False, False, False),
])
async def test_official_snapshot_respects_configured_render_mode(
    settings, monkeypatch, mode, browser_enabled, long_document, expected
):
    settings.crawl_render_mode = mode
    settings.browser_enabled = browser_enabled
    calls = []

    class Robots:
        def can_fetch(self, *_):
            return True

    async def robots(*_):
        return Robots(), 0, ''

    async def get(self, url, *_):
        return url, '<title>Bright Studio</title><p>'+('Public business text. '*40 if long_document else '')+'</p>', 200

    class Renderer:
        def __init__(self, *_):
            pass

        async def start(self):
            calls.append('start')

        async def render(self, url, *_args, **_kwargs):
            return {'url': url, 'html': '<title>Bright Studio</title><p>Published business enquiries public@bright-demo.com</p>', 'issues': []}

        async def close(self):
            calls.append('close')

    monkeypatch.setattr(PublicWeb, 'robots', robots)
    monkeypatch.setattr(PublicWeb, 'get', get)
    monkeypatch.setattr('outreach.browser.RenderSession', Renderer)
    result = await public_snapshot(settings, 'https://bright-demo.com/')
    assert result['state'] == 'captured'
    assert result['render_attempted'] is expected and result['rendered'] is expected
    assert calls == (['start', 'close'] if expected else [])
    assert ('public@bright-demo.com' in result['published_emails']) is expected
    assert result['render_mode'] == mode


async def test_long_official_snapshot_executes_real_chromium_staff_hydration(settings, monkeypatch):
    settings.crawl_render_mode = 'always'
    settings.browser_settle_seconds = .01
    html = ('<html><head><title>Bright Studio</title></head><body><main><p>'
        + 'Current public business services. '*40 + '</p></main><script>'
        + 'document.querySelector("main").insertAdjacentHTML("beforeend", '
        + "'<section><h2>Alex Doe</h2><p>Founder</p><a href=\"mailto:alex@bright-demo.com\">Business enquiries</a><a href=\"https://www.linkedin.com/in/alex-doe\">LinkedIn</a></section>');"
        + '</script></body></html>')

    class Robots:
        def can_fetch(self, *_):
            return True

    async def robots(*_):
        return Robots(), 0, ''

    async def get(self, url, *_):
        self.last_document = {'url': url, 'body': html.encode(), 'status': 200,
                              'headers': {'content-type': 'text/html'}}
        return url, html, 200

    async def no_network(*_args, **_kwargs):
        pytest.fail('The fictional initial document must be reused; no external requests')

    monkeypatch.setattr(PublicWeb, 'robots', robots)
    monkeypatch.setattr(PublicWeb, 'get', get)
    monkeypatch.setattr(PublicWeb, 'resource', no_network)
    result = await public_snapshot(settings, 'https://bright-demo.com/team')
    assert result['rendered'] and result['render_attempted']
    assert not result['render_issues']
    assert result['published_emails'] == ['alex@bright-demo.com']
    person = result['named_people'][0]
    assert person['name'] == 'Alex Doe' and person['role'] == 'Founder'
    assert person['professional_links'] == ['https://www.linkedin.com/in/alex-doe']
    assert person['email_publications'][0]['email'] == 'alex@bright-demo.com'
    assert result['http_snapshot']['capture_method'] == 'public_html'
    assert not result['http_snapshot']['named_people']
    assert result['http_snapshot']['sha256'] != result['sha256']


async def test_failed_official_render_preserves_raw_publication_with_explicit_partial_status(settings, monkeypatch):
    class Robots:
        def can_fetch(self, *_):
            return True

    async def robots(*_):
        return Robots(), 0, ''

    async def get(self, url, *_):
        return url, '<title>Bright Studio</title><p>Published public@bright-demo.com</p>', 200

    class Renderer:
        def __init__(self, *_):
            pass

        async def start(self):
            raise RuntimeError('synthetic startup failure')

        async def close(self):
            pass

    monkeypatch.setattr(PublicWeb, 'robots', robots)
    monkeypatch.setattr(PublicWeb, 'get', get)
    monkeypatch.setattr('outreach.browser.RenderSession', Renderer)
    result = await public_snapshot(settings, 'https://bright-demo.com/')
    assert result['state'] == 'captured' and result['render_attempted'] and not result['rendered']
    assert result['render_issues'] == [{'reason': 'official_render_unavailable', 'error_type': 'RuntimeError'}]
    assert result['published_emails'] == ['public@bright-demo.com']
