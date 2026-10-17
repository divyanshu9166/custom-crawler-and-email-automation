"""Automatic public platform research and conservative company-site resolution.

Search snippets are indexed signals, never current official ownership evidence.
Direct snapshots honor robots and refuse login/challenge pages. Published signal
emails are retained for review; official website research owns contact imports.
"""
import asyncio
import hashlib
import re
import time
from urllib.parse import urlsplit, urlunsplit, urljoin

from bs4 import BeautifulSoup

from . import providers
from .web import PublicWeb, BLOCKED_SOURCES, EMAIL_RE, crawl_url, domain_of, extract_page, normalize_email

DIRECTORIES = {"clutch.co", "crunchbase.com", "trustpilot.com", "yelp.com", "bbb.org",
               "yellowpages.com", "superpages.com", "yell.com", "thomsonlocal.com", "coffeeroaster.com",
               "angi.com", "homeadvisor.com", "treatwell.co.uk", "dentaly.org", "docdental.uk",
               "the-coffee-box.com", "roastlocal.com"}
NON_COMPANY = BLOCKED_SOURCES | DIRECTORIES | {"google.com", "bing.com", "duckduckgo.com", "youtube.com", "t.co", "bit.ly", "linktr.ee", "wikipedia.org", "instagram.com", "amazon.com", "amazon.co.uk", "ebay.com", "ebay.co.uk", "reddit.com"}

# Indexed results can identify candidates, but cannot establish official ownership.
# Keep known editorial/marketplace results out of both site imports and profile
# resolution. Directory signals remain available through configured platforms.
NON_PROSPECT_HOSTS = {"independent.co.uk", "theguardian.com", "bbc.com", "bbc.co.uk",
                      "nytimes.com", "forbes.com", "flipkart.com", "etsy.com",
                      "indiamart.com", "exportersindia.com", "tradeindia.com", "alibaba.com",
                      "wikipedia.org", "reddit.com", "youtube.com", "amazon.com", "amazon.co.uk", "ebay.com", "ebay.co.uk"}


def indexed_exclusion(row):
    host = domain_of(row["url"])
    if any(host == d or host.endswith("." + d) for d in NON_PROSPECT_HOSTS):
        return "editorial_or_marketplace_source"
    title = row.get("title", "")
    snippet = row.get('snippet', '')
    if (re.search(r"\b(?:business|roaster|company|companies|supplier) directory\b|\bfind (?:the )?best\b|\b(?:top|best) \d+\b|\b\d+ (?:top|best)\b|\bas told by\b", title, re.I)
            or re.search(r'\b\d{1,3}\s+(?:most|leading|successful|impressive)\b[^.!?]{0,100}\b(?:founders?|companies|brands?|startups?|suppliers?)\b', title, re.I)
            or re.search(r'\b(?:this|our|the) list\s+(?:showcases|ranks|lists|features)\b[^.!?]{0,160}\b(?:founders?|companies|brands?|startups?|suppliers?)\b', snippet, re.I)
            or re.search(r'\bour directory (?:includes|lists|contains)\b|\b\d+ verified listings\b', snippet, re.I)):
        return "directory_or_listicle_result"
    return ""


def platform_of(url, configured=()):
    domain = domain_of(url)
    return next((p for p in NON_COMPANY | set(configured) if domain == p or domain.endswith("." + p)), "")


def company_title(title):
    pieces = re.split(r"\s[|–—]\s|\s-\s|\s/\s", title)
    name = pieces[0]
    if len(pieces) > 1 and re.fullmatch(r'home|contact us|about us|order .{1,80} online|shop (?:online|now)', name, re.I):
        name = pieces[-1]
    elif len(pieces) > 1 and re.fullmatch(r'team|our team|meet the team|about|our story|news|leadership', name, re.I):
        # Page-label prefixes precede the publisher brand: "Team | IF_DO —
        # Architecture & Design" and "Our Story - ELEMIS". Still only a name
        # hint; current business identity requires independent review.
        name = pieces[1]
    name = re.sub(r"\s*\(@[^)]+\)", "", name)
    return re.sub(r"\s+(?:on |at )?(?:LinkedIn|Twitter|X)$", "", name, flags=re.I).strip()[:160]


