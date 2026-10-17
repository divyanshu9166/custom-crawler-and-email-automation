"""Cross-node regressions and a connected acquisition/client journey in isolated fixtures."""
import json
import time

import pytest
from fastapi.testclient import TestClient

from outreach.app import create_app
from outreach.campaigns import approve, create_drafts, review_lead
from outreach.deliverables import create, action
from outreach.research import add_contact, contact_candidates, research_lead, verify_contact
from outreach.workflow import snapshot
from outreach.workflow_detail import detailed_snapshot
from test_contact_candidates import publish_candidate
from test_profile_prospects import PROFILE, mock_profile, review_value
from test_sales import proposal_payload, sales_payload
from test_mail_wire import tls, configure_smtp  # noqa: F401 -- pytest fixture discovery
from mail_servers import mail_server


def mapped(db, settings, lid):
    return {n['id']: n for n in detailed_snapshot(db, settings, lid)['nodes']}


def test_complete_current_page_and_qualification_states_expire_together(db, settings, prepared):
    db.execute('UPDATE evidence SET fetched_at=?', (time.time()-31*86400,))
    detailed = mapped(db, settings, prepared['lead_id'])
    assert detailed['E']['metric'] == '0 current source pages'
    assert all(detailed[key]['state'] != 'complete' for key in ('G', 'AA', 'J'))
    overview = {n['id']: n for n in snapshot(db, settings, prepared['lead_id'])['nodes']}
    assert overview['qualify']['state'] == 'review'
    assert overview['approval']['state'] == 'blocked'


@pytest.mark.parametrize('change', ['source', 'body', 'identity'])
def test_complete_changed_approval_context_visible_before_worker_attempt(db, settings, active, change):
    if change == 'source':
        db.execute("UPDATE evidence SET sha256='changed-source'")
    elif change == 'body':
        db.execute("UPDATE messages SET body=body || ' Unreviewed claim' WHERE step=0")
    else:
        settings.sender_email = 'changed@sender.example.com'
    detailed = mapped(db, settings, active['lead_id'])
    assert detailed['J']['state'] == detailed['K']['state'] == 'blocked'
    assert detailed['H']['state'] == 'blocked'


@pytest.mark.parametrize('change', ['source', 'expired'])
def test_complete_artifact_map_does_not_treat_historical_approval_as_current(db, settings, prepared, change):
    aid = create(db, prepared['lead_id'], {'kind': 'audit', 'title': 'Fictional sourced audit'})
    action(db, aid, 'approve')
    assert mapped(db, settings, prepared['lead_id'])['S']['state'] == 'complete'
    if change == 'source':
        db.execute("UPDATE evidence SET sha256='changed-artifact-source'")
    else:
        db.execute('UPDATE evidence SET fetched_at=?', (time.time()-31*86400,))
    assert mapped(db, settings, prepared['lead_id'])['S']['state'] == 'review'


@pytest.mark.parametrize('age', [31*86400, -120])
async def test_complete_expired_or_future_alias_source_cannot_probe(db, settings, prepared, monkeypatch, age):
    source = publish_candidate(db, prepared['lead_id'], 'owner@external-demo.com')
    cid = add_contact(db, prepared['lead_id'], 'owner@external-demo.com', source,
                      ownership_notes='Fictional business explicitly publishes this as its current inquiry inbox.')
    db.execute('UPDATE evidence SET fetched_at=? WHERE url=?', (time.time()-age, source))
    async def forbidden(*_):
        pytest.fail('Stale ownership must never reach verification provider')
    monkeypatch.setattr('outreach.providers.verify_email', forbidden)
    assert contact_candidates(db, prepared['lead_id']) == []
    with pytest.raises(ValueError, match='current official-source'):
        await verify_contact(db, settings, cid)


async def test_complete_expired_profile_identity_cannot_probe(db, settings, monkeypatch):
    from outreach.profiles import add_profile_lead
    mock_profile(monkeypatch)
    lid = add_profile_lead(db, 'Fictional Bright Studio', PROFILE, 'A', 'UK')
    await research_lead(db, settings, lid)
    review_lead(db, lid, review_value(db, lid))
    cid = add_contact(db, lid, 'bright-fixture@gmail.com', PROFILE,
                      ownership_notes='Fictional business profile explicitly publishes its own business inbox.')
    db.execute('UPDATE evidence SET fetched_at=?', (time.time()-31*86400,))
    db.execute('UPDATE crawls SET created_at=?', (time.time()-32*86400,))
    async def forbidden(*_):
        pytest.fail('Expired profile must never reach verification provider')
    monkeypatch.setattr('outreach.providers.verify_email', forbidden)
    with pytest.raises(ValueError, match='current business profile'):
        await verify_contact(db, settings, cid)


