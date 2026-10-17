import importlib.util
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest


spec = importlib.util.spec_from_file_location("reacher_startup_smoke", Path(__file__).resolve().parents[1] / "scripts" / "reacher_smoke.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.mark.parametrize("mode", ["normal", "syntax_error", "pinned_header_400", "unprotected", "unprotected_400", "bad_contract"])
def test_reacher_startup_smoke_uses_invalid_syntax_and_checks_auth(mode):
    calls = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            calls.append((self.path, payload))
            status = 200
            if mode not in {"unprotected", "unprotected_400"} and self.headers.get("x-reacher-secret") != "disposable-test":
                status = 400 if mode == "pinned_header_400" else 401
            elif mode in {"syntax_error", "unprotected_400"}:
                status = 422
                if mode == "unprotected_400":
                    status = 400
            body = json.dumps({"input": payload["to_email"], "is_reachable": "safe" if mode == "bad_contract" else "invalid"}).encode()
            if mode == "pinned_header_400" and status == 400:
                body = b'Invalid request header "x-reacher-secret"'
            self.send_response(status)
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}"
        if mode in {"unprotected", "unprotected_400", "bad_contract"}:
            with pytest.raises(RuntimeError):
                module.check(url, "disposable-test")
        else:
            assert module.check(url, "disposable-test")["header_auth"] == "passed"
        assert calls and all(path == "/v0/check_email" and value == {"to_email": "invalid-address-without-at-sign"} for path, value in calls)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
