import asyncio

from fastapi.testclient import TestClient

from outreach.app import create_app
from outreach.worker import run


def test_demo_status_and_resume_blocked(db, settings):
    db.set("demo", "true")
    client = TestClient(create_app(settings), headers={"Authorization": "Bearer " + settings.api_token})
    assert client.get("/api/status").json()["demo"] is True
    result = client.post("/api/resume")
    assert result.status_code == 400 and "Offline demo" in result.json()["detail"]
    assert db.get("paused", "true") == "true"


async def test_demo_worker_never_runs_provider_or_mail_jobs(db, settings, monkeypatch):
    db.set("demo", "true")
    job_id = db.enqueue("discover", {"query": "fictional"})
    settings.worker_enabled = True
    async def forbidden(*args, **kwargs):
        raise AssertionError("Demo must not run provider or mailbox lanes")
    monkeypatch.setattr("outreach.worker.mail_loop", forbidden)
    monkeypatch.setattr("outreach.worker.job_loop", forbidden)
    stop = asyncio.Event()
    task = asyncio.create_task(run(db, settings, stop))
    try:
        await asyncio.sleep(0.03)
        assert db.get("worker_heartbeat")
        assert db.one("SELECT state FROM jobs WHERE id=?", (job_id,))["state"] == "pending"
    finally:
        stop.set()
        await asyncio.wait_for(task, timeout=1)
