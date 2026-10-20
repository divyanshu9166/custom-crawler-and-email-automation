import base64
import json

import pytest
from fastapi.testclient import TestClient

from outreach.app import create_app
from outreach.campaigns import review_lead
from test_requirements_audit import review_payload


@pytest.fixture
def client(settings):
    return TestClient(create_app(settings), headers={"Authorization": "Bearer " + settings.api_token})


def value(kind, prepared):
    return {"kind": kind, "title": "Source-backed fictional value artifact", "reviewed_source_points": True,
            "headline": "A clearer consultation journey", "intro": "Proposed introductory copy for an illustrative consultation page.",
            "primary_action": "Explore a consultation",
            "faqs": [{"evidence_id": prepared["evidence_id"], "question": "How can I enquire about a consultation?", "quote": "Contact us for a consultation."}]}


@pytest.mark.parametrize("kind", ["audit", "concept", "faq_demo", "whatsapp_flow"])
def test_each_value_artifact_is_sourced_reviewable_and_deliverable(client, db, prepared, kind):
    lid = prepared["lead_id"]
    if kind == "whatsapp_flow":
        db.execute("UPDATE leads SET campaign='B',campaign_id=(SELECT id FROM campaign_groups WHERE goal='B' AND is_default=1) WHERE id=?", (lid,))
        review = {**review_payload(db, prepared), "service": "whatsapp_automation", "channel_fit_notes": "Illustrative channel context; qualify permission and actual customer fit before any pilot."}
        db.execute('UPDATE evidence SET text=text || ? WHERE id=?', (' We sell our own products online to consumers.', prepared['evidence_id']))
        review.update(selling_stage='selling_online', commerce_evidence_id=prepared['evidence_id'],
                      commerce_quote='We sell our own products online to consumers.',
                      d2c_fit_notes='Fictional consumer-product store ownership and selling process reviewed.')
        review_lead(db, lid, review)
    created = client.post(f"/api/leads/{lid}/artifacts", json=value(kind, prepared))
    assert created.status_code == 200
    aid = created.json()["id"]
    downloaded = client.get(f"/api/artifacts/{aid}/download")
    assert "Contact us for a consultation." in downloaded.text
    assert "https://bright-demo.com/" in downloaded.text
    assert "DRAFT" in downloaded.text and "Content-Disposition" in downloaded.headers
    assert client.post(f"/api/artifacts/{aid}/sent", json={"reference": "Synthetic fixture delivery reference", "actually_delivered": True}).status_code == 400
    assert client.post(f"/api/artifacts/{aid}/approve", json={"reviewed_scope_and_terms": True}).status_code == 200
    assert "DRAFT" not in client.get(f"/api/artifacts/{aid}/download").text
    assert client.post(f"/api/artifacts/{aid}/sent", json={"reference": "Synthetic fixture delivery reference", "actually_delivered": True}).status_code == 200
    detail = client.get(f"/api/leads/{lid}").json()["deliverables"][0]
    assert detail["state"] == "sent" and prepared["evidence_id"] in json.loads(detail["evidence_ids"])


def test_artifact_rejects_unsourced_or_other_company_claim(client, prepared):
    payload = value("audit", prepared)
    payload["points"] = [{"evidence_id": prepared["evidence_id"], "quote": "An invented revenue loss", "observation": "An unsupported client pain point", "suggestion": "An unsupported recommendation"}]
    assert client.post(f"/api/leads/{prepared['lead_id']}/artifacts", json=payload).status_code == 400
    payload["points"][0].update(evidence_id=999, quote="Contact us for a consultation.")
    assert client.post(f"/api/leads/{prepared['lead_id']}/artifacts", json=payload).status_code == 400


def test_faq_and_concept_labels_do_not_claim_live_ai_or_finished_website(client, prepared):
    lid = prepared["lead_id"]
    for kind, phrase in [("faq_demo", "not a live AI assistant"), ("concept", "not a finished client website")]:
        aid = client.post(f"/api/leads/{lid}/artifacts", json=value(kind, prepared)).json()["id"]
        text = client.get(f"/api/artifacts/{aid}/download").text
        assert phrase in text and "<script" not in text


def test_prospect_html_is_escaped_in_export(client, db, prepared):
    dangerous = '<script>alert("untrusted source")</script>'
    db.execute("UPDATE evidence SET text=text || ? WHERE id=?", (dangerous, prepared["evidence_id"]))
    payload = value("faq_demo", prepared)
    payload["faqs"][0]["quote"] = dangerous
    aid = client.post(f"/api/leads/{prepared['lead_id']}/artifacts", json=payload).json()["id"]
    text = client.get(f"/api/artifacts/{aid}/download").text
    assert "<script" not in text and "&lt;script&gt;" in text


def test_annotated_artifact_embeds_only_its_saved_company_screenshot(client, db, prepared):
    folder = db.path.parent / "screenshots"
    folder.mkdir()
    name = f"lead-{prepared['lead_id']}-123-abcdef-mobile.png"
    png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jNwoAAAAASUVORK5CYII=")
    (folder / name).write_bytes(png)
    payload = {**value("audit", prepared), "screenshot_name": name, "markers": [{"point_index": 0, "left": 35, "top": 20}]}
    result = client.post(f"/api/leads/{prepared['lead_id']}/artifacts", json=payload)
    assert result.status_code == 200
    body = client.get(f"/api/artifacts/{result.json()['id']}/download").text
    assert "data:image/png;base64," in body and "left:35.0%" in body
    payload["screenshot_name"] = "lead-999-123-abcdef-mobile.png"
    assert client.post(f"/api/leads/{prepared['lead_id']}/artifacts", json=payload).status_code == 400
    payload["screenshot_name"] = "../../private.png"
    assert client.post(f"/api/leads/{prepared['lead_id']}/artifacts", json=payload).status_code == 400


def test_whatsapp_flow_requires_qualified_channel_and_artifacts_require_auth(settings, client, prepared):
    assert client.post(f"/api/leads/{prepared['lead_id']}/artifacts", json=value("whatsapp_flow", prepared)).status_code == 400
    assert TestClient(create_app(settings)).get("/api/artifacts/1/download").status_code == 401
