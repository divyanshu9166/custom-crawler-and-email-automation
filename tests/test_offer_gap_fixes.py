"""Regression coverage for offer routing, uncertainty and automatic value previews."""
import json
import time

import pytest

from outreach import deliverables, diagnostics, email_writer, offers, preparation
from outreach.campaigns import create_drafts, review_lead
from outreach.app import create_app
from fastapi.testclient import TestClient
from test_second_workflow import CASES, fixture_review

REAL_GENERATE = email_writer.generate_sequence


@pytest.fixture
def client(settings):
    return TestClient(create_app(settings), headers={'Authorization': 'Bearer '+settings.api_token})

@pytest.mark.parametrize('campaign,service,signal,node,kind', CASES)
def test_automatic_proof_for_each_route_is_current_idempotent_and_unsent(db, campaign, service, signal, node, kind):
    lid, eid, review = fixture_review(db, campaign, service, signal)
    review_lead(db, lid, review)
    aid = deliverables.prepare_automatic(db, lid)
    assert deliverables.prepare_automatic(db, lid) == aid
    row = db.one('SELECT * FROM deliverables WHERE id=?', (aid,))
    assert row['kind'] == kind and row['state'] == 'draft'
    assert signal in row['body'] and 'No form was submitted' in row['body']
    assert 'Status: DRAFT' in row['body']
    deliverables.assert_current_artifact(db, row)
    assert offers.snapshot(db, lid)['prepared_current_artifact_ids'] == [aid]
    assert offers.snapshot(db, lid)['reviewed_current_artifact_ids'] == []
    assert not db.all('SELECT * FROM messages')
    assert not db.all('SELECT * FROM jobs')
    if service.startswith('whatsapp_'):
        assert 'Qualification-first outline' in row['body']


def test_generic_contact_wording_does_not_establish_an_offer(db):
    lid, eid, review = fixture_review(db, 'A', 'website_improvement', 'Book a consultation.')
    db.execute('UPDATE evidence SET text=text||? WHERE id=?', (' Contact us.', eid))
    review_lead(db, lid, {**review, 'quote': 'Contact us.'})
    result = offers.snapshot(db, lid)
    assert result['evidence_basis']['classification'] == 'insufficient_evidence'
    assert result['selected_service'] == ''
    with pytest.raises(ValueError, match='source-backed offer'):
        deliverables.prepare_automatic(db, lid)


def test_partial_audit_cannot_promote_exploratory_proposal_to_measured_problem(db, prepared):
    lead = db.one('SELECT * FROM leads WHERE id=?', (prepared['lead_id'],))
    db.event('screenshot', {'lead_id': lead['id'], 'url': lead['website'], 'complete': False,
                           'visual': {'mobileHorizontalOverflow': True}, 'issues': ['widget blocked']})
    db.event('performance', {'lead_id': lead['id'], 'url': lead['website'], 'status': 'failed',
                            'errors': [{'reason': 'HTTP 429'}]})
    basis = offers.snapshot(db, lead['id'])['evidence_basis']
    assert basis['classification'] == 'exploratory_opportunity'
    assert basis['business_pain_confirmed'] is False and basis['diagnostic_refs'] == []
    db.event('performance', {'lead_id': lead['id'], 'url': lead['website'], 'status': 'complete',
                            'strategies': {'mobile': {'final_url': lead['website'], 'score': 51}}})
    basis = offers.snapshot(db, lead['id'])['evidence_basis']
    assert basis['classification'] == 'measured_observation'
    assert basis['business_pain_confirmed'] is False and len(basis['diagnostic_refs']) == 1


def test_new_service_page_on_existing_site_is_automatically_routed_without_absence_claim(db):
    lid, eid, review = fixture_review(db, 'A', 'website_build', 'We are announcing a new service.')
    lead = db.one('SELECT * FROM leads WHERE id=?', (lid,))
    # The fixture uses an unincorporated display name; do not invent corporate status.
    review['business_type'] = 'other'
    pages = db.all('SELECT * FROM evidence WHERE lead_id=?', (lid,))
    validated = preparation._validate_review(lead, {'ready': True, 'review': review}, pages)
    review_lead(db, lid, validated, review_method='research_ai')
    assert offers.snapshot(db, lid)['context']['website_scope'] == 'new_service_page'
    aid = deliverables.prepare_automatic(db, lid)
    assert 'service-page' in db.one('SELECT body FROM deliverables WHERE id=?', (aid,))['body']
    with pytest.raises(ValueError, match='existing website'):
        review_lead(db, lid, {**review, 'website_scope': 'website_launch'})
    with pytest.raises(ValueError, match='announcement'):
        review_lead(db, lid, {**review, 'quote': 'Our business is based in London UK.'})


