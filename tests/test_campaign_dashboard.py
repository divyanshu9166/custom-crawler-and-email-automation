"""Named campaign attribution, aggregate accuracy and bounded bulk actions."""
import csv
import io
import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from outreach.app import create_app
from outreach.campaign_manager import bulk, create, prospects, set_state, summary
from outreach.db import DB
from outreach.mail import send_one, smtp_send
from outreach.research import add_lead
from test_campaigns_mail import ready


def client(settings):
    return TestClient(create_app(settings), headers={'Authorization': 'Bearer ' + settings.api_token})


def test_default_groups_backfill_existing_records_without_changing_drafts(db, settings, prepared):
    assert len(summary(db)['campaigns']) == 2
    before = db.all('SELECT * FROM messages')
    db.execute('UPDATE leads SET campaign_id=NULL')
    DB(settings.database)
    assert db.one('SELECT campaign_id FROM leads')['campaign_id']
    assert db.all('SELECT * FROM messages') == before


def test_create_named_campaign_and_direct_ingestion_goal_validation(db, settings):
    c = client(settings)
    cid = c.post('/api/campaigns', json={'name': 'UK Cleaning - October', 'goal': 'A'}).json()['id']
    response = c.post('/api/leads', json={'company': 'Synthetic Cleaner', 'website': 'https://cleaner-fixture.com', 'source_url': 'https://cleaner-fixture.com', 'campaign': 'A', 'campaign_id': cid})
    assert response.status_code == 200
    assert db.one('SELECT campaign_id FROM leads')['campaign_id'] == cid
    assert c.post('/api/campaigns', json={'name': 'uk cleaning - october', 'goal': 'A'}).status_code == 400
    assert c.post('/api/discover', json={'query': 'Fictional product shops in UK', 'campaign': 'B', 'country_hint': 'UK', 'campaign_id': cid}).status_code == 400
    assert c.post('/api/campaigns', json={'name': '   ', 'goal': 'A'}).status_code == 400


def test_aggregation_does_not_multiply_contacts_or_messages(db, active):
    lid = active['lead_id']
    db.execute("UPDATE messages SET state='sent',sent_at=100 WHERE step IN (0,1)")
    db.execute("UPDATE contacts SET delivery_state='REPLIED'")
    db.execute("INSERT INTO contacts(lead_id,email,source_url,unsubscribe_token,created_at,delivery_state) VALUES(?,?,?,?,?,'BOUNCED')",
               (lid, 'other@bright-demo.com', 'https://bright-demo.com', 'other-unique', 1))
    totals = summary(db)['totals']
    assert (totals['prospects'], totals['contacts'], totals['sent'], totals['replied'], totals['bounced']) == (1, 2, 2, 1, 1)
    assert totals['queued'] == 2


def test_move_only_unapproved_same_goal_prospects(db, settings, prepared):
    target = create(db, 'Named UK test', 'A')
    other = create(db, 'Store test', 'B')
    lid = prepared['lead_id']
    assert bulk(db, settings, [lid], 'assign', campaign_id=other)['succeeded'] == 0
    assert bulk(db, settings, [lid], 'assign', campaign_id=target)['succeeded'] == 1
    assert db.one('SELECT campaign_id FROM leads')['campaign_id'] == target
    assert db.one('SELECT COUNT(*) n FROM messages')['n'] == 4
    with pytest.raises(sqlite3.IntegrityError):
        db.execute('UPDATE leads SET campaign_id=?', (other,))


def test_approved_outreach_cannot_move_and_rewrite_campaign_results(db, settings, active):
    target = create(db, 'Another batch', 'A')
    before = db.one('SELECT campaign_id FROM leads')['campaign_id']
    result = bulk(db, settings, [active['lead_id']], 'assign', campaign_id=target)
    assert result['succeeded'] == 0 and 'attribution' in result['results'][0]['reason']
    assert db.one('SELECT campaign_id FROM leads')['campaign_id'] == before


def test_campaign_pause_stops_sending_and_resume_keeps_global_controls(db, settings, active):
    now = ready(db, active['contact_id'])
    cid = db.one('SELECT campaign_id FROM leads')['campaign_id']
    set_state(db, cid, 'paused')
    assert send_one(db, settings, now, lambda *_: pytest.fail('Paused campaign')) == 'idle'
    assert db.one("SELECT state FROM messages WHERE step=0")['state'] == 'queued'
    set_state(db, cid, 'active')
    assert settings.sending_enabled is True
    db.set('paused', 'true')
    assert send_one(db, settings, now, lambda *_: pytest.fail('Global pause')) == 'disabled'


@pytest.mark.parametrize('action', ['pause', 'delete'])
def test_campaign_stop_during_login_blocks_data(db, settings, active, monkeypatch, action):
    now = ready(db, active['contact_id'])
    class SMTP:
        def __init__(self, *a, **kw):
            pass
        def ehlo(self):
            pass
        def starttls(self, **kw):
            pass
        def login(self, *a):
            if action == 'pause':
                set_state(db, db.one('SELECT campaign_id FROM leads')['campaign_id'], 'paused')
            else:
                bulk(db, settings, [active['lead_id']], 'delete', 'No longer a target')
        def send_message(self, *_):
            pytest.fail('Stopped campaign must not reach DATA')
        def quit(self):
            pass
    monkeypatch.setattr('outreach.mail.smtplib.SMTP', SMTP)
    assert send_one(db, settings, now, smtp_send) == 'cancelled'
    assert db.one('SELECT state FROM messages WHERE step=0')['state'] == ('queued' if action == 'pause' else 'cancelled')


