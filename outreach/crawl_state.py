"""Serializable recovery state; captured evidence and permanent denials stay untouched."""
import math
import time

import httpx

CHECKPOINT_WORK = ('frontier', 'sitemap_queue', 'retry_urls', 'retry_sitemaps', 'inflight', 'sitemap_inflight')


def transient_failure(exc):
    return (isinstance(exc, (httpx.TransportError, OSError)) or
            isinstance(exc, httpx.HTTPStatusError) and
            exc.response.status_code in {408, 429, 500, 502, 503, 504})


def timestamp(value):
    try:
        result = float(value)
        return result if math.isfinite(result) and result >= 0 else 0
    except (TypeError, ValueError):
        return 0


def continuation_wait(checkpoint, now=None):
    """Never make even a robots request while an origin cooldown is active."""
    now = time.time() if now is None else now
    wait = timestamp(checkpoint.get('domain_not_before')) - now
    if wait > 0:
        return wait
    if any(checkpoint.get(k) for k in ('frontier', 'sitemap_queue', 'inflight', 'sitemap_inflight')):
        return 0
    entries = checkpoint.get('retry_urls', [])+checkpoint.get('retry_sitemaps', [])
    return max(0, min((timestamp(e.get('not_before')) for e in entries), default=0)-now)


def current_errors(report):
    return [error for error in report.get('errors', []) if not error.get('resolved_at')]