def test_whatsapp_writer_packets_preserve_enums_without_laundering_free_form_notes(db):
    lid, eid, review = fixture_review(db, 'B', 'whatsapp_automation', 'Chat with us on WhatsApp about your order.')
    packets = []
    for state in ['unknown', 'confirmed']:
        review_lead(db, lid, {**review, 'channel_fit_status': state, 'customer_permission_status': state})
        lead = db.one('SELECT * FROM leads WHERE id=?', (lid,))
        finding = json.loads(lead['findings'])[0]
        finding['offer_context']['d2c_fit_notes'] = 'UNSUPPORTED_SUMMARY'
        finding['channel_fit_notes'] = 'UNSUPPORTED_SUMMARY'
        finding['observation'] = 'UNSUPPORTED_SUMMARY'
        packet = email_writer.research_packet(lead, finding, db.all('SELECT * FROM evidence WHERE lead_id=?', (lid,)))
        assert 'UNSUPPORTED_SUMMARY' not in json.dumps(packet)
        assert packet['reviewed_finding']['offer_context']['customer_permission_status'] == state
        packets.append(packet)
    assert packets[0] != packets[1]
    assert packets[0]['reviewed_finding']['offer_context']['qualification_only'] is True
    assert packets[1]['reviewed_finding']['offer_context']['qualification_only'] is False
    assert offers.typed_context({'channel_fit_status': 'unknown', 'qualification_only': False})['qualification_only'] is True


def test_unknown_whatsapp_rejects_implementation_pitch_and_accepts_qualification(db):
    lid, eid, review = fixture_review(db, 'B', 'whatsapp_automation', 'Chat with us on WhatsApp about your order.')
    review_lead(db, lid, review)
    lead = db.one('SELECT * FROM leads WHERE id=?', (lid,))
    finding = json.loads(lead['findings'])[0]
    with pytest.raises(ValueError, match='qualification-first'):
        email_writer.validate_offer_intent(lead, finding, 'We can launch order updates for your customers tomorrow. Shall we start?')
    email_writer.validate_offer_intent(lead, finding, 'Could we first check whether WhatsApp fits your customers and confirm opt-in permission?')
    with pytest.raises(ValueError, match='cannot be asserted'):
        email_writer.validate_offer_intent(lead, finding, 'Could we check the pilot? Your customers have opted-in permission.')


@pytest.mark.parametrize('change', ['source', 'audit', 'body', 'expiry'])
def test_automatic_proof_invalidates_when_its_inputs_change(db, prepared, change):
    lid = prepared['lead_id']
    aid = deliverables.prepare_automatic(db, lid)
    row = db.one('SELECT * FROM deliverables WHERE id=?', (aid,))
    if change == 'source':
        db.execute('UPDATE evidence SET sha256=? WHERE id=?', ('new-hash', prepared['evidence_id']))
    elif change == 'body':
        db.execute('UPDATE deliverables SET body=body||? WHERE id=?', ('Tampered claim', aid))
        row = db.one('SELECT * FROM deliverables WHERE id=?', (aid,))
    elif change == 'expiry':
        db.execute('UPDATE evidence SET fetched_at=? WHERE id=?', (time.time()-31*86400, prepared['evidence_id']))
    else:
        lead = db.one('SELECT * FROM leads WHERE id=?', (lid,))
        db.event('performance', {'lead_id': lid, 'url': lead['website'], 'status': 'failed'})
    with pytest.raises(ValueError, match='changed|fresh|expired'):
        deliverables.assert_current_artifact(db, row)
    assert deliverables.writer_context(db, lid) == {}


def test_backfill_prepares_proof_and_preserves_edited_email_exactly(client, db, prepared):
    lid = prepared['lead_id']
    db.execute("UPDATE messages SET subject='My edited subject',body='My edited email; do not replace.' WHERE contact_id=? AND step=0", (prepared['contact_id'],))
    before = db.all('SELECT * FROM messages')
    result = client.post(f'/api/leads/{lid}/proof-preview', json={})
    assert result.status_code == 200 and result.json()['sending'] is False
    assert client.post(f'/api/leads/{lid}/proof-preview', json={}).json()['id'] == result.json()['id']
    assert db.all('SELECT * FROM messages') == before


