import json
import time

import pytest
from fastapi.testclient import TestClient

from outreach.app import create_app
from outreach.campaigns import approve
from outreach.mail import record_inbound, send_one
from outreach.research import add_lead
from outreach.sales import record_activity, release_outreach_hold
from test_campaigns_mail import inbound, ready


@pytest.fixture
def client(settings):
    return TestClient(create_app(settings), headers={"Authorization": "Bearer " + settings.api_token})


def sales_payload(client, lid, stage="qualified"):
    current = client.get(f"/api/leads/{lid}").json()["sales"]
    return {"stage": stage, "version": current["version"], "confirmed_problem": "Client confirmed that the booking route is confusing.",
            "primary_goal": "Improve qualified consultation inquiries", "success_metric": "Compare qualified inquiries with the prior measured baseline", "decision_maker": "Alex Demo, founder, confirmed decision owner",
            "baseline_notes": "Unknown baseline; agree a two-week measurement period before assessing the pilot.",
            "timeline": "Client plans a four-week pilot", "budget_notes": "Client-confirmed pilot budget; record details privately", "call_at": time.time() + 3600,
            "next_action_at": time.time() + 7200}


def proposal_payload():
    return {"title": "Consultation booking pilot proposal", "scope": "Improve the agreed consultation journey", "deliverables": "One landing page and one reviewed inquiry route",
            "timeline": "Four weeks with weekly review milestones", "exclusions": "Hosting and external provider subscriptions excluded", "acceptance_criteria": "Client approves the agreed inquiry route and measurement setup",
            "payment_terms": "Agreed initial payment followed by a delivery milestone", "ownership_revision_terms": "Record agreed ownership, revisions and change-request terms",
            "fee": "1200.50", "currency": "GBP"}


def test_manual_linkedin_history_blocks_new_cold_email(client, db, settings, prepared):
    lid, cid = prepared["lead_id"], prepared["contact_id"]
    result = client.post(f"/api/leads/{lid}/activity", json={"channel": "linkedin", "kind": "outreach", "note": "Operator sent an actual manual LinkedIn introduction to this founder.", "source_url": "https://linkedin.com/in/fictional-fixture"})
    assert result.status_code == 200
    with pytest.raises(ValueError, match="shared outreach"):
        approve(db, settings, cid, "Reviewed applicable business outreach eligibility", "Founder owns this website")
    release_outreach_hold(db, lid, "Reviewed shared history and confirmed a distinct appropriate email approach")
    approve(db, settings, cid, "Reviewed applicable business outreach eligibility", "Founder owns this website")
    assert db.one("SELECT status FROM contacts")["status"] == "active"


def test_manual_reply_stops_active_sequence_and_cannot_release(client, db, settings, active):
    lid = active["lead_id"]
    record_activity(db, lid, {"channel": "linkedin", "kind": "reply", "note": "Founder replied manually asking for the proposed website review."})
    assert db.one("SELECT status FROM contacts")["status"] == "replied"
    assert db.one("SELECT COUNT(*) n FROM tasks WHERE lead_id=? AND kind='review'", (lid,))["n"] == 1
    assert send_one(db, settings, ready(db, active["contact_id"]), lambda *_: pytest.fail("Must not send")) == "idle"
    with pytest.raises(ValueError, match="remain stopped"):
        release_outreach_hold(db, lid, "Manual replies must not be overridden to restart cold outreach")


def test_manual_optout_suppresses_and_preserves_history(client, db, prepared):
    lid = prepared["lead_id"]
    response = client.post(f"/api/leads/{lid}/activity", json={"channel": "email", "kind": "opt_out", "contact_id": prepared["contact_id"], "note": "Recipient explicitly asked to stop further outreach."})
    assert response.status_code == 200
    assert db.one("SELECT status FROM contacts")["status"] == "suppressed"
    assert len(client.get(f"/api/leads/{lid}").json()["activities"]) == 1


def test_sales_report_includes_companies_without_sales_records(client, db, prepared):
    add_lead(db, "Uncontacted fixture", "https://uncontacted-fixture.com", "B", "https://uncontacted-fixture.com")
    stages = client.get("/api/sales/report").json()["stages"]
    assert {"campaign": "A", "stage": "new", "n": 1} in stages
    assert {"campaign": "B", "stage": "new", "n": 1} in stages


def test_contact_from_another_company_is_rejected(client, db, prepared):
    lid = add_lead(db, "Other fixture", "https://other-fixture.com", "B", "https://other-fixture.com")
    response = client.post(f"/api/leads/{lid}/activity", json={"channel": "phone", "kind": "reply", "contact_id": prepared["contact_id"], "note": "A source-attested real conversation happened."})
    assert response.status_code == 400
    assert db.one("SELECT COUNT(*) n FROM activities")["n"] == 0


def test_inbound_reply_creates_one_fulfillment_task_and_shared_hold(client, db, active):
    raw = inbound(db, "Yes, please send the audit")
    record_inbound(db, raw, "actual-local-fixture-reply")
    record_inbound(db, raw, "actual-local-fixture-reply")
    detail = client.get(f"/api/leads/{active['lead_id']}").json()
    assert detail["sales"]["cold_email_hold"] == 1
    assert len(detail["tasks"]) == 1 and detail["tasks"][0]["kind"] == "followup"


def test_unconfirmed_client_need_cannot_advance_or_create_proposal(client, prepared):
    lid = prepared["lead_id"]
    assert client.put(f"/api/leads/{lid}/sales", json=sales_payload(client, lid)).status_code == 400
    assert client.post(f"/api/leads/{lid}/proposals", json=proposal_payload()).status_code == 400


