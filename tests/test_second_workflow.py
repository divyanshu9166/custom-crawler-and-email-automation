"""Executed checks of the second business diagram, including unsafe transitions."""
import json
import time

import pytest

from outreach import deliverables
from outreach.campaigns import review_lead
from outreach.offers import snapshot
from outreach.opportunities import proposals
from outreach.research import add_lead


def artifact_value():
    return {'kind': 'audit', 'title': 'A source-backed inquiry journey review'}


def test_artifact_cannot_use_pages_from_before_latest_failed_research(db, prepared):
    db.execute('INSERT INTO crawls(lead_id,report,created_at) VALUES(?,?,?)',
               (prepared['lead_id'], '{"status":"failed"}', time.time()+.01))
    with pytest.raises(ValueError, match='current|fresh|Source'):
        deliverables.create(db, prepared['lead_id'], artifact_value())


def test_artifact_approval_rechecks_source_changed_since_draft(db, prepared):
    aid = deliverables.create(db, prepared['lead_id'], artifact_value())
    db.execute('UPDATE evidence SET text=?,sha256=? WHERE id=?', ('Changed public source content', 'changed', prepared['evidence_id']))
    with pytest.raises(ValueError, match='current|fresh|Source'):
        deliverables.action(db, aid, 'approve')
    assert db.one('SELECT state FROM deliverables WHERE id=?', (aid,))['state'] == 'draft'


CASES = [
    ('A', 'website_build', 'We are announcing a new service.', 'website_build', 'concept'),
    ('A', 'website_improvement', 'Book a consultation with our team.', 'website_improvement', 'audit'),
    ('A', 'chatbot', 'Frequently asked questions about booking.', 'inquiry_chatbot', 'faq_demo'),
    ('B', 'store_launch', 'Our online store is launching soon.', 'store_launch', 'concept'),
    ('B', 'store_improvement', 'Add to cart to purchase our products.', 'store_improvement', 'audit'),
    ('B', 'chatbot', 'Customer support answers questions about products.', 'shopping_chatbot', 'faq_demo'),
    ('B', 'whatsapp_marketing', 'Subscribe to our WhatsApp updates.', 'whatsapp_offer', 'whatsapp_flow'),
    ('B', 'whatsapp_automation', 'Chat with us on WhatsApp about your order.', 'whatsapp_offer', 'whatsapp_flow'),
]


def fixture_review(db, campaign, service, signal):
    lid = add_lead(db, 'Fictional offer fixture', 'https://offer-fixture.example/', campaign, 'https://offer-fixture.example/')
    commerce = 'We sell our own consumer products online.'
    text = 'Our business is based in London UK. '+commerce+' '+signal
    eid = db.execute('INSERT INTO evidence(lead_id,url,title,text,sha256,fetched_at) VALUES(?,?,?,?,?,?)',
                     (lid, 'https://offer-fixture.example/', 'Fictional offer fixture', text, 'fixture-source', time.time()))
    page = db.one('SELECT * FROM evidence WHERE id=?', (eid,))
    idea = next(f for f in proposals({'campaign': campaign}, [page]) if f['service'] == service)
    review = {'company': 'Fictional offer fixture', 'country': 'UK', 'country_source': page['url'],
              'country_quote': 'based in London UK', 'timezone': 'Europe/London', 'business_type': 'corporate',
              'service': service, 'fit_notes': 'Reviewed fictional business identity and relevance to this offer.',
              'evidence_id': eid, 'quote': idea['quote'], 'observation': idea['observation'], 'suggestion': idea['suggestion'],
              'primary_goal': 'inquiries_bookings' if campaign == 'A' else 'd2c_growth',
              'selling_stage': 'starting_ecommerce' if service == 'store_launch' else 'selling_online',
              'commerce_evidence_id': eid, 'commerce_quote': commerce,
              'd2c_fit_notes': 'Fictional owned products sold directly to consumers; selling process reviewed.',
              'channel_fit_notes': 'Customer channel and permissions are not established; confirm them before any pilot.'}
    return lid, eid, review


