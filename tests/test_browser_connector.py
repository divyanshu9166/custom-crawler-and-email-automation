import json
import shutil
import subprocess
from pathlib import Path

import pytest
from playwright.sync_api import sync_playwright

from outreach.browser_references import save_reference

ROOT = Path(__file__).resolve().parents[1]
READER = ROOT/'deploy/browser-connector/reader.js'
LINKEDIN = 'https://www.linkedin.com/company/bright-demo/about/'
BASE = '''<nav><button>PRIVATE TEST ACCOUNT</button></nav><h1>Bright Studio</h1>
<a href="/company/bright-demo/about/">About</a><dl><dt><h3>Website</h3></dt>
<dd><a href="https://bright-demo.com/contact">Our website</a></dd>
<dt>Phone</dt><dd>PRIVATE TEST PHONE NOT COLLECTED</dd></dl>
<aside><a href="https://irrelevant-ad.com">An ad</a></aside>'''


@pytest.fixture(scope='module')
def browser():
    with sync_playwright() as p:
        instance = p.chromium.launch()
        yield instance
        instance.close()


def capture(browser, url=LINKEDIN, html=BASE):
    with browser.new_context() as context:
        context.route('**/*', lambda route: route.fulfill(status=200, body=html, content_type='text/html'))
        page = context.new_page()
        page.goto(url)
        page.add_script_tag(path=str(READER))
        return page.evaluate('OutreachBusinessReader()')


def test_scoped_company_reader_excludes_navigation_phone_and_ads(browser, db):
    ref = capture(browser)
    assert ref['company'] == 'Bright Studio' and ref['website'] == 'https://bright-demo.com/contact'
    assert ref['source_url'] == LINKEDIN.rstrip('/')
    assert 'PRIVATE' not in json.dumps(ref) and 'irrelevant-ad' not in json.dumps(ref)
    result = save_reference(db, **ref, campaign='A', country_hint='UK', public_business_confirmed=True)
    event = json.loads(db.one("SELECT detail FROM events WHERE kind='browser_business_reference'")['detail'])
    assert event['method'] == 'browser_connector_reference'
    assert event['contact_publication_proof'] is False and event['identity_verified'] is False
    assert db.one('SELECT status FROM leads WHERE id=?', (result['id'],))['status'] == 'new'
    assert not db.all('SELECT * FROM contacts') and not db.all('SELECT * FROM evidence')


@pytest.mark.parametrize('url,html', [
    ('https://www.linkedin.com/in/private-person', BASE),
    ('https://www.linkedin.com/messaging/', BASE),
    (LINKEDIN, BASE.replace('<h1>Bright Studio</h1>', '<h1 hidden>Bright Studio</h1>')),
    (LINKEDIN, BASE.replace('/company/bright-demo/about/', '/company/old-company/about/')),
    (LINKEDIN, BASE.replace('https://bright-demo.com/contact', 'http://127.0.0.1/internal')),
    (LINKEDIN, BASE.replace('https://bright-demo.com/contact', 'javascript:alert(1)')),
    (LINKEDIN, BASE.replace('</dd>', '<a href="https://another-company.com">Other company</a></dd>', 1)),
    (LINKEDIN, '<h1>Sign in</h1><input type="password">'),
    ('https://notlinkedin.com/company/bright-demo/about/', BASE),
])
def test_missing_ambiguous_private_or_stale_page_is_not_captured(browser, url, html):
    assert capture(browser, url, html) is None


@pytest.mark.parametrize('authority', [
    'demo-user@bright-demo.com',
    ':demo-only@bright-demo.com',
    'demo-user:demo-only@bright-demo.com',
    'bright-demo.com:8443',
])
def test_website_candidate_rejects_embedded_credentials_and_custom_port(browser, authority):
    html = BASE.replace('https://bright-demo.com/contact', f'https://{authority}/contact')
    assert capture(browser, html=html) is None


def test_modern_x_header_uses_only_public_website_label(browser):
    html = '''<div><h1>Bright Studio</h1><p>Profile bio</p><div><div>
    <a href="https://t.co/opaque">bright-demo.com</a><a href="/BrightDemo/about">Joined 2020</a>
    </div></div></div><article><a href="https://irrelevant-ad.com">Other post</a>
    <a href="/BrightDemo/status/123">Date</a></article><div>PRIVATE TEST NAV</div>'''
    result = capture(browser, 'https://x.com/BrightDemo', html)
    assert result['company'] == 'Bright Studio' and result['website'] == 'https://bright-demo.com/'
    assert 'label' in result['observation'] and 'PRIVATE' not in json.dumps(result)
    assert capture(browser, 'https://x.com/messages', html) is None
    assert capture(browser, 'https://x.com/BrightDemo/status/123', html) is None


