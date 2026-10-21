"""Google Business Profile discovery from public, visible Maps pages, never hidden RPCs."""
import asyncio
import hashlib
import re
from urllib.parse import parse_qs, unquote, urlencode, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup
import httpx

from .web import PublicWeb, crawl_url, domain_of, normalize_email

CAMPAIGN_NAME = 'Campaign 3 - Google Business Profiles'


def listing_url(url):
    value = crawl_url(url)
    p = urlsplit(value)
    if p.scheme != 'https' or domain_of(value) != 'google.com':
        raise ValueError('Use a public Google Maps business listing')
    query = parse_qs(p.query)
    cid = query.get('cid', [''])[0]
    ftid = query.get('ftid', [''])[0]
    match = re.search(r'!1s(0x[0-9a-f]+:0x[0-9a-f]+)', p.path, re.I)
    if match:
        ftid = match[1]
    if re.fullmatch(r'0x[0-9a-f]+:0x[0-9a-f]+', ftid, re.I):
        cid = str(int(ftid.split(':')[1], 16))
    if cid and re.fullmatch(r'\d{1,20}', cid) and 0 < int(cid) < 2**64 and (p.path.rstrip('/') in {'/maps', '/maps/place'} or p.path.startswith('/maps/place/')):
        # Keep the observed source route. A synthesized /maps?cid= endpoint has
        # different robots rules and is not interchangeable as a fetch target.
        q = '' if match else urlencode({'cid': str(int(cid))})
        return urlunsplit(('https', 'www.google.com', p.path.rstrip('/'), q, ''))
    place_id = query.get('q', [''])[0]
    if p.path.rstrip('/') in {'/maps', '/maps/place'} and re.fullmatch(r'place_id:[A-Za-z0-9_-]{10,200}', place_id):
        return 'https://www.google.com/maps?'+urlencode({'q': place_id})
    if not re.match(r'^/maps/place/[^/]+', p.path) or p.path.startswith('/maps/place/data='):
        raise ValueError('Use a specific Google business listing, not a Maps search/home page')
    return urlunsplit(('https', 'www.google.com', p.path.rstrip('/'), '', ''))


def listing_key(url):
    value = listing_url(url)
    p = urlsplit(value)
    q = parse_qs(p.query)
    cid = q.get('cid', [''])[0]
    match = re.search(r'!1s0x[0-9a-f]+:0x([0-9a-f]+)', unquote(p.path), re.I)
    if match:
        cid = str(int(match[1], 16))
    if cid:
        return 'google-cid:'+cid
    return q.get('q', [value])[0]


def is_listing(url):
    try:
        listing_url(url)
        return True
    except ValueError:
        return False


def campaign(db, campaign_id=None):
    """Named campaign, with the existing A website/inquiry service goal."""
    from .campaign_manager import create
    if campaign_id is not None:
        selected = db.one('SELECT name,goal FROM campaign_groups WHERE id=?', (campaign_id,))
        if not selected or selected['name'].casefold() != CAMPAIGN_NAME.casefold() or selected['goal'] != 'A':
            raise ValueError('Google Business discovery belongs in Campaign 3 with website/inquiry goal A')
    row = db.one('SELECT * FROM campaign_groups WHERE name=? COLLATE NOCASE', (CAMPAIGN_NAME,))
    if not row:
        try:
            cid = create(db, CAMPAIGN_NAME, 'A')
        except ValueError:
            row = db.one('SELECT * FROM campaign_groups WHERE name=? COLLATE NOCASE', (CAMPAIGN_NAME,))
            if not row:
                raise
        else:
            row = db.one('SELECT * FROM campaign_groups WHERE id=?', (cid,))
    if row['goal'] != 'A' or campaign_id is not None and row['id'] != campaign_id:
        raise ValueError('Google Business discovery belongs in Campaign 3 with website/inquiry goal A')
    return row['id']


def is_campaign(db, lead):
    row = db.one('SELECT name FROM campaign_groups WHERE id=?', (lead.get('campaign_id'),))
    return bool(row and row['name'] == CAMPAIGN_NAME and is_listing(lead.get('profile_url', '')))


def clean_document(html):
    soup = BeautifulSoup(html, 'html.parser')
    title = soup.title.get_text(' ', strip=True) if soup.title else ''
    if re.search(r'captcha|unusual traffic|verify you are human|security check', title, re.I) or soup.select_one('.g-recaptcha,iframe[src*="recaptcha"]'):
        return soup, 'login_or_challenge'
    if soup.select_one('form[action*="consent.google"],form[action*="/sorry/"]'):
        return soup, 'consent_or_challenge'
    for node in soup.select('script,style,nav,footer,aside,[hidden],[aria-hidden="true"],[role="dialog"],dialog,[data-review-id],.jftiEf,[data-section-id="reviews"]'):
        node.decompose()
    for node in list(soup.select('[style]')):
        if node.attrs and re.search(r'display\s*:\s*none|visibility\s*:\s*hidden', node.get('style', ''), re.I):
            node.decompose()
    return soup, ''