def official_root(url):
    value = crawl_url(url)
    if platform_of(value) or indexed_exclusion({"url": value}):
        raise ValueError("Platform or directory is not an official company website")
    parts = urlsplit(value)
    return urlunsplit((parts.scheme, parts.netloc, "/", "", ""))


async def public_snapshot(settings, url, platform=False):
    if platform and settings.platform_browser_enabled and platform_of(url) in {'linkedin.com','x.com','twitter.com'}:
        from .platform_browser import browser_snapshot
        return await browser_snapshot(settings,url)
    if platform and platform_of(url) in {'x.com', 'twitter.com'} and '/status/' in urlsplit(url).path:
        from .public_posts import public_post_snapshot
        return await public_post_snapshot(settings, url)
    web = PublicWeb(settings, signal_only=platform)
    try:
        url = crawl_url(url)
        robots, delay, _ = await web.robots(url)
        if not robots.can_fetch(settings.crawler_user_agent, url):
            return {"state": "robots_denied", "url": url}
        await asyncio.sleep(delay)
        final, html, code = await web.get(url, domain_of(url))
        if code == 404:
            return {"state": "not_found", "url": url}
        soup = BeautifulSoup(html, "html.parser")
        title = soup.title.get_text(" ", strip=True) if soup.title else ""
        if soup.select_one('input[type="password"]') or re.search(r"captcha|verify you are human|just a moment|sign in to|log in to|security check", title, re.I):
            return {"state": "login_or_challenge", "url": final}
        page = extract_page(final, html)
        http_snapshot = {'state': 'captured', 'url': final, 'title': title,
            'text': page['text'][:12000], 'sha256': page['sha256'],
            'capture_method': 'public_html', 'named_people': page.get('named_people', []),
            'public_links': page['links'][:500]}
        rendered, render_attempted, render_issues = False, False, []
        should_render = settings.crawl_render_mode == 'always' or (
            settings.crawl_render_mode == 'auto' and len(page['text']) < 300)
        if not platform and settings.browser_enabled and should_render:
            # Normal rendering of an allowed official page only; no alternate
            # client for robots-denied, login or challenge platform profiles.
            from .browser import RenderSession
            renderer = RenderSession(web)
            render_attempted = True
            try:
                await renderer.start()
                result = await renderer.render(final, domain_of(final), robots, document=web.last_document)
                render_issues = result.get('issues', [])[:20]
                if result.get('html'):
                    if domain_of(result.get('url', '')) != domain_of(final):
                        raise ValueError('Rendered source moved outside the official domain')
                    html, final = result['html'], result['url']
                    soup = BeautifulSoup(html, 'html.parser')
                    title = soup.title.get_text(' ', strip=True) if soup.title else ''
                    if soup.select_one('input[type="password"]') or re.search(r'captcha|verify you are human|just a moment|sign in to|log in to|security check', title, re.I):
                        return {'state': 'login_or_challenge', 'url': final}
                    page, rendered = extract_page(final, html), True
            except Exception as exc:
                render_issues.append({'reason': 'official_render_unavailable', 'error_type': type(exc).__name__})
            finally:
                try:
                    await renderer.close()
                except Exception as exc:
                    render_issues.append({'reason': 'official_render_cleanup_issue', 'error_type': type(exc).__name__})
        from .profile_resolution import organization_identity
        email_links = []
        for anchor in soup.select('a[href^="mailto:"]'):
            try:
                email_links.append(normalize_email(anchor["href"][7:].split("?")[0]))
            except ValueError:
                pass
        outgoing = []
        for a in soup.select("a[href]"):
            label = a.get_text(" ", strip=True)
            if re.search(r"website|visit (?:site|company)|official|\bwww\.", label, re.I):
                try:
                    target = official_root(urljoin(final, a["href"]))
                    if domain_of(target) != domain_of(final):
                        outgoing.append(target)
                except ValueError:
                    pass
        for c in soup.select('script[type="application/ld+json"]'):
            # Published Organization metadata is a signal, not owner verification.
            import json
            try:
                def walk(value):
                    if isinstance(value, list):
                        for v in value:
                            walk(v)
                    elif isinstance(value, dict):
                        kind = value.get("@type", "")
                        if kind in ("Organization", "LocalBusiness") and isinstance(value.get("url"), str):
                            try:
                                target = official_root(value["url"])
                                if domain_of(target) != domain_of(final):
                                    outgoing.append(target)
                            except ValueError:
                                pass
                        for v in value.values():
                            if isinstance(v, (dict, list)):
                                walk(v)
                walk(json.loads(c.string or c.get_text()))
            except (ValueError, TypeError, RecursionError):
                pass
        identity = organization_identity(soup, final)
        return {"state": "captured", "url": final, "title": title, "text": page["text"][:12000],
                "sha256": page["sha256"], "published_emails": page["emails"] + [c["email"] for c in page["review_candidates"]],
                "published_email_links": list(dict.fromkeys(email_links)),
                "outgoing_websites": list(dict.fromkeys(outgoing))[:10], "public_links": page["links"][:500],
                'organization_profile_links': identity['links'], 'organization_names': identity['names'],
                'rendered': rendered, 'render_attempted': render_attempted,
                'render_mode': 'public_http' if platform else settings.crawl_render_mode,
                'render_issues': render_issues, 'named_people': page.get('named_people', []),
                'http_snapshot': http_snapshot if rendered else None}
        # Snapshot scope is a selected public page, not a completeness claim.
    except Exception as exc:
        return {"state": "unavailable", "url": url, "error_type": type(exc).__name__}


