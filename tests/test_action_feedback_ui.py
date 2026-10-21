"""Actual Chromium feedback flows using isolated API/database fixtures; no external jobs run."""
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from playwright.sync_api import expect, sync_playwright

from outreach.app import create_app
from outreach.research import add_lead


@pytest.fixture
def dashboard(settings):
    settings.worker_enabled = True
    settings.sending_enabled = settings.followups_enabled = False
    client = TestClient(create_app(settings), base_url=settings.public_url,
                        headers={'Authorization':'Bearer '+settings.api_token})
    controls = {'hold': False, 'pending': [], 'mutations': [], 'offline': False, 'activity_offline': False, 'failure': None}
    errors = []
    with sync_playwright() as runtime:
        browser = runtime.chromium.launch()
        context = browser.new_context(viewport={'width': 1440, 'height': 1000})
        def respond(route):
            request = route.request
            path = request.url.removeprefix(settings.public_url)
            response = client.request(request.method, path, content=request.post_data_buffer,
                headers={k:v for k,v in request.headers.items() if k in {'content-type','origin'}})
            route.fulfill(status=response.status_code, body=response.content,
                          headers={'content-type':response.headers.get('content-type','text/plain')})
        def route(r):
            assert r.request.url.startswith(settings.public_url+'/')
            path = r.request.url.removeprefix(settings.public_url)
            if controls['activity_offline'] and path.startswith('/api/leads/') and path.endswith('/activity'):
                r.abort('failed')
                return
            if controls['offline'] and path.startswith('/api/jobs/'):
                r.abort('failed')
                return
            if r.request.method not in {'GET','HEAD'}:
                controls['mutations'].append(path)
                if controls['failure']:
                    status, body = controls['failure']
                    if status is None:
                        r.abort('failed')
                    else:
                        r.fulfill(status=status,json=body)
                    return
                if controls['hold']:
                    controls['pending'].append(r)
                    return
            respond(r)
        context.route('**/*',route)
        page = context.new_page()
        page.on('pageerror',lambda e:errors.append(str(e)))
        yield page, controls, respond, errors
        browser.close()


def search(page, settings):
    page.goto(settings.public_url+'/')
    page.get_by_role('button',name='Find prospects',exact=True).first.click()
    form = page.locator('#search-form')
    form.locator('[name=query]').fill('Fictional UK cleaning businesses')
    form.locator('[name=limit]').fill('2')
    return form.get_by_role('button',name='Start research',exact=True)


@pytest.mark.parametrize('mobile',[False,True])
def test_visible_queue_running_completion_and_refresh_persistence(settings,db,dashboard,mobile):
    page, controls, respond, errors = dashboard
    page.set_viewport_size({'width':390 if mobile else 1440,'height':1000})
    button = search(page,settings)
    controls['hold'] = True
    button.click()
    expect(button).to_be_disabled()
    expect(button).to_have_attribute('aria-busy','true')
    page.evaluate("document.querySelector('#search-form button[type=submit],#search-form button.primary').click()")
    assert controls['mutations'] == ['/api/discover']
    assert len(controls['pending']) == 1
    controls['hold'] = False
    respond(controls['pending'].pop())
    notices = page.locator('#feedback-notifications')
    expect(notices).to_contain_text('Prospect search · Queued')
    expect(button).to_be_enabled()
    expect(button).not_to_have_attribute('aria-busy','true')
    jid = db.one("SELECT id FROM jobs WHERE kind='discover'")['id']
    page.locator('#activity-toggle').click()
    panel = page.locator('#activity-panel')
    expect(panel).to_be_visible()
    expect(panel.locator('.activity-state')).to_have_text('Queued')
    page.wait_for_load_state('networkidle')
    db.execute("UPDATE jobs SET state='running',started_at=? WHERE id=?",(time.time(),jid))
    db.event('discovery_progress',{'job_id':jid,'stage':'google_business_check','company':'Fixture <img onerror=alert(1)>','retained':1})
    page.evaluate('WorkbenchFeedback.poll()')
    expect(panel.locator('.activity-state')).to_have_text('Running')
    expect(panel).to_contain_text('Checking a Google business listing')
    assert panel.locator('img').count() == 0
    page.reload()
    page.locator('#activity-toggle').click()
    expect(page.locator('#activity-panel .activity-state')).to_have_text('Running')
    assert controls['mutations'] == ['/api/discover']
    first=add_lead(db,'Fixture One','https://fixture-one.example.com','A','https://fixture-one.example.com')
    second=add_lead(db,'Fixture Two','https://fixture-two.example.com','A','https://fixture-two.example.com')
    db.event('discovery',{'job_id':jid,'lead_ids':[first,second]})
    db.execute("UPDATE jobs SET state='done' WHERE id=?",(jid,))
    page.wait_for_load_state('networkidle')
    page.evaluate('WorkbenchFeedback.poll()')
    expect(page.locator('#activity-panel .activity-state')).to_have_text('Completed')
    expect(page.locator('#activity-panel')).to_contain_text('2 prospects saved')
    expect(page.locator('#activity-panel')).to_contain_text('detailed research or audits may still be queued')
    page.wait_for_load_state('networkidle')
    output=Path('data/action-feedback-ui')
    output.mkdir(parents=True,exist_ok=True)
    page.screenshot(path=str(output/('activity-mobile.png' if mobile else 'activity-desktop.png')),full_page=True,animations='disabled')
    page.locator('#activity-panel').get_by_role('button',name='Open Pipeline',exact=True).click()
    expect(page.locator('#pipeline')).to_be_visible()
    assert not db.one('SELECT 1 FROM send_attempts')
    assert not errors


