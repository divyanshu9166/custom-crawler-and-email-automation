"""Published professional contacts, bound to an existing company and reviewed employer proof."""

import asyncio
import hashlib
import json
import re
import time
from urllib.parse import urlsplit

from bs4 import BeautifulSoup

from .web import PublicWeb, crawl_url, domain_of, normalize_email, EMAIL_RE, outreach_email_allowed


def professional_target(url):
    value = crawl_url(url)
    parts = urlsplit(value)
    host = domain_of(value)
    if parts.query:
        raise ValueError("Use the public professional profile URL without query parameters")
    if host == "linkedin.com" or host.endswith(".linkedin.com"):
        if re.fullmatch(r"/in/[A-Za-z0-9_-]{2,100}/?", parts.path):
            return "linkedin.com", "https://www.linkedin.com" + parts.path.rstrip("/")
    elif host in {"x.com", "twitter.com"}:
        from .platform_browser import profile_target

        platform, target = profile_target(value)
        if urlsplit(target).path.strip("/").lower() not in {"intent", "tos", "privacy", "explore"}:
            return platform, target
    raise ValueError("Use a LinkedIn /in/ professional profile or an X public profile root")


def public_addresses(text):
    result = set()
    for address in re.findall(EMAIL_RE, text):
        try:
            email = normalize_email(address)
            if outreach_email_allowed(email):
                result.add(email)
        except ValueError:
            pass
    return sorted(result)


def sourced_profile_links(page):
    result = []
    for link in page.get("links", [])[:500]:
        try:
            _, url = professional_target(link)
            if url not in result:
                result.append(url)
        except ValueError:
            pass
        if len(result) == 20:
            break
    return result


