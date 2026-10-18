import json
import re
import time
import uuid
from zoneinfo import ZoneInfo

from .providers import SERVICES
from .web import crawl_url
from .sales import assert_outreach_open
from .research import assert_contact_ownership, fresh_evidence


OFFERS = {
    "website_build": ("website launch", "a focused website concept", "make your services and inquiry route clearer"),
    "website_improvement": ("website journey", "a short page improvement outline", "make the next step clearer for visitors"),
    "chatbot": ("customer questions", "a small FAQ assistant outline", "give visitors clearer answers and a route to human support"),
    "store_launch": ("online store launch", "a focused store launch outline", "give customers a clear path from products to purchase"),
    "store_improvement": ("shopping journey", "a short shopping journey review", "make product selection and purchase steps clearer"),
    "whatsapp_marketing": ("customer retention", "a permission-based campaign outline", "test relevant repeat-purchase conversations with opted-in customers"),
    "whatsapp_automation": ("customer workflows", "a small WhatsApp workflow outline", "connect eligible customer events to useful messages and human support"),
}

CAMPAIGN_SERVICES = {
    "A": {"website_build", "website_improvement", "chatbot"},
    "B": {"store_launch", "store_improvement", "chatbot", "whatsapp_marketing", "whatsapp_automation"},
}
FOLLOWUP_IDEAS = {
    "website_build": "Start with one primary page, a clear description of the service and one inquiry route; agree on the success metric before expanding the site.",
    "website_improvement": "Check whether a first-time visitor can explain the offer and identify the next step; compare inquiry quality before and after a small change.",
    "chatbot": "Start with a narrow set of questions from approved content, a clear human handoff and a way to review incorrect or unanswered responses.",
    "store_launch": "Pilot a small product range first, with clear delivery, returns and support information alongside the purchase journey.",
    "store_improvement": "Review one product-to-purchase journey first and agree which completion and support metrics to compare before expanding the work.",
    "whatsapp_marketing": "Start with one customer segment, confirm permission and opt-out handling, and compare incremental results with a suitable control group.",
    "whatsapp_automation": "Pilot one eligible customer event, confirm permission and message requirements, and include a human support handoff before adding more workflows.",
}


def context(db, contact_id):
    contact = db.one("SELECT * FROM contacts WHERE id=?", (contact_id,))
    if not contact:
        raise ValueError("Contact not found")
    lead = db.one("SELECT * FROM leads WHERE id=?", (contact["lead_id"],))
    return contact, lead


