import json

import pytest

from outreach.source_versions import retain_http_publications
from outreach.web import extract_page, PublicWeb
from outreach.research import add_lead, research_lead, company_publication


URL = 'https://bright-demo.com/team'
PROFILE = 'https://www.linkedin.com/in/alex-doe'
RAW = ('<title>Bright Demo</title><main><article class="hover-card"><h2>Alex Doe</h2>'
       '<p>Founder</p><a href="mailto:alex@bright-demo.com">Business enquiries</a>'
       '<a href="https://www.linkedin.com/in/alex-doe">LinkedIn</a></article></main>')
DOM = '<title>Bright Demo</title><main><p>Current public services.</p></main>'


def test_retains_public_http_staff_contact_with_independent_scope_and_digest():
    raw, dom = extract_page(URL, RAW), extract_page(URL, DOM)
    combined = retain_http_publications(dom, raw)
    assert combined['emails'] == ['alex@bright-demo.com']
    assert combined['contacts'][0]['name'] == 'Alex Doe'
    assert combined['named_people'][0]['source_capture_method'] == 'public_html'
    assert combined['named_people'][0]['source_sha256'] == raw['sha256']
    assert combined['sha256'] not in {raw['sha256'], dom['sha256']}
    assert combined['capture_sources'] == [{'capture_method': 'rendered_dom', 'sha256': dom['sha256']},
                                           {'capture_method': 'public_html', 'sha256': raw['sha256']}]
    assert 'not rendered visibility' in combined['text']
    assert raw['text'] in combined['text']
    assert raw['named_people'][0]['quote'] in combined['text']
    assert 'source_capture_method' not in raw['named_people'][0]  # No input mutation.


def test_http_email_is_not_attached_to_another_capture_person_profile():
    raw = extract_page(URL, RAW.replace('alex@bright-demo.com', 'other@bright-demo.com').replace(PROFILE, PROFILE+'-other'))
    dom = extract_page(URL, RAW.replace('<a href="mailto:alex@bright-demo.com">Business enquiries</a>', ''))
    combined = retain_http_publications(dom, raw)
    exact = [p for p in combined['named_people'] if PROFILE in p['professional_links']]
    assert len(exact) == 1 and not exact[0]['email_publications']
    assert combined['contacts'][0]['named_associations'][0]['professional_links'] == [PROFILE+'-other']


def test_shared_address_across_named_scopes_clears_individual_identity():
    raw = extract_page(URL, RAW.replace('alex@', 'team@'))
    dom = extract_page(URL, RAW.replace('Alex Doe', 'Sam Roe').replace('alex@', 'team@').replace('alex-doe', 'sam-roe'))
    combined = retain_http_publications(dom, raw)
    contact = combined['contacts'][0]
    assert contact['name'] == contact['role'] == '' and contact['identity_ambiguous']
    assert {p['name'] for p in contact['named_associations']} == {'Alex Doe', 'Sam Roe'}


def test_other_domain_http_address_remains_a_review_candidate():
    combined = retain_http_publications(extract_page(URL, DOM), extract_page(URL, RAW.replace('alex@bright-demo.com', 'business@other-demo.com')))
    assert not combined['emails'] and not combined['contacts']
    assert combined['review_candidates'][0]['review_required'] is True
    assert combined['review_candidates'][0]['name'] == 'Alex Doe'


@pytest.mark.parametrize('case', ['different_url', 'same_hash', 'no_additional_contact_data'])
def test_no_bundle_for_different_route_or_no_additional_publication(case):
    dom = extract_page(URL, DOM)
    raw = extract_page('https://bright-demo.com/contact' if case == 'different_url' else URL,
                       RAW if case == 'different_url' else DOM if case == 'same_hash' else DOM+'<!-- metadata change -->')
    assert retain_http_publications(dom, raw) is dom