@pytest.mark.parametrize('campaign,service,signal,node,kind', CASES)
def test_every_offer_branch_selects_one_service_and_prepares_relevant_source_proof(db, campaign, service, signal, node, kind):
    lid, eid, review = fixture_review(db, campaign, service, signal)
    review_lead(db, lid, review)
    result = snapshot(db, lid)
    states = {n['id']: n['state'] for n in result['nodes']}
    assert len(states) == 15
    assert states['input'] == states['goal'] == states['primary_offer'] == 'complete'
    assert result['selected_service'] == service and kind in result['recommended_artifacts']
    assert states[node] == ('qualification_only' if service.startswith('whatsapp_') else 'selected')
    assert len(json.loads(db.one('SELECT findings FROM leads WHERE id=?', (lid,))['findings'])) == 1
    artifact = {'kind': kind, 'title': 'Fictional source-backed proof of value', 'headline': 'A clear route to the next step',
                'intro': 'A proposed direction based on the reviewed public content.', 'primary_action': 'Explore the next step',
                'faqs': [{'evidence_id': eid, 'question': 'What does the published information say?', 'quote': signal}]}
    aid = deliverables.create(db, lid, artifact)
    assert {n['id']: n['state'] for n in snapshot(db, lid)['nodes']}['value_artifact'] == 'needs_artifact_review'
    deliverables.action(db, aid, 'approve')
    assert snapshot(db, lid)['reviewed_current_artifact_ids'] == [aid]
    body = db.one('SELECT body FROM deliverables WHERE id=?', (aid,))['body']
    if service.startswith('whatsapp_'):
        assert 'Qualification-first outline' in body and states['whatsapp_qualify'] == 'needs_qualification'
    if kind == 'faq_demo':
        assert 'human' in body.lower() or 'reach the team' in body.lower()
        assert 'not a live AI assistant' in body
    assert db.one('SELECT count(*) n FROM messages')['n'] == 0
    assert db.one('SELECT count(*) n FROM jobs')['n'] == 0


@pytest.mark.parametrize('changes,reason', [
    ({'primary_goal': 'inquiries_bookings'}, 'Primary goal'),
    ({'selling_stage': 'unknown'}, 'selling stage'),
    ({'selling_stage': 'not_d2c'}, 'selling stage'),
    ({'selling_stage': 'starting_ecommerce'}, 'store offer'),
    ({'commerce_quote': 'Invented direct-to-consumer model'}, 'D2C source'),
    ({'commerce_evidence_id': 999}, 'D2C source'),
    ({'d2c_fit_notes': 'unknown'}, 'D2C source'),
])
def test_d2c_branch_rejects_unreviewed_or_mismatched_business_model(db, changes, reason):
    lid, eid, review = fixture_review(db, 'B', 'store_improvement', 'Add to cart.')
    with pytest.raises(ValueError, match=reason):
        review_lead(db, lid, {**review, **changes})
    assert db.one('SELECT status FROM leads WHERE id=?', (lid,))['status'] == 'new'


@pytest.mark.parametrize('fit,permission,expected', [
    ('unknown', 'unknown', 'needs_qualification'), ('confirmed', 'unknown', 'needs_qualification'),
    ('unknown', 'confirmed', 'needs_qualification'), ('confirmed', 'confirmed', 'confirmed'),
])
def test_whatsapp_confirmed_and_unknown_routes_are_distinct_operator_records(db, fit, permission, expected):
    lid, eid, review = fixture_review(db, 'B', 'whatsapp_automation', 'Chat with us on WhatsApp.')
    review_lead(db, lid, {**review, 'channel_fit_status': fit, 'customer_permission_status': permission})
    states = {n['id']: n['state'] for n in snapshot(db, lid)['nodes']}
    assert states['whatsapp_fit'] == expected
    assert states['whatsapp_qualify'] == ('not_selected' if expected == 'confirmed' else 'needs_qualification')


@pytest.mark.parametrize('field', ['channel_fit_status', 'customer_permission_status'])
def test_unsuitable_whatsapp_route_requires_another_offer(db, field):
    lid, eid, review = fixture_review(db, 'B', 'whatsapp_automation', 'Chat with us on WhatsApp.')
    with pytest.raises(ValueError, match='not suitable'):
        review_lead(db, lid, {**review, field: 'not_suitable'})


def test_reselection_preserves_exactly_one_offer_and_invalidates_old_artifact_context(db):
    lid, eid, review = fixture_review(db, 'A', 'website_improvement', 'Book a consultation. Frequently asked questions about booking.')
    review_lead(db, lid, review)
    aid = deliverables.create(db, lid, artifact_value())
    review_lead(db, lid, {**review, 'service': 'chatbot', 'suggestion': 'Explore approved booking answers and a human support handoff.'})
    assert snapshot(db, lid)['selected_service'] == 'chatbot'
    assert len(json.loads(db.one('SELECT findings FROM leads WHERE id=?', (lid,))['findings'])) == 1
    with pytest.raises(ValueError, match='selected offer changed'):
        deliverables.action(db, aid, 'approve')


