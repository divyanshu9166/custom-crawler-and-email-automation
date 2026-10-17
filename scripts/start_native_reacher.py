"""Build/start pinned Reacher on Windows using isolated user-local GNU tools.

No mailbox probe, app configuration change or outbound outreach occurs here.
Large prerequisites are downloaded only with --prepare; compilation needs --build.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import shutil
import socket
import subprocess
import sys
import zipfile

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from outreach.config import Settings
from scripts.reacher_smoke import check

ROOT = Path(__file__).resolve().parents[1]
COMMIT = "681791d3d9a854dfcaadb5eb13e5a2f3cb4eed67"
# The PowerShell wrapper supplies a verified junction when the workspace has
# spaces: MinGW/OpenSSL build rules cannot reliably quote every generated path.
TOOLS = Path(os.environ.get("NATIVE_REACHER_TOOLS", str(ROOT / "data/tools/reacher-native")))
COMPILER = Path(os.environ.get("NATIVE_REACHER_COMPILER", str(TOOLS / "mingw64")))
SDK = Path(os.environ.get("NATIVE_REACHER_SDK", str(TOOLS / "openssl-sdk")))
RUSTUP_URL = "https://static.rust-lang.org/rustup/archive/1.29.1/x86_64-pc-windows-gnu/rustup-init.exe"
RUSTUP_SHA256 = "6d5b5709addc0122c916d8c810da8d8a7b086a5d64fa805ef404d506392aadc8"
GCC_URL = ("https://github.com/brechtsanders/winlibs_mingw/releases/download/16.2.0posix-14.0.0-ucrt-r2/"
           "winlibs-x86_64-posix-seh-gcc-16.2.0-mingw-w64ucrt-14.0.0-r2.zip")
GCC_SHA256 = "d5dbafc4a170e762ca6143151ec918fb9e2c72736fb14cd704abebc6bdd5276a"
SDK_URL = ("https://github.com/StrawberryPerl/Perl-Dist-Strawberry/releases/download/SP_54231_64bit/"
           "strawberry-perl-5.42.3.1-64bit-portable.zip")
SDK_SHA256 = "6a081a811781c30aca51dbc036afd93092af91e3297901f02c17043795a10690"
PATCH_PATH = "backend/src/worker/consume.rs"
PATCH_BEFORE = ("\t\t.with_executor(tokio_executor_trait::Tokio::current())\n"
                "\t\t.with_reactor(tokio_reactor_trait::Tokio)\n"
                "\t\t.with_connection_name(backend_name.into());")
PATCH_AFTER = ("\t\t.with_executor(tokio_executor_trait::Tokio::current())\n"
               "\t\t.with_connection_name(backend_name.into());\n"
               "\t// Tokio's reactor trait implementation is Unix-only; native preview disables worker mode.\n"
               "\t#[cfg(unix)]\n\tlet options = options.with_reactor(tokio_reactor_trait::Tokio);")


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def build_target():
    return Path(os.environ.get("NATIVE_REACHER_TARGET", str(TOOLS / "source/target")))


def download(url, destination, expected):
    if destination.is_file() and sha256(destination) == expected:
        return
    temporary = destination.with_suffix(destination.suffix + ".partial")
    with httpx.Client(follow_redirects=True, timeout=120) as client:
        with client.stream("GET", url) as response:
            response.raise_for_status()
            with temporary.open("wb") as stream:
                for chunk in response.iter_bytes():
                    stream.write(chunk)
    if sha256(temporary) != expected:
        raise RuntimeError("Tool download checksum mismatch; refusing execution/extraction")
    temporary.replace(destination)


def extract_compiler(archive, destination, members=None):
    with zipfile.ZipFile(archive) as bundle:
        for entry in bundle.infolist():
            target = (destination / entry.filename).resolve()
            windows_path = PureWindowsPath(entry.filename)
            if (windows_path.drive or ".." in windows_path.parts or
                    not target.is_relative_to(destination.resolve()) or
                    (entry.external_attr >> 16) & 0o170000 == 0o120000):
                raise RuntimeError("Unsafe compiler archive member")
        bundle.extractall(destination, members=members)


def prepare_openssl():
    # The checksum-pinned native SDK avoids Git's incomplete MSYS Perl during
    # OpenSSL compilation. No upstream Rust source or lockfile is patched.
    archive = TOOLS / "perl.zip"
    download(SDK_URL, archive, SDK_SHA256)
    with zipfile.ZipFile(archive) as bundle:
        members = [name for name in bundle.namelist()
                   if name.startswith("c/include/openssl/") or
                   name in {"c/lib/libcrypto.a", "c/lib/libssl.a"} or
                   (name.startswith("c/bin/") and name.endswith(".dll"))]
    SDK.mkdir(parents=True, exist_ok=True)
    extract_compiler(archive, SDK, members)


def environment():
    result = os.environ.copy()
    result.update(RUSTUP_HOME=str(TOOLS / "rustup"), CARGO_HOME=str(TOOLS / "cargo"),
                  SQLX_OFFLINE="true", CARGO_BUILD_JOBS="1",
                  CARGO_TARGET_DIR=str(build_target()),
                  CARGO_PROFILE_RELEASE_DEBUG="false", CARGO_PROFILE_RELEASE_OPT_LEVEL="1",
                  CARGO_PROFILE_RELEASE_LTO="false", CMAKE_POLICY_VERSION_MINIMUM="3.5",
                  OPENSSL_NO_VENDOR="1", OPENSSL_DIR=str(SDK / "c"),
                  OPENSSL_LIB_DIR=str(SDK / "c/lib"), OPENSSL_INCLUDE_DIR=str(SDK / "c/include"),
                  OPENSSL_STATIC="0")
    result["PATH"] = os.pathsep.join([str(COMPILER / "bin"), str(TOOLS / "cargo/bin"),
                                    str(SDK / "c/bin"), result.get("PATH", "")])
    result["CC"] = str(COMPILER / "bin/gcc.exe")
    result["AR"] = str(COMPILER / "bin/ar.exe")
    result["CARGO_TARGET_X86_64_PC_WINDOWS_GNU_LINKER"] = result["CC"]
    return result


def backend_environment(secret):
    # Only the documented local config is passed. Clear inherited upstream RCH
    # overrides so storage, workers, webhooks or Sentry cannot start incidentally.
    env = {key: value for key, value in environment().items() if not key.upper().startswith("RCH__")}
    env.update(RCH__HTTP_HOST="127.0.0.1", RCH__HTTP_PORT="8081", RCH__HEADER_SECRET=secret,
               RCH__WORKER__ENABLE="false", RUST_LOG="info")
    return env


def prepare():
    TOOLS.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(TOOLS).free < 8 * 1024**3:
        raise RuntimeError("Native preparation needs at least 8 GiB free disk; Linux/Docker deployment remains available")
    download(RUSTUP_URL, TOOLS / "rustup-init.exe", RUSTUP_SHA256)
    download(GCC_URL, TOOLS / "winlibs.zip", GCC_SHA256)
    if not (COMPILER / "bin/gcc.exe").is_file():
        COMPILER.parent.mkdir(parents=True, exist_ok=True)
        extract_compiler(TOOLS / "winlibs.zip", COMPILER.parent)
    prepare_openssl()
    env = environment()
    subprocess.run([str(TOOLS / "rustup-init.exe"), "-y", "--no-modify-path", "--profile", "minimal",
                    "--default-host", "x86_64-pc-windows-gnu", "--default-toolchain", "1.99.0"],
                   env=env, check=True)
    source = TOOLS / "source"
    if not (source / ".git").exists():
        source.mkdir(exist_ok=True)
        subprocess.run(["git", "init", "--quiet", str(source)], check=True)
        subprocess.run(["git", "-C", str(source), "remote", "add", "origin",
                        "https://github.com/reacherhq/check-if-email-exists.git"], check=True)
        subprocess.run(["git", "-C", str(source), "fetch", "--depth", "1", "origin", COMMIT], check=True)
        subprocess.run(["git", "-C", str(source), "checkout", "--quiet", "FETCH_HEAD"], check=True)


def patched_source(original):
    if original.count(PATCH_BEFORE) != 1:
        raise RuntimeError("Pinned Windows compatibility patch context changed; refusing modification")
    return original.replace(PATCH_BEFORE, PATCH_AFTER)


def apply_windows_patch(source):
    original = subprocess.check_output(["git", "-C", str(source), "show", COMMIT + ":" + PATCH_PATH], text=True)
    expected = patched_source(original)
    path = source / PATCH_PATH
    current = path.read_text(encoding="utf-8")
    if current not in {original, expected}:
        raise RuntimeError("Worker source differs from the pinned revision or approved Windows patch")
    if current != expected:
        path.write_text(expected, encoding="utf-8", newline="\n")


def source_commit():
    source = TOOLS / "source"
    actual = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    changed = subprocess.check_output(["git", "-C", str(source), "status", "--porcelain"], text=True).strip()
    if actual != COMMIT or changed not in {"", "M " + PATCH_PATH}:
        raise RuntimeError("Reacher source must match the pinned, unmodified MIT revision or its exact approved Windows patch")
    if changed:
        original = subprocess.check_output(["git", "-C", str(source), "show", COMMIT + ":" + PATCH_PATH], text=True)
        if (source / PATCH_PATH).read_text(encoding="utf-8") != patched_source(original):
            raise RuntimeError("Reacher source differs from the exact approved Windows compatibility patch")
    return source


def build():
    source = source_commit()
    apply_windows_patch(source)
    env = environment()
    cargo = TOOLS / "cargo/bin/cargo.exe"
    if " " in str(TOOLS) or " " in str(COMPILER) or " " in str(SDK):
        raise RuntimeError("Native build tools require a space-free path; use scripts/start_native_reacher.ps1")
    if (not cargo.is_file() or not Path(env["CC"]).is_file() or
            not (SDK / "c/lib/libssl.a").is_file()):
        raise RuntimeError("Missing isolated Rust/GCC/OpenSSL prerequisites; use --prepare and install Git for Windows")
    with (TOOLS / "build.log").open("w", encoding="utf-8") as log:
        result = subprocess.run([str(cargo), "+1.99.0-x86_64-pc-windows-gnu", "build", "--locked", "--release",
                                 "--bin", "reacher_backend"], cwd=source, env=env, stdout=log, stderr=log)
    if result.returncode:
        raise RuntimeError("Actual Reacher compilation failed; inspect data/tools/reacher-native/build.log")
    binary = build_target() / "release/reacher_backend.exe"
    (TOOLS / "build-proof.json").write_text(json.dumps({"source_commit": COMMIT, "binary_sha256": sha256(binary),
        "cargo_lock_sha256": sha256(source / "Cargo.lock"), "rust_toolchain": "1.99.0-x86_64-pc-windows-gnu",
        "native_openssl_sdk_sha256": SDK_SHA256, "native_openssl_version": "3.6.1 (dynamic)",
        "windows_patch_file": PATCH_PATH, "windows_patch_source_sha256": sha256(source / PATCH_PATH),
        "scope": "Build provenance only; SMTP/provider accuracy remains unverified"}, indent=2), encoding="utf-8")


def start():
    source_commit()
    binary = build_target() / "release/reacher_backend.exe"
    proof = json.loads((TOOLS / "build-proof.json").read_text(encoding="utf-8"))
    if proof.get("source_commit") != COMMIT or proof.get("binary_sha256") != sha256(binary):
        raise RuntimeError("Backend build provenance mismatch; rebuild before startup")
    if proof.get("windows_patch_source_sha256") != sha256((TOOLS / "source") / PATCH_PATH):
        raise RuntimeError("Windows compatibility patch provenance mismatch; rebuild before startup")
    settings = Settings()
    if not settings.reacher_secret:
        raise RuntimeError("Configure a private REACHER_SECRET before startup; no settings were changed")
    with socket.socket() as candidate:
        candidate.bind(("127.0.0.1", 8081))
    runtime = TOOLS / "runtime"
    runtime.mkdir(exist_ok=True)
    shutil.copyfile(ROOT / "deploy/reacher.toml", runtime / "backend_config.toml")
    env = backend_environment(settings.reacher_secret)
    with (runtime / "backend.log").open("ab") as log:
        process = subprocess.Popen([str(binary)], cwd=runtime, env=env, stdout=log, stderr=log,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        result = check("http://127.0.0.1:8081", settings.reacher_secret)
        if process.poll() is not None:
            raise RuntimeError("Native backend exited during readiness check")
    except Exception:
        process.terminate()
        process.wait(timeout=10)
        raise
    record = {"ready": True, "url": "http://127.0.0.1:8081", "pid": process.pid, "source_commit": COMMIT,
              "binary_sha256": proof["binary_sha256"], "check": result, "sending_enabled": False,
              "settings_changed": False, "real_recipients_submitted": 0}
    (TOOLS / "runtime.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true", help="Download isolated tools (large); no system PATH changes")
    parser.add_argument("--build", action="store_true", help="Compile actual pinned Reacher; may take several minutes")
    args = parser.parse_args()
    try:
        if os.name != "nt":
            raise RuntimeError("This helper is Windows-only; use the existing Linux Compose verifier profile")
        if args.prepare:
            print("Preparing checksum-verified workspace-local build tools", flush=True)
            prepare()
        if args.build:
            print("Building actual Reacher with one compilation worker; progress is in build.log", flush=True)
            build()
        print(json.dumps(start(), indent=2))
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        # Do not print arbitrary subprocess output or environment/secret values.
        print(json.dumps({"ready": False, "error_type": type(exc).__name__,
                          "reason": str(exc) if isinstance(exc, RuntimeError) else "Native setup failed; inspect local prerequisites/logs",
                          "settings_changed": False, "real_recipients_submitted": 0}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
