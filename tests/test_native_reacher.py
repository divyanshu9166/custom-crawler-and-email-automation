import importlib.util
import json
from pathlib import Path
from unittest.mock import Mock
import zipfile

import httpx
import pytest


spec = importlib.util.spec_from_file_location("native_reacher", Path(__file__).resolve().parents[1] / "scripts/start_native_reacher.py")
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)


def test_native_bad_checksum_preserves_existing_tool(tmp_path, monkeypatch):
    tool = tmp_path / "installer.exe"
    tool.write_bytes(b"old-verified-tool")
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=b"wrong-download"))
    original_client = httpx.Client
    monkeypatch.setattr(native.httpx, "Client", lambda **kwargs: original_client(transport=transport, **kwargs))
    with pytest.raises(RuntimeError, match="checksum"):
        native.download("https://example.test/installer", tool, "0" * 64)
    assert tool.read_bytes() == b"old-verified-tool"


def test_native_verified_cached_tool_does_not_redownload(tmp_path, monkeypatch):
    tool = tmp_path / "installer.exe"
    tool.write_bytes(b"verified-tool")
    client = Mock(side_effect=AssertionError("No network needed for verified cache"))
    monkeypatch.setattr(native.httpx, "Client", client)
    native.download("https://example.test/installer", tool, native.sha256(tool))
    client.assert_not_called()


@pytest.mark.parametrize("member", ["../escape.exe", "/escape.exe", "C:/escape.exe", r"..\escape.exe"])
def test_native_compiler_archive_cannot_escape_tools(tmp_path, member):
    archive = tmp_path / "compiler.zip"
    destination = tmp_path / "tools"
    destination.mkdir()
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr(member, b"untrusted")
    with pytest.raises(RuntimeError, match="Unsafe"):
        native.extract_compiler(archive, destination)
    assert list(destination.iterdir()) == []


def test_native_compiler_archive_rejects_symlink(tmp_path):
    archive = tmp_path / "compiler.zip"
    member = zipfile.ZipInfo("mingw64/bin/compiler")
    member.external_attr = 0o120777 << 16
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr(member, "../../../elsewhere")
    with pytest.raises(RuntimeError, match="Unsafe"):
        native.extract_compiler(archive, tmp_path / "tools")


def test_native_runtime_overrides_cannot_enable_external_services(monkeypatch):
    inherited = {"RCH__HTTP_HOST": "0.0.0.0", "RCH__WORKER__ENABLE": "true",
                 "RCH__STORAGE__DB_URL": "postgres://external", "rch__sentry_dsn": "https://external",
                 "RCH__WORKER__WEBHOOK__URL": "https://external", "PATH": "ordinary"}
    monkeypatch.setattr(native, "environment", lambda: inherited.copy())
    env = native.backend_environment("disposable")
    assert env["RCH__HTTP_HOST"] == "127.0.0.1" and env["RCH__HTTP_PORT"] == "8081"
    assert env["RCH__WORKER__ENABLE"] == "false" and env["RCH__HEADER_SECRET"] == "disposable"
    assert "RCH__STORAGE__DB_URL" not in env and "rch__sentry_dsn" not in env
    assert "RCH__WORKER__WEBHOOK__URL" not in env and inherited["RCH__WORKER__ENABLE"] == "true"


@pytest.mark.parametrize("commit,dirty", [("wrong-commit", ""), (native.COMMIT, " M Cargo.lock")])
def test_native_build_rejects_changed_or_unpinned_source(tmp_path, monkeypatch, commit, dirty):
    monkeypatch.setattr(native, "TOOLS", tmp_path)
    monkeypatch.setattr(native.subprocess, "check_output", Mock(side_effect=[commit, dirty]))
    with pytest.raises(RuntimeError, match="pinned, unmodified"):
        native.source_commit()


def test_native_start_rejects_modified_binary_before_process_or_secret_access(tmp_path, monkeypatch):
    source = tmp_path / "source"
    binary = source / "target/release/reacher_backend.exe"
    binary.parent.mkdir(parents=True)
    binary.write_bytes(b"changed-binary")
    (tmp_path / "build-proof.json").write_text(json.dumps({"source_commit": native.COMMIT,
                                                         "binary_sha256": "0" * 64}), encoding="utf-8")
    monkeypatch.setattr(native, "TOOLS", tmp_path)
    monkeypatch.setattr(native, "source_commit", lambda: source)
    settings = Mock(side_effect=AssertionError("No secret access"))
    process = Mock(side_effect=AssertionError("No process launch"))
    monkeypatch.setattr(native, "Settings", settings)
    monkeypatch.setattr(native.subprocess, "Popen", process)
    with pytest.raises(RuntimeError, match="provenance"):
        native.start()
    settings.assert_not_called()
    process.assert_not_called()


def test_native_platform_patch_is_exact_and_idempotent(tmp_path, monkeypatch):
    source = tmp_path / "source"
    worker = source / native.PATCH_PATH
    worker.parent.mkdir(parents=True)
    original = "before\n" + native.PATCH_BEFORE + "\nafter\n"
    worker.write_text(original, encoding="utf-8")
    monkeypatch.setattr(native.subprocess, "check_output", lambda *args, **kwargs: original)
    native.apply_windows_patch(source)
    expected = "before\n" + native.PATCH_AFTER + "\nafter\n"
    assert worker.read_text(encoding="utf-8") == expected
    native.apply_windows_patch(source)
    assert worker.read_text(encoding="utf-8") == expected
    worker.write_text(expected + "unexpected change", encoding="utf-8")
    with pytest.raises(RuntimeError, match="differs"):
        native.apply_windows_patch(source)


def test_native_source_guard_rejects_unapproved_change_inside_patched_file(tmp_path, monkeypatch):
    source = tmp_path / "source"
    worker = source / native.PATCH_PATH
    worker.parent.mkdir(parents=True)
    original = "before\n" + native.PATCH_BEFORE + "\nafter\n"
    worker.write_text(native.patched_source(original) + "unexpected", encoding="utf-8")
    monkeypatch.setattr(native, "TOOLS", tmp_path)
    monkeypatch.setattr(native.subprocess, "check_output", Mock(side_effect=[native.COMMIT, " M " + native.PATCH_PATH, original]))
    with pytest.raises(RuntimeError, match="exact approved"):
        native.source_commit()
