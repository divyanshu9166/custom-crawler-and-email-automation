import json
import time
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from outreach import aftercare, finance, priorities
from outreach.app import create_app
from outreach.db import DB
from outreach.research import add_lead
from test_sales import proposal_payload, sales_payload


@pytest.fixture
def client(settings):
    return TestClient(create_app(settings), headers={'Authorization': 'Bearer ' + settings.api_token})


def entry(kind='acquisition_cost', currency='GBP', amount='20.25', reference='Fictional receipt cost 0001'):
    return {'kind': kind, 'currency': currency, 'amount': amount, 'reference': reference,
            'note': 'Fictional actually allocated transaction for protocol testing only', 'actual_transaction_confirmed': True}


def complete(client, lid):
    assert client.post(f'/api/leads/{lid}/activity', json={'channel': 'meeting', 'kind': 'reply', 'note': 'Fictional client confirmed this scoped need.'}).status_code == 200
    assert client.put(f'/api/leads/{lid}/sales', json=sales_payload(client, lid)).status_code == 200
    pid = client.post(f'/api/leads/{lid}/proposals', json=proposal_payload()).json()['id']
    assert client.post(f'/api/proposals/{pid}/approve', json={'reviewed_scope_and_terms': True}).status_code == 200
    assert client.post(f'/api/proposals/{pid}/sent', json={'reference': 'Fictional actual delivery reference', 'actually_delivered': True}).status_code == 200
    value = {**sales_payload(client, lid, 'completed'), 'proposal_id': pid,
             'agreement_reference': 'Fictional signed scope reference', 'payment_reference': 'Fictional actual initial payment',
             'acceptance_reference': 'Fictional client acceptance reference', 'outcome_notes': 'Observed outcome inconclusive; no uplift measured.'}
    assert client.put(f'/api/leads/{lid}/sales', json=value).status_code == 200


def plan(kind='maintenance'):
    return {'kind': kind, 'title': 'Fictional client continuity plan', 'scope': 'Review documented support and maintenance needs with the client.', 'due_at': time.time() + 86400}


def test_empty_finance_has_no_invented_roi_or_contract_receipts(db, client, prepared):
    assert finance.report(db)['currencies'] == []
    assert client.get('/api/sales/report').json()['finance']['currencies'] == []
    assert client.get(f"/api/leads/{prepared['lead_id']}").json()['financial_entries'] == []


def test_exact_currency_arithmetic_refunds_and_no_exchange_conversion(db, prepared):
    lid = prepared['lead_id']
    for value in (entry(), entry('delivery_cost', amount='9.75', reference='Fictional delivery cost 0002'),
                  entry('payment', amount='100.10', reference='Fictional actual receipt 0003'),
                  entry('refund', amount='0.10', reference='Fictional refund receipt 0004'),
                  entry('payment', 'USD', '200.00', 'Fictional USD receipt 0005')):
        finance.record(db, lid, value)
    currencies = {c['currency']: c for c in finance.report(db)['currencies']}
    assert currencies['GBP']['total_cost'] == '30.00'
    assert currencies['GBP']['net_receipts'] == '100.00'
    assert currencies['GBP']['recorded_contribution'] == '70.00'
    assert currencies['GBP']['recorded_return_on_cost'] == pytest.approx(70/30)
    assert currencies['GBP']['cost_per_recorded_win'] is None
    assert currencies['USD']['net_receipts'] == '200.00'
    assert currencies['USD']['recorded_return_on_cost'] is None


@pytest.mark.parametrize('amount', ['NaN', 'Infinity', '-1', '0', '0.001', '10000000000.00'])
def test_finance_rejects_invalid_money_without_saving(db, prepared, amount):
    with pytest.raises(ValueError):
        finance.record(db, prepared['lead_id'], entry(amount=amount))
    assert db.one('SELECT count(*) n FROM financial_entries')['n'] == 0


def test_duplicate_receipt_retry_is_idempotent_conflict_and_void_preserve_history(db, prepared):
    lid = prepared['lead_id']
    eid = finance.record(db, lid, entry())
    assert finance.record(db, lid, entry()) == eid
    assert db.one("SELECT count(*) n FROM events WHERE kind='financial_record'")['n'] == 1
    with pytest.raises(ValueError, match='already recorded'):
        finance.record(db, lid, entry(amount='21.25'))
    finance.void(db, eid, 'Wrong allocation recorded; corrected receipt follows')
    assert finance.report(db)['currencies'] == []
    assert finance.entries(db, lid)[0]['voided_at']
    with pytest.raises(ValueError):
        finance.void(db, eid, 'Another attempt to void same recorded receipt')
    with pytest.raises(ValueError):
        finance.record(db, lid, entry())


