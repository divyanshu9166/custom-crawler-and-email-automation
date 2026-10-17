"""Optional free community X profile hints, separate from first-party evidence."""
import asyncio
import hashlib
import html
import json
import re
import time

import httpx

from .public_posts import x_author_key

BASE = 'https://api.fxtwitter.com/2/profile/'
MAX_BYTES = 128 * 1024


def bio_email_occurrences(bio):
    """Read explicit address notation with an exact original-publication span."""
    from .web import EMAIL_RE, normalize_email, outreach_email_allowed
    token = re.compile(r'\[at\]|\(at\)|\[dot\]|\(dot\)', re.I)
    chars, offsets, position = [], [], 0
    for match in token.finditer(bio):
        for i in range(position, match.start()):
            chars.append(bio[i])
            offsets.append((i, i+1))
        chars.append('@' if 'at' in match[0].lower() else '.')
        offsets.append((match.start(), match.end()))
        position = match.end()
    for i in range(position, len(bio)):
        chars.append(bio[i])
        offsets.append((i, i+1))
    text, result = ''.join(chars), []
    for match in re.finditer(EMAIL_RE, text):
        try:
            email = normalize_email(match[0])
            if not outreach_email_allowed(email):
                continue
        except ValueError:
            continue
        start, end = offsets[match.start()][0], offsets[match.end()-1][1]
        literal = bio[start:end]
        result.append({'email': email, 'start': start, 'end': end, 'publication_quote': literal,
            'method': 'visible_obfuscation' if token.search(literal) else 'visible_text'})
    return result


def bio_email_routes(bio, emails):
    """Describe explicit nearby labels, never infer a decision-maker from an inbox."""
    label = re.compile(r'(?P<label>customer support(?: email)?|support(?: email)?|order (?:inquiries|enquiries)|'
        r'business (?:inquiries|enquiries)|partnerships?|press|sales|media)\s*(?:email|contact)?\s*[:=-]\s*$', re.I)
    routes = {email: [] for email in emails}
    for occurrence in bio_email_occurrences(bio):
        email = occurrence['email']
        if email not in routes:
            continue
        prefix = bio[max(0, occurrence['start']-100):occurrence['start']]
        context = label.search(prefix)
        value = context['label'].lower() if context else ''
        purpose = ('customer_support' if 'support' in value or value.startswith('order ') else
                   'business_enquiries' if value.startswith('business ') else
                   'partnerships' if value.startswith('partnership') else
                   'press_media' if value in {'press', 'media'} else 'sales' if value == 'sales' else 'unknown')
        quote_start = occurrence['start']-len(prefix)+context.start() if context else max(0, occurrence['start']-60)
        routes[email].append({'purpose': purpose, 'context_quote': bio[quote_start:occurrence['end']],
            'publication_quote': occurrence['publication_quote'], 'method': occurrence['method']})
    result = []
    for email, contexts in routes.items():
        purposes = set(item['purpose'] for item in contexts)
        result.append({'email': email, 'purpose': next(iter(purposes)) if len(purposes) == 1 else
            'multiple_purposes' if purposes else 'unknown', 'contexts': contexts[:5], 'buyer_contact_verified': False})
    return result


