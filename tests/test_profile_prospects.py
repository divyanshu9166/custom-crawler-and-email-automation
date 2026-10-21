import hashlib
import json
import sqlite3
import time

import pytest
from fastapi.testclient import TestClient

from outreach.app import create_app
from outreach.campaigns import approve, create_drafts, review_lead
from outreach.db import DB
from outreach.profiles import add_profile_lead, canonical_profile
from outreach.research import add_contact, assert_contact_ownership, contact_candidates, discover_leads, research_lead, verify_contact


PROFILE = "https://www.facebook.com/fictional-bright-studio"
TEXT = "FICTIONAL Bright Studio. UK consulting services. Call us to arrange a consultation. We sell our own handmade products through business messages. Business email: bright-fixture@gmail.com"


def review_value(db, lid, campaign="A"):
    e = db.one("SELECT * FROM evidence WHERE lead_id=?", (lid,))
    return {"company": "Bright Studio", "country": "UK", "country_source": e["url"], "country_quote": "UK consulting services",
            "timezone": "Europe/London", "business_type": "corporate", "service": "website_build" if campaign == "A" else "store_launch",
            "fit_notes": "Fictional active company with a sourced inquiry process", "evidence_id": e["id"],
            "quote": "Call us to arrange a consultation.", "observation": "Your profile invites customers to arrange a consultation by phone.",
            "suggestion": "Explore a services page with a clear consultation request form.",
            'selling_stage': 'starting_ecommerce', 'commerce_evidence_id': e['id'],
            'commerce_quote': 'We sell our own handmade products through business messages.',
            'd2c_fit_notes': 'Fictional owned consumer products sold by messages; explore an online store launch.',
            "profile_ownership_notes": "Fictional fixture: business name, services and location match this business profile.",
            "profile_activity_quote": "UK consulting services", "website_search_notes": "Reviewed the search; no website matched, but search coverage is not proof of absence.",
            "website_search_reviewed": True}


def mock_profile(monkeypatch, state="no_company_match", snapshot_state="captured", website=""):
    async def resolve(*args):
        return {"source_url": PROFILE, "company": "Bright Studio", "platform": "facebook.com", "website": website, "state": state,
                "website_search": {"query": '"Bright Studio" official website UK', "completed": True, "engine_issues": []},
                "public_snapshot": {"state": snapshot_state, "url": PROFILE, "text": TEXT, "title": "Bright Studio",
                                    "published_emails": ["bright-fixture@gmail.com"], "sha256": hashlib.sha256(TEXT.encode()).hexdigest()}}
    monkeypatch.setattr("outreach.discovery.resolve_signal", resolve)
    monkeypatch.setattr("outreach.profiles.resolve_signal", resolve)


@pytest.mark.parametrize("campaign", ["A", "B"])
async def test_profile_to_reviewed_contact_and_four_drafts_retains_approval_gate(db, settings, monkeypatch, campaign):
    mock_profile(monkeypatch)
    lid = add_profile_lead(db, "Bright Studio", PROFILE, campaign, "UK")
    await research_lead(db, settings, lid)
    lead = db.one("SELECT * FROM leads WHERE id=?", (lid,))
    assert lead["website"] == "" and lead["website_status"] == "website_not_found"
    assert len(contact_candidates(db, lid)) == 1
    assert db.one("SELECT COUNT(*) n FROM contacts")["n"] == 0
    assert db.one("SELECT COUNT(*) n FROM jobs WHERE kind='verify'")["n"] == 0
    with pytest.raises(ValueError, match="Review current business profile"):
        add_contact(db, lid, "bright-fixture@gmail.com", PROFILE, ownership_notes="This current business profile publishes its own business inbox.")
    review_lead(db, lid, review_value(db, lid, campaign))
    cid = add_contact(db, lid, "bright-fixture@gmail.com", PROFILE, ownership_notes="This current business profile publishes its own business inbox.")
    assert_contact_ownership(db, db.one("SELECT * FROM contacts WHERE id=?", (cid,)), db.one("SELECT * FROM leads WHERE id=?", (lid,)))
    create_drafts(db, settings, cid)
    drafts = db.all("SELECT * FROM messages WHERE contact_id=? ORDER BY step", (cid,))
    assert len(drafts) == 4 and all(d["state"] == "draft" for d in drafts)
    assert "couldn't find" in drafts[0]["body"] and "please correct me" in drafts[0]["body"]
    assert "business profile" in drafts[0]["body"] and "sales double" not in drafts[0]["body"]
    with pytest.raises(ValueError, match="safe Reacher"):
        approve(db, settings, cid, "Reviewed business outreach eligibility and opt-out", "Owner manages business inquiries")


