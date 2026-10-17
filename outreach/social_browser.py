"""Bounded research using the existing VPS browser, session lock and access holds."""
import asyncio
import hashlib
import time
from pathlib import Path
from urllib.parse import urlencode

from . import platform_browser as browser
from .platform_access import hold, record_hold
from .providers import SearchRows

STATIC = Path(__file__).parent / 'static'


async def browser_people_discover(settings, query, limit=5):
    if not settings.platform_browser_enabled or not settings.linkedin_people_search_enabled:
        return SearchRows([], [['linkedin.com', 'people_search_disabled']])
    if not 5 <= len(query) <= 500:
        raise ValueError('Use a bounded company and buyer query')
    target = 'https://www.linkedin.com/search/results/people/?' + urlencode({'keywords': query})
    try:
        async with settings._platform_browser_lock:
            if hold(settings, 'linkedin.com'):
                return SearchRows([], [['linkedin.com', 'operator_attention']])
            return await browser._discover_locked(settings, 'linkedin.com', target, min(limit, 20), people=True)
    except browser.LoginTransitionError:
        record_hold(settings, 'linkedin.com', 'login_or_challenge')
        return SearchRows([], [['linkedin.com', 'login_or_challenge']])
    except Exception as exc:
        return SearchRows([], [['linkedin.com', 'browser_unavailable:' + type(exc).__name__]])


async def enrich_professional(settings, session, target, result):
    """A root capture stays attributable; missing optional sections are explicit."""
    result = {**result, 'sections': dict(result.get('sections', {})), 'section_errors': []}
    try:
        async with asyncio.timeout(settings.platform_browser_search_timeout_seconds):
            await _enrich_sections(settings, session, target, result)
    except TimeoutError:
        result['section_errors'].append({'section': 'optional_sections', 'state': 'deadline'})
    if 'contact_info' in result['sections']:
        result['scope'] = 'account_visible_professional_fields'
    return result


async def _enrich_sections(settings, session, target, result):
    sections = result['sections']
    requested = []
    if settings.linkedin_profile_experience_enabled and 'experience' not in sections:
        requested.append(('experience', '/details/experience/'))
    if settings.linkedin_contact_info_enabled:
        requested.append(('contact_info', '/overlay/contact-info/'))
    reader = (STATIC / 'professional-section-reader.js').read_text(encoding='utf-8')
    for name, suffix in requested:
        if hold(settings, 'linkedin.com'):
            result['section_errors'].append({'section': name, 'state': 'operator_attention'})
            break
        try:
            await asyncio.sleep(settings.platform_browser_delay_seconds)
            page, denied = await session.navigate(target.rstrip('/') + suffix)
            try:
                if denied:
                    value = {'state': 'http_error', 'http_status': denied}
                    if denied in {401, 403, 429, 999}:
                        record_hold(settings, 'linkedin.com', 'http_' + str(denied), session.last_access_issue)
                else:
                    for attempt in range(3):
                        value = await page.evaluate(reader, {'profile': target, 'section': name})
                        if value.get('state') != 'fields_not_ready':
                            break
                        if attempt < 2:
                            await asyncio.sleep(1)
            finally:
                await page.close()
            if value.get('state') == 'login_or_challenge':
                record_hold(settings, 'linkedin.com', 'login_or_challenge')
            if value.get('state') != 'captured' or not value.get('text'):
                result['section_errors'].append({'section': name, **{k: value[k] for k in ('state', 'http_status') if k in value}})
                continue
            text = value['text'][:6000]
            mailto = value.get('mailto', [])[:20]
            sections[name] = {'state': 'captured', 'text': text, 'source_url': value['source_url'],
                              'sha256': hashlib.sha256(text.encode()).hexdigest(),
                              'visibility': value.get('visibility', 'visible_profile')}
            result['text'] += '\n' + name + ' [source: ' + value['source_url'] + ']: ' + text
            if mailto:
                result['text'] += '\nPublished mailto links: ' + ', '.join(mailto)
            result['links'] = list(dict.fromkeys(result['links'] + value.get('links', [])))[:80]
            result['mailto'] = list(dict.fromkeys(result['mailto'] + mailto))[:40]
        except browser.LoginTransitionError:
            record_hold(settings, 'linkedin.com', 'login_or_challenge')
            result['section_errors'].append({'section': name, 'state': 'login_or_challenge'})
            break
        except Exception as exc:
            result['section_errors'].append({'section': name, 'state': 'unavailable', 'error_type': type(exc).__name__})


