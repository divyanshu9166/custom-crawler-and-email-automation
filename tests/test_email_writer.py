"""Controlled provider contracts; no live model or human-quality claim."""
import copy
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from outreach import email_writer
from outreach.app import create_app
from outreach.campaigns import approve, create_drafts
from outreach.config import Settings
from outreach.workflow import snapshot

# Capture the real implementation before conftest installs controlled workflow copy.
REAL_GENERATE = email_writer.generate_sequence
REAL_CLIENT = httpx.Client


def inputs(db, prepared):
    lead = db.one('SELECT * FROM leads WHERE id=?', (prepared['lead_id'],))
    contact = db.one('SELECT * FROM contacts WHERE id=?', (prepared['contact_id'],))
    finding = json.loads(lead['findings'])[0]
    sources = db.all('SELECT * FROM evidence WHERE lead_id=?', (lead['id'],))
    return lead, contact, finding, sources


def output(lead, evidence):
    # Fictional provider content for protocol/state tests, deliberately not templates.
    bodies = [
        f"{lead['company']} invites people to contact you for a consultation. Could explaining what the first conversation covers make that next step clearer? Would a short page outline be useful?",
        'Following up on the consultation invitation: a brief example of the questions you cover might help a visitor decide whether to enquire. Would that be a useful starting point?',
        'The consultation invitation could sit beside a short explanation of what happens after someone contacts you. Could we start by reviewing that one section together?',
        'I will leave the consultation-page idea with you. If that becomes a priority, I would be happy to discuss what a suitable next step could look like.'
    ]
    return {'messages': [{'step': i, 'subject': f'Consultation page idea {i+1}', 'body': body,
                          'support': [{'evidence_id': evidence[0]['id'], 'quote': 'Contact us for a consultation.'}]}
                         for i, body in enumerate(bodies)]}


def provider(monkeypatch, settings, handler):
    settings.draft_api_key = 'fictional-writer-secret'
    settings.draft_model = 'fictional-research-model'
    monkeypatch.setattr(email_writer, 'generate_sequence', REAL_GENERATE)
    monkeypatch.setattr(email_writer.httpx, 'Client',
                        lambda **kw: REAL_CLIENT(transport=httpx.MockTransport(handler), **kw))


def response(value, finish='stop'):
    return httpx.Response(200, json={'choices': [{'finish_reason': finish, 'message': {'content': json.dumps(value)}}]})


def test_real_writer_uses_reviewed_research_and_saves_unactivated_ai_provenance(db, settings, prepared, monkeypatch):
    lead, contact, finding, sources = inputs(db, prepared)
    calls = []
    def handle(request):
        calls.append(request)
        packet = json.loads(request.content)
        assert request.url == 'https://integrate.api.nvidia.com/v1/chat/completions'
        assert request.headers['authorization'] == 'Bearer fictional-writer-secret'
        assert packet['model'] == 'fictional-research-model'
        context = json.loads(packet['messages'][1]['content'])
        assert context['business']['company'] == lead['company']
        assert context['reviewed_finding']['observation'] == finding['observation']
        assert context['sources'][0]['sha256'] == sources[0]['sha256']
        assert contact['email'] not in request.content.decode()
        assert 'Alex' not in request.content.decode()
        return response(output(lead, sources))
    provider(monkeypatch, settings, handle)
    create_drafts(db, settings, contact['id'])
    assert len(calls) == 1
    messages = db.all('SELECT * FROM messages WHERE contact_id=? ORDER BY step', (contact['id'],))
    assert len(messages) == 4 and all(m['state'] == 'draft' and m['due_at'] is None for m in messages)
    assert len({m['body'] for m in messages}) == 4
    assert messages[0]['body'].startswith('Hi Alex,\n\nBright Demo')
    saved = json.loads(db.one("SELECT detail FROM events WHERE kind='drafts_created' ORDER BY id DESC LIMIT 1")['detail'])
    assert saved['model'] == settings.draft_model and saved['method'] == 'research_ai'
    assert len(saved['input_sha256']) == 64 and saved['source_ids'] == [prepared['evidence_id']]
    assert len(saved['support']) == 4
    email_writer.assert_ai_origin(db, contact['id'])
    client = TestClient(create_app(settings), headers={'Authorization': 'Bearer '+settings.api_token})
    detail = client.get(f"/api/leads/{lead['id']}").json()
    assert detail['contacts'][0]['ai_drafts'] and detail['email_writer']['configured']
    assert settings.draft_api_key not in json.dumps(detail)