def name_matches(name, text):
    from .profile_resolution import identity_text
    tokens = [t for t in re.findall(r"[a-z0-9]+", identity_text(name)) if len(t) >= 2 and t not in {"the", "ltd", "limited", "inc", "company", "uk", "us", "usa"}]
    haystack = set(re.findall(r"[a-z0-9]+", identity_text(text)))
    return bool(tokens) and all(t in haystack for t in tokens)


def query_relevant(query, row):
    cleaned = re.sub(r"site:\S+", "", query.lower())
    stop = {"uk", "us", "usa", "united", "kingdom", "states", "contact", "official", "website", "business", "company", "companies", "brand", "brands", "independent", "the", "and", "for", "with", "in",
            "local", "online", "shop", "shops", "specialty", "speciality"}
    terms = [t for t in re.findall(r"[a-z0-9]+", cleaned) if len(t) > 2 and t not in stop]
    text = (row.get("title", "") + " " + row.get("snippet", "")).lower()
    # A location/adjective cannot substitute for the requested industry. Actual
    # live search engines sometimes return a dictionary article or local-time
    # page for a multiword query. Preserve common business vocabulary variants;
    # this is only indexed relevance, never identity or geography verification.
    subjects = (
        r"\b(?:dental\w*|dentist\w*|dentistry)\b",
        r"\b(?:roof\w*)\b",
        r"\b(?:florist\w*|floral|flowers?|bouquets?)\b",
        r"\b(?:coffee|roaster\w*|roastery|roasteries)\b",
        r"\b(?:skincare|skin\s+care|cosmetics?|beauty)\b",
    )
    required = [subject for subject in subjects if re.search(subject, cleaned)]
    if required:
        return all(re.search(subject, text) for subject in required)
    return not terms or any(re.search(r"\b" + re.escape(t), text) for t in terms)


def indexed_market_exclusion(row, country_hint):
    """Explicit conflicting search signals are exclusions, not verified location."""
    host = domain_of(row['url'])
    text = row.get('title', '') + ' ' + row.get('snippet', '')
    # "Contact US" is often an all-caps navigation label, not geography.
    us = r'\b(?i:USA|United States|America|American)\b|\bU\.S\.(?:A\.)?|\bUS[-\s]+(?i:based|office|company|store|business|location|market|brand)\b'
    uk = r'\b(?i:UK|United Kingdom|Britain|British)\b'
    target = uk if country_hint == 'UK' else us
    if re.search(target, text):
        return ''  # Mixed/target presence still requires current source review.
    foreign_suffixes = ('.in', '.pk', '.bd', '.au', '.nz', '.za', '.ng', '.ae', '.sg')
    foreign_country = r'\b(?:India|Indian|Pakistan|Bangladesh|Australia|New Zealand|South Africa|Nigeria|Singapore)\b'
    other_market = us if country_hint == 'UK' else uk
    if host.endswith(foreign_suffixes) or re.search(foreign_country, text, re.I) or re.search(other_market, text):
        return 'indexed_market_conflict'
    return ''