def test_complete_operator_confirmed_sales_lifecycle(client, db, prepared):
    lid = prepared["lead_id"]
    assert client.post(f"/api/leads/{lid}/activity", json={"channel": "meeting", "kind": "reply", "note": "Client confirmed the need during an actual discovery discussion."}).status_code == 200
    assert client.put(f"/api/leads/{lid}/sales", json=sales_payload(client, lid)).status_code == 200
    assert client.put(f"/api/leads/{lid}/sales", json=sales_payload(client, lid, "call_booked")).status_code == 200
    result = client.post(f"/api/leads/{lid}/proposals", json=proposal_payload())
    assert result.status_code == 200
    pid = result.json()["id"]
    download = client.get(f"/api/proposals/{pid}/download")
    assert "Client confirmed that the booking route" in download.text
    assert "GBP 1200.50" in download.text and "DRAFT" in download.text
    assert client.post(f"/api/proposals/{pid}/sent", json={"reference": "Actually delivered proposal to client", "actually_delivered": True}).status_code == 400
    assert client.post(f"/api/proposals/{pid}/approve", json={"reviewed_scope_and_terms": True}).status_code == 200
    assert "DRAFT" not in client.get(f"/api/proposals/{pid}/download").text
    assert client.post(f"/api/proposals/{pid}/sent", json={"reference": "Operator-confirmed delivery reference fixture", "actually_delivered": True}).status_code == 200
    for stage in ("proposal", "won", "delivery", "completed"):
        value = {**sales_payload(client, lid, stage), "proposal_id": pid, "agreement_reference": "Signed agreement fixture reference", "payment_reference": "Actual initial-payment fixture reference", "acceptance_reference": "Client recorded acceptance fixture reference", "outcome_notes": "Pilot completed; outcome remains inconclusive, not a promised lift."}
        assert client.put(f"/api/leads/{lid}/sales", json=value).status_code == 200
    report = client.get("/api/sales/report").json()
    assert report["recorded_contract_value"] == {"GBP": "1200.50"}
    assert any(row["stage"] == "completed" for row in report["stages"])
    assert "not verified revenue" in report["note"]


def test_won_requires_real_references_and_delivered_proposal(client, prepared):
    lid = prepared["lead_id"]
    client.post(f"/api/leads/{lid}/activity", json={"channel": "email", "kind": "reply", "note": "Client actually requested a discussion of this scope."})
    value = sales_payload(client, lid, "won")
    response = client.put(f"/api/leads/{lid}/sales", json=value)
    assert response.status_code == 400 and "agreement" in response.json()["detail"]


def test_stale_sales_update_cannot_overwrite_new_client_context(client, prepared):
    lid = prepared["lead_id"]
    client.post(f"/api/leads/{lid}/activity", json={"channel": "email", "kind": "reply", "note": "Client asked for an outline of the actual proposal."})
    value = sales_payload(client, lid)
    assert client.put(f"/api/leads/{lid}/sales", json=value).status_code == 200
    assert client.put(f"/api/leads/{lid}/sales", json=value).status_code == 400


def test_tasks_are_due_visible_and_close_with_outcome(client, prepared):
    lid = prepared["lead_id"]
    task = client.post(f"/api/leads/{lid}/tasks", json={"kind": "audit", "title": "Prepare the promised annotated audit", "due_at": time.time() - 600}).json()["id"]
    assert client.get("/api/sales/report").json()["overdue_tasks"] == 1
    assert client.put(f"/api/tasks/{task}", json={"state": "done", "outcome": "Prepared the source-backed audit for human review."}).status_code == 200
    assert client.put(f"/api/tasks/{task}", json={"state": "done", "outcome": "Duplicate completion must not change the task."}).status_code == 400
    assert client.get("/api/sales/report").json()["overdue_tasks"] == 0


def test_sales_artifacts_and_static_asset_require_auth(settings, client, prepared):
    unauthenticated = TestClient(create_app(settings))
    assert unauthenticated.get("/api/sales/report").status_code == 401
    assert unauthenticated.get("/api/proposals/1/download").status_code == 401
    assert client.get("/static/sales.js").status_code == 200
    assert unauthenticated.get("/static/sales.js").status_code == 401


def test_invalid_dates_and_future_activity_are_rejected(client, prepared):
    lid = prepared["lead_id"]
    assert client.post(f"/api/leads/{lid}/activity", json={"channel": "email", "kind": "outreach", "note": "Future outreach is not an already-performed activity.", "happened_at": time.time() + 3600}).status_code == 400
    value = sales_payload(client, lid, "new")
    value["call_at"] = -20
    assert client.put(f"/api/leads/{lid}/sales", json=value).status_code == 400
    assert client.post(f"/api/leads/{lid}/tasks", content='{"kind":"call","title":"Review real client context","due_at":NaN}', headers={"Content-Type": "application/json"}).status_code in {400, 422}


def test_schema_upgrade_preserves_existing_approved_sequence(db, active):
    from outreach.db import DB
    before = db.all("SELECT * FROM messages ORDER BY id")
    # Remove only the new empty tables from the isolated fixture to reproduce an actual v1 layout.
    for name in ("deliverables", "proposals", "tasks", "activities", "sales"):
        db.execute(f"DROP TABLE {name}")
    db.execute("PRAGMA user_version=1")
    reopened = DB(db.path)
    assert reopened.all("SELECT * FROM messages ORDER BY id") == before
    assert reopened.one("PRAGMA user_version")["user_version"] == 5
    assert reopened.one("SELECT COUNT(*) n FROM activities")["n"] == 0
    assert json.loads(reopened.one("SELECT findings FROM leads")["findings"])
