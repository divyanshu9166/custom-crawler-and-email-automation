"""Independent public-journey evidence, negative cases and source-to-copy gates."""
from pathlib import Path
from types import SimpleNamespace

import pytest
from playwright.sync_api import sync_playwright

from outreach import diagnostics, email_writer, journey, preparation
from outreach.conclusions import build


URL = 'https://bright-demo.com/'
IMAGE = 'lead-1-1792410725-123abc-mobile.png'


def sample(**patch):
    return {'ready': True, 'styles_ready': True, 'url': URL, 'width': 390, 'scroll_width': 390,
            'controls': [{'selector': '#email', 'hint': 'Email', 'type': 'email'}],
            'ctas': [{'selector': '#quote', 'label': 'Get a quote', 'url': URL+'quote/'}], **patch}


def report():
    return {'version': 1, 'state': 'checked', 'captures': [journey.capture(sample(),sample(),'mobile',IMAGE)],
            'links': [], 'limitations': []}


@pytest.mark.parametrize('change', ['ready','styles','url','width','controls'])
def test_incomplete_unstable_or_unstyled_capture_does_not_invent_a_form_problem(change):
    first, second = sample(), sample()
    if change == 'ready':
        second['ready'] = False
    elif change == 'styles':
        second['styles_ready'] = False
    elif change == 'url':
        second['url'] = URL+'other/'
    elif change == 'width':
        second['width'] = 1440
    else:
        second['controls'] = []
    assert not journey.capture(first,second,'mobile',IMAGE)['findings']


def test_repeatable_problem_has_selector_capture_and_matching_implementation():
    audit = {'reports': [{'event_id':1}], 'observations':journey.observations(report(), {'id':1,'website':URL},1,100)}
    value = build(audit, 'website_improvement')
    point = value['findings'][0]
    assert value['draft_allowed'] and point['screenshot'] == IMAGE
    assert point['selector'] == '#email' and 'persistent labels' in point['proposed_fix']
    assert 'keyboard' in point['proposed_fix'] and 'Repeat' in point['verification']
    assert not value['business_pain_confirmed']


def test_aggregate_low_score_without_underlying_finding_holds_improvement_pitch(db,prepared):
    lid = prepared['lead_id']
    db.event('performance', {'lead_id':lid,'url':URL,'status':'complete',
        'strategies':{'mobile':{'score':51,'final_url':URL}}})
    audit = diagnostics.snapshot(db,db.one('SELECT * FROM leads WHERE id=?',(lid,)))
    assert audit['reports'][0]['measurements'][0]['score'] == 51
    assert not audit['conclusion']['draft_allowed']
    assert not audit['conclusion']['findings']


@pytest.mark.parametrize('metric,value,unit,fragment,ready', [
    ('largest-contentful-paint',4800,'millisecond','largest visible element',True),
    ('largest-contentful-paint',4800,'seconds','',False),
    ('total-blocking-time',350,'millisecond','main-thread tasks',True),
    ('total-blocking-time',100,'millisecond','',False),
    ('cumulative-layout-shift',.25,'unitless','layout-shift trace',True),
    ('cumulative-layout-shift',.25,'millisecond','',False),
    ('first-contentful-paint',2800,'millisecond','initial rendering path',True),
    ('first-contentful-paint',800,'millisecond','',False)])
def test_underlying_lab_metric_has_a_matching_bounded_repair(db,prepared,metric,value,unit,fragment,ready):
    lid = prepared['lead_id']
    db.event('performance', {'lead_id':lid,'url':URL,'status':'complete',
        'strategies':{'mobile':{'score':51,'final_url':URL,
            'metrics':{metric:{'numericValue':value,'numericUnit':unit}}}}})
    result = diagnostics.snapshot(db,db.one('SELECT * FROM leads WHERE id=?',(lid,)))['conclusion']
    assert result['draft_allowed'] is ready
    if ready:
        assert fragment in result['findings'][0]['proposed_fix']


