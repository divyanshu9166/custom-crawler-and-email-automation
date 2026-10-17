import asyncio
import json
import secrets
import hashlib
import time
import re
from urllib.parse import urlsplit, urlunsplit

from . import providers
from .web import PublicWeb, domain_of, crawl_url, normalize_email, outreach_email_allowed, BLOCKED_SOURCES, EMAIL_RE


def add_lead(db, company, website, campaign, source_url, country_hint=""):
    website, source_url = crawl_url(website), crawl_url(source_url)
    domain = domain_of(website)
    if any(domain == d or domain.endswith("." + d) for d in BLOCKED_SOURCES):
        raise ValueError("Use the official company website; platform URLs may be recorded as source_url only")
    from .discovery import official_root
    official_root(website)  # CSV/manual imports must honor the same marketplace/source gate as discovery.
    if campaign not in {"A", "B"}:
        raise ValueError("Campaign must be A or B")
    now = time.time()
    with db.connect() as con:
        con.execute("INSERT OR IGNORE INTO leads(domain,website,company,campaign,source_url,research_notes,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                    (domain, website, company[:200], campaign, source_url,
                     f"Discovery country hint: {country_hint or 'unknown'}; confirm against original source.", now, now))
        return con.execute("SELECT id FROM leads WHERE domain=?", (domain,)).fetchone()[0]


def current_evidence(db, lead_id):
    """Keep old captures for history; new research/reviews use only refreshed pages."""
    return db.all("""SELECT e.* FROM evidence e WHERE e.lead_id=?
        AND e.fetched_at >= COALESCE((SELECT created_at FROM crawls WHERE lead_id=e.lead_id ORDER BY id DESC LIMIT 1),0)
        ORDER BY e.id""", (lead_id,))


def fresh_evidence(db, lead_id):
    """Current review sources, with a 30-day age limit and bounded clock skew."""
    now = time.time()
    return [e for e in current_evidence(db, lead_id) if now-30*86400 <= e['fetched_at'] <= now+60]


def candidate_source(db, lead_id, email, source_url):
    """Only current, saved official-page extraction can support an ownership review."""
    return db.one("""SELECT e.sha256 FROM evidence e JOIN events v
        ON v.kind='contact_candidate_found'
        AND json_extract(v.detail,'$.lead_id')=e.lead_id
        AND json_extract(v.detail,'$.source_url')=e.url
        AND json_extract(v.detail,'$.evidence_sha256')=e.sha256
        WHERE e.lead_id=? AND e.url=? AND json_extract(v.detail,'$.email')=?
        AND e.fetched_at >= COALESCE((SELECT created_at FROM crawls WHERE lead_id=e.lead_id ORDER BY id DESC LIMIT 1),0)
        AND e.fetched_at BETWEEN ? AND ?
        LIMIT 1""",
        (lead_id, source_url, email, time.time()-30*86400, time.time()+60))


def record_contact_publications(db, lead_id, page):
    """Retain extraction proof for visible, mailto and public structured contacts."""
    for email in page['emails']:
        detail = {'lead_id': lead_id, 'email': email, 'source_url': page['url'],
                  'evidence_sha256': page['sha256']}
        key = hashlib.sha256(json.dumps([lead_id, page['url'], email, page['sha256']]).encode()).hexdigest()
        db.event('contact_publication_found', detail, external_id='publication:'+key)


def company_publication(db, contact, lead):
    """A matching domain alone cannot establish that an address was published."""
    if domain_of(contact['source_url']) != lead['domain']:
        from .professionals import reviewed_publication
        return reviewed_publication(db,lead,contact['source_url'],contact['email'])
    page = db.one("""SELECT e.* FROM evidence e WHERE e.lead_id=? AND e.url=?
        AND e.fetched_at>=COALESCE((SELECT created_at FROM crawls WHERE lead_id=e.lead_id ORDER BY id DESC LIMIT 1),0)
        AND e.fetched_at BETWEEN ? AND ?""",
        (lead['id'], contact['source_url'], time.time()-30*86400, time.time()+60))
    if not page:
        page = next((p for p in fresh_evidence(db, lead['id'])
                     if crawl_url(p['url']) == crawl_url(contact['source_url'])), None)
    if not page:
        return None
    proof = db.one("""SELECT 1 FROM events WHERE kind='contact_publication_found'
        AND json_extract(detail,'$.lead_id')=? AND json_extract(detail,'$.email')=?
        AND json_extract(detail,'$.source_url')=? AND json_extract(detail,'$.evidence_sha256')=? LIMIT 1""",
        (lead['id'], contact['email'], page['url'], page['sha256']))
    if proof:
        return page
    # Older captures and manual imports can use the exact email in current
    # visible text. Snippets, patterns, hidden scripts and unrelated pages cannot.
    for value in re.findall(EMAIL_RE, page['text']):
        try:
            if normalize_email(value) == contact['email']:
                return page
        except ValueError:
            pass
    return None


