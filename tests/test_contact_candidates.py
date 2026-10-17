import json
import time

import pytest
from fastapi.testclient import TestClient

from outreach.app import create_app
from outreach.campaigns import approve, create_drafts
from outreach.research import add_contact, add_lead, assert_contact_ownership, contact_candidates, research_lead, verify_contact
from outreach.web import PublicWeb, extract_page


def publish_candidate(db, lid, email, source="https://bright-demo.com/contact"):
    page = extract_page(source, f'<p>Business enquiries: {email}</p>')
    db.execute("INSERT INTO evidence(lead_id,url,title,text,sha256,fetched_at) VALUES(?,?,?,?,?,?)",
               (lid, source, page["title"], page["text"], page["sha256"], time.time()))
    db.event("contact_candidate_found", {**page["review_candidates"][0], "lead_id": lid, "evidence_sha256": page["sha256"]})
    return source


def test_external_published_addresses_are_candidates_not_automatic_contacts():
    page = extract_page("https://bright-demo.com/", '<p>hello@bright-demo.com business@example.net privacy@example.net</p><a href="mailto:owner@gmail.com">Business owner</a><script>hidden@external-demo.com</script>')
    assert page["emails"] == ["hello@bright-demo.com"]
    assert {c["email"] for c in page["review_candidates"]} == {"business@example.net", "owner@gmail.com"}
    assert all(c["review_required"] and c["source_url"] == page["url"] for c in page["review_candidates"])


async def test_research_retains_candidates_without_importing_or_verifying_them(db, settings, monkeypatch):
    lid = add_lead(db, "Bright Demo", "https://bright-demo.com", "A", "https://bright-demo.com")
    page = extract_page("https://bright-demo.com/", '<p>hello@bright-demo.com owner@gmail.com agency@external-demo.com</p>')
    async def crawl(self, website):
        self.report["status"] = "complete"
        return [page]
    monkeypatch.setattr(PublicWeb, "crawl", crawl)
    await research_lead(db, settings, lid)
    assert [c["email"] for c in db.all("SELECT * FROM contacts")] == ["hello@bright-demo.com"]
    assert len(db.all("SELECT * FROM jobs WHERE kind='verify'")) == 1
    assert len(contact_candidates(db, lid)) == 2
    await research_lead(db, settings, lid)
    assert len(db.all("SELECT * FROM events WHERE kind='contact_candidate_found'")) == 2
    db.execute("UPDATE evidence SET sha256='changed' WHERE lead_id=?", (lid,))
    assert contact_candidates(db, lid) == []


def test_alias_contact_requires_source_and_ownership_then_remains_unverified(db, settings, prepared):
    lid = prepared["lead_id"]
    source = publish_candidate(db, lid, "owner@external-demo.com")
    with pytest.raises(ValueError, match="ownership review"):
        add_contact(db, lid, "owner@external-demo.com", source)
    with pytest.raises(ValueError, match="saved official-source"):
        add_contact(db, lid, "invented@external-demo.com", source, ownership_notes="Claimed business ownership without publication proof.")
    cid = add_contact(db, lid, "owner@external-demo.com", source, ownership_notes="The fixture company explicitly identifies this as its business enquiry inbox.")
    contact = db.one("SELECT * FROM contacts WHERE id=?", (cid,))
    assert contact["verification"] == "unverified" and contact["status"] == "new"
    create_drafts(db, settings, cid)
    with pytest.raises(ValueError, match="safe Reacher"):
        approve(db, settings, cid, "Fictional eligibility for this fixture business.", "Fixture business enquiry inbox.")
    db.execute("UPDATE contacts SET verification='safe',verified_at=? WHERE id=?", (time.time(), cid))
    approve(db, settings, cid, "Fictional eligibility for this fixture business.", "Fixture business enquiry inbox.")
    assert db.one("SELECT status FROM contacts WHERE id=?", (cid,))["status"] == "active"


def test_stale_source_invalidates_ownership_and_new_review_can_refresh_it(db, prepared):
    lid = prepared["lead_id"]
    source = publish_candidate(db, lid, "owner@external-demo.com")
    notes = "The fixture explicitly publishes this business enquiry address for this company."
    cid = add_contact(db, lid, "owner@external-demo.com", source, ownership_notes=notes)
    db.execute("UPDATE evidence SET sha256='new-snapshot' WHERE lead_id=? AND url=?", (lid, source))
    contact = db.one("SELECT * FROM contacts WHERE id=?", (cid,))
    lead = db.one("SELECT * FROM leads WHERE id=?", (lid,))
    with pytest.raises(ValueError, match="current official-source"):
        assert_contact_ownership(db, contact, lead)
    db.event("contact_candidate_found", {"lead_id": lid, "email": contact["email"], "source_url": source, "evidence_sha256": "new-snapshot"})
    assert add_contact(db, lid, contact["email"], source, ownership_notes=notes) == cid
    assert_contact_ownership(db, contact, lead)
    db.execute("UPDATE contacts SET status='replied' WHERE id=?", (cid,))
    with pytest.raises(ValueError, match="Existing outreach history"):
        add_contact(db, lid, contact["email"], source, ownership_notes=notes)


