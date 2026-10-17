import json

import pytest

from outreach.opportunities import proposals
from outreach.research import add_lead, research_lead
from outreach.web import extract_page


def source(text, eid=1):
    return {'id': eid, 'url': 'https://fictional-business.example/contact', 'text': text}


def test_inquiry_offer_is_grounded_and_reviewed_without_claiming_an_observed_problem():
    page = source('UK consulting services. Book a consultation with our team to discuss your project.')
    result = proposals({'campaign': 'A'}, [page])
    assert result[0]['service'] == 'website_improvement'
    assert result[0]['quote'] in page['text'] and result[0]['source_url'] == page['url']
    assert result[0]['review_required'] and result[0]['proposal_method'] == 'explicit_public_signal'
    assert 'Review that inquiry journey' in result[0]['suggestion']
    assert 'not a verified pain point' in result[0]['limitations']


def test_d2c_signals_prioritize_existing_shopping_journey_and_preserve_campaign_gate():
    page = source('Add to cart. Frequently asked questions. How do I place an order? Subscribe to our WhatsApp updates.')
    result = proposals({'campaign': 'B'}, [page])
    assert [f['service'] for f in result] == ['store_improvement', 'chatbot', 'whatsapp_marketing', 'whatsapp_automation']
    assert all(f['quote'] in page['text'] for f in result)
    assert not any(f['service'].startswith('website_') for f in result)
    assert all(f['review_required'] for f in result)


def test_channel_signal_does_not_infer_customer_permission():
    result = proposals({'campaign': 'B'}, [source('Chat with us on WhatsApp about your order.')])
    assert result[0]['service'] == 'whatsapp_automation'
    assert 'First qualify customer channel fit, permission' in result[0]['suggestion']
    assert 'eligible events' in result[0]['suggestion']


@pytest.mark.parametrize('campaign,text,expected', [
    ('A', 'We provide UK consulting services. Call us to arrange a consultation.', 'website_build'),
    ('B', 'We sell handmade products. Place your orders through our published business contact.', 'store_launch'),
])
def test_profile_launch_proposal_requires_completed_not_found_search(campaign, text, expected):
    lead = {'campaign': campaign, 'lead_kind': 'profile', 'website_status': 'website_not_found'}
    assert proposals(lead, [source(text)])[0]['service'] == expected
    for state in ('checking', 'ambiguous', 'search_unavailable', 'website_found', 'not_checked'):
        assert proposals({**lead, 'website_status': state}, [source(text)]) == []


@pytest.mark.parametrize('campaign,text', [
    ('A', 'We do not let visitors book a consultation here.'),
    ('B', 'You cannot add to cart on this page.'),
    ('B', 'We do not offer customer support via WhatsApp.'),
])
def test_negative_signal_does_not_propose_available_route(campaign, text):
    assert proposals({'campaign': campaign}, [source(text)]) == []


def test_insufficient_evidence_stays_empty_instead_of_inventing_friction_or_absent_features():
    assert proposals({'campaign': 'A'}, [source('A fictional company serving its community.')]) == []
    assert proposals({'campaign': 'B'}, [source('Our company news and public address.')]) == []


def test_new_service_and_store_announcements_have_relevant_launch_offer():
    assert proposals({'campaign': 'A'}, [source('We are introducing our new service this month.')])[0]['service'] == 'website_build'
    assert proposals({'campaign': 'B'}, [source('Our online store is launching soon.')])[0]['service'] == 'store_launch'


@pytest.mark.asyncio
async def test_no_ai_research_saves_current_signal_proposal_without_qualification_or_drafts(db, settings, monkeypatch):
    lid = add_lead(db, 'Fictional consultation business', 'https://fictional-business.example', 'A',
                   'https://fictional-business.example/contact', 'UK')
    settings.auto_visual_audit = False
    async def crawl(web, url):
        web.report.update(status='partial', errors=[], remaining=0)
        return [extract_page(url, '<p>UK consulting services. Book a consultation with our team.</p>')]
    monkeypatch.setattr('outreach.web.PublicWeb.crawl', crawl)
    await research_lead(db, settings, lid)
    lead = db.one('SELECT * FROM leads WHERE id=?', (lid,))
    finding = json.loads(lead['findings'])[0]
    page = db.one('SELECT * FROM evidence WHERE id=?', (finding['evidence_id'],))
    assert lead['status'] == 'review' and lead['service'] == ''
    assert finding['quote'] in page['text'] and finding['service'] == 'website_improvement'
    assert finding['review_required'] and finding['suggestion']
    assert db.one('SELECT COUNT(*) n FROM messages')['n'] == 0
