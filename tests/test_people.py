import json
import time

import pytest

from outreach import people, professionals, providers
from outreach.web import extract_page


URL = 'https://bright-demo.com/team'


@pytest.mark.parametrize('value,expected', [('adam frickleton', 'Adam Frickleton'),
    ('Mark McIntosh MCIAT FCIAT', 'Mark McIntosh'), ('Alex Doe MBA', 'Alex Doe'),
    ('Coffee shop founder', ''), ('John Mba', 'John Mba')])
def test_index_name_hint_normalization_does_not_approve_identity(value, expected):
    assert people.indexed_person_name(value) == expected


def test_official_people_route_is_a_staff_source_but_article_under_it_is_not():
    html = '<main><article><h2>Alex Doe</h2><p>Director</p><a href="https://linkedin.com/in/alex-doe">LinkedIn</a></article></main>'
    assert extract_page('https://bright-demo.com/uk/people/alex-doe', html)['named_people'][0]['name'] == 'Alex Doe'
    assert not extract_page('https://bright-demo.com/people/news/old-article', html)['named_people']


@pytest.mark.parametrize('section', ['projects', 'case-studies', 'testimonials', 'reviews'])
def test_studio_client_or_editorial_pages_are_not_employee_records(section):
    html = '<main><article><h2>Alex Doe</h2><p>Director</p><a href="https://linkedin.com/in/alex-doe">LinkedIn</a></article></main>'
    assert not extract_page('https://bright-demo.com/studio/'+section+'/demo', html)['named_people']


def test_segmented_staff_heading_preserves_name_role_and_scope():
    page = extract_page('https://bright-demo.com/people/alex-doe', '<main><section><h1><span>Alex Doe</span><br><span>Architect Director</span></h1><p>London</p></section></main>')
    person = page['named_people'][0]
    assert person['name'] == 'Alex Doe' and person['role'] == 'Director'
    assert person['quote'] in page['text'] and not person['professional_links'] and not person['email_publications']


def test_multi_person_heading_does_not_select_one_name_as_card_owner():
    assert not extract_page(URL, '<main><section><h1><span>Alex Doe</span><span>Sam Roe</span><span>Directors</span></h1></section></main>')['named_people']


@pytest.mark.parametrize('wrapper', ['body', 'div role="main"'])
def test_staff_body_without_main_and_br_heading_keeps_real_name_role_and_card_scope(wrapper):
    end = wrapper.split()[0]
    html = f'<{wrapper}><section><h3>Alex Doe <br> Co-Founding Director</h3><p>Architecture practice</p>'
    html += '<a href="mailto:alex@bright-demo.com">Email</a><a href="https://www.linkedin.com/in/alex-doe">LinkedIn</a></section>'
    html += '<section><h3>Sam Roe <br> Director</h3><a href="mailto:sam@bright-demo.com">Email</a></section>'
    html += f'<footer><h3>Other Person</h3><p>Director footer@bright-demo.com</p></footer></{end}>'
    people = extract_page(URL, html)['named_people']
    assert {p['name'] for p in people} == {'Alex Doe', 'Sam Roe'}
    alex = next(p for p in people if p['name'] == 'Alex Doe')
    assert alex['professional_links'] == ['https://www.linkedin.com/in/alex-doe']
    assert [p['email'] for p in alex['email_publications']] == ['alex@bright-demo.com']
    assert alex['buyer_verified'] is False


def test_br_heading_with_two_different_names_does_not_choose_one_owner():
    html = '<body><section><h3>Alex Doe <br> Sam Roe <br> Directors</h3><a href="mailto:team@bright-demo.com">Email</a></section></body>'
    assert not extract_page(URL, html)['named_people']


def test_body_fallback_excludes_dialog_and_form_demo_identities():
    html = '<body><div role="dialog"><h3>Demo Person</h3><p>Founder</p></div><form><h3>Form Person</h3><p>Director</p></form></body>'
    assert not extract_page(URL, html)['named_people']


@pytest.mark.parametrize('role', ['Principal', 'Managing Partner', 'Founding Partner', 'Partner and Architect'])
def test_official_staff_principal_partner_titles_are_unverified_named_hints(role):
    html = f'<body><article><h3>Alex Doe</h3><p>{role}</p><a href="mailto:alex@bright-demo.com">Business email</a></article></body>'
    person = extract_page(URL, html)['named_people'][0]
    assert person['name'] == 'Alex Doe' and person['email_publications'][0]['email'] == 'alex@bright-demo.com'
    assert person['buyer_verified'] is False and person['current_employer_verified'] is False