def test_shared_alias_inbox_cannot_attach_to_wrong_company(db, prepared):
    first = prepared["lead_id"]
    source = publish_candidate(db, first, "shared@external-demo.com")
    notes = "The fixture website publishes this for company enquiries; ownership reviewed."
    cid = add_contact(db, first, "shared@external-demo.com", source, ownership_notes=notes)
    other = add_lead(db, "Other Demo", "https://other-demo.com", "B", "https://other-demo.com")
    source = publish_candidate(db, other, "shared@external-demo.com", "https://other-demo.com/contact")
    with pytest.raises(ValueError, match="another company"):
        add_contact(db, other, "shared@external-demo.com", source, ownership_notes=notes)
    assert db.one("SELECT lead_id FROM contacts WHERE id=?", (cid,))["lead_id"] == first


def test_api_shows_candidates_but_only_queues_reviewed_inbox(db, settings, prepared):
    lid = prepared["lead_id"]
    source = publish_candidate(db, lid, "owner@external-demo.com")
    client = TestClient(create_app(settings), headers={"Authorization": "Bearer " + settings.api_token})
    candidate = client.get(f"/api/leads/{lid}").json()["review_candidates"][0]
    assert candidate["email"] == "owner@external-demo.com"
    payload = {"email": candidate["email"], "source_url": source}
    assert client.post(f"/api/leads/{lid}/contacts", json=payload).status_code == 400
    assert not db.one("SELECT id FROM contacts WHERE email=?", (candidate["email"],))
    payload["ownership_notes"] = "The fixture's official contact page labels this as its business inbox."
    result = client.post(f"/api/leads/{lid}/contacts", json=payload)
    assert result.status_code == 200
    contact = db.one("SELECT * FROM contacts WHERE id=?", (result.json()["id"],))
    assert contact["verification"] == "unverified"
    assert json.loads(db.one("SELECT payload FROM jobs WHERE id=?", (result.json()["job_id"],))["payload"])["contact_id"] == contact["id"]


async def test_stale_alias_source_blocks_provider_probe(db, settings, prepared, monkeypatch):
    from outreach import providers
    lid = prepared["lead_id"]
    source = publish_candidate(db, lid, "owner@external-demo.com")
    cid = add_contact(db, lid, "owner@external-demo.com", source, ownership_notes="The fixture confirms this as the company's business enquiry address.")
    db.execute("UPDATE evidence SET sha256='changed' WHERE lead_id=? AND url=?", (lid, source))
    async def verify(*args):
        pytest.fail("Stale ownership must not reach recipient probing")
    monkeypatch.setattr(providers, "verify_email", verify)
    with pytest.raises(ValueError, match="current official-source"):
        await verify_contact(db, settings, cid)


@pytest.mark.parametrize("change", ["source", "suppression"])
async def test_verification_rechecks_eligibility_after_spacing_wait(db, settings, prepared, monkeypatch, change):
    import asyncio
    lid = prepared["lead_id"]
    source = publish_candidate(db, lid, "owner@external-demo.com")
    cid = add_contact(db, lid, "owner@external-demo.com", source,
                      ownership_notes="The fixture explicitly identifies this as its current business inbox.")
    db.set("last_verification_attempt", time.time())
    waits = []
    async def spacing(seconds):
        waits.append(seconds)
        if change == "source":
            db.execute("UPDATE evidence SET sha256='changed-during-wait' WHERE lead_id=? AND url=?", (lid, source))
        else:
            db.suppress("owner@external-demo.com", "Fictional opt-out during verification spacing")
    async def unexpected_verify(*args):
        pytest.fail("Changed ownership or an opt-out during spacing must prevent the provider call")
    monkeypatch.setattr(asyncio, "sleep", spacing)
    monkeypatch.setattr("outreach.providers.verify_email", unexpected_verify)
    if change == "source":
        with pytest.raises(ValueError, match="current official-source"):
            await verify_contact(db, settings, cid)
    else:
        await verify_contact(db, settings, cid)
        assert db.one("SELECT status FROM contacts WHERE id=?", (cid,))["status"] == "suppressed"
    assert len(waits) == 1 and waits[0] > 0
    assert db.one("SELECT verification FROM contacts WHERE id=?", (cid,))["verification"] == "unverified"


