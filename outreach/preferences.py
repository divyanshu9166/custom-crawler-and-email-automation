"""Private, atomically persisted workspace settings; never expose stored secrets."""
import hashlib
import json
import os
import secrets
from threading import RLock

from .config import Settings
from .web import normalize_email

MAIL_FIELDS = {"sender_name", "sender_company", "sender_email", "sender_website", "postal_address",
               "smtp_host", "smtp_port", "smtp_user", "smtp_password", "smtp_security",
               "imap_host", "imap_port", "imap_user", "imap_password", "imap_folder",
               "daily_send_limit", "hourly_send_limit", "min_send_interval_seconds", "send_hour_start", "send_hour_end", "domain_auth_confirmed"}
AUTH_FIELDS = {"admin_user", "admin_password_hash", "session_version"}
WRITER_FIELDS = {'draft_api_url', 'draft_api_key', 'draft_model', 'draft_timeout_seconds'}
PAGESPEED_FIELDS = {'pagespeed_api_key'}
RUNTIME_FIELDS = {'worker_enabled', 'sending_enabled'}
RESEARCH_FIELDS = {'auto_prepare_enabled', 'linkedin_people_search_enabled', 'linkedin_profile_experience_enabled',
                   'linkedin_contact_info_enabled', 'social_posts_enabled', 'social_posts_max_profiles',
                   'social_posts_max_posts'}


def password_matches(settings, password):
    if not settings.admin_password_hash:
        return secrets.compare_digest(password.encode(), settings.admin_password.encode())
    try:
        algorithm, salt, digest = settings.admin_password_hash.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        value = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 600_000).hex()
        return secrets.compare_digest(value, digest)
    except (ValueError, TypeError):
        return False


def session_key(settings):
    return settings.api_token if not settings.session_version else hashlib.sha256(
        (settings.api_token + ":" + settings.session_version).encode()).hexdigest()