def test_finance_requires_actual_confirmation_and_past_time(client, db, prepared):
    lid = prepared['lead_id']
    value = entry()
    value.pop('actual_transaction_confirmed')
    assert client.post(f'/api/leads/{lid}/finance', json=value).status_code == 422
    assert client.post(f'/api/leads/{lid}/finance', json={**entry(), 'happened_at': time.time()+86400}).status_code == 400
    assert client.post('/api/leads/9999/finance', json=entry()).status_code == 400
    assert db.one('SELECT count(*) n FROM financial_entries')['n'] == 0


def test_priority_read_only_explainable_recrawl_and_suppression_reduce_readiness(db, settings, prepared):
    lid = prepared['lead_id']
    before = db.all('SELECT * FROM jobs')
    score = priorities.ranked(db, settings, lid)[0]['priority']
    assert score['score'] == 100 and score['lane'] == 'outreach_review'
    assert score['requires_approval'] and sum(r['points'] for r in score['reasons']) == 100
    db.suppress('alex@bright-demo.com', 'Explicit opt-out test fixture')
    score = priorities.ranked(db, settings, lid)[0]['priority']
    assert score['score'] == 70 and score['lane'] == 'research_review'
    db.execute('INSERT INTO crawls(lead_id,report,created_at) VALUES(?,?,?)', (lid, '{}', time.time()+1))
    score = priorities.ranked(db, settings, lid)[0]['priority']
    assert score['score'] == 0
    assert db.all('SELECT * FROM jobs') == before


def test_priority_ignores_stale_safe_and_existing_conversations(db, settings, prepared):
    lid = prepared['lead_id']
    db.execute('UPDATE contacts SET verified_at=?', (time.time()-settings.verification_max_age_hours*3600-100,))
    assert priorities.ranked(db, settings, lid)[0]['priority']['score'] == 85
    db.execute('INSERT INTO sales(lead_id,stage,cold_email_hold,updated_at) VALUES(?,?,?,?)', (lid, 'qualified', 1, time.time()))
    assert priorities.ranked(db, settings, lid)[0]['priority']['lane'] == 'existing_conversation'


def test_priority_country_source_and_quote_are_not_trusted_after_change(db, settings, prepared):
    db.execute("UPDATE evidence SET text='Contact us for a consultation. Location is not established. alex@bright-demo.com' WHERE id=?", (prepared['evidence_id'],))
    priority = priorities.ranked(db, settings, prepared['lead_id'])[0]['priority']
    assert priority['score'] == 50 and priority['lane'] == 'research_review'


def test_old_evidence_and_cross_company_safe_contact_cannot_inflate_priority(db, settings, prepared):
    lid = add_lead(db, 'Other incomplete business', 'https://other-incomplete.example.com', 'A', 'https://other-incomplete.example.com')
    assert priorities.ranked(db, settings, lid)[0]['priority']['score'] == 0
    db.execute('UPDATE evidence SET fetched_at=?', (time.time()-31*86400,))
    priority = priorities.ranked(db, settings, prepared['lead_id'])[0]['priority']
    assert priority['score'] == 0 and priority['lane'] == 'research_review'


def test_priority_newest_batch_does_not_sort_by_unverified_country_or_empty_text(db, settings, prepared):
    lid = add_lead(db, 'Unreviewed discovery', 'https://unreviewed.example.com', 'B', 'https://unreviewed.example.com', 'UK')
    ranking = priorities.ranked(db, settings)
    assert ranking[0]['id'] == prepared['lead_id']
    assert ranking[-1]['id'] == lid and ranking[-1]['priority']['score'] == 0


def test_active_sequences_are_not_ranked_as_new_outreach_work(db, settings, active):
    lid = add_lead(db, 'New research fixture', 'https://new-research.example.com', 'A', 'https://new-research.example.com')
    ranking = priorities.ranked(db, settings)
    assert ranking[0]['id'] == lid
    assert ranking[-1]['id'] == active['lead_id'] and ranking[-1]['priority']['lane'] == 'active_sequence'


def test_aftercare_requires_actual_completed_acceptance_not_won_label(client, db, prepared):
    lid = prepared['lead_id']
    assert client.post(f'/api/leads/{lid}/client-plans', json=plan()).status_code == 400
    db.execute('INSERT INTO sales(lead_id,stage,updated_at) VALUES(?,?,?)', (lid, 'completed', time.time()))
    assert client.post(f'/api/leads/{lid}/client-plans', json=plan()).status_code == 400


