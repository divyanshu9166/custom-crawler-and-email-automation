import json
import sqlite3
import subprocess
import sys
import tomllib
from pathlib import Path

import yaml
import pytest


ROOT = Path(__file__).resolve().parents[1]


def test_compose_keeps_provider_ports_internal():
    compose = yaml.safe_load((ROOT / "compose.yaml").read_text())
    assert "ports" not in compose["services"]["reacher"]
    assert "ports" not in compose["services"]["searxng"]
    assert compose["services"]["app"]["ports"] == ["127.0.0.1:8000:8000"]
    assert "sha256:" in compose["services"]["searxng"]["image"]


def test_reacher_low_memory_config_and_n8n_inactive():
    config = tomllib.loads((ROOT / "deploy/reacher.toml").read_text())
    assert config["worker"]["enable"] is False
    assert config["overrides"]["hotmailb2c"]["type"] == "smtp"
    flow = json.loads((ROOT / "deploy/n8n-discovery.json").read_text())
    assert flow["active"] is False
    assert len(flow["nodes"]) == 2


def test_consistent_backup_of_wal_database(settings, db, prepared, tmp_path):
    import os
    output = tmp_path / "copies"
    result = subprocess.run([sys.executable, "scripts/backup.py", "--output", str(output)],
                            cwd=ROOT, env={**os.environ, "DATA_DIR": str(settings.data_dir)},
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    backups = list(output.glob("*.db"))
    assert len(backups) == 1
    with sqlite3.connect(backups[0]) as con:
        assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert con.execute("SELECT COUNT(*) FROM messages").fetchone()[0] == 4


def test_preflight_uses_managed_mailbox_values_without_disclosing_them(settings):
    import os
    from outreach.preferences import Preferences
    prefs = Preferences(settings)
    prefs.persist({'smtp_host': 'private-managed-smtp.example.com', 'smtp_password': 'private-managed-app-password',
                   'imap_host': 'private-managed-imap.example.com', 'imap_password': 'private-managed-imap-password'})
    result = subprocess.run([sys.executable, 'scripts/preflight.py'], cwd=ROOT,
                            env={**os.environ, 'DATA_DIR': str(settings.data_dir), 'BROWSER_ENABLED': 'false',
                                 'SMTP_HOST': '', 'SMTP_PASSWORD': '', 'IMAP_HOST': '', 'IMAP_PASSWORD': ''},
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report['managed_workspace_settings_loaded'] is True
    assert not {'smtp_host', 'smtp_password', 'imap_host', 'imap_password'} & set(report['sending_gaps'])
    assert 'private-managed-' not in result.stdout + result.stderr


def test_preflight_checks_platform_chromium_even_if_website_browser_is_disabled(settings):
    import os
    result = subprocess.run([sys.executable, 'scripts/preflight.py'], cwd=ROOT,
        env={**os.environ, 'DATA_DIR': str(settings.data_dir), 'BROWSER_ENABLED': 'false',
             'PLATFORM_BROWSER_ENABLED': 'true', 'PLATFORM_BROWSER_HEADLESS': 'false', 'DISPLAY': ''},
        capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report['platform_browser']['enabled'] is True
    assert report['platform_browser']['display_required'] is True
    assert report['platform_browser']['display_configured'] is False
    assert report['platform_browser']['profile_directory_present'] is False
    assert 'not established' in report['platform_browser']['authenticated_access']
    assert isinstance(report['chromium_installed'], bool)


def test_reacher_readiness_rejects_wrong_service_http_success(monkeypatch):
    from scripts import reacher_smoke
    from unittest.mock import MagicMock
    response = MagicMock()
    response.status = 200
    response.read.return_value = b'<html>Server is up and running.</html>'
    response.__enter__.return_value = response
    monkeypatch.setattr(reacher_smoke.urllib.request, 'urlopen', lambda *a, **k: response)
    with pytest.raises(RuntimeError, match='not a Reacher JSON API'):
        reacher_smoke.check('http://127.0.0.1:8080', 'fixture-secret', attempts=1)


def test_reacher_readiness_rejects_unknown_json_schema(monkeypatch):
    from scripts import reacher_smoke
    from unittest.mock import MagicMock
    response = MagicMock()
    response.status = 200
    response.read.return_value = b'[]'
    response.__enter__.return_value = response
    monkeypatch.setattr(reacher_smoke.urllib.request, 'urlopen', lambda *a, **k: response)
    with pytest.raises(RuntimeError, match='response schema'):
        reacher_smoke.check('http://127.0.0.1:8080', 'fixture-secret', attempts=1)


def test_reacher_readiness_checks_auth_without_a_valid_recipient(monkeypatch):
    import io
    from scripts import reacher_smoke
    from unittest.mock import MagicMock
    requests = []
    def respond(req, **kwargs):
        requests.append(req)
        assert json.loads(req.data) == {'to_email': 'invalid-address-without-at-sign'}
        if req.get_header('X-reacher-secret') != 'fixture-secret':
            raise reacher_smoke.urllib.error.HTTPError(req.full_url, 400, 'bad header', {},
                                                     io.BytesIO(b'Invalid request header x-reacher-secret'))
        response = MagicMock()
        response.status = 200
        response.read.return_value = b'{"input":"invalid-address-without-at-sign","is_reachable":"invalid"}'
        response.__enter__.return_value = response
        return response
    monkeypatch.setattr(reacher_smoke.urllib.request, 'urlopen', respond)
    result = reacher_smoke.check('http://127.0.0.1:8080', 'fixture-secret', attempts=1)
    assert result['header_auth'] == 'passed'
    assert len(requests) == 2
    assert all(req.full_url.endswith('/v0/check_email') for req in requests)


def test_reacher_readiness_single_attempt_does_not_wait(monkeypatch):
    from scripts import reacher_smoke
    def unavailable(*args, **kwargs):
        raise OSError('fixture unreachable')
    def unexpected_sleep(*args):
        pytest.fail('Read-only preflight must not enter startup retry sleep')
    monkeypatch.setattr(reacher_smoke.urllib.request, 'urlopen', unavailable)
    monkeypatch.setattr(reacher_smoke.time, 'sleep', unexpected_sleep)
    with pytest.raises(RuntimeError, match='did not become reachable'):
        reacher_smoke.check('http://127.0.0.1:8080', 'fixture-secret', attempts=1)