def test_complete_call_requires_dated_next_action(db, settings, prepared):
    client = TestClient(create_app(settings), headers={'Authorization': 'Bearer '+settings.api_token})
    lid = prepared['lead_id']
    client.post(f'/api/leads/{lid}/activity', json={'channel': 'meeting', 'kind': 'reply', 'note': 'Fictional client agreed a discovery discussion.'})
    value = sales_payload(client, lid, 'call_booked')
    value.pop('next_action_at')
    response = client.put(f'/api/leads/{lid}/sales', json=value)
    assert response.status_code == 400 and 'next-action' in response.json()['detail']


def test_complete_approved_proposal_context_change_visible_on_map(db, settings, prepared):
    client = TestClient(create_app(settings), headers={'Authorization': 'Bearer '+settings.api_token})
    lid = prepared['lead_id']
    client.post(f'/api/leads/{lid}/activity', json={'channel': 'meeting', 'kind': 'reply', 'note': 'Fictional client agreed the pilot need.'})
    client.put(f'/api/leads/{lid}/sales', json=sales_payload(client, lid))
    pid = client.post(f'/api/leads/{lid}/proposals', json=proposal_payload()).json()['id']
    client.post(f'/api/proposals/{pid}/approve', json={'reviewed_scope_and_terms': True})
    assert mapped(db, settings, lid)['V']['state'] == 'complete'
    value = sales_payload(client, lid)
    value['confirmed_problem'] = 'Client changed the requirement to a support FAQ pilot.'
    client.put(f'/api/leads/{lid}/sales', json=value)
    assert mapped(db, settings, lid)['V']['state'] == 'review'


def test_complete_historical_sales_without_baseline_cannot_complete_call_node(db, settings, prepared):
    from outreach.sales import QUALIFICATION
    lid = prepared['lead_id']
    value = {**{key: 'Fictional confirmed '+key for key in QUALIFICATION}, 'call_at': time.time(),
             'next_action_at': time.time()+86400}
    db.execute('INSERT INTO activities(lead_id,channel,kind,note,happened_at,created_at) VALUES(?,?,?,?,?,?)',
               (lid, 'meeting', 'reply', 'Fictional prior conversation', time.time(), time.time()))
    db.execute('INSERT INTO sales(lead_id,stage,details,updated_at) VALUES(?,?,?,?)', (lid, 'call_booked', json.dumps(value), time.time()))
    assert mapped(db, settings, lid)['U']['state'] == 'review'