@pytest.mark.parametrize('kind', ['maintenance', 'expansion', 'case_study'])
def test_aftercare_order_permission_idempotency_and_optimistic_version(client, db, prepared, kind):
    lid = prepared['lead_id']
    complete(client, lid)
    value = plan(kind)
    pid = client.post(f'/api/leads/{lid}/client-plans', json=value).json()['id']
    assert client.post(f'/api/leads/{lid}/client-plans', json=value).json()['id'] == pid
    assert client.put(f'/api/client-plans/{pid}', json={'version': 0, 'state': 'completed'}).status_code == 400
    permission = {'client_permission_confirmed': True, 'permission_reference': 'Fictional client permission reference'} if kind == 'case_study' else {}
    if kind == 'case_study':
        assert client.put(f'/api/client-plans/{pid}', json={'version': 0, 'state': 'reviewed'}).status_code == 400
    assert client.put(f'/api/client-plans/{pid}', json={'version': 0, 'state': 'reviewed', **permission}).status_code == 200
    assert client.put(f'/api/client-plans/{pid}', json={'version': 0, 'state': 'reviewed', **permission}).status_code == 400
    assert client.put(f'/api/client-plans/{pid}', json={'version': 1, 'state': 'agreed', **permission}).status_code == 400
    assert client.put(f'/api/client-plans/{pid}', json={'version': 1, 'state': 'agreed', 'agreement_reference': 'Actual scope agreement fixture', **permission}).status_code == 200
    assert client.put(f'/api/client-plans/{pid}', json={'version': 2, 'state': 'completed', 'outcome_reference': 'Recorded real-world completion fixture', 'outcome_notes': 'Fictional completion, with inconclusive measured result.', **permission}).status_code == 200
    report = aftercare.report(db)
    assert report['open_plans'] == 0 and report['completed_by_kind'][kind] == 1
    assert db.one("SELECT count(*) n FROM messages WHERE state='sent'")['n'] == 0


def test_case_study_freezes_outcome_escapes_html_and_preserves_inconclusive(client, db, prepared):
    lid = prepared['lead_id']
    complete(client, lid)
    value = {**plan('case_study'), 'title': '<script>alert(1)</script> Client case study'}
    pid = client.post(f'/api/leads/{lid}/client-plans', json=value).json()['id']
    details = json.loads(db.one('SELECT details FROM sales')['details'])
    details['outcome_notes'] = 'Later edited outcome notes cannot rewrite frozen case study'
    db.execute('UPDATE sales SET details=?', (json.dumps(details),))
    export = client.get(f'/api/client-plans/{pid}/download')
    assert export.status_code == 200
    assert '<script>alert' not in export.text and '&lt;script&gt;' in export.text
    assert 'inconclusive' in export.text and 'DRAFT - internal' in export.text
    assert 'Later edited outcome' not in export.text


def test_finance_and_growth_reports_scoped_authenticated_no_automatic_side_effects(client, settings, db, prepared):
    lid = prepared['lead_id']
    assert client.post(f'/api/leads/{lid}/finance', json=entry()).status_code == 200
    other = add_lead(db, 'Other fixture business', 'https://other.example.com', 'A', 'https://other.example.com')
    assert client.get(f'/api/leads/{other}').json()['financial_report']['currencies'] == []
    before = db.all('SELECT * FROM events')
    result = client.get('/api/sales/report')
    assert result.status_code == 200 and result.json()['finance']['currencies'][0]['acquisition_cost'] == '20.25'
    assert db.all('SELECT * FROM events') == before
    unauthenticated = TestClient(create_app(settings))
    for path in ('/api/leads', '/api/sales/report', '/api/client-plans/1/download', '/static/growth.js'):
        assert unauthenticated.get(path).status_code == 401
    assert unauthenticated.post(f'/api/leads/{lid}/finance', json=entry()).status_code == 401


def test_additive_v4_upgrade_keeps_existing_mail_and_records(db, active):
    before = db.all('SELECT * FROM messages')
    db.execute('DROP TABLE financial_entries')
    db.execute('DROP TABLE client_plans')
    db.execute('PRAGMA user_version=3')
    reopened = DB(db.path)
    assert reopened.one('PRAGMA user_version')['user_version'] == 6
    assert reopened.all('SELECT * FROM messages') == before
    assert reopened.one('SELECT count(*) n FROM financial_entries')['n'] == 0


def test_finance_wins_and_void_correct_denominators_without_fee_as_income(client, db, prepared):
    lid = prepared['lead_id']
    complete(client, lid)
    eid = finance.record(db, lid, entry(amount=Decimal('20.25')))
    report = finance.report(db)['currencies'][0]
    assert report['payment'] == '0.00' and report['cost_per_recorded_win'] == '20.25'
    assert report['recorded_return_on_cost'] == -1
    finance.void(db, eid, 'Allocation corrected to the actual appropriate client')
    assert finance.report(db)['currencies'] == []
