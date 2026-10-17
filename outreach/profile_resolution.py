"""Free public-source hints are candidates, never account access or email proof."""
import json
import re
import unicodedata
from urllib.parse import urljoin, urlsplit

from .web import company_crawl_url, domain_of


def identity_text(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', value.casefold()) if not unicodedata.combining(c))


def website_hints(row):
    from .discovery import official_root
    text = row.get('title', '')+' '+row.get('snippet', '')
    raw = re.findall(r'(?<![@\w])https?://[^\s<>"\']+', text, re.I)
    raw += re.findall(r'(?<![@\w.-])(?:www\.)?[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?\.(?:co\.uk|com|org|net|io|co|uk|shop|store)(?:/[^\s<>"\']*)?', text, re.I)
    result, seen = [], set()
    for value in raw[:30]:
        try:
            value = value.rstrip('.,;)]}')
            source = value if '://' in value else 'https://'+value
            root = official_root(source)
            url = company_crawl_url(source, domain_of(root))
            parts = urlsplit(url)
            key = (domain_of(url), parts.path, parts.query)
            if url and key not in seen:
                seen.add(key)
                result.append(url)
        except ValueError:
            pass
    return result[:6]


def organization_identity(soup, url):
    """Read the page's own Organization sameAs, excluding unrelated entities."""
    from .discovery import profile_key
    links, names = [], []
    def walk(value):
        if isinstance(value, list):
            for child in value:
                walk(child)
        elif isinstance(value, dict):
            kinds = value.get('@type', [])
            kinds = [kinds] if isinstance(kinds, str) else kinds
            own_url = value.get('url', '')
            owns_site = (not own_url and urlsplit(url).path in {'', '/'} or
                         isinstance(own_url, str) and bool(own_url) and domain_of(urljoin(url, own_url)) == domain_of(url)
                         and urlsplit(urljoin(url, own_url)).path in {'', '/'})
            if isinstance(kinds, list) and any(k in {'Organization', 'LocalBusiness', 'Corporation', 'Store'} for k in kinds) and owns_site:
                if isinstance(value.get('name'), str) and value['name'] not in names:
                    names.append(value['name'][:200])
                aliases = value.get('sameAs', [])
                aliases = [aliases] if isinstance(aliases, str) else aliases
                if isinstance(aliases, list):
                    for alias in aliases:
                        if isinstance(alias, str):
                            try:
                                from .profiles import canonical_profile
                                target = canonical_profile(alias)
                                if profile_key(target) not in {profile_key(u) for u in links}:
                                    links.append(target)
                            except ValueError:
                                pass
            for child in value.values():
                if isinstance(child, (dict, list)):
                    walk(child)
    for script in soup.select('script[type="application/ld+json"]')[:100]:
        try:
            walk(json.loads(script.string or script.get_text()))
        except (ValueError, TypeError, RecursionError):
            pass
    return {'links': links[:100], 'names': names[:20]}


def organization_links(soup, url):
    return organization_identity(soup, url)['links']


def lookup_queries(name, profile_url, country):
    safe = name.replace('"', ' ').strip()
    return [f'"{safe}" official website {country}',
            f'"{profile_url}" -site:linkedin.com -site:x.com -site:twitter.com',
            f'"{safe}" (contact OR about OR team) {country}']