def review_lead(db, lead_id, review, *, expected_lead=None, expected_contacts=None, review_method='operator'):
    from .profiles import source_allowed
    lead = db.one("SELECT * FROM leads WHERE id=?", (lead_id,))
    if not lead:
        raise ValueError("Lead not found")
    if lead.get('lead_kind') != 'profile':
        from .discovery import official_root
        official_root(lead['website'])
    if lead["status"] == "researching":
        raise ValueError("Research is still running; review complete or explicitly partial evidence after it finishes")
    if db.one("SELECT id FROM contacts WHERE lead_id=? AND status IN ('active','replied','hold','closed')", (lead_id,)):
        raise ValueError("Outreach has started; do not overwrite its reviewed evidence")
    if review["country"] not in {"US", "UK"}:
        raise ValueError("Only US and UK are in scope")
    ZoneInfo(review["timezone"])
    if review["country"] == "UK" and review["timezone"] != "Europe/London":
        raise ValueError("Use Europe/London for UK contacts")
    if review["country"] == "US" and review["timezone"] not in {
        "America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles",
        "America/Phoenix", "America/Anchorage", "Pacific/Honolulu"
    }:
        raise ValueError("Select the prospect's US timezone")
    source = crawl_url(review["country_source"])
    if not source_allowed(lead, source):
        raise ValueError("Country evidence must be on the official company website")
    from .social_research import is_social_evidence
    available = [p for p in fresh_evidence(db,lead_id) if source_allowed(lead,p['url']) or is_social_evidence(db, lead_id, p)]
    by_id = {e["id"]: e for e in available}
    country_evidence = next((e for e in available if crawl_url(e["url"]) == source), None)
    country_quote = review.get("country_quote", "").strip()
    if not country_evidence or len(country_quote) < 3 or country_quote not in country_evidence["text"]:
        raise ValueError("Country quote must match a saved official website page at the country source URL")
    if review["service"] not in SERVICES:
        raise ValueError("Choose a supported service")
    if review["service"] not in CAMPAIGN_SERVICES[lead["campaign"]]:
        raise ValueError(f"Unsupported offer for Campaign {lead['campaign']}")
    if review["service"].startswith("whatsapp_") and len(review.get("channel_fit_notes", "").strip()) < 20:
        raise ValueError("Record WhatsApp channel fit, what is observed and what still needs qualification")
    evidence = by_id.get(review["evidence_id"])
    if not evidence or not source_allowed(lead, evidence['url']) or review["quote"] not in evidence["text"] or len(review["quote"]) < 8:
        raise ValueError("Quote must match saved evidence for this lead")
    for field in ["observation", "suggestion", "fit_notes"]:
        if len(review[field].strip()) < 12:
            raise ValueError(f"Provide a specific {field}")
    finding = {k: review[k] for k in ["evidence_id", "quote", "observation", "suggestion", "service"]}
    reviewed_sources = {e["id"]: e["sha256"] for e in (country_evidence, evidence)}
    from .offers import review_context
    offer_context, commerce_sources = review_context(lead, review, by_id)
    finding['offer_context'] = offer_context
    reviewed_sources.update(commerce_sources)
    finding.update(country_quote=country_quote, industry=review.get("industry", "").strip(),
                   channel_fit_notes=review.get("channel_fit_notes", "").strip())
    profile_review = None
    if lead.get("lead_kind") == "profile":
        if lead["website_status"] != "website_not_found":
            raise ValueError("Profile needs a completed website search with no matched website; found/ambiguous/unavailable results stay held")
        ownership = review.get("profile_ownership_notes", "").strip()
        activity = review.get("profile_activity_quote", "").strip()
        search_notes = review.get("website_search_notes", "").strip()
        if (not review.get("website_search_reviewed") or len(ownership) < 30 or len(search_notes) < 30
                or len(activity) < 8 or activity not in evidence["text"] or not source_allowed(lead, evidence["url"])):
            raise ValueError("Review profile ownership, quote business activity and acknowledge website-search limitations")
        allowed = {"website_build", "chatbot"} if lead["campaign"] == "A" else {"store_launch", "chatbot"}
        if review["service"] not in allowed:
            raise ValueError("Profile-only prospects need website/store launch or a sourced customer-question offer")
        profile_review = {"evidence_id": evidence["id"], "evidence_sha256": evidence["sha256"],
                          "ownership_notes": ownership, "activity_quote": activity, "website_search_notes": search_notes,
                          "reviewed_at": time.time()}
        finding.update(profile_only=True, website_status="website_not_found",
                       website_search_note="I couldn't find a dedicated website linked from the profile or in our search; please correct me if I missed it.")
    trigger = review.get("recent_trigger", "").strip()
    if trigger:
        trigger_evidence = by_id.get(review.get("trigger_evidence_id"))
        trigger_quote = review.get("trigger_quote", "").strip()
        if not trigger_evidence or len(trigger_quote) < 8 or trigger_quote not in trigger_evidence["text"]:
            raise ValueError("Recent trigger requires an exact quote from saved evidence")
        finding["trigger"] = {"description": trigger, "quote": trigger_quote,
                              "evidence_id": trigger_evidence["id"], "url": trigger_evidence["url"]}
        reviewed_sources[trigger_evidence["id"]] = trigger_evidence["sha256"]
    elif review.get("trigger_quote") or review.get("trigger_evidence_id"):
        raise ValueError("Provide the trigger description or clear its evidence fields")
    followup = review.get("followup_suggestion", "").strip()
    if followup:
        followup_evidence = by_id.get(review.get("followup_evidence_id"))
        followup_quote = review.get("followup_quote", "").strip()
        if not followup_evidence or len(followup_quote) < 8 or followup_quote not in followup_evidence["text"]:
            raise ValueError("Extra follow-up idea requires an exact quote from saved evidence")
        if followup.casefold() == review["suggestion"].strip().casefold():
            raise ValueError("Extra follow-up idea must add value beyond the first suggestion")
        finding["followup"] = {"suggestion": followup, "quote": followup_quote,
                               "evidence_id": followup_evidence["id"], "url": followup_evidence["url"]}
        reviewed_sources[followup_evidence["id"]] = followup_evidence["sha256"]
    elif review.get("followup_quote") or review.get("followup_evidence_id"):
        raise ValueError("Provide the follow-up suggestion or clear its evidence fields")
    finding["review_required"] = False
    finding['qualification_method'] = review_method
    finding['final_message_review_required'] = True
    with db.connect() as con:
        con.execute("BEGIN IMMEDIATE")
        if expected_lead is not None:
            current = dict(con.execute('SELECT * FROM leads WHERE id=?', (lead_id,)).fetchone())
            contacts_now = [dict(c) for c in con.execute('SELECT * FROM contacts WHERE lead_id=? ORDER BY id', (lead_id,))]
            if (current != expected_lead or contacts_now != expected_contacts or
                    con.execute('SELECT 1 FROM messages m JOIN contacts c ON c.id=m.contact_id WHERE c.lead_id=?', (lead_id,)).fetchone() or
                    con.execute("SELECT 1 FROM jobs WHERE kind IN ('research','contact_research','professional_research','social_research') AND state IN ('pending','running') AND json_extract(payload,'$.lead_id')=?", (lead_id,)).fetchone()):
                raise ValueError('Research, contact or drafts changed during preparation; existing work preserved')
        if con.execute("SELECT id FROM contacts WHERE lead_id=? AND status IN ('active','replied','hold','closed')", (lead_id,)).fetchone():
            raise ValueError("Outreach started during review; preserve its evidence")
        if con.execute("SELECT status FROM leads WHERE id=?", (lead_id,)).fetchone()[0] == "researching":
            raise ValueError("Research is still running")
        if profile_review:
            current_lead = dict(con.execute("SELECT * FROM leads WHERE id=?", (lead_id,)).fetchone())
            if current_lead["website_status"] != "website_not_found":
                raise ValueError("Website-search status changed during review")
            con.execute("UPDATE leads SET profile_review=? WHERE id=?", (json.dumps(profile_review), lead_id))
        for eid, digest in reviewed_sources.items():
            current = con.execute("""SELECT e.sha256 FROM evidence e WHERE e.id=? AND e.lead_id=?
                AND e.fetched_at >= COALESCE((SELECT created_at FROM crawls WHERE lead_id=e.lead_id ORDER BY id DESC LIMIT 1),0)
                AND e.fetched_at BETWEEN ? AND ?""",
                                  (eid, lead_id, time.time()-30*86400, time.time()+60)).fetchone()
            if not current or current[0] != digest:
                raise ValueError("Source changed during review; reload current research before qualifying")
        con.execute("UPDATE leads SET company=?,country=?,country_source=?,timezone=?,business_type=?,service=?,fit_notes=?,findings=?,status='qualified',updated_at=? WHERE id=?",
                    (review["company"], review["country"], source, review["timezone"], review["business_type"],
                     review["service"], review["fit_notes"], json.dumps([finding]), time.time(), lead_id))
        # A changed research review invalidates all unsent drafts for this company.
        con.execute("DELETE FROM messages WHERE contact_id IN (SELECT id FROM contacts WHERE lead_id=?) AND state='draft'", (lead_id,))
    db.event("lead_reviewed", {"lead_id": lead_id, "service": review["service"], 'method': review_method})


