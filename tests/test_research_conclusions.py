"""Problem-led pitches need evidence and a matching, bounded proposed fix."""
import json
import time

import pytest

from outreach import conclusions, diagnostics, email_writer, preparation
from outreach.campaigns import archive_followups, create_drafts
from outreach.deliverables import prepare_automatic

REAL_GENERATE = email_writer.generate_sequence


def audit(db, lid, *, failed=False):
    db.event('performance', {'lead_id': lid, 'url': 'https://bright-demo.com/',
        'status': 'failed' if failed else 'complete', 'errors': [{'reason': 'HTTP 429'}] if failed else [],
        'strategies': {} if failed else {'mobile': {'score': 51, 'final_url': 'https://bright-demo.com/',
            'metrics': {'largest-contentful-paint': {'numericValue': 4800, 'numericUnit': 'millisecond'}}}}})


@pytest.mark.parametrize('state', ['absent', 'quota', 'stale', 'partial', 'different_target'])
def test_raw_research_is_not_a_problem_and_held_writer_preserves_edits(db, settings, prepared, monkeypatch, state):
    lid, cid = prepared['lead_id'], prepared['contact_id']
    settings.followups_enabled = False
    archive_followups(db, cid)
    db.execute("UPDATE messages SET body='My human reviewed wording' WHERE step=0")
    before = db.all('SELECT * FROM messages')
    if state in {'quota', 'stale', 'different_target'}:
        audit(db, lid, failed=state == 'quota')
        if state == 'stale':
            db.execute("UPDATE events SET created_at=? WHERE kind='performance'", (time.time()-8*86400,))
        if state == 'different_target':
            row = db.one("SELECT id,detail FROM events WHERE kind='performance'")
            data = json.loads(row['detail']); data['url'] = 'https://another-demo.com/'
            db.execute('UPDATE events SET detail=? WHERE id=?', (json.dumps(data), row['id']))
    if state == 'partial':
        db.event('screenshot', {'lead_id': lid, 'url': 'https://bright-demo.com/', 'complete': False,
            'issues': [{'reason': 'blocked_widget'}], 'visual': {'mobileHorizontalOverflow': True}})
    settings.draft_model, settings.draft_api_key = 'fictional-model', 'fictional-key'
    monkeypatch.setattr(email_writer, 'generate_sequence', REAL_GENERATE)
    monkeypatch.setattr(email_writer, 'chat', lambda *a, **k: pytest.fail('Must hold before provider call'))
    with pytest.raises(ValueError, match='no current reproducible finding'):
        create_drafts(db, settings, cid)
    assert db.all('SELECT * FROM messages') == before
    lead = db.one('SELECT * FROM leads WHERE id=?', (lid,))
    conclusion = diagnostics.snapshot(db, lead)['conclusion']
    assert conclusion['state'] == 'needs_evidence' and not conclusion['draft_allowed']


def test_current_lab_finding_drives_fix_packet_and_reproducible_artifact(db, prepared):
    lid = prepared['lead_id']
    audit(db, lid)
    lead = db.one('SELECT * FROM leads WHERE id=?', (lid,))
    context = diagnostics.snapshot(db, lead)
    conclusion = context['conclusion']
    assert conclusion['state'] == 'finding_ready' and conclusion['draft_allowed']
    finding = conclusion['findings'][0]
    assert 'largest visible element' in finding['proposed_fix']
    assert '2,500 ms' in finding['verification']
    assert finding['supporting_measurements'][0] == {'metric': 'largest-contentful-paint', 'numericValue': 4800, 'numericUnit': 'millisecond'}
    assert 'mobile strategy' in finding['reproduce']
    assert not conclusion['business_pain_confirmed']
    packet = email_writer.research_packet(lead, json.loads(lead['findings'])[0], db.all('SELECT * FROM evidence'), context)
    copy_conclusion = json.loads(json.dumps(conclusion))
    for item in copy_conclusion['findings']:
        item.pop('supporting_measurements', None)
    assert packet['conclusion'] == copy_conclusion
    assert finding['supporting_measurements']  # Measurements remain in the audit/artifact, not the sales readout.
    assert packet['reviewed_finding']['suggestion'] == finding['proposed_fix']
    artifact_id = prepare_automatic(db, lid)
    artifact = db.one('SELECT body FROM deliverables WHERE id=?', (artifact_id,))
    assert finding['proposed_fix'] in artifact['body'] and finding['verification'] in artifact['body']
    audit(db, lid, failed=True)
    assert not diagnostics.snapshot(db, lead)['conclusion']['draft_allowed']


