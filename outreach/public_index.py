"""Small, paced public-index lookups. Index records are URL hints, never publication proof."""

import asyncio
import copy
import json
import re
import time

import httpx

from .web import company_crawl_url, domain_of, retry_after_seconds


async def cached_lookup(settings, key, provider, fetch, ttl, *, persistent=False):
    # Shared by shallow Settings copies; the lock covers pacing and requests so
    # concurrent company jobs cannot burst the same index service.
    async with settings._discovery_lock:
        state = settings._discovery_state
        now = time.time()
        cache = state.setdefault('cache', {})
        holds = state.setdefault('holds', {})
        next_requests = state.setdefault('next', {})
        if persistent:
            from . import source_cache
            try:
                saved = source_cache.load(settings, provider, key)
                holds[provider] = max(holds.get(provider, 0), saved['hold_until'])
                next_requests[provider] = max(next_requests.get(provider, 0), saved['next_at'])
                if saved['entry']:
                    cache[key] = saved['entry']
                else:
                    cache.pop(key, None)
            except Exception as exc:
                # Do not forget a saved provider hold when storage is unreadable.
                return {'state': 'cache_storage_unavailable', 'rows': [], 'provider': provider,
                        'error_type': type(exc).__name__, 'cached': False}
        entry = cache.get(key)
        if entry and entry['until'] > now:
            result = copy.deepcopy(entry['value'])
            result['cached'] = True
            return result
        if holds.get(provider, 0) > now:
            return {'state': 'cooldown', 'rows': [], 'retry_at': holds[provider], 'provider': provider}
        wait = state.setdefault('next', {}).get(provider, 0) - now
        if wait > 0:
            await asyncio.sleep(wait)
        try:
            value = await fetch()
            value.update(provider=provider, observed_at=time.time(), cached=False)
        except Exception as exc:
            delay = settings.search_failure_cooldown_seconds
            if isinstance(exc, httpx.HTTPStatusError):
                delay = max(delay, min(3600, retry_after_seconds(exc.response.headers)))
            holds[provider] = time.time() + delay
            value = {'state': 'unavailable', 'rows': [], 'provider': provider,
                     'error_type': type(exc).__name__, 'retry_at': holds[provider], 'cached': False}
            if isinstance(exc, httpx.HTTPStatusError):
                value['http_status'] = exc.response.status_code
        finally:
            state['next'][provider] = time.time() + max(2, settings.discovery_query_delay_seconds)
        cache_ttl = ttl if value['state'] == 'available' else min(ttl, 60)
        if provider.startswith('searxng:') and not value['rows']:
            cache_ttl = min(cache_ttl, 60)
        cache_entry = {'until': time.time() + cache_ttl, 'value': copy.deepcopy(value)}
        cache[key] = cache_entry
        while len(cache) > 256:
            cache.pop(next(iter(cache)))
        if persistent:
            try:
                source_cache.save(settings, provider, key, cache_entry,
                    holds.get(provider, 0), next_requests.get(provider, 0))
            except Exception as exc:
                return {'state': 'cache_storage_unavailable', 'rows': [], 'provider': provider,
                        'error_type': type(exc).__name__, 'cached': False}
        return value


async def bounded_get(url, params=None, maximum=1_000_000):
    async with httpx.AsyncClient(timeout=20, trust_env=False, follow_redirects=False) as client:
        async with client.stream('GET', url, params=params) as response:
            response.raise_for_status()
            if response.is_redirect:
                raise ValueError('Index redirects are not accepted')
            body = bytearray()
            async for chunk in response.aiter_bytes():
                body.extend(chunk)
                if len(body) > maximum:
                    raise ValueError('Index response exceeds byte budget')
            return bytes(body)


async def commoncrawl_routes(settings, website):
    """One page in the latest index for one exact company domain. No WARC downloads."""
    if not settings.commoncrawl_hints_enabled:
        return {'state': 'disabled', 'rows': [], 'provider': 'commoncrawl'}
    domain = domain_of(website)
    # Also validate the scheme/address using the normal crawler URL gate.
    if not company_crawl_url(website, domain):
        raise ValueError('Official company URL required')

    async def collections():
        payload = json.loads(await bounded_get('https://index.commoncrawl.org/collinfo.json'))
        if not isinstance(payload, list):
            raise ValueError('Invalid collection listing')
        ids = [r.get('id', '') for r in payload[:100] if isinstance(r, dict)]
        ids = [v for v in ids if re.fullmatch(r'CC-MAIN-20\d{2}-\d{2}', v)]
        if not ids:
            raise ValueError('No valid Common Crawl collection')
        return {'state': 'available', 'rows': [], 'collection': max(ids)}

    listing = await cached_lookup(settings, 'cc:collections', 'commoncrawl', collections, 86400)
    if listing['state'] != 'available':
        return listing
    collection = listing['collection']

    async def routes():
        from .contact_recovery import contact_route
        try:
            body = await bounded_get('https://index.commoncrawl.org/' + collection + '-index',
                {'url': '*.' + domain + '/*', 'output': 'json', 'filter': 'status:200',
                 'collapse': 'urlkey', 'pageSize': '1', 'page': '0'})
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                return {'state': 'available', 'rows': [], 'collection': collection, 'reason': 'Domain not present in this index'}
            raise
        found = {}
        lines = body.splitlines()
        for line in lines[:2000]:
            row = json.loads(line)
            if not isinstance(row, dict) or str(row.get('status')) != '200':
                continue
            try:
                url = contact_route(row.get('url', ''), domain)
            except ValueError:
                continue
            # The wildcard can include subdomains; identity remains exact.
            if not url or domain_of(url) != domain:
                continue
            stamp = row.get('timestamp', '')
            if not re.fullmatch(r'\d{14}', stamp):
                continue
            found.setdefault(url, {'url': url, 'indexed_at': stamp, 'collection': collection,
                                   'origin': 'commoncrawl_url_hint', 'current_publication': False})
        return {'state': 'available', 'rows': list(found.values())[:20], 'collection': collection,
                'records_examined': min(2000, len(lines)), 'bounded_first_page': True}

    return await cached_lookup(settings, 'cc:' + collection + ':' + domain, 'commoncrawl', routes, 86400)