@pytest.mark.parametrize('campaign,profile', [('A', False), ('B', False), ('A', True), ('B', True)])
async def test_connected_discovery_to_client_outcome(db, settings, safe_result, monkeypatch, tls, campaign, profile):  # noqa: F811 -- pytest fixture injection
    """Real queue, crawler, gates, API and TLS mail; published sites/search/Reacher are fixtures."""
    import email
    from email.message import EmailMessage
    from email.policy import default
    from outreach.worker import execute_job
    from outreach.web import PublicWeb
    from outreach.mail import send_one, smtp_send, poll_inbox
    from outreach.sales import finish_task

    settings.discovery_platforms = 'facebook.com' if profile else ''
    settings.discovery_query_delay_seconds = .1
    settings.crawl_render_mode = 'never'
    settings.auto_visual_audit = False
    settings.crawl_delay_seconds = .1
    mock_profile(monkeypatch)
    async def search(*_, **__):
        return [{'url': PROFILE if profile else 'https://bright-demo.com/',
                 'title': 'Fictional Bright Studio', 'snippet': 'UK consulting services'}]
    monkeypatch.setattr('outreach.providers.discover', search)
    async def public_page(self, url, expected_domain=None):
        if url.endswith('robots.txt'):
            return url, 'User-agent: *\nAllow: /', 200
        if 'sitemap' in url:
            return url, '', 404
        return url, ('<title>Fictional Bright Studio</title><p>UK consulting services. '
                     'Call us to arrange a consultation. We sell our own handmade products through business messages.</p>'
                     '<a href="mailto:alex@bright-demo.com">Business contact</a>'), 200
    monkeypatch.setattr(PublicWeb, 'get', public_page)
    queried = []
    async def reacher(_, address, *, before_probe=None):
        if before_probe:
            before_probe()
        queried.append(address)
        return 'safe', {**safe_result, 'input': address}
    monkeypatch.setattr('outreach.providers.verify_email', reacher)
    async def run(kind):
        job = db.claim({kind})
        assert job is not None
        await execute_job(db, settings, job)
        row = db.one('SELECT state,error FROM jobs WHERE id=?', (job['id'],))
        assert row['state'] == 'done', row
    db.enqueue('discover', {'query': 'consulting', 'campaign': campaign, 'country_hint': 'UK', 'limit': 1})
    await run('discover')
    await run('research')
    assert db.one('SELECT COUNT(*) n FROM leads')['n'] == 1
    lid = db.one('SELECT id FROM leads')['id']
    if profile:
        assert db.all('SELECT id FROM contacts') == [] and queried == []
    value = review_value(db, lid, campaign)
    review_lead(db, lid, value)
    if profile:
        cid = add_contact(db, lid, 'bright-fixture@gmail.com', PROFILE, 'Alex', 'Founder',
                          'Fictional business publishes and owns this current inquiry inbox.')
        db.enqueue('verify', {'contact_id': cid})
    else:
        cid = db.one('SELECT id FROM contacts')['id']
        db.execute("UPDATE contacts SET name='Alex',role='Founder' WHERE id=?", (cid,))
    await run('verify')
    assert len(queried) == 1
    assert mapped(db, settings, lid)['F']['state'] == 'complete'
    create_drafts(db, settings, cid)
    approve(db, settings, cid, 'Reviewed fictional UK corporate eligibility and opt-out route.',
            'Founder confirmed as the relevant owner of the proposed pilot.')
    before = mapped(db, settings, lid)
    assert all(before[n]['state'] == 'complete' for n in ['E', 'F', 'G', 'I', 'J', 'K', 'AA' if campaign == 'A' else 'BB'])
    db.set('paused', 'false')
    db.set('imap_caught_up', 'true')
    db.set('imap_last_success', time.time())
    # Calendar behavior is separately tested across DST/weekends; transport here uses current wall time.
    monkeypatch.setattr('outreach.mail.eligible_now', lambda *_: True)
    with mail_server(tls) as smtp:
        configure_smtp(settings, smtp, 'starttls')
        assert send_one(db, settings, time.time(), smtp_send) == 'sent'
        assert len(smtp.messages) == 1
        delivered = email.message_from_bytes(smtp.messages[0], policy=default)
    reply = EmailMessage()
    reply['From'] = queried[0]
    reply['To'] = settings.sender_email
    reply['In-Reply-To'] = delivered['Message-ID']
    reply['Subject'] = 'Re: Fictional pilot'
    reply.set_content('Yes, please send the outline and discuss the pilot scope.')
    with mail_server(tls, protocol='imap', inbound=reply.as_bytes()) as imap:
        settings.imap_host, settings.imap_port = imap.server_address
        assert poll_inbox(db, settings) and poll_inbox(db, settings)
    assert db.one("SELECT COUNT(*) n FROM events WHERE kind='reply'")['n'] == 1
    assert db.one("SELECT COUNT(*) n FROM messages WHERE state='queued'")['n'] == 0
    assert db.one('SELECT status FROM contacts WHERE id=?', (cid,))['status'] == 'replied'
    later = time.time()+1000
    db.set('imap_last_success', later)
    assert send_one(db, settings, later, smtp_send) == 'idle'
    aid = create(db, lid, {'kind': 'concept', 'title': 'Fictional sourced homepage concept',
                           'headline': 'Explore our services and products', 'intro': 'An illustrative source-backed page direction for discussion.',
                           'primary_action': 'Request a conversation'})
    action(db, aid, 'approve')
    action(db, aid, 'sent', 'Isolated fictional client delivery reference')
    for task in db.all("SELECT id FROM tasks WHERE state='open'"):
        finish_task(db, task['id'], 'done', 'Fictional requested concept reviewed and fulfilled in isolated test.')
    client = TestClient(create_app(settings), headers={'Authorization': 'Bearer '+settings.api_token})
    for stage in ['qualified', 'call_booked']:
        response = client.put(f'/api/leads/{lid}/sales', json=sales_payload(client, lid, stage))
        assert response.status_code == 200, response.text
    pid = client.post(f'/api/leads/{lid}/proposals', json=proposal_payload()).json()['id']
    assert client.post(f'/api/proposals/{pid}/approve', json={'reviewed_scope_and_terms': True}).status_code == 200
    assert client.post(f'/api/proposals/{pid}/sent', json={'reference': 'Fictional approved proposal delivered in fixture', 'actually_delivered': True}).status_code == 200
    for stage in ['proposal', 'won', 'delivery', 'completed']:
        payload = {**sales_payload(client, lid, stage), 'proposal_id': pid,
                   'agreement_reference': 'Fictional signed agreement reference', 'payment_reference': 'Fictional initial payment reference',
                   'acceptance_reference': 'Fictional client acceptance reference', 'outcome_notes': 'Inconclusive fixture outcome; no measured sales uplift.'}
        response = client.put(f'/api/leads/{lid}/sales', json=payload)
        assert response.status_code == 200, response.text
    final = mapped(db, settings, lid)
    assert len(final) == 35 and all(final[key]['state'] == 'complete' for key in 'ORSTUVWXYZ')
    report = client.get('/api/sales/report').json()
    assert report['recorded_contract_value'] == {'GBP': '1200.50'}
    assert db.one("SELECT COUNT(*) n FROM messages WHERE state='sent'")['n'] == 1


@pytest.mark.parametrize('age', [72*3600, -120])
def test_complete_stale_safe_verdict_routes_to_hold(db, settings, active, age):
    db.execute('UPDATE contacts SET verified_at=?', (time.time()-age,))
    nodes = mapped(db, settings, active['lead_id'])
    assert nodes['F']['state'] == 'blocked'
    assert nodes['H']['state'] == 'blocked'