def draft_sequence(company, service, finding, source_url, recipient_name=""):
    """Offline illustrative preview only. Never the live email-writing fallback."""
    topic, offer, benefit = OFFERS[service]
    greeting = "Hi " + (recipient_name.split()[0] if recipient_name.strip() else company + " team") + ","
    trigger = finding.get("trigger", {})
    intro = f"I came across {company} after seeing this announcement: {trigger['description']}\n{trigger['url']}\n" if trigger else f"I was looking at this page from {company}: {source_url}\n"
    if finding.get("profile_only"):
        intro = f"I found {company} through this business profile: {source_url}\n"
        intro += finding["website_search_note"] + "\n"
    first = (f"{greeting}\n\n{intro}{finding['observation']}\n\n"
             f"I help businesses {benefit}. One idea worth exploring: {finding['suggestion']}\n\n"
             f"Would it be useful if I sent {offer} specific to your business?")
    followup = finding.get("followup", {})
    extra = followup.get("suggestion") or FOLLOWUP_IDEAS[service]
    bodies = [first,
              f"{greeting}\n\nOne extra thought: {extra}\n\nWould a short outline help your team assess whether this is worth testing?",
              f"{greeting}\n\nIf your team is reviewing {topic}, I could put together {offer} around the page I mentioned.\n\nWould that be useful, or is another area more important right now?",
              f"{greeting}\n\nI'll close the loop here. If your team prioritizes {topic} later, feel free to reply.\n\nAll the best."]
    subject = f"An idea for {company}"[:150]
    evidence_ids = sorted({finding["evidence_id"], *([trigger["evidence_id"]] if trigger else []),
                           *([followup["evidence_id"]] if followup else [])})
    return [{"step": step, "subject": subject if step == 0 else "Re: " + subject,
             "body": body, "evidence_ids": evidence_ids} for step, body in enumerate(bodies)]