@pytest.mark.parametrize('mobile',[False,True])
def test_prospect_research_and_screenshot_states_update_in_place_without_losing_edits(settings,db,dashboard,mobile):
    from outreach.activity import lead_activity
    settings.auto_prepare_enabled=False
    page,controls,_,errors=dashboard
    lid=add_lead(db,'Fictional Swift Fixture','https://swift.example.com','A','https://swift.example.com')
    db.execute("UPDATE leads SET status='review' WHERE id=?",(lid,))
    db.execute('INSERT INTO evidence(lead_id,url,title,text,sha256,fetched_at) VALUES(?,?,?,?,?,?)',
               (lid,'https://swift.example.com/','Fixture source','UK business enquiry source','fixture',time.time()))
    jid=db.enqueue('research',{'lead_id':lid})
    lead=db.one('SELECT * FROM leads WHERE id=?',(lid,))
    previous=lead_activity(db,settings,lead)
    page.set_viewport_size({'width':390 if mobile else 1440,'height':1000})
    page.goto(settings.public_url+'/?prospect='+str(lid))
    panel=page.get_by_role('region',name='Research progress')
    expect(panel).to_contain_text('Research queued')
    expect(page.locator('[data-lead="'+str(lid)+'"]')).to_contain_text('Research queued')
    expect(panel).to_contain_text('No action needed')
    expect(panel).to_contain_text('Screenshots waiting for website research')
    expect(panel).to_contain_text('automatic email preparation is OFF')
    expect(page.locator('[data-research-step]')).not_to_have_class('done')
    expect(page.locator('#prepare-emails')).to_be_disabled()
    db.execute("UPDATE jobs SET state='running',started_at=? WHERE id=?",(time.time(),jid))
    page.evaluate('([id,previous])=>{clearTimeout(researchActivityTimer);return pollResearchActivity(id,previous);}',[lid,previous])
    expect(panel).to_contain_text('Research running')
    previous=lead_activity(db,settings,lead)
    db.execute("UPDATE jobs SET state='done' WHERE id=?",(jid,))
    capture_id=db.enqueue('screenshot',{'lead_id':lid})
    page.evaluate('([id,previous])=>{clearTimeout(researchActivityTimer);return pollResearchActivity(id,previous);}',[lid,previous])
    expect(panel).to_contain_text('Screenshots queued')
    page.locator('#advanced-research > summary').click()
    page.locator('#qualification-tools-group > summary').click()
    page.locator('#review-form').locator('..').locator('summary').first.click()
    name=page.locator('#review-form [name=company]')
    name.fill('Unsaved fictional company edit')
    previous=lead_activity(db,settings,lead)
    folder=settings.data_dir/'screenshots'
    folder.mkdir(exist_ok=True)
    filename=f'lead-{lid}-123456-abcdef-desktop.png'
    (folder/filename).write_bytes(b'fictional image fixture')
    db.event('screenshot',{'lead_id':lid,'url':lead['website'],'complete':False,'issues':['fixture rendering issue'],'files':{'desktop':filename}})
    db.execute("UPDATE jobs SET state='done' WHERE id=?",(capture_id,))
    page.evaluate('([id,previous])=>{clearTimeout(researchActivityTimer);return pollResearchActivity(id,previous);}',[lid,previous])
    expect(panel).to_contain_text('Research saved')
    expect(panel).to_contain_text('Screenshots saved · partial capture')
    expect(panel.get_by_role('link',name='View desktop screenshot')).to_have_attribute('href','/api/screenshots/'+filename)
    expect(panel.get_by_role('button',name='View updated research')).to_be_visible()
    expect(name).to_have_value('Unsaved fictional company edit')
    expect(page.locator('[data-lead="'+str(lid)+'"]')).to_contain_text('Research saved')
    expect(page.locator('[data-research-step]')).to_have_class('done')
    assert not controls['mutations'] and not errors
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')
    panel.scroll_into_view_if_needed()
    output=Path('data/research-status-ui')
    output.mkdir(parents=True,exist_ok=True)
    panel.screenshot(path=str(output/('status-mobile.png' if mobile else 'status-desktop.png')))
    page.screenshot(path=str(output/('mobile.png' if mobile else 'desktop.png')),full_page=True)


