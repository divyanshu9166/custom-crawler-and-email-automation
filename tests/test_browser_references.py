import json
import time

import pytest
from fastapi.testclient import TestClient

from outreach.app import create_app
from outreach.browser_references import save_reference


def reference(**changes):
    return dict(company='Bright Demo', source_url='https://linkedin.com/company/bright-demo/about/',
                website='https://bright-demo.com/contact', campaign='A', country_hint='UK',
                observed_at=time.time(), observation='The business About page links its website.',
                public_business_confirmed=True, **changes)


def test_browser_reference_cannot_create_capture_contact_or_publication_proof(db):
    value = reference()
    result = save_reference(db, **value)
    lead = db.one('SELECT * FROM leads WHERE id=?', (result['id'],))
    assert lead['status'] == 'new' and lead['country'] == ''
    assert lead['website'] == 'https://bright-demo.com/'
    event = json.loads(db.one("SELECT detail FROM events WHERE kind='browser_business_reference'")['detail'])
    assert event['source_url'] == value['source_url']
    assert event['server_profile_fetched'] is False
    assert event['identity_verified'] is False and event['contact_publication_proof'] is False
    job = db.one('SELECT * FROM jobs WHERE id=?', (result['job_id'],))
    assert job['kind'] == 'research'
    assert json.loads(job['payload'])['seed_urls'] == [value['website']]
    for table in ('evidence', 'contacts', 'messages'):
        assert db.one(f'SELECT COUNT(*) n FROM {table}')['n'] == 0
    assert save_reference(db, **value) == result
    assert db.one('SELECT COUNT(*) n FROM jobs')['n'] == 1
    assert db.one('SELECT COUNT(*) n FROM events')['n'] == 1


def test_existing_qualified_company_and_approved_messages_are_preserved(db, prepared):
    before = db.one('SELECT * FROM leads WHERE id=?', (prepared['lead_id'],))
    messages = db.all('SELECT * FROM messages')
    result = save_reference(db, **reference())
    assert result['id'] == prepared['lead_id'] and result['job_id'] is None
    assert db.one('SELECT * FROM leads WHERE id=?', (prepared['lead_id'],)) == before
    assert db.all('SELECT * FROM messages') == messages
    assert not db.all('SELECT * FROM jobs')


@pytest.mark.parametrize('key,value', [
    ('source_url', 'https://linkedin.com/in/private-person'),
    ('source_url', 'https://notlinkedin.com/company/bright-demo'),
    ('source_url', 'https://linkedin.com/company/bright-demo/about?token=secret'),
    ('source_url', 'https://x.com/bright/status/123'),
    ('website', 'https://bright-demo.com/account'),
    ('website', 'https://linkedin.com/company/bright-demo'),
    ('website', 'https://127.0.0.1/contact'),
    ('observed_at', float('nan')),
    ('observed_at', time.time()-31*86400),
    ('observed_at', time.time()+3600),
    ('public_business_confirmed', False),
])
def test_rejected_reference_leaves_no_partial_rows(db, key, value):
    data = reference()
    data[key] = value
    with pytest.raises(ValueError):
        save_reference(db, **data)
    assert not db.all('SELECT * FROM leads') and not db.all('SELECT * FROM events')
    assert not db.all('SELECT * FROM jobs')


def test_api_requires_authentication_and_rejects_private_payload_fields(settings):
    client = TestClient(create_app(settings))
    assert client.post('/api/browser-references', json=reference()).status_code == 401
    client.headers['Authorization'] = 'Bearer '+settings.api_token
    value = reference()
    assert client.post('/api/browser-references', json={**value, 'cookies': 'do not collect'}).status_code == 422
    result = client.post('/api/browser-references', json=value)
    assert result.status_code == 200 and result.json()['server_profile_fetched'] is False
