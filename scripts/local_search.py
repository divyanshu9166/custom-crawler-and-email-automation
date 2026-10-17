"""Install/start the free local SearXNG development backend; no paid API keys."""
import argparse
import io
import json
import os
from pathlib import Path, PurePosixPath
import secrets
import subprocess
import sys
import types
import urllib.request
import venv
import zipfile

COMMIT = "f4822b3fc46726bb259d14c6332b702c76b98f82"
ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/tools/searxng-native"
ENV = ROOT / "data/tools/search-venv"


def install():
    provenance = SOURCE / "OUTREACH-SOURCE.json"
    if not provenance.exists():
        if SOURCE.exists() and any(SOURCE.iterdir()):
            raise RuntimeError("Existing untracked search source: preserve it and check provenance before installing")
        with urllib.request.urlopen(f"https://codeload.github.com/searxng/searxng/zip/{COMMIT}", timeout=60) as response:
            archive = response.read(60_000_001)
        if len(archive) > 60_000_000:
            raise ValueError("Search source archive exceeds installation budget")
        SOURCE.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(io.BytesIO(archive)) as z:
            if len(z.infolist()) > 10000 or sum(info.file_size for info in z.infolist()) > 150_000_000:
                raise ValueError("Search source archive exceeds extraction budget")
            for info in z.infolist():
                parts = PurePosixPath(info.filename).parts[1:]
                if not parts or parts[0] not in {"searx", "searxng_extra", "requirements.txt", "LICENSE", "README.rst"}:
                    continue
                if any(p in {"..", "."} or ":" in p or "\\" in p for p in parts) or info.file_size > 10_000_000:
                    raise ValueError("Unsafe source archive member")
                target = SOURCE.joinpath(*parts).resolve()
                if not target.is_relative_to(SOURCE.resolve()) or (info.external_attr >> 16) & 0o170000 == 0o120000:
                    raise ValueError("Unsafe source archive path")
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(z.read(info))
        provenance.write_text(json.dumps({"repository": "https://github.com/searxng/searxng", "commit": COMMIT, "license": "AGPL-3.0-or-later"}), encoding="utf-8")
    recorded = json.loads(provenance.read_text(encoding="utf-8"))
    if recorded["commit"] != COMMIT:
        raise ValueError("Different search-source version; deliberate upgrade and revalidation required")
    if not ENV.exists():
        venv.create(ENV, with_pip=True)
    python = ENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    subprocess.run([str(python), "-m", "pip", "install", "-r", str(SOURCE / "requirements.txt")], check=True)
    print("Installed pinned local search runtime. Start with scripts/local_search.py.")


def run():
    if not (SOURCE / "OUTREACH-SOURCE.json").exists():
        raise RuntimeError("First run scripts/local_search.py --install")
    if json.loads((SOURCE / "OUTREACH-SOURCE.json").read_text(encoding="utf-8"))["commit"] != COMMIT:
        raise ValueError("Search source version differs from the reviewed pin")
    settings = ROOT / "data/local-searxng.yml"
    if not settings.exists():
        names = ["google", "bing", "duckduckgo", "brave", "yahoo", "qwant", "mojeek"]
        settings.write_text("use_default_settings:\n  engines:\n    keep_only: [" + ", ".join(names) + "]\n"
                            "server:\n  bind_address: '127.0.0.1'\n  port: 8888\n  limiter: false\n"
                            "  secret_key: '" + secrets.token_hex(32) + "'\n"
                            "search:\n  formats: [json, html]\n"
                            "outgoing:\n  request_timeout: 12.0\n  max_request_timeout: 20.0\n"
                            "valkey:\n  url: false\nengines:\n" +
                            "".join(f"  - name: {name}\n    disabled: false\n" for name in names), encoding="utf-8")
    python = ENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    env = os.environ.copy()
    env["SEARXNG_SETTINGS_PATH"] = str(settings)
    env["PYTHONPATH"] = str(SOURCE)
    # Re-execute in the isolated dependency runtime; never install into the app venv.
    if Path(sys.executable).resolve() != python.resolve():
        subprocess.run([str(python), str(Path(__file__).resolve())], env=env, check=True)
        return
    os.environ.update(env)
    sys.path.insert(0, str(SOURCE))
    if os.name == "nt":
        # Upstream imports pwd for a Valkey diagnostic. Valkey is disabled here.
        def unsupported(*args):
            raise OSError("POSIX user lookup unavailable; use Linux for Valkey")
        module = types.ModuleType("pwd")
        module.getpwuid = unsupported
        sys.modules["pwd"] = module
    from searx.webapp import run as serve
    serve()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--install", action="store_true")
    args = parser.parse_args()
    if args.install:
        install()
    else:
        run()