def test_complete_overflow_maps_to_layout_fix_with_matching_capture(db, prepared):
    lid = prepared['lead_id']
    name = f'lead-{lid}-1792348580-13a929-mobile.png'
    db.event('screenshot', {'lead_id': lid, 'url': 'https://bright-demo.com/', 'complete': True,
        'issues': [], 'files': {'mobile': name, 'desktop': '../unrelated.png'},
        'visual': {'mobileHorizontalOverflow': True}})
    value = diagnostics.snapshot(db, db.one('SELECT * FROM leads WHERE id=?', (lid,)))['conclusion']
    finding = value['findings'][0]
    assert finding['screenshot'] == name
    assert '390px' in finding['reproduce'] and 'wrapping' in finding['proposed_fix']


def test_source_led_other_offers_do_not_claim_a_technical_problem():
    result = conclusions.require_finding({}, 'chatbot')
    assert result['draft_allowed'] and result['state'] == 'opportunity_only'
    assert not result['business_pain_confirmed']


@pytest.mark.parametrize('specific_help', [False, True, 'review_only'])
def test_font_pitch_needs_implementation_and_intended_benefit(db, prepared, specific_help):
    lid = prepared['lead_id']
    audit(db,lid)
    event = db.one("SELECT id,detail FROM events WHERE kind='performance'")
    report = json.loads(event['detail'])
    report['strategies']['mobile']['opportunities'] = [{'id':'font-display-insight'}]
    db.execute('UPDATE events SET detail=? WHERE id=?',(json.dumps(report),event['id']))
    lead = db.one('SELECT * FROM leads WHERE id=?',(lid,))
    context = diagnostics.snapshot(db,lead)
    body = 'Bright Demo scored 51/100 in a mobile Lighthouse lab test. '
    body += ('I can adjust the flagged font-loading rules so text appears sooner, then retest text and icons. Would a short walkthrough be useful?' if specific_help is True else
             'We can review the font-loading rules so text remains visible while fonts load. After the change we would repeat the same lab strategy. Would a call be useful?' if specific_help == 'review_only' else
             'Would reviewing the performance score and font finding be useful?')
    value = {'messages':[{'step':0,'subject':'Bright Demo mobile finding','body':body,
        'diagnostic_refs':[context['observations'][0]['ref']],
        'support':[{'evidence_id':prepared['evidence_id'],'quote':'Contact us for a consultation.'}]}]}
    contact = db.one('SELECT * FROM contacts WHERE id=?',(prepared['contact_id'],))
    if specific_help is True:
        assert email_writer.validate_output(value,lead,contact,db.all('SELECT * FROM evidence'),audit_context=context)
    else:
        with pytest.raises(ValueError,match='concrete help'):
            email_writer.validate_output(value,lead,contact,db.all('SELECT * FROM evidence'),audit_context=context)


@pytest.mark.parametrize('opportunity,fragment', [('font-display-insight', 'font-display fallback'),
    ('render-blocking-insight', 'critical styles'), ('untrusted-random-claim', 'largest visible element')])
def test_only_supported_positive_insights_change_the_proposed_fix(db, prepared, opportunity, fragment):
    lid = prepared['lead_id']
    audit(db, lid)
    event = db.one("SELECT id,detail FROM events WHERE kind='performance'")
    report = json.loads(event['detail'])
    report['strategies']['mobile']['opportunities'] = [{'id': opportunity, 'title': 'UNTRUSTED TITLE'}]
    report['report_url'] = 'https://pagespeed.web.dev/analysis/example/report?form_factor=mobile'
    db.execute('UPDATE events SET detail=? WHERE id=?', (json.dumps(report), event['id']))
    value = diagnostics.snapshot(db, db.one('SELECT * FROM leads WHERE id=?', (lid,)))
    assert fragment in value['conclusion']['findings'][0]['proposed_fix']
    assert 'UNTRUSTED TITLE' not in json.dumps(value)
    assert value['conclusion']['findings'][0]['report_url'] == report['report_url']


def test_automatic_preparation_holds_unsupported_improvement_without_changing_review(db, settings, prepared, monkeypatch):
    lid = prepared['lead_id']
    db.execute('DELETE FROM messages')
    settings.draft_api_key, settings.draft_model = 'fictional-key', 'fictional-model'
    lead = db.one('SELECT * FROM leads WHERE id=?', (lid,))
    finding = json.loads(lead['findings'])[0]
    review = {**finding, **{key: lead[key] for key in
        ('company', 'country', 'country_source', 'timezone', 'business_type', 'service', 'fit_notes')},
        'primary_goal': 'inquiries_bookings', 'business_type': 'other'}
    from outreach.app import ReviewInput
    review = {key: value for key, value in review.items() if key in ReviewInput.model_fields}
    monkeypatch.setattr(preparation, '_assessment', lambda *a: {'ready': True, 'review': review})
    monkeypatch.setattr(email_writer, 'generate_sequence', lambda *a, **k: pytest.fail('Unsupported offer must be held'))
    preparation.prepare(db, settings, lid)
    assert preparation.latest(db, lid)['result']['state'] == 'needs_evidence'
    assert db.one('SELECT * FROM leads WHERE id=?', (lid,)) == lead
    assert not db.all('SELECT * FROM messages')
