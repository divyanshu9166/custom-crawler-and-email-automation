"""The review queue must use the same current service proof as workflow G/AA/BB."""
import json
import time

import pytest

from outreach.offers import selected_offer
from outreach.priorities import ranked


def priority(db, settings, prepared):
    before = {name: db.all('SELECT * FROM '+name) for name in ('jobs', 'messages', 'events')}
    value = ranked(db, settings, prepared['lead_id'])[0]['priority']
    assert {name: db.all('SELECT * FROM '+name) for name in before} == before
    assert value['score'] == sum(reason['points'] for reason in value['reasons'])
    assert value['requires_approval']
    return value


def test_future_research_cannot_inflate_priority(db, settings, prepared):
    db.execute('UPDATE evidence SET fetched_at=?', (time.time()+120,))
    value = priority(db, settings, prepared)
    assert value['score'] == 0 and value['lane'] == 'research_review'


@pytest.mark.parametrize('change', ['review_required', 'service_mismatch', 'campaign_mismatch',
                                    'multiple_findings', 'outside_market'])
def test_priority_rechecks_complete_selected_offer(db, settings, prepared, change):
    lead = db.one('SELECT * FROM leads WHERE id=?', (prepared['lead_id'],))
    findings = json.loads(lead['findings'])
    if change == 'review_required':
        findings[0]['review_required'] = True
    elif change == 'service_mismatch':
        findings[0]['service'] = 'website_build'
    elif change == 'campaign_mismatch':
        findings[0]['service'] = 'store_improvement'
        db.execute("UPDATE leads SET service='store_improvement' WHERE id=?", (lead['id'],))
    elif change == 'multiple_findings':
        findings.append(dict(findings[0]))
    else:
        db.execute("UPDATE leads SET country='CA' WHERE id=?", (lead['id'],))
    db.execute('UPDATE leads SET findings=? WHERE id=?', (json.dumps(findings), lead['id']))
    assert not selected_offer(db, db.one('SELECT * FROM leads WHERE id=?', (lead['id'],)))
    value = priority(db, settings, prepared)
    assert value['score'] == 50 and value['lane'] == 'research_review'
    assert 'Current business, buyer and offer review needed' in value['blockers']


def test_canonical_country_source_has_same_priority_as_workflow(db, settings, prepared):
    db.execute("UPDATE evidence SET url='https://bright-demo.com' WHERE id=?", (prepared['evidence_id'],))
    lead = db.one('SELECT * FROM leads WHERE id=?', (prepared['lead_id'],))
    assert selected_offer(db, lead) == 'website_improvement'
    value = priority(db, settings, prepared)
    assert value['score'] == 100 and value['lane'] == 'outreach_review'


@pytest.mark.parametrize('change', ['missing_source', 'removed_quote', 'future_source'])
def test_d2c_priority_rechecks_separate_commerce_evidence(db, settings, prepared, change):
    lid = prepared['lead_id']
    quote = 'We sell our own skincare products online.'
    eid = db.execute('INSERT INTO evidence(lead_id,url,title,text,sha256,fetched_at) VALUES(?,?,?,?,?,?)',
                     (lid, 'https://bright-demo.com/shop', 'Fictional store', quote, 'commerce', time.time()))
    lead = db.one('SELECT * FROM leads WHERE id=?', (lid,))
    findings = json.loads(lead['findings'])
    findings[0]['service'] = 'store_improvement'
    findings[0]['offer_context'] = {'primary_goal': 'd2c_growth', 'goal_reviewed': True,
        'selling_stage': 'selling_online', 'commerce_evidence_id': eid, 'commerce_quote': quote,
        'd2c_fit_notes': 'Fictional product ownership and shopping process reviewed for this test.'}
    db.execute("UPDATE leads SET campaign='B',campaign_id=(SELECT id FROM campaign_groups WHERE goal='B' AND is_default=1),service='store_improvement',findings=? WHERE id=?",
               (json.dumps(findings), lid))
    assert priority(db, settings, prepared)['score'] == 100
    if change == 'missing_source':
        db.execute('DELETE FROM evidence WHERE id=?', (eid,))
    elif change == 'removed_quote':
        db.execute("UPDATE evidence SET text='The consumer shop has closed',sha256='changed' WHERE id=?", (eid,))
    else:
        db.execute('UPDATE evidence SET fetched_at=? WHERE id=?', (time.time()+120, eid))
    assert not selected_offer(db, db.one('SELECT * FROM leads WHERE id=?', (lid,)))
    value = priority(db, settings, prepared)
    assert value['score'] == 50 and value['lane'] == 'research_review'
