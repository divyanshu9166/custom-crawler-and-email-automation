"""Read-only execution map. Node states come from persisted jobs and records."""
import json
import time

from .research import assert_contact_ownership
from .offers import selected_offer
from .sequence import assert_approved


DEFINITIONS = [
    ("discovery", "Discover prospects", "Public search and known business imports", "discovery"),
    ("website", "Website research", "Rendered pages, evidence and audit", "research"),
    ("profile", "Profile research", "Business identity and website lookup", "research"),
    ("contacts", "Published contacts", "Extraction and inbox ownership review", "contacts"),
    ("qualify", "Qualify business", "Country, buyer fit and one useful offer", "review"),
    ("verify", "Verify email", "Fresh technical Reacher verdict", "verification"),
    ("drafts", "Write 4 touches", "Personalized pitch and follow-ups", "drafts"),
    ("approval", "Approve outreach", "Recipient, eligibility and message review", "review"),
    ("send", "Send sequence", "Mailbox, quota and prospect time window", "mail"),
    ("replies", "Monitor replies", "Stop on reply, opt-out or delivery issue", "mail"),
    ("sales", "Client journey", "Calls, proposals, delivery and outcomes", "sales"),
]
EDGES = [("discovery", "website"), ("discovery", "profile"), ("website", "contacts"),
         ("profile", "contacts"), ("contacts", "qualify"), ("contacts", "verify"),
         ("qualify", "drafts"), ("drafts", "approval"), ("verify", "approval"),
         ("approval", "send"), ("send", "replies"), ("replies", "sales")]