@pytest.mark.parametrize('wording', ['precise','wrong_unit','whole_page'])
def test_email_can_use_one_underlying_lab_timing_without_a_generic_score(db,prepared,wording):
    lid = prepared['lead_id']
    db.event('performance', {'lead_id':lid,'url':URL,'status':'partial',
        'strategies':{'mobile':{'score':58,'final_url':URL,
            'opportunities':[{'id':'font-display-insight'}],
            'metrics':{'largest-contentful-paint':{'numericValue':13100,'numericUnit':'millisecond'}}}}})
    lead = db.one('SELECT * FROM leads WHERE id=?',(lid,))
    audit = diagnostics.snapshot(db,lead)
    assert '13.1 seconds' in audit['conclusion']['summary']
    point = audit['observations'][0]
    observation = ('largest visible content took 13.1 seconds' if wording == 'precise' else
        'largest visible content took 13.1 milliseconds' if wording == 'wrong_unit' else 'the whole page loaded in 13.1 seconds')
    body = ('In our mobile Lighthouse lab test for Bright Demo, '+observation+'. '
        'I can adjust font loading so service text appears sooner, then retest the existing enquiry journey. '
        'Would a short walkthrough of the proposed fix be useful?')
    output = {'messages':[{'step':0,'subject':'Bright Demo enquiry journey','body':body,
        'diagnostic_refs':[point['ref']],
        'support':[{'evidence_id':prepared['evidence_id'],'quote':'Contact us for a consultation.'}]}]}
    args = (output,lead,db.one('SELECT * FROM contacts WHERE id=?',(prepared['contact_id'],)),db.all('SELECT * FROM evidence'))
    if wording == 'precise':
        assert email_writer.validate_output(*args,audit_context=audit)
    else:
        with pytest.raises(ValueError):
            email_writer.validate_output(*args,audit_context=audit)


def test_overlong_initial_pitch_is_rejected_before_it_can_replace_copy(db,prepared):
    lead = db.one('SELECT * FROM leads WHERE id=?',(prepared['lead_id'],))
    contact = db.one('SELECT * FROM contacts WHERE id=?',(prepared['contact_id'],))
    value = {'messages':[{'step':0,'subject':'Bright Demo proposal',
        'body':('Discuss the proposed enquiry improvement. '*30)+'Would a walkthrough help?',
        'support':[{'evidence_id':prepared['evidence_id'],'quote':'Contact us for a consultation.'}]}]}
    with pytest.raises(ValueError,match='130 words'):
        email_writer.validate_output(value,lead,contact,db.all('SELECT * FROM evidence'))


@pytest.mark.parametrize('url', ['https://other-demo.com/contact/','http://127.0.0.1/admin', URL+'logout/', URL+'contact/?delete=1', URL+'#contact','mailto:team@bright-demo.com'])
def test_external_mutating_or_non_navigation_urls_are_not_requested(url):
    value = journey.capture(sample(),sample(),'mobile',IMAGE)
    value['ctas'][0]['url'] = url
    assert not journey.targets(URL, [value])


@pytest.mark.parametrize('statuses,confirmed', [([404,404],True),([410,410],True),([404,200],False),([403],False),([429],False),([500],False),([200],False)])
async def test_broken_link_needs_two_matching_http_errors(statuses, confirmed):
    calls = []
    responses = iter(statuses)
    async def resource(url, domain, **kw):
        assert domain == 'bright-demo.com' and kw['redirects'] is False
        calls.append(url)
        return {'url':url,'status':next(responses),'headers':{}}
    web = SimpleNamespace(settings=SimpleNamespace(crawler_user_agent='test'),resource=resource)
    robots = SimpleNamespace(can_fetch=lambda *a:True)
    target = journey.targets(URL, [journey.capture(sample(),sample(),'mobile',IMAGE)])[0]
    value = await journey.check_link(web, robots, URL, target)
    assert (value['state']=='confirmed_http_error') is confirmed
    assert len(calls) == len(statuses)