def create_drafts(db, settings, contact_id, *, cancelled=lambda: False, preserve_existing=False):
    contact, lead = context(db, contact_id)
    assert_contact_ownership(db, contact, lead)
    if lead['status'] != 'qualified':
        raise ValueError('Research qualification is pending. Use Prepare emails, or review one source-backed offer in section 02.')
    if contact["status"] in {"suppressed", "active", "replied", "hold", "closed"}:
        raise ValueError('Existing outreach/contact status cannot be overwritten; review its history first')
    from .offers import selected_offer
    if not selected_offer(db, lead):
        raise ValueError('Review current source evidence and one Campaign A/B offer before drafting')
    if db.one("SELECT id FROM messages WHERE contact_id=? AND state<>'draft'", (contact_id,)):
        raise ValueError("Sequence has already been activated")
    finding = json.loads(lead["findings"])[0]
    evidence = db.one("SELECT url FROM evidence WHERE id=? AND lead_id=?", (finding["evidence_id"], lead["id"]))
    if not evidence:
        raise ValueError("Reviewed source is unavailable; qualify again")
    from . import email_writer
    source_ids = {finding['evidence_id']}
    available = fresh_evidence(db, lead['id'])
    country_page = next((e for e in available if crawl_url(e['url']) == crawl_url(lead['country_source'])), None)
    if not country_page:
        raise ValueError('Reviewed writing sources are not current; qualify again')
    source_ids.add(country_page['id'])
    commerce = finding.get('offer_context', {}).get('commerce_evidence_id')
    if commerce:
        source_ids.add(commerce)
    for part in ('trigger', 'followup'):
        if finding.get(part):
            source_ids.add(finding[part]['evidence_id'])
    sources = [e for e in available if e['id'] in source_ids]
    if source_ids != {e['id'] for e in sources}:
        raise ValueError('Reviewed writing sources are not current; qualify again')
    previous_messages = db.all('SELECT * FROM messages WHERE contact_id=? ORDER BY step', (contact_id,))
    if not settings.followups_enabled and any(m['step'] > 0 for m in previous_messages):
        raise ValueError('Archive previous follow-up drafts before regenerating the initial email')
    if preserve_existing and previous_messages:
        raise ValueError('New messages appeared during automatic preparation; existing copy preserved')
    writer_configuration = (settings.draft_api_url, settings.draft_api_key, settings.draft_model, settings.draft_timeout_seconds)

    def assert_unchanged(reader):
        if cancelled():
            raise ValueError('Preparation cancelled; no new copy will be saved')
        from .sequence import Reader
        current = reader if hasattr(reader, 'all') else Reader(reader)
        if writer_configuration != (settings.draft_api_url, settings.draft_api_key, settings.draft_model, settings.draft_timeout_seconds):
            raise ValueError('AI writing configuration changed during generation; result discarded')
        if (current.one('SELECT * FROM contacts WHERE id=?', (contact_id,)) != contact
                or current.one('SELECT * FROM leads WHERE id=?', (lead['id'],)) != lead
                or current.all('SELECT * FROM messages WHERE contact_id=? ORDER BY step', (contact_id,)) != previous_messages
                or [e for e in fresh_evidence(current, lead['id']) if e['id'] in source_ids] != sources):
            raise ValueError('Contact, research or drafts changed during AI writing; result discarded')
        assert_contact_ownership(current, contact, lead)
        if not selected_offer(current, lead):
            raise ValueError('Current research review changed during AI writing')
        if current.one('SELECT 1 FROM suppression WHERE email=?', (contact['email'],)):
            raise ValueError('Contact suppressed during AI writing')
        if not hasattr(reader, 'all'):
            assert_outreach_open(reader, lead['id'])
        else:
            with db.connect() as check:
                assert_outreach_open(check, lead['id'])

    generated = email_writer.generate_sequence(settings, lead, contact, finding, sources,
                                               before_request=lambda: assert_unchanged(db))
    drafts = generated['messages']
    domain = settings.sender_email.split("@")[-1] if "@" in settings.sender_email else "outreach.invalid"
    with db.connect() as con:
        con.execute("BEGIN IMMEDIATE")
        assert_unchanged(con)
        current_contact = con.execute("SELECT status FROM contacts WHERE id=?", (contact_id,)).fetchone()
        current_lead = con.execute("SELECT status,findings FROM leads WHERE id=?", (lead["id"],)).fetchone()
        if current_contact["status"] != "new" or current_lead["status"] != "qualified" or current_lead["findings"] != lead["findings"]:
            raise ValueError("Contact or qualification changed; reload before creating drafts")
        from .sequence import Reader
        if not selected_offer(Reader(con), lead):
            raise ValueError('Review current source evidence and offer context before drafting')
        if con.execute("SELECT id FROM messages WHERE contact_id=? AND state<>'draft'", (contact_id,)).fetchone():
            raise ValueError("Sequence has already been activated")
        for draft in drafts:
            con.execute("INSERT INTO messages(contact_id,step,subject,body,evidence_ids,message_id) VALUES(?,?,?,?,?,?) ON CONFLICT(contact_id,step) DO UPDATE SET subject=excluded.subject,body=excluded.body,evidence_ids=excluded.evidence_ids",
                        (contact_id, draft["step"], draft["subject"], draft["body"],
                         json.dumps(draft["evidence_ids"]), f"<{uuid.uuid4().hex}@{domain}>"))
        message_ids = [r[0] for r in con.execute('SELECT id FROM messages WHERE contact_id=? ORDER BY step', (contact_id,))]
        con.execute("INSERT INTO events(kind,detail,contact_id,created_at) VALUES('drafts_created',?,?,?)",
                    (json.dumps({**generated['provenance'], 'steps': len(drafts), 'message_ids': message_ids}), contact_id, time.time()))


