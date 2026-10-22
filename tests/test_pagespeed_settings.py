import json
import os

from fastapi.testclient import TestClient

from outreach.app import create_app
from outreach.config import Settings
from outreach.preferences import Preferences


KEY = 'fictional-pagespeed-secret-12345'


def client_for(settings):
    app = create_app(settings)
    client = TestClient(app, base_url=settings.public_url,
                        headers={'Authorization': 'Bearer '+settings.api_token})
    return app, client


def test_pagespeed_secret_persists_without_exposure_and_blank_preserves(settings):
    original = settings.model_dump()
    app, client = client_for(settings)
    response = client.put('/api/settings/pagespeed', json={'pagespeed_api_key': KEY})
    assert response.status_code == 200 and response.json()['pagespeed_api_key_configured']
    assert settings.pagespeed_api_key == KEY
    assert app.state.db.get('paused') == 'true'
    assert not app.state.db.all("SELECT id FROM jobs WHERE kind='performance'")
    for path in ['/api/settings', '/api/events', '/api/status', '/api/workflow']:
        assert KEY not in client.get(path).text
    assert 'pagespeed_api_key' not in response.json()
    assert client.put('/api/settings/pagespeed', json={'pagespeed_api_key': ''}).status_code == 200
    assert settings.pagespeed_api_key == KEY
    restarted = Settings(_env_file=None, **original)
    Preferences(restarted)
    assert restarted.pagespeed_api_key == KEY
    stored = settings.data_dir/'workspace-settings.json'
    if os.name != 'nt':
        assert stored.stat().st_mode & 0o777 == 0o600
    assert client.put('/api/settings/pagespeed', json={'pagespeed_api_key': 'replacement-fixture'}).status_code == 200
    assert settings.pagespeed_api_key == 'replacement-fixture'
    assert client.put('/api/settings/pagespeed', json={'clear_pagespeed_api_key': True}).status_code == 200
    assert not settings.pagespeed_api_key
    assert not client.get('/api/settings').json()['pagespeed_api_key_configured']


def test_pagespeed_protected_and_validation_never_echoes_secret(settings):
    _, client = client_for(settings)
    anonymous = TestClient(create_app(settings))
    assert anonymous.put('/api/settings/pagespeed', json={'pagespeed_api_key': KEY}).status_code == 401
    for value in [KEY*100, KEY+' invalid whitespace']:
        response = client.put('/api/settings/pagespeed', json={'pagespeed_api_key': value})
        assert response.status_code == 422 and KEY not in response.text
    response = client.put('/api/settings/pagespeed', json={'pagespeed_api_key':KEY,'clear_pagespeed_api_key':True})
    assert response.status_code == 400 and KEY not in response.text
    assert client.put('/api/settings/pagespeed', json={'sending_enabled':True}).status_code == 422
    assert not settings.pagespeed_api_key


def test_managed_pagespeed_removal_survives_environment_default(settings):
    settings.pagespeed_api_key = 'environment-fixture-key'
    original = settings.model_dump()
    _, client = client_for(settings)
    assert client.get('/api/settings').json()['pagespeed_api_key_configured']
    client.put('/api/settings/pagespeed', json={'clear_pagespeed_api_key':True})
    restarted = Settings(_env_file=None, **original)
    Preferences(restarted)
    assert restarted.pagespeed_api_key == ''
    assert json.loads((settings.data_dir/'workspace-settings.json').read_text())['pagespeed_api_key'] == ''


def test_pagespeed_cookie_write_requires_same_origin(settings):
    client = TestClient(create_app(settings), base_url=settings.public_url)
    origin = {'Origin':settings.public_url}
    assert client.post('/api/login',json={'username':settings.admin_user,'password':settings.admin_password},headers=origin).status_code==200
    assert client.put('/api/settings/pagespeed',json={'pagespeed_api_key':KEY}).status_code==403
    assert client.put('/api/settings/pagespeed',json={'pagespeed_api_key':KEY},headers=origin).status_code==200
