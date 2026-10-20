import json
import smtplib
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from outreach.campaigns import approve, create_drafts, review_lead
from outreach.mail import record_inbound, send_one
from outreach.research import discover_leads
from test_campaigns_mail import inbound, ready


def review_payload(db, prepared):
    lead = db.one("SELECT * FROM leads WHERE id=?", (prepared["lead_id"],))
    finding = json.loads(lead["findings"])[0]
    return {**{key: lead[key] for key in ["company", "country", "country_source", "timezone", "business_type", "service", "fit_notes"]},
            **{key: finding[key] for key in ["evidence_id", "quote", "observation", "suggestion", "country_quote"]}}


@pytest.mark.parametrize("bad", [{"country_source": "https://bright-demo.com/unknown"},
                                {"country_quote": "We are based in Australia"}])
def test_country_evidence_must_match_saved_source(db, prepared, bad):
    with pytest.raises(ValueError, match="Country quote"):
        review_lead(db, prepared["lead_id"], {**review_payload(db, prepared), **bad})


def test_campaign_b_rejects_non_d2c_website_offer(db, prepared):
    db.execute("UPDATE leads SET campaign='B',campaign_id=(SELECT id FROM campaign_groups WHERE goal='B' AND is_default=1) WHERE id=?", (prepared["lead_id"],))
    with pytest.raises(ValueError, match="Campaign B"):
        review_lead(db, prepared["lead_id"], review_payload(db, prepared))


def test_whatsapp_requires_recorded_channel_fit(db, prepared):
    db.execute("UPDATE leads SET campaign='B',campaign_id=(SELECT id FROM campaign_groups WHERE goal='B' AND is_default=1) WHERE id=?", (prepared["lead_id"],))
    review = {**review_payload(db, prepared), "service": "whatsapp_automation"}
    with pytest.raises(ValueError, match="WhatsApp channel fit"):
        review_lead(db, prepared["lead_id"], review)
    review["channel_fit_notes"] = "Channel signal not yet confirmed; qualify relevance and customer permissions before a pilot."
    db.execute('UPDATE evidence SET text=text || ? WHERE id=?', (' We sell our own products online to consumers.', prepared['evidence_id']))
    review.update(selling_stage='selling_online', commerce_evidence_id=prepared['evidence_id'],
                  commerce_quote='We sell our own products online to consumers.',
                  d2c_fit_notes='Fictional consumer-product store ownership and selling process reviewed.')
    review_lead(db, prepared["lead_id"], review)
    assert json.loads(db.one("SELECT findings FROM leads")["findings"])[0]["channel_fit_notes"]


def test_sourced_trigger_and_extra_value_survive_into_drafts(db, settings, prepared):
    eid = db.execute("INSERT INTO evidence(lead_id,url,title,text,sha256,fetched_at) VALUES(?,?,?,?,?,?)",
                     (prepared["lead_id"], "https://bright-demo.com/news", "Launch announcement",
                      "We launched a new consulting service on 9 October 2026. The service offers a dedicated consultation.", "fixture", time.time()))
    review = {**review_payload(db, prepared), "industry": "Consulting", "recent_trigger": "your new consulting service launch on 9 October 2026",
              "trigger_evidence_id": eid, "trigger_quote": "We launched a new consulting service on 9 October 2026.",
              "followup_evidence_id": eid, "followup_quote": "The service offers a dedicated consultation.",
              "followup_suggestion": "Explain who the dedicated consultation is for before the inquiry link."}
    review_lead(db, prepared["lead_id"], review)
    create_drafts(db, settings, prepared["contact_id"])
    messages = db.all("SELECT * FROM messages ORDER BY step")
    assert review["recent_trigger"] in messages[0]["body"]
    assert "https://bright-demo.com/news" in messages[0]["body"]
    assert review["followup_suggestion"] in messages[1]["body"]
    assert review["suggestion"] not in messages[1]["body"]
    assert eid in json.loads(messages[0]["evidence_ids"])


@pytest.mark.parametrize("field", ["trigger_quote", "followup_quote"])
def test_unsourced_optional_claims_are_rejected(db, prepared, field):
    review = review_payload(db, prepared)
    if field == "trigger_quote":
        review.update(recent_trigger="An invented launch announcement", trigger_evidence_id=prepared["evidence_id"], trigger_quote="Invented announcement")
    else:
        review.update(followup_suggestion="A specific additional improvement idea", followup_evidence_id=prepared["evidence_id"], followup_quote="Invented feature")
    with pytest.raises(ValueError, match="exact quote"):
        review_lead(db, prepared["lead_id"], review)


