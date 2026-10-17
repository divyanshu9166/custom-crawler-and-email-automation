"""Live crawling found a privacy-only inbox; prevent that route from sales/probe automation."""
import json
import time

import pytest

from outreach.research import add_contact, verify_contact, contact_candidates
from outreach.web import extract_page
from test_contact_candidates import publish_candidate
from outreach.research import add_lead, discover_leads, research_lead


@pytest.mark.parametrize('url', ['https://m.indiamart.com/roofing/', 'https://exportersindia.com/roofing/',
                                  'https://www.tradeindia.com/roofing/', 'https://alibaba.com/roofing/'])
def test_marketplace_cannot_enter_as_official_company_even_via_import(db, url):
    with pytest.raises(ValueError, match='not an official company'):
        add_lead(db, 'Roofing directory fixture', url, 'A', url)
    assert db.all('SELECT id FROM leads') == []


async def test_noisy_live_search_marketplace_cannot_consume_official_lead_slot(db, settings, monkeypatch):
    settings.discovery_platforms = ''
    async def search(*_, **__):
        return [{'url': 'https://m.indiamart.com/roofing/', 'title': 'Roofing Contractors Services in India'},
                {'url': 'https://roofing-fixture.example/contact/', 'title': 'Raleigh roofing contractor fixture'}]
    monkeypatch.setattr('outreach.providers.discover', search)
    await discover_leads(db, settings, 'roofing contractor Raleigh', 'A', 'US', 1)
    assert db.one('SELECT domain FROM leads')['domain'] == 'roofing-fixture.example'
    assert db.one('SELECT COUNT(*) n FROM leads')['n'] == 1


async def test_historical_marketplace_candidate_cannot_recrawl_or_qualify(db, settings, prepared, monkeypatch):
    from outreach.offers import selected_offer
    lid = prepared['lead_id']
    db.execute("UPDATE leads SET domain='m.indiamart.com',website='https://m.indiamart.com/' WHERE id=?", (lid,))
    async def forbidden(*_):
        pytest.fail('Known marketplace cannot consume a company research crawl')
    monkeypatch.setattr('outreach.web.PublicWeb.crawl', forbidden)
    lead = db.one('SELECT * FROM leads WHERE id=?', (lid,))
    assert selected_offer(db, lead) == ''
    with pytest.raises(ValueError, match='not an official company'):
        await research_lead(db, settings, lid)
    assert db.one('SELECT status FROM leads WHERE id=?', (lid,))['status'] == 'research_failed'


@pytest.mark.parametrize('status', ['running', 'researching'])
def test_worker_restart_labels_preserved_capture_interrupted(db, prepared, status):
    lid = prepared['lead_id']
    report = {'status': status, 'pages': [{'url': 'https://bright-demo.com/', 'text_chars': 100}]}
    crawl = db.execute('INSERT INTO crawls(lead_id,report,created_at) VALUES(?,?,?)', (lid, json.dumps(report), time.time()))
    job = db.enqueue('research', {'lead_id': lid})
    db.execute("UPDATE jobs SET state='running',attempts=1 WHERE id=?", (job,))
    db.recover()
    recovered = json.loads(db.one('SELECT report FROM crawls WHERE id=?', (crawl,))['report'])
    assert recovered['status'] == 'interrupted' and recovered['pages'] == report['pages']
    assert db.one('SELECT state FROM jobs WHERE id=?', (job,))['state'] == 'pending'


@pytest.mark.parametrize('local', ['dataprotection', 'data-protection', 'data.protection', 'dpo', 'DPO+request',
                                  'gdpr', 'security', 'compliance', 'postmaster', 'no_reply', 'privacy-office', 'abuse'])
def test_dedicated_nonbuyer_inbox_not_extracted_as_outreach_contact(local):
    address = local+'@bright-demo.com'
    page = extract_page('https://bright-demo.com/contact',
                        '<p>'+address+'</p><a href="mailto:'+address+'">Contact</a>'
                        '<script type="application/ld+json">'+json.dumps({'@type': 'Organization', 'email': address})+'</script>'
                        '<a href="mailto:hello@bright-demo.com">Business inquiries</a>')
    assert page['emails'] == ['hello@bright-demo.com']
    assert all(c['email'] == 'hello@bright-demo.com' for c in page['contacts'])


def test_privacy_only_external_candidate_cannot_be_added_or_probe(db, settings, prepared):
    source = publish_candidate(db, prepared['lead_id'], 'legacy@external-demo.com')
    db.execute("UPDATE events SET detail=json_set(detail,'$.email','dpo@external-demo.com') WHERE kind='contact_candidate_found'")
    assert contact_candidates(db, prepared['lead_id']) == []
    with pytest.raises(ValueError, match='not a relevant outreach'):
        add_contact(db, prepared['lead_id'], 'dpo@external-demo.com', source,
                    ownership_notes='Published company privacy inbox on current official source.')


async def test_legacy_privacy_contact_cannot_reach_verification_provider(db, settings, prepared, monkeypatch):
    cid = prepared['contact_id']
    db.execute("UPDATE contacts SET email='dataprotection@bright-demo.com',verified_at=? WHERE id=?", (time.time(), cid))
    async def forbidden(*_):
        pytest.fail('A dedicated privacy inbox must not be probed for outreach')
    monkeypatch.setattr('outreach.providers.verify_email', forbidden)
    with pytest.raises(ValueError, match='not a relevant outreach'):
        await verify_contact(db, settings, cid)