async def test_profile_discovery_imports_deduplicates_but_never_probes(db, settings, monkeypatch):
    mock_profile(monkeypatch)
    settings.discovery_platforms = "facebook.com"
    settings.discovery_query_delay_seconds = .1
    async def search(*args, **kwargs):
        return [{"url": PROFILE, "title": "Bright Studio", "snippet": "UK consulting services"}]
    monkeypatch.setattr("outreach.providers.discover", search)
    await discover_leads(db, settings, "UK consulting", "A", "UK", 1)
    await discover_leads(db, settings, "UK consulting", "A", "UK", 1)
    assert db.one("SELECT COUNT(*) n FROM leads")["n"] == 1
    assert db.one("SELECT COUNT(*) n FROM jobs WHERE kind='research'")["n"] == 1
    assert db.one("SELECT COUNT(*) n FROM contacts")["n"] == 0
    assert json.loads(db.one("SELECT detail FROM events WHERE kind='prospect_signal'")["detail"])["lead_id"]


@pytest.mark.parametrize("state,snapshot", [("ambiguous_search_matches", "captured"), ("no_company_match", "robots_denied")])
async def test_ambiguous_or_blocked_profile_cannot_be_qualified(db, settings, monkeypatch, state, snapshot):
    mock_profile(monkeypatch, state, snapshot)
    lid = add_profile_lead(db, "Bright Studio", PROFILE, "A", "UK")
    await research_lead(db, settings, lid)
    if snapshot == "captured":
        with pytest.raises(ValueError, match="completed website search"):
            review_lead(db, lid, review_value(db, lid))
    else:
        assert db.one("SELECT status FROM leads WHERE id=?", (lid,))["status"] == "profile_unavailable"
        assert not contact_candidates(db, lid)
        assert not db.all("SELECT * FROM evidence")
    assert not db.all("SELECT * FROM contacts")


async def test_failed_website_search_is_not_absence(db, settings, monkeypatch):
    async def fail(*args):
        raise TimeoutError()
    monkeypatch.setattr("outreach.profiles.resolve_signal", fail)
    lid = add_profile_lead(db, "Bright Studio", PROFILE, "A", "US")
    with pytest.raises(TimeoutError):
        await research_lead(db, settings, lid)
    lead = db.one("SELECT * FROM leads WHERE id=?", (lid,))
    assert lead["website_status"] == "search_unavailable" and lead["discovery_country"] == "US"


async def test_found_website_routes_to_normal_research_without_merging_contacts(db, settings, monkeypatch):
    mock_profile(monkeypatch, "linked_website_candidate", website="https://bright-demo.com/")
    lid = add_profile_lead(db, "Bright Studio", PROFILE, "A", "UK")
    await research_lead(db, settings, lid)
    assert db.one("SELECT website_status FROM leads WHERE id=?", (lid,))["website_status"] == "website_found"
    target = db.one("SELECT * FROM leads WHERE lead_kind='website'")
    assert target["website"] == "https://bright-demo.com/"
    assert json.loads(db.one("SELECT payload FROM jobs WHERE kind='research'")["payload"])["lead_id"] == target["id"]
    assert not db.all("SELECT * FROM contacts")


async def test_profile_recrawl_invalidates_old_ownership_and_prevents_probe(db, settings, monkeypatch):
    mock_profile(monkeypatch)
    lid = add_profile_lead(db, "Bright Studio", PROFILE, "A", "UK")
    await research_lead(db, settings, lid)
    review_lead(db, lid, review_value(db, lid))
    cid = add_contact(db, lid, "bright-fixture@gmail.com", PROFILE, ownership_notes="This current business profile publishes its own business inbox.")
    await research_lead(db, settings, lid)
    async def forbidden(*args):
        raise AssertionError("Unreviewed recipient probed")
    monkeypatch.setattr("outreach.providers.verify_email", forbidden)
    with pytest.raises(ValueError, match="Review current business profile"):
        await verify_contact(db, settings, cid)
    # A different business profile on the same platform is never interchangeable.
    review_lead(db, lid, review_value(db, lid))
    with pytest.raises(ValueError, match="ownership review"):
        add_contact(db, lid, "bright-fixture@gmail.com", "https://www.facebook.com/other-company", ownership_notes="A different fictional business page is not acceptable ownership evidence.")