def assert_contact_ownership(db, contact, lead):
    from .profiles import assert_profile_review, source_allowed
    if not outreach_email_allowed(contact['email']):
        raise ValueError('Dedicated privacy/security/automated inbox is not a relevant outreach contact')
    profile = lead.get("lead_kind") == "profile"
    if profile:
        assert_profile_review(db, lead)
    else:
        from .discovery import official_root
        official_root(lead['website'])
    host = contact["email"].split("@")[1]
    if not profile and (host == lead["domain"] or host.endswith("." + lead["domain"])):
        if not company_publication(db, contact, lead):
            raise ValueError('Company-domain inbox needs current saved official-source publication evidence; refresh its contact page')
        return
    proof = candidate_source(db, lead["id"], contact["email"], contact["source_url"])
    review = db.one("""SELECT detail FROM events WHERE kind='contact_source_reviewed' AND contact_id=?
        AND json_extract(detail,'$.source_url')=? AND json_extract(detail,'$.evidence_sha256')=?
        ORDER BY id DESC LIMIT 1""", (contact["id"], contact["source_url"], proof["sha256"] if proof else ""))
    if (not source_allowed(lead, contact["source_url"],db,contact['email']) or not proof or not review
            or len(json.loads(review["detail"]).get("ownership_notes", "").strip()) < 30):
        raise ValueError("Different-domain inbox needs current official-source evidence and company ownership review")


def contact_candidates(db, lead_id):
    rows = db.all("""SELECT DISTINCT v.detail FROM evidence e JOIN events v
        ON v.kind='contact_candidate_found' AND json_extract(v.detail,'$.lead_id')=e.lead_id
        AND json_extract(v.detail,'$.source_url')=e.url AND json_extract(v.detail,'$.evidence_sha256')=e.sha256
        WHERE e.lead_id=?
        AND e.fetched_at >= COALESCE((SELECT created_at FROM crawls WHERE lead_id=e.lead_id ORDER BY id DESC LIMIT 1),0)
        AND e.fetched_at BETWEEN ? AND ?
        ORDER BY v.id DESC LIMIT 500""", (lead_id, time.time()-30*86400, time.time()+60))
    found = {}
    for row in rows:
        candidate = json.loads(row["detail"])
        if candidate.get('method')=='reviewed_professional':
            continue  # Dedicated professional-source review, not the generic inbox form.
        if not outreach_email_allowed(candidate['email']):
            continue
        found.setdefault(candidate["email"], candidate)
    return list(found.values())