def snapshot(db, settings, lead_id=None):
    leads = db.all("SELECT * FROM leads" + (" WHERE id=?" if lead_id else ""), (lead_id,) if lead_id else ())
    if lead_id and not leads:
        raise ValueError("Prospect not found")
    ids = {lead["id"] for lead in leads}
    contacts = [c for c in db.all("SELECT * FROM contacts") if c["lead_id"] in ids]
    cids = {c["id"] for c in contacts}
    messages = [m for m in db.all("SELECT contact_id,state,step FROM messages") if m["contact_id"] in cids]
    jobs = []
    for job in db.all("SELECT id,kind,state,payload FROM jobs ORDER BY id"):
        payload = json.loads(job["payload"])
        if not lead_id or payload.get("lead_id") in ids or payload.get("contact_id") in cids:
            jobs.append(job)
    candidates = [dict(row) for row in db.all("""SELECT DISTINCT e.lead_id,json_extract(v.detail,'$.email') email
        FROM evidence e JOIN events v ON v.kind='contact_candidate_found'
        AND json_extract(v.detail,'$.lead_id')=e.lead_id AND json_extract(v.detail,'$.source_url')=e.url
        AND json_extract(v.detail,'$.evidence_sha256')=e.sha256
        WHERE e.fetched_at>=COALESCE((SELECT created_at FROM crawls WHERE lead_id=e.lead_id ORDER BY id DESC LIMIT 1),0)
        AND e.fetched_at BETWEEN ? AND ?
        AND NOT EXISTS(SELECT 1 FROM contacts c WHERE c.lead_id=e.lead_id AND c.email=json_extract(v.detail,'$.email'))""",
        (time.time()-30*86400, time.time()+60)) if row['lead_id'] in ids]
    sales = [s for s in db.all("SELECT lead_id,stage FROM sales") if s["lead_id"] in ids]
    def job_state(kinds, scope=None):
        rows = [j for j in jobs if j["kind"] in kinds and (scope is None or json.loads(j["payload"]).get("lead_id") in scope)]
        if any(j["state"] == "running" for j in rows):
            return "running"
        if any(j["state"] == "pending" for j in rows):
            return "queued"
        # A successful later attempt supersedes a prior terminal failure for the same work.
        latest = {}
        for j in rows:
            payload = json.loads(j["payload"])
            latest[(j["kind"], payload.get("lead_id"), payload.get("contact_id"))] = j
        return "failed" if any(j["state"] == "failed" for j in latest.values()) else "idle"
    nodes = {key: {"id": key, "title": title, "description": description, "category": category,
                   "state": "waiting", "metric": "Waiting for earlier steps", "details": []}
             for key, title, description, category in DEFINITIONS}
    def set_node(key, state, metric, *details):
        nodes[key].update(state=state, metric=metric, details=list(details))
    discovered = job_state({"discover"})
    set_node("discovery", discovered if discovered in {"running", "queued", "failed"} else "complete" if leads else "ready",
             f"{len(leads)} businesses", "Search/imports create candidates; identity and country still need review.")
    websites = [lead for lead in leads if lead["lead_kind"] == "website"]
    profiles = [lead for lead in leads if lead["lead_kind"] == "profile"]
    for key, group in [("website", websites), ("profile", profiles)]:
        pending_job = job_state({"research", "screenshot", "performance", 'contact_research','professional_research','social_research'}, {lead["id"] for lead in group})
        failed = any(lead["status"] in {"research_failed", "profile_unavailable"} for lead in group)
        working = any(lead["status"] == "researching" for lead in group)
        new = any(lead["status"] == "new" for lead in group)
        state = pending_job if pending_job in {"running", "queued", "failed"} else "running" if working else "ready" if new else "blocked" if failed else "complete" if group else "waiting"
        noun = "business" if len(group) == 1 else "businesses"
        set_node(key, state, f"{len(group)} {noun}", "Complete means the research step finished; coverage may still be partial.",
                 *(f"{lead['company']}: {lead['status'].replace('_', ' ')}. {lead['research_notes'][:400]}" for lead in group[:5]))
    publication_holds = []
    lead_by_id = {lead['id']: lead for lead in leads}
    for contact in contacts:
        if contact['status'] == 'suppressed':
            continue
        try:
            assert_contact_ownership(db, contact, lead_by_id[contact['lead_id']])
        except ValueError:
            publication_holds.append(contact['id'])
    from .professionals import captures,reviewed_publication
    professional_pending=0
    for lead in websites:
        for source in captures(db,lead['id']):
            if source['state']=='captured' and source['fresh']:
                professional_pending+=sum(not reviewed_publication(db,lead,source['url'],email) for email in source['published_emails'])
    set_node("contacts", "review" if candidates or publication_holds or professional_pending else "complete" if contacts else "waiting",
             f"{len(contacts)} contacts · {len(candidates)} captured candidates · {professional_pending} professional candidates",
             f"{len(publication_holds)} stored contacts need current publication/ownership evidence. Indexed-only and guessed emails stay held.")
    qualified_ids = {lead['id'] for lead in leads if selected_offer(db, lead)}
    qualified = len(qualified_ids)
    reviewable = any(lead['status'] in {'review', 'qualified'} and lead['id'] not in qualified_ids for lead in leads)
    set_node("qualify", "review" if reviewable else "complete" if leads and qualified == len(leads) else "waiting", f"{qualified}/{len(leads)} qualified",
             "Confirm current evidence, geography, business identity and one relevant offer.")
    now = time.time()
    lead_by_id = {lead['id']: lead for lead in leads}
    safe_ids = set()
    for contact in contacts:
        if (contact['status'] == 'suppressed' or contact['verification'] != 'safe' or not contact['verified_at']
                or not 0 <= now-contact['verified_at'] <= settings.verification_max_age_hours*3600
                or db.one('SELECT 1 FROM suppression WHERE email=?', (contact['email'],))):
            continue
        try:
            assert_contact_ownership(db, contact, lead_by_id[contact['lead_id']])
        except ValueError:
            continue
        safe_ids.add(contact['id'])
    safe = len(safe_ids)
    verification = job_state({"verify"})
    set_node("verify", verification if verification in {"running", "queued", "failed"} else "complete" if contacts and safe == len(contacts) else "blocked" if contacts else "waiting",
             f"{safe}/{len(contacts)} fresh safe", "Only unsuppressed contacts with current ownership proof count. Technical verification does not establish buyer fit or outreach eligibility.")
    drafts = sum(m["state"] == "draft" for m in messages)
    set_node("drafts", "review" if drafts else "complete" if messages else "ready" if qualified and contacts else "waiting",
             f"{drafts} drafts", "Review every observation, offer and follow-up before approval.")
    from .email_writer import assert_ai_origin, configuration as writer_configuration
    ai_contacts, legacy_contacts = set(), set()
    for contact in contacts:
        if not any(m['contact_id'] == contact['id'] for m in messages):
            continue
        try:
            assert_ai_origin(db, contact['id'])
            ai_contacts.add(contact['id'])
        except ValueError:
            legacy_contacts.add(contact['id'])
    writer = writer_configuration(settings)
    if legacy_contacts:
        set_node('drafts', 'blocked', f'{len(legacy_contacts)} legacy sequences',
                 'Old template drafts cannot be approved. Rewrite from current reviewed research using the AI writer.', writer['note'])
    elif qualified and contacts and not writer['configured'] and not messages:
        set_node('drafts', 'blocked', 'AI writer not configured', writer['note'])
    else:
        nodes['drafts']['details'].append(writer['note'])
    preparation_state = job_state({'prepare'})
    if preparation_state in {'running', 'queued', 'failed'} and not messages:
        nodes['drafts'].update(state=preparation_state,
                               description='AI prepares source-backed qualification and an unsent initial email. Final recipient/message review remains manual.')
        if preparation_state in {'running', 'queued'}:
            nodes['qualify']['state'] = preparation_state
    preparation_events = db.all("SELECT detail FROM events WHERE kind='preparation' ORDER BY id")
    latest_preparation = {}
    for event in preparation_events:
        detail = json.loads(event['detail'])
        if detail.get('lead_id') in ids:
            latest_preparation[detail['lead_id']] = detail
    exceptions = [r for r in latest_preparation.values() if r.get('state') in {'needs_attention', 'needs_evidence'}]
    if exceptions and not messages and preparation_state not in {'running', 'queued'}:
        nodes['drafts'].update(state='blocked', metric=f'{len(exceptions)} preparation exceptions')
        nodes['drafts']['details'].extend(r['reason'] for r in exceptions)
    approved = sum(bool(c['reviewed_at']) for c in contacts)
    review_candidates = []
    for contact in contacts:
        sequence = [m for m in messages if m['contact_id'] == contact['id']]
        if (contact['status'] == 'new' and contact['id'] in safe_ids and contact['id'] in ai_contacts
                and contact['lead_id'] in qualified_ids
                and {m['step'] for m in sequence} == set(range(4 if settings.followups_enabled else 1))
                and all(m['state'] == 'draft' for m in sequence)):
            review_candidates.append(contact['id'])
    context_holds = set()
    def check_pending(con):
        for contact in contacts:
            if not contact['reviewed_at'] or contact['status'] not in {'active', 'hold'}:
                continue
            if not any(m['contact_id'] == contact['id'] and m['state'] == 'queued' for m in messages):
                continue
            try:
                assert_approved(con, settings, lead_by_id[contact['lead_id']], contact)
            except ValueError:
                context_holds.add(contact['lead_id'])
    if hasattr(db, 'con'):
        check_pending(db.con)
    else:
        with db.connect() as con:
            check_pending(con)
    approval_blocked = bool(drafts) or bool(context_holds) or any(c['status'] == 'suppressed' for c in contacts)
    set_node("approval", "review" if review_candidates else "blocked" if approval_blocked else "complete" if approved else "waiting",
             f"{approved} activated contacts", "Readiness uses one contact's own business, current proof and complete sequence; it cannot combine different prospects. Final approval enforces sender identity, buyer relevance, eligibility and every remaining gate.")
    sent = sum(m["state"] == "sent" for m in messages)
    active = sum(c["status"] == "active" for c in contacts)
    paused = not settings.sending_enabled or db.get("paused", "true") != "false"
    set_node("send", "paused" if paused else "running" if any(m["state"] == "sending" for m in messages) else "queued" if active else "waiting",
             f"{sent} accepted by SMTP", "Sending is disabled or paused." if paused else "Approved messages obey mailbox quota and prospect-local sending windows.")
    replied = sum(c["status"] == "replied" for c in contacts)
    inbox_fresh = (db.get('imap_caught_up') == 'true' and 0 <= now-float(db.get('imap_last_success', '0')) <= 180)
    set_node("replies", "running" if sent and inbox_fresh and settings.worker_enabled else "blocked" if sent else "waiting",
             f"{replied} replies", "Inbox monitoring stops follow-ups on replies and handles delivery/opt-out events.")
    open_tasks = sum(task['lead_id'] in ids for task in db.all("SELECT lead_id FROM tasks WHERE state='open'"))
    sales_finished = bool(sales) and all(s['stage'] in {'completed', 'lost'} for s in sales) and not open_tasks
    set_node("sales", "complete" if sales_finished else "review" if sales else "ready" if replied else "waiting", f"{len(sales)} opportunities",
             f"{open_tasks} open tasks. Calls, external delivery, payments and acceptance are operator-recorded, not automatically performed.",
             *(f"{s['stage'].replace('_', ' ')}" for s in sales[:5]))
    next_key = "discovery"
    order = ["discovery", "website", "profile", "qualify", "contacts", "verify", "drafts", "approval", "send", "replies", "sales"]
    for priorities in [{"running", "queued"}, {"review", "ready"}, {"failed", "blocked"}, {"paused"}]:
        pending = next((key for key in order if nodes[key]["state"] in priorities), None)
        if pending:
            next_key = pending
            break
    target = None
    if lead_id and profiles and profiles[0]["website_status"] == "website_found":
        crawl = db.one("SELECT report FROM crawls WHERE lead_id=? ORDER BY id DESC LIMIT 1", (lead_id,))
        target = json.loads(crawl["report"]).get("website_lead_id") if crawl else None
    return {"lead_id": lead_id, "scope": leads[0]["company"] if lead_id else "All prospects", "nodes": list(nodes.values()),
            "edges": EDGES, "next_node": next_key, "next_action": "Open matched website prospect" if target else nodes[next_key]["title"],
            "matched_website_lead_id": target, "sending_paused": paused, "context_hold_lead_ids": sorted(context_holds),
            "activity": execution_activity(db, settings, lead_id),
            "attention_count": sum(n["state"] in {"failed", "blocked", "review"} for n in nodes.values()),
            "note": "Live execution state; dragging changes the visual layout, not pipeline rules."}