def focused_query(query, country_hint):
    """One bounded retry removes vague modifiers without inventing a new niche."""
    words = re.findall(r'[a-z0-9]+', re.sub(r'site:\S+', '', query.lower()))
    vague = {'local', 'independent', 'specialty', 'speciality', 'official', 'online',
             'company', 'companies', 'business', 'brand', 'brands', 'shop', 'shops',
             'contact', 'website', 'the', 'and', 'for', 'with', 'in',
             'us', 'usa', 'uk', 'united', 'states', 'kingdom'}
    terms = [word for word in words if word not in vague]
    return (' '.join(terms) + (' United States' if country_hint == 'US' else ' United Kingdom')).strip() if terms else ''


def relaxed_profile_query(query, country_hint):
    """One public-index retry retains platform, profile path, sector and roles.

    Only the trailing search-market term and phrase quoting are relaxed. Source
    country/identity review still applies; this never approves geography.
    """
    match = re.fullmatch(r'site:(linkedin\.com/(?:in|company)/|x\.com|twitter\.com)\s+(.+)', query)
    if not match or country_hint not in {'US', 'UK'}:
        return ''
    host, body = match.groups()
    roles = ''
    suffix = re.search(r'\s+(\(founder OR owner OR director OR marketing\))$', body)
    if suffix:
        roles = ' '+suffix[1]
        body = body[:suffix.start()]
    # Leave arbitrary operators/parentheses alone rather than rewriting their
    # semantics. This path is for the normal generated sector/profile query.
    if not re.fullmatch(r'[A-Za-z0-9\s"\x27&.-]+', body):
        return ''
    market = r'(?:United States|USA|US)' if country_hint == 'US' else r'(?:United Kingdom|UK)'
    core = re.sub(r'\s+"?'+market+r'"?$', '', body, flags=re.I)
    if core == body:
        return ''  # No explicit trailing search-market constraint to relax.
    core = ' '.join(core.replace('"', '').split())
    if not core or not re.search(r'[A-Za-z]{3}', core):
        return ''
    return f'site:{host} {core}{roles}'


def profile_key(url):
    parts = urlsplit(url)
    domain = domain_of(url)
    if domain == 'linkedin.com' or domain.endswith('.linkedin.com'):
        domain = "linkedin.com"
    if domain in {"twitter.com", "x.com"}:
        domain = "x.com"
    return domain, parts.path.rstrip("/").lower()


def brand_key(name):
    from .profile_resolution import identity_text
    return "".join(t for t in re.findall(r"[a-z0-9]+", identity_text(name))
                   if t not in {"uk", "us", "usa", "ltd", "limited", "inc", "llc"})


def brand_domain_candidate(name, website):
    labels = domain_of(website).split('.')
    suffix_size = 2 if '.'.join(labels[-2:]) in {'co.uk', 'org.uk', 'me.uk'} else 1
    return len(labels) > suffix_size and brand_key(name) == labels[-suffix_size-1]


