import json
import time

import pytest
from fastapi.testclient import TestClient
from playwright.async_api import async_playwright

from outreach.app import create_app
from outreach import professionals, platform_browser
from outreach.professionals import (
    professional_target,
    parse_public_html,
    research_professionals,
    review_contact,
    captures,
)
from outreach.research import assert_contact_ownership
from outreach.profiles import canonical_profile, source_allowed
from outreach.crawl_scheduler import schedule_final_audits

URL = "https://www.linkedin.com/in/alex-doe"
HTML = """<title>Alex Doe</title><nav>PRIVATE inbox@private-demo.com</nav><main>
<section><h1>Alex Doe</h1><div class="text-body-medium">Founder at Bright Demo</div>
<a href="mailto:alex.doe%40bright-demo.com">Business enquiries</a></section>
<section><h2>About</h2><div class="inline-show-more-text">Founder at Bright Demo. Public business email alex.doe@bright-demo.com.
<span hidden>hidden@private-demo.com</span></div></section>
<section><h2>Activity</h2><p>other@other-demo.com</p></section></main>"""


def test_guest_professional_parser_excludes_dialog_contact_overlays_inside_top_card():
    html = HTML.replace('<a href="mailto:alex.doe%40bright-demo.com">',
        '<div role="dialog"><a href="mailto:private@private-demo.com">private@private-demo.com</a></div>'
        '<dialog open><a href="mailto:overlay@private-demo.com">overlay@private-demo.com</a></dialog>'
        '<a href="mailto:alex.doe%40bright-demo.com">')
    result = parse_public_html(URL, html)
    assert result['state'] == 'captured'
    assert 'private-demo.com' not in result['text']
    assert 'alex.doe@bright-demo.com' in result['text']


@pytest.mark.parametrize(
    "url",
    [
        "https://linkedin.com/company/bright",
        "https://linkedin.com/in/alex/overlay/contact-info/",
        "https://linkedin.com/in/alex/details/experience/",
        "https://linkedin.com/messaging",
        "https://notlinkedin.com/in/alex",
        "http://127.0.0.1/in/alex",
        "https://x.com/messages",
        "https://x.com/BrightDemo/status/123",
        "https://x.com/intent",
        "https://linkedin.com/in/alex?secret=token",
    ],
)
def test_professional_routes_are_separate_and_private_routes_rejected(url):
    with pytest.raises(ValueError):
        professional_target(url)


def test_person_profile_is_not_reclassified_as_a_business_lead():
    assert professional_target("https://uk.linkedin.com/in/alex-doe/")[1] == URL
    with pytest.raises(ValueError):
        canonical_profile(URL)


def test_guest_html_parser_extracts_published_bio_and_mailto_without_account_activity_or_hidden_data():
    result = parse_public_html(URL, HTML)
    assert result["state"] == "captured" and result["title"] == "Alex Doe"
    assert professionals.public_addresses(result["text"]) == ["alex.doe@bright-demo.com"]
    assert "private-demo" not in result["text"] and "other-demo" not in result["text"]


def test_public_profile_fields_are_not_discarded_due_to_unrelated_footer_signin_form():
    result = parse_public_html(URL, HTML + '<footer><form><input type="password"><input value="account-secret"></form></footer>')
    assert result['state'] == 'captured' and 'account-secret' not in result['text']


@pytest.mark.parametrize('handle,state', [('alex_doe','captured'),('other_doe','profile_handle_mismatch')])
def test_x_user_name_field_matches_requested_handle_and_excludes_hidden_and_timeline_emails(handle, state):
    html = f'''<title>Alex Doe on X</title><nav><h1>Home</h1></nav><main>
    <div data-testid="UserName"><span>Alex Doe</span><span>@{handle}</span></div>
    <div data-testid="UserDescription">Founder at Bright Demo <span hidden>hidden@bright-demo.com</span>
    <a href="mailto:alex.doe%40bright-demo.com">Business email</a></div>
    <div data-testid="UserProfileHeader_Items">London</div><article>someone@other-demo.com</article></main>'''
    result = parse_public_html('https://x.com/alex_doe',html)
    assert result['state'] == state
    if state == 'captured':
        assert result['title'] == 'Alex Doe'
        assert professionals.public_addresses(result['text']) == ['alex.doe@bright-demo.com']


