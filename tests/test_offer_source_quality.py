"""Useful offer evidence must come from actual business-facing source context."""
import pytest

from outreach.opportunities import proposals


def page(text, url='https://business.example/', eid=1, title='Business'):
    return {'id': eid, 'url': url, 'title': title, 'text': text}


@pytest.mark.parametrize('url,title', [
    ('https://business.example/policies/privacy-policy', 'Privacy Policy'),
    ('https://business.example/terms-of-service', 'Terms of Service'),
    ('https://business.example/cookie-policy', 'Cookie Policy'),
    ('https://business.example/pages/information', 'Privacy Notice | Business'),
])
def test_legal_boilerplate_is_not_a_customer_support_offer(url, title):
    source = page('Information you give us, for example when sending a customer support inquiry.', url, title=title)
    assert proposals({'campaign': 'B'}, [source]) == []


@pytest.mark.parametrize('metadata', [False, True])
def test_rejected_marketplace_history_cannot_propose_company_services(metadata):
    lead = {'campaign': 'A'}
    if metadata:
        lead['website'] = 'https://m.indiamart.com/'
    assert proposals(lead, [page('Contact us for a consultation.', 'https://m.indiamart.com/')]) == []


def test_foreign_page_cannot_support_official_company_offer():
    lead = {'campaign': 'A', 'website': 'https://business.example/'}
    assert proposals(lead, [page('Book a consultation with our team.', 'https://unrelated.example/contact')]) == []


def test_bare_contact_menu_does_not_establish_a_useful_inquiry_signal():
    source = page('About us Contact us Products Blog Academy Careers Privacy Policy')
    assert proposals({'campaign': 'A'}, [source]) == []


@pytest.mark.parametrize('reverse', [False, True])
def test_actual_booking_invitation_wins_over_generic_contact_route(reverse):
    weaker = page('Contact us for more information about our business.', 'https://business.example/contact')
    stronger = page('Book your appointment with our dental team to discuss treatment options.', eid=2)
    sources = [weaker, stronger]
    if reverse:
        sources.reverse()
    proposal = proposals({'campaign': 'A'}, sources)[0]
    assert proposal['evidence_id'] == 2
    assert proposal['quote'] in stronger['text']
    assert proposal['review_required'] and 'not a verified pain point' in proposal['limitations']


def test_saved_quote_never_starts_or_ends_inside_a_word():
    text = ('Our consultation service provides a straightforward customer journey with clear explanations. '
            'Book a consultation with our team to discuss your project and agree the next useful step. '
            'All appointments include a focused review of the available options for your business.')
    proposal = proposals({'campaign': 'A'}, [page(text)])[0]
    quote = proposal['quote']
    start, end = text.index(quote), text.index(quote)+len(quote)
    assert (start == 0 or not text[start-1].isalnum()) and (end == len(text) or not text[end].isalnum())


def test_explicit_phone_contact_remains_a_reviewable_inquiry_route():
    source = page('Our service team is available. Call us at (512) 820-6505 to discuss your project.')
    proposal = proposals({'campaign': 'A'}, [source])[0]
    assert proposal['service'] == 'website_improvement' and proposal['review_required']


def test_faq_footer_link_without_question_content_is_not_a_chatbot_signal():
    source = page('Our Story Awards Areas We Serve Frequently Asked Questions Customer Stories Referrals Copyright 2026',
                  'https://business.example/contact-us')
    assert proposals({'campaign': 'A'}, [source]) == []


@pytest.mark.parametrize('reverse', [False, True])
def test_product_purchase_evidence_wins_over_unrelated_support_page_shop_banner(reverse):
    banner = page('Build your autumn wardrobe. SHOP NOW. Contact our team.', 'https://business.example/pages/faq')
    product = page('Our skincare hair mask. Add to cart. Choose size and quantity.',
                   'https://business.example/products/hair-mask', eid=2)
    sources = [banner, product]
    if reverse:
        sources.reverse()
    idea = proposals({'campaign': 'B'}, sources)[0]
    assert idea['evidence_id'] == 2 and 'Add to cart' in idea['quote']