def post_profile(url):
    """Only a known company profile or X author can supply recent posts."""
    from .professionals import professional_target
    platform, target = browser.profile_target(url) if '/company/' in url else professional_target(url)
    if platform == 'linkedin.com':
        if '/company/' not in target:
            raise ValueError('LinkedIn posts require a company profile')
        profile = target.removesuffix('/about/')
        return platform, profile, profile + '/posts/'
    return platform, target, target


async def browser_recent_posts(settings, url):
    platform, profile, target = post_profile(url)
    base = {'profile_url': profile, 'provider': 'managed_browser:' + platform,
            'capture_method': 'managed_browser_author_posts', 'observed_at': time.time(),
            'posts': [], 'identity_verified': False, 'review_required': True}
    if not settings.platform_browser_enabled or not settings.social_posts_enabled:
        return {**base, 'state': 'disabled'}
    found = {}
    def interrupted(state, **detail):
        return {**base, 'state': 'captured' if found else state, 'stop_reason': state,
                'coverage': 'bounded_visible_posts', 'partial': True,
                'posts': list(found.values())[:settings.social_posts_max_posts], **detail}
    try:
        async with settings._platform_browser_lock:
            if blocked := hold(settings, platform):
                return {**base, **blocked, 'state': 'operator_attention'}
            async with asyncio.timeout(settings.platform_browser_search_timeout_seconds):
                async with browser.BrowserSession(settings) as session:
                    await asyncio.sleep(settings.platform_browser_delay_seconds)
                    page, denied = await session.navigate(target)
                    if denied:
                        if denied in {401, 403, 429, 999}:
                            record_hold(settings, platform, 'http_' + str(denied), session.last_access_issue)
                        return {**base, 'state': 'http_error', 'http_status': denied}
                    reader = (STATIC / 'social-posts-reader.js').read_text(encoding='utf-8')
                    stop, state = 'step_budget', 'fields_not_ready'
                    for step in range(min(3, settings.platform_browser_search_steps)):
                        result = await page.evaluate(reader, {'profile': profile, 'limit': settings.social_posts_max_posts})
                        state = result.get('state', 'unavailable')
                        if state == 'login_or_challenge':
                            record_hold(settings, platform, state)
                        if state not in {'captured', 'fields_not_ready', 'no_author_matched_posts'}:
                            stop = state
                            break
                        for post in result.get('posts', []):
                            post['sha256'] = hashlib.sha256(post['text'].encode()).hexdigest()
                            found.setdefault(post['url'], post)
                        if len(found) >= settings.social_posts_max_posts:
                            stop = 'requested_limit'
                            break
                        if step + 1 < min(3, settings.platform_browser_search_steps):
                            await page.mouse.wheel(0, 650)
                            await asyncio.sleep(max(.25, settings.platform_browser_delay_seconds))
                    return {**base, 'state': 'captured' if found else state, 'stop_reason': stop,
                            'coverage': 'bounded_visible_posts', 'partial': stop != 'requested_limit',
                            'posts': list(found.values())[:settings.social_posts_max_posts]}
    except browser.LoginTransitionError:
        record_hold(settings, platform, 'login_or_challenge')
        return interrupted('login_or_challenge')
    except TimeoutError:
        return interrupted('deadline')
    except Exception as exc:
        return interrupted('browser_unavailable', error_type=type(exc).__name__)