async def test_x_managed_reader_uses_scoped_profile_name_and_bio_mailto_with_real_chromium(settings, monkeypatch):
    settings.platform_browser_delay_seconds = 0
    html = '''<nav><h1>Home</h1></nav><main>
    <div data-testid="UserName">Alex Doe <span>@alex_doe</span></div>
    <div data-testid="UserDescription">Founder at Bright Demo <span hidden>hidden@bright-demo.com</span>
    <a href="mailto:alex.doe%40bright-demo.com">Business email</a></div>
    <div data-testid="UserProfileHeader_Items"><p>London</p></div><article>third@other-demo.com</article></main>'''
    class Fixture:
        def __init__(self,*args):
            pass
        async def __aenter__(self):
            self.p = await async_playwright().start()
            self.browser = await self.p.chromium.launch()
            self.context = await self.browser.new_context()
            await self.context.route('**/*', lambda r: r.fulfill(status=200,body=html,content_type='text/html'))
            return self
        async def navigate(self,url):
            page = await self.context.new_page()
            await page.goto(url)
            return page,None
        async def __aexit__(self,*args):
            await self.browser.close()
            await self.p.stop()
    monkeypatch.setattr(platform_browser,'BrowserSession',Fixture)
    result = await platform_browser.browser_professional_snapshot(settings,'https://x.com/alex_doe')
    assert result['state'] == 'captured' and result['title'] == 'Alex Doe'
    assert result['published_emails'] == ['alex.doe@bright-demo.com']
    assert 'hidden@' not in result['text'] and 'third@' not in result['text']


async def test_managed_professional_reader_uses_real_chromium_scoped_dom(settings, monkeypatch):
    settings.platform_browser_delay_seconds = 0

    class Fixture:
        def __init__(self, *args):
            pass

        async def __aenter__(self):
            self.p = await async_playwright().start()
            self.browser = await self.p.chromium.launch()
            self.context = await self.browser.new_context()
            await self.context.route(
                "**/*", lambda r: r.fulfill(status=200, body=HTML, content_type="text/html")
            )
            return self

        async def navigate(self, url):
            page = await self.context.new_page()
            await page.goto(url)
            return page, None

        async def __aexit__(self, *args):
            await self.browser.close()
            await self.p.stop()

    monkeypatch.setattr(platform_browser, "BrowserSession", Fixture)
    result = await platform_browser.browser_professional_snapshot(settings, URL)
    assert result["state"] == "captured" and result["scope"] == "visible_professional_fields"
    assert result["published_emails"] == ["alex.doe@bright-demo.com"]
    assert "private-demo" not in result["text"] and "other-demo" not in result["text"]


@pytest.fixture
async def public_person(db, settings, prepared, monkeypatch):
    lid = prepared["lead_id"]
    company_quote = "Alex Doe is our Founder at Bright Demo."
    eid = db.execute(
        "INSERT INTO evidence(lead_id,url,title,text,sha256,fetched_at) VALUES(?,?,?,?,?,?)",
        (lid, "https://bright-demo.com/team", "Team", company_quote, "employer-hash", time.time()),
    )

    async def source(s, url):
        return {
            **parse_public_html(url, HTML),
            "observed_at": time.time(),
            "capture_method": "fictional-public-profile-fixture",
        }

    monkeypatch.setattr(professionals, "profile_snapshot", source)
    await research_professionals(db, settings, lid, URL)
    capture = captures(db, lid)[0]
    value = {
        "capture_id": capture["capture_id"],
        "email": "alex.doe@bright-demo.com",
        "employer_quote": "Founder at Bright Demo",
        "role_quote": "Founder",
        "company_evidence_id": eid,
        "company_quote": company_quote,
        "ownership_notes": "Checked the public work email, current employer and named founder on the company team page.",
        "reviewed_current_employer_and_publication": True,
    }
    return lid, value


async def test_capture_does_not_create_contacts_probe_jobs_or_business_evidence(db, public_person):
    lid, value = public_person
    assert not db.one("SELECT 1 FROM contacts WHERE email='alex.doe@bright-demo.com'")
    assert not db.one("SELECT 1 FROM evidence WHERE url=?", (URL,))
    assert not db.one("SELECT 1 FROM jobs WHERE kind='verify'")
    assert captures(db, lid)[0]["employer_verified"] is False


