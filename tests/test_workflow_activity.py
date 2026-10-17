import time

from outreach.workflow import execution_activity, snapshot
from outreach.workflow_detail import detailed_snapshot


def test_actual_activity_does_not_treat_next_review_as_running(db, settings, prepared):
    for result in (snapshot(db, settings, prepared['lead_id']), detailed_snapshot(db, settings, prepared['lead_id'])):
        assert result['activity']['running'] == 0
        assert result['activity']['queued'] == 0
        assert result['activity']['sending'] == 0
        assert result['activity']['worker_fresh'] is False


def test_selected_activity_uses_contact_ownership_and_excludes_global_jobs(db, settings, prepared):
    research = db.enqueue('research', {'lead_id': prepared['lead_id']})
    verify = db.enqueue('verify', {'contact_id': prepared['contact_id']})
    db.enqueue('discover', {'query': 'coffee US'})
    db.enqueue('research', {'lead_id': prepared['lead_id'] + 1})
    db.execute("UPDATE jobs SET state='running',started_at=? WHERE id=?", (time.time(), verify))
    result = execution_activity(db, settings, prepared['lead_id'])
    assert (result['running'], result['queued']) == (1, 1)
    assert [j['id'] for j in result['jobs']] == [verify, research]
    assert all(j['company'] == 'Bright Demo' for j in result['jobs'])
    assert 'payload' not in result['jobs'][0]
    assert execution_activity(db, settings)['queued'] == 3


def test_old_active_job_is_not_hidden_by_recent_completed_history(db, settings):
    running = db.enqueue('discover', {'query': 'roofers UK'})
    db.execute("UPDATE jobs SET state='running' WHERE id=?", (running,))
    for n in range(110):
        jid = db.enqueue('discover', {'query': str(n)})
        db.execute("UPDATE jobs SET state='done' WHERE id=?", (jid,))
    result = execution_activity(db, settings)
    assert result['running'] == 1
    assert result['jobs'][0]['id'] == running


def test_display_limit_does_not_truncate_active_counts(db, settings):
    for n in range(15):
        db.enqueue('discover', {'query': str(n)})
    result = execution_activity(db, settings)
    assert result['queued'] == 15
    assert len(result['jobs']) == result['display_limit'] == 12


def test_smtp_execution_is_independent_and_scoped(db, settings, prepared):
    db.execute("UPDATE messages SET state='sending' WHERE contact_id=? AND step=0", (prepared['contact_id'],))
    assert execution_activity(db, settings, prepared['lead_id'])['sending'] == 1
    assert execution_activity(db, settings, prepared['lead_id'] + 1)['sending'] == 0
    assert execution_activity(db, settings)['running'] == 0


def test_worker_freshness_does_not_claim_disabled_or_stale_worker_is_live(db, settings):
    settings.worker_enabled = True
    db.set('worker_heartbeat', str(time.time()))
    assert execution_activity(db, settings)['worker_fresh'] is True
    db.set('worker_heartbeat', str(time.time() - 300))
    assert execution_activity(db, settings)['worker_fresh'] is False
    db.set('worker_heartbeat', 'invalid')
    assert execution_activity(db, settings)['worker_fresh'] is False
    settings.worker_enabled = False
    db.set('worker_heartbeat', str(time.time()))
    assert execution_activity(db, settings)['worker_fresh'] is False