@pytest.mark.parametrize('text', ['Our partnership programme', 'Partnerships with local suppliers', 'Principalities and regional design'])
def test_partner_principal_fragments_are_not_job_titles(text):
    assert not extract_page(URL, f'<body><article><h3>Alex Doe</h3><p>{text}</p></article></body>')['named_people']


def test_linked_bold_staff_paragraph_preserves_exact_profile_and_email_without_footer_borrowing():
    html = '<body><div><p><a href="https://www.linkedin.com/in/alex-doe"><strong>Alex Doe</strong><br>Founder and Managing Partner</a>'
    html += '<a href="mailto:alex@bright-demo.com">Business enquiries</a></p></div>'
    html += '<p><strong>Sam Roe</strong><br>Principal</p><footer>general@bright-demo.com</footer></body>'
    people = extract_page(URL, html)['named_people']
    alex = next(p for p in people if p['name'] == 'Alex Doe')
    assert alex['method'] == 'official_bold_staff_block'
    assert alex['professional_links'] == ['https://www.linkedin.com/in/alex-doe']
    assert [e['email'] for e in alex['email_publications']] == ['alex@bright-demo.com']
    assert not next(p for p in people if p['name'] == 'Sam Roe')['email_publications']


@pytest.mark.parametrize('path', ['/team', '/about', '/'])
def test_bold_multi_person_paragraph_does_not_choose_one_recipient(path):
    html = '<body><p><strong>Alex Doe</strong> and <strong>Sam Roe</strong><br>Managing Partners <a href="mailto:team@bright-demo.com">Email</a></p></body>'
    assert not extract_page('https://bright-demo.com'+path, html)['named_people']


def test_bold_article_author_does_not_create_staff_identity():
    html = '<body><p><strong>Alex Doe</strong><br>Founder and Principal</p></body>'
    assert not extract_page('https://bright-demo.com/blog/article', html)['named_people']


@pytest.mark.parametrize('name,role', [('Paul Vincent Arceo', 'Project Assistant'),
    ('Alex Doe', 'Homeowner liaison'), ('Sam Roe', 'Directorship programme')])
def test_names_and_words_containing_role_fragments_do_not_create_buyer_hints(name, role):
    html = f'<body><p><strong>{name}</strong><br>{role}</p></body>'
    assert not extract_page(URL, html)['named_people']


def test_nested_staff_header_links_public_email_and_exact_profile_without_footer_inbox():
    page = extract_page(URL, '<main><section><div><h1>Alex Doe</h1></div><p>Founder</p>'
        '<div><a href="mailto:alex@bright-demo.com">Email</a><a href="https://linkedin.com/in/alex-doe">LinkedIn</a></div>'
        '</section></main><footer>general@bright-demo.com</footer>')
    person = page['named_people'][0]
    assert person['email_publications'] == [{'email': 'alex@bright-demo.com', 'method': 'scoped_mailto'}]
    assert person['professional_links'] == ['https://www.linkedin.com/in/alex-doe']
    contacts = {c['email']: c for c in page['contacts']}
    assert contacts['alex@bright-demo.com']['name'] == 'Alex Doe'
    assert contacts['general@bright-demo.com']['name'] == ''
    assert person['inbox_ownership_verified'] is False


def test_shared_staff_inbox_does_not_select_an_individual_recipient():
    html = '<main>' + ''.join(f'<section><h3>{name}</h3><p>Director</p>'
        '<a href="mailto:team@bright-demo.com">Email</a></section>' for name in ['Alex Doe', 'Sam Roe']) + '</main>'
    page = extract_page(URL, html)
    contact = page['contacts'][0]
    assert len(contact['named_associations']) == 2 and contact['name'] == ''


def test_shared_jsonld_inbox_clears_first_person_assignment():
    value = [{'@type': 'Person', 'name': name, 'jobTitle': 'Director', 'email': 'team@bright-demo.com'}
             for name in ['Alex Doe', 'Sam Roe']]
    page = extract_page(URL, '<script type="application/ld+json">'+json.dumps(value)+'</script>')
    assert page['contacts'][0]['name'] == '' and len(page['contacts'][0]['named_associations']) == 2