def test_collector_deduplicates_and_stops_on_request(browser):
    with browser.new_context() as context:
        context.route('**/*', lambda route: route.fulfill(status=200,body=BASE,content_type='text/html'))
        page=context.new_page()
        page.goto(LINKEDIN)
        page.evaluate('''() => {
          window.recorded=[]; window.listeners=[];
          window.chrome={runtime:{sendMessage:async m=>{recorded.push(m.reference);return {saved:true};},
          onMessage:{addListener:f=>listeners.push(f),removeListener:f=>listeners=listeners.filter(x=>x!==f)}}};
        }''')
        page.add_script_tag(path=str(READER))
        page.add_script_tag(path=str(ROOT/'deploy/browser-connector/collector.js'))
        page.wait_for_function('recorded.length===1')
        page.evaluate("document.body.append(document.createElement('span'))")
        page.wait_for_timeout(950)
        assert page.evaluate('recorded.length') == 1
        page.evaluate("listeners[0]({type:'stop-collector'}); document.querySelector('dd a').href='https://other-demo.com';")
        page.wait_for_timeout(950)
        assert page.evaluate('recorded.length') == 1
        assert page.evaluate('listeners.length') == 0


def test_extension_uses_no_persistent_site_or_account_permissions():
    manifest=json.loads((ROOT/'deploy/browser-connector/manifest.json').read_text())
    assert set(manifest['permissions']) == {'activeTab','scripting','storage'}
    assert not manifest.get('host_permissions') and not manifest.get('content_scripts')
    assert not manifest.get('externally_connectable')


def test_unknown_capture_method_cannot_forge_first_party_provenance(db):
    with pytest.raises(ValueError, match='Unsupported browser reference method'):
        save_reference(db, company='Bright Studio', source_url=LINKEDIN, website='https://bright-demo.com',
                       campaign='A',country_hint='UK',observed_at=0,observation='A public website label',
                       public_business_confirmed=True,capture_method='verified_linkedin_api')
    assert not db.all('SELECT * FROM leads')


def test_extension_background_arm_buffer_and_origin_lifecycle():
    node=shutil.which('node')
    if not node:
        pytest.skip('Node required for the isolated Chrome service-worker mock')
    code=r'''
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const listeners={}, state={armed:{tabId:7,origin:'https://www.linkedin.com'},references:[]}, executed=[];
const event=key=>({addListener:f=>listeners[key]=f});
const chrome={runtime:{onMessage:event('message')},storage:{local:{
  get:async()=>structuredClone(state),set:async value=>Object.assign(state,structuredClone(value)),remove:async key=>delete state[key]}},
  tabs:{onUpdated:event('updated'),onRemoved:event('removed')},scripting:{executeScript:async value=>executed.push(value)}};
const context=vm.createContext({chrome,URL,Promise});
vm.runInContext(fs.readFileSync(process.argv[1],'utf8'),context);
const source='https://www.linkedin.com/company/bright-demo/about';
const ref={company:'Bright Studio',source_url:source,website:'https://bright-demo.com',observed_at:1,
  observation:'A public business website link',capture_method:'browser_connector_reference',privateSecret:'MUST NOT BE STORED'};
const send=(reference=ref,sender={tab:{id:7},url:source})=>new Promise(resolve=>listeners.message({type:'business-reference',reference},sender,resolve));
(async()=>{
  assert.equal((await send()).saved,true);assert.equal(state.references.length,1);
  assert.equal(state.references[0].privateSecret,undefined);
  await Promise.all([send(),send(),send()]);assert.equal(state.references.length,1);
  assert.equal((await send(ref,{tab:{id:8},url:source})).saved,false);
  assert.equal((await send({...ref,source_url:'https://www.linkedin.com/company/old/about'})).saved,false);
  assert.equal((await send(ref,{tab:{id:7},url:'https://attacker.test'})).saved,false);
  state.references=Array.from({length:100},(_,i)=>({...ref,company:'Business '+i}));
  assert.equal((await send()).saved,false);assert.equal(state.references.length,100);
  listeners.updated(7,{status:'complete'},{url:source});await vm.runInContext('serial.pending',context);
  assert.equal(executed.length,1);
  listeners.updated(7,{status:'complete'},{url:'https://different-site.test'});await vm.runInContext('serial.pending',context);
  assert.equal(state.armed,undefined);assert.equal(executed.length,1);
})().catch(e=>{console.error(e);process.exitCode=1});
'''
    result=subprocess.run([node,'-e',code,str(ROOT/'deploy/browser-connector/background.js')],
                          capture_output=True,text=True,timeout=15)
    assert result.returncode == 0, result.stderr
