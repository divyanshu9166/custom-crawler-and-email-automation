import json

import httpx
import pytest

from outreach.providers import classify_reacher, verify_email, discover, research_suggestions
from outreach.research import add_lead, add_contact, research_lead, verify_contact
from outreach.web import extract_page, normalize_url, PublicWeb


def test_reacher_safe_requires_all_checks(safe_result):
    assert classify_reacher(safe_result) == "safe"
    safe_result["smtp"].pop("is_catch_all")
    assert classify_reacher(safe_result) == "unknown"


@pytest.mark.parametrize("key,value,expected", [("is_catch_all", True, "catch_all"), ("is_deliverable", False, "unknown"),
                                               ("is_disabled", True, "unknown"), ("has_full_inbox", True, "unknown")])
def test_reacher_contradictions(safe_result, key, value, expected):
    safe_result["smtp"][key] = value
    assert classify_reacher(safe_result) == expected


@pytest.mark.parametrize("value", ["risky", "unknown", "invalid"])
def test_reacher_reachability(safe_result, value):
    safe_result["is_reachable"] = value
    assert classify_reacher(safe_result) == value


def test_reacher_disposable(safe_result):
    safe_result["misc"]["is_disposable"] = True
    assert classify_reacher(safe_result) == "disposable"
    assert classify_reacher({}) == "unknown"


def test_extract_only_sourced_business_emails():
    page = extract_page("https://bright-demo.com", '<title>Bright</title><a href="mailto:alex@bright-demo.com">Alex</a><p>hello@bright-demo.com outsider@gmail.com privacy@bright-demo.com</p><script>secret@bright-demo.com</script>')
    assert page["emails"] == ["alex@bright-demo.com", "hello@bright-demo.com"]
    assert "secret" not in page["text"]


def test_relative_contact_links_are_discovered():
    page = extract_page("https://bright-demo.com/", '<a href="contact">Contact</a><a href="javascript:alert(1)">Ignore</a>')
    assert page["links"] == ["https://bright-demo.com/contact"]


@pytest.mark.parametrize("url", ["http://127.0.0.1", "http://169.254.169.254/", "http://localhost", "file:///etc/passwd", "https://user:pass@domain.com", "https://domain.com:8080"])
def test_reject_unsafe_urls(url):
    with pytest.raises(ValueError):
        normalize_url(url)


def test_company_and_contact_dedup_preserves_suppression(db):
    lid = add_lead(db, "Demo", "https://www.bright-demo.com/", "A", "https://bright-demo.com/")
    assert add_lead(db, "Duplicate", "https://bright-demo.com", "B", "https://bright-demo.com") == lid
    cid = add_contact(db, lid, "alex@bright-demo.com", "https://bright-demo.com")
    db.suppress("alex@bright-demo.com", "opt out")
    assert add_contact(db, lid, "alex@bright-demo.com", "https://bright-demo.com") == cid
    assert db.one("SELECT status FROM contacts WHERE id=?", (cid,))["status"] == "suppressed"
    with pytest.raises(ValueError):
        add_contact(db, lid, "another@gmail.com", "https://bright-demo.com")


async def test_public_fetch_pins_checked_ip(settings, monkeypatch):
    from outreach import web
    async def ip(host):
        return "93.184.215.14"
    monkeypatch.setattr(web, "public_ip", ip)
    def handle(request):
        assert request.url.host == "93.184.215.14"
        assert request.headers["host"] == "example.com"
        assert request.extensions["sni_hostname"] == "example.com"
        return httpx.Response(200, headers={"content-type": "text/html"}, text="<h1>Works</h1>")
    original = httpx.AsyncClient
    monkeypatch.setattr(web.httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(handle), **kwargs))
    _, html, _ = await PublicWeb(settings).get("https://example.com", "example.com")
    assert "Works" in html


async def test_robots_denial_prevents_crawl(settings, monkeypatch):
    calls = []
    async def get(self, url, expected_domain=None):
        calls.append(url)
        return url, "User-agent: *\nDisallow: /", 200
    monkeypatch.setattr(PublicWeb, "get", get)
    with pytest.raises(ValueError, match="No accessible"):
        await PublicWeb(settings).crawl("https://bright-demo.com/")
    assert len(calls) == 1


