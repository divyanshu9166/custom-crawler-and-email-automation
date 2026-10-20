"""Calling offers use a published task, never invented missed calls or a lab score."""
import json

import pytest

from outreach import calling, email_writer, offers, preparation, deliverables
from outreach.campaigns import review_lead, create_drafts
from outreach.opportunities import proposals
from outreach.research import add_contact
from test_second_workflow import fixture_review

REAL_GENERATE = email_writer.generate_sequence


@pytest.mark.parametrize('quote,mode', [
    ('Call us for a quote about your project.', 'lead_qualification'),
    ('For appointments call 020 1234 5678 to book your visit.', 'booking'),
    ('Request a callback to discuss your requirements and get a quote.', 'lead_qualification'),
    ('Telephone our customer support team with service questions.', 'customer_support'),
])
def test_positive_task_selects_a_specific_calling_flow(quote, mode):
    plan = calling.pitch_plan(quote)
    assert plan['use_case'] == mode and plan['quote'] in quote
    assert plan['scope'] == 'inbound_or_requested_callback'
    assert plan['intended_benefit'] and 'human' in plan['proposed_work']


@pytest.mark.parametrize('quote', [
    'Get a Quote', 'Contact us. Tel: 020 1234 5678.',
    'We offer bookings online. Phone: 020 1234 5678.',
    'Do not call us for a quote.', 'We do not offer phone bookings.',
    'Call our emergency helpline for an appointment.',
    'For recruitment questions call our team.',
    'No phone bookings; use our online form.',
])
def test_bare_numbers_negation_unrelated_and_emergency_routes_are_insufficient(quote):
    assert calling.source_signal(quote) is None
    with pytest.raises(ValueError, match='phone/callback route'):
        calling.pitch_plan(quote)


@pytest.mark.parametrize('campaign', ['A', 'B'])
def test_candidate_discovery_requires_the_right_campaign_and_official_task(campaign):
    page = {'id': 1, 'url': 'https://bright-demo.com/contact', 'text': 'Call us to book an appointment.'}
    result = proposals({'campaign': campaign, 'website': 'https://bright-demo.com/'}, [page])
    voice = [p for p in result if p['service'] == 'ai_calling_agent']
    assert bool(voice) == (campaign == 'A')
    if voice:
        assert voice[0]['quote'] in page['text'] and voice[0]['review_required']
    assert not proposals({'campaign': campaign, 'website': 'https://bright-demo.com/'}, [{**page, 'url': 'https://unrelated.example/contact'}])


def voice_review(db, quote='Call us for a quote about your cleaning requirements.'):
    lid, eid, review = fixture_review(db, 'A', 'ai_calling_agent', quote)
    review_lead(db, lid, review)
    return lid, eid, review


def test_automatic_assessment_accepts_support_and_infers_mode_without_an_extra_form(db):
    lid, eid, review = voice_review(db, 'Telephone our customer support team with service questions.')
    lead = db.one('SELECT * FROM leads WHERE id=?', (lid,))
    pages = db.all('SELECT * FROM evidence WHERE lead_id=?', (lid,))
    validated = preparation._validate_review(lead, {'ready': True, 'review': {**review, 'business_type': 'other'}}, pages)
    assert validated['service'] == 'ai_calling_agent'
    state = offers.snapshot(db, lid)
    assert state['context']['calling_use_case'] == 'customer_support'
    assert state['calling_plan']['intended_benefit']
    assert state['evidence_basis']['classification'] == 'exploratory_opportunity'


def test_campaign_b_cannot_qualify_a_calling_agent_even_with_a_phone_signal(db):
    lid, eid, review = voice_review(db)
    db.execute("UPDATE leads SET campaign='B',campaign_id=(SELECT id FROM campaign_groups WHERE goal='B' AND is_default=1) WHERE id=?", (lid,))
    with pytest.raises(ValueError, match='Campaign B'):
        review_lead(db, lid, review)
    assert offers.snapshot(db, lid)['selected_service'] == ''


def test_number_alone_cannot_qualify_or_prepare_a_calling_pitch(db):
    lid, eid, review = voice_review(db)
    quote = 'Tel: 020 1234 5678. Contact us.'
    db.execute('UPDATE evidence SET text=text||? WHERE id=?', (' '+quote, eid))
    with pytest.raises(ValueError, match='phone/callback route'):
        review_lead(db, lid, {**review, 'quote': quote})