@pytest.mark.parametrize('base,model,effort', [
    ('https://integrate.api.nvidia.com/v1', 'nvidia/nemotron-3-ultra-550b-a55b', 'none'),
    ('https://integrate.api.nvidia.com/v1/', 'nvidia/nemotron-3-ultra-550b-a55b', 'none'),
    ('https://integrate.api.nvidia.com/v1', 'another-model', None),
    ('https://another-provider.example/v1', 'nvidia/nemotron-3-ultra-550b-a55b', None),
])
def test_nvidia_ultra_uses_final_output_budget_without_changing_other_providers(db, settings, prepared, monkeypatch, base, model, effort):
    lead, contact, _, sources = inputs(db, prepared)
    def handle(request):
        packet = json.loads(request.content)
        assert request.url == base.rstrip('/')+'/chat/completions'
        assert packet.get('reasoning_effort') == effort
        assert packet['stream'] is False and packet['max_tokens'] == 3000
        assert packet['model'] == model
        assert contact['email'] not in request.content.decode()
        return response(output(lead, sources))
    provider(monkeypatch, settings, handle)
    settings.draft_api_url, settings.draft_model = base, model
    create_drafts(db, settings, contact['id'])
    assert all(m['state'] == 'draft' and m['due_at'] is None for m in db.all('SELECT * FROM messages'))


@pytest.mark.parametrize('problem', ['key', 'model'])
def test_missing_writer_configuration_preserves_drafts_no_fallback(db, settings, prepared, monkeypatch, problem):
    settings.draft_api_key = '' if problem == 'key' else 'fictional-key'
    settings.draft_model = '' if problem == 'model' else 'fictional-model'
    monkeypatch.setattr(email_writer, 'generate_sequence', REAL_GENERATE)
    monkeypatch.setattr(email_writer.httpx, 'Client', lambda **_: pytest.fail('No configured writer: no network'))
    before = db.all('SELECT * FROM messages')
    with pytest.raises(ValueError, match='No template fallback'):
        create_drafts(db, settings, prepared['contact_id'])
    assert db.all('SELECT * FROM messages') == before


@pytest.mark.parametrize('problem', ['http', 'invalid_json', 'truncated', 'missing_choices', 'null_choice', 'timeout', 'oversized'])
def test_provider_failures_preserve_existing_drafts(db, settings, prepared, monkeypatch, problem):
    lead, _, _, sources = inputs(db, prepared)
    before = db.all('SELECT * FROM messages')
    events = db.all('SELECT * FROM events')
    def handle(request):
        if problem == 'http':
            return httpx.Response(429, text='fictional-writer-secret echoed')
        if problem == 'invalid_json':
            return httpx.Response(200, text='not JSON')
        if problem == 'truncated':
            return response(output(lead, sources), finish='length')
        if problem == 'missing_choices':
            return httpx.Response(200, json={'choices': []})
        if problem == 'null_choice':
            return httpx.Response(200, json={'choices': [None]})
        if problem == 'timeout':
            raise httpx.ReadTimeout('Secret echoed', request=request)
        return httpx.Response(200, text='x'*200001)
    provider(monkeypatch, settings, handle)
    with pytest.raises(ValueError) as exc:
        create_drafts(db, settings, prepared['contact_id'])
    assert 'fictional-writer-secret' not in str(exc.value)
    assert db.all('SELECT * FROM messages') == before and db.all('SELECT * FROM events') == events