def test_default_followup_adds_new_value(db, prepared):
    messages = db.all("SELECT body FROM messages ORDER BY step")
    assert "Test a clearer explanation" not in messages[1]["body"]
    assert "compare inquiry quality" in messages[1]["body"]


@pytest.mark.parametrize("stale_part", ["country", "observation", "trigger", "followup"])
def test_review_rejects_sources_not_refreshed_in_latest_crawl(db, prepared, stale_part):
    review = review_payload(db, prepared)
    old = db.one("SELECT * FROM evidence WHERE id=?", (prepared["evidence_id"],))
    started = time.time()
    db.execute("INSERT INTO crawls(lead_id,report,created_at) VALUES(?,?,?)",
               (prepared["lead_id"], '{"status":"partial"}', started))
    fresh = db.execute("INSERT INTO evidence(lead_id,url,title,text,sha256,fetched_at) VALUES(?,?,?,?,?,?)",
                       (prepared["lead_id"], "https://bright-demo.com/current", "Current page", old["text"], "current", started + 1))
    if stale_part != "country":
        review["country_source"] = "https://bright-demo.com/current"
    if stale_part != "observation":
        review["evidence_id"] = fresh
    if stale_part == "trigger":
        review.update(recent_trigger="A launch mentioned on the earlier saved page",
                      trigger_evidence_id=old["id"], trigger_quote=review["quote"])
    if stale_part == "followup":
        review.update(followup_suggestion="Explain consultation preparation before visitors make an inquiry.",
                      followup_evidence_id=old["id"], followup_quote=review["quote"])
    with pytest.raises(ValueError):
        review_lead(db, prepared["lead_id"], review)
    assert db.one("SELECT COUNT(*) n FROM evidence")["n"] == 2


def test_review_cannot_commit_historical_snapshot_after_recrawl_finishes(db, prepared, monkeypatch):
    review = review_payload(db, prepared)
    original = db.all
    changed = False
    def snapshot(sql, params=()):
        nonlocal changed
        rows = original(sql, params)
        if not changed and sql.startswith("SELECT e.* FROM evidence e"):
            changed = True
            db.execute("INSERT INTO crawls(lead_id,report,created_at) VALUES(?,?,?)",
                       (prepared["lead_id"], '{"status":"partial"}', time.time()))
            db.execute("UPDATE leads SET status='review' WHERE id=?", (prepared["lead_id"],))
        return rows
    monkeypatch.setattr(db, "all", snapshot)
    with pytest.raises(ValueError, match="Source changed"):
        review_lead(db, prepared["lead_id"], review)
    assert db.one("SELECT status FROM leads WHERE id=?", (prepared["lead_id"],))["status"] == "review"
    assert db.one("SELECT COUNT(*) n FROM messages")["n"] == 4


@pytest.mark.parametrize("stopped", ["replied", "suppressed"])
def test_temporary_smtp_failure_cannot_overwrite_concurrent_stop(db, settings, active, stopped):
    def refusal(*args):
        if stopped == "suppressed":
            db.suppress("alex@bright-demo.com", "Operator received opt-out during SMTP attempt")
        else:
            record_inbound(db, inbound(db, "Yes, please send it"), "concurrent-reply")
        raise smtplib.SMTPRecipientsRefused({"alex@bright-demo.com": (450, b"Try later")})
    assert send_one(db, settings, ready(db, active["contact_id"]), refusal) == "failed"
    assert db.one("SELECT status FROM contacts")["status"] == stopped


@pytest.mark.parametrize("stopped", ["replied", "suppressed"])
def test_recovery_preserves_stop_status_during_inflight_send(db, active, stopped):
    db.execute("UPDATE messages SET state='sending' WHERE step=0")
    db.execute("UPDATE contacts SET status=?", (stopped,))
    db.recover()
    assert db.one("SELECT status FROM contacts")["status"] == stopped
    assert db.one("SELECT state FROM messages WHERE step=0")["state"] == "uncertain"


def test_late_auto_reply_cannot_reopen_human_conversation(db, active):
    record_inbound(db, inbound(db, "Please send the audit"), "human-reply")
    record_inbound(db, inbound(db, "Away from office", automatic=True), "late-auto")
    assert db.one("SELECT status FROM contacts")["status"] == "replied"


