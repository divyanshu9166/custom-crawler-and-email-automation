"""Durable per-platform access holds; denial never becomes contact evidence."""
import json
import sqlite3
import time
from contextlib import contextmanager
from datetime import timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit

PLATFORMS = ('linkedin.com', 'x.com')


def retry_seconds(value, now=None):
    now = time.time() if now is None else now
    try:
        seconds = int(value) if str(value).strip().isdigit() else (
            parsedate_to_datetime(value).replace(tzinfo=timezone.utc)
            if parsedate_to_datetime(value).tzinfo is None else parsedate_to_datetime(value)
        ).timestamp() - now
    except (ValueError, TypeError, OverflowError):
        seconds = 3600
    return min(30 * 86400, max(60, int(seconds)))


async def response_issue(response):
    """Whitelist diagnostic metadata; exclude cookies, headers with tokens and bodies."""
    issue = {'http_status': response.status, 'response_host': urlsplit(response.url).hostname,
             'denial_kind': 'http_error'}
    try:
        headers = await response.all_headers()
    except Exception:
        headers = {}
    if headers.get('server'):
        issue['server'] = headers['server'][:160]
    if headers.get('x-mitmproxy-blocked-reason'):
        issue['denial_kind'] = 'network_policy_denial'
    elif response.status == 429:
        issue['denial_kind'] = 'rate_limited'
    elif response.status in {401, 403, 999}:
        # Status alone cannot distinguish account, IP, region and anti-bot policy.
        issue['denial_kind'] = 'access_denied_cause_unconfirmed'
    if response.status == 429:
        issue['retry_after_seconds'] = retry_seconds(headers.get('retry-after'))
    return issue


@contextmanager
def storage(settings, create=False):
    folder = settings.data_dir / 'platform-browser'
    path = folder / 'access.sqlite3'
    if not create and not path.exists():
        yield None
        return
    if create:
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
    con = sqlite3.connect(str(path), timeout=2)
    try:
        if create:
            con.execute('CREATE TABLE IF NOT EXISTS holds (platform TEXT PRIMARY KEY, detail TEXT NOT NULL, expires_at REAL)')
        yield con
        con.commit()
    finally:
        con.close()


def hold(settings, platform):
    if platform not in PLATFORMS:
        raise ValueError('Unsupported platform')
    try:
        with storage(settings) as con:
            row = con.execute('SELECT detail,expires_at FROM holds WHERE platform=?', (platform,)).fetchone() if con else None
            if row:
                detail = json.loads(row[0])
                if row[1] is None or row[1] > time.time():
                    settings._platform_browser_holds[platform] = detail['reason']
                    settings._platform_browser_persisted_holds.add(platform)
                    return detail
                con.execute('DELETE FROM holds WHERE platform=? AND expires_at=?', (platform, row[1]))
                if settings._platform_browser_holds.get(platform) == detail['reason']:
                    settings._platform_browser_holds.pop(platform, None)
                settings._platform_browser_persisted_holds.discard(platform)
            elif platform in settings._platform_browser_persisted_holds:
                # A separate operator process may clear the durable hold.
                settings._platform_browser_holds.pop(platform, None)
                settings._platform_browser_persisted_holds.discard(platform)
    except (sqlite3.Error, ValueError, KeyError, TypeError):
        return {'reason': 'access_state_unavailable', 'operator_action_required': True}
    reason = settings._platform_browser_holds.get(platform)
    return {'reason': reason, 'operator_action_required': True} if reason else None


def record_hold(settings, platform, reason, issue=None):
    if platform not in PLATFORMS:
        raise ValueError('Unsupported platform')
    detail = {'reason': reason, 'observed_at': time.time(), 'operator_action_required': reason != 'http_429'}
    detail.update({k: v for k, v in (issue or {}).items() if k in
                   {'http_status', 'response_host', 'server', 'denial_kind', 'retry_after_seconds'}})
    expiry = detail['observed_at'] + retry_seconds(str(detail.get('retry_after_seconds', 3600))) if reason == 'http_429' else None
    if expiry:
        detail['retry_at'] = expiry
    settings._platform_browser_holds[platform] = reason
    try:
        with storage(settings, create=True) as con:
            con.execute('INSERT INTO holds(platform,detail,expires_at) VALUES(?,?,?) ON CONFLICT(platform) DO UPDATE SET detail=excluded.detail,expires_at=excluded.expires_at',
                        (platform, json.dumps(detail), expiry))
        settings._platform_browser_persisted_holds.add(platform)
    except (OSError, sqlite3.Error):
        # Preserve the actual denial even when durable storage is unavailable.
        detail.update(persistence_error=True, operator_action_required=True)
    return detail


def clear_hold(settings, platform):
    if platform not in PLATFORMS:
        raise ValueError('Unsupported platform')
    with storage(settings) as con:
        if con:
            con.execute('DELETE FROM holds WHERE platform=?', (platform,))
    settings._platform_browser_holds.pop(platform, None)
    settings._platform_browser_persisted_holds.discard(platform)


def access_status(settings):
    return {platform: value for platform in PLATFORMS if (value := hold(settings, platform))}