def execution_activity(db, settings, lead_id=None):
    """Actual durable work, separate from recommended/review workflow stages."""
    where = " WHERE j.state IN ('pending','running')"
    args = ()
    if lead_id:
        where += """ AND (json_extract(j.payload,'$.lead_id')=? OR
                   json_extract(j.payload,'$.contact_id') IN (SELECT id FROM contacts WHERE lead_id=?))"""
        args = (lead_id, lead_id)
    # Active work must not disappear behind a limit on recent completed jobs.
    rows = db.all("""SELECT j.id,j.kind,j.state,j.due_at,j.started_at,j.created_at,
                 json_extract(j.payload,'$.auto_pass') AS auto_pass,
                 COALESCE(json_extract(j.payload,'$.lead_id'),c.lead_id) AS lead_id,
                 l.company FROM jobs j
                 LEFT JOIN contacts c ON c.id=json_extract(j.payload,'$.contact_id')
                 LEFT JOIN leads l ON l.id=COALESCE(json_extract(j.payload,'$.lead_id'),c.lead_id)"""
                 + where, args)
    rows.sort(key=lambda j: (j['state'] != 'running', j['due_at'], j['id']))
    sending = db.one("""SELECT COUNT(*) n FROM messages m JOIN contacts c ON c.id=m.contact_id
                       WHERE m.state='sending'""" + (" AND c.lead_id=?" if lead_id else ""),
                     (lead_id,) if lead_id else ())['n']
    heartbeat = db.get('worker_heartbeat', '0') or '0'
    try:
        heartbeat = float(heartbeat)
    except (TypeError, ValueError):
        heartbeat = 0
    now = time.time()
    return {'running': sum(j['state'] == 'running' for j in rows),
            'queued': sum(j['state'] == 'pending' for j in rows),
            'sending': sending, 'jobs': rows[:12], 'display_limit': 12,
            'worker_enabled': settings.worker_enabled,
            'worker_fresh': settings.worker_enabled and 0 <= now-heartbeat <= 180,
            'worker_heartbeat': heartbeat or None,
            'crawler_runtime': json.loads(db.get('crawler_runtime', '{}')),
            'checked_at': now,
            'note': 'Selected prospect work only; global discovery is shown under All prospects.' if lead_id else
                    'All prospect jobs. Inbox monitoring and scheduled searches run separately.'}