async def test_redirect_robots_and_external_hosts_are_checked_before_following():
    calls = []
    async def resource(url, domain, **kw):
        calls.append(url)
        return {'url':url,'status':302,'headers':{'location':'https://other-demo.com/private'}}
    web = SimpleNamespace(settings=SimpleNamespace(crawler_user_agent='test'),resource=resource)
    robots = SimpleNamespace(can_fetch=lambda *a:True)
    target = {'url':URL+'quote/','selector':'#quote','label':'Get a quote'}
    assert (await journey.check_link(web,robots,URL,target))['state'] == 'unavailable'
    assert len(calls) == 1
    calls.clear()
    robots.can_fetch = lambda *a:False
    assert (await journey.check_link(web,robots,URL,target))['state'] == 'unavailable'
    assert not calls


@pytest.mark.parametrize('state', ['valid','stale','old_cycle','wrong_target','bad_image','unstable','late_completion'])
def test_current_scoped_journey_observation_can_survive_unrelated_analytics_failures(db,prepared,state):
    import time
    lid = prepared['lead_id']
    data = report()
    if state == 'bad_image':
        data['captures'][0]['screenshot'] = 'lead-999-1792410725-123abc-mobile.png'
    if state == 'unstable':
        data['captures'][0]['state'] = 'incomplete'
    db.event('screenshot', {'lead_id':lid,'url':URL if state!='wrong_target' else 'https://other-demo.com/',
        'complete':False,'issues':[{'reason':'analytics_denied'}],'journey':data})
    if state == 'stale':
        db.execute("UPDATE events SET created_at=? WHERE kind='screenshot'", (time.time()-8*86400,))
    if state == 'old_cycle':
        db.execute('INSERT INTO crawls(lead_id,report,created_at) VALUES(?,?,?)',(lid,'{}',time.time()+1))
    if state == 'late_completion':
        row = db.one("SELECT id,detail FROM events WHERE kind='screenshot'")
        import json
        value = json.loads(row['detail'])
        value['requested_at'] = time.time()-60
        db.execute('UPDATE events SET detail=? WHERE id=?',(json.dumps(value),row['id']))
        db.execute('INSERT INTO crawls(lead_id,report,created_at) VALUES(?,?,?)',(lid,'{}',time.time()-30))
    value = diagnostics.snapshot(db, db.one('SELECT * FROM leads WHERE id=?',(lid,)))
    assert bool(value['observations']) is (state == 'valid')
    if state == 'valid':
        assert value['conclusion']['findings'][0]['code'] == 'form_labels'


def test_automatic_preparation_queues_audit_before_model_and_preserves_existing_copy(settings,db,prepared,monkeypatch):
    settings.journey_audit_enabled = True
    settings.draft_api_key, settings.draft_model = 'fixture-key', 'fixture-model'
    monkeypatch.setattr(preparation, '_assessment', lambda *a,**k:pytest.fail('Must audit before assessment'))
    preparation.prepare(db,settings,prepared['lead_id'])
    assert not db.one("SELECT id FROM jobs WHERE kind='screenshot'")
    db.execute('DELETE FROM messages')
    preparation.prepare(db,settings,prepared['lead_id'])
    assert db.one("SELECT id FROM jobs WHERE kind='screenshot' AND state='pending'")
    assert preparation.latest(db,prepared['lead_id'])['research_pending']
    db.execute("UPDATE jobs SET state='failed' WHERE kind='screenshot'")
    db.event('journey_audit_started', {'lead_id':prepared['lead_id'],'url':URL,'version':1})
    lead = db.one('SELECT * FROM leads WHERE id=?',(prepared['lead_id'],))
    assert not journey.needs_audit(db,settings,lead)


