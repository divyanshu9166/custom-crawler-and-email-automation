"""Profile-first prospects: absence of a search result is not absence of a site."""
import hashlib
import json
import re
import time
from urllib.parse import urlsplit, urlunsplit

from .discovery import platform_of, profile_key, resolve_signal
from .web import crawl_url, normalize_email


PROFILE_PLATFORMS = {"linkedin.com", "x.com", "twitter.com", "facebook.com", "instagram.com",
                     "peopleperhour.com", "clutch.co", "crunchbase.com", "yelp.com", "bbb.org",
                     "trustpilot.com", "google.com"}


def canonical_profile(url):
    url = crawl_url(url)
    parts = urlsplit(url)
    platform = platform_of(url)
    if platform == 'google.com':
        from .google_business import listing_url
        return listing_url(url)
    segments = parts.path.strip("/").split("/")
    if platform == 'linkedin.com' and len(segments) == 3 and segments[0] == 'company' and segments[2] == 'about':
        parts = parts._replace(path='/'+ '/'.join(segments[:2]))
        segments = segments[:2]
    specific_routes = {
        'clutch.co': 'profile', 'crunchbase.com': 'organization',
        'trustpilot.com': 'review', 'yelp.com': 'biz', 'peopleperhour.com': 'freelancer',
    }
    if (platform not in PROFILE_PLATFORMS or not parts.path.strip("/")
            or (platform == "linkedin.com" and (segments[0] not in {'company', 'in'} or len(segments) != 2))
            or (platform == "google.com" and not parts.path.startswith("/maps/place/"))
            or (platform in {"x.com", "twitter.com", "instagram.com"} and (len(segments) != 1 or segments[0].lower() in {"search", "explore", "home", "i", "p", "reel", "messages", "notifications", "settings", "compose", "login", "logout"}))
            or (platform == "facebook.com" and any(p in segments for p in {"posts", "search", "login", "watch", "groups", "reel"}))
            or (platform in specific_routes and (segments[0] != specific_routes[platform] or len(segments) < 2))
            or (platform == 'bbb.org' and ('profile' not in segments or segments.index('profile') >= len(segments)-2))):
        raise ValueError("Use a specific public business profile or listing, not a platform home/search or post URL")
    # Google listing IDs can live in the query. Preserve them to avoid merging listings.
    query = parts.query if platform == "google.com" else ""
    return urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), query, ""))


def business_profile_links(links):
    """Retain observed profile routes for later research, without claiming ownership."""
    found = []
    for link in links[:1000]:
        try:
            value = canonical_profile(link)
            # Employee links on a company page are professional-research hints,
            # not additional owned business presences. Self-selling individuals
            # enter through explicit profile discovery and its identity checks.
            if platform_of(value) == 'linkedin.com' and '/in/' in urlsplit(value).path:
                continue
            if value not in found:
                found.append(value)
        except ValueError:
            pass
        if len(found) >= 20:
            break
    return found


def source_allowed(lead, url, db=None, email=None):
    from .web import domain_of
    if lead.get("lead_kind") == "profile":
        try:
            if platform_of(lead['profile_url']) == 'google.com':
                from .google_business import listing_key
                return listing_key(url) == listing_key(lead['profile_url'])
            return canonical_profile(url) == canonical_profile(lead["profile_url"]) or (
                platform_of(url) != "google.com" and profile_key(canonical_profile(url)) == profile_key(lead["profile_url"]))
        except ValueError:
            return False
    if domain_of(url)==lead['domain']:
        return True
    if db:
        from .professionals import reviewed_publication
        return bool(reviewed_publication(db,lead,url,email))
    return False


