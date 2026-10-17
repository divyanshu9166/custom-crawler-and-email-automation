from datetime import datetime, timezone
from email.utils import format_datetime
from types import SimpleNamespace

import pytest

from outreach.config import Settings
from outreach.platform_access import access_status, clear_hold, hold, record_hold, response_issue, retry_seconds


def restarted(settings):
    return Settings(_env_file=None, data_dir=settings.data_dir)


def test_hold_survives_restart_and_stays_platform_specific(settings):
    record_hold(settings, 'linkedin.com', 'http_999', {'http_status': 999})
    other = restarted(settings)
    assert hold(other, 'linkedin.com')['http_status'] == 999
    assert hold(other, 'x.com') is None
    assert set(access_status(other)) == {'linkedin.com'}


def test_operator_clear_updates_already_running_process(settings):
    record_hold(settings, 'x.com', 'http_403')
    clear_hold(restarted(settings), 'x.com')
    assert hold(settings, 'x.com') is None
    assert not settings._platform_browser_holds


def test_rate_limit_expires_after_server_interval(settings, monkeypatch):
    monkeypatch.setattr('outreach.platform_access.time.time', lambda: 1000)
    record_hold(settings, 'x.com', 'http_429', {'retry_after_seconds': 7200})
    assert hold(settings, 'x.com')['retry_at'] == 8200
    monkeypatch.setattr('outreach.platform_access.time.time', lambda: 8199)
    assert hold(restarted(settings), 'x.com')
    monkeypatch.setattr('outreach.platform_access.time.time', lambda: 8201)
    assert hold(settings, 'x.com') is None
    assert hold(restarted(settings), 'x.com') is None


def test_access_denial_never_auto_expires(settings, monkeypatch):
    record_hold(settings, 'linkedin.com', 'http_999')
    monkeypatch.setattr('outreach.platform_access.time.time', lambda: 1e12)
    assert hold(restarted(settings), 'linkedin.com')['operator_action_required']


def test_corrupt_state_stops_access_instead_of_relaunching(settings):
    folder = settings.data_dir / 'platform-browser'
    folder.mkdir()
    (folder / 'access.sqlite3').write_bytes(b'invalid database')
    assert hold(settings, 'x.com')['reason'] == 'access_state_unavailable'


@pytest.mark.parametrize('value,expected', [('120', 120), ('bad', 3600), ('0', 60), ('604800', 604800)])
def test_retry_after_formats(value, expected):
    assert retry_seconds(value, now=1000) == expected


def test_retry_after_http_date():
    date = format_datetime(datetime.fromtimestamp(8200, timezone.utc), usegmt=True)
    assert retry_seconds(date, now=1000) == 7200


async def test_diagnostic_metadata_never_contains_cookies_tokens_or_error_body():
    async def headers():
        return {'server': 'edge', 'set-cookie': 'session=secret', 'authorization': 'secret',
                'retry-after': '120', 'x-mitmproxy-blocked-reason': 'ROBOTS_DENIED'}
    response = SimpleNamespace(status=429, url='https://x.com/bright', all_headers=headers)
    issue = await response_issue(response)
    assert issue['denial_kind'] == 'network_policy_denial'
    assert issue['retry_after_seconds'] == 120
    assert 'secret' not in str(issue) and 'set-cookie' not in issue


async def test_persisted_denial_prevents_browser_relaunch(settings, monkeypatch):
    from outreach.platform_browser import browser_professional_snapshot
    record_hold(settings, 'linkedin.com', 'http_999')
    def forbidden(*args):
        pytest.fail('Restart must not automatically retry a denied platform')
    monkeypatch.setattr('outreach.platform_browser.BrowserSession', forbidden)
    result = await browser_professional_snapshot(restarted(settings), 'https://linkedin.com/in/bright-person')
    assert result['reason'] == 'http_999' and result['state'] == 'operator_attention'


async def test_both_platform_denials_do_not_stop_free_discovery(settings, monkeypatch):
    from outreach.discovery import prospect_candidates
    from outreach.providers import SearchRows
    settings.platform_browser_enabled = True
    settings.discovery_platforms = 'linkedin.com,x.com'
    settings.discovery_query_delay_seconds = 0
    record_hold(settings, 'linkedin.com', 'http_999')
    record_hold(settings, 'x.com', 'http_403')
    def forbidden(*args):
        pytest.fail('Denied platforms must not relaunch')
    async def public_search(config, query, limit, **kwargs):
        assert config.search_provider == 'searxng' and not config.serpapi_key
        return SearchRows([{'url': 'https://bright-demo.com/', 'title': 'Bright Dental UK', 'snippet': 'UK dental practice'}])
    monkeypatch.setattr('outreach.platform_browser.BrowserSession', forbidden)
    monkeypatch.setattr('outreach.providers.discover', public_search)
    rows, report = await prospect_candidates(settings, 'UK dental practice', 'UK', 3)
    assert [row['url'] for row in rows] == ['https://bright-demo.com/']
    held = [item for item in report['engine_reports'] if item['source'] in ('linkedin.com', 'x.com')]
    assert len(held) == 2 and all(item['engine_issues'] for item in held)
    assert any(item['source'] == 'public_search' and item['results'] for item in report['engine_reports'])