def test_stale_d2c_source_invalidates_selection_even_with_fresh_other_findings(db):
    lid, eid, review = fixture_review(db, 'B', 'store_improvement', 'Add to cart.')
    commerce = db.execute('INSERT INTO evidence(lead_id,url,title,text,sha256,fetched_at) VALUES(?,?,?,?,?,?)',
                         (lid, 'https://offer-fixture.example/about', 'Model', review['commerce_quote'], 'model-source', time.time()))
    review_lead(db, lid, {**review, 'commerce_evidence_id': commerce})
    db.execute('UPDATE evidence SET fetched_at=? WHERE id=?', (time.time()-31*86400, commerce))
    assert snapshot(db, lid)['selected_service'] == ''


def test_unqualified_live_like_capture_is_not_a_selected_offer(db):
    lid, eid, review = fixture_review(db, 'B', 'store_improvement', 'Add to cart.')
    before = db.all('SELECT * FROM leads')
    result = snapshot(db, lid)
    assert result['selected_service'] == '' and result['reviewed_current_artifact_ids'] == []
    assert {n['id']: n['state'] for n in result['nodes']}['input'] == 'needs_review'
    assert db.all('SELECT * FROM leads') == before


@pytest.mark.parametrize('kind', ['audit', 'concept', 'faq_demo'])
def test_expired_source_cannot_create_a_value_artifact(db, prepared, kind):
    db.execute('UPDATE evidence SET fetched_at=? WHERE id=?', (time.time()-31*86400, prepared['evidence_id']))
    with pytest.raises(ValueError, match='fresh'):
        deliverables.create(db, prepared['lead_id'], {**artifact_value(), 'kind': kind})


def test_source_change_during_artifact_preparation_is_caught_before_commit(db, prepared, monkeypatch):
    original = deliverables.source_point
    def changed(*args):
        page, quote = original(*args)
        db.execute('UPDATE evidence SET sha256=? WHERE id=?', ('changed-during-preparation', page['id']))
        return page, quote
    monkeypatch.setattr(deliverables, 'source_point', changed)
    with pytest.raises(ValueError, match='Source changed'):
        deliverables.create(db, prepared['lead_id'], artifact_value())
    assert not db.all('SELECT * FROM deliverables')


def test_historical_artifact_without_source_snapshot_cannot_be_newly_approved(db, prepared):
    aid = db.execute('INSERT INTO deliverables(lead_id,kind,title,body,evidence_ids,created_at) VALUES(?,?,?,?,?,?)',
                     (prepared['lead_id'], 'audit', 'Historical draft', 'Historical content preserved', '[]', time.time()))
    with pytest.raises(ValueError, match='snapshot is missing'):
        deliverables.action(db, aid, 'approve')


def test_profile_customer_questions_can_propose_a_handoff_offer_without_a_website():
    page = {'id': 1, 'url': 'https://facebook.com/fictional-brand', 'text': 'Frequently asked questions about booking.'}
    result = proposals({'campaign': 'A', 'lead_kind': 'profile', 'website_status': 'website_not_found'}, [page])
    assert [f['service'] for f in result] == ['chatbot']
    assert 'human handoff' in result[0]['suggestion'] and result[0]['review_required']


def test_all_sourced_b_alternatives_remain_available_before_choosing_one():
    text = 'Our online store is launching soon. Add to cart. Frequently asked questions. How do I place an order? Subscribe to our WhatsApp updates.'
    result = proposals({'campaign': 'B'}, [{'id': 1, 'url': 'https://offer-fixture.example/', 'text': text}])
    assert {f['service'] for f in result} == {'store_launch', 'store_improvement', 'chatbot', 'whatsapp_marketing', 'whatsapp_automation'}
    assert len(result) == 5 and all(f['review_required'] for f in result)


def test_offer_readout_and_d2c_validation_use_the_authenticated_api(db, settings):
    from fastapi.testclient import TestClient
    from outreach.app import create_app
    lid, eid, review = fixture_review(db, 'B', 'store_improvement', 'Add to cart.')
    client = TestClient(create_app(settings), headers={'Authorization': 'Bearer '+settings.api_token})
    assert TestClient(create_app(settings)).get(f'/api/leads/{lid}').status_code == 401
    bad = client.post(f'/api/leads/{lid}/review', json={**review, 'selling_stage': 'unknown'})
    assert bad.status_code == 400 and 'selling stage' in bad.json()['detail']
    assert client.post(f'/api/leads/{lid}/review', json=review).status_code == 200
    detail = client.get(f'/api/leads/{lid}').json()
    assert detail['offer_workflow']['selected_service'] == 'store_improvement'
    assert len(detail['offer_workflow']['nodes']) == 15
    assert detail['offer_proposals'][0]['quote'] in detail['evidence'][0]['text']