def parse_public_html(url, html):
    """Scoped HTTP guest fields only. Hidden elements/account shells are excluded."""
    platform, target = professional_target(url)
    soup = BeautifulSoup(html, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    if re.search(
        r"captcha|sign in|authwall|security check|just a moment", title, re.I
    ):
        return {"state": "login_or_challenge"}
    for node in list(soup.select('script,style,nav,aside,button,dialog,[role="dialog"],[hidden],[aria-hidden="true"]')):
        node.decompose()
    for node in list(soup.select("[style]")):
        if node.attrs is not None and re.search(r"display\s*:\s*none|visibility\s*:\s*hidden", node.get("style", ""), re.I):
            node.decompose()
    h = soup.select_one('main [data-testid="UserName"]') if platform == 'x.com' else None
    h = h or soup.select_one("main h1")
    if not h:
        return {"state": "fields_not_ready"}
    scopes = []
    if platform == "linkedin.com":
        card = h.find_parent("section") or h.find_parent(class_="top-card-layout")
        if not card:
            return {"state": "fields_not_ready"}
        headline = card.select_one(
            '[data-testid="profile-headline"],.text-body-medium,.top-card-layout__headline'
        )
        scopes = [headline] if headline else []
        for section in soup.select("main section"):
            header = section.find("h2")
            if header and header.get_text(" ", strip=True).lower() == "about":
                content = section.select_one(
                    '[data-testid="profile-about"],.inline-show-more-text,.pv-shared-text-with-see-more'
                )
                if content:
                    scopes.append(content)
        # Public mailto links in the top card are also valid visible candidates.
        scopes.extend(card.select('a[href^="mailto:"]'))
    else:
        scopes = list(
            soup.select('main [data-testid="UserDescription"],main [data-testid="UserProfileHeader_Items"]')
        )
    if not scopes:
        return {"state": "fields_not_ready"}
    name = h.get_text(' ', strip=True)
    if platform == 'x.com' and h.get('data-testid') == 'UserName':
        handle = urlsplit(target).path.strip('/')
        if not re.search(r'@' + re.escape(handle) + r'\b', name, re.I):
            return {'state': 'profile_handle_mismatch'}
        name = re.split(r'\s*@' + re.escape(handle) + r'\b', name, maxsplit=1, flags=re.I)[0].strip()
    pieces = [name] + [s.get_text(" ", strip=True) for s in scopes]
    mailto = []
    from urllib.parse import unquote

    for scope in scopes:
        for a in [scope] if scope.name == "a" else scope.select('a[href^="mailto:"]'):
            try:
                mailto.append(unquote(a["href"][7:].split("?")[0]))
            except (KeyError, ValueError):
                pass
    if mailto:
        pieces.append("Published mailto links: " + ", ".join(mailto))
    return {
        "state": "captured",
        "url": target,
        "title": pieces[0][:150],
        "text": "\n".join(pieces)[:12000],
        "headline": pieces[1][:300] if len(pieces) > 1 else "",
    }


async def profile_snapshot(settings, url):
    _, target = professional_target(url)
    if settings.platform_browser_enabled:
        from .platform_browser import browser_professional_snapshot

        return await browser_professional_snapshot(settings, target)
    web = PublicWeb(settings, signal_only=True)
    base = {
        "url": target,
        "capture_method": "public_professional_http",
        "scope": "public_professional_fields",
        "observed_at": time.time(),
    }
    try:
        robots, delay, _ = await web.robots(target)
        if not robots.can_fetch(settings.crawler_user_agent, target):
            return {**base, "state": "robots_denied"}
        await asyncio.sleep(delay)
        final, html, code = await web.get(target, domain_of(target))
        if code == 404:
            return {**base, "state": "not_found"}
        if professional_target(final)[1] != target:
            return {**base, "state": "redirect_identity_mismatch"}
        return {**base, **parse_public_html(final, html)}
    except Exception as exc:
        return {**base, "state": "unavailable", "error_type": type(exc).__name__}


def captures(db, lead_id):
    seen, result = set(), []
    for row in db.all(
        "SELECT id,detail,created_at FROM events WHERE kind='professional_capture' AND json_extract(detail,'$.lead_id')=? ORDER BY id DESC LIMIT 200",
        (lead_id,),
    ):
        value = json.loads(row["detail"])
        if value["url"] in seen:
            continue
        seen.add(value["url"])
        fresh = time.time() - 30 * 86400 <= value["observed_at"] <= time.time() + 60
        result.append({**value, "capture_id": row["id"], "fresh": fresh, "review_required": True})
    return result


async def research_professionals(db, settings, lead_id, profile_url=""):
    from .contact_recovery import eligible_lead
    from .providers import discover

    lead = eligible_lead(db, lead_id)
    settings = settings.model_copy(
        update={
            "search_provider": "searxng",
            "serpapi_key": "",
            "search_language": "en-US"
            if (lead["country"] == "US" or "hint: US" in lead["research_notes"])
            else "en-GB",
        }
    )
    report = {
        "lead_id": lead_id,
        "queries": [],
        "captures": [],
        "other_public_profile_hints": [],
        "named_people": [],
        "community_profile_hints": [],
        "state": "researching",
        "note": "Public profile email candidates only; current employer, role, ownership and mailbox existence require review. No guessed addresses or SMTP probes.",
    }
    targets = {}
    people = {}
    if profile_url:
        _, target = professional_target(profile_url)
        targets[target] = {"origin": "operator_profile_hint"}
    else:
        from .research import fresh_evidence

        pages = {p["url"]: p for p in fresh_evidence(db, lead_id) if domain_of(p["url"]) == lead["domain"]}
        crawl = db.one("SELECT report FROM crawls WHERE lead_id=? ORDER BY id DESC LIMIT 1", (lead_id,))
        for page in json.loads(crawl["report"]).get("pages", []) if crawl else []:
            saved = pages.get(page["url"])
            if not saved or saved["sha256"] != page.get("sha256"):
                continue
            for person in page.get('named_people', [])[:20]:
                from .people import person_name
                if person_name(person.get('name', '')):
                    people.setdefault(person['name'], {**person, 'company_evidence_id': saved['id'],
                        'company_sha256': saved['sha256'], 'observed_at': saved['fetched_at']})
                    for link in person.get('professional_links', [])[:10]:
                        try:
                            target = professional_target(link)[1]
                            targets.setdefault(target, {'origin': 'captured_official_named_person',
                                'person': person['name'], 'company_evidence_id': saved['id'],
                                'company_sha256': saved['sha256'], 'source_url': saved['url']})
                        except ValueError:
                            pass
            for link in page.get("professional_links", [])[:20]:
                try:
                    _, target = professional_target(link)
                    targets.setdefault(
                        target,
                        {
                            "origin": "captured_official_link",
                            "company_evidence_id": saved["id"],
                            "company_sha256": saved["sha256"],
                            "source_url": saved["url"],
                        },
                    )
                except ValueError:
                    pass
            from .profiles import canonical_profile
            for link in page.get('business_profile_links', page.get('links', []))[:500]:
                try:
                    business = canonical_profile(link)
                    if business not in {h['url'] for h in report['other_public_profile_hints']}:
                        report['other_public_profile_hints'].append({'url': business, 'origin': 'captured_official_navigation',
                            'source_url': saved['url'], 'company_sha256': saved['sha256'], 'company_evidence_id': saved['id']})
                except ValueError:
                    pass
                if len(report['other_public_profile_hints']) >= 20:
                    break
        # Refresh a bounded set of observed official routes when older reports
        # lack outgoing profile links. No guessed profile handles or paths.
        if settings.professional_refresh_official_links and len(targets) < settings.professional_max_profiles:
            from .contact_recovery import official_contact_seeds
            from .public_index import commoncrawl_routes
            from .discovery import public_snapshot
            from .web import priority

            archive = await commoncrawl_routes(settings, lead['website'])
            report['url_index'] = archive
            routes = set(official_contact_seeds(db, lead)) | {r['url'] for r in archive['rows']}
            routes.add(crawl_url(lead['website']))
            report['official_link_refresh'] = []
            for route in sorted(routes, key=lambda u: (priority(u), u))[:3]:
                eligible_lead(db, lead_id)
                snap = await public_snapshot(settings, route)
                item = {'url': route, 'state': snap.get('state', 'unavailable'), 'observed_at': time.time()}
                report['official_link_refresh'].append(item)
                if snap.get('state') != 'captured' or domain_of(snap.get('url', '')) != lead['domain']:
                    continue
                links = sourced_profile_links({'links': snap.get('public_links', [])})
                from .profiles import canonical_profile
                for link in snap.get('public_links', [])[:500]:
                    try:
                        business = canonical_profile(link)
                        hint = {'url': business, 'origin': 'current_official_navigation',
                                'source_url': snap['url'], 'observed_at': item['observed_at'],
                                'email_publication_verified': False}
                        if not any(h['url'] == business for h in report['other_public_profile_hints']):
                            report['other_public_profile_hints'].append(hint)
                    except ValueError:
                        pass
                    if len(report['other_public_profile_hints']) >= 20:
                        break
                item.update(sha256=snap['sha256'], professional_links=links,
                            published_company_email_candidates=len(snap.get('published_emails', [])))
                for person in snap.get('named_people', [])[:20]:
                    from .people import person_name
                    if person_name(person.get('name', '')):
                        people[person['name']] = {**person, 'company_sha256': snap['sha256'],
                            'source_url': snap['url'], 'observed_at': item['observed_at']}
                        for target in person.get('professional_links', [])[:10]:
                            try:
                                target = professional_target(target)[1]
                                targets.setdefault(target, {'origin': 'current_official_named_person',
                                    'person': person['name'], 'source_url': snap['url'], 'company_sha256': snap['sha256']})
                            except ValueError:
                                pass
                for target in links:
                    targets.setdefault(target, {'origin': 'current_official_navigation', 'source_url': snap['url'],
                        'company_sha256': snap['sha256'], 'observed_at': item['observed_at']})
                if len(targets) >= settings.professional_max_profiles:
                    break
                await asyncio.sleep(settings.discovery_query_delay_seconds)
        from .discovery import name_matches, company_title
        name = company_title(lead["company"]).replace('"', " ").strip()
        report['query_company_name'] = name
        report['named_people'] = list(people.values())[:20]
        if settings.platform_browser_enabled and settings.linkedin_people_search_enabled and len(targets) < settings.professional_max_profiles:
            from .social_browser import browser_people_discover
            from .source_status import record
            query = f'"{name}" (founder OR owner OR director OR marketing OR ecommerce)'
            started = time.monotonic()
            rows = await browser_people_discover(settings, query, settings.professional_max_profiles)
            report['queries'].append({'query': query, 'source': 'managed_browser:linkedin.com', 'results': len(rows),
                'engine_issues': getattr(rows, 'engine_issues', []), 'providers': getattr(rows, 'provider_reports', [])})
            record(db, 'managed_browser:linkedin.com', 'people_search', query,
                   {'state': 'captured' if rows else 'unavailable', 'reason': 'Search cards are unverified buyer hints'},
                   lead_id=lead_id, elapsed=time.monotonic()-started)
            for row in rows:
                try:
                    _, target = professional_target(row['url'])
                    targets.setdefault(target, {'origin': 'managed_people_search', 'query': query,
                        'snippet': row.get('snippet', '')[:1200], 'identity_verified': False, 'buyer_verified': False})
                except (ValueError, KeyError):
                    pass
        person_queries = []
        for person in list(people)[:3]:
            person_queries.extend([f'site:linkedin.com/in/ "{person}" "{name}"',
                                   f'site:x.com "{person}" "{name}"'])
        queries = person_queries + [
            f'site:linkedin.com/in/ "{name}" (founder OR owner OR marketing OR ecommerce OR director)',
            f'site:x.com "{name}" (founder OR owner OR marketing OR ecommerce)',
            f'site:linkedin.com/in/ "{name}"',
            f'site:x.com "{name}"',
            f'"{lead["domain"]}" LinkedIn founder',
            f'"{name}"',
        ]
        if settings.platform_browser_enabled and not settings.platform_browser_public_fallback:
            queries = []
        for query in list(dict.fromkeys(queries))[:settings.professional_max_queries]:
            if len(targets) >= settings.professional_max_profiles:
                break
            try:
                rows = await discover(settings, query, 10, include_platforms=True)
                report["queries"].append(
                    {
                        "query": query,
                        "results": len(rows),
                        "engine_issues": getattr(rows, "engine_issues", []),
                        "providers": getattr(rows, "provider_reports", []),
                        "rejected_company_mismatch": 0,
                    }
                )
                for row in rows:
                    text = row.get('title', '') + ' ' + row.get('snippet', '')
                    if name_matches(name, text):
                        from .profiles import canonical_profile
                        from .discovery import indexed_market_exclusion
                        try:
                            business = canonical_profile(row['url'])
                            if not indexed_market_exclusion(row, lead['country']) and not any(
                                h['url'] == business for h in report['other_public_profile_hints']
                            ) and len(report['other_public_profile_hints']) < 20:
                                report['other_public_profile_hints'].append({'url': business, 'origin': 'search_index',
                                    'query': query, 'company_identity_verified': False, 'email_publication_verified': False})
                        except ValueError:
                            pass
                    try:
                        _, target = professional_target(row["url"])
                        if not name_matches(name, text) and lead['domain'] not in text.lower():
                            report['queries'][-1]['rejected_company_mismatch'] += 1
                            continue
                        targets.setdefault(target, {"origin": "search_index", "query": query,
                                                    "engines": row.get('engines', [])})
                    except ValueError:
                        pass
            except Exception as exc:
                report["queries"].append({"query": query, "error_type": type(exc).__name__})
            await asyncio.sleep(settings.discovery_query_delay_seconds)
    for target in list(targets)[: settings.professional_max_profiles]:
        eligible_lead(db, lead_id)
        started = time.monotonic()
        snap = await profile_snapshot(settings, target)
        eligible_lead(db, lead_id)
        state = snap.get("state", "unavailable")
        text = snap.get("text", "")[:40000] if state == "captured" else ""
        # Exact capture identity is mandatory even for adapter replacements.
        if state == "captured":
            try:
                matched = professional_target(snap.get("url", ""))[1] == target
            except ValueError:
                matched = False
            if not matched:
                state, text = "redirect_identity_mismatch", ""
        value = {
            "lead_id": lead_id,
            "url": target,
            "state": state,
            "text": text,
            "name": snap.get("title", "")[:150] if text else "",
            "headline": snap.get("headline", "")[:300] if text else "",
            "observed_at": snap.get("observed_at", time.time()),
            "sha256": hashlib.sha256(text.encode()).hexdigest(),
            "published_emails": public_addresses(text),
            "capture_method": snap.get("capture_method", "public_professional_http"),
            "scope": snap.get('scope', 'public_professional_fields'),
            "sections": snap.get('sections', {}),
            "section_errors": snap.get('section_errors', []),
            "identity_verified": False,
            "employer_verified": False,
            "source_hint": targets[target],
            "access_issue": {k: snap[k] for k in ('http_status', 'error_type', 'reason',
                'response_host', 'server', 'denial_kind', 'retry_at', 'operator_action_required') if k in snap},
        }
        from .sequence import Reader

        with db.connect() as con:
            con.execute("BEGIN IMMEDIATE")
            eligible_lead(Reader(con), lead_id)
            con.execute(
                "INSERT INTO events(kind,detail,created_at) VALUES(?,?,?)",
                ("professional_capture", json.dumps(value), time.time()),
            )
        report["captures"].append(
            {"url": target, "state": state, "published_email_candidates": len(value["published_emails"]),
             "access_issue": value['access_issue']}
        )
        from .source_status import record
        record(db, 'managed_browser:' + professional_target(target)[0] if settings.platform_browser_enabled else 'website',
               'professional_profile', target, {**snap, 'state': state}, lead_id=lead_id,
               elapsed=time.monotonic()-started, contacts=len(value['published_emails']))
        if settings.fxembed_profiles_enabled and professional_target(target)[0] == 'x.com' and state != 'captured':
            from .fxembed import profile_hint
            try:
                hint = await profile_hint(settings, target)
            except Exception as exc:
                # Optional community hints must not discard native captures or
                # prevent subsequent profiles from being researched. Keep only
                # the exception type: provider errors can contain private data.
                hint = {'state': 'unavailable', 'profile_url': target, 'error_type': type(exc).__name__}
            eligible_lead(db, lead_id)
            # Keep the original denial and the community response separately.
            # These hints cannot enter first-party source review or verify/send.
            report['community_profile_hints'].append(hint)
            record(db, 'fxembed_profiles', 'profile_hint', target, hint, lead_id=lead_id,
                   contacts=len(hint.get('published_email_candidates', [])))
    if settings.social_posts_enabled and settings.platform_browser_enabled:
        from .social_research import research_posts
        report['social_research'] = await research_posts(db, settings, lead_id,
            report['other_public_profile_hints'] + [{'url': u, **h} for u, h in targets.items() if '/company/' in u or professional_target(u)[0] == 'x.com'])
    report.update(
        state="captured" if any(c["state"] == "captured" for c in report["captures"]) else "held",
        official_person_email_candidates=[{**publication, 'name': person['name'], 'role': person.get('role', ''),
            'source_url': person.get('source_url', ''), 'company_sha256': person.get('company_sha256', ''),
            'professional_links': person.get('professional_links', []), 'review_required': True,
            'inbox_ownership_verified': False, 'native_profile_publication': False}
            for person in report['named_people'] for publication in person.get('email_publications', [])],
        finished_at=time.time(),
    )
    db.event("professional_research", report)
    return report


def reviewed_publication(db, lead, url, email=None):
    """Recheck the latest profile and its independent current employer evidence."""
    try:
        _, target = professional_target(url)
    except ValueError:
        return None
    source = next((c for c in captures(db, lead["id"]) if c["url"] == target), None)
    if not source or source["state"] != "captured" or not source["fresh"]:
        return None
    from .research import fresh_evidence

    pages = {p["id"]: p for p in fresh_evidence(db, lead["id"])}
    recipient = next(
        (p for p in pages.values() if p["url"] == target and p["sha256"] == source["sha256"]), None
    )
    if not recipient:
        return None
    for event in db.all(
        "SELECT detail FROM events WHERE kind='professional_source_reviewed' AND json_extract(detail,'$.lead_id')=? AND json_extract(detail,'$.url')=? ORDER BY id DESC LIMIT 50",
        (lead["id"], target),
    ):
        review = json.loads(event["detail"])
        employer = pages.get(review["company_evidence_id"])
        from .discovery import name_matches

        if (
            review["capture_id"] == source["capture_id"]
            and review["sha256"] == source["sha256"]
            and (email is None or email == review["email"])
            and review["email"] in source["published_emails"]
            and employer
            and domain_of(employer["url"]) == lead["domain"]
            and employer["sha256"] == review["company_sha256"]
            and review["company_quote"] in employer["text"]
            and review["employer_quote"] in source["text"]
            and name_matches(lead["company"], review["employer_quote"])
        ):
            return recipient
    return None


def review_contact(db, lead_id, value):
    if value.get("reviewed_current_employer_and_publication") is not True:
        raise ValueError("Confirm current employer and public inbox ownership review")
    from .contact_recovery import eligible_lead
    from .discovery import name_matches
    from .research import fresh_evidence
    from .sequence import Reader

    with db.connect() as con:
        con.execute("BEGIN IMMEDIATE")
        reader = Reader(con)
        lead = eligible_lead(reader, lead_id)
        source = next((s for s in captures(reader, lead_id) if s["capture_id"] == value["capture_id"]), None)
        if not source or source["state"] != "captured" or not source["fresh"]:
            raise ValueError("Review the latest fresh public professional capture")
        email = normalize_email(value["email"])
        if email not in source["published_emails"]:
            raise ValueError("Select an email actually published in this capture")
        employer_quote, role_quote = value["employer_quote"].strip(), value["role_quote"].strip()
        if (
            len(employer_quote) < 8
            or employer_quote not in source["text"]
            or not name_matches(lead["company"], employer_quote)
            or len(role_quote) < 3
            or role_quote not in source["text"]
            or not re.search(
                r"\b(founder|owner|CEO|president|marketing|ecommerce|e-commerce|CX|director|manager|head)\b",
                role_quote,
                re.I,
            )
        ):
            raise ValueError(
                "Use exact public employer and relevant buyer-role quotes; prior employment alone is insufficient"
            )
        if re.search(r"\b(former|previous|past|ex[- ]|used to)\b", employer_quote + " " + role_quote, re.I):
            raise ValueError("Former employment is not current employer evidence")
        employer = next(
            (
                p
                for p in fresh_evidence(reader, lead_id)
                if p["id"] == value["company_evidence_id"] and domain_of(p["url"]) == lead["domain"]
            ),
            None,
        )
        company_quote = value["company_quote"].strip()
        if (
            not employer
            or len(company_quote) < 8
            or company_quote not in employer["text"]
            or not name_matches(source["name"], company_quote)
        ):
            raise ValueError(
                "Corroborate this named person using an exact quote from a current official company page"
            )
        note = value["ownership_notes"].strip()
        if len(note) < 30:
            raise ValueError("Review the published inbox ownership and current employer context")
        existing = con.execute("SELECT * FROM contacts WHERE email=?", (email,)).fetchone()
        if existing and (
            existing["lead_id"] != lead_id
            or existing["status"] != "new"
            or existing["name"]
            and existing["name"] != source["name"]
        ):
            raise ValueError("Existing inbox/person or outreach history requires separate review")
        con.execute(
            "INSERT INTO evidence(lead_id,url,title,text,sha256,fetched_at) VALUES(?,?,?,?,?,?) ON CONFLICT(lead_id,url) DO UPDATE SET title=excluded.title,text=excluded.text,sha256=excluded.sha256,fetched_at=excluded.fetched_at",
            (lead_id, source["url"], source["name"], source["text"], source["sha256"], source["observed_at"]),
        )
        detail = {
            **value,
            "lead_id": lead_id,
            "url": source["url"],
            "sha256": source["sha256"],
            "company_sha256": employer["sha256"],
            "email": email,
            "company_quote": company_quote,
        }
        con.execute(
            "INSERT INTO events(kind,detail,created_at) VALUES(?,?,?)",
            ("professional_source_reviewed", json.dumps(detail), time.time()),
        )
        con.execute(
            "INSERT INTO events(kind,detail,created_at) VALUES(?,?,?)",
            (
                "contact_candidate_found",
                json.dumps(
                    {
                        "lead_id": lead_id,
                        "source_url": source["url"],
                        "email": email,
                        "evidence_sha256": source["sha256"],
                        "reason": "Published professional email; current employer and source reviewed",
                        "method": "reviewed_professional",
                    }
                ),
                time.time(),
            ),
        )
        # Use the same transaction to bind import to this exact source review.
        cid = _import_contact(con, reader, lead, email, source, role_quote, note)
    if not db.one("SELECT 1 FROM contacts WHERE id=? AND status='suppressed'", (cid,)):
        db.enqueue("verify", {"contact_id": cid})
    return cid


def _import_contact(con, reader, lead, email, source, role, note):
    # add_contact owns a DB transaction; its public safeguards are reproduced
    # here under the already-held review transaction, without nested writers.
    import secrets

    if not reviewed_publication(reader, lead, source["url"], email):
        raise ValueError("Professional review changed before import")
    suppressed = con.execute("SELECT 1 FROM suppression WHERE email=?", (email,)).fetchone()
    con.execute(
        "INSERT OR IGNORE INTO contacts(lead_id,email,name,role,source_url,unsubscribe_token,created_at,status) VALUES(?,?,?,?,?,?,?,?)",
        (
            lead["id"],
            email,
            source["name"],
            role[:150],
            source["url"],
            secrets.token_urlsafe(32),
            time.time(),
            "suppressed" if suppressed else "new",
        ),
    )
    cid = con.execute("SELECT id FROM contacts WHERE email=?", (email,)).fetchone()[0]
    con.execute(
        "UPDATE contacts SET source_url=?,name=?,role=? WHERE id=? AND status='new'",
        (source["url"], source["name"], role[:150], cid),
    )
    con.execute(
        "INSERT INTO events(kind,contact_id,detail,created_at) VALUES(?,?,?,?)",
        (
            "contact_source_reviewed",
            cid,
            json.dumps(
                {
                    "lead_id": lead["id"],
                    "source_url": source["url"],
                    "evidence_sha256": source["sha256"],
                    "ownership_notes": note,
                }
            ),
            time.time(),
        ),
    )
    return cid
