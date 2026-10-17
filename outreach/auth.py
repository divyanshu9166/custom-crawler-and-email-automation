"""Signed browser sessions; API tokens and Basic auth remain supported."""
import hashlib
import hmac
import secrets
import time

COOKIE = "outreach_session"
MAX_AGE = 8 * 3600


def issue_session(secret):
    value = f"{int(time.time()) + MAX_AGE}.{secrets.token_hex(16)}"
    return value + "." + hmac.new(secret.encode(), value.encode(), hashlib.sha256).hexdigest()


def valid_session(token, secret):
    try:
        expiry, nonce, signature = token.split(".")
        if len(nonce) != 32 or not 0 < int(expiry) - time.time() <= MAX_AGE:
            return False
        expected = hmac.new(secret.encode(), f"{expiry}.{nonce}".encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(signature, expected)
    except (AttributeError, TypeError, ValueError):
        return False
