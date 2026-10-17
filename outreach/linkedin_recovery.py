"""Recover LinkedIn-linked people from current independent company pages.

This never retries a denied profile, reads a private panel, or treats an index
snippet as email publication. A company-owned team page must link the exact
profile in the same named staff card. All candidates remain unqualified.
"""
import asyncio
import re
import time
from urllib.parse import unquote, urlsplit

# Contact brokers and people directories are not the current employer's own
# publication. Do not turn their copied/guessed contacts into official evidence.
CONTACT_AGGREGATORS = {'rocketreach.co', 'revonect.com', '192.com', 'contactout.com',
    'signalhire.com', 'zoominfo.com', 'lusha.com', 'apollo.io', 'whitepages.com', 'peekyou.com'}
INDIRECT_EMPLOYER_ROOTS = CONTACT_AGGREGATORS | {'findglocal.com', 'endole.co.uk', 'ipaddress.com', 'shop.app', 'teaandcoffee.net'}


def indexed_employer_hint(row):
    """A declared employer phrase guides a query; it never verifies employment."""
    from .people import ROLE
    text = row.get('title', '')+' | '+row.get('snippet', '')
    # Internal name connectors are part of the declared employer: truncating
    # "Dental Care of Corona" to "Dental Care" sends recovery to unrelated firms.
    # Require a capitalized word after the connector so trailing role prose is
    # not swallowed (e.g. "Bright Demo with a focus on services").
    # A capitalized first-person contraction can begin the next sentence even
    # when search snippets omit punctuation: "Skincare Scientists I’m ...".
    # Keep legitimate apostrophes in company names, but stop before that prose.
    word = r'(?!(?:I[\x27’](?:m|ve|ll|d)|We[\x27’](?:re|ve|ll|d))\b)[A-Z][A-Za-z0-9&.\x27’_-]*'
    tail = r'(?:\s+(?:(?:of|the|and|de|la|van|von|&)\s+){0,2}'+word+r'){0,6}'
    pattern = r'(?P<quote>'+ROLE+r'\s+(?:at|within|of|for)\s+(?P<company>[A-Za-z0-9][A-Za-z0-9&.\x27’_-]*'+tail+r'))'
    for match in re.finditer(pattern, text):
        name = match['company'].rstrip('.,').strip()
        if (len(name) < 2 or len(name) > 120 or not any(c.isupper() for c in name)
                or name.lower() in {'self-employed', 'freelance', 'independent', 'none', 'company', 'our'}):
            continue
        return {'company': name, 'quote': match['quote'], 'origin': 'indexed_title_or_snippet', 'verified': False}
    # Some index headlines declare the employer after a role/department/region
    # rather than "at": "Regional Director, Architecture UK&I, AECOM · ...".
    # Only accept a terminal capitalized company segment at a headline boundary;
    # it is still an unverified query hint, never employer evidence.
    terminal = re.compile(r'(?P<quote>'+ROLE+r'\s*,\s*[^|·\n]{2,100},\s*'
        r'(?P<company>'+word+tail+r'))\s*(?=[|·\n]|$)')
    for match in terminal.finditer(row.get('snippet', '')):
        name = match['company'].rstrip('.,').strip()
        if (2 <= len(name) <= 120 and name.lower() not in {
                'uk', 'uk&i', 'us', 'usa', 'united kingdom', 'united states',
                'self-employed', 'freelance', 'independent', 'none', 'company'}):
            return {'company': name, 'quote': match['quote'],
                    'origin': 'indexed_role_department_employer_headline', 'verified': False}
    return {}


async def employer_company_candidate(settings, hint, country):
    """Resolve the business separately without approving the indexed person."""
    from . import providers
    from .discovery import indexed_exclusion, indexed_market_exclusion, name_matches, official_root, public_snapshot
    from .web import domain_of
    report = {'query': f'"{hint["company"]}" official website {country}', 'candidates': [], 'state': 'unconfirmed'}
    try:
        rows = await providers.discover(settings, report['query'], 10, include_platforms=True)
        report.update(engine_issues=getattr(rows, 'engine_issues', []), providers=getattr(rows, 'provider_reports', []))
    except Exception as exc:
        report.update(state='search_unavailable', error_type=type(exc).__name__)
        return report
    seen, matches = set(), []
    for row in rows:
        if indexed_exclusion(row) or indexed_market_exclusion(row, country):
            continue
        try:
            root = official_root(row['url'])
        except ValueError:
            continue
        host = domain_of(root)
        if host in seen or any(host == h or host.endswith('.'+h) for h in INDIRECT_EMPLOYER_ROOTS):
            continue
        if len(seen) >= 3:
            break
        seen.add(host)
        snap = await public_snapshot(settings, root)
        owner = snap.get('state') == 'captured' and domain_of(snap.get('url', '')) == host and (
            name_matches(hint['company'], snap.get('title', '')) or
            any(name_matches(hint['company'], n) for n in snap.get('organization_names', [])))
        report['candidates'].append({'website': root, 'state': snap.get('state'), 'own_company_name_match': owner})
        if owner:
            matches.append({'website': root, 'company': hint['company'], 'official_match_url': snap['url'],
                'official_snapshot_sha256': snap['sha256'], 'observed_at': time.time(),
                'person_identity_verified': False, 'native_profile_publication': False, 'review_required': True})
    if len(matches) == 1:
        report.update(state='company_only_candidate', company_candidate=matches[0])
    elif matches:
        report['state'] = 'ambiguous_company_candidates'
    return report