GOOD = 'Your published phone route invites quote enquiries. We can build an AI calling agent to ask callers about service, location and timeline, then pass a useful summary to your team. The aim is to give your team the details needed to assess fit before following up, with a human handoff when needed. Would a short example call flow for Fictional offer fixture be useful?'


def validate(db, body=GOOD, support_quote=None, refs=None):
    existing = db.one('SELECT * FROM leads LIMIT 1')
    if existing:
        lid = existing['id']
        review = json.loads(existing['findings'])[0]
        eid = review['evidence_id']
    else:
        lid, eid, review = voice_review(db)
    lead = db.one('SELECT * FROM leads WHERE id=?', (lid,))
    finding = json.loads(lead['findings'])[0]
    evidence = db.all('SELECT * FROM evidence WHERE lead_id=?', (lid,))
    value = {'messages': [{'step': 0, 'subject': 'A phone enquiry idea for '+lead['company'], 'body': body,
                         'support': [{'evidence_id': eid, 'quote': support_quote or review['quote']}], 'diagnostic_refs': refs or []}]}
    return email_writer.validate_output(value, lead, {'name': ''}, evidence, finding=finding)


def test_initial_pitch_explains_concrete_help_not_just_ai_hype(db):
    assert validate(db)[0]['step'] == 0
    with pytest.raises(ValueError, match='concrete collection'):
        validate(db, 'An AI agent could transform your business. Would you like to discuss it?')


@pytest.mark.parametrize('claim', ['Your missed calls are costing you sales.', 'You are losing leads every day.',
                                  'Your staff are overwhelmed.', 'Never miss another call.',
                                  'We are already connected to your calendar.'])
def test_calling_pitch_cannot_invent_pain_or_existing_integration(db, claim):
    with pytest.raises(ValueError, match='invented operational pain'):
        validate(db, claim+' '+GOOD)


def test_phone_task_must_be_cited_not_just_a_generic_company_quote(db):
    with pytest.raises(ValueError, match='phone-process quote'):
        validate(db, support_quote='based in London UK')


def test_calling_pitch_cannot_invent_an_ongoing_sender_pilot(db):
    with pytest.raises(ValueError, match='sender deployment or ongoing pilot'):
        validate(db, "We're testing an AI calling agent. "+GOOD)


def test_real_writer_contract_prepares_one_unsent_email_and_mode_specific_proof(db, settings, monkeypatch):
    lid, eid, review = voice_review(db)
    db.execute('UPDATE evidence SET text=text||? WHERE id=?', (' hello@offer-fixture.example', eid))
    cid = add_contact(db, lid, 'hello@offer-fixture.example', review['country_source'])
    settings.sending_enabled = settings.followups_enabled = False
    settings.draft_api_key, settings.draft_model = 'fictional-key', 'fictional-model'
    db.event('performance', {'lead_id': lid, 'status': 'complete', 'url': review['country_source'],
                             'strategies': {'mobile': {'score': 40, 'final_url': review['country_source']}}})
    calls = []
    def chat(s, instructions, encoded, **kw):
        kw['before_request']()
        packet = json.loads(encoded)
        calls.append(packet)
        assert packet['calling_plan']['use_case'] == 'lead_qualification'
        assert not packet['audit_context']['observations']
        assert not packet['conclusion']['findings']
        assert 'missed calls' in instructions and 'font-loading' not in instructions
        return json.dumps({'messages': [{'step': 0, 'subject': 'A phone enquiry idea for Fictional offer fixture',
            'body': GOOD, 'support': [{'evidence_id': eid, 'quote': review['quote']}], 'diagnostic_refs': []}]})
    monkeypatch.setattr(email_writer, 'chat', chat)
    monkeypatch.setattr(email_writer, 'generate_sequence', REAL_GENERATE)
    create_drafts(db, settings, cid)
    assert len(calls) == 1
    messages = db.all('SELECT * FROM messages WHERE contact_id=?', (cid,))
    assert len(messages) == 1 and messages[0]['state'] == 'draft'
    assert messages[0]['due_at'] is messages[0]['sent_at'] is None
    artifact = db.one('SELECT * FROM deliverables WHERE lead_id=?', (lid,))
    assert artifact['kind'] == 'call_flow' and artifact['state'] == 'draft'
    assert 'No phone calls' in artifact['body'] and 'Lighthouse' not in artifact['body']
    deliverables.assert_current_artifact(db, artifact)
    assert not db.all('SELECT * FROM jobs')