def approve(db, settings, contact_id, basis, contact_relevance):
    contact, lead = context(db, contact_id)
    assert_contact_ownership(db, contact, lead)
    if contact["status"] in {"suppressed", "replied", "active", "hold", "closed"}:
        raise ValueError("Contact is not eligible for a new sequence")
    if db.one("SELECT 1 FROM suppression WHERE email=?", (contact["email"],)):
        raise ValueError("Address is suppressed")
    if lead["status"] != "qualified" or not lead["country"] or not lead["timezone"]:
        raise ValueError("Company qualification is incomplete")
    findings = json.loads(lead["findings"])
    if not findings or not findings[0].get("country_quote"):
        raise ValueError("Qualification needs a saved country quote; review this company again")
    if lead["service"] not in CAMPAIGN_SERVICES[lead["campaign"]]:
        raise ValueError("Review the campaign's supported offer again")
    from .offers import selected_offer
    if not selected_offer(db, lead):
        raise ValueError('Review current source evidence and offer context before approval')
    if lead["service"].startswith("whatsapp_") and len(findings[0].get("channel_fit_notes", "")) < 20:
        raise ValueError("Review WhatsApp channel fit and qualification questions again")
    if (contact["verification"] != "safe" or not contact["verified_at"]
            or time.time() - contact["verified_at"] > settings.verification_max_age_hours * 3600):
        raise ValueError("Fresh safe Reacher result required")
    if len(basis.strip()) < 20 or len(contact_relevance.strip()) < 12:
        raise ValueError("Record outreach eligibility and why this contact is relevant")
    if not all([settings.sender_name, settings.sender_company, settings.sender_email, settings.postal_address]):
        raise ValueError("Configure real sender identity and postal address before approval")
    messages = db.all("SELECT * FROM messages WHERE contact_id=? ORDER BY step", (contact_id,))
    expected_steps = list(range(4 if settings.followups_enabled else 1))
    if [m['step'] for m in messages] != expected_steps or any(m["state"] != "draft" for m in messages):
        raise ValueError("Review the initial email before approving; archive legacy follow-ups first in single-email mode")
    from .email_writer import assert_ai_origin
    assert_ai_origin(db, contact_id)
    if any(re.search(r"\[(?:your|first|company|specific)[^\]]*\]|\{\{", m["body"], re.I) for m in messages):
        raise ValueError("Replace unresolved template placeholders")
    with db.connect() as con:
        con.execute("BEGIN IMMEDIATE")
        current_contact = con.execute("SELECT * FROM contacts WHERE id=?", (contact_id,)).fetchone()
        current_lead = con.execute("SELECT * FROM leads WHERE id=?", (lead["id"],)).fetchone()
        assert_contact_ownership(db, dict(current_contact), dict(current_lead))
        current_messages = [dict(m) for m in con.execute("SELECT * FROM messages WHERE contact_id=? ORDER BY step", (contact_id,))]
        assert_outreach_open(con, lead["id"])
        if (current_contact["status"] != "new" or current_contact["verification"] != "safe"
                or current_contact["verified_at"] != contact["verified_at"]
                or current_lead["status"] != "qualified" or current_lead["findings"] != lead["findings"]
                or current_messages != messages
                or con.execute("SELECT 1 FROM suppression WHERE email=?", (contact["email"],)).fetchone()):
            raise ValueError("Contact, evidence or drafts changed during approval; reload and review again")
        other = con.execute("SELECT id FROM contacts WHERE lead_id=? AND id<>? AND status IN ('active','replied','hold')",
                            (lead["id"], contact_id)).fetchone()
        if other:
            raise ValueError("Another contact at this company already has an active conversation")
        from .sequence import capture
        review_snapshot = capture(con, settings, dict(current_lead), dict(current_contact))
        con.execute("UPDATE contacts SET status='active',eligibility_basis=?,reviewed_at=? WHERE id=?",
                    (basis + "\nContact relevance: " + contact_relevance, time.time(), contact_id))
        # Only the first step has a due date; subsequent steps are scheduled relative to actual acceptance.
        con.execute("UPDATE messages SET state='queued',due_at=NULL WHERE contact_id=?", (contact_id,))
        con.execute("UPDATE messages SET due_at=? WHERE contact_id=? AND step=0", (time.time(), contact_id))
        # Freeze the outreach context with approval, so later labels cannot rewrite campaign learning.
        con.execute("INSERT INTO events(kind,contact_id,detail,created_at) VALUES(?,?,?,?)",
                    ("sequence_approved", contact_id, json.dumps({"basis": basis, "contact_relevance": contact_relevance,
                     "review_snapshot": review_snapshot,
                     "context": {"lead_id": lead['id'], "campaign": lead['campaign'], "country": lead['country'],
                                 "service": lead['service'], "industry": findings[0].get('industry', ''),
                                 "prospect_kind": lead.get('lead_kind', 'website')}}), time.time()))


