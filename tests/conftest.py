import json
import time

import pytest

from outreach.config import Settings
from outreach.db import DB
from outreach.research import add_lead, add_contact
from outreach.campaigns import review_lead, create_drafts, approve


@pytest.fixture(autouse=True)
def fictional_email_writer(monkeypatch):
    """Legacy workflow tests use controlled copy, never live AI or network calls.

    Real writer/validation/provider contracts are exercised separately. This
    fixture is not evidence of human-sounding model quality.
    """
    from outreach import email_writer
    from outreach.campaigns import draft_sequence

    def generate(settings, lead, contact, finding, evidence, *, before_request=None, audit_context=None, proof_context=None):
        if before_request:
            before_request()
        source = next(e for e in evidence if e['id'] == finding['evidence_id'])
        return {'messages': draft_sequence(lead['company'], lead['service'], finding, source['url'], contact['name'])[:4 if settings.followups_enabled else 1],
                'provenance': {'method': 'research_ai', 'model': 'fictional-test-writer',
                               'source_ids': [e['id'] for e in evidence], 'review_required': True}}
    monkeypatch.setattr(email_writer, 'generate_sequence', generate)


@pytest.fixture
def settings(tmp_path):
    # Legacy pilots remain explicitly covered; production defaults and dispatch are
    # exercised with followups_enabled=False in test_single_email.py.
    return Settings(_env_file=None, data_dir=tmp_path, admin_password="test-admin-password-123",
                    api_token="test-token-" + "a" * 40, public_url="https://outreach.example.com",
                    worker_enabled=False, sending_enabled=True, followups_enabled=True, auto_contact_research=False,auto_professional_research=False, journey_audit_enabled=False,
                    commoncrawl_hints_enabled=False, professional_refresh_official_links=False, search_fallback_engines="", sender_name="Test Sender",
                    sender_company="Example Studio", sender_email="team@sender.example.com",
                    postal_address="123 Example Street, Test City", domain_auth_confirmed=True,
                    smtp_host="smtp.example.com", smtp_user="test", smtp_password="test",
                    imap_host="imap.example.com", imap_user="test", imap_password="test",
                    copy_min_score=0)  # Copy-score rewrites are covered in test_copywriting.py.


@pytest.fixture
def db(settings):
    return DB(settings.database)


@pytest.fixture
def safe_result():
    return {"input": "alex@bright-demo.com", "is_reachable": "safe",
            "syntax": {"is_valid_syntax": True}, "mx": {"accepts_mail": True},
            "misc": {"is_disposable": False, "is_role_account": False},
            "smtp": {"can_connect_smtp": True, "is_deliverable": True, "is_catch_all": False,
                     "is_disabled": False, "has_full_inbox": False}}


@pytest.fixture
def prepared(db, settings, safe_result):
    lid = add_lead(db, "Bright Demo", "https://bright-demo.com", "A", "https://bright-demo.com/about")
    eid = db.execute("INSERT INTO evidence(lead_id,url,title,text,sha256,fetched_at) VALUES(?,?,?,?,?,?)",
                     (lid, "https://bright-demo.com/", "Bright Demo", "We offer UK consulting services. Contact us for a consultation. Business enquiries: alex@bright-demo.com", "abc", time.time()))
    review_lead(db, lid, {"company": "Bright Demo", "country": "UK", "country_source": "https://bright-demo.com/",
                         "country_quote": "UK consulting services",
                         "timezone": "Europe/London", "business_type": "corporate", "service": "website_improvement",
                         'primary_goal': 'inquiries_bookings',
                         "fit_notes": "Relevant consulting company serving UK business clients.", "evidence_id": eid,
                         "quote": "Contact us for a consultation.",
                         "observation": "Your homepage invites visitors to contact you for a consultation.",
                         "suggestion": "Test a clearer explanation of what the first consultation includes."})
    cid = add_contact(db, lid, "alex@bright-demo.com", "https://bright-demo.com/", "Alex", "Founder")
    db.execute("UPDATE contacts SET verification='safe',verification_raw=?,verified_at=? WHERE id=?", (json.dumps(safe_result), time.time(), cid))
    create_drafts(db, settings, cid)
    return {"lead_id": lid, "contact_id": cid, "evidence_id": eid}


@pytest.fixture
def active(db, settings, prepared):
    approve(db, settings, prepared["contact_id"], "Reviewed UK corporate B2B eligibility and legitimate interests, with opt-out.", "Founder responsible for the company website.")
    db.set("paused", "false")
    return prepared
