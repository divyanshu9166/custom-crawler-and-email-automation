"""Tracked actions report their own job, never a different batch or a fabricated percentage."""
import json
import time

import pytest
from fastapi.testclient import TestClient

from outreach.app import create_app
from outreach.activity import job_status


def test_activity_requires_auth_and_omits_unrelated_payload_fields(settings, db):
    client = TestClient(create_app(settings))
    jid = db.enqueue('prepare', {'lead_id': 456, 'private_marker': 'fictional-private-value'})
    assert client.get('/api/jobs/'+str(jid)).status_code == 401
    assert client.get('/static/feedback.js').status_code == 401
    client.headers['Authorization'] = 'Bearer '+settings.api_token
    response = client.get('/api/jobs/'+str(jid))
    assert response.status_code == 200
    assert response.json()['state'] == 'pending' and response.json()['lead_id'] == 456
    assert 'fictional-private-value' not in response.text and 'payload' not in response.json()
    assert client.get('/api/jobs/99999').status_code == 404
    assert client.get('/static/feedback.js').status_code == 200
    assert client.get('/static/feedback.css').status_code == 200


@pytest.mark.parametrize('state', ['pending', 'running', 'done', 'failed', 'cancelled'])
def test_activity_reports_actual_state_and_worker_pause(settings, db, state):
    settings.worker_enabled = False
    jid = db.enqueue('research', {'lead_id': 1})
    db.execute('UPDATE jobs SET state=?,error=? WHERE id=?', (state, 'Fixture status detail', jid))
    report = job_status(db, settings, jid)
    assert report['state'] == state and report['worker_enabled'] is False
    assert report['error'] == 'Fixture status detail'
    assert 'percentage' not in report


def test_activity_progress_is_attributed_by_job_even_for_identical_queries(settings, db):
    first = db.enqueue('discover', {'query': 'fictional UK cleaning', 'limit': 1})
    db.execute("UPDATE jobs SET state='done' WHERE id=?", (first,))
    second = db.enqueue('discover', {'query': 'fictional UK cleaning', 'limit': 1})
    db.event('discovery_progress', {'job_id': first, 'stage': 'google_business_check', 'company': 'First fixture'})
    for i in range(120):
        db.event('discovery_progress', {'job_id': second, 'company': 'Unrelated fixture '+str(i)})
    assert job_status(db, settings, first)['progress']['company'] == 'First fixture'
    db.event('discovery', {'job_id': first, 'lead_ids': [2, 3, 3], 'report': {'private_marker': 'not-for-activity'}})
    report = job_status(db, settings, first)
    assert report['saved_prospects'] == 2 and 'detailed research' in report['note']
    assert 'not-for-activity' not in json.dumps(report)
    assert job_status(db, settings, second).get('saved_prospects') is None


async def test_worker_records_actual_discovery_job_id_for_progress(settings, db, monkeypatch):
    from outreach.worker import execute_job
    async def discover(_settings, query, market, limit, **kwargs):
        kwargs['on_progress']({'stage': 'search', 'company': 'Fictional business'})
        return [], {'signals': [], 'queries': [query], 'errors': []}
    monkeypatch.setattr('outreach.discovery.prospect_candidates', discover)
    jid = db.enqueue('discover', {'query': 'Fictional UK cleaning', 'campaign': 'A', 'country_hint': 'UK', 'limit': 1})
    job = db.claim({'discover'})
    await execute_job(db, settings, job)
    events = [json.loads(row['detail']) for row in db.all("SELECT detail FROM events WHERE kind IN ('discovery_started','discovery_progress','discovery')")]
    assert events and all(row['job_id'] == jid for row in events)
    assert any(row.get('stage') == 'search' for row in events)


def test_activity_index_can_be_added_without_rewriting_existing_jobs_or_schema(settings, db):
    from outreach.db import DB
    jid = db.enqueue('research', {'lead_id': 1})
    before = db.one('SELECT * FROM jobs WHERE id=?', (jid,))
    db.execute('DROP INDEX events_job_activity')
    db.execute("INSERT INTO events(kind,detail,created_at) VALUES(?,?,?)", ('discovery_progress', 'legacy non-json', time.time()))
    reopened = DB(settings.database)
    assert reopened.one('SELECT * FROM jobs WHERE id=?', (jid,)) == before
    assert reopened.one('PRAGMA user_version')['user_version'] == 8
    assert reopened.one("SELECT 1 FROM sqlite_master WHERE type='index' AND name='events_job_activity'")