def parse_listing(url, html):
    target = listing_url(url)
    soup, blocked = clean_document(html)
    base = {'url': target, 'capture_method': 'google_business_visible_listing'}
    if blocked:
        return {**base, 'state': blocked}
    main = soup.select_one('[role="main"]') or soup.select_one('main')
    if not main or main.select_one('[role="feed"]'):
        return {**base, 'state': 'fields_not_ready'}
    if main.find(string=re.compile(r'^\s*(?:Permanently|Temporarily) closed\s*$', re.I)):
        return {**base, 'state': 'business_closed'}
    h1 = main.find('h1')
    if not h1 or not h1.get_text(' ', strip=True):
        return {**base, 'state': 'fields_not_ready'}
    name = h1.get_text(' ', strip=True)
    category = main.select_one('button[jsaction*="category"],button.DkEaL,[data-item-id="category"]')
    address = main.select_one('[data-item-id="address"],[aria-label^="Address:"]')
    phone = main.select_one('[data-item-id^="phone:"],[aria-label^="Phone:"]')
    if not any((category, address, phone)):
        return {**base, 'state': 'fields_not_ready'}
    def field(node, label):
        if not node:
            return ''
        value = node.get('aria-label') or node.get_text(' ', strip=True)
        return re.sub(r'^'+label+r'\s*:\s*', '', value, flags=re.I).strip()[:500]
    category_text, address_text, phone_text = field(category, 'Category'), field(address, 'Address'), field(phone, 'Phone')
    lines = [name]
    for label, value in [('Business category', category_text), ('Address', address_text), ('Phone', phone_text)]:
        if value:
            lines.append(label+': '+value)
    websites, profiles, emails = [], [], []
    from .discovery import official_root
    for a in main.select('a[data-item-id="authority"][href],a[aria-label^="Website:"][href]'):
        raw = urljoin(url, a['href'])
        if domain_of(raw) == 'google.com' and urlsplit(raw).path == '/url':
            raw = parse_qs(urlsplit(raw).query).get('q', parse_qs(urlsplit(raw).query).get('url', ['']))[0]
        try:
            websites.append(official_root(raw))
        except ValueError:
            if raw.startswith('https://'):
                profiles.append(raw)
    for a in main.select('a[data-item-id="email"][href^="mailto:"],a[aria-label^="Email:"][href^="mailto:"]'):
        try:
            email = normalize_email(a['href'][7:].split('?')[0])
        except ValueError:
            continue
        emails.append(email)
        lines.append('Business email: '+email)
    description = main.select_one('[data-section-id="description"],[data-item-id="description"]')
    if description:
        lines.append(description.get_text(' ', strip=True)[:3000])
    if websites:
        lines.append('Website: '+websites[0])
    text = '\n'.join(lines)
    return {**base, 'state': 'captured', 'title': name, 'name': name, 'text': text,
            'sha256': hashlib.sha256(text.encode()).hexdigest(), 'business_category': category_text,
            'address': address_text, 'public_phone': phone_text, 'published_emails': list(dict.fromkeys(emails)),
            'outgoing_websites': list(dict.fromkeys(websites)), 'public_links': profiles,
            'website_field': 'listed' if websites else 'not_observed', 'absence_confirmed': False}


def parse_search(url, html, limit):
    soup, blocked = clean_document(html)
    if blocked:
        return [], blocked
    feed = soup.select_one('[role="feed"]')
    if not feed:
        if is_listing(url):
            listing = parse_listing(url, html)
            if listing['state'] == 'captured':
                return [{'url': listing['url'], 'title': listing['title'], 'snippet': ''}], ''
        return [], 'fields_not_ready'
    found = {}
    for a in feed.select('a[href]'):
        try:
            target = listing_url(urljoin(url, a['href']))
        except ValueError:
            continue
        title = a.get('aria-label') or a.get_text(' ', strip=True)
        if title:
            found.setdefault(listing_key(target), {'url': target, 'title': title[:160], 'snippet': ''})
        if len(found) >= limit:
            break
    return list(found.values()), '' if found else 'fields_not_ready'


