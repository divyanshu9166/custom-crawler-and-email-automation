"""Single public X posts via X's publishing service, without account access."""
import asyncio
import hashlib
import json
import re
import time
from urllib.parse import urlsplit

import httpx
from bs4 import BeautifulSoup

from .web import crawl_url, domain_of, extract_page, normalize_email

ENDPOINT = 'https://publish.x.com/oembed'
MAX_RESPONSE = 128 * 1024


def x_post_url(url):
    parts = urlsplit(crawl_url(url))
    if parts.hostname not in {'x.com', 'www.x.com', 'twitter.com', 'www.twitter.com'} or parts.port:
        raise ValueError('Use a public X post URL')
    match = re.fullmatch(r'/([A-Za-z0-9_]{1,15})/status/([0-9]{1,20})/?', parts.path)
    if not match or match[1].lower() in {'i', 'home', 'search', 'explore', 'intent', 'settings'}:
        raise ValueError('Use a specific public X post, not search, private messages or a profile')
    return f'https://x.com/{match[1]}/status/{match[2]}'


def x_author_key(url):
    parts = urlsplit(crawl_url(url))
    if parts.hostname not in {'x.com', 'www.x.com', 'twitter.com', 'www.twitter.com'} or parts.port:
        raise ValueError('Invalid X author URL')
    if not re.fullmatch(r'/[A-Za-z0-9_]{1,15}/?', parts.path):
        raise ValueError('Invalid X author URL')
    return parts.path.strip('/').lower()


async def public_post_snapshot(settings, url):
    url = x_post_url(url)
    result = {'url': url, 'transport_url': ENDPOINT, 'capture_method': 'official_public_oembed',
              'scope': 'single_public_post', 'profile_snapshot': False, 'observed_at': time.time()}
    try:
        # A fixed first-party publication endpoint. No profile HTML request,
        # sessions, alternate proxies, script execution or hidden API tokens.
        timeout = min(25, settings.crawl_request_timeout_seconds)
        async with asyncio.timeout(timeout), httpx.AsyncClient(timeout=timeout, trust_env=False,
                                                             follow_redirects=False) as client:
            async with client.stream('GET', ENDPOINT, params={'url': url, 'omit_script': 'true', 'dnt': 'true'},
                                     headers={'User-Agent': settings.crawler_user_agent}) as response:
                if response.status_code != 200:
                    return {**result, 'state': 'rate_limited' if response.status_code == 429 else 'public_post_unavailable',
                            'http_status': response.status_code,
                            'retry_after': response.headers.get('retry-after', '')[:100]}
                if 'application/json' not in response.headers.get('content-type', '').lower():
                    raise ValueError('Unexpected publishing response type')
                body = bytearray()
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    body.extend(chunk)
                    if len(body) > MAX_RESPONSE:
                        raise ValueError('Publishing response exceeds size limit')
        data = json.loads(body)
        handle = urlsplit(url).path.split('/')[1].lower()
        if (not isinstance(data, dict) or data.get('type') != 'rich'
                or data.get('version') != '1.0'
                or domain_of(data.get('provider_url', '')) not in {'x.com', 'twitter.com'}
                or x_post_url(data.get('url', '')).lower() != url.lower()
                or x_author_key(data.get('author_url', '')) != handle
                or not isinstance(data.get('author_name'), str) or not 2 <= len(data['author_name']) <= 200
                or not isinstance(data.get('html'), str) or len(data['html']) > 65536):
            raise ValueError('Publishing response does not match the requested post/author')
        soup = BeautifulSoup(data['html'], 'html.parser')
        block = soup.select_one('blockquote.twitter-tweet')
        if not block or len(soup.select('blockquote.twitter-tweet')) != 1:
            raise ValueError('Expected a single public-post blockquote')
        for element in list(block.select('script,style,iframe,form,svg,[hidden],[aria-hidden="true"]')):
            element.decompose()
        for element in list(block.select('[style]')):
            if element.attrs is not None and re.search(r'display\s*:\s*none|visibility\s*:\s*hidden', element.get('style', ''), re.I):
                element.decompose()
        paragraphs = block.find_all('p', recursive=False)
        if len(paragraphs) != 1 or paragraphs[0].find('blockquote'):
            raise ValueError('Missing or ambiguous public post body')
        content = paragraphs[0]
        page = extract_page(url, str(content))
        text = page['text'][:12000]
        # extract_page already normalizes explicit mailto and visible bracket
        # obfuscation. X-domain routing is irrelevant to a publication candidate;
        # none of these addresses becomes a verified contact automatically.
        from .web import outreach_email_allowed
        emails = [e for e in [*page['emails'], *(c['email'] for c in page['review_candidates'])]
                  if outreach_email_allowed(e)]
        email_links = []
        for anchor in content.select('a[href]'):
            if anchor['href'].lower().startswith('mailto:'):
                from urllib.parse import unquote
                for value in unquote(anchor['href'][7:]).split('?')[0].split(','):
                    try:
                        email = normalize_email(value)
                        if email in emails:
                            email_links.append(email)
                    except ValueError:
                        pass
        if email_links:
            text += '\nPublished mailto links: ' + ', '.join(dict.fromkeys(email_links))
        from .discovery import official_root
        links = []
        for target in page['links']:
            try:
                official_root(target)
                links.append(target)
            except ValueError:
                pass
        posted_label = ''
        for anchor in block.find_all('a', recursive=False):
            try:
                if x_post_url(anchor.get('href', '')).lower() == url.lower():
                    posted_label = anchor.get_text(' ', strip=True)[:100]
                    break
            except ValueError:
                pass
        return {**result, 'state': 'captured', 'title': data['author_name'],
                'author_url': f'https://x.com/{urlsplit(url).path.split("/")[1]}',
                'text': text, 'sha256': page['sha256'],
                'response_sha256': hashlib.sha256(body).hexdigest(),
                'posted_label': posted_label,
                'published_emails': list(dict.fromkeys(emails)), 'published_email_links': list(dict.fromkeys(email_links)),
                'outgoing_websites': list(dict.fromkeys(links))[:10], 'public_links': page['links'][:100],
                'review_required': True, 'identity_verified': False}
    except Exception as exc:
        return {**result, 'state': 'public_post_unavailable', 'error_type': type(exc).__name__}