@pytest.mark.parametrize('copy_kind', ['good','score_only','audit_only'])
def test_writer_must_explain_the_strongest_journey_finding_and_concrete_repair(db,prepared,copy_kind):
    lid = prepared['lead_id']
    db.event('screenshot', {'lead_id':lid,'url':URL,'complete':False,'journey':report()})
    lead = db.one('SELECT * FROM leads WHERE id=?',(lid,))
    contact = db.one('SELECT * FROM contacts WHERE id=?',(prepared['contact_id'],))
    audit = diagnostics.snapshot(db,lead)
    point = audit['observations'][0]
    body = ('In our mobile capture, Bright Demo enquiry fields have no connected labels. '
            'I can add persistent labels to the existing enquiry form layout and check keyboard use, '
            'keeping its current integrations. The aim is to make each field clearer to identify. '
            'Would a short walkthrough of the finding and proposed fix be useful?')
    if copy_kind == 'audit_only':
        body = 'Our capture of Bright Demo shows fields without labels. Would another general audit of the enquiry form be useful?'
    refs = [] if copy_kind == 'score_only' else [point['ref']]
    output = {'messages':[{'step':0,'subject':'Bright Demo enquiry form','body':body,
        'support':[{'evidence_id':prepared['evidence_id'],'quote':'Contact us for a consultation.'}], 'diagnostic_refs':refs}]}
    if copy_kind == 'good':
        assert email_writer.validate_output(output,lead,contact,db.all('SELECT * FROM evidence'),audit_context=audit)
    else:
        with pytest.raises(ValueError):
            email_writer.validate_output(output,lead,contact,db.all('SELECT * FROM evidence'),audit_context=audit)


def test_real_dom_reader_distinguishes_business_form_labels_hidden_fields_and_newsletter():
    reader = Path('outreach/static/journey-reader.js').read_text(encoding='utf-8')
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width':390,'height':844})
        page.set_content('''<html><body><h1>Fictional quote</h1>
          <form><input id="name" placeholder="Name"><input id="email" type="email" placeholder="Email">
          <input style="display:none" id="secret"><textarea aria-label="Message"></textarea>
          <button>Get a quote</button></form><form><input type="email"><button>Subscribe</button></form>
          <form style="opacity:0"><input id="invisible"><button>Contact</button></form>
          <a id="quote" href="https://bright-demo.com/quote/">Get a quote</a></body></html>''')
        first = page.evaluate(reader)
        assert {c['selector'] for c in first['controls']} == {'#name','#email'}
        assert first['ctas'][0]['selector'] == '#quote'
        page.evaluate("document.querySelector('#name').setAttribute('aria-label','Name'); document.querySelector('#email').insertAdjacentHTML('beforebegin','<label for=email>Email</label>')")
        assert page.evaluate(reader)['controls'] == []
        browser.close()


async def test_real_mediated_audit_follows_two_task_pages_and_retains_existing_draft(settings,db,prepared,monkeypatch):
    from urllib.robotparser import RobotFileParser
    from outreach.browser import screenshot
    from outreach.web import PublicWeb
    import json
    settings.journey_audit_enabled = True
    settings.browser_settle_seconds = .1
    robots = RobotFileParser()
    robots.parse(['User-agent: *','Allow: /'])
    calls = []
    root = '<html><title>Fictional business</title><a id="quote" href="/quote/">Get a quote</a><a href="/contact/">Contact</a></html>'
    contact = '<html><title>Fictional enquiry</title><form><input id="email" type="email" placeholder="Email"><textarea aria-label="Message"></textarea><button>Send enquiry</button></form></html>'
    async def allow(*args):
        return robots, None, None
    async def resource(self, url, *args, **kwargs):
        calls.append(url)
        return {'url':url,'body':(contact if url==URL+'contact/' else root).encode(),
            'status':404 if url==URL+'quote/' else 200,
            'headers':{'content-type':'text/html'},'encoding':'utf-8'}
    monkeypatch.setattr(PublicWeb,'robots',allow)
    monkeypatch.setattr(PublicWeb,'resource',resource)
    before = db.all('SELECT * FROM messages')
    await screenshot(db,settings,prepared['lead_id'])
    raw = json.loads(db.one("SELECT detail FROM events WHERE kind='screenshot'")['detail'])
    assert {c['url'] for c in raw['journey']['captures']} == {URL,URL+'contact/'}
    assert calls.count(URL+'quote/') == 2
    audit = diagnostics.snapshot(db,db.one('SELECT * FROM leads WHERE id=?',(prepared['lead_id'],)))
    assert audit['observations'][0]['code'] == 'broken_cta'
    assert any(o.get('code') == 'form_labels' and o['url']==URL+'contact/' for o in audit['observations'])
    assert (settings.data_dir/'screenshots'/audit['observations'][0]['screenshot']).exists()
    from outreach.deliverables import prepare_automatic
    aid = prepare_automatic(db,prepared['lead_id'])
    artifact = db.one('SELECT body FROM deliverables WHERE id=?',(aid,))
    assert 'data:image/png;base64,' in artifact['body'] and 'HTTP 404' in artifact['body']
    assert 'Repair the existing enquiry/booking link' in artifact['body']
    assert db.all('SELECT * FROM messages') == before