async def page(settings, url):
    """One bounded robots-permitted public page; never accept consent or bypass a hold."""
    web = PublicWeb(settings, signal_only=True)
    renderer = None
    try:
        robots, delay, _ = await web.robots(url)
        if not robots.can_fetch(settings.crawler_user_agent, url):
            return {'state': 'robots_denied', 'url': url}
        await asyncio.sleep(delay)
        final, html, status = await web.get(url, domain_of(url))
        if status != 200:
            return {'state': 'http_'+str(status), 'url': final, 'http_status': status}
        _, blocked = clean_document(html)
        if blocked:
            return {'state': blocked, 'url': url}
        if settings.browser_enabled:
            from .browser import RenderSession
            async with settings._platform_browser_lock:
                renderer = RenderSession(web)
                try:
                    await renderer.start()
                    result = await renderer.render(final, domain_of(final), robots, document=web.last_document)
                    if result.get('html'):
                        final, html = result['url'], result['html']
                finally:
                    await renderer.close()
        return {'state': 'captured', 'url': final, 'html': html}
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        return {'state': 'http_'+str(status), 'url': url, 'http_status': status}
    except Exception as exc:
        return {'state': 'source_unavailable', 'url': url, 'error_type': type(exc).__name__}


async def snapshot(settings, url):
    target = listing_url(url)
    result = await page(settings, target)
    if result['state'] != 'captured':
        return {k: v for k, v in result.items() if k != 'html'}
    if not is_listing(result['url']) or listing_key(result['url']) != listing_key(target):
        return {'state': 'listing_identity_changed', 'url': target}
    return parse_listing(result['url'], result['html'])


async def prospect_candidates(settings, query, country_hint, limit, on_signal=None, on_candidate=None, on_progress=None):
    from . import providers
    from .discovery import resolve_signal
    market = 'United Kingdom' if country_hint == 'UK' else 'United States'
    if country_hint not in {'UK', 'US'}:
        raise ValueError('Choose UK or US for Google business research')
    search = query if re.search(r'\b(?:UK|United Kingdom|US|USA|United States)\b', query, re.I) else query+' '+market
    url = 'https://www.google.com/maps/search/?'+urlencode({'api': 1, 'query': search, 'hl': 'en'})
    if on_progress:
        on_progress({'stage': 'google_maps_search', 'query': search})
    initial = await page(settings, url)
    rows, state = parse_search(initial['url'], initial.get('html', ''), max(30, limit)) if initial['state'] == 'captured' else ([], initial['state'])
    errors, skipped, signals, seen = [], [], [], set()
    if state:
        errors.append({'stage': 'maps_search', 'state': state})
    denied = {'robots_denied', 'login_or_challenge', 'consent_or_challenge', 'http_401', 'http_403', 'http_429', 'source_unavailable'}
    if state in denied:
        return [], {'source': 'google_maps', 'queries': [search], 'signals': [], 'errors': errors, 'skipped': [],
                    'captured_candidates': 0, 'pending_website_lookup': 0, 'requested_limit': limit, 'stop_reason': state,
                    'note': 'Google access needs attention. This run stopped without retrying listings or bypassing the restriction.'}
    # An independent public index can contribute listing references. Its snippets
    # remain hints; each selected listing still needs its own current capture.
    if len(rows) < limit:
        try:
            indexed = await providers.discover(settings, 'site:google.com/maps/place/ '+search, 30, include_platforms=True)
            errors.extend({'stage': 'maps_index', 'reason': str(i)[:150]} for i in getattr(indexed, 'engine_issues', []))
            rows += list(indexed)
        except Exception as exc:
            errors.append({'stage': 'maps_index', 'error_type': type(exc).__name__})
    retained, pending_lookup, unavailable = 0, 0, 0
    for row in rows[:min(60, max(10, limit*3))]:
        try:
            target = listing_url(row['url'])
        except ValueError:
            continue
        key = listing_key(target)
        if key in seen:
            continue
        seen.add(key)
        if on_progress:
            on_progress({'stage': 'google_business_check', 'company': row.get('title', ''), 'retained': retained})
        signal = await resolve_signal(settings, {**row, 'url': target}, country_hint, ['google.com'])
        signal['discovery_source'] = 'google_maps'
        signals.append(signal)
        snap = signal.get('public_snapshot', {})
        if snap.get('state') in denied:
            skipped.append({'url': target, 'reason': snap['state']})
            errors.append({'stage': 'listing_capture', 'state': snap['state']})
            break
        if signal.get('website'):
            skipped.append({'url': target, 'reason': 'official_website_found'})
        elif snap.get('state') != 'captured':
            skipped.append({'url': target, 'reason': snap.get('state', 'capture_unavailable')})
            unavailable += 1
            if unavailable >= 3:
                errors.append({'stage': 'listing_capture', 'state': 'repeated_incomplete_captures'})
                break
        else:
            if signal.get('state') != 'no_company_match' or not signal.get('website_search', {}).get('completed'):
                pending_lookup += 1
            retained += 1
            if on_signal and on_signal(signal):
                break
        if not on_signal and retained >= limit:
            break
    return [], {'source': 'google_maps', 'queries': [search], 'signals': signals, 'errors': errors, 'skipped': skipped,
                'captured_candidates': retained, 'pending_website_lookup': pending_lookup, 'requested_limit': limit,
                'note': 'Current Google listing plus bounded independent website lookup. Website not found is not proof of absence. Phone does not establish an email address.'}
