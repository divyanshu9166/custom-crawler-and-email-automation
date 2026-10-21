"""Prospect status follows actual source jobs, never a stale review label."""
import json
import time

from fastapi.testclient import TestClient

from outreach.activity import lead_activity, source_jobs, source_job
from outreach.app import create_app
from outreach.research import add_lead


def prospect(db):
    lid = add_lead(db, 'Fictional Research Ltd', 'https://research.example.com', 'A', 'https://research.example.com')
    db.execute("UPDATE leads SET status='review' WHERE id=?", (lid,))
    return db.one('SELECT * FROM leads WHERE id=?', (lid,))


def test_queued_job_overrides_review_in_list_and_workspace_without_exposing_payload(settings, db):
    lead = prospect(db)
    jid = db.enqueue('research', {'lead_id': lead['id'], 'private_marker': 'not-for-browser'})
    client = TestClient(create_app(settings), headers={'Authorization':'Bearer '+settings.api_token})
    row = client.get('/api/leads').json()[0]
    detail = client.get('/api/leads/'+str(lead['id'])).json()
    activity = client.get('/api/leads/'+str(lead['id'])+'/activity').json()
    assert row['status'] == 'review' and row['source_job']['state'] == 'pending'
    assert activity == detail['research_activity']
    assert activity['job']['id'] == jid and not activity['worker_enabled']
    assert activity['screenshots']['state'] == 'waiting_for_research'
    assert 'not-for-browser' not in json.dumps(activity)
    assert client.get('/api/leads/99999/activity').status_code == 404
    assert TestClient(create_app(settings)).get('/api/leads/'+str(lead['id'])+'/activity').status_code == 401


def test_running_work_wins_over_newer_completed_job_and_other_prospect(settings, db):
    lead = prospect(db)
    running = db.enqueue('research', {'lead_id': lead['id']})
    db.execute("UPDATE jobs SET state='running' WHERE id=?", (running,))
    other = add_lead(db,'Other Fixture','https://other.example.com','A','https://other.example.com')
    db.enqueue('screenshot', {'lead_id': other})
    newer = db.execute("INSERT INTO jobs(kind,payload,state,due_at,created_at) VALUES(?,?,?,?,?)", ('research',json.dumps({'lead_id':lead['id']}),'done',time.time(),time.time()))
    rows = source_jobs(db, [lead['id']])[lead['id']]
    assert source_job(rows)['id'] == running
    db.execute("UPDATE jobs SET state='done' WHERE id=?", (running,))
    assert source_job(source_jobs(db, [lead['id']])[lead['id']])['id'] == newer


def test_screenshot_links_require_safe_existing_files_and_partial_is_explicit(settings, db):
    lead = prospect(db)
    folder = settings.data_dir/'screenshots'
    folder.mkdir()
    name = f"lead-{lead['id']}-123456-abcdef-desktop.png"
    (folder/name).write_bytes(b'fictional image fixture')
    db.event('screenshot', {'lead_id':lead['id'], 'url':lead['website'], 'complete':False,
        'issues':['fixture incomplete render'], 'files':{'desktop':name, 'mobile':'../../private.env','other':name}})
    activity = lead_activity(db,settings,lead)
    assert activity['screenshots']['state'] == 'partial'
    assert activity['screenshots']['files'] == {'desktop':name}
    jid = db.enqueue('screenshot', {'lead_id':lead['id']})
    assert lead_activity(db,settings,lead)['screenshots']['state'] == 'pending'
    db.execute("UPDATE jobs SET state='failed',error='Fictional capture failure' WHERE id=?", (jid,))
    capture = lead_activity(db,settings,lead)['screenshots']
    assert capture['state'] == 'failed' and capture['files'] == {'desktop':name}
    assert capture['error'] == 'Fictional capture failure'
    db.enqueue('research', {'lead_id':lead['id']})
    assert lead_activity(db,settings,lead)['screenshots']['state'] == 'waiting_for_research'
    (folder/name).unlink()
    assert lead_activity(db,settings,lead)['screenshots']['files'] == {}


def test_pages_are_not_screenshots_and_auto_capture_disabled_is_visible(settings, db):
    lead = prospect(db)
    db.execute('INSERT INTO evidence(lead_id,url,title,text,sha256,fetched_at) VALUES(?,?,?,?,?,?)',
               (lead['id'],lead['website'],'Fixture','Fixture business source','fixture',time.time()))
    settings.auto_visual_audit = False
    activity = lead_activity(db,settings,lead)
    assert activity['saved_pages'] == 1 and activity['screenshots']['files'] == {}
    assert activity['screenshots']['state'] == 'disabled'
    lead['lead_kind'] = 'profile'
    assert lead_activity(db,settings,lead)['screenshots']['state'] == 'not_applicable'


def test_source_activity_index_preserves_legacy_rows_and_report_freshness(settings, db):
    from outreach.db import DB
    lead = prospect(db)
    jid = db.enqueue('research', {'lead_id':lead['id']})
    before = db.one('SELECT * FROM jobs WHERE id=?', (jid,))
    db.execute('DROP INDEX jobs_lead_activity')
    db.execute('INSERT INTO jobs(kind,payload,state,due_at,created_at) VALUES(?,?,?,?,?)',
               ('research','legacy invalid json','done',time.time(),time.time()))
    reopened = DB(settings.database)
    assert reopened.one('SELECT * FROM jobs WHERE id=?',(jid,)) == before
    assert source_jobs(reopened,[lead['id']])[lead['id']][0]['id'] == jid
    folder=settings.data_dir/'screenshots'
    folder.mkdir()
    name=f"lead-{lead['id']}-123456-abcdef-mobile.png"
    (folder/name).write_bytes(b'fictional image fixture')
    db.event('screenshot',{'lead_id':lead['id'],'url':lead['website'],'complete':True,'files':{'mobile':name}})
    db.execute("UPDATE jobs SET state='done' WHERE id=?",(jid,))
    assert lead_activity(db,settings,lead)['screenshots']['state'] == 'complete'
    db.execute('INSERT INTO crawls(lead_id,report,created_at) VALUES(?,?,?)',(lead['id'],'{}',time.time()+1))
    assert lead_activity(db,settings,lead)['screenshots']['state'] == 'stale'