def resume_contact(db, settings, contact_id, note, next_at):
    contact, lead = context(db, contact_id)
    assert_contact_ownership(db, contact, lead)
    if contact["status"] != "hold" or db.one("SELECT 1 FROM suppression WHERE email=?", (contact["email"],)):
        raise ValueError("Only held, unsuppressed contacts may resume; replied or closed conversations stay stopped")
    if db.one("SELECT id FROM messages WHERE contact_id=? AND state='uncertain'", (contact_id,)):
        raise ValueError("Reconcile uncertain sends first")
    if (not contact["reviewed_at"] or contact["verification"] != "safe" or not contact["verified_at"]
            or time.time() - contact["verified_at"] > settings.verification_max_age_hours * 3600):
        raise ValueError("Previous sequence approval and a fresh safe verification are required")
    if next_at < time.time() or len(note.strip()) < 20:
        raise ValueError("Choose a future time and explain why outreach can resume")
    with db.connect() as con:
        con.execute("BEGIN IMMEDIATE")
        current = con.execute("SELECT * FROM contacts WHERE id=?", (contact_id,)).fetchone()
        assert_outreach_open(con, lead["id"])
        from .sequence import assert_approved
        current_lead = con.execute('SELECT * FROM leads WHERE id=?', (lead['id'],)).fetchone()
        assert_approved(con, settings, dict(current_lead), dict(current))
        if (current["status"] != "hold" or current["verification"] != "safe"
                or current["verified_at"] != contact["verified_at"]
                or con.execute("SELECT 1 FROM suppression WHERE email=?", (contact["email"],)).fetchone()
                or con.execute("SELECT 1 FROM messages WHERE contact_id=? AND state='uncertain'", (contact_id,)).fetchone()):
            raise ValueError("Contact changed during resume; reload and review its conversation")
        pending = con.execute("SELECT * FROM messages WHERE contact_id=? AND state IN ('draft','queued','cancelled') ORDER BY step", (contact_id,)).fetchall()
        if not pending:
            raise ValueError("No remaining sequence steps")
        con.execute("UPDATE contacts SET status='active' WHERE id=? AND status='hold'", (contact_id,))
        for row in pending:
            con.execute("UPDATE messages SET state='queued',due_at=? WHERE id=?", (next_at if row['id'] == pending[0]['id'] else None, row['id']))
    db.event("contact_resumed", {"reason": note, "next_at": next_at}, contact_id)