def add_contact(db, lead_id, email, source_url, name="", role="", ownership_notes=""):
    from .profiles import assert_profile_review, source_allowed
    email = normalize_email(email)
    if not outreach_email_allowed(email):
        raise ValueError('Dedicated privacy/security/automated inbox is not a relevant outreach contact')
    source_url = crawl_url(source_url)
    lead = db.one("SELECT * FROM leads WHERE id=?", (lead_id,))
    if not lead:
        raise ValueError("Lead not found")
    if lead.get("lead_kind") == "profile":
        assert_profile_review(db, lead)
    email_domain = email.split("@")[1]
    different_domain = email_domain != lead["domain"] and not email_domain.endswith("." + lead["domain"])
    proof = None
    if different_domain:
        proof = candidate_source(db, lead_id, email, source_url)
        if not source_allowed(lead, source_url,db,email) or not proof or len(ownership_notes.strip()) < 30:
            raise ValueError("Only business emails matching this company domain are accepted automatically; other domains need saved official-source evidence and ownership review")
    with db.connect() as con:
        con.execute("BEGIN IMMEDIATE")
        existing = con.execute("SELECT id,lead_id,status FROM contacts WHERE email=?", (email,)).fetchone()
        if existing and existing["lead_id"] != lead_id:
            raise ValueError("This inbox is already linked to another company; review shared ownership before proceeding")
        if different_domain and existing and existing["status"] != "new":
            raise ValueError("Existing outreach history: preserve this contact's ownership review")
        suppressed = con.execute("SELECT 1 FROM suppression WHERE email=?", (email,)).fetchone()
        con.execute("INSERT OR IGNORE INTO contacts(lead_id,email,name,role,source_url,unsubscribe_token,created_at,status) VALUES(?,?,?,?,?,?,?,?)",
                    (lead_id, email, name[:150], role[:150], source_url, secrets.token_urlsafe(32), time.time(),
                     "suppressed" if suppressed else "new"))
        cid = con.execute("SELECT id FROM contacts WHERE email=?", (email,)).fetchone()[0]
        if not different_domain and existing and existing['status'] == 'new':
            from .sequence import Reader
            if company_publication(Reader(con), {'email': email, 'source_url': source_url}, lead):
                con.execute("UPDATE contacts SET source_url=? WHERE id=? AND status='new'", (source_url, cid))
        if different_domain:
            if lead.get("lead_kind") == "profile":
                current_lead = dict(con.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone())
                assert_profile_review(db, current_lead)
                if current_lead["profile_review"] != lead["profile_review"]:
                    raise ValueError("Profile review changed during contact import; reload")
            current = con.execute("""SELECT e.sha256 FROM evidence e WHERE e.lead_id=? AND e.url=?
                AND e.fetched_at >= COALESCE((SELECT created_at FROM crawls WHERE lead_id=e.lead_id ORDER BY id DESC LIMIT 1),0)""",
                (lead_id, source_url)).fetchone()
            if not current or current[0] != proof["sha256"]:
                raise ValueError("Source changed during review; reload its evidence")
            con.execute("UPDATE contacts SET source_url=? WHERE id=? AND status='new'", (source_url, cid))
            con.execute("INSERT INTO events(kind,contact_id,detail,created_at) VALUES(?,?,?,?)",
                        ("contact_source_reviewed", cid, json.dumps({"lead_id": lead_id, "source_url": source_url,
                         "evidence_sha256": proof["sha256"], "ownership_notes": ownership_notes.strip()[:2000]}), time.time()))
        return cid


def research_checkpoint(db, lead_id):
    from .crawl_state import CHECKPOINT_WORK, continuation_wait
    lead = db.one('SELECT * FROM leads WHERE id=?', (lead_id,))
    if not lead or lead['lead_kind'] == 'profile':
        raise ValueError('Continuation requires an official website prospect')
    from .discovery import official_root
    official_root(lead['website'])
    row = db.one('SELECT * FROM crawls WHERE lead_id=? ORDER BY id DESC LIMIT 1', (lead_id,))
    report = json.loads(row['report']) if row else {}
    checkpoint = report.get('checkpoint', {})
    if not row or not time.time()-30*86400 <= row['created_at'] <= time.time()+60:
        raise ValueError('Refresh stale research before continuing')
    if checkpoint.get('website') != crawl_url(lead['website']):
        raise ValueError('No matching crawl checkpoint; refresh this older capture first')
    if not any(checkpoint.get(key) for key in CHECKPOINT_WORK):
        raise ValueError('No queued URLs remain; inspect access/render issues instead')
    if continuation_wait(checkpoint):
        raise ValueError('Crawl cooldown is active; continue after the saved retry time')
    return row, report