def parse_profile(payload, target):
    if not isinstance(payload, dict) or payload.get('code') != 200:
        return {'state': 'provider_error', 'provider_code': payload.get('code') if isinstance(payload, dict) else None}
    user = payload.get('user')
    if not isinstance(user, dict) or user.get('type') != 'profile':
        return {'state': 'invalid_contract'}
    if user.get('protected') is not False:
        return {'state': 'private_or_visibility_unknown'}
    try:
        if not isinstance(user.get('screen_name'), str) or user['screen_name'].lower() != x_author_key(target):
            return {'state': 'identity_mismatch'}
        if not isinstance(user.get('url'), str) or x_author_key(user['url']) != x_author_key(target):
            return {'state': 'identity_mismatch'}
    except ValueError:
        return {'state': 'identity_mismatch'}
    name, bio = user.get('name'), user.get('description')
    if not isinstance(name, str) or not 1 <= len(name) <= 200 or not isinstance(bio, str) or len(bio) > 16000:
        return {'state': 'invalid_contract'}
    bio = html.unescape(bio)
    occurrences = bio_email_occurrences(bio)
    emails = sorted({item['email'] for item in occurrences})
    website_hint = ''
    website = user.get('website')
    value = website.get('url') if isinstance(website, dict) else None
    if isinstance(value, str) and len(value) <= 2048:
        from .web import normalize_url
        try:
            website_hint = normalize_url(value)
        except ValueError:
            pass
    return {'state': 'public_mirror_hint', 'profile_url': target, 'name': name,
            'handle': user['screen_name'], 'description': bio,
            'bio_sha256': hashlib.sha256(bio.encode()).hexdigest(),
            'published_email_candidates': emails, 'candidate_routes': bio_email_routes(bio, emails),
            'email_publications': [{k: item[k] for k in ('email', 'publication_quote', 'method')} for item in occurrences],
            'published_website_hint': website_hint, 'website_ownership_verified': False,
            'location': str(user.get('location', ''))[:200],
            'first_party_publication_verified': False, 'current_employer_verified': False,
            'buyer_verified': False, 'source_freshness_verified': False, 'review_required': True}


async def profile_hint(settings, target):
    from .professionals import professional_target
    from .public_index import cached_lookup
    platform, target = professional_target(target)
    if platform != 'x.com':
        raise ValueError('FxEmbed profile hints support X public profile roots only')
    if not settings.fxembed_profiles_enabled:
        return {'state': 'disabled', 'profile_url': target}
    transport_url = BASE + x_author_key(target)
    provider = 'fxembed_profiles'

    async def fetch():
        timeout = min(20, settings.crawl_request_timeout_seconds)
        async with asyncio.timeout(timeout), httpx.AsyncClient(timeout=timeout, trust_env=False,
                follow_redirects=False, headers={'User-Agent': settings.crawler_user_agent,
                'Accept': 'application/json'}) as client:
            async with client.stream('GET', transport_url) as response:
                if response.status_code in (401, 403, 404, 429, 999):
                    if response.status_code != 404:
                        from .platform_access import retry_seconds
                        interval = retry_seconds(response.headers.get('retry-after')) if response.status_code == 429 else 3600
                        settings._discovery_state.setdefault('holds', {})[provider] = time.time() + interval
                    error = {'state': 'not_found' if response.status_code == 404 else 'source_denied',
                             'http_status': response.status_code, 'profile_url': target,
                             'transport_url': transport_url}
                    return {'state': error['state'], 'rows': [], 'profile': error}
                response.raise_for_status()
                if response.is_redirect or 'application/json' not in response.headers.get('content-type', '').lower():
                    raise ValueError('Unexpected community profile response type or redirect')
                body = bytearray()
                async for chunk in response.aiter_bytes(chunk_size=8192):
                    body.extend(chunk)
                    if len(body) > MAX_BYTES:
                        raise ValueError('Community profile response exceeds byte budget')
                parsed = parse_profile(json.loads(body), target)
                parsed.update(profile_url=target, transport_url=transport_url, http_status=response.status_code,
                    response_sha256=hashlib.sha256(body).hexdigest(), retrieved_at=time.time())
                if parsed.get('provider_code') in (401, 403, 429, 999):
                    from .platform_access import retry_seconds
                    interval = retry_seconds(response.headers.get('retry-after')) if parsed['provider_code'] == 429 else 3600
                    settings._discovery_state.setdefault('holds', {})[provider] = time.time() + interval
                return {'state': 'available' if parsed['state'] == 'public_mirror_hint' else parsed['state'],
                        'rows': [], 'profile': parsed}

    result = await cached_lookup(settings, 'fxprofile:' + x_author_key(target), provider, fetch, 900,
                                 persistent=True)
    if 'profile' in result:
        return {**result['profile'], 'cached': result['cached']}
    return {**result, 'profile_url': target, 'transport_url': transport_url}