def archive_followups(db, contact_id):
    """Retain edited initial copy and preserve unapproved follow-ups in the audit log."""
    with db.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        contact = con.execute('SELECT * FROM contacts WHERE id=?', (contact_id,)).fetchone()
        if not contact or contact['status'] != 'new' or contact['reviewed_at']:
            raise ValueError('Only an unapproved contact can switch to one initial email')
        messages = [dict(m) for m in con.execute('SELECT * FROM messages WHERE contact_id=? ORDER BY step', (contact_id,))]
        if not messages or messages[0]['step'] != 0 or any(m['state'] != 'draft' or m['sent_at'] or m['due_at'] for m in messages):
            raise ValueError('Submitted, approved or scheduled messages cannot be archived here')
        archived = [m for m in messages if m['step'] > 0]
        if not archived:
            return {'archived': 0, 'retained_message_id': messages[0]['id']}
        row = con.execute("SELECT detail FROM events WHERE kind='drafts_created' AND contact_id=? ORDER BY id DESC LIMIT 1", (contact_id,)).fetchone()
        origin = json.loads(row[0]) if row else {}
        con.execute('INSERT INTO events(kind,contact_id,detail,created_at) VALUES(?,?,?,?)',
                    ('followup_drafts_archived', contact_id, json.dumps({'messages': archived, 'retained_message_id': messages[0]['id']}), time.time()))
        con.execute('DELETE FROM messages WHERE contact_id=? AND step>0', (contact_id,))
        if origin.get('method') == 'research_ai' and origin.get('message_ids') == [m['id'] for m in messages]:
            origin.update(steps=1, message_ids=[messages[0]['id']], support=origin.get('support', [])[:1],
                          migration='retained_initial_email; followups preserved in archive event')
            con.execute('INSERT INTO events(kind,contact_id,detail,created_at) VALUES(?,?,?,?)',
                        ('drafts_created', contact_id, json.dumps(origin), time.time()))
    return {'archived': len(archived), 'retained_message_id': messages[0]['id']}


def revise_unsent_sequence(db, contact_id, note):
    """Revoke an unsubmitted pilot approval so evidence/copy can be reviewed again."""
    if len(note.strip()) < 20:
        raise ValueError('Explain why the unsent pilot needs another review')
    with db.connect() as con:
        con.execute('BEGIN IMMEDIATE')
        contact = con.execute('SELECT * FROM contacts WHERE id=?', (contact_id,)).fetchone()
        if not contact or contact['status'] not in {'active', 'hold'}:
            raise ValueError('Only an active or held unsent pilot can return to review')
        assert_outreach_open(con, contact['lead_id'])
        if con.execute('SELECT 1 FROM suppression WHERE email=?', (contact['email'],)).fetchone():
            raise ValueError('Suppressed contacts stay stopped')
        messages = [dict(m) for m in con.execute('SELECT * FROM messages WHERE contact_id=? ORDER BY step', (contact_id,))]
        if [m['step'] for m in messages] not in ([0], [0, 1, 2, 3]) or any(m['sent_at'] or m['state'] not in {'draft', 'queued', 'cancelled'} for m in messages):
            raise ValueError('Submitted, uncertain or failed messages require delivery/conversation review; they cannot reset')
        con.execute('INSERT INTO events(kind,contact_id,detail,created_at) VALUES(?,?,?,?)',
                    ('sequence_returned_to_review', contact_id, json.dumps({'reason': note, 'previous_messages': messages}), time.time()))
        con.execute("UPDATE messages SET state='draft',due_at=NULL,error='' WHERE contact_id=?", (contact_id,))
        con.execute("UPDATE contacts SET status='new',reviewed_at=NULL,eligibility_basis='' WHERE id=?", (contact_id,))