def test_proof_creation_never_trusts_old_observation_summary(db, prepared):
    lid = prepared['lead_id']
    lead = db.one('SELECT * FROM leads WHERE id=?', (lid,))
    findings = json.loads(lead['findings'])
    findings[0]['observation'] = 'UNSUPPORTED old trial and missing forms'
    db.execute('UPDATE leads SET findings=? WHERE id=?', (json.dumps(findings), lid))
    aid = deliverables.prepare_automatic(db, lid)
    assert 'UNSUPPORTED' not in db.one('SELECT body FROM deliverables WHERE id=?', (aid,))['body']


def test_automatic_whatsapp_proof_excludes_unverified_channel_narrative(db):
    lid, eid, review = fixture_review(db, 'B', 'whatsapp_automation', 'Chat with us on WhatsApp about your order.')
    review_lead(db, lid, {**review, 'channel_fit_notes': 'UNSUPPORTED prior summary claiming all customers opted in.'})
    aid = deliverables.prepare_automatic(db, lid)
    body = db.one('SELECT body FROM deliverables WHERE id=?', (aid,))['body']
    assert 'UNSUPPORTED' not in body and 'Confirm customer channel fit' in body


def test_proof_context_reaches_writer_and_source_changes_preserve_previous_copy(db, settings, prepared, monkeypatch):
    before = db.all('SELECT * FROM messages')
    seen = []
    def writer(*args, **kwargs):
        seen.append(kwargs['proof_context'])
        assert seen[-1]['kind'] == 'audit'
        assert 'Local discussion preview' in seen[-1]['availability']
        db.execute('UPDATE deliverables SET body=body||? WHERE id=?', ('Changed during writing', seen[-1]['id']))
        kwargs['before_request']()
        pytest.fail('The changed proof must stop writing')
    monkeypatch.setattr(email_writer, 'generate_sequence', writer)
    with pytest.raises(ValueError, match='changed'):
        create_drafts(db, settings, prepared['contact_id'])
    assert db.all('SELECT * FROM messages') == before


def test_approving_proof_does_not_invalidate_its_unchanged_writer_context(db, prepared):
    lid = prepared['lead_id']
    aid = deliverables.prepare_automatic(db, lid)
    before = deliverables.writer_context(db, lid)
    deliverables.action(db, aid, 'approve')
    assert deliverables.writer_context(db, lid) == before
    lead = db.one('SELECT * FROM leads WHERE id=?', (lid,))
    assert diagnostics.snapshot(db, lead)['business_pain_confirmed'] is False


def test_automatic_proof_freezes_separate_commerce_source(db):
    lid, eid, review = fixture_review(db, 'B', 'whatsapp_automation', 'Chat with us on WhatsApp about your order.')
    commerce = review['commerce_quote']
    second = db.execute('INSERT INTO evidence(lead_id,url,title,text,sha256,fetched_at) VALUES(?,?,?,?,?,?)',
                        (lid, 'https://offer-fixture.example/shop/', 'Shop', commerce, 'commerce-hash', time.time()))
    review['commerce_evidence_id'] = second
    review_lead(db, lid, review)
    aid = deliverables.prepare_automatic(db, lid)
    db.execute('UPDATE evidence SET sha256=? WHERE id=?', ('changed-commerce', second))
    with pytest.raises(ValueError, match='Source changed'):
        deliverables.assert_current_artifact(db, db.one('SELECT * FROM deliverables WHERE id=?', (aid,)))


def test_workflow_map_requires_a_relevant_reviewed_artifact_not_every_draft_iteration(db, settings, prepared):
    from outreach.workflow_detail import detailed_snapshot
    lid = prepared['lead_id']
    unrelated = deliverables.create(db, lid, {'kind': 'faq_demo', 'title': 'Source-backed FAQ prototype',
                     'faqs': [{'evidence_id': prepared['evidence_id'], 'question': 'How can I enquire?', 'quote': 'Contact us for a consultation.'}]})
    deliverables.action(db, unrelated, 'approve')
    assert next(n for n in detailed_snapshot(db, settings, lid)['nodes'] if n['id'] == 'S')['state'] == 'review'
    aid = deliverables.prepare_automatic(db, lid)
    deliverables.action(db, aid, 'approve')
    assert next(n for n in detailed_snapshot(db, settings, lid)['nodes'] if n['id'] == 'S')['state'] == 'complete'


@pytest.mark.parametrize('claim', ['Your visitors struggle to request a quote.', 'Your quote flow has friction.', 'You are losing enquiries.',
                                  'Facilities managers who typically start the conversation are your buyers.',
                                  'Your team size suggests a high volume of inbound quote requests.'])