async def test_real_chromium_research_saves_http_contact_and_rejects_withdrawn_publication(
    db, settings, monkeypatch
):
    settings.crawl_max_pages = 1
    settings.crawl_max_depth = 0
    settings.crawl_max_sitemaps = 0
    settings.crawl_delay_seconds = .001
    settings.browser_settle_seconds = .01
    settings.auto_visual_audit = False
    settings.auto_contact_research = False
    settings.auto_professional_research = False
    current = {'html': RAW.replace('<main>', '<style>.hover-card{display:none}</style><main>')+ '<p>Current business services.</p>'}

    async def get(self, url, *_):
        if url.endswith('/robots.txt'):
            return url, 'User-agent: *\nAllow: /', 200
        html = current['html']
        self.last_document = {'url': url, 'body': html.encode(), 'status': 200,
                              'headers': {'content-type': 'text/html'}}
        return url, html, 200

    async def no_network(*_args, **_kwargs):
        pytest.fail('Controlled public documents must be reused, no provider calls')

    monkeypatch.setattr(PublicWeb, 'get', get)
    monkeypatch.setattr(PublicWeb, 'resource', no_network)
    lid = add_lead(db, 'Bright Demo', URL, 'A', URL)
    await research_lead(db, settings, lid)
    contact = db.one('SELECT * FROM contacts WHERE lead_id=?', (lid,))
    assert contact['email'] == 'alex@bright-demo.com' and contact['name'] == 'Alex Doe'
    assert contact['verification'] == 'unverified' and contact['status'] == 'new'
    lead = db.one('SELECT * FROM leads WHERE id=?', (lid,))
    proof = company_publication(db, contact, lead)
    assert proof and 'not rendered visibility' in proof['text']
    report = json.loads(db.one('SELECT report FROM crawls WHERE lead_id=?', (lid,))['report'])
    assert report['pages'][0]['http_publication_retained']
    assert report['pages'][0]['named_people'][0]['professional_links'] == [PROFILE]
    assert db.one("SELECT COUNT(*) n FROM jobs WHERE kind='verify'")['n'] == 1
    assert not db.all('SELECT * FROM messages')
    # The real automatic professional-research path must consume this saved
    # scope/hash, not just the standalone snapshot diagnostic.
    from outreach.professionals import research_professionals
    settings.professional_max_profiles = 1
    async def blocked_profile(_settings, target):
        assert target == PROFILE
        return {'state': 'robots_denied', 'url': target}
    monkeypatch.setattr('outreach.professionals.profile_snapshot', blocked_profile)
    monkeypatch.setattr('outreach.providers.discover', no_network)
    professional_report = await research_professionals(db, settings, lid)
    assert not professional_report['queries']
    candidates = professional_report['official_person_email_candidates']
    assert candidates[0]['email'] == 'alex@bright-demo.com'
    assert candidates[0]['name'] == 'Alex Doe' and candidates[0]['company_sha256'] == proof['sha256']
    assert candidates[0]['native_profile_publication'] is False
    # A newly shared address clears an earlier inferred identity in real saved
    # contact data. Scope conflicts must not retain the first owner's name.
    sam = RAW.replace('Alex Doe', 'Sam Roe').replace('alex-doe', 'sam-roe')
    current['html'] = RAW.replace('<main>', '<style>.hover-card{display:none}</style><main>') + sam.replace('class="hover-card"', '')
    await research_lead(db, settings, lid)
    updated = db.one('SELECT * FROM contacts WHERE id=?', (contact['id'],))
    assert updated['name'] == updated['role'] == ''
    assert company_publication(db, updated, lead)
    current['html'] = '<title>Bright Demo</title><p>Current business services.</p>'
    await research_lead(db, settings, lid)
    assert company_publication(db, contact, lead) is None
    assert db.one('SELECT sha256 FROM evidence WHERE lead_id=?', (lid,))['sha256'] != proof['sha256']
    assert not db.all('SELECT * FROM messages')
