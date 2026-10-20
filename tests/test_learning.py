import json
import time
import pytest

from fastapi.testclient import TestClient

from outreach.app import create_app
from outreach.campaigns import approve
from outreach.learning import report
from outreach.mail import mark_sent, record_inbound
from test_campaigns_mail import inbound


def accepted_fixture(db, cid, step=0):
    row = db.one('SELECT * FROM messages WHERE contact_id=? AND step=?', (cid, step))
    # Bookkeeping fixture only; real TLS acceptance is independently exercised by test_mail_wire.
    mark_sent(db, row, time.time() - 10)


def test_empty_learning_does_not_invent_rates_or_experiment_winners(db):
    result = report(db)
    assert result['cohorts'] == []
    assert result['totals']['smtp_accepted_records'] == 0
    assert all(value is None for value in result['totals']['rates'].values())
    assert result['totals']['sample_state'] == 'no_accepted_sample'


def test_funnel_counts_records_not_messages_and_excludes_automatic_replies(db, settings, active):
    cid = active['contact_id']
    accepted_fixture(db, cid)
    accepted_fixture(db, cid, 1)
    raw = inbound(db, 'Automatic out-of-office notice', {'Auto-Submitted': 'auto-replied'})
    record_inbound(db, raw, 'learning-auto')
    assert report(db)['totals']['human_email_reply_records'] == 0
    raw = inbound(db, 'Please send the relevant outline.')
    record_inbound(db, raw, 'learning-human')
    record_inbound(db, raw, 'learning-human')
    record_inbound(db, raw, 'learning-same-person-again')
    totals = report(db)['totals']
    assert totals['smtp_accepted_records'] == 1 and totals['smtp_accepted_messages'] == 2
    assert totals['human_email_reply_records'] == 1
    assert totals['rates']['human_email_reply_per_accepted_record'] == 1
    assert totals['qualified_sales_records'] == totals['recorded_won_records'] == 0
    assert totals['sample_state'] == 'small_sample'


def test_approval_snapshot_is_atomic_and_survives_later_business_label_changes(db, settings, prepared):
    cid, lid = prepared['contact_id'], prepared['lead_id']
    approve(db, settings, cid, 'Reviewed appropriate corporate outreach eligibility', 'Relevant website decision owner')
    snapshot = json.loads(db.one("SELECT detail FROM events WHERE kind='sequence_approved'")['detail'])['context']
    assert snapshot == {'lead_id': lid, 'campaign': 'A', 'country': 'UK', 'service': 'website_improvement',
                        'industry': '', 'prospect_kind': 'website'}
    accepted_fixture(db, cid)
    db.execute("UPDATE leads SET campaign='B',campaign_id=(SELECT id FROM campaign_groups WHERE goal='B' AND is_default=1),country='US',service='whatsapp_automation' WHERE id=?", (lid,))
    cohort = report(db)['cohorts'][0]
    assert (cohort['campaign'], cohort['country'], cohort['service']) == ('A', 'UK', 'website_improvement')
    assert cohort['attribution'] == 'approval_snapshot'


def test_legacy_approved_context_stays_unknown_instead_of_invented_historical_attribution(db, active):
    db.execute("UPDATE events SET detail=? WHERE kind='sequence_approved'", (json.dumps({'basis': 'Old approval without cohort snapshot'}),))
    accepted_fixture(db, active['contact_id'])
    cohort = report(db)['cohorts'][0]
    assert cohort['attribution'] == 'legacy_without_snapshot'
    assert cohort['campaign'] == cohort['country'] == 'unknown'
    assert cohort['service'] == 'legacy_unknown'


def test_manual_email_reply_requires_acceptance_and_non_email_conversation_not_email_response(db, active):
    lid, cid = active['lead_id'], active['contact_id']
    before = time.time() - 100
    db.execute('INSERT INTO activities(lead_id,channel,kind,note,happened_at,created_at) VALUES(?,?,?,?,?,?)',
               (lid, 'email', 'reply', 'Pre-send fictional email response', before, before))
    accepted_fixture(db, cid)
    db.execute('INSERT INTO activities(lead_id,channel,kind,note,happened_at,created_at) VALUES(?,?,?,?,?,?)',
               (lid, 'phone', 'reply', 'Fictional phone conversation', time.time(), time.time()))
    assert report(db)['totals']['human_email_reply_records'] == 0
    db.execute('INSERT INTO activities(lead_id,channel,kind,note,happened_at,created_at) VALUES(?,?,?,?,?,?)',
               (lid, 'email', 'reply', 'Post-send fictional email response', time.time(), time.time()))
    assert report(db)['totals']['human_email_reply_records'] == 1


def test_recorded_sales_funnel_retains_history_and_does_not_call_contract_value_revenue(db, active):
    lid = active['lead_id']
    accepted_fixture(db, active['contact_id'])
    for stage in ('qualified', 'won', 'completed'):
        db.event('sales_stage', {'lead_id': lid, 'stage': stage, 'operator_recorded': True})
    # Lifecycle API gates are tested separately; a later lost label must not erase reached milestones.
    db.execute("INSERT INTO sales(lead_id,stage,updated_at) VALUES(?,?,?)", (lid, 'lost', time.time()))
    result = report(db)
    assert result['totals']['qualified_sales_records'] == result['totals']['recorded_won_records'] == 1
    assert result['totals']['completed_records'] == 1
    assert result['totals']['rates']['recorded_won_per_qualified_sales_record'] == 1
    assert 'no independently verified payment' in result['definitions']['won']


def test_learning_is_authenticated_redacted_and_read_only(settings, db, active):
    accepted_fixture(db, active['contact_id'])
    client = TestClient(create_app(settings))
    assert client.get('/api/sales/report').status_code == 401
    client.headers['Authorization'] = 'Bearer ' + settings.api_token
    count = db.one('SELECT COUNT(*) n FROM events')['n']
    response = client.get('/api/sales/report')
    assert response.status_code == 200
    assert response.json()['learning']['totals']['approved_records'] == 1
    assert 'alex@bright-demo.com' not in response.text
    assert settings.api_token not in response.text and settings.admin_password not in response.text
    assert db.one('SELECT COUNT(*) n FROM events')['n'] == count


@pytest.mark.parametrize('change', ['expired', 'future', 'quote_changed', 'new_attempt'])
def test_learning_current_qualification_expires_without_erasing_accepted_history(db, active, change):
    cid, lid = active['contact_id'], active['lead_id']
    accepted_fixture(db, cid)
    assert report(db)['totals']['qualified_for_outreach'] == 1
    if change == 'expired':
        db.execute('UPDATE evidence SET fetched_at=?', (time.time()-31*86400,))
    elif change == 'future':
        db.execute('UPDATE evidence SET fetched_at=?', (time.time()+120,))
    elif change == 'quote_changed':
        db.execute("UPDATE evidence SET text='Different business details, without the reviewed source quote'")
    else:
        db.execute('INSERT INTO crawls(lead_id,report,created_at) VALUES(?,?,?)',
                   (lid, json.dumps({'status': 'partial'}), time.time()))
    result = report(db)
    assert result['totals']['qualified_for_outreach'] == 0
    assert result['totals']['approved_records'] == result['totals']['smtp_accepted_records'] == 1
    assert result['cohorts'][0]['attribution'] == 'approval_snapshot'
    assert result['cohorts'][0]['service'] == 'website_improvement'