def test_public_service_quote_does_not_support_invented_client_pain(db, prepared, claim):
    lead = db.one('SELECT * FROM leads WHERE id=?', (prepared['lead_id'],))
    pages = db.all('SELECT * FROM evidence WHERE lead_id=?', (lead['id'],))
    value = {'messages': [{'step': 0, 'subject': 'An idea for '+lead['company'],
                           'body': claim+' Could a short review help?', 'support': [{'evidence_id': pages[0]['id'], 'quote': 'Contact us for a consultation.'}]}]}
    with pytest.raises(ValueError, match='client pain'):
        email_writer.validate_output(value, lead, {'name': ''}, pages)


@pytest.mark.parametrize('claim', ["We've been running tests for similar businesses.", 'We have helped similar clients.', 'Our clients see better results.'])
def test_writer_cannot_invent_sender_track_record(db, prepared, claim):
    lead = db.one('SELECT * FROM leads WHERE id=?', (prepared['lead_id'],))
    pages = db.all('SELECT * FROM evidence WHERE lead_id=?', (lead['id'],))
    value = {'messages': [{'step': 0, 'subject': 'An idea for '+lead['company'], 'body': claim+' Could a short assessment help?',
                           'support': [{'evidence_id': pages[0]['id'], 'quote': 'Contact us for a consultation.'}]}]}
    with pytest.raises(ValueError, match='sender experience'):
        email_writer.validate_output(value, lead, {'name': ''}, pages)


def test_failed_audit_reports_stay_internal_and_cannot_leak_into_email(db, prepared):
    lead = db.one('SELECT * FROM leads WHERE id=?', (prepared['lead_id'],))
    finding = json.loads(lead['findings'])[0]
    pages = db.all('SELECT * FROM evidence WHERE lead_id=?', (lead['id'],))
    audit = {'reports': [{'state': 'failed', 'error': 'INTERNAL_PROVIDER_ERROR'}], 'observations': []}
    packet = email_writer.research_packet(lead, finding, pages, audit)
    assert 'INTERNAL_PROVIDER_ERROR' not in json.dumps(packet) and 'reports' not in packet['audit_context']
    value = {'messages': [{'step': 0, 'subject': 'An idea for '+lead['company'],
             'body': 'The performance capture failed and the screenshot showed partial rendering issues. Could a review help?',
             'support': [{'evidence_id': pages[0]['id'], 'quote': finding['quote']}]}]}
    with pytest.raises(ValueError, match='capture failures'):
        email_writer.validate_output(value, lead, {'name': ''}, pages)


def test_real_writer_corrects_unknown_whatsapp_pitch_using_typed_context_and_real_proof(db, settings, monkeypatch):
    lid, eid, review = fixture_review(db, 'B', 'whatsapp_automation', 'Chat with us on WhatsApp about your order.')
    review_lead(db, lid, review)
    deliverables.prepare_automatic(db, lid)
    lead = db.one('SELECT * FROM leads WHERE id=?', (lid,))
    finding = json.loads(lead['findings'])[0]
    pages = db.all('SELECT * FROM evidence WHERE lead_id=?', (lid,))
    packets = []
    def chat(settings, instructions, encoded, **kwargs):
        packets.append(json.loads(encoded))
        assert 'ONLY WhatsApp offer' in instructions
        body = ('We could launch order updates for your customers immediately. Shall we start?' if len(packets) == 1 else
                'Could we first check whether WhatsApp fits your customers and confirm opt-in permission before exploring an order-support pilot?')
        return json.dumps({'messages': [{'step': 0, 'subject': 'An idea for '+lead['company'], 'body': body,
                                        'support': [{'evidence_id': eid, 'quote': finding['quote']}], 'diagnostic_refs': []}]})
    monkeypatch.setattr(email_writer, 'chat', chat)
    settings.followups_enabled = False
    settings.draft_api_key = 'fictional-test-key'
    settings.draft_model = 'fictional-test-model'
    result = REAL_GENERATE(settings, lead, {'name': '', 'email': 'hello@offer-fixture.example'}, finding, pages,
                           proof_context=deliverables.writer_context(db, lid))
    assert len(packets) == 2 and 'qualification-first' in packets[1]['validation_feedback']['error']
    assert packets[0]['reviewed_finding']['offer_context']['qualification_only'] is True
    assert result['provenance']['proof_context']['id'] == packets[0]['proof_preview']['id']
    assert 'confirm opt-in permission' in result['messages'][0]['body']
    assert not db.all('SELECT * FROM messages')