def test_staff_email_obfuscation_is_decoded_only_inside_its_card():
    email = 'alex@bright-demo.com'
    encoded = bytes([23] + [ord(c) ^ 23 for c in email]).hex()
    page = extract_page(URL, f'<main><section><h2>Alex Doe</h2><p>CEO</p><a data-cfemail="{encoded}">[email protected]</a></section></main>')
    assert page['named_people'][0]['email_publications'][0]['email'] == email


def test_jsonld_person_email_has_a_quote_saved_in_page_evidence():
    value = {'@type': 'Person', 'name': 'Alex Doe', 'jobTitle': 'CEO', 'email': 'alex@bright-demo.com',
             'sameAs': 'https://linkedin.com/in/alex-doe'}
    page = extract_page(URL, '<script type="application/ld+json">'+json.dumps(value)+'</script>')
    person = page['named_people'][0]
    assert person['quote'] in page['text'] and person['email_publications'][0]['email'] == value['email']


def test_email_is_not_taken_from_adjacent_person_or_hidden_card_content():
    page = extract_page(URL, '<main><section><div><h2>Alex Doe</h2><p>CEO</p>'
        '<a hidden href="mailto:hidden@bright-demo.com">Email</a></div>'
        '<div><h2>Sam Roe</h2><p>Founder</p><a href="mailto:sam@bright-demo.com">Email</a></div></section></main>')
    people = {p['name']: p for p in page['named_people']}
    assert people['Alex Doe']['email_publications'] == []
    assert people['Sam Roe']['email_publications'][0]['email'] == 'sam@bright-demo.com'


def test_staff_person_without_an_email_still_becomes_a_sourced_buyer_search_hint():
    html = '<main><article><h3>Alex Doe</h3><p>Founder at Bright Demo</p><a href="https://linkedin.com/in/alex-doe">Profile</a></article></main>'
    page = extract_page(URL, html)
    assert not page['emails']
    person = page['named_people'][0]
    assert person['name'] == 'Alex Doe' and person['professional_links'] == ['https://www.linkedin.com/in/alex-doe']
    assert person['quote'] in page['text'] and person['buyer_verified'] is False


def test_public_jsonld_person_without_mailto_retains_exact_metadata_and_rejects_private_profile_routes():
    value = {'@type':'Person','name':'Alex Doe','jobTitle':'CEO','sameAs':['https://linkedin.com/in/alex-doe','https://linkedin.com/in/alex-doe/overlay/contact-info/']}
    page = extract_page(URL, '<script type="application/ld+json">' + json.dumps(value) + '</script><main>Bright Demo team</main>')
    p = page['named_people'][0]
    assert p['role'] == 'CEO' and p['quote'] in page['text']
    assert len(p['professional_links']) == 1 and not page['contacts']


def test_small_business_about_relationship_does_not_invent_founder_or_owner_title():
    page = extract_page('https://bright-demo.com/about', '<main><p>Bright Demo is the work of independent Bristol florist Ellie Jones, established in 2020.</p></main>')
    person = page['named_people'][0]
    assert person['name'] == 'Ellie Jones' and person['role'] == ''
    assert person['method'] == 'official_named_relationship' and person['current_employer_verified'] is False


def test_observed_about_page_greeting_is_not_included_in_person_name():
    page = extract_page('https://bright-demo.com/about', '<main><article><h2>Hi I\'m Justin Inahara</h2><p>Founder of Bright Demo</p></article></main>')
    assert page['named_people'][0]['name'] == 'Justin Inahara'
    assert page['named_people'][0]['quote'] in page['text']


def test_mission_heading_and_team_container_are_not_invented_people():
    page = extract_page('https://bright-demo.com/about', '<main><section><h2>Our Mission</h2><p>Our founder guides us.</p></section><section><h3>Alex Doe</h3><h3>Sam Roe</h3><p>CEO</p></section></main>')
    assert not page['named_people']