async def test_platform_only_search_results_are_retained_as_unqualified_profiles(db, settings, monkeypatch):
    settings.discovery_query_delay_seconds = .1
    async def platform_results(*args, **kwargs):
        return [{"url": "https://linkedin.com/company/fictional", "title": "Company profile", "snippet": "UK consulting business"}]
    async def denied(*args, **kwargs):
        return {"state": "robots_denied"}
    monkeypatch.setattr("outreach.providers.discover", platform_results)
    monkeypatch.setattr("outreach.discovery.public_snapshot", denied)
    await discover_leads(db, settings, "UK consulting business", "A", "UK", 10)
    lead = db.one("SELECT * FROM leads")
    assert lead["lead_kind"] == "profile" and lead["website"] == "" and lead["status"] == "new"
    assert not db.all("SELECT * FROM contacts")


def test_old_qualification_cannot_skip_new_country_review(db, settings, prepared):
    finding = json.loads(db.one("SELECT findings FROM leads")["findings"])[0]
    finding.pop("country_quote")
    db.execute("UPDATE leads SET findings=?", (json.dumps([finding]),))
    with pytest.raises(ValueError, match="saved country quote"):
        approve(db, settings, prepared["contact_id"], "Reviewed applicable business outreach eligibility", "Founder owns this website")


async def test_search_filters_platforms_before_company_limit(settings, monkeypatch):
    import httpx
    from outreach.providers import discover
    async def get(*args, **kwargs):
        return httpx.Response(200, request=httpx.Request("GET", "https://search.example.com/search"),
                              json={"results": [{"url": "https://linkedin.com/company/example", "title": "Profile"},
                                                {"url": "https://bright-demo.com", "title": "Official company"}]})
    monkeypatch.setattr("httpx.AsyncClient.get", get)
    rows = await discover(settings, "UK consulting", limit=1)
    assert len(rows) == 1 and rows[0]["url"] == "https://bright-demo.com/"


def test_two_concurrent_approvals_cannot_activate_twice(db, settings, prepared, monkeypatch):
    barrier = Barrier(2)
    original_all = db.all
    def snapshot(sql, params=()):
        rows = original_all(sql, params)
        if sql == "SELECT * FROM messages WHERE contact_id=? ORDER BY step":
            barrier.wait(timeout=5)
        return rows
    monkeypatch.setattr(db, "all", snapshot)
    def attempt():
        try:
            approve(db, settings, prepared["contact_id"], "Reviewed applicable business outreach eligibility", "Founder owns this website")
            return "approved"
        except ValueError:
            return "changed"
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: attempt(), range(2)))
    assert sorted(results) == ["approved", "changed"]
    assert db.one("SELECT COUNT(*) n FROM events WHERE kind='sequence_approved'")["n"] == 1


def test_eligible_timezone_not_starved_by_first_hundred_due_contacts(db, settings, active):
    now = ready(db, active["contact_id"])
    with db.connect() as con:
        for index in range(101):
            domain = f"fictional-{index}.example.com"
            lid = con.execute("INSERT INTO leads(domain,website,company,campaign,source_url,timezone,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?)",
                              (domain, "https://" + domain, "Fictional timezone fixture", "A", "https://" + domain, "America/New_York", now, now)).lastrowid
            cid = con.execute("INSERT INTO contacts(lead_id,email,source_url,verification,verified_at,status,unsubscribe_token,created_at) VALUES(?,?,?,?,?,?,?,?)",
                              (lid, "test@" + domain, "https://" + domain, "safe", now, "active", f"fixture-{index}", now)).lastrowid
            con.execute("INSERT INTO messages(contact_id,step,subject,body,evidence_ids,state,due_at,message_id) VALUES(?,?,?,?,?,?,?,?)",
                        (cid, 0, "Fixture", "Never delivered", "[]", "queued", now - 1000, f"<fixture-{index}@sender.example.com>"))
    captured = []
    assert send_one(db, settings, now, lambda _, message: captured.append(message)) == "sent"
    assert len(captured) == 1 and captured[0]["To"] == "alex@bright-demo.com"


def test_draft_generation_cannot_overwrite_a_sequence_approved_mid_request(db, settings, prepared, monkeypatch):
    original_one = db.one
    def source_read(sql, params=()):
        row = original_one(sql, params)
        if sql == "SELECT url FROM evidence WHERE id=? AND lead_id=?":
            approve(db, settings, prepared["contact_id"], "Reviewed applicable business outreach eligibility", "Founder owns this website")
        return row
    monkeypatch.setattr(db, "one", source_read)
    with pytest.raises(ValueError, match="changed"):
        create_drafts(db, settings, prepared["contact_id"])
    assert db.one("SELECT status FROM contacts")["status"] == "active"
    assert db.one("SELECT COUNT(*) n FROM messages WHERE state='queued'")["n"] == 4