def add_profile_lead(db, company, profile_url, campaign, country_hint="", campaign_id=None):
    from .campaign_manager import assert_target
    assert_target(db, campaign_id, campaign)
    profile_url = canonical_profile(profile_url)
    if campaign not in {"A", "B"} or len(company.strip()) < 2 or country_hint not in {"US", "UK"}:
        raise ValueError("Provide a business name and Campaign A or B")
    # Internal identity key only; website stays empty and no pretend domain is created.
    from .google_business import listing_key
    identity = (listing_key(profile_url) if platform_of(profile_url) == "google.com"
                else repr(profile_key(profile_url)))
    key = "profile:" + hashlib.sha256(identity.encode()).hexdigest()
    now = time.time()
    with db.connect() as con:
        con.execute("""INSERT OR IGNORE INTO leads(domain,website,company,campaign,source_url,research_notes,
            created_at,updated_at,lead_kind,profile_url,website_status,discovery_country,campaign_id) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (key, "", company.strip()[:200], campaign, profile_url,
                     f"Profile discovery country hint: {country_hint or 'unknown'}; identity, activity and website status need research/review.",
                     now, now, "profile", profile_url, "not_checked", country_hint, campaign_id))
        row = con.execute('SELECT id,campaign_id,deleted_at FROM leads WHERE domain=?', (key,)).fetchone()
        if row['deleted_at'] or (campaign_id and row['campaign_id'] != campaign_id):
            raise ValueError('Existing prospect is deleted or belongs to another campaign; review it explicitly')
        return row['id']


def assert_profile_review(db, lead):
    review = json.loads(lead.get("profile_review", "{}"))
    page = db.one("SELECT * FROM evidence WHERE id=? AND lead_id=?", (review.get("evidence_id"), lead["id"]))
    latest = db.one("SELECT created_at FROM crawls WHERE lead_id=? ORDER BY id DESC LIMIT 1", (lead["id"],))
    if (lead["website_status"] != "website_not_found" or not page or not latest
            or page["sha256"] != review.get("evidence_sha256") or page["fetched_at"] < latest["created_at"]
            or not time.time()-30*86400 <= page['fetched_at'] <= time.time()+60
            or len(review.get("ownership_notes", "")) < 30
            or len(review.get("activity_quote", "")) < 8 or review["activity_quote"] not in page["text"]):
        raise ValueError("Review current business profile identity/activity and website-search limitations before contact verification or outreach")
    if review.get('method') == 'research_ai_profile':
        from .profile_preparation import evidence_context
        if evidence_context(db, lead)['crawl_id'] != review.get('research_crawl_id'):
            raise ValueError('Automatic profile review no longer matches current research')


def personal_business_snapshot(snapshot):
    """An employee/founder keyword alone does not turn a person into a business."""
    if snapshot.get('state') != 'captured':
        return False
    text = snapshot.get('headline', '')+' '+snapshot.get('text', '')[:1000]
    if re.search(r'\b(?:formerly|previously|retired|used to)\b', text, re.I):
        return False
    return bool(re.search(r'\b(?:self[- ]employed|independent consultant|freelance\s+(?:designer|developer|consultant|photographer|writer)|I\s+(?:offer|provide|sell)|my\s+(?:business|shop))\b', text, re.I))


async def research_profile(db, settings, lead):
    from .research import add_lead
    lid = lead["id"]
    settings = settings.model_copy(update={"search_language": "en-US" if _country_hint(lead) == "US" else "en-GB"})
    with db.connect() as con:
        con.execute("BEGIN IMMEDIATE")
        if con.execute("SELECT id FROM contacts WHERE lead_id=? AND status IN ('active','replied','hold','closed')", (lid,)).fetchone():
            raise ValueError("Existing outreach history: preserve profile evidence")
        started = time.time()
        crawl_id = con.execute("INSERT INTO crawls(lead_id,report,created_at) VALUES(?,?,?)",
                               (lid, '{"kind":"profile","status":"researching"}', started)).lastrowid
        con.execute("UPDATE leads SET status='researching',website_status='checking',profile_review='{}',updated_at=? WHERE id=?", (started, lid))
    report = {"kind": "profile", "status": "partial", "profile_url": lead["profile_url"], "errors": []}
    try:
        signal = await resolve_signal(settings, {"url": lead["profile_url"], "title": lead["company"], "snippet": ""},
                                      lead["country"] or _country_hint(lead), PROFILE_PLATFORMS)
        report["signal"] = signal
        snapshot = signal.get("public_snapshot", {})
        captured = snapshot.get("state") == "captured" and source_allowed(lead, snapshot.get("url", "")) and bool(snapshot.get("text", "").strip())
        website_status = ("website_found" if signal.get("website") else
                          "website_not_found" if signal["state"] == "no_company_match" and signal.get("website_search", {}).get("completed") else
                          "ambiguous" if signal["state"].startswith("ambiguous") else "search_unavailable")
        if captured:
            url, text = snapshot["url"], snapshot["text"]
            if snapshot.get("published_email_links"):
                text += "\nPublished mailto links: " + ", ".join(snapshot["published_email_links"])
            digest = hashlib.sha256(text.encode()).hexdigest()
            db.execute("INSERT INTO evidence(lead_id,url,title,text,sha256,fetched_at) VALUES(?,?,?,?,?,?) ON CONFLICT(lead_id,url) DO UPDATE SET title=excluded.title,text=excluded.text,sha256=excluded.sha256,fetched_at=excluded.fetched_at",
                       (lid, url, snapshot.get("title", lead["company"]), text, digest, time.time()))
            from .web import EMAIL_RE
            for email in dict.fromkeys([*snapshot.get("published_emails", []), *re.findall(EMAIL_RE, text)]):
                try:
                    email = normalize_email(email)
                except ValueError:
                    continue
                # Only an address actually present in the saved text is reviewable.
                if email not in text.lower():
                    continue
                db.event("contact_candidate_found", {"lead_id": lid, "email": email, "source_url": url,
                         "evidence_sha256": digest, "reason": "Published profile email; business/profile/inbox ownership must be reviewed. No contact or probe created."},
                         external_id="profile-candidate:" + hashlib.sha256(f"{lid}:{url}:{email}:{digest}".encode()).hexdigest())
            eid = db.one("SELECT id FROM evidence WHERE lead_id=? AND url=?", (lid, url))["id"]
            from .opportunities import proposals
            proposed = proposals({**lead, 'website_status': website_status}, [{'id': eid, 'url': url, 'text': text}])
            finding = {"evidence_id": eid, "quote": text[:240], "observation": "Review the published inquiry/order process on this business profile.",
                       "suggestion": "", "service": "website_build" if lead["campaign"] == "A" else "store_launch", "review_required": True, "kind": "needs_review"}
            if proposed:
                finding = proposed[0]
        else:
            finding = None
            report["errors"].append({"stage": "profile", "reason": snapshot.get("state", "unavailable")})
        if signal.get("website"):
            from .google_business import is_campaign
            if is_campaign(db, lead):
                report['campaign_exclusion'] = 'Official website found; excluded from Campaign 3 website-launch preparation'
            else:
                target = add_lead(db, lead["company"], signal["website"], lead["campaign"], lead["profile_url"], _country_hint(lead), campaign_id=lead.get("campaign_id"))
                if db.one("SELECT status FROM leads WHERE id=?", (target,))["status"] == "new":
                    payload = {'lead_id': target}
                    if signal.get('official_match_url') and crawl_url(signal['official_match_url']) != crawl_url(signal['website']):
                        payload['seed_urls'] = [signal['official_match_url']]
                    db.enqueue("research", payload)
                report["website_lead_id"] = target
        notes = (f"Profile research: {website_status}; public snapshot {snapshot.get('state', 'unavailable')}. "
                 "Website not found means not found in this search, not confirmed absent. Confirm business identity, current activity, geography and contact ownership. Indexed-only emails cannot be imported.")
        db.execute("UPDATE leads SET status=?,website_status=?,findings=?,research_notes=?,updated_at=? WHERE id=?",
                   ("review" if captured else "profile_unavailable", website_status, json.dumps([finding] if finding else []), notes, time.time(), lid))
        db.event("profile_research", {"lead_id": lid, **report})
    except BaseException:
        report["status"] = "interrupted_or_failed"
        db.execute("UPDATE leads SET status='research_failed',website_status='search_unavailable',updated_at=? WHERE id=?", (time.time(), lid))
        raise
    finally:
        db.execute("UPDATE crawls SET report=? WHERE id=?", (json.dumps(report), crawl_id))


def _country_hint(lead):
    return lead.get("discovery_country") or ("US" if "hint: US" in lead.get("research_notes", "") else "UK")
