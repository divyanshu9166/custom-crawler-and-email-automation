import base64
import json
import time

from fastapi.testclient import TestClient

from outreach.app import create_app


def test_auth_and_csrf(settings):
    app = create_app(settings)
    client = TestClient(app)
    assert client.get("/health").status_code == 200
    assert client.get("/api/leads").status_code == 401
    auth = base64.b64encode(f"{settings.admin_user}:{settings.admin_password}".encode()).decode()
    client.headers["Authorization"] = "Basic " + auth
    assert client.get("/").status_code == 200
    assert client.post("/api/pause").status_code == 403
    assert client.post("/api/pause", headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.post("/api/pause", headers={"Origin": settings.public_url}).status_code == 200


def test_api_import_detail_and_export(settings):
    client = TestClient(create_app(settings), headers={"Authorization": "Bearer " + settings.api_token})
    csv = "company,website,campaign,source_url,country_hint,email\nDemo,https://bright-demo.com,A,https://bright-demo.com,UK,alex@bright-demo.com\nBad,https://linkedin.com/company/bad,A,https://linkedin.com,US,\n"
    result = client.post("/api/import", json={"content": csv})
    assert result.status_code == 200
    assert len(result.json()["ids"]) == 1
    assert len(result.json()["errors"]) == 1
    lid = result.json()["ids"][0]
    detail = client.get(f"/api/leads/{lid}").json()
    assert detail["lead"]["country"] == ""
    assert detail["contacts"][0]["verification"] == "unverified"
    assert "alex@bright-demo.com" in client.get("/api/export").text


def test_authenticated_crawl_report_and_audit_images(settings, db, prepared):
    client = TestClient(create_app(settings), headers={"Authorization": "Bearer " + settings.api_token})
    report = {"status": "partial", "pages": [], "errors": [{"reason": "not_found"}]}
    db.execute("INSERT INTO crawls(lead_id,report,created_at) VALUES(?,?,?)",
               (prepared["lead_id"], json.dumps(report), time.time()))
    detail = client.get(f"/api/leads/{prepared['lead_id']}").json()
    assert json.loads(detail["crawl"]["report"]) == report
    assert not detail["evidence"][0]["current_for_review"]
    assert detail["evidence"][0]["text"]  # Preserved history remains readable.
    folder = settings.data_dir / "screenshots"
    folder.mkdir()
    filename = "lead-1-123456-abcdef-mobile.png"
    (folder / filename).write_bytes(b"image fixture")
    assert client.get(f"/api/screenshots/{filename}").content == b"image fixture"
    assert TestClient(create_app(settings)).get(f"/api/screenshots/{filename}").status_code == 401
    assert client.get("/api/screenshots/invalid.png").status_code == 404


def test_unsubscribe_get_does_not_mutate(settings, db, active):
    client = TestClient(create_app(settings))
    token = db.one("SELECT unsubscribe_token FROM contacts")["unsubscribe_token"]
    assert client.get(f"/unsubscribe/{token}").status_code == 200
    assert db.one("SELECT status FROM contacts")["status"] == "active"
    assert client.post(f"/unsubscribe/{token}", content="List-Unsubscribe=One-Click").status_code == 200
    assert db.one("SELECT status FROM contacts")["status"] == "suppressed"


def test_approve_and_edit_freeze(settings, db, prepared):
    client = TestClient(create_app(settings), headers={"Authorization": "Bearer " + settings.api_token})
    cid = prepared["contact_id"]
    payload = {"eligibility_basis": "Reviewed UK corporate eligibility and opt-out handling.",
               "contact_relevance": "Founder responsible for the website", "reviewed_all_messages": True}
    assert client.post(f"/api/contacts/{cid}/approve", json=payload).status_code == 200
    mid = db.one("SELECT id FROM messages")["id"]
    assert client.put(f"/api/messages/{mid}", json={"subject": "Changed", "body": "This would change approved content."}).status_code == 400
    assert client.post(f"/api/contacts/{cid}/approve", json=payload).status_code == 400


def test_job_dedup_and_schedule(settings, db):
    client = TestClient(create_app(settings), headers={"Authorization": "Bearer " + settings.api_token})
    payload = {"query": "UK SaaS contact", "campaign": "A", "country_hint": "UK", "limit": 5}
    first = client.post("/api/discover", json=payload).json()["job_id"]
    assert client.post("/api/discover", json=payload).json()["job_id"] == first
    sid = client.post("/api/schedules", json={**payload, "interval_hours": 24}).json()["id"]
    assert client.delete(f"/api/schedules/{sid}").status_code == 200
    assert client.get("/api/schedules").json()[0]["enabled"] == 0


def test_resume_blocked_when_unconfigured(settings):
    settings.smtp_password = ""
    client = TestClient(create_app(settings), headers={"Authorization": "Bearer " + settings.api_token})
    assert client.post("/api/resume").status_code == 400