@pytest.mark.parametrize('problem', ['missing_touch', 'duplicate_step', 'bool_step', 'duplicate_copy',
                                    'invented_quote', 'foreign_source', 'header', 'fake_reply',
                                    'placeholder', 'promise', 'completed_asset', 'company_omitted',
                                    'missing_question', 'invented_checklist'])
def test_invalid_ai_output_rejected(problem, db, prepared):
    lead, contact, _, sources = inputs(db, prepared)
    value = output(lead, sources)
    first = value['messages'][0]
    if problem == 'missing_touch':
        value['messages'].pop()
    elif problem == 'duplicate_step':
        value['messages'][1]['step'] = 0
    elif problem == 'bool_step':
        first['step'] = False
    elif problem == 'duplicate_copy':
        value['messages'][1]['body'] = first['body']
    elif problem == 'invented_quote':
        first['support'][0]['quote'] = 'We lose customers because the booking process fails.'
    elif problem == 'foreign_source':
        first['support'][0]['evidence_id'] = 999999
    elif problem == 'header':
        first['subject'] = 'Idea\r\nBcc: stranger@example.com'
    elif problem == 'fake_reply':
        first['subject'] = 'Re: Prior discussion'
    elif problem == 'placeholder':
        first['body'] += ' {{company_name}}'
    elif problem == 'promise':
        first['body'] += ' This will double your sales.'
    elif problem == 'completed_asset':
        first['body'] += ' I have prepared an audit for you.'
    elif problem == 'missing_question':
        first['body'] = first['body'].rstrip('?') + '.'
    elif problem == 'invented_checklist':
        first['body'] = lead['company']+' uses a long checklist in your current quote form. Could we review it?'
    else:
        first['body'] = first['body'].replace(lead['company'], 'Your business')
    with pytest.raises(ValueError):
        email_writer.validate_output(value, lead, contact, sources)


@pytest.mark.parametrize('outcome', ['corrected', 'still_invalid', 'network_error', 'context_changed'])
def test_writer_corrects_once_without_weakening_identity_or_preservation(db, settings, prepared, monkeypatch, outcome):
    lead, _, _, sources = inputs(db, prepared)
    before = db.all('SELECT * FROM messages')
    calls = []
    def handle(request):
        packet = json.loads(request.content)
        calls.append(json.loads(packet['messages'][1]['content']))
        if outcome == 'network_error':
            raise httpx.ReadTimeout('private provider detail', request=request)
        value = output(lead, sources)
        if len(calls) == 1 or outcome == 'still_invalid':
            value['messages'][0]['body'] = value['messages'][0]['body'].replace(lead['company'], 'Your business')
        if outcome == 'context_changed':
            db.execute("UPDATE messages SET subject='Keep human edit' WHERE step=0")
        return response(value)
    provider(monkeypatch, settings, handle)
    if outcome == 'corrected':
        create_drafts(db, settings, prepared['contact_id'])
        assert len(calls) == 2
        assert 'business identity' in calls[1]['validation_feedback']['error']
        email_writer.assert_ai_origin(db, prepared['contact_id'])
        assert all(m['state'] == 'draft' and m['due_at'] is None for m in db.all('SELECT * FROM messages'))
    else:
        with pytest.raises(ValueError):
            create_drafts(db, settings, prepared['contact_id'])
        if outcome == 'context_changed':
            before[0]['subject'] = 'Keep human edit'
        assert db.all('SELECT * FROM messages') == before
        assert len(calls) == (2 if outcome == 'still_invalid' else 1)