@pytest.mark.parametrize("failed", [False, True])
async def test_recrawl_without_alias_page_invalidates_old_proof_but_preserves_history(db, settings, prepared, monkeypatch, failed):
    import httpx
    from outreach import providers
    lid = prepared["lead_id"]
    source = publish_candidate(db, lid, "owner@external-demo.com")
    cid = add_contact(db, lid, "owner@external-demo.com", source,
                      ownership_notes="The fixture publishes this as its current business enquiry inbox.")
    original = db.one("SELECT * FROM evidence WHERE lead_id=? AND url=?", (lid, source))
    async def crawl(self, website):
        if failed:
            raise httpx.ReadTimeout("Controlled recrawl failed before refreshing the contact source")
        self.report["status"] = "partial"
        return [extract_page("https://bright-demo.com/", "<p>New homepage; previous contact page was not captured.</p>")]
    monkeypatch.setattr(PublicWeb, "crawl", crawl)
    if failed:
        with pytest.raises(httpx.ReadTimeout):
            await research_lead(db, settings, lid)
    else:
        await research_lead(db, settings, lid)
    assert db.one("SELECT sha256 FROM evidence WHERE lead_id=? AND url=?", (lid, source))["sha256"] == original["sha256"]
    assert db.one("SELECT id FROM events WHERE contact_id=? AND kind='contact_source_reviewed'", (cid,))
    assert contact_candidates(db, lid) == []
    async def verify(*args):
        pytest.fail("Unrefreshed ownership source must not reach the provider")
    monkeypatch.setattr(providers, "verify_email", verify)
    with pytest.raises(ValueError, match="current official-source"):
        await verify_contact(db, settings, cid)
    # A later successful capture restores the same unchanged source/hash proof.
    async def refreshed(self, website):
        self.report["status"] = "complete"
        return [extract_page(source, "<p>Business enquiries: owner@external-demo.com</p>")]
    monkeypatch.setattr(PublicWeb, "crawl", refreshed)
    await research_lead(db, settings, lid)
    assert len(contact_candidates(db, lid)) == 1
    assert_contact_ownership(db, db.one("SELECT * FROM contacts WHERE id=?", (cid,)), db.one("SELECT * FROM leads WHERE id=?", (lid,)))


def test_recrawl_starting_during_alias_import_rejects_stale_proof_atomically(db, prepared, monkeypatch):
    lid = prepared["lead_id"]
    source = publish_candidate(db, lid, "owner@external-demo.com")
    original_one = db.one
    started = False
    def raced(sql, params=()):
        nonlocal started
        row = original_one(sql, params)
        if not started and sql.startswith("SELECT e.sha256 FROM evidence e JOIN events v"):
            started = True
            db.execute("INSERT INTO crawls(lead_id,report,created_at) VALUES(?,?,?)", (lid, '{"status":"running"}', time.time()))
        return row
    monkeypatch.setattr(db, "one", raced)
    with pytest.raises(ValueError, match="Source changed during review"):
        add_contact(db, lid, "owner@external-demo.com", source,
                    ownership_notes="The fixture published this business inbox before the new research started.")
    assert started
    assert not db.one("SELECT id FROM contacts WHERE email='owner@external-demo.com'")
    assert not db.one("SELECT id FROM events WHERE kind='contact_source_reviewed'")


def test_stale_ownership_holds_approved_sequence_before_smtp(db, settings, prepared):
    from datetime import datetime, timezone
    from outreach.mail import send_one
    lid = prepared["lead_id"]
    source = publish_candidate(db, lid, "owner@external-demo.com")
    cid = add_contact(db, lid, "owner@external-demo.com", source, ownership_notes="The fixture company publishes this as its reviewed business enquiry inbox.")
    create_drafts(db, settings, cid)
    db.execute("UPDATE contacts SET verification='safe',verified_at=? WHERE id=?", (time.time(), cid))
    approve(db, settings, cid, "Fictional corporate eligibility reviewed for this fixture.", "Fixture company enquiry inbox.")
    now = datetime(2026, 10, 12, 12, tzinfo=timezone.utc).timestamp()
    db.execute("UPDATE contacts SET verified_at=? WHERE id=?", (now, cid))
    db.execute("UPDATE messages SET due_at=? WHERE contact_id=? AND step=0", (now - 1, cid))
    db.set("imap_last_success", now)
    db.set("imap_caught_up", "true")
    db.set("paused", "false")
    db.execute("UPDATE evidence SET sha256='changed' WHERE lead_id=? AND url=?", (lid, source))
    assert send_one(db, settings, now, lambda *_: pytest.fail("Must not submit SMTP")) == "idle"
    assert db.one("SELECT status FROM contacts WHERE id=?", (cid,))["status"] == "hold"
    assert db.one("SELECT COUNT(*) n FROM messages WHERE contact_id=? AND state='sending'", (cid,))["n"] == 0
    from outreach.campaigns import resume_contact
    with pytest.raises(ValueError, match="current official-source"):
        resume_contact(db, settings, cid, "Fictional request to resume after inspecting the held sequence.", now + 3600)