@pytest.mark.parametrize('html', [
    '<main><blockquote><h3>Alex Doe</h3><p>Founder at Other Company</p></blockquote></main>',
    '<main><section hidden><h3>Alex Doe</h3><p>CEO</p></section></main>',
    '<main><section style="display:none"><h3>Alex Doe</h3><p>CEO</p></section></main>',
    '<main><article><h3>Alex Doe</h3><p>Former founder at Bright Demo</p></article></main>',
    '<main><h3>Alex Doe</h3></main><footer>Marketing director</footer>',
    '<main><article><h3>Contact Us</h3><p>Founder details</p></article></main>',
    '<script type="application/ld+json">{"@type":"Review","author":{"@type":"Person","name":"Alex Doe","jobTitle":"CEO"}}</script>',
])
def test_hidden_testimonial_former_and_unassociated_roles_do_not_create_named_people(html):
    assert people.people_from_html(URL, html) == []


def test_blog_article_author_is_not_a_current_employee_candidate():
    assert not people.people_from_html('https://bright-demo.com/blog/marketing',
        '<main><article><h3>Alex Doe</h3><p>Founder</p></article></main>')


async def test_hash_matched_named_person_link_avoids_unnecessary_index_requests(db, settings, prepared, monkeypatch):
    lid = prepared['lead_id']
    page = db.one('SELECT * FROM evidence WHERE id=?', (prepared['evidence_id'],))
    db.execute('INSERT INTO crawls(lead_id,report,created_at) VALUES(?,?,?)',
        (lid,json.dumps({'pages':[{'url':page['url'],'sha256':page['sha256'],'named_people':[
            {'name':'Alex Doe','role':'Founder','professional_links':['https://linkedin.com/in/alex-doe']}]}]}),time.time()-1))
    settings.professional_max_profiles = 1
    async def search(*args, **kw):
        pytest.fail('Observed named-person profile fills the profile budget')
    async def snapshot(s, url):
        return {'state':'robots_denied','url':url}
    monkeypatch.setattr(providers,'discover',search)
    monkeypatch.setattr(professionals,'profile_snapshot',snapshot)
    result = await professionals.research_professionals(db,settings,lid)
    assert result['captures'][0]['state'] == 'robots_denied' and not result['queries']
    assert professionals.captures(db,lid)[0]['source_hint']['person'] == 'Alex Doe'
    assert not db.one("SELECT 1 FROM jobs WHERE kind='verify'")


async def test_named_person_queries_require_sourced_company_match_and_preserve_blocked_capture(db, settings, prepared, monkeypatch):
    lid = prepared['lead_id']
    settings.professional_refresh_official_links = True
    settings.professional_max_queries = 2
    settings.discovery_query_delay_seconds = 0.001
    from outreach import discovery
    async def page(s, url):
        return {'state':'captured','url':url,'sha256':'current','public_links':[],
                'named_people':[{'name':'Alex Doe','role':'Founder','quote':'Alex Doe, Founder at Bright Demo','source_url':url}]}
    calls = []
    async def search(s,q,*args,**kw):
        calls.append(q)
        return [{'url':'https://linkedin.com/in/alex-doe','title':'Alex Doe Founder Bright Demo'},
                {'url':'https://linkedin.com/in/alex-other','title':'Alex Doe Founder Other Company'}]
    async def snapshot(s,url):
        assert url == 'https://www.linkedin.com/in/alex-doe'
        return {'state':'robots_denied','url':url}
    monkeypatch.setattr(discovery,'public_snapshot',page)
    monkeypatch.setattr(providers,'discover',search)
    monkeypatch.setattr(professionals,'profile_snapshot',snapshot)
    result = await professionals.research_professionals(db,settings,lid)
    assert len(calls) == 2 and all('"Alex Doe"' in q for q in calls)
    assert len(result['captures']) == 1 and result['state'] == 'held'
    assert all(q['rejected_company_mismatch'] == 1 for q in result['queries'])
    assert not db.one("SELECT 1 FROM jobs WHERE kind='verify'")


@pytest.mark.parametrize('style', ['display:none', 'visibility:hidden'])
def test_nested_hidden_staff_elements_do_not_crash_or_publish_people(style):
    hidden = '<section style="'+style+'"><div style="color:red"><h2>Hidden Person</h2><p>Director</p></div></section>'
    html = '<main>'+hidden+'<article><h2>Alex Doe</h2><p>Director</p></article></main>'
    page = extract_page(URL, html)
    assert [p['name'] for p in page['named_people']] == ['Alex Doe']
    result = professionals.parse_public_html('https://www.linkedin.com/in/alex-doe/', '<main>'+hidden+'<h1>Alex Doe</h1><p>Director at Bright Studio in London</p></main>')
    assert 'Hidden Person' not in str(result)
