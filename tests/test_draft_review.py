import importlib.util
import json
from pathlib import Path

import pytest

from outreach.campaigns import create_drafts
from outreach.web import extract_page

spec = importlib.util.spec_from_file_location("draft_review", Path(__file__).resolve().parents[1] / "scripts" / "draft_review.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.fixture
def review_input(tmp_path):
    run = tmp_path / "benchmark"
    run.mkdir()
    name = "company-001-bright-demo.com.json"
    page = extract_page("https://bright-demo.com/", '<p>Bright Demo. Based in London UK. Contact us for a consultation.</p>')
    (run / name).write_text(json.dumps({"company": "Bright Demo", "website": page["url"], "campaign": "A", "pages": [page]}))
    (run / "summary.json").write_text(json.dumps({"scope": {"max_pages": 30}, "companies": [{"detail_file": name, "status": "partial"}]}))
    annotation = {"detail_file": name, "service": "website_improvement", "evidence_url": page["url"],
                  "quote": "Contact us for a consultation.", "country": "UK", "country_source": page["url"],
                  "country_quote": "London UK", "observation": "Your page invites visitors to contact you for a consultation.",
                  "suggestion": "Test an explanation of what the initial consultation includes.",
                  "review_notes": "Specific published invitation checked; no conversion loss or buyer identity claimed."}
    return run, annotation, tmp_path / "review"


def test_historical_offline_previews_match_controlled_fixture_copy_only(review_input, db, settings, prepared):
    run, annotation, output = review_input
    report = module.build_review(run, [annotation], output)
    cid = prepared["contact_id"]
    db.execute("UPDATE contacts SET name='' WHERE id=?", (cid,))
    lid = prepared["lead_id"]
    finding = json.loads(db.one('SELECT findings FROM leads WHERE id=?', (lid,))['findings'])[0]
    finding.update(observation=annotation['observation'], suggestion=annotation['suggestion'])
    db.execute("UPDATE leads SET findings=? WHERE id=?", (json.dumps([finding]), lid))
    create_drafts(db, settings, cid)
    expected = db.all("SELECT step,subject,body FROM messages WHERE contact_id=? ORDER BY step", (cid,))
    assert [{key: item[key] for key in ("step", "subject", "body")} for item in report["records"][0]["sequence"]] == expected
    assert report["method"] == "offline_template_preview"
    assert report["message_count"] == 4
    assert report["records"][0]["recipient_email"] is None
    assert report["records"][0]["send_ready"] is False
    assert not list(output.glob("*.db"))
    assert "operator approval" in (output / "draft-review.html").read_text()


@pytest.mark.parametrize("field,value,reason", [
    ("quote", "An invented observation", "exactly match"),
    ("country_quote", "Invented country", "exact quote"),
    ("evidence_url", "https://other-demo.com/", "saved official"),
    ("service", "store_improvement", "campaign"),
    ("detail_file", "unfinished.json", "completed"),
    ("company", "Invented legal company name", "Company name"),
])
def test_preview_rejects_unsourced_or_ineligible_annotations(review_input, field, value, reason):
    run, annotation, output = review_input
    annotation[field] = value
    with pytest.raises(ValueError, match=reason):
        module.build_review(run, [annotation], output)
    assert not output.exists()


def test_preview_rejects_duplicate_companies_and_escapes_observation(review_input):
    run, annotation, output = review_input
    with pytest.raises(ValueError, match="distinct"):
        module.build_review(run, [annotation, annotation], output)
    annotation["observation"] = '<script>alert("untrusted instruction")</script>'
    module.build_review(run, [annotation], output)
    rendered = (output / "draft-review.html").read_text()
    assert "<script>" not in rendered and "&lt;script&gt;" in rendered
