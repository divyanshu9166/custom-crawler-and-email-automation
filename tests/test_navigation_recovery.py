"""Contact navigation must survive JS replacement without fabricating contacts."""
import json

import pytest

from outreach.source_versions import retain_http_publications
from outreach.web import PublicWeb, extract_page
from outreach.research import add_lead, research_lead, company_publication


ROOT = 'https://bright-demo.com/'
HOME = ('<title>Bright Demo</title><h1>Current business services</h1>'
        '<nav id="server-nav"><a href="/contact">Contact</a><a href="/team">Team</a></nav>'
        '<script>document.getElementById("server-nav").remove()</script>')
DOM = '<title>Bright Demo</title><h1>Current business services</h1>'


def test_http_only_contact_navigation_is_preserved_with_original_capture_hashes():
    raw, dom = extract_page(ROOT, HOME), extract_page(ROOT, DOM)
    result = retain_http_publications(dom, raw)
    assert result['links'] == [ROOT+'contact', ROOT+'team']
    assert result['http_navigation_retained'] is True
    assert result['http_navigation_links'] == [ROOT+'contact', ROOT+'team']
    assert result['capture_sources'][1]['sha256'] == raw['sha256']
    assert result['sha256'] not in {raw['sha256'], dom['sha256']}
    assert not result['contacts'] and not result['named_people']
    assert 'not rendered visibility' in result['text']
    assert not dom['links']  # Inputs stay unchanged.


@pytest.mark.parametrize('href', [
    'https://other-demo.com/contact', '/login/contact', '/account/team',
    '/blog/contact', '/products/team', '/contact.pdf', '/news/article',
])
def test_unrelated_private_editorial_or_external_links_do_not_trigger_http_bundle(href):
    dom = extract_page(ROOT, DOM)
    raw = extract_page(ROOT, DOM+f'<a href="{href}">Contact</a>')
    assert retain_http_publications(dom, raw) is dom


def test_contact_navigation_from_another_document_route_is_not_transferred():
    dom = extract_page(ROOT, DOM)
    assert retain_http_publications(dom, extract_page(ROOT+'other', HOME)) is dom


def test_removing_http_only_navigation_changes_digest_when_rendered_dom_stays_same():
    dom = extract_page(ROOT, DOM)
    with_link = retain_http_publications(dom, extract_page(ROOT, HOME))
    without_link = retain_http_publications(dom, extract_page(ROOT, DOM))
    assert with_link['sha256'] != without_link['sha256']
    assert not without_link['links']


@pytest.mark.parametrize('deny_contact', [False, True])
async def test_real_chromium_research_follows_http_only_routes_and_saves_actual_page_publication(
    db, settings, monkeypatch, deny_contact
):
    settings.crawl_max_pages = 3
    settings.crawl_max_depth = 2
    settings.crawl_max_sitemaps = 0
    settings.crawl_delay_seconds = .001
    settings.browser_settle_seconds = .01
    settings.auto_visual_audit = False
    settings.auto_contact_research = False
    settings.auto_professional_research = False
    settings.sending_enabled = False
    calls=[]
    documents={ROOT:HOME,
        ROOT+'contact':'<title>Bright Demo Contact</title><p>Business enquiries hello@bright-demo.com</p>',
        ROOT+'team':'<title>Bright Demo Team</title><main><article><h2>Alex Doe</h2><p>Founder</p>'
                    '<a href="mailto:alex@bright-demo.com">Business enquiries</a></article></main>'}

    async def get(self, url, *_):
        calls.append(url)
        if url.endswith('/robots.txt'):
            return url, 'User-agent: *\nAllow: /'+ ('\nDisallow: /contact' if deny_contact else ''), 200
        assert url in documents, 'Only explicitly published company routes may be requested'
        html=documents[url]
        self.last_document={'url':url,'body':html.encode(),'status':200,
                            'headers':{'content-type':'text/html'}}
        return url,html,200

    async def forbidden(*_args, **_kwargs):
        pytest.fail('No direct external network/provider/recipient call in this controlled test')

    monkeypatch.setattr(PublicWeb,'get',get)
    monkeypatch.setattr(PublicWeb,'resource',forbidden)
    lid=add_lead(db,'Bright Demo',ROOT,'A',ROOT)
    await research_lead(db,settings,lid)
    expected_calls=[ROOT+'robots.txt', ROOT]+([] if deny_contact else [ROOT+'contact'])+[ROOT+'team']
    assert calls == expected_calls
    contacts=db.all('SELECT * FROM contacts WHERE lead_id=?',(lid,))
    expected_emails={'alex@bright-demo.com'}| (set() if deny_contact else {'hello@bright-demo.com'})
    assert {c['email'] for c in contacts} == expected_emails
    lead=db.one('SELECT * FROM leads WHERE id=?',(lid,))
    for contact in contacts:
        proof=company_publication(db,contact,lead)
        assert proof and proof['url'] != ROOT
        assert contact['verification']=='unverified'
    report=json.loads(db.one('SELECT report FROM crawls WHERE lead_id=?',(lid,))['report'])
    assert report['pages'][0]['http_navigation_retained'] is True
    assert len(report['pages'])==(2 if deny_contact else 3)
    if deny_contact:
        assert any(p['url']==ROOT+'contact' and p['reason']=='robots' for p in report['skipped'])
    assert not db.all('SELECT * FROM messages')