def test_delete_preserves_sent_history_and_suppression_restore_never_resumes(db, settings, active):
    now = ready(db, active['contact_id'])
    assert send_one(db, settings, now, lambda *_: None) == 'sent'
    db.suppress('alex@bright-demo.com', 'opt_out')
    bulk(db, settings, [active['lead_id']], 'delete', 'Operator removed this prospect')
    report = summary(db)['totals']
    assert report['sent'] == report['deleted'] == report['unsubscribed'] == 1
    assert prospects(db)['total'] == 0
    assert prospects(db, deleted='deleted')['total'] == 1
    assert client(settings).get('/api/leads').json() == []
    bulk(db, settings, [active['lead_id']], 'restore')
    assert db.one('SELECT status FROM contacts')['status'] == 'suppressed'
    assert db.one('SELECT delivery_state FROM contacts')['delivery_state'] == 'UNSUBSCRIBED'
    assert db.one('SELECT COUNT(*) n FROM suppression')['n'] == 1
    assert not db.one("SELECT 1 FROM messages WHERE state='queued'")


def test_delete_cancels_jobs_reimport_and_new_jobs_are_blocked(db, settings, active):
    job = db.enqueue('verify', {'contact_id': active['contact_id']})
    bulk(db, settings, [active['lead_id']], 'delete', 'Remove from this list')
    assert db.one('SELECT state FROM jobs WHERE id=?', (job,))['state'] == 'cancelled'
    with pytest.raises(ValueError, match='Deleted'):
        db.enqueue('research', {'lead_id': active['lead_id']})
    with pytest.raises(ValueError, match='deleted'):
        add_lead(db, 'Same company', 'https://bright-demo.com', 'A', 'https://bright-demo.com')
    bulk(db, settings, [active['lead_id']], 'restore')
    assert db.one('SELECT status FROM contacts')['status'] == 'hold'
    assert not db.one("SELECT 1 FROM messages WHERE state='queued'")


def test_pagination_filters_and_export_cover_more_than_pipeline_page(db, settings):
    for n in range(515):
        add_lead(db, f'Fixture {n}', f'https://fixture-{n}.com', 'A', f'https://fixture-{n}.com')
    first = prospects(db, limit=50)
    second = prospects(db, limit=50, offset=50)
    assert first['total'] == 515 and len(first['rows']) == len(second['rows']) == 50
    assert not ({r['id'] for r in first['rows']} & {r['id'] for r in second['rows']})
    c = client(settings)
    csv_rows = list(csv.DictReader(io.StringIO(c.get('/api/campaign-export').text)))
    assert len(csv_rows) == 515
    assert c.get('/api/campaign-prospects?state=invalid').status_code == 400
    assert c.get('/api/campaign-prospects?limit=201').status_code == 422
    assert c.get('/api/campaign-prospects?search=Fixture%20114').json()['total'] == 1


def test_bulk_is_bounded_authenticated_and_reports_partial_failures(db, settings, prepared):
    c = client(settings)
    assert TestClient(create_app(settings)).get('/api/campaigns').status_code == 401
    assert c.post('/api/campaign-prospects/bulk', json={'action': 'delete', 'lead_ids': list(range(1, 202)), 'reason': 'test'}).status_code == 422
    result = c.post('/api/campaign-prospects/bulk', json={'action': 'delete', 'lead_ids': [prepared['lead_id'], 999], 'reason': 'Removed from outreach'}).json()
    assert result['succeeded'] == 1 and len(result['results']) == 2
    assert 'suppression' in result['note']
    response = c.get('/api/campaigns').json()
    assert response['totals']['deleted'] == 1
    assert 'unsubscribe_token' not in json.dumps(response)


def test_recurring_search_keeps_named_campaign_and_legacy_payloads_unchanged(db, settings):
    target = create(db, 'Recurring batch', 'B')
    c = client(settings)
    response = c.post('/api/schedules', json={'query': 'Fictional D2C stores', 'campaign': 'B', 'country_hint': 'US', 'campaign_id': target})
    assert response.status_code == 200
    assert db.one('SELECT campaign_id FROM schedules')['campaign_id'] == target


async def test_discovery_imports_directly_into_named_campaign(db, settings, monkeypatch):
    from outreach.research import discover_leads
    target = create(db, 'US D2C discovery', 'B')
    async def candidates(_settings, _query, _country, _limit, *, on_candidate, **kwargs):
        row = {'url': 'https://store-fixture.com/', 'title': 'Fictional store'}
        on_candidate(row)
        return [row], {'signals': []}
    monkeypatch.setattr('outreach.discovery.prospect_candidates', candidates)
    await discover_leads(db, settings, 'Fictional stores', 'B', 'US', 3, campaign_id=target)
    assert db.one('SELECT campaign_id FROM leads')['campaign_id'] == target
    report = db.one("SELECT detail FROM events WHERE kind='discovery'")
    assert json.loads(report['detail'])['campaign_id'] == target


def test_profile_and_csv_inputs_can_target_named_campaigns(db, settings):
    target = create(db, 'Named source imports', 'A')
    c = client(settings)
    assert c.post('/api/profile-leads', json={'company': 'Profile fixture', 'profile_url': 'https://www.facebook.com/campaign-fixture',
                  'campaign': 'A', 'country_hint': 'UK', 'campaign_id': target}).status_code == 200
    content = f'company,website,campaign,source_url,campaign_id\nCSV Fixture,https://csv-fixture.com,A,https://csv-fixture.com,{target}\n'
    result = c.post('/api/import', json={'content': content}).json()
    assert len(result['ids']) == 1 and result['errors'] == []
    assert db.one('SELECT COUNT(*) n FROM leads WHERE campaign_id=?', (target,))['n'] == 2
