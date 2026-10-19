import json
import time

import pytest
from fastapi.testclient import TestClient

from outreach import email_writer, pitch_strategy as strategy
from outreach.app import create_app
from outreach.campaigns import archive_followups, create_drafts

REAL_GENERATE = email_writer.generate_sequence


def page(text, eid=1, url='https://bright-demo.com/'):
    return {'id': eid, 'url': url, 'text': text, 'title': 'Official business page',
            'sha256': 'fictional-context', 'fetched_at': time.time()}


def inputs(text):
    lead = {'company': 'Bright Demo', 'campaign': 'A', 'service': 'website_improvement',
            'website': 'https://bright-demo.com/', 'domain': 'bright-demo.com', 'lead_kind': 'website'}
    finding = {'service': lead['service'], 'evidence_id': 1, 'quote': 'Book a consultation.'}
    return lead, finding, [page('Book a consultation. '+text)]


def test_existing_chatbot_is_preserved_with_conditional_calling_addition():
    lead, finding, pages = inputs('By EnquiryBot. Phone 0330 094 7733.')
    plan = strategy.build(lead, finding, pages)
    assert plan['primary_service'] == 'website_improvement'
    assert plan['chatbot_status'] == 'present'
    assert [o['service'] for o in plan['optional_services']] == ['ai_calling_agent']
    assert plan['optional_services'][0]['status'] == 'optional_fit_check'
    assert plan['ui_design_status'] == 'not_established_by_speed_test'
    assert not plan['conversion_loss_confirmed']


def test_questions_can_support_optional_chatbot_without_claiming_it_is_missing():
    lead, finding, pages = inputs('Frequently asked questions about booking. Phone 0330 094 7733.')
    plan = strategy.build(lead, finding, pages)
    assert plan['chatbot_status'] == 'unknown'
    assert {o['service'] for o in plan['optional_services']} == {'chatbot', 'ai_calling_agent'}
    assert all(o['status'] == 'optional_fit_check' for o in plan['optional_services'])


def test_a_published_phone_task_supports_a_more_specific_addition():
    lead, finding, pages = inputs('Call us to book an appointment.')
    plan = strategy.build(lead, finding, pages)
    option = plan['optional_services'][0]
    assert option['status'] == 'source_backed_option' and 'calendar' in option['proposal']


def test_helpdesk_context_is_not_used_as_a_sales_qualification_need():
    lead, finding, pages = inputs('Call our customer support team for help.')
    plan = strategy.build(lead, finding, pages)
    assert next(o for o in plan['optional_services'] if o['service'] == 'ai_calling_agent')['use_case'] == 'customer_support'
    with pytest.raises(ValueError, match='helpdesk phone route'):
        strategy.validate_copy(plan, 'We can add an AI calling agent to qualify sales leads.')


def test_bounded_writer_context_keeps_decisive_quotes_from_long_pages():
    lead, finding, pages = inputs('')
    pages[0]['text'] = 'Business introduction. '*1000+' Book a consultation. By EnquiryBot. Call our customer support team for help.'
    excerpt = strategy.writer_excerpt(pages[0], finding)
    assert len(excerpt) < 4000 and len(excerpt) < len(pages[0]['text'])
    assert finding['quote'] in excerpt and 'By EnquiryBot' in excerpt and 'customer support team' in excerpt


def test_a_date_or_vendor_blog_mention_is_not_a_phone_number_or_installed_bot():
    lead, finding, pages = inputs('Published 2026-10-19. We discuss Intercom alternatives in our blog.')
    plan = strategy.build(lead, finding, pages)
    assert plan['chatbot_status'] == 'unknown' and not plan['optional_services']
    assert strategy.phone_match('Order reference 123456789012.') is None


def test_profile_website_build_keeps_search_uncertainty():
    lead, finding, _ = inputs('')
    lead.update(service='website_build', lead_kind='profile', profile_url='https://www.linkedin.com/company/bright-demo', website_status='website_not_found')
    finding['service'] = 'website_build'
    plan = strategy.build(lead, finding, [page('Book a consultation.', url=lead['profile_url'])])
    assert plan['primary_service'] == 'website_build'
    assert plan['website_scope'] == 'website_not_found_in_research'
    assert 'confirming' in plan['project_scope']


def test_campaign_b_does_not_receive_campaign_a_additions():
    lead, finding, pages = inputs('Frequently asked questions. Call us to book an appointment.')
    lead.update(campaign='B', service='store_improvement')
    assert not strategy.build(lead, finding, pages)['optional_services']


@pytest.mark.parametrize('claim', ['We can add a chatbot.', 'Your website needs a redesign.',
                                  'Your UI is outdated.', 'We can build a new AI chatbot.'])
def test_unsupported_absence_redesign_and_duplicate_bot_claims_are_rejected(claim):
    lead, finding, pages = inputs('By EnquiryBot.')
    with pytest.raises(ValueError):
        strategy.validate_copy(strategy.build(lead, finding, pages), claim)


def test_calling_addition_from_number_alone_stays_conditional():
    lead, finding, pages = inputs('Phone 0330 094 7733.')
    plan = strategy.build(lead, finding, pages)
    with pytest.raises(ValueError, match='conditional'):
        strategy.validate_copy(plan, 'We can add an AI calling agent to handle your enquiries.')
    strategy.validate_copy(plan, 'If phone enquiries are relevant, we can add an AI calling agent.')