async def test_reviewed_employer_and_published_email_import_remain_unverified_and_bound_to_source(
    db, public_person
):
    lid, value = public_person
    cid = review_contact(db, lid, value)
    contact = db.one("SELECT * FROM contacts WHERE id=?", (cid,))
    lead = db.one("SELECT * FROM leads WHERE id=?", (lid,))
    assert contact["name"] == "Alex Doe" and contact["verification"] == "unverified"
    assert contact["source_url"] == URL and contact["status"] == "new"
    assert_contact_ownership(db, contact, lead)
    assert not source_allowed(lead, URL)  # Not country/business qualification evidence.
    assert source_allowed(lead, URL, db, contact["email"])
    assert db.one("SELECT payload FROM jobs WHERE kind='verify'")["payload"] == json.dumps(
        {"contact_id": cid}, sort_keys=True
    )
    assert not db.one("SELECT 1 FROM messages WHERE state='sent'")


@pytest.mark.parametrize(
    "patch",
    [
        {"email": "guessed@bright-demo.com"},
        {"employer_quote": "Founder at Other Company"},
        {"role_quote": "random visitor"},
        {"company_quote": "Alex Doe invented quote"},
        {"ownership_notes": "short"},
        {"reviewed_current_employer_and_publication": False},
    ],
)
async def test_unsupported_review_has_no_partial_mutations(db, public_person, patch):
    lid, value = public_person
    before = {t: db.all("SELECT * FROM " + t) for t in ["contacts", "evidence", "events", "jobs"]}
    with pytest.raises(ValueError):
        review_contact(db, lid, {**value, **patch})
    assert {t: db.all("SELECT * FROM " + t) for t in before} == before


@pytest.mark.parametrize("change", ["company_source", "profile_refresh", "profile_stale", "company_rename"])
async def test_professional_ownership_fails_when_employer_or_profile_proof_changes(
    db, settings, public_person, change
):
    lid, value = public_person
    cid = review_contact(db, lid, value)
    if change == "company_source":
        db.execute("UPDATE evidence SET sha256=? WHERE id=?", ("changed", value["company_evidence_id"]))
    elif change == "profile_refresh":
        await research_professionals(db, settings, lid, URL)
    elif change == "profile_stale":
        row = db.one("SELECT id,detail FROM events WHERE kind='professional_capture' ORDER BY id DESC")
        detail = json.loads(row["detail"])
        detail["observed_at"] = time.time() - 31 * 86400
        db.execute("UPDATE events SET detail=? WHERE id=?", (json.dumps(detail), row["id"]))
    else:
        db.execute("UPDATE leads SET company='Different Company' WHERE id=?", (lid,))
    with pytest.raises(ValueError):
        assert_contact_ownership(
            db,
            db.one("SELECT * FROM contacts WHERE id=?", (cid,)),
            db.one("SELECT * FROM leads WHERE id=?", (lid,)),
        )


async def test_global_suppression_is_preserved_and_no_probe_is_queued(db, public_person):
    lid, value = public_person
    db.suppress(value["email"], "Opted out")
    cid = review_contact(db, lid, value)
    assert db.one("SELECT status FROM contacts WHERE id=?", (cid,))["status"] == "suppressed"
    assert not db.one("SELECT 1 FROM jobs WHERE kind='verify'")


async def test_api_research_and_review_are_authenticated_and_only_queue_public_routes(
    settings, db, public_person
):
    lid, value = public_person
    with TestClient(create_app(settings)) as client:
        path = f"/api/leads/{lid}/professional-research"
        assert client.post(path, json={}).status_code == 401
        headers = {"Authorization": "Bearer " + settings.api_token}
        assert (
            client.post(
                path, headers=headers, json={"profile_url": URL + "/overlay/contact-info"}
            ).status_code
            == 400
        )
        response = client.post(path, headers=headers, json={"profile_url": URL})
        assert response.status_code == 200 and response.json()["job_id"]
        data = client.get(f"/api/leads/{lid}", headers=headers).json()
        assert data["professional_captures"][0]["published_emails"] == [value["email"]]
        assert data["professional_report"]["state"] == "captured"
        assert (
            client.post(f"/api/leads/{lid}/professional-review", headers=headers, json=value).status_code
            == 200
        )
        refreshed = client.get(f"/api/leads/{lid}", headers=headers).json()
        assert refreshed["professional_captures"][0]["reviewed_emails"] == [value["email"]]
        assert not next(e for e in refreshed["evidence"] if e["url"] == URL)["business_for_review"]


def test_professional_job_serializes_with_company_research(db):
    db.enqueue("professional_research", {"lead_id": 1})
    db.enqueue("research", {"lead_id": 1})
    db.enqueue("research", {"lead_id": 2})
    assert db.claim()["kind"] == "professional_research"
    assert json.loads(db.claim()["payload"])["lead_id"] == 2
    assert db.claim() is None