class Preferences:
    def __init__(self, settings):
        self.settings, self.path, self.lock = settings, settings.data_dir / "workspace-settings.json", RLock()
        self.saved = {}
        if self.path.exists():
            self.saved = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(self.saved, dict) or set(self.saved) - MAIL_FIELDS - AUTH_FIELDS - WRITER_FIELDS - PAGESPEED_FIELDS - RUNTIME_FIELDS - RESEARCH_FIELDS:
                raise RuntimeError("Invalid managed workspace settings")
            checked = Settings.model_validate({**settings.model_dump(), **self.saved})
            for key in self.saved:
                setattr(settings, key, getattr(checked, key))

    def public(self):
        with self.lock:
            values = {k: getattr(self.settings, k) for k in (MAIL_FIELDS | WRITER_FIELDS | RESEARCH_FIELDS) - {"smtp_password", "imap_password", 'draft_api_key'}}
            return {**values, "smtp_password_configured": bool(self.settings.smtp_password),
                    'draft_api_key_configured': bool(self.settings.draft_api_key),
                    'pagespeed_api_key_configured': bool(self.settings.pagespeed_api_key),
                    "imap_password_configured": bool(self.settings.imap_password), "admin_user": self.settings.admin_user,
                    "public_url": self.settings.public_url, "sending_enabled": self.settings.sending_enabled,
                    "worker_enabled": self.settings.worker_enabled,
                    "sending_gaps": self.settings.sending_gaps()}

    def persist(self, patch):
        value = {**self.saved, **patch}
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_name(".workspace-settings-" + secrets.token_hex(8) + ".tmp")
        try:
            fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(value, stream, ensure_ascii=True)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp, self.path)
            self.saved = value
            for key, item in patch.items():
                setattr(self.settings, key, item)
        finally:
            temp.unlink(missing_ok=True)

    def update_mail(self, db, patch):
        with self.lock:
            for key in ("smtp_password", "imap_password"):
                clear = patch.pop("clear_" + key, False)
                if clear and patch.get(key):
                    raise ValueError("Choose either replacement or removal for each password")
                if clear:
                    patch[key] = ""
                elif key in patch and not patch[key]:
                    del patch[key]
            if set(patch) - MAIL_FIELDS:
                raise ValueError("Unsupported mailbox setting")
            checked = Settings.model_validate({**self.settings.model_dump(), **patch})
            if checked.sender_email:
                patch["sender_email"] = normalize_email(checked.sender_email)
            if checked.send_hour_end <= checked.send_hour_start:
                raise ValueError("Sending window end must be later than its start")
            if checked.smtp_security not in {"ssl", "starttls"} or not 1 <= checked.smtp_port <= 65535 or not 1 <= checked.imap_port <= 65535:
                raise ValueError("Use TLS SMTP and valid mailbox ports")
            if not self.settings._mailbox_lock.acquire(blocking=False):
                raise ValueError("Mailbox activity is in progress; retry after it finishes")
            try:
                if db.one("SELECT id FROM messages WHERE state='sending'"):
                    raise ValueError("A message submission is in progress; retry after it finishes")
                db.set("paused", "true")
                self.persist({key: getattr(checked, key) if key not in {"smtp_password", "imap_password", "sender_email"} else val
                              for key, val in patch.items()})
                db.set("imap_caught_up", "false")
                db.set("imap_last_success", "0")
                db.event("workspace_mail_settings_changed", {"fields": sorted(patch), "sending_paused": True})
            finally:
                self.settings._mailbox_lock.release()
            return self.public()

    def update_writer(self, db, patch):
        with self.lock:
            clear = patch.pop('clear_draft_api_key', False)
            if clear and patch.get('draft_api_key'):
                raise ValueError('Choose either replacement or removal for the API key')
            if clear:
                patch['draft_api_key'] = ''
            elif 'draft_api_key' in patch and not patch['draft_api_key']:
                del patch['draft_api_key']
            if set(patch) - WRITER_FIELDS:
                raise ValueError('Unsupported AI writer setting')
            checked = Settings.model_validate({**self.settings.model_dump(), **patch})
            from .email_writer import completion_url
            completion_url(checked.draft_api_url)
            db.set('writer_last_check', 'null')
            db.set('paused', 'true')
            self.persist({key: getattr(checked, key) for key in patch})
            db.event('workspace_writer_settings_changed', {'fields': sorted(patch), 'sending_paused': True})
            return self.public()

    def update_pagespeed(self, db, patch):
        with self.lock:
            clear = patch.pop('clear_pagespeed_api_key', False)
            if clear and patch.get('pagespeed_api_key'):
                raise ValueError('Choose either replacement or removal for the PageSpeed API key')
            if clear:
                patch['pagespeed_api_key'] = ''
            elif 'pagespeed_api_key' in patch and not patch['pagespeed_api_key']:
                del patch['pagespeed_api_key']
            if set(patch) - PAGESPEED_FIELDS:
                raise ValueError('Unsupported PageSpeed setting')
            checked = Settings.model_validate({**self.settings.model_dump(), **patch})
            db.set('paused', 'true')
            self.persist({key: getattr(checked, key) for key in patch})
            db.event('workspace_pagespeed_settings_changed', {'fields': sorted(patch), 'sending_paused': True})
            return self.public()

    def update_research(self, db, patch):
        with self.lock:
            if not patch or set(patch) - RESEARCH_FIELDS:
                raise ValueError('Choose supported research controls')
            for key, value in patch.items():
                if key.endswith('_enabled') and type(value) is not bool:
                    raise ValueError('Research switches must be true or false')
            checked = Settings.model_validate({**self.settings.model_dump(), **patch})
            db.set('paused', 'true')
            self.persist({key: getattr(checked, key) for key in patch})
            db.event('workspace_research_settings_changed', {'fields': sorted(patch), 'sending_paused': True})
            return self.public()

    def update_runtime(self, db, patch):
        with self.lock:
            if not patch or set(patch) - RUNTIME_FIELDS or any(type(value) is not bool for value in patch.values()):
                raise ValueError("Choose worker and sending on/off controls")
            if db.get('demo') == 'true' and any(patch.values()):
                raise ValueError("Offline demo cannot enable automation or sending")
            # Changing an enable flag never resumes previously approved messages.
            db.set('paused', 'true')
            self.persist(patch)
            db.event('workspace_runtime_settings_changed', {**patch, 'sending_paused': True})
            return {**self.public(), 'paused': True, 'demo': db.get('demo') == 'true'}

    def update_credentials(self, db, username, password, current_password):
        with self.lock:
            if not password_matches(self.settings, current_password):
                raise ValueError("Current password is incorrect")
            salt = secrets.token_bytes(16)
            digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 600_000).hex()
            self.persist({"admin_user": username, "admin_password_hash": f"pbkdf2_sha256${salt.hex()}${digest}",
                          "session_version": secrets.token_urlsafe(32)})
            db.event("workspace_login_changed", {"browser_sessions_revoked": True})