async def research_lead(db, settings, lead_id, continuation=False, protect_review=False, seed_urls=None):
    lead = db.one("SELECT * FROM leads WHERE id=?", (lead_id,))
    if not lead:
        raise ValueError("Lead not found")
    if protect_review and lead['status'] == 'qualified':
        raise ValueError('Automatic research stopped after business review')
    if lead.get("lead_kind") == "profile":
        if continuation:
            raise ValueError('Profile research has no website crawl checkpoint')
        from .profiles import research_profile
        return await research_profile(db, settings, lead)
    from .discovery import official_root
    try:
        official_root(lead['website'])
    except ValueError:
        db.execute("UPDATE leads SET status='research_failed',research_notes=?,updated_at=? WHERE id=?",
                   ('Official company identity rejected: this source is a platform/directory/marketplace, not an official business website.', time.time(), lead_id))
        raise
    active = db.one("SELECT id FROM contacts WHERE lead_id=? AND status IN ('active','replied','hold','closed')", (lead_id,))
    if active:
        raise ValueError("Existing outreach history: preserve evidence and review manually instead of recrawling")
    resume_row, resume_report = research_checkpoint(db, lead_id) if continuation else (None, None)
    saved = {p['url'] for p in current_evidence(db, lead_id)} if continuation else set()
    crawl_id = None
    async def save_page(page, report):
        db.execute("INSERT INTO evidence(lead_id,url,title,text,sha256,fetched_at) VALUES(?,?,?,?,?,?) ON CONFLICT(lead_id,url) DO UPDATE SET title=excluded.title,text=excluded.text,sha256=excluded.sha256,fetched_at=excluded.fetched_at",
                   (lead_id, page["url"], page["title"], page["text"], page["sha256"], time.time()))
        record_contact_publications(db, lead_id, page)
        sourced = {entry["email"]: entry for entry in page.get("contacts", [])}
        for entry in page.get("review_candidates", []):
            detail = {**entry, "lead_id": lead_id, "source_url": page["url"], "evidence_sha256": page["sha256"]}
            key = hashlib.sha256(json.dumps([lead_id, page["url"], entry["email"], page["sha256"]]).encode()).hexdigest()
            db.event("contact_candidate_found", detail, external_id="candidate:" + key)
        for email in page["emails"]:
            entry = sourced.get(email, {})
            cid = add_contact(db, lead_id, email, page["url"], entry.get("name", ""), entry.get("role", ""))
            # Enrich only missing identity fields with explicitly published structured data.
            if entry.get('identity_ambiguous'):
                db.execute("UPDATE contacts SET name='',role='' WHERE id=? AND status='new'", (cid,))
            else:
                db.execute("UPDATE contacts SET name=CASE WHEN name='' THEN ? ELSE name END,role=CASE WHEN role='' THEN ? ELSE role END WHERE id=? AND status='new'",
                           (entry.get("name", ""), entry.get("role", ""), cid))
            contact = db.one("SELECT status,verification FROM contacts WHERE id=?", (cid,))
            if contact["status"] != "suppressed" and contact["verification"] == "unverified":
                db.enqueue("verify", {"contact_id": cid})
        saved.add(page["url"])
        if crawl_id:
            db.execute("UPDATE crawls SET report=? WHERE id=?", (json.dumps(report), crawl_id))
    def save_checkpoint(report):
        if crawl_id:
            db.execute('UPDATE crawls SET report=? WHERE id=?', (json.dumps(report), crawl_id))
    crawler = PublicWeb(settings, on_page=save_page, on_checkpoint=save_checkpoint)
    if continuation:
        crawler.report = json.loads(json.dumps(resume_report))
        crawler.report['status'] = 'running'
    # Approval and research start must serialize around the same lead state.
    # The initial check can become stale before this job obtains its write lock.
    with db.connect() as con:
        con.execute("BEGIN IMMEDIATE")
        if protect_review and con.execute("SELECT status FROM leads WHERE id=?", (lead_id,)).fetchone()['status'] == 'qualified':
            raise ValueError('Automatic research stopped after business review')
        if con.execute("SELECT id FROM contacts WHERE lead_id=? AND status IN ('active','replied','hold','closed')", (lead_id,)).fetchone():
            raise ValueError("Existing outreach history: preserve evidence and review manually instead of recrawling")
        started_at = time.time()
        if continuation:
            current = con.execute('SELECT id,report FROM crawls WHERE lead_id=? ORDER BY id DESC LIMIT 1', (lead_id,)).fetchone()
            if not current or current['id'] != resume_row['id'] or current['report'] != resume_row['report']:
                raise ValueError('Crawl changed before continuation; reload its checkpoint')
            crawl_id = resume_row['id']
            con.execute('UPDATE crawls SET report=? WHERE id=?', (json.dumps(crawler.report), crawl_id))
        else:
            crawl_id = con.execute("INSERT INTO crawls(lead_id,report,created_at) VALUES(?,?,?)",
                                   (lead_id, json.dumps(crawler.report), started_at)).lastrowid
        con.execute("UPDATE leads SET status='researching',updated_at=? WHERE id=?", (started_at, lead_id))
    try:
        if continuation:
            pages = await crawler.crawl(lead['website'], continuation=resume_report)
        elif seed_urls:
            pages = await crawler.crawl(lead['website'], seed_urls=[lead['website'], *seed_urls[:8]])
        else:
            pages = await crawler.crawl(lead['website'])
    except (Exception, asyncio.CancelledError) as exc:
        from .crawl_state import transient_failure
        crawler.report.update(status="interrupted" if isinstance(exc, asyncio.CancelledError) else "failed")
        crawler.report["errors"].append({"stage": "crawl", "reason": type(exc).__name__,
                                        'url': crawler.report.get('activity', {}).get('url', lead['website']),
                                        'retryable': transient_failure(exc) or isinstance(exc, asyncio.CancelledError)})
        if getattr(exc, 'response', None) is not None:
            crawler.report['errors'][-1]['http_status'] = exc.response.status_code
        crawler.report['errors'][-1]['last_stage'] = crawler.report.get('activity', {}).get('stage', 'unknown')
        db.execute("UPDATE crawls SET report=? WHERE id=?", (json.dumps(crawler.report), crawl_id))
        db.execute("UPDATE leads SET status=?,research_notes=?,updated_at=? WHERE id=?",
                   ("review" if saved else "research_failed",
                    f"Research {crawler.report['status']}; {len(saved)} pages preserved. Inspect report and retry before making completeness claims.",
                    time.time(), lead_id))
        raise
    for page in pages:
        if page["url"] not in saved:
            await save_page(page, crawler.report)
    db.execute("UPDATE crawls SET report=? WHERE id=?", (json.dumps(crawler.report), crawl_id))
    evidence = current_evidence(db, lead_id)
    if not evidence:
        db.execute("UPDATE leads SET status='research_failed',research_notes=?,updated_at=? WHERE id=?",
                   ("No current source pages saved; historical captures are preserved but cannot support new findings.", time.time(), lead_id))
        raise ValueError("No current source pages available from this research attempt")
    report = crawler.report
    from .crawl_state import current_errors
    issues = len(current_errors(report))
    notes = (f"Website research: {report['status']}; {len(evidence)} saved pages, "
             f"{issues} current issues, {report.get('remaining', 0)} URLs remaining. "
             "Confirm company, country, buyer role and selected opportunity; inspect the crawl report before making claims.")
    db.event("research", {"lead_id": lead_id, "status": report["status"], "pages": len(evidence), 'continuation': continuation,
                          "issues": issues, "remaining": report.get("remaining", 0)})
    try:
        findings = await providers.research_suggestions(settings, lead, evidence)
    except Exception as exc:
        findings = []
        notes += f" AI suggestions unavailable ({type(exc).__name__}); review saved evidence."
    if not findings:
        from .opportunities import proposals
        findings = proposals(lead, evidence)
        if findings:
            notes += ' Free service proposals use explicit public signals; review relevance, buyer fit and the proposed change.'
    if not findings:
        first = evidence[0]
        findings = [{"evidence_id": first["id"], "quote": first["text"][:240],
                     "observation": "Review this page for one specific opportunity.",
                     "suggestion": "", "service": "website_improvement" if lead["campaign"] == "A" else "store_improvement",
                     "review_required": True, "kind": "needs_review"}]
    db.execute("UPDATE leads SET status='review',findings=?,research_notes=?,updated_at=? WHERE id=?",
               (json.dumps(findings), notes, time.time(), lead_id))
    if settings.browser_enabled and settings.auto_visual_audit:
        db.enqueue("screenshot", {"lead_id": lead_id})
    if settings.auto_contact_research and not continuation:
        db.enqueue('contact_research', {'lead_id': lead_id})
    if settings.auto_professional_research and not continuation:
        db.enqueue('professional_research',{'lead_id':lead_id})