def test_prospect_status_reports_pause_offline_and_failure_without_repeating_research(settings,db,dashboard):
    from outreach.activity import lead_activity
    page,controls,_,errors=dashboard
    settings.worker_enabled=False
    lid=add_lead(db,'Fictional Paused Fixture','https://paused.example.com','A','https://paused.example.com')
    jid=db.enqueue('research',{'lead_id':lid})
    lead=db.one('SELECT * FROM leads WHERE id=?',(lid,))
    previous=lead_activity(db,settings,lead)
    page.goto(settings.public_url+'/?prospect='+str(lid))
    panel=page.get_by_role('region',name='Research progress')
    expect(panel).to_contain_text('Research automation is OFF')
    controls['activity_offline']=True
    page.evaluate('([id,previous])=>{clearTimeout(researchActivityTimer);return pollResearchActivity(id,previous);}',[lid,previous])
    expect(panel).to_contain_text('Live status is unavailable')
    expect(panel).to_contain_text('Research queued')
    controls['activity_offline']=False
    db.execute("UPDATE jobs SET state='failed',error=? WHERE id=?",('Fictional source failed <script>bad()</script>',jid))
    page.locator('#advanced-research > summary').click()
    page.evaluate('([id,previous])=>{clearTimeout(researchActivityTimer);return pollResearchActivity(id,previous);}',[lid,previous])
    expect(panel).to_contain_text('Research needs attention')
    expect(panel).to_contain_text('Fictional source failed <script>bad()</script>')
    expect(panel).not_to_contain_text('Live status is unavailable')
    assert panel.locator('script').count()==0
    assert page.evaluate("leadState({status:'researching',source_job:{state:'failed',kind:'research'}})[0]") == 'Needs attention'
    assert page.evaluate("leadState({status:'researching',source_job:null})[0]") == 'Research status needs checking'
    assert not controls['mutations'] and not errors
    assert page.evaluate('document.documentElement.scrollWidth<=innerWidth+1')


def test_finished_research_refreshes_clean_workspace_automatically(settings,db,dashboard):
    from outreach.activity import lead_activity
    page,controls,_,errors=dashboard
    settings.auto_prepare_enabled=False
    lid=add_lead(db,'Fictional Completed Fixture','https://completed.example.com','A','https://completed.example.com')
    jid=db.enqueue('research',{'lead_id':lid})
    lead=db.one('SELECT * FROM leads WHERE id=?',(lid,))
    previous=lead_activity(db,settings,lead)
    page.goto(settings.public_url+'/?prospect='+str(lid))
    expect(page.locator('#prospect-research-status')).to_contain_text('Research queued')
    db.execute('INSERT INTO evidence(lead_id,url,title,text,sha256,fetched_at) VALUES(?,?,?,?,?,?)',
               (lid,lead['website'],'Saved fixture','Current UK business fixture','fixture',time.time()))
    db.execute("UPDATE jobs SET state='done' WHERE id=?",(jid,))
    db.execute("UPDATE leads SET status='review' WHERE id=?",(lid,))
    page.evaluate('([id,previous])=>{clearTimeout(researchActivityTimer);return pollResearchActivity(id,previous);}',[lid,previous])
    expect(page.locator('#prospect-research-status')).to_contain_text('Research saved')
    expect(page.locator('#prospect-research-status')).to_contain_text('1 saved page contents')
    expect(page.locator('[aria-label="Email preparation"]')).to_be_visible()
    expect(page.locator('#detail')).to_contain_text('Saved source pages (1)')
    assert not controls['mutations'] and not errors


