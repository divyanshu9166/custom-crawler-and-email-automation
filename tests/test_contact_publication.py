"""Company-domain addresses need public evidence before probing or outreach."""
import json
import time

import pytest
from fastapi.testclient import TestClient

from outreach import providers
from outreach.app import create_app
from outreach.campaigns import approve, create_drafts
from outreach.research import add_contact, assert_contact_ownership, record_contact_publications, verify_contact
from outreach.sequence import assert_approved
from outreach.web import extract_page


def save(db, lid, page):
    db.execute('INSERT INTO evidence(lead_id,url,title,text,sha256,fetched_at) VALUES(?,?,?,?,?,?) ON CONFLICT(lead_id,url) DO UPDATE SET text=excluded.text,sha256=excluded.sha256,fetched_at=excluded.fetched_at',
               (lid, page['url'], page['title'], page['text'], page['sha256'], time.time()))
    record_contact_publications(db, lid, page)


async def test_same_domain_guessed_address_never_reaches_provider(db, settings, prepared, monkeypatch):
    cid = add_contact(db, prepared['lead_id'], 'guessed@bright-demo.com', 'https://bright-demo.com/')
    async def forbidden(*_, **__):
        pytest.fail('An unpublished address must not reach a verification provider')
    monkeypatch.setattr(providers, 'verify_email', forbidden)
    with pytest.raises(ValueError, match='publication evidence'):
        await verify_contact(db, settings, cid)
    assert db.one('SELECT verification FROM contacts WHERE id=?', (cid,))['verification'] == 'unverified'


@pytest.mark.parametrize('change', ['expired', 'future', 'removed', 'new_attempt', 'foreign_source'])
async def test_same_domain_publication_rechecked_before_probe(db, settings, prepared, monkeypatch, change):
    if change == 'expired':
        db.execute('UPDATE evidence SET fetched_at=?', (time.time()-31*86400,))
    elif change == 'future':
        db.execute('UPDATE evidence SET fetched_at=?', (time.time()+120,))
    elif change == 'removed':
        db.execute("UPDATE evidence SET text='Business contact is now a form only'")
    elif change == 'new_attempt':
        db.execute('INSERT INTO crawls(lead_id,report,created_at) VALUES(?,?,?)',
                   (prepared['lead_id'], '{}', time.time()))
    else:
        db.execute("UPDATE contacts SET source_url='https://foreign-demo.com/contact'")
    async def forbidden(*_, **__):
        pytest.fail('Invalid source cannot reach a provider')
    monkeypatch.setattr(providers, 'verify_email', forbidden)
    with pytest.raises(ValueError, match='publication evidence'):
        await verify_contact(db, settings, prepared['contact_id'])


@pytest.mark.parametrize('html', [
    '<p>Public business email</p><a href="mailto:hello@bright-demo.com">Contact us</a>',
    '<p>Our public team</p><script type="application/ld+json">{"@type":"Person","name":"Alex","email":"hello@bright-demo.com"}</script>',
])
async def test_extraction_proof_allows_published_mailto_or_structured_email_not_in_visible_text(db, settings, prepared, monkeypatch, safe_result, html):
    page = extract_page('https://bright-demo.com/contact', html)
    assert 'hello@bright-demo.com' not in page['text']
    save(db, prepared['lead_id'], page)
    cid = add_contact(db, prepared['lead_id'], 'hello@bright-demo.com', page['url'])
    calls = []
    async def verify(_, email, *, before_probe=None):
        if before_probe:
            before_probe()
        calls.append(email)
        return 'safe', {**safe_result, 'input': email}
    monkeypatch.setattr(providers, 'verify_email', verify)
    await verify_contact(db, settings, cid)
    assert calls == ['hello@bright-demo.com']
    db.execute("UPDATE evidence SET sha256='changed' WHERE url=?", (page['url'],))
    with pytest.raises(ValueError, match='publication evidence'):
        assert_contact_ownership(db, db.one('SELECT * FROM contacts WHERE id=?', (cid,)),
                                 db.one('SELECT * FROM leads WHERE id=?', (prepared['lead_id'],)))


def test_new_pending_contact_adopts_actual_fresh_publication_but_not_unsubstantiated_source(db, prepared):
    lid = prepared['lead_id']
    cid = add_contact(db, lid, 'hello@bright-demo.com', 'https://bright-demo.com/')
    page = extract_page('https://bright-demo.com/contact', '<p>Business enquiries hello@bright-demo.com</p>')
    save(db, lid, page)
    assert add_contact(db, lid, 'hello@bright-demo.com', page['url']) == cid
    assert db.one('SELECT source_url FROM contacts WHERE id=?', (cid,))['source_url'] == page['url']
    assert add_contact(db, lid, 'hello@bright-demo.com', 'https://bright-demo.com/team') == cid
    assert db.one('SELECT source_url FROM contacts WHERE id=?', (cid,))['source_url'] == page['url']


def test_approval_freezes_separate_recipient_publication_page(db, settings, prepared):
    lid, cid = prepared['lead_id'], prepared['contact_id']
    page = extract_page('https://bright-demo.com/contact', '<p>Business contact alex@bright-demo.com</p>')
    save(db, lid, page)
    add_contact(db, lid, 'alex@bright-demo.com', page['url'])
    approve(db, settings, cid, 'Reviewed appropriate corporate outreach eligibility', 'Relevant website decision owner')
    db.execute("UPDATE evidence SET sha256='new-contact-page' WHERE url=?", (page['url'],))
    with db.connect() as con:
        with pytest.raises(ValueError, match='changed'):
            assert_approved(con, settings, db.one('SELECT * FROM leads WHERE id=?', (lid,)),
                            db.one('SELECT * FROM contacts WHERE id=?', (cid,)))
    # Publication remains visible, but it no longer matches the frozen review.
    assert_contact_ownership(db, db.one('SELECT * FROM contacts WHERE id=?', (cid,)),
                             db.one('SELECT * FROM leads WHERE id=?', (lid,)))