def test_profile_api_no_fake_website_and_visual_audits_rejected(settings):
    client = TestClient(create_app(settings))
    client.headers["Authorization"] = "Bearer " + settings.api_token
    value = {"company": "Bright Studio", "profile_url": PROFILE, "campaign": "A", "country_hint": "UK"}
    response = client.post("/api/profile-leads", json=value)
    assert response.status_code == 200
    lid = response.json()["id"]
    lead = client.get(f"/api/leads/{lid}").json()["lead"]
    assert lead["website"] == "" and lead["lead_kind"] == "profile"
    assert client.post(f"/api/leads/{lid}/screenshot").status_code == 400
    assert client.post(f"/api/leads/{lid}/performance").status_code == 400
    exported = client.get("/api/export").text
    assert "profile_url" in exported and PROFILE in exported and "profile:" not in exported


async def test_reviewed_profile_contact_can_verify_and_queue_with_all_existing_gates(db, settings, monkeypatch, safe_result):
    mock_profile(monkeypatch)
    lid = add_profile_lead(db, "Bright Studio", PROFILE, "A", "UK")
    await research_lead(db, settings, lid)
    review_lead(db, lid, review_value(db, lid))
    cid = add_contact(db, lid, "bright-fixture@gmail.com", PROFILE, ownership_notes="This current business profile publishes its own business inbox.")
    calls = []
    async def controlled_verify(s, email, *, before_probe=None):
        if before_probe:
            before_probe()
        calls.append(email)
        return "safe", {**safe_result, "input": email}
    monkeypatch.setattr("outreach.providers.verify_email", controlled_verify)
    await verify_contact(db, settings, cid)
    assert calls == ["bright-fixture@gmail.com"]
    create_drafts(db, settings, cid)
    approve(db, settings, cid, "Reviewed business outreach eligibility and opt-out", "Owner manages business inquiries")
    assert db.one("SELECT status FROM contacts WHERE id=?", (cid,))["status"] == "active"
    assert len(db.all("SELECT * FROM messages WHERE state='queued'")) == 4
    assert not db.all("SELECT * FROM messages WHERE state='sent'")
    # Even after approval a changed published source invalidates contact ownership.
    db.execute("UPDATE evidence SET sha256='changed' WHERE lead_id=?", (lid,))
    with pytest.raises(ValueError, match="Review current business profile"):
        assert_contact_ownership(db, db.one("SELECT * FROM contacts WHERE id=?", (cid,)), db.one("SELECT * FROM leads WHERE id=?", (lid,)))


@pytest.mark.parametrize("url", ["https://x.com/name/status/123", "https://www.facebook.com/",
                                 "https://google.com/maps/search/plumbers", "https://instagram.com/p/post"])
def test_non_business_profile_paths_rejected(url):
    with pytest.raises(ValueError):
        canonical_profile(url)


def test_v2_database_migrates_without_losing_data(tmp_path):
    path = tmp_path / "legacy.db"
    # Use the old schema and a real old row, rather than testing a fresh v3 database.
    from outreach.db import SCHEMA
    with sqlite3.connect(path) as con:
        con.executescript(SCHEMA)
        con.execute("INSERT INTO leads(domain,website,company,campaign,source_url,created_at,updated_at) VALUES(?,?,?,?,?,?,?)",
                    ("bright-demo.com", "https://bright-demo.com/", "Bright Studio", "A", "https://bright-demo.com/", time.time(), time.time()))
        con.execute("PRAGMA user_version=2")
    db = DB(path)
    lead = db.one("SELECT * FROM leads")
    assert lead["website"] == "https://bright-demo.com/" and lead["lead_kind"] == "website"
    assert db.one("PRAGMA user_version")["user_version"] == 8