def test_initial_website_pitch_cannot_omit_the_project_or_all_relevant_additions():
    lead, finding, pages = inputs('Phone 0330 094 7733.')
    plan = strategy.build(lead, finding, pages)
    with pytest.raises(ValueError, match='primary website project'):
        strategy.validate_copy(plan, 'We can adjust fonts. If useful, an AI calling agent could help.', initial=True)
    with pytest.raises(ValueError, match='optional feature'):
        strategy.validate_copy(plan, 'We can refresh the mobile enquiry layout and improve loading.', initial=True)
    strategy.validate_copy(plan, 'We can refresh the mobile enquiry layout. If phone enquiries are relevant, an AI calling agent could collect details for the team.', initial=True)


def test_review_api_records_a_typed_positive_observation_and_preserves_the_email(settings, db, prepared):
    client = TestClient(create_app(settings), headers={'Authorization':'Bearer '+settings.api_token})
    before = db.all('SELECT * FROM messages')
    body = {'chatbot_status':'present','source_url':'https://bright-demo.com/',
            'evidence_reference':'Operator screenshot showing a live enquiry widget.'}
    response = client.put(f"/api/leads/{prepared['lead_id']}/business-tools", json=body)
    assert response.status_code == 200
    review = strategy.review_snapshot(db, prepared['lead_id'])
    assert review['chatbot_status'] == 'present'
    assert db.all('SELECT * FROM messages') == before
    assert client.put(f"/api/leads/{prepared['lead_id']}/business-tools", json={**body,'source_url':'https://unrelated.example/'}).status_code == 400
    assert client.put(f"/api/leads/{prepared['lead_id']}/business-tools", json={**body,'chatbot_status':'absent'}).status_code == 422


@pytest.mark.parametrize('change_during_generation', [None, 'source', 'tool_review', 'new_page'])
def test_broader_context_reaches_real_writer_and_changes_invalidate_copy(settings, db, prepared, monkeypatch, change_during_generation):
    lid, cid = prepared['lead_id'], prepared['contact_id']
    settings.followups_enabled = settings.sending_enabled = False
    settings.draft_api_key, settings.draft_model = 'fictional-key', 'fictional-model'
    archive_followups(db, cid)
    text = 'Frequently asked questions about booking. Phone 0330 094 7733. By EnquiryBot.'
    eid = db.execute('INSERT INTO evidence(lead_id,url,title,text,sha256,fetched_at) VALUES(?,?,?,?,?,?)',
        (lid, 'https://bright-demo.com/contact', 'Contact', text, 'context-v1', time.time()))
    db.event('performance', {'lead_id':lid,'url':'https://bright-demo.com/','status':'complete',
        'strategies':{'mobile':{'score':51,'final_url':'https://bright-demo.com/',
            'opportunities':[{'id':'font-display-insight','title':'Font display'}]}}})
    seen = []
    def chat(s, instructions, encoded, **kwargs):
        kwargs['before_request']()
        packet = json.loads(encoded); seen.append(packet)
        assert packet['prospect_solution']['chatbot_status'] == 'present'
        assert any(p['evidence_id'] == eid for p in packet['sources'])
        if change_during_generation == 'source':
            db.execute('UPDATE evidence SET sha256=? WHERE id=?', ('context-v2',eid))
        elif change_during_generation == 'tool_review':
            db.event('business_tool_review', {'lead_id':lid,'chatbot_status':'present','source_url':'https://bright-demo.com/', 'evidence_reference':'A new operator-reviewed screenshot.'})
        elif change_during_generation == 'new_page':
            db.execute('INSERT INTO evidence(lead_id,url,title,text,sha256,fetched_at) VALUES(?,?,?,?,?,?)',
                (lid,'https://bright-demo.com/faq','FAQ','By Tidio. Questions about booking.', 'new-page',time.time()))
        return json.dumps({'messages':[{'step':0,'subject':'An enquiry journey idea for Bright Demo',
            'body':'Your mobile Lighthouse lab test scored 51/100. We can improve loading and propose a clearer mobile enquiry layout, keeping your existing assistant. If phone enquiries are relevant, an AI calling agent could collect service and location details and pass a summary to your team. Would a short outline of that project be useful?',
            'support':[{'evidence_id':prepared['evidence_id'],'quote':'Contact us for a consultation.'},
                       {'evidence_id':eid,'quote':text}], 'diagnostic_refs':[packet['audit_context']['observations'][0]['ref']]}]})
    monkeypatch.setattr(email_writer, 'chat', chat)
    monkeypatch.setattr(email_writer, 'generate_sequence', REAL_GENERATE)
    if change_during_generation:
        before = db.all('SELECT * FROM messages')
        with pytest.raises(ValueError, match='changed during AI writing'):
            create_drafts(db, settings, cid)
        assert db.all('SELECT * FROM messages') == before
    else:
        create_drafts(db, settings, cid)
        email_writer.assert_ai_origin(db, cid)
        event = json.loads(db.one("SELECT detail FROM events WHERE kind='drafts_created' ORDER BY id DESC LIMIT 1")['detail'])
        assert eid in event['source_ids']
        db.execute('UPDATE evidence SET sha256=? WHERE id=?', ('context-v2',eid))
        with pytest.raises(ValueError, match='Business context sources changed'):
            email_writer.assert_ai_origin(db, cid)
    assert seen and not db.one('SELECT 1 FROM messages WHERE sent_at IS NOT NULL')