@pytest.mark.parametrize('failure',[503,None])
def test_failed_or_unknown_request_is_visible_and_never_repeated(settings,db,dashboard,failure):
    page, controls, _, errors = dashboard
    button=search(page,settings)
    controls['failure']=(failure,{'detail':'Fixture provider unavailable'})
    button.click()
    toast=page.locator('#feedback-notifications .feedback-toast.error')
    expect(toast).to_be_visible()
    expect(toast).to_contain_text('Fixture provider unavailable' if failure else 'Request status is unknown')
    expect(button).to_be_enabled()
    assert controls['mutations']==['/api/discover']
    assert not db.one('SELECT 1 FROM jobs')
    assert not errors


def test_paused_worker_offline_status_and_recorded_failure_are_distinct(settings,db,dashboard):
    page, controls, _, errors=dashboard
    settings.worker_enabled=False
    search(page,settings).click()
    expect(page.locator('#feedback-notifications')).to_contain_text('automation is OFF')
    page.locator('#activity-toggle').click()
    page.wait_for_load_state('networkidle')
    controls['offline']=True
    page.evaluate('WorkbenchFeedback.poll()')
    expect(page.locator('.activity-connection')).to_contain_text('Existing jobs may still be running')
    expect(page.locator('.activity-state')).to_have_text('Status unavailable')
    expect(page.locator('#activity-toggle')).to_have_attribute('aria-label','Activity, status updates unavailable')
    assert controls['mutations']==['/api/discover']
    controls['offline']=False
    db.execute("UPDATE jobs SET state='failed',error='Fixture search provider rejected the request'")
    page.evaluate('WorkbenchFeedback.poll()')
    expect(page.locator('.activity-state')).to_have_text('Failed')
    expect(page.locator('#activity-panel')).to_contain_text('Fixture search provider rejected the request')
    assert not errors


def test_settings_validation_errors_are_visible_without_echoing_secrets(settings,dashboard):
    page, controls, _, errors=dashboard
    page.goto(settings.public_url+'/')
    page.get_by_role('button',name='Settings',exact=True).click()
    form=page.locator('#writer-settings-form')
    form.locator('[name=draft_api_key]').fill('fictional-private-input-marker')
    controls['failure']=(422,{'detail':[{'loc':['body','draft_api_key'],'msg':'Invalid value','input':'fictional-private-input-marker'}]})
    form.get_by_role('button',name='Save AI writer settings',exact=True).click()
    expect(page.locator('#feedback-notifications')).to_contain_text('draft_api_key: Invalid value')
    assert 'fictional-private-input-marker' not in page.locator('body').inner_text()
    expect(form.get_by_role('button',name='Save AI writer settings',exact=True)).to_be_enabled()
    assert not errors


def test_unsaved_writer_test_and_local_preset_give_visible_feedback(settings,dashboard):
    page, controls, _, errors=dashboard
    page.goto(settings.public_url+'/')
    page.get_by_role('button',name='Settings',exact=True).click()
    form=page.locator('#writer-settings-form')
    expect(page.locator('#writer-settings-result')).not_to_contain_text('Loading')
    page.wait_for_load_state('networkidle')
    form.locator('[name=draft_model]').fill('fictional-unsaved-model')
    page.locator('#writer-test').click()
    expect(page.locator('#feedback-notifications')).to_contain_text('Unsaved AI settings')
    assert controls['mutations']==[]
    page.locator('#writer-nvidia').click()
    expect(page.locator('#feedback-notifications')).to_contain_text('NVIDIA values filled')
    assert not errors


@pytest.mark.parametrize('row_errors',[[],[{'row':3,'error':'Fixture row needs a valid website'}]])
def test_import_result_counts_and_warning_tone_match_partial_outcome(settings,dashboard,row_errors):
    page, controls, _, errors=dashboard
    page.goto(settings.public_url+'/')
    page.get_by_role('button',name='Find prospects',exact=True).first.click()
    page.locator('.discovery-advanced > summary').click()
    page.locator('#csv-file').set_input_files({'name':'fixture.csv','mimeType':'text/csv',
        'buffer':b'company,website,campaign\nFixture,https://fixture.example.com,A\n'})
    controls['failure']=(200,{'ids':[1],'errors':row_errors})
    page.locator('#csv-form').get_by_role('button',name='Import',exact=True).click()
    expect(page.locator('#notice')).to_contain_text('Import processed: 1 rows accepted; '+str(len(row_errors))+' rows need attention')
    expect(page.locator('#feedback-notifications .feedback-toast').last).to_have_attribute('data-tone','warning' if row_errors else 'success')
    assert controls['mutations']==['/api/import']
    assert not errors
