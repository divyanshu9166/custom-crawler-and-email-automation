"""Runtime switches use isolated databases and controlled jobs, never real providers."""
import asyncio
from threading import Event

import pytest
from fastapi.testclient import TestClient

from outreach.app import create_app
from outreach.config import Settings
from outreach.mail import send_one
from outreach.preferences import Preferences
from outreach.worker import mail_loop


def client_for(settings):
    return TestClient(create_app(settings), base_url=settings.public_url,
                      headers={'Authorization': 'Bearer ' + settings.api_token})


def test_runtime_flags_persist_override_environment_and_never_resume(settings, db):
    settings.sending_enabled = False
    original = settings.model_dump()
    client = client_for(settings)
    db.set('paused', 'false')
    response = client.put('/api/settings/runtime', json={'worker_enabled': True, 'sending_enabled': True})
    assert response.status_code == 200
    assert response.json()['paused'] is True
    assert db.get('paused') == 'true'
    assert settings.worker_enabled and settings.sending_enabled
    restarted = Settings(_env_file=None, **original)
    state = client_for(restarted).get('/api/settings').json()
    assert state['worker_enabled'] and state['sending_enabled']
    assert restarted.worker_enabled and restarted.sending_enabled
    assert client.post('/api/resume').status_code == 200
    assert db.get('paused') == 'false'
    assert client.put('/api/settings/runtime', json={'sending_enabled': False}).status_code == 200
    assert settings.worker_enabled and not settings.sending_enabled
    assert db.get('paused') == 'true'
    assert client.post('/api/resume').status_code == 400
    assert client.put('/api/settings/runtime', json={'worker_enabled': False}).status_code == 200
    state = client.get('/api/status').json()
    assert not state['worker_enabled'] and not state['sending_enabled'] and state['paused']


def test_runtime_auth_origin_strict_input_and_demo_guards(settings, db):
    client = TestClient(create_app(settings), base_url=settings.public_url)
    patch = {'worker_enabled': True, 'sending_enabled': True}
    assert client.put('/api/settings/runtime', json=patch).status_code == 401
    origin = {'Origin': settings.public_url}
    assert client.post('/api/login', json={
        'username': settings.admin_user, 'password': settings.admin_password,
    }, headers=origin).status_code == 200
    assert client.put('/api/settings/runtime', json=patch).status_code == 403
    for invalid in ({'worker_enabled': 'false'}, {'sending_enabled': 1}, {'api_token': 'unexpected'}):
        assert client.put('/api/settings/runtime', json=invalid, headers=origin).status_code == 422
    assert client.put('/api/settings/runtime', json={}, headers=origin).status_code == 400
    assert not (settings.data_dir / 'workspace-settings.json').exists()
    db.set('demo', 'true')
    assert client.put('/api/settings/runtime', json=patch, headers=origin).status_code == 400
    assert client.put('/api/settings/runtime', json={
        'worker_enabled': False, 'sending_enabled': False,
    }, headers=origin).status_code == 200
    assert not settings.worker_enabled and not settings.sending_enabled
    assert client.post('/api/resume', headers=origin).status_code == 400


def test_runtime_storage_failure_leaves_flags_unchanged_and_sending_paused(settings, db, monkeypatch):
    preferences = Preferences(settings)
    db.set('paused', 'false')
    def fail(*args):
        raise OSError('controlled storage failure')
    monkeypatch.setattr(preferences, 'persist', fail)
    with pytest.raises(OSError, match='controlled'):
        preferences.update_runtime(db, {'worker_enabled': True, 'sending_enabled': False})
    assert not settings.worker_enabled and settings.sending_enabled
    assert db.get('paused') == 'true'


def test_worker_can_enable_from_dashboard_drain_and_resume_without_restart(settings, db, monkeypatch):
    settings.sending_enabled = False
    # This checks the runtime switches, not this machine's transient CPU load.
    # Resource-pressure admission is exercised separately with controlled probes.
    settings.crawl_adaptive_concurrency = False
    first = db.enqueue('research', {'lead_id': 1})
    started, release, finished, second_finished = Event(), Event(), Event(), Event()
    executed = []
    async def execute(database, configured, job):
        executed.append(job['id'])
        if job['id'] == first:
            started.set()
            while not release.is_set():
                await asyncio.sleep(.01)
        database.execute("UPDATE jobs SET state='done' WHERE id=?", (job['id'],))
        (finished if job['id'] == first else second_finished).set()
    monkeypatch.setattr('outreach.worker.execute_job', execute)
    monkeypatch.setattr('outreach.worker.poll_all', lambda *args: False)
    monkeypatch.setattr('outreach.worker.send_one', lambda *args: 'disabled')
    app = create_app(settings)
    with TestClient(app, headers={'Authorization': 'Bearer ' + settings.api_token}) as client:
        assert not started.wait(.1)
        assert db.one('SELECT state FROM jobs WHERE id=?', (first,))['state'] == 'pending'
        assert client.post('/api/resume').status_code == 400
        assert client.put('/api/settings/runtime', json={'worker_enabled': True}).status_code == 200
        try:
            assert started.wait(5)
            second = db.enqueue('research', {'lead_id': 2})
            assert client.put('/api/settings/runtime', json={'worker_enabled': False}).status_code == 200
            assert db.one('SELECT state FROM jobs WHERE id=?', (first,))['state'] == 'running'
        finally:
            release.set()
        assert finished.wait(2)
        assert not second_finished.wait(.1)
        assert db.one('SELECT state FROM jobs WHERE id=?', (second,))['state'] == 'pending'
        assert client.put('/api/settings/runtime', json={'worker_enabled': True}).status_code == 200
        assert second_finished.wait(5)
        assert executed == [first, second]
        assert db.get('paused') == 'true'


async def test_worker_off_blocks_mail_and_switch_during_poll_prevents_next_send(settings, db, monkeypatch):
    stop, polled = asyncio.Event(), Event()
    calls = []
    def poll(*args):
        calls.append('poll')
        settings.worker_enabled = False
        polled.set()
    monkeypatch.setattr('outreach.worker.poll_all', poll)
    monkeypatch.setattr('outreach.worker.send_one', lambda *args: calls.append('send'))
    task = asyncio.create_task(mail_loop(db, settings, stop))
    try:
        await asyncio.sleep(.05)
        assert calls == [] and not db.get('worker_heartbeat')
        settings.worker_enabled = True
        assert await asyncio.to_thread(polled.wait, 5)
        await asyncio.sleep(.05)
        assert calls == ['poll']
    finally:
        stop.set()
        await asyncio.wait_for(task, timeout=2)


async def test_sending_off_keeps_inbox_monitoring_without_submitting_mail(settings, db, monkeypatch):
    settings.worker_enabled, settings.sending_enabled = True, False
    stop, calls = asyncio.Event(), []
    loop = asyncio.get_running_loop()
    def forbidden_sender(*args):
        raise AssertionError('Disabled sending must not submit mail')
    def send(database, configured):
        calls.append(send_one(database, configured, sender=forbidden_sender))
        loop.call_soon_threadsafe(stop.set)
    monkeypatch.setattr('outreach.worker.poll_all', lambda *args: calls.append('poll'))
    monkeypatch.setattr('outreach.worker.send_one', send)
    await asyncio.wait_for(mail_loop(db, settings, stop), timeout=3)
    assert calls == ['poll', 'disabled']