async def test_reacher_adapter_contract(settings, safe_result, monkeypatch):
    def handle(request):
        assert request.url.path == "/v0/check_email"
        assert "to_email" in json.loads(request.content)
        if json.loads(request.content)['to_email'] == 'invalid-address-without-at-sign':
            return httpx.Response(200, json={'input': 'invalid-address-without-at-sign', 'is_reachable': 'invalid'})
        return httpx.Response(200, json=safe_result)
    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(handle), **kwargs))
    assert (await verify_email(settings, "alex@bright-demo.com"))[0] == "safe"
    with pytest.raises(ValueError, match="does not match"):
        await verify_email(settings, "different@bright-demo.com")


async def test_research_to_contacts_and_verification(db, settings, monkeypatch, safe_result):
    from outreach import providers
    lid = add_lead(db, "Bright Demo", "https://bright-demo.com", "A", "https://bright-demo.com")
    async def crawl(self, website):
        return [extract_page(website, '<title>Demo</title><p>UK consulting services. Contact Alex alex@bright-demo.com for a consultation.</p>')]
    async def verify(settings, email, *, before_probe=None):
        if before_probe:
            before_probe()
        return "safe", safe_result
    monkeypatch.setattr(PublicWeb, "crawl", crawl)
    monkeypatch.setattr(providers, "verify_email", verify)
    await research_lead(db, settings, lid)
    c = db.one("SELECT * FROM contacts")
    assert c["verification"] == "unverified"
    assert db.one("SELECT kind FROM jobs")["kind"] == "verify"
    await verify_contact(db, settings, c["id"])
    assert db.one("SELECT verification FROM contacts")["verification"] == "safe"
    assert db.one("SELECT status FROM leads")["status"] == "review"
    assert db.one("SELECT country FROM leads")["country"] == ""  # No country inferred from query.


async def test_recrawl_suggestions_exclude_unvisited_historical_pages(db, settings, monkeypatch):
    import time
    lid = add_lead(db, "Bright Demo", "https://bright-demo.com", "A", "https://bright-demo.com")
    old = db.execute("INSERT INTO evidence(lead_id,url,title,text,sha256,fetched_at) VALUES(?,?,?,?,?,?)",
                     (lid, "https://bright-demo.com/legacy", "Old page", "Old launch and old contact details.", "old", time.time() - 60))
    async def crawl(self, website):
        self.report.update(status="partial")
        return [extract_page(website, '<h1>Current company services</h1><p>Contact the team for current information.</p>')]
    seen = []
    async def suggest(settings, lead, evidence):
        seen.extend(evidence)
        return []
    monkeypatch.setattr(PublicWeb, "crawl", crawl)
    monkeypatch.setattr("outreach.providers.research_suggestions", suggest)
    await research_lead(db, settings, lid)
    assert len(seen) == 1 and seen[0]["url"] == "https://bright-demo.com/"
    assert json.loads(db.one("SELECT findings FROM leads WHERE id=?", (lid,))["findings"])[0]["evidence_id"] != old
    assert db.one("SELECT COUNT(*) n FROM evidence WHERE lead_id=?", (lid,))["n"] == 2


async def test_search_contract(settings, monkeypatch):
    def handle(request):
        assert request.url.params["format"] == "json"
        return httpx.Response(200, json={"results": [{"url": "https://bright-demo.com", "title": "Demo"}]})
    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(handle), **kwargs))
    assert (await discover(settings, "UK businesses"))[0]["title"] == "Demo"


async def test_ai_rejects_invented_quote(settings, monkeypatch):
    settings.openai_api_key = "test"
    settings.openai_model = "configured-model"
    def handle(request):
        request_json = json.loads(request.content)
        assert request_json["store"] is False
        assert "tools" not in request_json
        findings = [{"evidence_id": 1, "quote": "not actually present", "service": "website_improvement",
                     "observation": "Unfounded", "suggestion": "Fix it"}]
        return httpx.Response(200, json={"status": "completed", "output": [{"content": [{"type": "output_text", "text": json.dumps({"findings": findings})}]}]})
    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: original(transport=httpx.MockTransport(handle), **kwargs))
    assert await research_suggestions(settings, {"campaign": "A", "company": "Demo"}, [{"id": 1, "text": "Actual public content"}]) == []
