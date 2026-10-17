"""Check self-hosted Reacher startup/auth/syntax without probing a valid recipient or sending mail."""
import argparse
import json
import time
import urllib.error
import urllib.request


def check(url, secret, attempts=30, path='/v0/check_email'):
    endpoint = url.rstrip("/") + path
    payload = json.dumps({"to_email": "invalid-address-without-at-sign"}).encode()
    def request(header_secret):
        req = urllib.request.Request(endpoint, data=payload,
                                     headers={"Content-Type": "application/json", "x-reacher-secret": header_secret})
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                return response.status, response.read(65536)
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read(65536)
    for attempt in range(attempts):
        try:
            status, body = request(secret)
            break
        except (OSError, TimeoutError):
            if attempt + 1 < attempts:
                time.sleep(1)
    else:
        raise RuntimeError("Reacher did not become reachable")
    if status == 200:
        try:
            result = json.loads(body)
        except (ValueError, UnicodeError) as exc:
            raise RuntimeError("Endpoint is not a Reacher JSON API; HTTP reachability alone is insufficient") from exc
        if not isinstance(result, dict):
            raise RuntimeError("Unexpected Reacher response schema")
        if result.get("input") != "invalid-address-without-at-sign" or result.get("is_reachable") != "invalid":
            raise RuntimeError("Unexpected invalid-syntax response")
    elif status not in {400, 422}:
        raise RuntimeError(f"Reacher syntax check returned HTTP {status}")
    rejected, rejection_body = request(secret + "-wrong")
    # The pinned backend uses Warp's exact-header filter, whose InvalidHeader
    # rejection is HTTP 400. Accept that specific error, not an arbitrary 400
    # that could merely be the same unauthenticated syntax rejection.
    header_rejection = rejected == 400 and b"x-reacher-secret" in rejection_body.lower() and b"header" in rejection_body.lower()
    if rejected not in {401, 403} and not header_rejection:
        raise RuntimeError("Reacher did not reject an incorrect header secret")
    return {"startup": "reachable", "syntax_rejection": "passed", "header_auth": "passed",
            "scope": "Startup/auth/syntax only; recipient probing and provider accuracy remain unverified."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", required=True)
    parser.add_argument("--secret", required=True, help="Use only a disposable CI/local-test secret here")
    args = parser.parse_args()
    print(json.dumps(check(args.url, args.secret), indent=2))
