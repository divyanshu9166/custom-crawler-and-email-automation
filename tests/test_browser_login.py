import pytest
from fastapi.testclient import TestClient

from outreach.app import create_app
from outreach.auth import COOKIE, issue_session, valid_session


@pytest.mark.parametrize('password', ['x', 'small', 'मेरी पसंद'])
def test_short_configured_password_can_sign_in(settings, password):
    settings.admin_password = password
    client = TestClient(create_app(settings), base_url=settings.public_url)
    origin = {'Origin': settings.public_url}
    assert client.get('/health').json() == {'status': 'ok'}
    assert client.post('/api/login', json={
        'username': settings.admin_user, 'password': password + 'wrong',
    }, headers=origin).status_code == 401
    assert client.post('/api/login', json={
        'username': settings.admin_user, 'password': password,
    }, headers=origin).status_code == 200
    assert client.get('/api/status').status_code == 200


def test_missing_password_and_short_api_token_have_specific_startup_errors(settings):
    settings.admin_password = ''
    with pytest.raises(RuntimeError, match='nonempty ADMIN_PASSWORD'):
        create_app(settings)
    settings.admin_password = 'x'
    settings.api_token = 'too-short'
    with pytest.raises(RuntimeError, match='API_TOKEN with at least 32 characters'):
        create_app(settings)


def test_login_page_and_cookie_auth_with_origin_guards(settings):
    client = TestClient(create_app(settings), base_url=settings.public_url)
    assert 'Sign in to your workspace' in client.get('/').text
    assert client.get('/api/status').status_code == 401
    assert client.get('/static/login.js').status_code == 200
    body = {'username': settings.admin_user, 'password': settings.admin_password}
    assert client.post('/api/login', json=body).status_code == 403
    response = client.post('/api/login', json=body, headers={'Origin': settings.public_url})
    assert response.status_code == 200
    assert 'HttpOnly' in response.headers['set-cookie'] and 'Secure' in response.headers['set-cookie']
    assert client.get('/api/status').status_code == 200
    assert 'id="pipeline"' in client.get('/').text
    assert client.post('/api/pause').status_code == 403
    assert client.post('/api/pause', headers={'Origin': settings.public_url}).status_code == 200
    assert client.post('/api/logout', headers={'Origin': settings.public_url}).status_code == 200
    assert client.get('/api/status').status_code == 401


def test_invalid_credentials_throttle_and_tampered_sessions(settings, monkeypatch):
    client = TestClient(create_app(settings), base_url=settings.public_url)
    body = {'username': settings.admin_user, 'password': 'incorrect'}
    for _ in range(10):
        assert client.post('/api/login', json=body, headers={'Origin': settings.public_url}).status_code == 401
    assert client.post('/api/login', json=body, headers={'Origin': settings.public_url}).status_code == 429
    value = issue_session(settings.api_token)
    assert valid_session(value, settings.api_token)
    assert not valid_session(value+'x', settings.api_token)
    client.cookies.set(COOKIE, value+'x')
    assert client.get('/api/status').status_code == 401
    monkeypatch.setattr('outreach.auth.time.time', lambda: 99999999999)
    assert not valid_session(value, settings.api_token)


@pytest.mark.parametrize('token', [None, '', 'garbage', '1.x.y'])
def test_malformed_session_is_not_authentication(token):
    assert not valid_session(token, 'secret')
