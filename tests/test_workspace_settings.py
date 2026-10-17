from threading import Event, Thread

from fastapi.testclient import TestClient

from outreach.app import create_app
from outreach.auth import COOKIE
from outreach.config import Settings


def client_for(settings):
    client = TestClient(create_app(settings), base_url=settings.public_url)
    client.headers['Authorization'] = 'Bearer ' + settings.api_token
    return client


def test_settings_protected_and_passwords_never_returned_or_logged(settings):
    app = create_app(settings)
    client = TestClient(app)
    assert client.get('/api/settings').status_code == 401
    assert client.put('/api/settings/mail', json={'sender_company': 'Fictional team'}).status_code == 401
    client.headers['Authorization'] = 'Bearer ' + settings.api_token
    body = {'smtp_password': 'fictional-smtp-secret-456', 'imap_password': 'fictional-imap-secret-456', 'sender_company': 'Fictional team'}
    response = client.put('/api/settings/mail', json=body)
    assert response.status_code == 200
    assert response.json()['smtp_password_configured'] and response.json()['imap_password_configured']
    for url in ['/api/settings', '/api/events', '/api/status', '/api/workflow']:
        output = client.get(url).text
        assert body['smtp_password'] not in output and body['imap_password'] not in output
        assert settings.api_token not in output
    assert app.state.db.get('paused') == 'true'
    assert app.state.db.get('imap_caught_up') == 'false'
    assert settings.sending_enabled  # Saving never changes the deployment's enabling flag.
    client.put('/api/settings/mail', json={'smtp_password': '', 'imap_password': ''})
    assert settings.smtp_password == body['smtp_password'] and settings.imap_password == body['imap_password']
    client.put('/api/settings/mail', json={'clear_smtp_password': True})
    assert settings.smtp_password == ''


def test_mail_settings_persist_on_restart_and_forbid_enabling_or_login_fields(settings):
    original = settings.model_dump()
    client = client_for(settings)
    assert client.put('/api/settings/mail', json={'sender_company': 'Saved team', 'smtp_host': 'smtp.fixture.example', 'smtp_password': 'private-fixture-secret'}).status_code == 200
    restarted = Settings(_env_file=None, **original)
    saved = client_for(restarted).get('/api/settings').json()
    assert saved['sender_company'] == 'Saved team' and restarted.smtp_password == 'private-fixture-secret'
    assert client.put('/api/settings/mail', json={'sending_enabled': True}).status_code == 422
    assert client.put('/api/settings/mail', json={'admin_password': 'unapproved'}).status_code == 422
    assert client.put('/api/settings/mail', json={'smtp_security': 'plain'}).status_code == 422
    assert client.put('/api/settings/mail', json={'sender_email': 'invalid-email'}).status_code == 400
    assert client.put('/api/settings/mail', json={'send_hour_start': 18, 'send_hour_end': 10}).status_code == 400
    invalid = client.put('/api/settings/mail', json={'smtp_password': 'SECRET' * 250})
    assert invalid.status_code == 422 and 'SECRET' not in invalid.text


def test_cookie_settings_need_same_origin_and_current_password_change_revokes_sessions(settings):
    original = settings.model_dump()
    client = TestClient(create_app(settings), base_url=settings.public_url)
    origin = {'Origin': settings.public_url}
    body = {'username': settings.admin_user, 'password': settings.admin_password}
    assert client.post('/api/login', json=body, headers=origin).status_code == 200
    old_cookie = client.cookies.get(COOKIE)
    assert client.put('/api/settings/mail', json={'sender_company': 'Team'}).status_code == 403
    assert client.put('/api/settings/mail', json={'sender_company': 'Team'}, headers=origin).status_code == 200
    patch = {'username': 'changed-admin', 'new_password': 'new-private-password-4567', 'current_password': 'wrong'}
    assert client.put('/api/settings/credentials', json=patch, headers=origin).status_code == 400
    patch['current_password'] = original['admin_password']
    assert client.put('/api/settings/credentials', json=patch, headers=origin).status_code == 200
    assert client.get('/api/settings').status_code == 401
    client.cookies.set(COOKIE, old_cookie)
    assert client.get('/api/settings').status_code == 401
    assert client.post('/api/login', json=body, headers=origin).status_code == 401
    client.cookies.clear()
    login = {'username': patch['username'], 'password': patch['new_password']}
    assert client.post('/api/login', json=login, headers=origin).status_code == 200
    file = settings.data_dir / 'workspace-settings.json'
    assert patch['new_password'] not in file.read_text()
    assert 'pbkdf2_sha256$' in file.read_text()
    assert patch['new_password'] not in client.get('/api/events').text
    restarted = Settings(_env_file=None, **original)
    other = TestClient(create_app(restarted), base_url=settings.public_url)
    assert other.post('/api/login', json=login, headers=origin).status_code == 200
    assert other.post('/api/login', json=body, headers=origin).status_code == 401
    assert restarted.api_token == original['api_token']


def test_mail_settings_cannot_change_inflight_connection(settings):
    client = client_for(settings)
    entered, release = Event(), Event()
    def activity():
        with settings._mailbox_lock:
            entered.set()
            release.wait(10)
    thread = Thread(target=activity)
    thread.start()
    assert entered.wait(5)
    try:
        response = client.put('/api/settings/mail', json={'smtp_password': 'new-private-password'})
        assert response.status_code == 400 and 'in progress' in response.json()['detail']
        assert settings.smtp_password == 'test'
        assert not (settings.data_dir / 'workspace-settings.json').exists()
    finally:
        release.set()
        thread.join(10)


def test_auth_change_attempts_throttled(settings):
    client = client_for(settings)
    body = {'username': 'new-admin', 'new_password': 'long-new-private-password', 'current_password': 'wrong'}
    for _ in range(5):
        assert client.put('/api/settings/credentials', json=body).status_code == 400
    assert client.put('/api/settings/credentials', json=body).status_code == 429
    assert not (settings.data_dir / 'workspace-settings.json').exists()