async def discover_leads(db, settings, query, campaign, country_hint, limit):
    from .discovery import prospect_candidates
    context = {"run_id": secrets.token_hex(12), "base_query": query, "campaign": campaign, "country_hint": country_hint}
    db.event("discovery_started", {**context, "limit": limit})
    added = []
    def import_candidate(row):
        if len(set(added)) >= limit:
            return
        parts = urlsplit(row["url"])
        website = urlunsplit((parts.scheme, parts.netloc, "/", "", ""))
        try:
            lid = add_lead(db, row["title"] or domain_of(website), website, campaign, row.get("source_url", row["url"]), country_hint)
            if db.one("SELECT status FROM leads WHERE id=?", (lid,))["status"] == "new":
                payload = {'lead_id': lid}
                if row.get('research_seed_url') and crawl_url(row['research_seed_url']) != crawl_url(website):
                    payload['seed_urls'] = [row['research_seed_url']]
                db.enqueue("research", payload)
            if lid not in added:
                added.append(lid)
        except ValueError:
            return
    def save_signal(signal):
        from .profiles import add_profile_lead
        match = db.one("SELECT id FROM leads WHERE domain=?", (domain_of(signal["website"]),)) if signal.get("website") else None
        if not signal.get("website") and signal.get("company") and len(set(added)) < limit:
            try:
                lid = add_profile_lead(db, signal["company"], signal["source_url"], campaign, country_hint)
                if db.one("SELECT status FROM leads WHERE id=?", (lid,))["status"] == "new":
                    db.enqueue("research", {"lead_id": lid})
                if lid not in added:
                    added.append(lid)
                match = {"id": lid}
            except ValueError:
                pass
        db.event("prospect_signal", {**signal, **context, "lead_id": match["id"] if match else None, "query": query, "observed_at": time.time()})
    try:
        rows, report = await prospect_candidates(settings, query, country_hint, limit,
                        on_candidate=import_candidate, on_signal=save_signal,
                        on_progress=lambda progress: db.event("discovery_progress", {**progress, **context}))
    except (Exception, asyncio.CancelledError) as exc:
        db.event("discovery_interrupted", {**context, "lead_ids": added, "error_type": type(exc).__name__})
        raise
    db.event("discovery", {**context, "query": query, "lead_ids": added, "candidates": len(rows), "report": report})
    if not rows and not added:
        if report["signals"]:
            raise ValueError("Search returned no usable official company websites; unresolved platform signals were saved for review")
        raise ValueError("Search returned no candidates; inspect engine availability or revise query")
    if not added:
        raise ValueError("Search returned no usable official company websites; inspect results or revise query")