@pytest.mark.parametrize('change', ['source', 'contact', 'lead', 'draft', 'suppression', 'model'])
def test_research_or_context_change_during_provider_call_discards_output(db, settings, prepared, monkeypatch, change):
    lead, _, _, sources = inputs(db, prepared)
    before = copy.deepcopy(db.all('SELECT * FROM messages'))
    def handle(_):
        if change == 'source':
            db.execute("UPDATE evidence SET sha256='new-hash'")
        elif change == 'contact':
            db.execute("UPDATE contacts SET name='Different buyer'")
        elif change == 'lead':
            db.execute("UPDATE leads SET fit_notes='Changed business research'")
        elif change == 'draft':
            db.execute("UPDATE messages SET subject='Human edit wins' WHERE step=0")
        elif change == 'suppression':
            db.execute("INSERT INTO suppression(email,reason,created_at) VALUES(?,?,?)", ('alex@bright-demo.com', 'opt out', 1))
        else:
            settings.draft_model = 'changed-model'
        return response(output(lead, sources))
    provider(monkeypatch, settings, handle)
    with pytest.raises(ValueError):
        create_drafts(db, settings, prepared['contact_id'])
    after = db.all('SELECT * FROM messages')
    if change == 'draft':
        before[0]['subject'] = 'Human edit wins'
    assert before == after
    assert db.one("SELECT COUNT(*) n FROM events WHERE kind='drafts_created'")['n'] == 1


def test_pre_request_guard_prevents_dispatch_on_context_change(db, settings, prepared, monkeypatch):
    lead, contact, finding, sources = inputs(db, prepared)
    provider(monkeypatch, settings, lambda _: pytest.fail('Guard must run before dispatch'))
    def guard():
        raise ValueError('Research changed')
    with pytest.raises(ValueError, match='Research changed'):
        REAL_GENERATE(settings, lead, contact, finding, sources, before_request=guard)


@pytest.mark.parametrize('url', ['http://provider.example/v1', 'https://', 'https://user:secret@provider.example/v1',
                               'https://provider.example/v1?secret=private', 'https://provider.example/v1#secret'])
def test_writer_rejects_unsafe_endpoint_before_request(url):
    with pytest.raises(ValueError):
        email_writer.validate_endpoint(url)


def test_legacy_template_sequences_cannot_be_approved_and_are_labelled(db, settings, prepared):
    db.execute("DELETE FROM events WHERE kind='drafts_created'")
    with pytest.raises(ValueError, match='Legacy template'):
        approve(db, settings, prepared['contact_id'], 'Reviewed UK corporate outreach eligibility', 'Relevant founder contact')
    overview = {n['id']: n for n in snapshot(db, settings, prepared['lead_id'])['nodes']}
    assert overview['drafts']['state'] == 'blocked' and overview['approval']['state'] == 'blocked'
    client = TestClient(create_app(settings), headers={'Authorization': 'Bearer '+settings.api_token})
    assert not client.get(f"/api/leads/{prepared['lead_id']}").json()['contacts'][0]['ai_drafts']


def test_writer_settings_protected_secret_private_and_persisted(settings):
    original = settings.model_dump()
    app = create_app(settings)
    client = TestClient(app)
    assert client.put('/api/settings/writer', json={'draft_model': 'fictional'}).status_code == 401
    client.headers['Authorization'] = 'Bearer '+settings.api_token
    body = {'draft_api_url': 'https://writer.fixture.example/v1', 'draft_model': 'fictional-model',
            'draft_api_key': 'fictional-private-writer-key', 'draft_timeout_seconds': 30}
    assert client.put('/api/settings/writer', json=body).status_code == 200
    assert app.state.db.get('paused') == 'true'
    for path in ['/api/settings', '/api/events', '/api/workflow']:
        assert body['draft_api_key'] not in client.get(path).text
    assert client.get('/api/settings').json()['draft_api_key_configured']
    assert client.put('/api/settings/writer', json={'draft_api_key': ''}).status_code == 200
    assert settings.draft_api_key == body['draft_api_key']
    restarted = Settings(_env_file=None, **original)
    create_app(restarted)
    assert restarted.draft_api_key == body['draft_api_key'] and restarted.draft_model == body['draft_model']
    assert client.put('/api/settings/writer', json={'clear_draft_api_key': True}).status_code == 200
    assert not settings.draft_api_key
    assert client.put('/api/settings/writer', json={'sending_enabled': True}).status_code == 422
    assert client.put('/api/settings/writer', json={'draft_api_url': 'http://external.example/v1'}).status_code == 400