async def resolve_signal(settings, row, country_hint, platforms):
    signal = {"source_url": row["url"], "source_title": row.get("title", ""), "indexed_snippet": row.get("snippet", "")[:3000],
              "indexed_signal_only": True, "platform": platform_of(row["url"], platforms), "website": "", "state": "unresolved"}
    snapshot = await public_snapshot(settings, row["url"], platform=True)
    signal["public_snapshot"] = snapshot
    signal['access_path'] = 'public_profile' if snapshot.get('state') == 'captured' else 'independent_public_sources'
    managed=snapshot.get('capture_method')=='managed_browser_public_profile'
    if managed:
        signal['access_path']='managed_browser_public_profile'
        signal['indexed_signal_only']=snapshot.get('state')!='captured'
        if snapshot.get('state')!='captured' and not settings.platform_browser_public_fallback:
            signal['state']=snapshot.get('state','browser_unavailable')
            return signal
    public_post = snapshot.get('capture_method') == 'official_public_oembed'
    profile_reference = snapshot.get('author_url', row['url']) if public_post else row['url']
    if public_post:
        signal['access_path'] = 'official_public_post_api'
        signal['profile_snapshot'] = False
        signal['indexed_signal_only'] = snapshot.get('state') != 'captured'
        if snapshot.get('state') != 'captured':
            signal['state'] = snapshot.get('state', 'public_post_unavailable')
            return signal
    community = {}
    if settings.fxembed_profiles_enabled and not public_post and snapshot.get('state') != 'captured' and signal['platform'] in {'x.com', 'twitter.com'}:
        from .fxembed import profile_hint
        try:
            community = await profile_hint(settings, row['url'])
        except ValueError:
            # A post/search/private route is not a profile lookup target.
            community = {}
        if community:
            signal['community_profile_hint'] = community
            signal['community_source_is_first_party'] = False
    signal["indexed_email_candidates"] = []
    for address in re.findall(EMAIL_RE, signal["indexed_snippet"]):
        try:
            value = normalize_email(address)
            if value not in signal["indexed_email_candidates"]:
                signal["indexed_email_candidates"].append(value)
        except ValueError:
            pass
    signal["indexed_sha256"] = hashlib.sha256((signal["source_title"] + "\n" + signal["indexed_snippet"]).encode()).hexdigest()
    if signal['platform'] == 'linkedin.com' and '/in/' in urlsplit(row['url']).path:
        from .linkedin_recovery import resolve_person_signal
        return await resolve_person_signal(settings, row, country_hint, signal)
    # Explicit platform website links take precedence. Multiple distinct companies stay held.
    direct = snapshot.get("outgoing_websites", []) if not public_post else []
    if len({domain_of(u) for u in direct}) == 1:
        signal.update(website=direct[0], state="linked_website_candidate", company=snapshot['title'] if managed else company_title(row.get("title", "")))
        return signal
    if len({domain_of(u) for u in direct}) > 1:
        signal["state"] = "ambiguous_websites"
        return signal
    name = snapshot['title'] if public_post else company_title(row.get("title", ""))
    if managed:
        name=snapshot['title'] if snapshot.get('state')=='captured' else name
        if not settings.platform_browser_public_fallback:
            signal.update(company=name,state='website_link_not_observed',website_search={'completed':False,'queries':[],
                'note':'No website field observed. This is not evidence that the business has no website.'})
            return signal
        signal.update(access_path='independent_public_sources',
            source_failover={'used':True,'profile_state':snapshot.get('state','unavailable'),
                             'transport':'free_search_and_official_pages','platform_access_recovered':False})
        # Failover uses only the configured free index plus independent public
        # company pages. Never re-request a denied profile or switch to a paid API.
        settings=settings.model_copy(update={'search_provider':'searxng','serpapi_key':''})
    signal["company"] = name
    # Individual profiles/empty titles do not establish a company name.
    if not name or len(name) < 4:
        return signal
    from .profile_resolution import lookup_queries, website_hints
    hints = website_hints(row)
    if community.get('state') == 'public_mirror_hint':
        hints = list(dict.fromkeys(website_hints({'snippet': community.get('description', '')+' '+community.get('published_website_hint', '')}) + hints))[:6]
    if public_post:
        hints = list(dict.fromkeys(snapshot.get('outgoing_websites', [])+website_hints({'snippet': snapshot.get('text', '')})+hints))[:6]
    hint_roots = {domain_of(h) for h in hints}
    signal['indexed_website_hints'] = hints
    for hinted in hints[:2]:
        official = await public_snapshot(settings, hinted)
        links = official.get('organization_profile_links', [])+official.get('public_links', [])
        if (official.get('state') == 'captured' and name_matches(name, official.get('title', '')+' '+official.get('text', '')[:1500])
                and any(profile_key(link) == profile_key(profile_reference) for link in links)):
            signal.update(website=official_root(hinted), company=name, state='reciprocal_profile_link_candidate',
                official_match_url=official.get('url', hinted), official_snapshot_sha256=official['sha256'],
                match_note='Published official-page backlink corroborates the indexed domain; identity and buyer review still required',
                website_search={'completed': False, 'queries': [], 'engine_issues': [],
                    'note': 'Explicit indexed domain checked against a current official-page backlink; no website absence assertion'})
            return signal
    candidates, searches, failures = [], [], []
    for search in lookup_queries(name, profile_reference, country_hint):
        # Strong named candidates are inspected by the existing conservative
        # matcher; fallback queries are used when the first search finds none.
        if candidates and any(name_matches(name, c.get('title', '')) and not indexed_exclusion(c)
                              and not platform_of(c.get('url', '')) and not indexed_market_exclusion(c, country_hint) for c in candidates):
            break
        await asyncio.sleep(settings.discovery_query_delay_seconds)
        try:
            rows = await providers.discover(settings, search, 10)
            searches.append({'query': search, 'result_count': len(rows), 'engine_issues': getattr(rows, 'engine_issues', []),
                             'providers': getattr(rows, 'provider_reports', [])})
            candidates.extend(rows)
        except Exception as exc:
            failures.append({'query': search, 'error_type': type(exc).__name__})
    # A domain explicitly printed in the index can be checked even if engines
    # are down. It is still held unless current official content matches.
    candidates.extend({'url': u, 'title': '', 'hint_only': True} for u in hints)
    signal['website_search'] = {'query': searches[0]['query'] if searches else lookup_queries(name, profile_reference, country_hint)[0],
        'queries': searches, 'errors': failures, 'completed': bool(searches) and not failures and not any(q['engine_issues'] for q in searches),
        'checked_at': time.time(), 'engine_issues': [i for q in searches for i in q['engine_issues']],
        'result_count': len(candidates), 'note': 'Bounded public search coverage; no result is not proof that no website exists.'}
    matching = {}
    for candidate in candidates:
        try:
            if indexed_exclusion(candidate) or indexed_market_exclusion(candidate, country_hint):
                continue
            website = official_root(candidate["url"])
            if (name_matches(name, candidate.get("title", "")) or domain_of(website) in hint_roots
                    or profile_key(profile_reference)[1] in candidate.get('snippet', '').lower()):
                matching.setdefault(domain_of(website), (website, candidate))
        except ValueError:
            pass
    if not matching:
        signal["state"] = "search_unavailable" if failures and not searches else "no_company_match"
        return signal
    inspected = []
    ranked = sorted(matching.values(), key=lambda item: brand_key(name) != domain_of(item[0]).split(".")[0])
    for website, candidate in ranked[:4]:
        source_url = candidate['url'] if domain_of(candidate['url']) == domain_of(website) else website
        homepage = await public_snapshot(settings, website)
        root_identity = (homepage.get('state') == 'captured' and name_matches(name,
                         homepage.get('title', '')+' '+homepage.get('text', '')[:1500]))
        owner_identity = (homepage.get('state') == 'captured' and
                          (name_matches(name, homepage.get('title', '')) or
                           any(name_matches(name, n) for n in homepage.get('organization_names', [])) or
                           brand_domain_candidate(name, website) and root_identity))
        official = homepage
        if source_url != website:
            leaf = await public_snapshot(settings, source_url)
            own_links = leaf.get('organization_profile_links', [])
            leaf_identity = (leaf.get('state') == 'captured' and name_matches(name,
                             leaf.get('title', '')+' '+leaf.get('text', '')[:1500]))
            leaf_owned = (owner_identity or
                          homepage.get('state') != 'captured' and brand_key(name) == domain_of(website).split('.')[0] or
                          any(profile_key(link) == profile_key(profile_reference) for link in own_links))
            if leaf_identity and leaf_owned:
                official = leaf
        official = {**official, 'homepage_identity_match': owner_identity}
        inspected.append((website, candidate, official))
    signal["resolution_candidates"] = [{"website": website, "snapshot_state": official["state"],
                                        'source_page': official.get('url'),
                                        'homepage_identity_match': official.get('homepage_identity_match'),
                                        'organization_names': official.get('organization_names', []),
                                        "name_matches_official": official["state"] == "captured" and name_matches(name, official.get("title", "") + " " + official.get("text", "")[:1500])}
                                       for website, _, official in inspected]
    reciprocal = [(website, candidate, official) for website, candidate, official in inspected
                  if official["state"] == "captured" and name_matches(name, official.get('title', '')+' '+official.get('text', '')[:1500])
                  and any(profile_key(link) == profile_key(profile_reference) for link in official.get("public_links", [])+official.get('organization_profile_links', []))]
    if len(reciprocal) > 1:
        signal['state'] = 'ambiguous_reciprocal_matches'
        return signal
    if len(reciprocal) == 1:
        website, candidate, official = reciprocal[0]
        signal.update(website=website, company=name, state="reciprocal_profile_link_candidate",
                      official_match_url=official.get('url', website),
                      resolution_search_url=candidate["url"], official_snapshot_sha256=official["sha256"])
        return signal
    exact_domain = [(website, candidate, official) for website, candidate, official in inspected
                    if brand_domain_candidate(name, website)
                    and official["state"] == "captured"
                    and name_matches(name, official.get("title", "") + " " + official.get("text", "")[:1500])]
    if len(exact_domain) > 1 and country_hint == "UK" and re.search(r"\bUK\b", name, re.I):
        regional = [item for item in exact_domain if domain_of(item[0]).endswith(".uk")]
        if len(regional) == 1:
            exact_domain = regional
    if len(exact_domain) == 1:
        website, candidate, official = exact_domain[0]
        signal.update(website=website, company=name, state="exact_brand_domain_candidate",
                      official_match_url=official.get('url', website),
                      resolution_search_url=candidate["url"], official_snapshot_sha256=official["sha256"],
                      match_note="Name/domain/content correlation only; not verified identity or contact ownership")
        return signal
    if len(matching) != 1:
        current_matches = [(w, c, o) for w, c, o in inspected if o.get('homepage_identity_match') and
                           o.get('state') == 'captured' and name_matches(name, o.get('title', '')+' '+o.get('text', '')[:1500])]
        if len(current_matches) != 1:
            signal["state"] = "ambiguous_search_matches"
            return signal
        website, candidate, official = current_matches[0]
    else:
        website, candidate, official = inspected[0]
    if official["state"] == "captured" and name_matches(name, official.get("title", "") + " " + official.get("text", "")[:1500]):
        signal.update(website=website, company=name, state="name_matched_website_candidate",
                      official_match_url=official.get('url', website),
                      resolution_search_url=candidate["url"], official_snapshot_sha256=official["sha256"])
    else:
        signal["state"] = "official_match_unconfirmed"
    return signal