async def resolve_person_signal(settings, row, country_hint, signal):
    from . import providers
    from .contact_recovery import contact_route
    from .discovery import (company_title, indexed_exclusion, indexed_market_exclusion,
                            official_root, profile_key, public_snapshot)
    from .people import indexed_person_name
    from .professionals import professional_target
    from .profile_resolution import website_hints
    from .web import domain_of

    _, target = professional_target(row['url'])
    name = indexed_person_name(company_title(row.get('title', '')))
    signal.update(company='', person_hint=name, indexed_signal_only=True,
        access_path='independent_public_sources',
        source_failover={'used': True, 'profile_state': signal['public_snapshot'].get('state', 'unavailable'),
                         'transport': 'free_search_and_official_staff_pages', 'platform_access_recovered': False},
        person_recovery={'queries': [], 'pages': [], 'matched_people': [], 'checked_at': time.time(),
                         'leaf_page_budget': 4, 'search_query_page_batch': 2,
                         'note': 'Exact staff-card LinkedIn link required. Published emails come from company pages; buyer, ownership and mailbox verification remain separate.'})
    if not name:
        signal['state'] = 'person_identity_hint_missing'
        return signal
    settings = settings.model_copy(update={'search_provider': 'searxng', 'serpapi_key': ''})
    report = signal['person_recovery']
    hint = indexed_employer_hint(row)
    report['indexed_employer_hint'] = hint
    report['official_person_observations'] = []
    candidates = {u: 'explicit_indexed_website_hint' for u in website_hints(row)}
    for url in signal['public_snapshot'].get('outgoing_websites', [])[:6]:
        try:
            official_root(url)
            candidates.setdefault(url, 'observed_public_profile_website_hint')
        except ValueError:
            pass
    safe = name.replace('"', '')
    # Search engines rarely expose outbound profile URLs in result snippets.
    # Start with a minimal name query; exact profile identity is checked on the
    # current staff page, rather than requiring that link in the search snippet.
    queries = [f'"{safe}"',
               f'"{safe}" (team OR founder OR director OR owner) {country_hint} -site:linkedin.com']
    if hint:
        queries = [f'"{safe}" "{hint["company"]}"', f'"{safe}"']
    # Explicit current team-page hints work even when free engines are down.
    # Keep requests bounded: at most two queries, four leaf pages/four roots.
    matched, roots = {}, {}
    seen, processed = set(), set()

    def rank(url):
        path = unquote(urlsplit(url).path).casefold()
        words = re.findall(r'\w+', path)
        if all(token.casefold() in words for token in name.split()):
            return 0, url
        if re.search(r'(?:^|/)(?:team|people|our-people|our-team|meet-the-team|leadership|founders?)(?:[-_/]|$)', path):
            return 1, url
        return 2, url

    async def inspect(max_new=None):
        started_with = len(seen)
        while len(seen) < 4 and (max_new is None or len(seen)-started_with < max_new):
            pending = sorted(set(candidates)-processed, key=rank)
            if not pending:
                break
            url = pending[0]
            origin = candidates[url]
            processed.add(url)
            if any(domain_of(url) == host or domain_of(url).endswith('.'+host) for host in INDIRECT_EMPLOYER_ROOTS):
                continue
            try:
                root = official_root(url)
                if not contact_route(url, domain_of(root)) and url != root:
                    continue  # Do not match historical article/event mentions.
            except ValueError:
                continue
            if root in matched:
                continue  # No unrelated staff-page fetches after this company's match.
            seen.add(url)
            leaf = await public_snapshot(settings, url)
            report['pages'].append({'url': url, 'state': leaf.get('state'), 'origin': origin,
                'render_attempted': leaf.get('render_attempted', False),
                'rendered': leaf.get('rendered', False), 'render_issues': leaf.get('render_issues', [])})
            if leaf.get('state') != 'captured' or domain_of(leaf.get('url', '')) != domain_of(root):
                continue
            if leaf.get('url') == root:
                roots[root] = leaf
            # Preserve independent HTTP and rendered captures. CSS/hover state
            # can hide published HTML staff cards; never pair one version's
            # name/profile link with the other version's email.
            versions = [leaf]
            raw = leaf.get('http_snapshot')
            if (isinstance(raw, dict) and raw.get('state') == 'captured'
                    and isinstance(raw.get('sha256'), str) and raw['sha256']
                    and raw.get('url') == leaf.get('url') and raw.get('sha256') != leaf['sha256']):
                versions.append(raw)
            # Follow observed current company navigation, never guessed paths.
            routes = set()
            for link in [link for version in versions for link in version.get('public_links', [])[:500]]:
                try:
                    route = contact_route(link, domain_of(root))
                    if route:
                        routes.add(route)
                except ValueError:
                    pass
            for route in sorted(routes, key=rank):
                if len(candidates) >= 40:
                    break
                candidates.setdefault(route, 'observed_official_navigation')
            named = [{**p, 'source_capture_method': version.get('capture_method',
                          'rendered_dom' if leaf.get('rendered') else 'public_html'),
                       'source_sha256': version['sha256']}
                     for version in versions for p in version.get('named_people', [])
                     if p.get('name', '').casefold() == name.casefold() and p.get('role')]
            people = []
            for person in named:
                exact = any(profile_key(link) == profile_key(target) for link in person.get('professional_links', []))
                report['official_person_observations'].append({**person, 'sha256': person['source_sha256'],
                    'observed_at': time.time(), 'matches_requested_profile': exact,
                    'review_required': True, 'reason': 'exact_profile_link_observed' if exact else 'exact_profile_link_missing'})
                if exact:
                    people.append(person)
            if not people:
                continue
            if root not in roots:
                roots[root] = leaf if leaf.get('url') == root else await public_snapshot(settings, root)
            home = roots[root]
            if home.get('state') != 'captured' or domain_of(home.get('url', '')) != domain_of(root):
                continue
            names = home.get('organization_names', [])
            company = names[0] if len(names) == 1 else company_title(home.get('title', ''))
            if not company or company == domain_of(root) or company.lower() in {'home', 'contact us', 'about us', 'welcome'}:
                continue
            for person in people:
                item = {**person, 'profile_url': target, 'official_snapshot_sha256': person['source_sha256'],
                        'observed_at': time.time(), 'website': root,
                        'native_linkedin_capture': False, 'review_required': True}
                if item not in report['matched_people']:
                    report['matched_people'].append(item)
            matched[root] = {'company': company, 'official_match_url': leaf['url'],
                             'official_snapshot_sha256': leaf['sha256']}

    await inspect()
    if not matched:
        for query in queries:
            if len(seen) >= 4:
                break
            try:
                rows = await providers.discover(settings, query, 10, include_platforms=True)
                report['queries'].append({'query': query, 'result_count': len(rows),
                    'engine_issues': getattr(rows, 'engine_issues', []), 'providers': getattr(rows, 'provider_reports', [])})
                for candidate in rows:
                    if indexed_exclusion(candidate) or indexed_market_exclusion(candidate, country_hint):
                        continue
                    try:
                        official_root(candidate['url'])
                        candidates.setdefault(candidate['url'], 'search_index_hint')
                    except ValueError:
                        pass
                # Preserve budget for the next identity query before a same-name
                # person's unrelated team frontier consumes every leaf request.
                await inspect(max_new=2)
            except Exception as exc:
                report['queries'].append({'query': query, 'error_type': type(exc).__name__})
            if matched:
                break
            await asyncio.sleep(settings.discovery_query_delay_seconds)
        # Still process observed pending routes if the second query failed or
        # supplied no alternatives; the original four-page ceiling is unchanged.
        if not matched:
            await inspect()
    if len(matched) == 1:
        root, value = next(iter(matched.items()))
        signal.update(website=root, state='official_staff_profile_candidate', **value)
    else:
        signal['state'] = 'ambiguous_person_company_matches' if matched else 'person_company_unconfirmed'
    report['person_identity_state'] = 'exact_official_link_observed' if len(matched) == 1 else 'held'
    if not matched and hint:
        report['company_search'] = await employer_company_candidate(settings, hint, country_hint)
        candidate = report['company_search'].get('company_candidate')
        if candidate:
            signal.update(**candidate, state='indexed_employer_company_candidate', resolved_company_only=True)
    report['finished_at'] = time.time()
    return signal