async def test_real_source_denial_status_is_retained_in_capture_api_and_report_without_contacts(db,settings,prepared,monkeypatch):
    async def snapshot(s,url):
        return {'state':'operator_attention','url':url,'http_status':999,'capture_method':'managed_browser_professional_profile'}
    monkeypatch.setattr(professionals,'profile_snapshot',snapshot)
    result=await research_professionals(db,settings,prepared['lead_id'],URL)
    assert result['captures'][0]['access_issue']=={'http_status':999}
    assert captures(db,prepared['lead_id'])[0]['access_issue']=={'http_status':999}
    assert not db.one("SELECT 1 FROM jobs WHERE kind='verify'")


def test_final_audits_queue_professional_lookup_even_when_a_generic_contact_exists(db, settings, prepared):
    lid = prepared["lead_id"]
    settings.auto_professional_research = True
    db.execute("UPDATE leads SET status='review' WHERE id=?", (lid,))
    db.execute(
        "INSERT INTO crawls(lead_id,report,created_at) VALUES(?,?,?)",
        (lid, '{"status":"partial"}', time.time() - 1),
    )
    schedule_final_audits(db, settings, {"lead_id": lid})
    assert db.one("SELECT payload FROM jobs WHERE kind='professional_research'")["payload"] == json.dumps(
        {"lead_id": lid}, sort_keys=True
    )


async def test_current_official_profile_links_skip_index_when_capture_budget_is_full(
    db, settings, public_person, monkeypatch
):
    lid, value = public_person
    page = db.one("SELECT * FROM evidence WHERE id=?", (value["company_evidence_id"],))
    report = {"pages": [{"url": page["url"], "sha256": page["sha256"], "professional_links": [URL]}]}
    db.execute(
        "INSERT INTO crawls(lead_id,report,created_at) VALUES(?,?,?)",
        (lid, json.dumps(report), time.time() - 1),
    )
    settings.professional_max_profiles = 1

    async def forbidden(*args, **kwargs):
        pytest.fail("Current sourced profile fills the budget; no index request needed")

    monkeypatch.setattr("outreach.providers.discover", forbidden)
    result = await research_professionals(db, settings, lid)
    assert len(result["captures"]) == 1 and not result["queries"]
    assert captures(db, lid)[0]["source_hint"]["origin"] == "captured_official_link"


async def test_changed_official_page_hash_does_not_reuse_old_profile_links(
    db, settings, public_person, monkeypatch
):
    lid, value = public_person
    page = db.one("SELECT * FROM evidence WHERE id=?", (value["company_evidence_id"],))
    report = {"pages": [{"url": page["url"], "sha256": "old-hash", "professional_links": [URL]}]}
    db.execute(
        "INSERT INTO crawls(lead_id,report,created_at) VALUES(?,?,?)",
        (lid, json.dumps(report), time.time() - 1),
    )
    settings.discovery_query_delay_seconds = 0.001

    async def search(*args, **kwargs):
        return []

    async def forbidden(*args, **kwargs):
        pytest.fail("Stale navigation is not current profile discovery proof")

    monkeypatch.setattr("outreach.providers.discover", search)
    monkeypatch.setattr(professionals, "profile_snapshot", forbidden)
    result = await research_professionals(db, settings, lid)
    assert result["state"] == "held" and not result["captures"]


async def test_imported_contact_proof_survives_approval_but_employer_change_stops_sequence(
    db, settings, public_person, safe_result
):
    from outreach.campaigns import create_drafts, approve
    from outreach.sequence import assert_approved

    lid, value = public_person
    cid = review_contact(db, lid, value)
    db.execute(
        "UPDATE contacts SET verification='safe',verification_raw=?,verified_at=? WHERE id=?",
        (json.dumps({**safe_result, "input": value["email"]}), time.time(), cid),
    )
    create_drafts(db, settings, cid)
    approve(
        db,
        settings,
        cid,
        "Reviewed UK corporate outreach eligibility and opt-out route.",
        "Current founder responsible for this company website.",
    )
    lead = db.one("SELECT * FROM leads WHERE id=?", (lid,))
    contact = db.one("SELECT * FROM contacts WHERE id=?", (cid,))
    with db.connect() as con:
        assert_approved(con, settings, lead, contact)
    db.execute(
        "UPDATE evidence SET sha256=? WHERE id=?", ("changed-employer-proof", value["company_evidence_id"])
    )
    with db.connect() as con:
        with pytest.raises(ValueError):
            assert_approved(con, settings, lead, contact)
    assert not db.one("SELECT 1 FROM messages WHERE state='sent'")
