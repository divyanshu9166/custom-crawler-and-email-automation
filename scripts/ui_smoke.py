"""Real Chromium smoke test, isolated local server and fictional data. Requires .[browser]."""
import os
import json
import hashlib
import secrets
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import psutil
from playwright.sync_api import sync_playwright, expect
from demo import seed
from outreach.db import DB
from outreach.web import extract_page
from outreach.research import add_lead


root = Path(__file__).resolve().parents[1]
output = Path(os.environ.get('OUTREACH_UI_OUTPUT', root / "docs" / "screenshots"))
output.mkdir(parents=True, exist_ok=True)
with tempfile.TemporaryDirectory(prefix="outreach-ui-") as tmp:
    seed(Path(tmp))
    fixture_db = DB(Path(tmp) / "outreach.db")
    candidate_page = extract_page("https://example.com/contact", '<p>FICTIONAL UI FIXTURE: business-demo@other-demo.com</p>')
    fixture_db.execute("INSERT INTO evidence(lead_id,url,title,text,sha256,fetched_at) VALUES(?,?,?,?,?,?)",
                       (1, candidate_page["url"], "Fictional business inbox ownership fixture", candidate_page["text"], candidate_page["sha256"], time.time()))
    fixture_db.event("contact_candidate_found", {**candidate_page["review_candidates"][0], "lead_id": 1, "evidence_sha256": candidate_page["sha256"]})
    fixture_db.event("prospect_signal", {"lead_id": 1, "platform": "linkedin.com", "state": "name_matched_website_candidate",
                     "source_url": "https://linkedin.com/company/fictional-ui-fixture", "indexed_snippet": "FICTIONAL UI SIGNAL: creative services",
                     "indexed_signal_only": True, "observed_at": time.time()})
    fixture_db.event('prospect_signal', {'lead_id':1,'platform':'x.com','state':'reciprocal_profile_link_candidate',
        'source_url':'https://x.com/FictionalDemo/status/123','indexed_snippet':'FICTIONAL index hint',
        'observed_at':time.time(),'public_snapshot':{'capture_method':'official_public_oembed','state':'captured',
        'text':'FICTIONAL PUBLIC POST UI FIXTURE: business services.','posted_label':'Fictional test date'}})
    fixture_db.event('prospect_signal', {'lead_id':1,'platform':'x.com','state':'no_company_match',
        'source_url':'https://x.com/BrightFounder','public_snapshot':{'state':'robots_denied'},
        'community_profile_hint':{'state':'public_mirror_hint','name':'FICTIONAL initial X research',
            'profile_url':'https://x.com/BrightFounder','transport_url':'https://api.fxtwitter.com/2/profile/brightfounder',
            'description':'FICTIONAL initial mirror bio: Business enquiries: initial-fixture@other-demo.com',
            'published_email_candidates':['initial-fixture@other-demo.com'],'retrieved_at':time.time(),
            'candidate_routes':[{'email':'initial-fixture@other-demo.com','purpose':'business_enquiries'}]}})
    fixture_db.event('prospect_signal', {'lead_id':1,'platform':'linkedin.com','state':'official_staff_profile_candidate',
        'source_url':'https://www.linkedin.com/in/alex-fixture-demo','observed_at':time.time(),
        'public_snapshot':{'state':'source_denied','http_status':999},
        'person_recovery':{'matched_people':[{'name':'Alex Fixture','role':'Founder',
            'quote':'FICTIONAL STAFF CARD <script>window.__staffInjected=true</script>',
            'source_url':'https://example.com/team','observed_at':time.time(),
            'email_publications':[{'email':'recovered-fixture@example.com','method':'scoped_mailto'}]}]}})
    fixture_db.event('prospect_signal', {'lead_id':1,'platform':'linkedin.com','state':'indexed_employer_company_candidate',
        'source_url':'https://www.linkedin.com/in/unresolved-fixture-demo','observed_at':time.time(),
        'public_snapshot':{'state':'source_denied','http_status':999},'resolved_company_only':True,'person_identity_verified':False,
        'person_recovery':{'matched_people':[], 'person_identity_state':'held',
            'company_search':{'company_candidate':{'company':'FICTIONAL Company <script>window.__companyInjected=true</script>','website':'https://example.com/'}},
            'official_person_observations':[{'name':'Alex Fixture','role':'Founder','quote':'FICTIONAL unresolved source',
                'source_url':'https://example.com/team','observed_at':time.time(),'matches_requested_profile':False}]}})
    person_quote='Alex Fixture is the Founder at Example Studio · DEMO.'
    person_eid=fixture_db.execute('INSERT INTO evidence(lead_id,url,title,text,sha256,fetched_at) VALUES(?,?,?,?,?,?)',
        (1,'https://example.com/team','FICTIONAL company team evidence',person_quote,'fictional-employer-hash',time.time()))
    person_text='FICTIONAL PROFESSIONAL UI FIXTURE: Alex Fixture\nFounder at Example Studio · DEMO\nPublic business enquiries: alex-fixture@example.com'
    fixture_db.event('professional_capture',{'lead_id':1,'url':'https://www.linkedin.com/in/alex-fixture-demo',
        'state':'captured','text':person_text,'name':'Alex Fixture','headline':'Founder at Example Studio · DEMO',
        'observed_at':time.time(),'sha256':hashlib.sha256(person_text.encode()).hexdigest(),
        'published_emails':['alex-fixture@example.com'],'capture_method':'fictional-ui-profile',
        'scope':'public_professional_fields','identity_verified':False,'employer_verified':False})
    fixture_db.event('professional_research',{'lead_id':1,'state':'held','queries':[{'query':'FICTIONAL PROFILE SEARCH','results':0,'engine_issues':[['fictional-engine','timeout']],
        'providers':[{'provider':'searxng:default'},{'provider':'searxng:yahoo'}]}],
        'official_link_refresh':[{'url':'https://example.com/team','state':'captured'}],
        'named_people':[{'name':'Alex Fixture','role':'Founder','quote':'FICTIONAL SOURCE: Alex Fixture, Founder','source_url':'https://example.com/team','email_publications':[{'email':'staff-fixture@example.com','method':'scoped_mailto'}],'professional_links':['https://www.linkedin.com/in/alex-fixture-demo']}],
        'community_profile_hints':[{'state':'public_mirror_hint','profile_url':'https://x.com/BrightFounder',
            'transport_url':'https://api.fxtwitter.com/2/profile/brightfounder','name':'Fictional community profile',
            'description':'FICTIONAL MIRROR BIO: Order inquiries: community-fixture@other-demo.com <script>window.__mirrorInjected=true</script>',
            'published_website_hint':'https://example.com/contact', 'website_ownership_verified':False,
            'published_email_candidates':['community-fixture@other-demo.com'],'retrieved_at':time.time(),
            'candidate_routes':[{'email':'community-fixture@other-demo.com','purpose':'customer_support','buyer_contact_verified':False}],
            'source_freshness_verified':False,'first_party_publication_verified':False,'cached':True}],
        'url_index':{'state':'available'},'other_public_profile_hints':[
            {'url':'https://instagram.com/fictional-company-demo','origin':'current_official_navigation'},
            {'url':'https://x.com/fictional_demo','origin':'search_index'}],
        'captures':[],'note':'FICTIONAL UI: no new profiles returned; prior saved capture remains separately visible.'})
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    password = secrets.token_urlsafe(32)
    base = f"http://127.0.0.1:{port}"
    env = {**os.environ, "DATA_DIR": tmp, "WORKER_ENABLED": "false", "SENDING_ENABLED": "false",
           "PUBLIC_URL": base, "ADMIN_USER": "admin", "ADMIN_PASSWORD": password,
           "API_TOKEN": secrets.token_urlsafe(36)}
    process = subprocess.Popen([sys.executable, "-m", "uvicorn", "outreach.app:create_app", "--factory", "--host", "127.0.0.1", "--port", str(port), "--no-access-log"],
                               cwd=root, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(base + "/health", timeout=1)
                break
            except OSError:
                time.sleep(0.2)
        else:
            raise RuntimeError("Local preview server failed to start")
        with sync_playwright() as p:
            browser = p.chromium.launch()
            context = browser.new_context(viewport={"width": 1440, "height": 1000})
            page = context.new_page()
            errors = []
            page.on("pageerror", lambda error: errors.append(str(error)))
            page.goto(base)
            page.get_by_role("heading", name="Sign in to your workspace").wait_for()
            page.screenshot(path=str(output / "login-desktop.png"), full_page=True)
            page.locator('[name="username"]').fill("admin")
            page.locator('[name="password"]').fill(password)
            page.get_by_role("button", name="Sign in", exact=True).click()
            expect(page.locator("#mode")).to_contain_text("Offline demo")
            expect(page.locator("#resume")).to_be_disabled()
            page.get_by_role("button", name="Pipeline", exact=True).click()
            page.locator("[data-lead='1']").click()
            page.get_by_role("heading", name="Example Studio · DEMO").wait_for()
            expect(page.locator('#detail')).to_contain_text('Legacy template drafts')
            expect(page.get_by_text("Platform research · linkedin.com · name matched website candidate", exact=True)).to_be_visible()
            page.get_by_text('Public X post · x.com · reciprocal profile link candidate', exact=True).click()
            expect(page.locator('#detail')).to_contain_text("This does not capture the author's profile")
            expect(page.locator('#detail')).to_contain_text('FICTIONAL PUBLIC POST UI FIXTURE')
            page.get_by_text("02 · Advanced: edit qualification & offer manually", exact=True).click()
            page.locator("#review-form input[name='industry']").fill("Fictional creative services")
            page.get_by_role("button", name="Save qualification", exact=True).click()
            expect(page.locator("#notice")).to_contain_text("Company qualified")
            expect(page.get_by_role("button", name="Write research-based emails", exact=True)).to_be_disabled()
            expect(page.locator('#detail')).to_contain_text('No template fallback')
            assert page.locator('[data-approve]').count() == 0
            page.locator('#professional-sources > summary').click()
            expect(page.locator('#professional-sources')).to_contain_text('FICTIONAL PROFESSIONAL UI FIXTURE')
            expect(page.locator('#professional-discovery-sources')).to_contain_text('2 search engine groups')
            expect(page.locator('#professional-discovery-sources')).to_contain_text('Observed company link')
            expect(page.locator('#professional-discovery-sources')).to_contain_text('Indexed · identity needs review')
            native_recovery = page.locator('.linkedin-person-recovery').filter(has_text='recovered-fixture@example.com')
            native_recovery.locator('..').locator('summary').click()
            company_recovery = page.locator('.linkedin-person-recovery').filter(has=page.locator('.company-only-recovery'))
            company_recovery.locator('..').locator('summary').click()
            expect(native_recovery).to_contain_text('recovered-fixture@example.com')
            expect(native_recovery).to_contain_text('Current publication source:')
            expect(native_recovery).to_contain_text('LinkedIn access was not recovered')
            assert page.evaluate('window.__staffInjected===undefined')
            expect(page.locator('.company-only-recovery')).to_contain_text('Company source found · person identity pending')
            expect(company_recovery).to_contain_text('Exact requested profile link is missing')
            expect(company_recovery).to_contain_text('0 matching company-page records')
            assert company_recovery.locator('[data-professional-review]').count() == 0
            assert page.evaluate('window.__companyInjected===undefined')
            expect(page.locator('#professional-discovery-sources')).to_contain_text('1 named people')
            expect(page.locator('#professional-discovery-sources')).to_contain_text('staff-fixture@example.com')
            expect(page.locator('#professional-discovery-sources')).to_contain_text('Inbox ownership and mailbox validity need review')
            expect(page.locator('#professional-discovery-sources')).to_contain_text('Employer and buyer relevance need review')
            expect(page.locator('#professional-discovery-sources')).to_contain_text('Community X profile hints')
            expect(page.locator('#professional-discovery-sources')).to_contain_text('community-fixture@other-demo.com')
            expect(page.locator('#professional-discovery-sources')).to_contain_text('Profile website reference:')
            expect(page.locator('#professional-discovery-sources')).to_contain_text('Ownership needs review')
            expect(page.locator('#professional-discovery-sources')).to_contain_text('these hints cannot import contacts')
            expect(page.locator('#professional-discovery-sources')).to_contain_text('Inbox purpose: customer support')
            expect(page.locator('#professional-discovery-sources')).to_contain_text('Buyer contact not verified')
            page.get_by_text('Platform research · x.com · no company match',exact=True).click()
            expect(page.locator('#detail')).to_contain_text('FICTIONAL initial mirror bio')
            expect(page.locator('#detail')).to_contain_text('Inbox purpose: business enquiries')
            assert not page.evaluate('Boolean(window.__mirrorInjected)')
            page.get_by_text('Last professional research · held',exact=True).click()
            expect(page.locator('#professional-sources')).to_contain_text('fictional-engine')
            professional_form=page.locator('[data-professional-review]')
            professional_form.locator('[name=employer_quote]').fill('Founder at Example Studio · DEMO')
            professional_form.locator('[name=role_quote]').fill('Founder')
            professional_form.locator('[name=company_evidence_id]').select_option(str(person_eid))
            professional_form.locator('[name=company_quote]').fill(person_quote)
            professional_form.locator('[name=ownership_notes]').fill('FICTIONAL UI: checked the public work email and named current founder against the company team page.')
            professional_form.locator('[name=reviewed_current_employer_and_publication]').check()
            page.screenshot(path=str(output/'professional-profile-review-fixture.png'),full_page=True)
            professional_form.get_by_role('button',name='Review & import published contact').click()
            expect(page.locator('#notice')).to_contain_text('Reviewed professional contact imported')
            expect(page.locator('#detail')).to_contain_text('alex-fixture@example.com')
            page.locator('#professional-sources > summary').click()
            expect(page.locator('#professional-sources')).to_contain_text('Current employer/source review passed')
            expect(page.locator('[data-professional-review]')).to_have_count(0)
            imported=fixture_db.one("SELECT * FROM contacts WHERE email='alex-fixture@example.com'")
            assert imported['verification']=='unverified' and imported['name']=='Alex Fixture'
            assert fixture_db.one("SELECT 1 FROM jobs WHERE kind='verify' AND json_extract(payload,'$.contact_id')=?",(imported['id'],))
            page.set_viewport_size({'width':390,'height':844})
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),'Professional sources mobile overflow'
            page.screenshot(path=str(output/'professional-profile-fixture-mobile.png'),full_page=True)
            page.set_viewport_size({'width':1440,'height':1000})
            page.get_by_role("button", name="Pause sending").click()
            expect(page.locator("#notice")).to_contain_text("paused")
            page.screenshot(path=str(output / "pipeline-desktop.png"), full_page=True)
            page.get_by_role("button", name="Find prospects", exact=True).click()
            coverage=page.locator('#discovery-source-coverage')
            expect(coverage).to_contain_text('linkedin.com')
            expect(coverage).to_contain_text('x.com')
            expect(coverage).to_contain_text('Recovered via independent sources')
            expect(coverage).to_contain_text('unqualified candidates')
            page.set_viewport_size({'width':390,'height':844})
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'),'Source coverage mobile overflow'
            page.screenshot(path=str(output/'source-coverage-fixture-mobile.png'),full_page=True)
            page.set_viewport_size({'width':1440,'height':1000})
            page.screenshot(path=str(output/'source-coverage-fixture-desktop.png'),full_page=True)
            # Browser mode UI only: fixture status, no platform job or session is started.
            expect(page.locator('#platform-browser-mode')).to_be_hidden()
            def managed_status(route):
                response=route.fetch()
                data=response.json()
                data.update(platform_browser_enabled=True,platform_browser_holds={'x.com':'login_or_challenge'})
                data['fxembed_profiles_enabled']=True
                route.fulfill(response=response,json=data)
            page.route('**/api/status',managed_status)
            page.reload()
            page.get_by_role("button", name="Find prospects", exact=True).click()
            expect(page.locator('#platform-browser-mode')).to_contain_text('Operator attention needed')
            expect(page.locator('#fxembed-mode')).to_contain_text('free FxEmbed community source')
            expect(page.locator('#platform-browser-mode')).to_contain_text('login_or_challenge')
            page.unroute('**/api/status',managed_status)
            page.reload()
            page.get_by_role("button", name="Find prospects", exact=True).click()
            reference = page.locator('#browser-reference-form')
            reference.locator('[name="company"]').fill('Browser Demo · FICTIONAL')
            reference.locator('[name="source_url"]').fill('https://linkedin.com/company/fictional-browser-demo/about/')
            reference.locator('[name="website"]').fill('https://browser-demo.com/contact')
            reference.locator('[name="observation"]').fill('FICTIONAL UI FIXTURE: the company profile links its website.')
            assert reference.locator('[name="observed_at"]').input_value()
            reference.locator('[name="public_business_confirmed"]').check()
            reference.get_by_role('button', name='Save reference & research new company').click()
            expect(page.locator('#notice')).to_contain_text('Business reference saved')
            page.get_by_role('button', name='Pipeline', exact=True).click()
            page.locator('.lead').filter(has_text='Browser Demo · FICTIONAL').click()
            expect(page.locator('#detail')).to_contain_text('Browser-observed business reference')
            summary = page.get_by_text('Browser-observed business reference · review required', exact=True)
            summary.click()
            expect(page.locator('#detail')).to_contain_text('The server did not fetch this profile')
            page.screenshot(path=str(output/'browser-reference-fixture.png'), full_page=True)
            page.get_by_role('button', name='Find prospects', exact=True).click()
            export = Path(tmp)/'connector-export.json'
            ref = {'company':'Connector Demo · FICTIONAL','source_url':'https://linkedin.com/company/fictional-connector/about',
                   'website':'https://connector-demo.com/contact','observed_at':time.time(),
                   'observation':'FICTIONAL UI FIXTURE: the business website field links this company.',
                   'capture_method':'browser_connector_reference'}
            export.write_text(json.dumps({'format':'outreach-business-references-v1','references':[
                ref,{**ref,'company':'Stale Demo · FICTIONAL','observed_at':time.time()-31*86400}]}),encoding='utf-8')
            page.locator('#connector-file').set_input_files(str(export))
            expect(page.locator('#connector-preview')).to_contain_text('Connector Demo · FICTIONAL')
            page.locator('#connector-import-form [name="confirmed"]').check()
            page.get_by_role('button',name='Import references & research new companies').click()
            expect(page.locator('#notice')).to_contain_text('Connector import processed')
            import_result=json.loads(page.locator('#connector-result').text_content())
            assert len(import_result['imported'])==1 and len(import_result['errors'])==1
            assert import_result['errors'][0]['row']==2
            page.screenshot(path=str(output/'browser-connector-import-fixture.png'),full_page=True)
            page.locator("#search-form input[name='query']").fill('"IT consulting" "London" "contact"')
            page.locator("#search-form button[type='submit']").click()
            expect(page.locator("#notice")).to_contain_text("Search queued")
            page.get_by_role("button", name="Operations", exact=True).click()
            discovery_job = fixture_db.one("SELECT id FROM jobs WHERE kind='discover' ORDER BY id DESC LIMIT 1")
            page.get_by_text(f"#{discovery_job['id']} discover", exact=True).wait_for()
            page.screenshot(path=str(output / "operations-desktop.png"), full_page=True)
            page.get_by_role("button", name="Pipeline", exact=True).click()
            page.locator("[data-lead='1']").click()
            page.set_viewport_size({"width": 390, "height": 844})
            page.screenshot(path=str(output / "pipeline-mobile.png"), full_page=True)
            assert page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth"), "Mobile horizontal overflow"
            assert not errors, errors
            # An unknown demo contact must never be approved.
            assert page.locator('[data-approve]').count() == 0
            rejected = context.request.post(base+'/api/contacts/1/approve', headers={'Origin': base}, data={
                'eligibility_basis': 'Fictional demo eligibility; cannot actually send.',
                'contact_relevance': 'Fictional founder for demo only.', 'reviewed_all_messages': True})
            assert rejected.status == 400 and 'safe Reacher' in rejected.text()
            # Exercise the shared-history, qualification, task and proposal controls using only demo fixtures.
            page.locator("#sales-workflow > summary").click()
            page.get_by_text("Record manual activity", exact=True).click()
            page.locator("#activity-form select[name='kind']").select_option("reply")
            page.locator("#activity-form textarea[name='note']").fill("FICTIONAL UI FIXTURE: demo founder requested a scoped website pilot. No real conversation occurred.")
            page.get_by_role("button", name="Record activity", exact=True).click()
            expect(page.locator("#notice")).to_contain_text("Manual activity recorded")
            page.locator("#sales-workflow > summary").click()
            page.get_by_text("Qualify and advance the opportunity", exact=True).click()
            page.locator("#sales-form select[name='stage']").select_option("qualified")
            for field, value in {
                "confirmed_problem": "FICTIONAL CLIENT CONTEXT: consultation route needs clarification.",
                "primary_goal": "Improve qualified consultation inquiries",
                "success_metric": "Compare inquiry quality with an agreed baseline",
                "baseline_notes": "Unknown fictional baseline; agree measurement before evaluating the pilot.",
                "decision_maker": "Alex Demo, fictional founder",
                "timeline": "Illustrative four-week pilot",
                "budget_notes": "Illustrative agreed pilot budget; not an actual commitment",
            }.items():
                page.locator(f"#sales-form textarea[name='{field}']").fill(value)
            page.get_by_role("button", name="Save sales stage", exact=True).click()
            expect(page.locator("#notice")).to_contain_text("Sales stage saved")
            page.locator("#sales-workflow > summary").click()
            page.get_by_text("Next-action tasks", exact=True).click()
            page.locator("#task-form input[name='title']").fill("Prepare the fictional annotated audit")
            page.locator("#task-form input[name='due_at']").fill(page.evaluate("localDateInput(Date.now()/1000+86400)"))
            page.get_by_role("button", name="Create task", exact=True).click()
            expect(page.locator("#notice")).to_contain_text("Next-action task created")
            page.locator("#sales-workflow > summary").click()
            page.get_by_text("Prepare a promised audit, concept or demo", exact=True).click()
            page.locator("#artifact-form input[name='title']").fill("Fictional source-backed audit demo")
            page.locator("#artifact-form input[type='checkbox']").check()
            page.get_by_role("button", name="Create value artifact", exact=True).click()
            expect(page.locator("#notice")).to_contain_text("Value artifact created")
            page.locator("#sales-workflow > summary").click()
            page.get_by_text("Prepare a promised audit, concept or demo", exact=True).click()
            page.locator("[data-artifact-review] input[type='checkbox']").check()
            page.get_by_role("button", name="Approve artifact", exact=True).click()
            expect(page.locator("#notice")).to_contain_text("Artifact reviewed")
            examples = root / "docs" / "examples"
            examples.mkdir(exist_ok=True)
            artifact = page.request.get(base + "/api/artifacts/1/download")
            assert artifact.ok
            artifact_path = examples / "audit-demo.html"
            artifact_path.write_bytes(artifact.body())
            preview = context.new_page()
            preview_requests = []
            preview.on("request", lambda request: preview_requests.append(request.url))
            preview.goto(artifact_path.as_uri())
            expect(preview.get_by_role("heading", name="Fictional source-backed audit demo")).to_be_visible()
            preview.set_viewport_size({"width": 390, "height": 844})
            assert preview.evaluate("document.documentElement.scrollWidth <= innerWidth"), "Artifact mobile overflow"
            preview.screenshot(path=str(output / "audit-mobile.png"), full_page=True)
            assert all(url.startswith(("file:", "data:")) for url in preview_requests), "Artifact loaded remote content"
            preview.close()
            page.locator("#sales-workflow > summary").click()
            page.get_by_text("Prepare a promised audit, concept or demo", exact=True).click()
            page.locator("#artifact-form select[name='kind']").select_option("faq_demo")
            page.locator("#artifact-form input[name='title']").fill("Fictional approved-excerpt FAQ demo")
            page.locator("#artifact-form input[name='faq_question']").fill("How can I ask about a consultation?")
            page.locator("#artifact-form textarea[name='faq_quote']").fill("Contact our team to book a consultation.")
            page.locator("#artifact-form input[type='checkbox']").check()
            page.get_by_role("button", name="Create value artifact", exact=True).click()
            expect(page.locator("#notice")).to_contain_text("Value artifact created")
            faq_path = examples / "faq-prototype-demo.html"
            faq_path.write_bytes(page.request.get(base + "/api/artifacts/2/download").body())
            preview = context.new_page()
            preview.goto(faq_path.as_uri())
            preview.get_by_text("How can I ask about a consultation?", exact=True).click()
            expect(preview.locator("details p")).to_contain_text("Contact our team to book a consultation.")
            preview.close()
            page.locator("#sales-workflow > summary").click()
            page.get_by_text("Prepare and review a scoped proposal", exact=True).click()
            for field in ["title", "scope", "deliverables", "timeline", "exclusions", "acceptance_criteria", "payment_terms", "ownership_revision_terms"]:
                page.locator(f"#proposal-form textarea[name='{field}']").fill(f"FICTIONAL DEMO {field}: illustrative content for workflow review only.")
            page.locator("#proposal-form input[name='fee']").fill("1200.50")
            page.locator("#proposal-form select[name='currency']").select_option("GBP")
            page.get_by_role("button", name="Create proposal draft", exact=True).click()
            expect(page.locator("#notice")).to_contain_text("Proposal draft created")
            page.locator("#sales-workflow > summary").click()
            page.get_by_text("Prepare and review a scoped proposal", exact=True).click()
            page.locator("[data-proposal-review] input[type='checkbox']").check()
            page.get_by_role("button", name="Approve proposal", exact=True).click()
            expect(page.locator("#notice")).to_contain_text("Proposal reviewed")
            page.set_viewport_size({"width": 1440, "height": 1000})
            page.locator("#sales-workflow > summary").click()
            page.get_by_text("Prepare and review a scoped proposal", exact=True).click()
            page.screenshot(path=str(output / "sales-desktop.png"), full_page=True)
            page.set_viewport_size({"width": 390, "height": 844})
            assert page.evaluate("() => document.documentElement.scrollWidth <= window.innerWidth"), "Sales mobile overflow"
            assert not errors, errors
            page.get_by_text("Published inboxes requiring ownership review (1)", exact=True).click()
            expect(page.get_by_text("business-demo@other-demo.com", exact=True)).to_be_visible()
            page.get_by_text("Add a sourced contact", exact=True).click()
            page.locator("#contact-form input[name='email']").fill("business-demo@other-demo.com")
            page.locator("#contact-form input[name='source_url']").fill("https://example.com/contact")
            page.locator("#contact-form button").click()
            expect(page.locator("#notice")).to_contain_text("ownership review")
            page.locator("#contact-form textarea[name='ownership_notes']").fill("FICTIONAL UI FIXTURE: the demo's saved page explicitly publishes its business inbox. No real recipient.")
            page.locator("#contact-form button").click()
            expect(page.locator("#notice")).to_contain_text("Contact saved")
            expect(page.get_by_role("heading", name="business-demo@other-demo.com", exact=True)).to_be_visible()
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "Ownership-review mobile overflow"
            assert not errors, errors
            page.screenshot(path=str(output / "contact-review-mobile.png"), full_page=True)
            page.set_viewport_size({"width":1440,"height":900})
            page.locator("#sales-workflow > summary").click()
            page.get_by_text("Record manual activity", exact=True).click()
            note = "FICTIONAL FIXTURE: one saved note survives a failed dashboard refresh without suggesting another submission."
            page.locator("#activity-form select[name='kind']").select_option("note")
            page.locator("#activity-form textarea[name='note']").fill(note)
            page.route("**/api/status", lambda route: route.fulfill(status=503, content_type="application/json",
                       body='{"detail":"Controlled refresh failure"}'), times=1)
            page.get_by_role("button", name="Record activity", exact=True).click()
            expect(page.locator("#notice")).to_contain_text("Manual activity recorded")
            expect(page.locator("#notice")).to_contain_text("Dashboard refresh failed: Controlled refresh failure")
            assert fixture_db.one("SELECT COUNT(*) n FROM activities WHERE note=?", (note,))["n"] == 1
            assert not errors
            # Old sources stay visible but cannot be selected for a new review.
            history_lead = add_lead(fixture_db, "FICTIONAL source freshness review", "https://history-demo.example.com/",
                                   "A", "https://history-demo.example.com/")
            started = time.time()
            old_id = fixture_db.execute("INSERT INTO evidence(lead_id,url,title,text,sha256,fetched_at) VALUES(?,?,?,?,?,?)",
                        (history_lead, "https://history-demo.example.com/old", "Old fictional source", "Historical UK services.", "old", started - 60))
            fixture_db.execute("INSERT INTO crawls(lead_id,report,created_at) VALUES(?,?,?)",
                               (history_lead, '{"status":"partial"}', started))
            fresh_id = fixture_db.execute("INSERT INTO evidence(lead_id,url,title,text,sha256,fetched_at) VALUES(?,?,?,?,?,?)",
                        (history_lead, "https://history-demo.example.com/current", "Fresh fictional source", "Current UK services and contact route.", "fresh", started + 1))
            page.reload()
            page.get_by_role("button", name="Pipeline", exact=True).click()
            page.locator(f"[data-lead='{history_lead}']").click()
            expect(page.get_by_text(f"#{old_id} · Old fictional source · Historical capture", exact=True)).to_be_visible()
            page.get_by_text("02 · Advanced: edit qualification & offer manually", exact=True).click()
            assert page.locator("#review-form select[name='evidence_id'] option").evaluate_all("items=>items.map(x=>x.value)") == [str(fresh_id)]
            assert page.locator("#review-form select[name='country_source'] option").evaluate_all("items=>items.map(x=>x.value)") == ["https://history-demo.example.com/current"]
            for key in ["trigger_evidence_id", "followup_evidence_id"]:
                assert page.locator(f"#review-form select[name='{key}'] option").evaluate_all("items=>items.map(x=>x.value)") == ["", str(fresh_id)]
            page.set_viewport_size({"width":390,"height":844})
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "Source-history mobile overflow"
            assert not errors
            # Exercise the distinct profile-only branch using fictional saved evidence.
            page.get_by_role("button", name="Find prospects", exact=True).click()
            page.locator("#profile-lead-form input[name='company']").fill("FICTIONAL Profile Studio")
            profile_url = "https://www.facebook.com/fictional-ui-profile-studio"
            page.locator("#profile-lead-form input[name='profile_url']").fill(profile_url)
            page.locator("#profile-lead-form button[type='submit']").click()
            expect(page.locator("#notice")).to_contain_text("Business profile queued")
            profile_lead = fixture_db.one("SELECT id FROM leads WHERE profile_url=?", (profile_url,))["id"]
            profile_started = time.time()
            profile_text = "FICTIONAL UI FIXTURE: UK consulting services. Call us for a consultation. Business contact: profile-fixture@gmail.com"
            profile_hash = hashlib.sha256(profile_text.encode()).hexdigest()
            fixture_db.execute("INSERT INTO crawls(lead_id,report,created_at) VALUES(?,?,?)", (profile_lead,
                               '{"kind":"profile","status":"partial","note":"FICTIONAL search fixture; no live lookup"}', profile_started))
            profile_eid = fixture_db.execute("INSERT INTO evidence(lead_id,url,title,text,sha256,fetched_at) VALUES(?,?,?,?,?,?)",
                            (profile_lead, profile_url, "Fictional business profile", profile_text, profile_hash, profile_started + 1))
            fixture_db.event("contact_candidate_found", {"lead_id": profile_lead, "source_url": profile_url,
                             "email": "profile-fixture@gmail.com", "evidence_sha256": profile_hash,
                             "reason": "Fictional published profile inbox requiring ownership review"})
            fixture_db.execute("UPDATE leads SET status='review',website_status='website_not_found',findings=? WHERE id=?",
                               (json.dumps([{"evidence_id": profile_eid, "quote": "Call us for a consultation.", "service": "website_build"}]), profile_lead))
            page.get_by_role("button", name="Pipeline", exact=True).click()
            page.get_by_role("button", name="Refresh", exact=True).click()
            page.locator(f"[data-lead='{profile_lead}']").click()
            expect(page.locator("#detail")).to_contain_text("Profile prospect")
            expect(page.locator("#screenshot")).to_be_disabled()
            expect(page.locator("#performance")).to_be_disabled()
            page.get_by_text("02 · Advanced: edit qualification & offer manually", exact=True).click()
            review_form = page.locator("#review-form")
            review_form.locator("textarea[name='country_quote']").fill("UK consulting services")
            review_form.locator("textarea[name='profile_ownership_notes']").fill("FICTIONAL: business name, location and services match this specific profile.")
            review_form.locator("textarea[name='profile_activity_quote']").fill("UK consulting services")
            review_form.locator("textarea[name='website_search_notes']").fill("FICTIONAL search fixture: website not found; absence is not established.")
            review_form.locator("input[name='website_search_reviewed']").check()
            review_form.locator("input[name='fit_notes']").fill("Fictional service business with a published consultation route")
            review_form.locator("textarea[name='observation']").fill("Your profile invites customers to call for a consultation.")
            review_form.locator("textarea[name='suggestion']").fill("Explore a services page with a consultation request form.")
            review_form.locator("textarea[name='quote']").fill("Call us for a consultation.")
            invalid = review_form.evaluate("form => [...form.elements].filter(e => !e.checkValidity()).map(e => ({name:e.name, message:e.validationMessage}))")
            assert not invalid, invalid
            review_form.get_by_role("button", name="Save qualification", exact=True).click()
            expect(page.locator("#notice")).to_contain_text("Company qualified")
            page.get_by_text("Add a sourced contact", exact=True).click()
            page.locator("#contact-form input[name='email']").fill("profile-fixture@gmail.com")
            page.locator("#contact-form input[name='source_url']").fill(profile_url)
            page.locator("#contact-form textarea[name='ownership_notes']").fill("FICTIONAL: this business profile explicitly publishes its own business contact email.")
            page.locator("#contact-form button").click()
            expect(page.locator("#notice")).to_contain_text("Contact saved")
            expect(page.get_by_role("button", name="Write research-based emails", exact=True)).to_be_disabled()
            expect(page.locator('#detail')).to_contain_text('No template fallback')
            page.screenshot(path=str(output / "profile-prospect-mobile.png"), full_page=True)
            assert page.evaluate("document.documentElement.scrollWidth <= innerWidth"), "Profile prospect mobile overflow"
            assert not errors
            # The connected map reads persisted state; dragging only changes layout.
            page.get_by_role("button", name="Workflow", exact=True).click()
            expect(page.locator('.flow-node')).to_have_count(17)
            expect(page.locator('#flow-research-steps button')).to_have_count(7)
            expect(page.locator('#flow-research-note')).to_contain_text('require review')
            page.locator('#flow-research-steps [data-focus-node="E"]').click()
            expect(page.locator('#flow-node-title')).to_contain_text('E · ')
            page.locator('#flow-close').click()
            page.locator('#flow-detail').select_option('overview')
            expect(page.locator('.flow-node')).to_have_count(11)
            expect(page.locator('.flow-path')).to_have_count(12)
            page.locator('#flow-prospect').select_option(str(profile_lead))
            expect(page.locator('#flow-scope')).to_contain_text('FICTIONAL Profile Studio')
            page.locator('[data-node="qualify"]').click()
            expect(page.locator('#flow-inspector')).to_be_visible()
            expect(page.locator('#flow-node-info')).to_contain_text('Complete')
            page.locator('#flow-close').click()
            page.set_viewport_size({'width':1440,'height':1000})
            page.locator('#flow-fit').click()
            before = page.locator('[data-node="discovery"]').evaluate('e=>e.style.left')
            box = page.locator('[data-node="discovery"]').bounding_box()
            page.mouse.move(box['x']+40,box['y']+35)
            page.mouse.down()
            page.mouse.move(box['x']+75,box['y']+60,steps=5)
            page.mouse.up()
            assert page.locator('[data-node="discovery"]').evaluate('e=>e.style.left') != before
            page.locator('#flow-reset').click()
            page.screenshot(path=str(output/'workflow-desktop.png'),full_page=True)
            page.set_viewport_size({'width':390,'height':844})
            page.locator('#flow-fit').click()
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), 'Workflow mobile overflow'
            page.screenshot(path=str(output/'workflow-mobile.png'),full_page=True)
            # Detailed view follows the complete graph and remains read-only.
            before_map = fixture_db.all('SELECT id,state FROM jobs ORDER BY id')
            page.locator('#flow-detail').select_option('detail')
            expect(page.locator('.flow-node')).to_have_count(35)
            expect(page.locator('.flow-path')).to_have_count(46)
            page.locator('#flow-stage').select_option('G')
            expect(page.locator('#flow-node-title')).to_contain_text('G · Country')
            expect(page.locator('#flow-node-info')).to_contain_text('AI preparation + exception/final review')
            expect(page.locator('[data-node="BB"] .node-state')).to_contain_text('Other branch')
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), 'Detailed map mobile overflow'
            canvas = page.locator('#flow-viewport').bounding_box()
            inspector = page.locator('#flow-inspector').bounding_box()
            assert inspector['y'] >= canvas['y']+canvas['height']-1, 'Mobile inspector must not obscure the canvas'
            page.evaluate('window.scrollTo(0,0)')
            page.screenshot(path=str(output/'workflow-detail-mobile.png'),full_page=True)
            page.locator('#flow-close').click()
            page.set_viewport_size({'width':1440,'height':1000})
            page.locator('#flow-prospect').select_option('')
            expect(page.locator('#flow-scope')).to_contain_text('All prospects')
            for key in ['A','CP','E3','F','J','L','M','N','O','P','R','S','T','U','V','W','X','Y','Z']:
                page.locator('#flow-stage').select_option(key)
                expect(page.locator('#flow-node-title')).to_contain_text(key+' · ')
            page.locator('#flow-stage').select_option('Z')
            expect(page.locator('#flow-node-action')).to_contain_text('Open Learning')
            page.locator('#flow-close').click()
            page.locator('#flow-fit').click()
            page.evaluate('window.scrollTo(0,0)')
            page.screenshot(path=str(output/'workflow-detail-desktop.png'),full_page=True)
            assert fixture_db.all('SELECT id,state FROM jobs ORDER BY id') == before_map
            page.locator('#flow-detail').select_option('overview')
            expect(page.locator('.flow-node')).to_have_count(11)
            page.set_viewport_size({'width':390,'height':844})
            # Learning uses saved fictional records only; no SMTP/provider is called.
            page.get_by_role('button',name='Learning',exact=True).click()
            expect(page.locator('#learning-content')).to_contain_text('No SMTP-accepted sample yet')
            expect(page.locator('.learning-table tbody')).to_contain_text('—')
            fixture_db.execute("INSERT INTO messages(contact_id,step,subject,body,evidence_ids,message_id,state,sent_at) VALUES(1,0,?,?,?,?,?,?)",
                               ('FICTIONAL bookkeeping only', 'FICTIONAL learning fixture. No SMTP submission occurred.',
                                '[]', '<fictional-learning@fixture.invalid>', 'sent', time.time()-10))
            fixture_db.event('sequence_approved', {'context': {'lead_id':1,'campaign':'A','country':'UK',
                'service':'website_improvement','industry':'FICTIONAL <img src=x onerror=alert(1)>', 'prospect_kind':'website'}}, 1)
            fixture_db.event('reply', {'subject':'Fictional reply bookkeeping fixture'}, 1)
            fixture_db.event('reply', {'subject':'Another fictional reply from same record'}, 1)
            fixture_db.event('auto_reply', {'subject':'Fictional automatic response'}, 1)
            page.get_by_role('button',name='Refresh learning',exact=True).click()
            expect(page.locator('#learning-content')).to_contain_text('Small sample')
            expect(page.locator('.learning-table tbody')).to_contain_text('100.0%')
            expect(page.locator('#learning-content img')).to_have_count(0)
            expect(page.locator('#learning-content')).to_contain_text('Fictional demo data')
            page.set_viewport_size({'width':1440,'height':1000})
            page.screenshot(path=str(output/'learning-desktop.png'),full_page=True)
            page.set_viewport_size({'width':390,'height':844})
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), 'Learning mobile overflow'
            page.screenshot(path=str(output/'learning-mobile.png'),full_page=True)
            # Extend the same isolated fixture through client growth and recorded economics.
            # External agreement/payment/delivery references below are explicitly fictional.
            detail = page.request.get(base+'/api/leads/1').json()
            proposal = detail['proposals'][0]
            delivered = page.request.post(base+f"/api/proposals/{proposal['id']}/sent", data={
                'reference':'FICTIONAL UI FIXTURE: reviewed proposal delivery reference', 'actually_delivered':True},headers={'Origin':base})
            assert delivered.ok, delivered.text()
            details = json.loads(detail['sales']['details'])
            completed = {**details, 'stage':'completed','version':detail['sales']['version'],
                'proposal_id':proposal['id'],'agreement_reference':'FICTIONAL client scope agreement',
                'payment_reference':'FICTIONAL initial-payment reference',
                'acceptance_reference':'FICTIONAL recorded client acceptance',
                'outcome_notes':'FICTIONAL measured outcome remains inconclusive; no uplift claimed.'}
            result = page.request.put(base+'/api/leads/1/sales',data=completed,headers={'Origin':base})
            assert result.ok, result.text()
            page.set_viewport_size({'width':1440,'height':1000})
            page.get_by_role('button',name='Pipeline',exact=True).click()
            page.locator('[data-lead="1"]').click()
            expect(page.locator('#priority-details')).to_contain_text('existing conversation')
            page.locator('#lead-sort').select_option('company')
            page.locator('#lead-sort').select_option('priority')
            for kind,amount,reference in [('acquisition_cost','12.50','FICTIONAL receipt acquisition 001'),
                                           ('payment','200.10','FICTIONAL receipt payment 002'),
                                           ('refund','0.10','FICTIONAL receipt refund 003')]:
                page.locator('#finance-workflow > summary').click()
                form=page.locator('#finance-form')
                form.locator('[name="kind"]').select_option(kind)
                form.locator('[name="amount"]').fill(amount)
                form.locator('[name="reference"]').fill(reference)
                form.locator('[name="note"]').fill('FICTIONAL UI FIXTURE: actual transaction bookkeeping simulation.')
                form.locator('input[type="checkbox"]').check()
                form.get_by_role('button',name='Record financial entry',exact=True).click()
                expect(page.locator('#notice')).to_contain_text('financial entry recorded')
            page.locator('#finance-workflow > summary').click()
            expect(page.locator('#finance-workflow')).to_contain_text('187.50')
            page.locator('[data-finance-void]').first.locator('[name="reason"]').fill('FICTIONAL duplicate refund correction; ledger history retained.')
            page.locator('[data-finance-void]').first.get_by_role('button').click()
            expect(page.locator('#notice')).to_contain_text('history retained')
            page.locator('#client-growth > summary').click()
            form=page.locator('#client-plan-form')
            form.locator('[name="kind"]').select_option('case_study')
            form.locator('[name="title"]').fill('Fictional client case-study outline')
            form.locator('[name="scope"]').fill('Present the agreed scope and inconclusive observed result without an uplift claim.')
            form.locator('[name="due_at"]').fill(page.evaluate('localDateInput(Date.now()/1000+86400)'))
            form.get_by_role('button').click()
            expect(page.locator('#notice')).to_contain_text('Client plan created')
            page.locator('#client-growth > summary').click()
            review=page.locator('[data-client-plan]').first
            review.get_by_role('button').click()
            expect(page.locator('#notice')).to_contain_text('explicit client permission')
            review.locator('[name="permission_reference"]').fill('FICTIONAL explicit client content permission')
            review.locator('[name="client_permission_confirmed"]').check()
            review.get_by_role('button').click()
            expect(page.locator('#notice')).to_contain_text('Client plan state recorded')
            page.locator('#client-growth > summary').click()
            review=page.locator('[data-client-plan]').first
            review.locator('[name="agreement_reference"]').fill('FICTIONAL approved case-study scope agreement')
            review.locator('[name="client_permission_confirmed"]').check()
            review.get_by_role('button').click()
            expect(page.locator('#notice')).to_contain_text('Client plan state recorded')
            page.locator('#client-growth > summary').click()
            review=page.locator('[data-client-plan]').first
            review.locator('[name="outcome_reference"]').fill('FICTIONAL actual publication reference; no real publication occurred')
            review.locator('[name="outcome_notes"]').fill('FICTIONAL case-study completion records the inconclusive outcome.')
            review.locator('[name="client_permission_confirmed"]').check()
            review.get_by_role('button').click()
            expect(page.locator('#notice')).to_contain_text('Client plan state recorded')
            page.locator('#client-growth > summary').click()
            form=page.locator('#client-plan-form')
            form.locator('[name="title"]').fill('Fictional quarterly maintenance review')
            form.locator('[name="scope"]').fill('Discuss actual support priorities and agree any maintenance scope before work.')
            form.locator('[name="due_at"]').fill(page.evaluate('localDateInput(Date.now()/1000+86400)'))
            form.get_by_role('button').click()
            expect(page.locator('#notice')).to_contain_text('Client plan created')
            page.locator('#finance-workflow > summary').click()
            page.locator('#client-growth > summary').click()
            page.locator('#client-growth').screenshot(path=str(output/'client-plans-desktop.png'))
            page.locator('#finance-workflow').screenshot(path=str(output/'finance-desktop.png'))
            page.evaluate('window.scrollTo(0,0)')
            page.screenshot(path=str(output/'client-growth-desktop.png'),full_page=True)
            page.set_viewport_size({'width':390,'height':844})
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), 'Client growth mobile overflow'
            page.locator('#client-growth').screenshot(path=str(output/'client-plans-mobile.png'))
            page.evaluate('window.scrollTo(0,0)')
            page.screenshot(path=str(output/'client-growth-mobile.png'),full_page=True)
            page.get_by_role('button',name='Learning',exact=True).click()
            expect(page.locator('#learning-content')).to_contain_text('187.60')
            expect(page.locator('#learning-content')).to_contain_text('1 open plans')
            page.locator('[data-growth-lead="1"]').click()
            expect(page.locator('#pipeline')).to_be_visible()
            expect(page.locator('#client-plan-form')).to_have_count(1)
            page.get_by_role('button',name='Learning',exact=True).click()
            page.set_viewport_size({'width':1440,'height':1000})
            page.evaluate('window.scrollTo(0,0)')
            page.screenshot(path=str(output/'learning-economics-desktop.png'),full_page=True)
            page.set_viewport_size({'width':390,'height':844})
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), 'Economics learning mobile overflow'
            page.evaluate('window.scrollTo(0,0)')
            page.screenshot(path=str(output/'learning-economics-mobile.png'),full_page=True)
            assert not errors, errors
            accepted_before_settings = fixture_db.all("SELECT id,sent_at FROM messages WHERE state='sent'")
            # Save fictional mailbox details without any network connection or sending.
            page.get_by_role('button',name='Worker: OFF',exact=True).click()
            expect(page.locator('#runtime-settings-form input[name="worker_enabled"]')).to_be_disabled()
            expect(page.locator('#runtime-settings-form input[name="sending_enabled"]')).to_be_disabled()
            expect(page.locator('#runtime-summary')).to_contain_text('Offline demo')
            expect(page.locator('#mail-settings-form input[name="smtp_port"]')).to_have_value('587')
            page.locator('#mail-settings-form input[name="sender_name"]').fill('Alex Fixture')
            page.locator('#mail-settings-form input[name="sender_company"]').fill('Fictional UI Studio')
            page.locator('#mail-settings-form input[name="sender_email"]').fill('fixture@sender-demo.example.com')
            page.locator('#mail-settings-form input[name="smtp_host"]').fill('smtp.fixture.example.com')
            page.locator('#mail-settings-form input[name="smtp_user"]').fill('fixture@sender-demo.example.com')
            page.locator('#mail-settings-form input[name="smtp_password"]').fill('fictional-smtp-private-password')
            page.locator('#mail-settings-form input[name="imap_password"]').fill('fictional-imap-private-password')
            page.get_by_role('button',name='Save email settings',exact=True).click()
            expect(page.locator('#mail-settings-result')).to_contain_text('Email settings saved')
            expect(page.locator('#runtime-summary')).to_contain_text('Offline demo')
            expect(page.locator('#mail-settings-form input[name="smtp_password"]')).to_have_value('')
            assert fixture_db.get('paused')=='true'
            assert fixture_db.all("SELECT id,sent_at FROM messages WHERE state='sent'") == accepted_before_settings
            assert page.evaluate('document.documentElement.scrollWidth<=innerWidth'), 'Settings mobile overflow'
            page.screenshot(path=str(output/'settings-mobile.png'),full_page=True)
            page.set_viewport_size({'width':1440,'height':1000})
            page.screenshot(path=str(output/'settings-desktop.png'),full_page=True)
            # Credential editing signs out and supports a fresh browser-form login.
            changed_password=secrets.token_urlsafe(32)
            page.locator('#credentials-form input[name="username"]').fill('fixture-admin')
            page.locator('#credentials-form input[name="current_password"]').fill(password)
            page.locator('#credentials-form input[name="new_password"]').fill(changed_password)
            page.locator('#credentials-form input[name="confirm_password"]').fill(changed_password)
            page.get_by_role('button',name='Update sign-in details',exact=True).click()
            page.get_by_role('heading',name='Sign in to your workspace').wait_for()
            page.locator('[name="username"]').fill('fixture-admin')
            page.locator('[name="password"]').fill(changed_password)
            page.get_by_role('button',name='Sign in',exact=True).click()
            expect(page.locator('.flow-node')).to_have_count(17)
            assert not errors
            browser.close()
        print("Browser smoke passed: auth, source-backed research, template-demo hold and missing AI writer configuration, demo isolation, shared activity, sales qualification, tasks, proposal creation/review, artifact creation/review/export, offline HTML rendering and FAQ interaction, sourced inbox candidate/ownership review, mobile layout, unsafe approval rejection, committed-action/refresh-failure feedback historical-source exclusion from new review and profile-only qualification/contact workflow and writer configuration hold, connected node drag/zoom/status map, private mailbox-settings save and credential-change/re-login, campaign learning empty/nonzero rates and escaped cohort labels, priority ordering, financial entry/void arithmetic, permission-reviewed case study lifecycle and post-client plans; zero JS errors.")
    finally:
        # Windows venv launchers can outlive terminate()/wait() as a child
        # interpreter. Release its worker/database handles before temp cleanup.
        try:
            children = psutil.Process(process.pid).children(recursive=True)
        except psutil.NoSuchProcess:
            children = []
        process.terminate()
        process.wait(timeout=15)
        for child in children:
            try:
                child.terminate()
            except psutil.NoSuchProcess:
                pass
        _, alive = psutil.wait_procs(children, timeout=15)
        for child in alive:
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
        psutil.wait_procs(alive, timeout=5)