async def test_failed_linked_capture_keeps_root_findings_and_stops_as_partial():
    async def resource(url, *args, **kwargs):
        return {'url':url,'status':200,'headers':{}}
    async def failed(*args):
        raise ValueError('Controlled render failure')
    web = SimpleNamespace(settings=SimpleNamespace(crawler_user_agent='test'),resource=resource)
    robots = SimpleNamespace(can_fetch=lambda *a:True)
    result = await journey.extend(web,robots,URL,{'journey_checks':[journey.capture(sample(),sample(),'mobile',IMAGE)]},failed)
    assert result['state']=='partial' and result['captures'][0]['findings']
    assert 'ValueError' in result['limitations'][0]


@pytest.mark.parametrize('mobile', [False,True])
def test_one_click_checks_journey_before_writer_and_shows_pending_stage(settings,db,prepared,monkeypatch,mobile):
    from fastapi.testclient import TestClient
    from outreach.app import create_app
    from playwright.sync_api import expect
    settings.journey_audit_enabled = settings.worker_enabled = True
    settings.sending_enabled = False
    settings.draft_api_key, settings.draft_model = 'fixture-key', 'fixture-model'
    db.execute('DELETE FROM messages')
    monkeypatch.setattr(preparation,'_assessment',lambda *a,**k:pytest.fail('Do not call the writer before audit'))
    client = TestClient(create_app(settings),base_url=settings.public_url,
        headers={'Authorization':'Bearer '+settings.api_token})
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={'width':390 if mobile else 1440,'height':900})
        def route(r):
            assert r.request.url.startswith(settings.public_url+'/')
            response = client.request(r.request.method,r.request.url.removeprefix(settings.public_url),
                content=r.request.post_data_buffer, headers={k:v for k,v in r.request.headers.items() if k in {'content-type','origin'}})
            r.fulfill(status=response.status_code,body=response.content,
                headers={'content-type':response.headers.get('content-type','text/plain')})
        context.route('**/*',route)
        page = context.new_page()
        page.clock.install()
        page.goto(settings.public_url+'/?prospect='+str(prepared['lead_id']))
        page.get_by_role('button',name='Check journey & prepare email',exact=True).click()
        expect(page.locator('#prepare-emails')).to_be_disabled()
        preparation.prepare(db,settings,prepared['lead_id'])
        db.execute("UPDATE jobs SET state='done' WHERE kind='prepare'")
        page.clock.fast_forward(5000)
        expect(page.get_by_role('region',name='Email preparation')).to_contain_text('Checking the enquiry journey')
        assert db.one("SELECT id FROM jobs WHERE kind='screenshot' AND state='pending'")
        assert not db.one('SELECT id FROM messages')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
        browser.close()