def test_suppressed_contact_keeps_original_source_on_reimport(db, prepared):
    lid, cid = prepared['lead_id'], prepared['contact_id']
    db.suppress('alex@bright-demo.com', 'Actual opt-out fixture')
    page = extract_page('https://bright-demo.com/contact', '<p>alex@bright-demo.com</p>')
    save(db, lid, page)
    add_contact(db, lid, 'alex@bright-demo.com', page['url'])
    row = db.one('SELECT source_url,status FROM contacts WHERE id=?', (cid,))
    assert row == {'source_url': 'https://bright-demo.com/', 'status': 'suppressed'}


def test_contact_detail_explains_publication_hold_without_mutation(db, settings, prepared):
    cid = add_contact(db, prepared['lead_id'], 'guessed@bright-demo.com', 'https://bright-demo.com/')
    before = db.all('SELECT * FROM events')
    client = TestClient(create_app(settings), headers={'Authorization': 'Bearer '+settings.api_token})
    response = client.get(f"/api/leads/{prepared['lead_id']}")
    row = next(c for c in response.json()['contacts'] if c['id'] == cid)
    assert row['source_eligible'] is False and 'publication evidence' in row['source_issue']
    assert db.all('SELECT * FROM events') == before
    assert not db.one("SELECT 1 FROM messages WHERE state='sent'")
    jobs = db.one('SELECT COUNT(*) n FROM jobs')['n']
    assert client.post(f'/api/contacts/{cid}/verify').status_code == 400
    assert db.one('SELECT COUNT(*) n FROM jobs')['n'] == jobs


def test_manual_unpublished_contact_can_be_saved_but_cannot_queue_probe(db, settings, prepared):
    client = TestClient(create_app(settings), headers={'Authorization': 'Bearer '+settings.api_token})
    response = client.post(f"/api/leads/{prepared['lead_id']}/contacts", json={
        'email': 'guessed@bright-demo.com', 'source_url': 'https://bright-demo.com/'})
    assert response.status_code == 200
    assert response.json()['job_id'] is None and response.json()['source_eligible'] is False
    assert not db.one("SELECT 1 FROM jobs WHERE kind='verify'")


def test_publication_proof_deduplicates_and_never_counts_hidden_script_address(db, prepared):
    page = extract_page('https://bright-demo.com/contact', '<p>Contact hello@bright-demo.com</p><script>hidden@bright-demo.com</script>')
    save(db, prepared['lead_id'], page)
    record_contact_publications(db, prepared['lead_id'], page)
    events = db.all("SELECT detail FROM events WHERE kind='contact_publication_found'")
    assert len(events) == 1 and json.loads(events[0]['detail'])['email'] == 'hello@bright-demo.com'


def test_safe_verdict_cannot_approve_an_unpublished_company_domain_recipient(db, settings, prepared, safe_result):
    cid = add_contact(db, prepared['lead_id'], 'guessed@bright-demo.com', 'https://bright-demo.com/')
    with pytest.raises(ValueError, match='publication evidence'):
        create_drafts(db, settings, cid)
    assert not db.one('SELECT 1 FROM messages WHERE contact_id=?', (cid,))
    db.execute("UPDATE contacts SET verification='safe',verified_at=?,verification_raw=? WHERE id=?",
               (time.time(), json.dumps({**safe_result, 'input': 'guessed@bright-demo.com'}), cid))
    with pytest.raises(ValueError, match='publication evidence'):
        approve(db, settings, cid, 'Reviewed corporate outreach eligibility', 'Relevant business enquiry inbox')
    assert not db.one("SELECT 1 FROM events WHERE kind='sequence_approved'")
    assert not db.one("SELECT 1 FROM messages WHERE state IN ('queued','sent','sending')")


def test_unpublished_contact_appears_as_review_and_hold_on_both_maps(db, settings, prepared):
    from outreach.workflow import snapshot
    from outreach.workflow_detail import detailed_snapshot
    add_contact(db, prepared['lead_id'], 'guessed@bright-demo.com', 'https://bright-demo.com/')
    overview = {n['id']: n for n in snapshot(db, settings, prepared['lead_id'])['nodes']}
    detail = {n['id']: n for n in detailed_snapshot(db, settings, prepared['lead_id'])['nodes']}
    assert overview['contacts']['state'] == 'review'
    assert detail['E1']['state'] == 'review' and detail['E1']['metric'].startswith('1/2')
    assert detail['H']['state'] == 'blocked'


async def test_publication_is_rechecked_after_provider_spacing_wait(db, settings, prepared, monkeypatch):
    db.set('last_verification_attempt', time.time())
    async def wait(_):
        db.execute("UPDATE evidence SET text='Only a public enquiry form remains'")
    async def forbidden(*_, **__):
        pytest.fail('Publication removed while waiting cannot reach provider')
    monkeypatch.setattr('outreach.research.asyncio.sleep', wait)
    monkeypatch.setattr(providers, 'verify_email', forbidden)
    with pytest.raises(ValueError, match='publication evidence'):
        await verify_contact(db, settings, prepared['contact_id'])