async def verify_contact(db, settings, contact_id):
    contact = db.one("SELECT * FROM contacts WHERE id=?", (contact_id,))
    if not contact or contact["status"] == "suppressed":
        return
    assert_contact_ownership(db, contact, db.one("SELECT * FROM leads WHERE id=?", (contact["lead_id"],)))
    last = float(db.get("last_verification_attempt", "0"))
    wait = settings.verification_interval_seconds - (time.time() - last)
    if wait > 0:
        await asyncio.sleep(wait)
    # Browser research and opt-outs run independently of the serial provider
    # lane. Its spacing delay must not carry stale ownership into a new probe.
    contact = db.one("SELECT * FROM contacts WHERE id=?", (contact_id,))
    if not contact or contact["status"] == "suppressed":
        return
    assert_contact_ownership(db, contact, db.one("SELECT * FROM leads WHERE id=?", (contact["lead_id"],)))
    db.set("last_verification_attempt", time.time())
    from .sequence import Reader

    def current_contact(view):
        current = view.one('SELECT * FROM contacts WHERE id=?', (contact_id,))
        if not current:
            raise ValueError('Contact no longer exists; verification stopped')
        if current['email'] != contact['email']:
            raise ValueError('Recipient changed during verification; research the current address again')
        if (current['status'] == 'suppressed' or
                view.one('SELECT 1 FROM suppression WHERE email=?', (current['email'],))):
            raise ValueError('Contact is suppressed; verification stopped')
        lead = view.one('SELECT * FROM leads WHERE id=?', (current['lead_id'],))
        if not lead:
            raise ValueError('Business no longer exists; verification stopped')
        assert_contact_ownership(view, current, lead)
        return current

    def before_probe():
        with db.connect() as con:
            con.execute('BEGIN')
            current_contact(Reader(con))

    try:
        verdict, raw = await providers.verify_email(settings, contact["email"], before_probe=before_probe)
        # The request may finish after an opt-out, new research or recipient
        # edit. Validation and the result write share one short transaction;
        # no database lock is held across the provider's network request.
        with db.connect() as con:
            con.execute('BEGIN IMMEDIATE')
            current_contact(Reader(con))
            con.execute("UPDATE contacts SET verification=?,verification_raw=?,verified_at=? WHERE id=?",
                        (verdict, json.dumps(raw), time.time(), contact_id))
            if verdict != 'safe':
                con.execute("UPDATE contacts SET status='hold' WHERE id=? AND status='active'", (contact_id,))
            con.execute("INSERT INTO events(kind,detail,contact_id,created_at) VALUES(?,?,?,?)",
                        ('verification', json.dumps({'verdict': verdict}), contact_id, time.time()))
    except Exception as exc:
        db.execute("""UPDATE contacts SET verification='unknown',verification_raw=?,verified_at=?,
                   status=CASE WHEN status='active' THEN 'hold' ELSE status END
                   WHERE id=? AND email=? AND status!='suppressed'""",
                   (json.dumps({"error": type(exc).__name__, 'provider_status': getattr(exc, 'detail', None)}),
                    time.time(), contact_id, contact['email']))
        raise
