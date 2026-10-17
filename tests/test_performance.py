import json

import httpx
import pytest
from fastapi.testclient import TestClient

from outreach.app import create_app
from outreach.performance import performance_audit
from outreach.web import PublicWeb


@pytest.fixture
def allow_robots(monkeypatch):
    from urllib.robotparser import RobotFileParser
    parser = RobotFileParser()
    parser.parse([])
    async def robots(*args):
        return parser, 0, "https://bright-demo.com/"
    monkeypatch.setattr(PublicWeb, "robots", robots)


@pytest.mark.parametrize("desktop", ["ok", "quota", "cross_domain"])
async def test_pagespeed_preserves_lab_evidence_and_partial_results(db, settings, prepared, allow_robots, monkeypatch, desktop):
    settings.pagespeed_api_key = "private-fixture-key"
    async def get(self, url, params):
        assert url == "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
        assert params["key"] == settings.pagespeed_api_key
        request = httpx.Request("GET", url, params=params)
        if params["strategy"] == "desktop" and desktop == "quota":
            return httpx.Response(429, request=request)
        return httpx.Response(200, request=request, json={"lighthouseResult": {
            "finalUrl": "https://other-business.com/" if params["strategy"] == "desktop" and desktop == "cross_domain" else "https://bright-demo.com/",
            "fetchTime": "2026-10-10T10:00:00Z", "lighthouseVersion": "fixture",
            "categories": {"performance": {"score": .83}},
            "audits": {"largest-contentful-paint": {"displayValue": "2.8 s", "numericValue": 2800, "numericUnit": "millisecond"},
                       "unused-css": {"scoreDisplayMode": "numeric", "score": .5, "title": "Reduce unused CSS"}}}})
    monkeypatch.setattr(httpx.AsyncClient, "get", get)
    result = await performance_audit(db, settings, prepared["lead_id"])
    assert result["strategies"]["mobile"]["score"] == 83
    assert result["status"] == ("complete" if desktop == "ok" else "partial")
    raw = db.one("SELECT detail FROM events WHERE kind='performance'")["detail"]
    assert "private-fixture-key" not in raw
    assert "not visitor analytics" in raw
    assert json.loads(raw)["strategies"]["mobile"]["metrics"]["largest-contentful-paint"]["numericValue"] == 2800


async def test_pagespeed_failure_never_creates_fake_score(db, settings, prepared, allow_robots, monkeypatch):
    async def get(*args, **kwargs):
        return httpx.Response(429, request=httpx.Request("GET", "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"))
    monkeypatch.setattr(httpx.AsyncClient, "get", get)
    with pytest.raises(ValueError, match="PageSpeed audit failed"):
        await performance_audit(db, settings, prepared["lead_id"])
    report = json.loads(db.one("SELECT detail FROM events WHERE kind='performance'")["detail"])
    assert report["status"] == "failed" and not report["strategies"]


def test_performance_job_and_company_events_visible_in_api(db, settings, prepared):
    client = TestClient(create_app(settings), headers={"Authorization": "Bearer " + settings.api_token})
    lid = prepared["lead_id"]
    job = client.post(f"/api/leads/{lid}/performance")
    assert job.status_code == 200
    assert db.one("SELECT kind FROM jobs")["kind"] == "performance"
    db.event("performance", {"lead_id": lid, "status": "fixture"})
    assert any(e["kind"] == "performance" for e in client.get(f"/api/leads/{lid}").json()["events"])
    assert client.post("/api/leads/9999/performance").status_code == 404