async def prospect_candidates(settings, query, country_hint, limit, on_signal=None, on_candidate=None, on_progress=None):
    # Consumers may return True once their retained website/profile record
    # quota is met. False means they own that mixed-record budget; None keeps
    # the default unique-website budget for observers and read-only callers.
    if country_hint not in {"US", "UK"}:
        raise ValueError("Choose the US or UK discovery market")
    settings = settings.model_copy(update={"search_language": "en-US" if country_hint == "US" else "en-GB"})
    aliases = r"\b(?:US|USA|United States)\b" if country_hint == "US" else r"\b(?:UK|United Kingdom)\b"
    market_query = query if re.search(aliases, query, re.I) else query + (" United States" if country_hint == "US" else " United Kingdom")
    platforms = [p.strip().lower() for p in settings.discovery_platforms.split(",") if p.strip()]
    if len(platforms) > 8 or any(not re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,}", p) for p in platforms):
        raise ValueError("Configure up to eight valid public platform domains")
    paths = {"linkedin.com": "linkedin.com/company/", "google.com": "google.com/maps/"}
    queries = [market_query] + [f"site:{paths.get(p, p)} {market_query}" for p in platforms]
    if 'linkedin.com' in platforms:
        queries.append(f'site:linkedin.com/in/ {market_query} (founder OR owner OR director OR marketing)')
    managed_queries={}
    if settings.platform_browser_enabled:
        managed_queries={f'browser:{p} {market_query}':p for p in ('linkedin.com','x.com')}
        queries=list(managed_queries)+(queries if settings.platform_browser_public_fallback else [])
        if settings.platform_browser_public_fallback:
            settings=settings.model_copy(update={'search_provider':'searxng','serpapi_key':''})
    found, signals, errors, skipped, engine_reports = {}, [], [], [], []
    relaxed_queries = {}
    seen_signals = set()
    executed_queries = []
    stop_reason = 'queries_exhausted'
    for search in queries:
        executed_queries.append(search)
        if on_progress:
            on_progress({"stage": "query_started", "query": search, "candidate_domains": len(found), "signals": len(signals)})
        if search != queries[0]:
            await asyncio.sleep(settings.discovery_query_delay_seconds)
        try:
            if search in managed_queries:
                from .platform_browser import browser_discover
                rows=await browser_discover(settings,managed_queries[search],market_query,min(30,max(10,limit)))
            else:
                # Retrieve a small overfetch before directory/profile filtering
                # and company-domain deduplication consume the requested slots.
                rows = await providers.discover(settings, search, 30, include_platforms=True)
            engine_reports.append({"query": search, "engine_issues": getattr(rows, "engine_issues", []),
                'providers':getattr(rows,'provider_reports',[]),
                'source':managed_queries.get(search,'public_search'),'results':len(rows),
                'fallback_of': relaxed_queries.get(search),
                'search_market_constraint_relaxed': search in relaxed_queries})
        except Exception as exc:
            errors.append({"query": search, "error_type": type(exc).__name__})
            if on_progress:
                on_progress({"stage": "query_failed", "query": search, "error_type": type(exc).__name__})
            continue
        if not rows and search not in managed_queries and search not in relaxed_queries:
            retry = relaxed_profile_query(search, country_hint)
            if retry and retry not in queries:
                # Insert immediately after this exhausted query. It runs through
                # the same pacing, budgets, deduplication and source review.
                queries.insert(queries.index(search)+1, retry)
                relaxed_queries[retry] = search
        for row in rows:
            try:
                if not query_relevant(query, row) and search not in managed_queries:
                    skipped.append({"url": row["url"], "reason": "no_query_term_in_indexed_result"})
                    continue
                exclusion = indexed_exclusion(row)
                if exclusion:
                    skipped.append({"url": row["url"], "reason": exclusion})
                    continue
                exclusion = indexed_market_exclusion(row, country_hint)
                if exclusion:
                    skipped.append({"url": row["url"], "reason": exclusion})
                    continue
                platform = platform_of(row["url"], platforms)
                if platform:
                    from .profiles import canonical_profile
                    try:
                        if platform in {'x.com', 'twitter.com'} and '/status/' in urlsplit(row['url']).path:
                            from .public_posts import x_post_url
                            x_post_url(row['url'])
                        elif platform == 'linkedin.com' and '/in/' in urlsplit(row['url']).path:
                            from .professionals import professional_target
                            from .people import indexed_person_name
                            professional_target(row['url'])
                            if not indexed_person_name(company_title(row.get('title', ''))):
                                raise ValueError('Individual result lacks a usable named-person hint')
                        else:
                            canonical_profile(row["url"])
                    except ValueError:
                        skipped.append({"url": row["url"], "reason": "not_a_supported_specific_business_profile"})
                        continue
                    if row["url"] in seen_signals:
                        continue
                    seen_signals.add(row["url"])
                    if len(signals) >= settings.discovery_max_signals:
                        skipped.append({"url": row["url"], "reason": "signal_budget"})
                        continue
                    try:
                        signal = await resolve_signal(settings, row, country_hint, platforms)
                    except Exception as exc:
                        signal = {"source_url": row["url"], "platform": platform, "state": "resolution_unavailable", "error_type": type(exc).__name__}
                    signals.append(signal)
                    if not signal.get("website"):
                        if on_signal and on_signal(signal) is True:
                            stop_reason = 'requested_limit'
                            break
                        continue
                    candidate = {"url": signal["website"], "source_url": row["url"], "title": signal.get("company") or row.get("title", ""),
                                 'research_seed_url': signal.get('official_match_url', signal['website'])}
                else:
                    candidate = {**row, "url": official_root(row["url"]), "source_url": row["url"],
                                 'research_seed_url': row['url'],
                                 "identity_status": "indexed_candidate_needs_review"}
                domain = domain_of(candidate["url"])
                first = domain not in found
                found.setdefault(domain, candidate)
                budget_result = on_candidate(candidate) if first and on_candidate else None
                if platform and on_signal:
                    signal_budget = on_signal(signal)
                    if signal_budget is True or budget_result is True:
                        budget_result = True
                    elif signal_budget is False:
                        budget_result = False
                if budget_result is True or (first and budget_result is None and len(found) >= limit):
                    stop_reason = 'requested_limit'
                    break
            except (ValueError, KeyError):
                continue
        if on_progress:
            on_progress({"stage": "query_finished", "query": search, "candidate_domains": len(found), "signals": len(signals)})
        if stop_reason == 'requested_limit':
            break
        if search == queries[0] and not found and not settings.platform_browser_enabled:
            retry = focused_query(query, country_hint)
            if retry and retry.lower() != market_query.lower():
                queries.insert(1, retry)
    return list(found.values())[:limit], {"queries": queries, "signals": signals, "errors": errors, "skipped": skipped, "engine_reports": engine_reports,
                                       'relaxed_queries': relaxed_queries,
                                       'stop_reason': stop_reason, 'requested_limit': limit, 'executed_queries': executed_queries,
                                       "candidate_domains_before_limit": len(found), "country_hint": country_hint,
                                       "note": "Automatic indexed/public research. Every company, geography, contact owner and offer remains unqualified until reviewed; indexed snippets can be stale."}
