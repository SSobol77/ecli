# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/packaging/test_install_ecli_linters_script.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Behavior tests for the standalone Debian 13 linter installer.

Covers menu parsing, invalid input, root/Debian-13/amd64 validation, APT
dependency resolution, secure command arrays, lock-file validation,
HTTPS-only downloads, checksum mismatch, interrupted downloads, safe
extraction (traversal / symlink escape / exact member), idempotent
reinstall, managed upgrade, corrupt binaries, PATH script idempotency,
state-file atomicity, version-probe handling (including stderr output),
partial failure, custom selections, the full 19-tool result, and the
no-false-success guarantee.
"""

from __future__ import annotations

import hashlib
import importlib.util
import io
import os
import stat
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
INSTALLER_PATH = REPO_ROOT / "scripts" / "install_ecli_linters.py"
_MODULE_NAME = "install_ecli_linters_under_test"


def _load_installer():
    if _MODULE_NAME in sys.modules:
        return sys.modules[_MODULE_NAME]
    spec = importlib.util.spec_from_file_location(_MODULE_NAME, INSTALLER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[_MODULE_NAME] = module
    spec.loader.exec_module(module)
    return module


MOD = _load_installer()

ALL_NUMBERS = frozenset(range(1, 20))


class LogStub:
    """Log double capturing every line without touching /var/log."""

    def __init__(self) -> None:
        """Start with an empty capture buffer."""
        self.lines: list[str] = []

    def log(self, message: str, *, echo: bool | None = None) -> None:
        self.lines.append(message)

    def detail(self, message: str) -> None:
        self.lines.append(message)

    def close(self) -> None:
        pass

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


@pytest.fixture
def payload_env(tmp_path, monkeypatch):
    """Redirect every payload path constant into an isolated tmp tree."""
    root = tmp_path / "opt-ecli-payload"
    mapping = {
        "PAYLOAD_ROOT": root,
        "PAYLOAD_BIN": root / "bin",
        "PAYLOAD_PACKAGES": root / "packages",
        "PAYLOAD_STATE": root / "state",
        "PAYLOAD_CACHE": root / "cache",
        "STATE_FILE": root / "state" / "installed-tools.json",
        "PROFILE_SCRIPT": tmp_path / "profile.d" / "ecli_payload.sh",
    }
    for name, value in mapping.items():
        monkeypatch.setattr(MOD, name, value)
    for name in ("PAYLOAD_BIN", "PAYLOAD_PACKAGES", "PAYLOAD_STATE", "PAYLOAD_CACHE"):
        mapping[name].mkdir(parents=True, exist_ok=True)
    return mapping


def _fake_tool_script(version_line: str, *, to_stderr: bool = False) -> bytes:
    stream = "1>&2" if to_stderr else ""
    return f'#!/bin/sh\necho "{version_line}" {stream}\n'.encode()


def _make_tar_gz(path: Path, members: dict[str, bytes], *, mode: int = 0o755):
    with tarfile.open(path, "w:gz") as handle:
        for name, payload in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            info.mode = mode
            handle.addfile(info, io.BytesIO(payload))


def _ruff_lock_entry(archive: Path, script: bytes) -> dict:
    return {
        "tool_id": "ruff",
        "version": "0.15.21",
        "source_url": "https://example.invalid/ruff",
        "asset_url": "https://example.invalid/ruff.tar.gz",
        "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "archive_type": "tar.gz",
        "expected_member": "ruff-x86_64-unknown-linux-gnu/ruff",
        "executable_name": "ruff",
        "version_command": ["ruff", "--version"],
        "install_directory": str(MOD.PAYLOAD_BIN),
        "architecture": "amd64",
        "license": "MIT",
        "max_download_bytes": max(archive.stat().st_size, 1),
    }


# ---------------------------------------------------------------------------
# Menu parsing and invalid input
# ---------------------------------------------------------------------------


class TestSelectionParsing:
    def test_a_selects_all_nineteen(self):
        assert MOD.parse_selection("A") == ALL_NUMBERS
        assert MOD.parse_selection("a") == ALL_NUMBERS
        assert MOD.parse_selection("  a  ") == ALL_NUMBERS

    def test_single_number(self):
        assert MOD.parse_selection("7") == frozenset({7})

    def test_comma_separated_with_whitespace(self):
        assert MOD.parse_selection(" 1 , 4 ,5 ") == frozenset({1, 4, 5})

    def test_duplicates_deduplicated(self):
        assert MOD.parse_selection("2,2,2") == frozenset({2})

    @pytest.mark.parametrize(
        "raw",
        ["", "   ", "0", "20", "-1", "1,,2", "1;2", "one", "1 2", "a,1", "A,3", "1.5"],
    )
    def test_malformed_input_rejected_not_ignored(self, raw):
        with pytest.raises(MOD.SelectionError):
            MOD.parse_selection(raw)

    def test_menu_lists_all_nineteen_tools_in_english(self):
        menu = MOD.render_menu()
        assert "[ A ] - Install All Linters" in menu
        for tool in MOD.TOOLS:
            assert f"{tool.number}." in menu
            assert tool.menu_name in menu
        assert len(MOD.TOOLS) == 19

    def test_interactive_prompt_reprompts_then_accepts(self, capsys):
        answers = iter(["bogus", "1,19"])
        selected = MOD.prompt_selection(input_fn=lambda _: next(answers))
        assert selected == frozenset({1, 19})
        assert "invalid selection" in capsys.readouterr().err

    def test_interactive_prompt_gives_up_after_bounded_attempts(self, capsys):
        with pytest.raises(MOD.SelectionError):
            MOD.prompt_selection(input_fn=lambda _: "nope")


# ---------------------------------------------------------------------------
# Root, Debian 13, and amd64 requirements
# ---------------------------------------------------------------------------


class TestPlatformValidation:
    GOOD = {"ID": "debian", "VERSION_ID": "13"}

    def test_supported_platform_has_no_errors(self):
        assert (
            MOD.platform_errors(
                euid=0,
                sys_platform="linux",
                os_release=self.GOOD,
                dpkg_arch="amd64",
            )
            == []
        )

    def test_root_required(self):
        errors = MOD.platform_errors(
            euid=1000, sys_platform="linux", os_release=self.GOOD, dpkg_arch="amd64"
        )
        assert any("root" in error for error in errors)

    def test_debian_required(self):
        errors = MOD.platform_errors(
            euid=0,
            sys_platform="linux",
            os_release={"ID": "ubuntu", "VERSION_ID": "24.04"},
            dpkg_arch="amd64",
        )
        assert any("Debian is required" in error for error in errors)

    @pytest.mark.parametrize("version_id", ["12", "14", "13.0.0-weird", ""])
    def test_debian_major_thirteen_required(self, version_id):
        os_release = {"ID": "debian", "VERSION_ID": version_id}
        errors = MOD.platform_errors(
            euid=0, sys_platform="linux", os_release=os_release, dpkg_arch="amd64"
        )
        if version_id.startswith("13"):
            assert errors == []
        else:
            assert any("Debian 13" in error for error in errors)

    @pytest.mark.parametrize("arch", ["arm64", "i386", None])
    def test_amd64_required(self, arch):
        errors = MOD.platform_errors(
            euid=0, sys_platform="linux", os_release=self.GOOD, dpkg_arch=arch
        )
        assert any("amd64" in error for error in errors)

    def test_linux_required(self):
        errors = MOD.platform_errors(
            euid=0, sys_platform="freebsd14", os_release=self.GOOD, dpkg_arch="amd64"
        )
        assert any("Linux is required" in error for error in errors)

    @pytest.mark.skipif(os.geteuid() == 0, reason="running as root")
    def test_main_exits_nonzero_on_unsupported_invocation(self):
        assert MOD.main(["--select", "A"]) == MOD.EXIT_PLATFORM


# ---------------------------------------------------------------------------
# APT dependency resolution (single transaction)
# ---------------------------------------------------------------------------


class TestAptResolution:
    def test_apt_only_tool_needs_no_acquisition_packages(self):
        assert MOD.resolve_apt_packages(frozenset({4})) == ("yamllint",)

    def test_standalone_tool_adds_base_acquisition_packages(self):
        assert MOD.resolve_apt_packages(frozenset({1})) == ("ca-certificates",)

    def test_java_tools_require_headless_jre(self):
        packages = MOD.resolve_apt_packages(frozenset({14, 15}))
        assert "default-jre-headless" in packages

    def test_markdownlint_requires_nodejs_and_npm(self):
        packages = MOD.resolve_apt_packages(frozenset({3}))
        assert {"nodejs", "npm"} <= set(packages)

    def test_golangci_lint_requires_go_toolchain(self):
        assert "golang-go" in MOD.resolve_apt_packages(frozenset({17}))

    def test_cargo_clippy_maps_to_cargo_and_rust_clippy(self):
        packages = MOD.resolve_apt_packages(frozenset({16}))
        assert {"cargo", "rust-clippy"} <= set(packages)

    def test_full_selection_resolves_complete_sorted_set(self):
        packages = MOD.resolve_apt_packages(ALL_NUMBERS)
        assert packages == tuple(sorted(packages))
        assert {
            "yamllint",
            "shellcheck",
            "clang-tidy",
            "cppcheck",
            "clang-format",
            "checkstyle",
            "cargo",
            "rust-clippy",
            "sqlfluff",
            "nodejs",
            "npm",
            "default-jre-headless",
            "golang-go",
            "ca-certificates",
        } == set(packages)

    def test_apt_install_is_one_update_plus_one_install(self, monkeypatch):
        calls: list[list[str]] = []
        monkeypatch.setattr(
            MOD,
            "run_command",
            lambda argv, log, **kwargs: calls.append(list(argv)),
        )
        log = LogStub()
        MOD.apt_install(("pkg-a", "pkg-b"), log)
        assert calls == [
            ["apt-get", "update"],
            [
                "apt-get",
                "install",
                "--yes",
                "--no-install-recommends",
                "pkg-a",
                "pkg-b",
            ],
        ]


# ---------------------------------------------------------------------------
# Secure command execution
# ---------------------------------------------------------------------------


class TestCommandRunner:
    def test_installer_source_never_uses_shell_true(self):
        import ast

        tree = ast.parse(INSTALLER_PATH.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                for keyword in node.keywords:
                    assert keyword.arg != "shell", (
                        f"shell= keyword found at line {node.lineno}"
                    )

    def test_installer_never_imports_ecli_modules(self):
        source = INSTALLER_PATH.read_text(encoding="utf-8")
        assert "import ecli" not in source
        assert "from ecli" not in source

    def test_run_command_rejects_non_string_argv(self):
        with pytest.raises(MOD.InstallerError):
            MOD.run_command(["echo", 42], LogStub(), timeout=5)  # type: ignore[list-item]

    def test_run_command_reports_failure_diagnostics(self):
        with pytest.raises(MOD.InstallerError) as excinfo:
            MOD.run_command(["/bin/sh", "-c", "exit 3"], LogStub(), timeout=5)
        assert "exit 3" in str(excinfo.value)

    def test_run_command_reports_missing_executable(self):
        with pytest.raises(MOD.InstallerError) as excinfo:
            MOD.run_command(["/does/not/exist-xyz"], LogStub(), timeout=5)
        assert "not found" in str(excinfo.value)

    def test_command_environment_never_leaks_caller_env(self, monkeypatch):
        monkeypatch.setenv("SECRET_TOKEN", "hunter2")
        env = MOD.command_environment()
        assert "SECRET_TOKEN" not in env


# ---------------------------------------------------------------------------
# Lock-file validation
# ---------------------------------------------------------------------------


class TestLockValidation:
    def test_committed_lock_passes_and_covers_all_standalone_tools(self):
        lock = MOD.load_lock(REPO_ROOT / "packaging/debian/ecli-linter-lock.json")
        expected_ids = {
            tool.lock_id for tool in MOD.TOOLS if tool.kind in ("payload", "npm")
        }
        assert set(lock) == expected_ids
        assert len(lock) == 11

    def test_committed_lock_uses_https_only_and_real_checksums(self):
        lock = MOD.load_lock(REPO_ROOT / "packaging/debian/ecli-linter-lock.json")
        for tool_id, entry in lock.items():
            assert entry["asset_url"].startswith("https://"), tool_id
            assert entry["source_url"].startswith("https://"), tool_id
            assert len(entry["sha256"]) == 64, tool_id
            assert "latest" not in entry["asset_url"], tool_id
            assert "master" not in str(entry["version"]).lower(), tool_id

    def test_missing_lock_file_raises(self, tmp_path):
        with pytest.raises(MOD.LockError):
            MOD.load_lock(tmp_path / "absent.json")

    def test_lock_entry_rejects_http_url(self):
        entry = {field: "x" for field in MOD.LOCK_REQUIRED_FIELDS}
        entry.update(
            tool_id="ruff",
            source_url="http://example.invalid",
            asset_url="https://example.invalid/a",
            sha256="0" * 64,
            archive_type="tar.gz",
            expected_member="dir/ruff",
            version_command=["ruff", "--version"],
            install_directory="/opt/ecli/payload/bin",
            architecture="amd64",
            version="1.0.0",
            max_download_bytes=10,
        )
        errors = MOD.validate_lock_entry("ruff", entry)
        assert any("https" in error for error in errors)

    def test_lock_entry_rejects_bad_sha256_and_master_version(self):
        entry = {
            "tool_id": "zig",
            "version": "master",
            "source_url": "https://example.invalid",
            "asset_url": "https://example.invalid/zig.tar.xz",
            "sha256": "NOT-HEX",
            "archive_type": "tar.xz",
            "expected_member": "zig/zig",
            "executable_name": "zig",
            "version_command": ["zig", "version"],
            "install_directory": "/opt/ecli/payload/packages/zig/master",
            "architecture": "amd64",
            "license": "MIT",
            "max_download_bytes": 10,
        }
        errors = MOD.validate_lock_entry("zig", entry)
        assert any("sha256" in error for error in errors)
        assert any("master" in error for error in errors)

    def test_lock_entry_rejects_traversal_member_and_foreign_arch(self):
        entry = {
            "tool_id": "ruff",
            "version": "1.0.0",
            "source_url": "https://example.invalid",
            "asset_url": "https://example.invalid/a.tar.gz",
            "sha256": "0" * 64,
            "archive_type": "tar.gz",
            "expected_member": "../escape",
            "executable_name": "ruff",
            "version_command": ["ruff", "--version"],
            "install_directory": "/opt/ecli/payload/bin",
            "architecture": "arm64",
            "license": "MIT",
            "max_download_bytes": 10,
        }
        errors = MOD.validate_lock_entry("ruff", entry)
        assert any("relative path" in error for error in errors)
        assert any("amd64" in error for error in errors)

    def test_npm_lock_dir_validation(self, tmp_path):
        MOD.validate_npm_lock_dir(
            REPO_ROOT / "packaging/debian/markdownlint-cli2", "0.22.1"
        )
        with pytest.raises(MOD.LockError):
            MOD.validate_npm_lock_dir(
                REPO_ROOT / "packaging/debian/markdownlint-cli2", "9.9.9"
            )
        with pytest.raises(MOD.LockError):
            MOD.validate_npm_lock_dir(tmp_path, "0.22.1")

    # -- install_directory boundary hardening ------------------------------

    _BASE_ENTRY = {
        "tool_id": "ruff",
        "version": "1.0.0",
        "source_url": "https://example.invalid/a",
        "asset_url": "https://example.invalid/a.tar.gz",
        "sha256": "0" * 64,
        "archive_type": "tar.gz",
        "expected_member": "dir/ruff",
        "executable_name": "ruff",
        "version_command": ["ruff", "--version"],
        "install_directory": "/opt/ecli/payload/bin",
        "architecture": "amd64",
        "license": "MIT",
        "max_download_bytes": 10,
    }

    @pytest.mark.parametrize(
        "install_directory",
        [
            "/opt/ecli/payload",  # the root itself, not strictly below it
            "/opt/ecli/payload-evil",  # string-prefix lookalike, not a child
            "/opt/ecli/payload/../../etc",  # lexical traversal escapes it
            "opt/ecli/payload/bin",  # not absolute
            "",
        ],
    )
    def test_lock_entry_rejects_unsafe_install_directory(self, install_directory):
        entry = dict(self._BASE_ENTRY, install_directory=install_directory)
        errors = MOD.validate_lock_entry("ruff", entry)
        assert any("install_directory" in error for error in errors), errors

    def test_lock_entry_accepts_genuine_payload_subdirectory(self):
        entry = dict(
            self._BASE_ENTRY,
            install_directory="/opt/ecli/payload/packages/zig/0.16.0",
        )
        assert MOD.validate_lock_entry("ruff", entry) == []

    # -- executable_name / expected_member basename hardening --------------

    @pytest.mark.parametrize(
        "executable_name",
        ["ruff/evil", "..", ".", "ruff;rm -rf /", "ruff$(whoami)", "ruf f", ""],
    )
    def test_lock_entry_rejects_unsafe_executable_name(self, executable_name):
        entry = dict(self._BASE_ENTRY, executable_name=executable_name)
        errors = MOD.validate_lock_entry("ruff", entry)
        assert any("executable_name" in error for error in errors), errors

    @pytest.mark.parametrize(
        "expected_member",
        [
            "../escape",
            "dir/../../escape",
            "/absolute/escape",
            "dir/\x00null",
            "dir/ru`ff`",
            "dir/$(whoami)",
            "dir//double-slash-empty-segment",
            "~root/escape",
        ],
    )
    def test_lock_entry_rejects_unsafe_expected_member(self, expected_member):
        entry = dict(self._BASE_ENTRY, expected_member=expected_member)
        errors = MOD.validate_lock_entry("ruff", entry)
        assert any("expected_member" in error for error in errors), errors

    def test_lock_entry_accepts_legitimate_multi_segment_member(self):
        entry = dict(
            self._BASE_ENTRY, expected_member="node_modules/.bin/markdownlint-cli2"
        )
        assert MOD.validate_lock_entry("ruff", entry) == []

    # -- mutable URL reference hardening -------------------------------

    @pytest.mark.parametrize(
        "url",
        [
            "https://github.com/x/y/releases/latest/download/z.tar.gz",
            "https://ziglang.org/builds/zig-x86_64-linux-master.tar.xz",
        ],
    )
    def test_lock_entry_rejects_mutable_reference_urls(self, url):
        entry = dict(self._BASE_ENTRY, asset_url=url)
        errors = MOD.validate_lock_entry("ruff", entry)
        assert any("mutable" in error for error in errors), errors

    # -- standalone helper-function unit coverage ---------------------------

    @pytest.mark.parametrize(
        "name,expected",
        [
            ("ruff", True),
            ("markdownlint-cli2", True),
            (".bin", True),
            ("a.b_c-9", True),
            ("", False),
            (".", False),
            ("..", False),
            ("a/b", False),
            ("a\\b", False),
            ("a\x00b", False),
            ("a;b", False),
            ("a b", False),
            ("$(a)", False),
        ],
    )
    def test_is_safe_basename(self, name, expected):
        assert MOD.is_safe_basename(name) is expected

    @pytest.mark.parametrize(
        "member,expected",
        [
            ("ruff", True),
            ("dir/ruff", True),
            ("node_modules/.bin/markdownlint-cli2", True),
            ("../escape", False),
            ("dir/../escape", False),
            ("/abs", False),
            ("~x", False),
            ("dir//x", False),
            ("dir/\x00", False),
            ("dir\\x", False),
        ],
    )
    def test_is_safe_relative_member(self, member, expected):
        assert MOD.is_safe_relative_member(member) is expected

    def test_has_mutable_reference(self):
        assert MOD.has_mutable_reference("https://x/releases/latest/y")
        assert MOD.has_mutable_reference("https://x/MASTER/y")
        assert not MOD.has_mutable_reference(
            "https://github.com/a/b/releases/download/v1.0/c"
        )


# ---------------------------------------------------------------------------
# Downloads: HTTPS-only, checksum mismatch, interruption
# ---------------------------------------------------------------------------


class _FakeResponse:
    def __init__(self, payload: bytes, *, fail_after: int | None = None) -> None:
        """Serve ``payload``, optionally failing after N reads."""
        self._buffer = io.BytesIO(payload)
        self._fail_after = fail_after
        self._reads = 0
        self.status = 200

    def read(self, size: int) -> bytes:
        self._reads += 1
        if self._fail_after is not None and self._reads > self._fail_after:
            raise OSError("connection interrupted")
        return self._buffer.read(size)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class _FakeOpener:
    def __init__(self, responses) -> None:
        """Queue canned responses for successive open() calls."""
        self._responses = list(responses)
        self.requests = 0

    def open(self, request, timeout=None):
        self.requests += 1
        return self._responses.pop(0)


class TestDownloads:
    def test_non_https_url_refused(self, payload_env):
        with pytest.raises(MOD.DownloadError):
            MOD.download_verified(
                "http://example.invalid/tool",
                payload_env["PAYLOAD_CACHE"] / "tool",
                "0" * 64,
                10,
                LogStub(),
            )

    def test_redirect_handler_refuses_downgrade(self):
        handler = MOD._HttpsOnlyRedirectHandler()
        with pytest.raises(MOD.DownloadError):
            handler.redirect_request(
                None, None, 302, "Found", {}, "http://example.invalid/x"
            )

    def test_checksum_mismatch_fails_and_cleans_partials(
        self, payload_env, monkeypatch
    ):
        payload = b"tool-bytes"
        opener = _FakeOpener([_FakeResponse(payload)])
        monkeypatch.setattr(
            MOD.urllib.request, "build_opener", lambda *handlers: opener
        )
        destination = payload_env["PAYLOAD_CACHE"] / "tool.bin"
        with pytest.raises(MOD.DownloadError) as excinfo:
            MOD.download_verified(
                "https://example.invalid/tool.bin",
                destination,
                "f" * 64,
                len(payload),
                LogStub(),
            )
        assert "SHA-256 mismatch" in str(excinfo.value)
        assert not destination.exists()
        assert not destination.with_name("tool.bin.part").exists()
        assert opener.requests == 1, "checksum mismatch must not be retried"

    def test_oversize_download_aborted(self, payload_env, monkeypatch):
        payload = b"x" * 64
        opener = _FakeOpener([_FakeResponse(payload)])
        monkeypatch.setattr(
            MOD.urllib.request, "build_opener", lambda *handlers: opener
        )
        destination = payload_env["PAYLOAD_CACHE"] / "big.bin"
        with pytest.raises(MOD.DownloadError) as excinfo:
            MOD.download_verified(
                "https://example.invalid/big.bin",
                destination,
                hashlib.sha256(payload).hexdigest(),
                8,
                LogStub(),
            )
        assert "maximum expected size" in str(excinfo.value)
        assert not destination.with_name("big.bin.part").exists()

    def test_interrupted_download_retries_then_fails_clean(
        self, payload_env, monkeypatch
    ):
        payload = b"y" * (2 << 20)
        opener = _FakeOpener([_FakeResponse(payload, fail_after=1) for _ in range(3)])
        monkeypatch.setattr(
            MOD.urllib.request, "build_opener", lambda *handlers: opener
        )
        destination = payload_env["PAYLOAD_CACHE"] / "flaky.bin"
        with pytest.raises(MOD.DownloadError):
            MOD.download_verified(
                "https://example.invalid/flaky.bin",
                destination,
                hashlib.sha256(payload).hexdigest(),
                len(payload),
                LogStub(),
            )
        assert opener.requests == 3
        assert not destination.exists()
        assert not destination.with_name("flaky.bin.part").exists()

    def test_successful_download_verifies_and_renames_atomically(
        self, payload_env, monkeypatch
    ):
        payload = b"verified-bytes"
        opener = _FakeOpener([_FakeResponse(payload)])
        monkeypatch.setattr(
            MOD.urllib.request, "build_opener", lambda *handlers: opener
        )
        destination = payload_env["PAYLOAD_CACHE"] / "good.bin"
        result = MOD.download_verified(
            "https://example.invalid/good.bin",
            destination,
            hashlib.sha256(payload).hexdigest(),
            len(payload),
            LogStub(),
        )
        assert result == destination
        assert destination.read_bytes() == payload
        assert not destination.with_name("good.bin.part").exists()

    def test_verified_cache_is_reused_without_network(self, payload_env):
        payload = b"cached"
        destination = payload_env["PAYLOAD_CACHE"] / "cached.bin"
        destination.write_bytes(payload)
        result = MOD.download_verified(
            "https://example.invalid/cached.bin",
            destination,
            hashlib.sha256(payload).hexdigest(),
            len(payload),
            LogStub(),
        )
        assert result == destination


# ---------------------------------------------------------------------------
# Safe extraction
# ---------------------------------------------------------------------------


class TestSafeExtraction:
    def test_plain_members_extract_with_by_type_modes(self, tmp_path):
        archive = tmp_path / "ok.tar.gz"
        _make_tar_gz(
            archive,
            {"dir/tool": b"#!/bin/sh\n", "dir/README": b"docs"},
            mode=0o755,
        )
        destination = tmp_path / "out"
        MOD.safe_extract_tar(archive, destination)
        tool_mode = stat.S_IMODE((destination / "dir/tool").stat().st_mode)
        assert tool_mode == 0o755

    @pytest.mark.parametrize("name", ["../evil", "/abs/evil", "a/../../evil"])
    def test_traversal_members_rejected(self, tmp_path, name):
        archive = tmp_path / "bad.tar.gz"
        _make_tar_gz(archive, {name: b"x"})
        with pytest.raises(MOD.ExtractionError):
            MOD.safe_extract_tar(archive, tmp_path / "out")

    def test_symlink_escape_rejected(self, tmp_path):
        archive = tmp_path / "link.tar.gz"
        with tarfile.open(archive, "w:gz") as handle:
            info = tarfile.TarInfo("escape")
            info.type = tarfile.SYMTYPE
            info.linkname = "../../etc/passwd"
            handle.addfile(info)
        with pytest.raises(MOD.ExtractionError):
            MOD.safe_extract_tar(archive, tmp_path / "out")

    def test_absolute_symlink_rejected(self, tmp_path):
        archive = tmp_path / "abslink.tar.gz"
        with tarfile.open(archive, "w:gz") as handle:
            info = tarfile.TarInfo("abs")
            info.type = tarfile.SYMTYPE
            info.linkname = "/etc/passwd"
            handle.addfile(info)
        with pytest.raises(MOD.ExtractionError):
            MOD.safe_extract_tar(archive, tmp_path / "out")

    def test_hardlink_escape_rejected(self, tmp_path):
        archive = tmp_path / "hard.tar.gz"
        with tarfile.open(archive, "w:gz") as handle:
            info = tarfile.TarInfo("hard")
            info.type = tarfile.LNKTYPE
            info.linkname = "../outside"
            handle.addfile(info)
        with pytest.raises(MOD.ExtractionError):
            MOD.safe_extract_tar(archive, tmp_path / "out")

    def test_device_and_fifo_members_rejected(self, tmp_path):
        archive = tmp_path / "dev.tar.gz"
        with tarfile.open(archive, "w:gz") as handle:
            info = tarfile.TarInfo("null")
            info.type = tarfile.CHRTYPE
            handle.addfile(info)
        with pytest.raises(MOD.ExtractionError):
            MOD.safe_extract_tar(archive, tmp_path / "out")
        archive2 = tmp_path / "fifo.tar.gz"
        with tarfile.open(archive2, "w:gz") as handle:
            info = tarfile.TarInfo("pipe")
            info.type = tarfile.FIFOTYPE
            handle.addfile(info)
        with pytest.raises(MOD.ExtractionError):
            MOD.safe_extract_tar(archive2, tmp_path / "out")

    def test_setuid_members_rejected(self, tmp_path):
        archive = tmp_path / "suid.tar.gz"
        _make_tar_gz(archive, {"tool": b"x"}, mode=0o4755)
        with pytest.raises(MOD.ExtractionError):
            MOD.safe_extract_tar(archive, tmp_path / "out")

    def test_zip_traversal_rejected(self, tmp_path):
        archive = tmp_path / "bad.zip"
        with zipfile.ZipFile(archive, "w") as handle:
            handle.writestr("../evil", b"x")
        with pytest.raises(MOD.ExtractionError):
            MOD.safe_extract_zip(archive, tmp_path / "out")

    def test_tar_duplicate_member_rejected(self, tmp_path):
        """A repeated path could silently overwrite an already-validated
        entry with attacker-controlled content; reject outright.
        """
        archive = tmp_path / "dup.tar.gz"
        with tarfile.open(archive, "w:gz") as handle:
            for payload in (b"benign", b"malicious-overwrite"):
                info = tarfile.TarInfo("dir/tool")
                info.size = len(payload)
                handle.addfile(info, io.BytesIO(payload))
        with pytest.raises(MOD.ExtractionError, match="duplicated"):
            MOD.safe_extract_tar(archive, tmp_path / "out")

    def test_zip_duplicate_member_rejected(self, tmp_path):
        archive = tmp_path / "dup.zip"
        with zipfile.ZipFile(archive, "w") as handle:
            handle.writestr("dir/tool", b"benign")
            handle.writestr("dir/tool", b"malicious-overwrite")
        with pytest.raises(MOD.ExtractionError, match="duplicated"):
            MOD.safe_extract_zip(archive, tmp_path / "out")

    def test_tar_duplicate_via_normpath_equivalence_rejected(self, tmp_path):
        """Different literal strings that normalize to the same path are
        just as ambiguous as an exact repeat.
        """
        archive = tmp_path / "dup2.tar.gz"
        with tarfile.open(archive, "w:gz") as handle:
            for name, payload in (
                ("dir/tool", b"first"),
                ("dir/./tool", b"second-ambiguous"),
            ):
                info = tarfile.TarInfo(name)
                info.size = len(payload)
                handle.addfile(info, io.BytesIO(payload))
        with pytest.raises(MOD.ExtractionError, match="duplicated"):
            MOD.safe_extract_tar(archive, tmp_path / "out")

    def test_stage_archive_requires_exact_expected_member(self, tmp_path):
        archive = tmp_path / "ruff.tar.gz"
        _make_tar_gz(archive, {"unexpected/other": b"x"})
        entry = {
            "archive_type": "tar.gz",
            "expected_member": "ruff-x86_64-unknown-linux-gnu/ruff",
        }
        with pytest.raises(MOD.ExtractionError) as excinfo:
            MOD.stage_archive(entry, archive, tmp_path / "stage")
        assert "expected archive member" in str(excinfo.value)

    def test_stage_archive_gz_single_member(self, tmp_path):
        import gzip as gzip_mod

        archive = tmp_path / "taplo.gz"
        archive.write_bytes(gzip_mod.compress(b"#!/bin/sh\necho taplo\n"))
        entry = {
            "archive_type": "gz",
            "expected_member": "taplo",
            "architecture": "amd64",
        }
        staged = MOD.stage_archive(entry, archive, tmp_path / "stage")
        assert staged.name == "taplo"
        assert stat.S_IMODE(staged.stat().st_mode) == 0o755


# ---------------------------------------------------------------------------
# ELF architecture verification
# ---------------------------------------------------------------------------


def _fake_elf_header(e_machine: int) -> bytes:
    """Minimal 20-byte prefix with a real ELF magic and a given e_machine."""
    header = bytearray(20)
    header[0:4] = b"\x7fELF"
    header[18:20] = e_machine.to_bytes(2, byteorder="little")
    return bytes(header)


class TestElfArchitectureVerification:
    def test_accepts_matching_x86_64_elf(self, tmp_path):
        path = tmp_path / "tool"
        path.write_bytes(_fake_elf_header(MOD._EM_X86_64))
        MOD.verify_elf_architecture(path, "amd64")  # does not raise

    def test_rejects_foreign_architecture_elf(self, tmp_path):
        path = tmp_path / "tool"
        aarch64_machine = 0xB7
        path.write_bytes(_fake_elf_header(aarch64_machine))
        with pytest.raises(MOD.ExtractionError, match="e_machine"):
            MOD.verify_elf_architecture(path, "amd64")

    def test_rejects_truncated_elf_header(self, tmp_path):
        path = tmp_path / "tool"
        path.write_bytes(b"\x7fELF\x01\x02")
        with pytest.raises(MOD.ExtractionError, match="truncated"):
            MOD.verify_elf_architecture(path, "amd64")

    def test_skips_non_elf_shell_script(self, tmp_path):
        path = tmp_path / "tool"
        path.write_bytes(b"#!/bin/sh\nexec java -jar app.jar\n")
        MOD.verify_elf_architecture(path, "amd64")  # does not raise

    def test_stage_archive_rejects_wrong_architecture_binary(self, tmp_path):
        archive = tmp_path / "tool.tar.gz"
        _make_tar_gz(archive, {"dir/tool": _fake_elf_header(0xB7)})
        entry = {
            "archive_type": "tar.gz",
            "expected_member": "dir/tool",
            "architecture": "amd64",
        }
        with pytest.raises(MOD.ExtractionError, match="e_machine"):
            MOD.stage_archive(entry, archive, tmp_path / "stage")


# ---------------------------------------------------------------------------
# Wrapper generation safety
# ---------------------------------------------------------------------------


class TestWrapperSafety:
    def test_wrapper_embeds_absolute_target_verbatim(self):
        target = Path("/opt/ecli/payload/packages/pmd/7.26.0/bin/pmd")
        content = MOD.wrapper_script_content(target)
        assert content.startswith("#!/bin/sh\n")
        assert f'exec "{target}" "$@"' in content

    def test_wrapper_rejects_relative_target(self):
        with pytest.raises(MOD.InstallerError, match="absolute"):
            MOD.wrapper_script_content(Path("relative/pmd"))

    @pytest.mark.parametrize("unsafe_char", ['"', "`", "$", "\\"])
    def test_wrapper_rejects_shell_unsafe_characters(self, unsafe_char):
        target = Path(f"/opt/ecli/payload/{unsafe_char}evil/pmd")
        with pytest.raises(MOD.InstallerError, match="unsafe character"):
            MOD.wrapper_script_content(target)

    def test_wrapper_rejects_control_characters(self):
        target = Path("/opt/ecli/payload/evil\nrm -rf /\npmd")
        with pytest.raises(MOD.InstallerError, match="unsafe character"):
            MOD.wrapper_script_content(target)


# ---------------------------------------------------------------------------
# Process-level installer lock
# ---------------------------------------------------------------------------


class TestInstallerProcessLock:
    def test_second_concurrent_instance_is_rejected(self, tmp_path):
        lock_path = tmp_path / "installer.lock"
        with MOD.installer_process_lock(lock_path):
            with pytest.raises(MOD.InstallerLockHeldError):
                with MOD.installer_process_lock(lock_path):
                    pass  # pragma: no cover - must never be entered

    def test_lock_is_released_after_the_context_exits(self, tmp_path):
        lock_path = tmp_path / "installer.lock"
        with MOD.installer_process_lock(lock_path):
            pass
        with MOD.installer_process_lock(lock_path):
            pass  # a fresh acquisition after release must succeed

    def test_lock_is_released_even_when_the_body_raises(self, tmp_path):
        lock_path = tmp_path / "installer.lock"
        with pytest.raises(RuntimeError, match="boom"):
            with MOD.installer_process_lock(lock_path):
                raise RuntimeError("boom")
        with MOD.installer_process_lock(lock_path):
            pass  # still released despite the exception


# ---------------------------------------------------------------------------
# Idempotency, managed upgrade, corrupt binaries
# ---------------------------------------------------------------------------


@pytest.fixture
def managed_ruff(payload_env, tmp_path, monkeypatch):
    """A PayloadInstaller with a fake downloadable ruff 0.15.21 archive."""
    script = _fake_tool_script("ruff 0.15.21")
    archive = tmp_path / "fixture-ruff.tar.gz"
    _make_tar_gz(archive, {"ruff-x86_64-unknown-linux-gnu/ruff": script})
    entry = _ruff_lock_entry(archive, script)
    monkeypatch.setattr(
        MOD,
        "download_verified",
        lambda url, dest, sha, max_bytes, log, **kwargs: archive,
    )
    log = LogStub()
    state: dict = {}
    installer = MOD.PayloadInstaller(
        {"ruff": entry}, state, log, REPO_ROOT / "packaging/debian/markdownlint-cli2"
    )
    ruff_tool = MOD.TOOLS_BY_NUMBER[1]
    return installer, ruff_tool, entry, log


class TestIdempotencyAndUpgrade:
    def test_fresh_install_promotes_binary_and_records_state(self, managed_ruff):
        installer, tool, entry, _log = managed_ruff
        installer.install(tool)
        target = MOD.PAYLOAD_BIN / "ruff"
        assert target.is_file()
        assert stat.S_IMODE(target.stat().st_mode) == 0o755
        state = MOD.read_state()
        assert state["ruff"]["version"] == "0.15.21"
        assert state["ruff"]["installed_sha256"] == MOD.sha256_of_file(target)

    def test_reinstall_skips_verified_current_version(self, managed_ruff):
        installer, tool, entry, log = managed_ruff
        installer.install(tool)
        first_mtime = (MOD.PAYLOAD_BIN / "ruff").stat().st_mtime_ns
        installer.install(tool)
        assert (MOD.PAYLOAD_BIN / "ruff").stat().st_mtime_ns == first_mtime
        assert "skipping reinstall" in log.text

    def test_corrupt_managed_binary_is_reinstalled(self, managed_ruff):
        installer, tool, entry, log = managed_ruff
        installer.install(tool)
        target = MOD.PAYLOAD_BIN / "ruff"
        target.write_bytes(b"corrupted")
        installer.install(tool)
        assert "does not match recorded checksum" in log.text
        assert target.read_bytes() == _fake_tool_script("ruff 0.15.21")

    def test_outdated_managed_version_is_upgraded(self, managed_ruff):
        installer, tool, entry, _log = managed_ruff
        installer.install(tool)
        installer.state["ruff"]["version"] = "0.15.20"
        MOD.write_state(installer.state)
        installer.install(tool)
        assert MOD.read_state()["ruff"]["version"] == "0.15.21"

    def test_unmanaged_file_is_never_overwritten(self, managed_ruff):
        installer, tool, entry, _log = managed_ruff
        target = MOD.PAYLOAD_BIN / "ruff"
        target.write_text("user-owned file", encoding="utf-8")
        with pytest.raises(MOD.InstallerError) as excinfo:
            installer.install(tool)
        assert "unmanaged" in str(excinfo.value)
        assert target.read_text(encoding="utf-8") == "user-owned file"

    def test_failed_staged_probe_retains_previous_installation(
        self, managed_ruff, tmp_path, monkeypatch
    ):
        installer, tool, entry, _log = managed_ruff
        installer.install(tool)
        good = (MOD.PAYLOAD_BIN / "ruff").read_bytes()
        broken_archive = tmp_path / "broken.tar.gz"
        _make_tar_gz(
            broken_archive,
            {"ruff-x86_64-unknown-linux-gnu/ruff": b"#!/bin/sh\nexit 9\n"},
        )
        entry["version"] = "0.15.22"
        entry["sha256"] = hashlib.sha256(broken_archive.read_bytes()).hexdigest()
        monkeypatch.setattr(
            MOD,
            "download_verified",
            lambda url, dest, sha, max_bytes, log, **kwargs: broken_archive,
        )
        with pytest.raises(MOD.InstallerError):
            installer.install(tool)
        assert (MOD.PAYLOAD_BIN / "ruff").read_bytes() == good

    def test_tree_tool_install_creates_exec_wrapper_not_symlink(
        self, payload_env, tmp_path, monkeypatch
    ):
        """PMD-style tools break behind symlinks; bin entry must be a wrapper."""
        import subprocess

        script = _fake_tool_script("PMD 7.26.0")
        archive = tmp_path / "fixture-pmd.tar.gz"
        _make_tar_gz(archive, {"pmd-bin-7.26.0/bin/pmd": script})
        entry = {
            "tool_id": "pmd",
            "version": "7.26.0",
            "source_url": "https://example.invalid/pmd",
            "asset_url": "https://example.invalid/pmd.tar.gz",
            "sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
            "archive_type": "tar.gz",
            "expected_member": "pmd-bin-7.26.0/bin/pmd",
            "executable_name": "pmd",
            "version_command": ["pmd", "--version"],
            "install_directory": str(MOD.PAYLOAD_PACKAGES / "pmd" / "7.26.0"),
            "architecture": "amd64",
            "license": "BSD-2-Clause",
            "max_download_bytes": max(archive.stat().st_size, 1),
        }
        monkeypatch.setattr(
            MOD,
            "download_verified",
            lambda url, dest, sha, max_bytes, log, **kwargs: archive,
        )
        installer = MOD.PayloadInstaller(
            {"pmd": entry},
            {},
            LogStub(),
            REPO_ROOT / "packaging/debian/markdownlint-cli2",
        )
        installer.install(MOD.TOOLS_BY_NUMBER[14])
        inner = MOD.PAYLOAD_PACKAGES / "pmd" / "7.26.0" / "bin" / "pmd"
        assert inner.is_file()
        wrapper = MOD.PAYLOAD_BIN / "pmd"
        assert wrapper.is_file() and not wrapper.is_symlink()
        assert stat.S_IMODE(wrapper.stat().st_mode) == 0o755
        content = wrapper.read_text(encoding="utf-8")
        assert content.startswith("#!/bin/sh\n")
        assert f'exec "{inner}" "$@"' in content
        probe = subprocess.run(
            [str(wrapper), "--version"], capture_output=True, text=True, check=True
        )
        assert "PMD 7.26.0" in probe.stdout

    def test_normalize_tree_ownership_applies_by_type_modes(self, tmp_path):
        """Staging must reset npm-preserved upstream tarball modes/owners."""
        tree = tmp_path / "nodejs"
        (tree / "node_modules" / "pkg").mkdir(parents=True)
        loose_dir = tree / "node_modules" / "pkg"
        os.chmod(loose_dir, 0o775)
        data_file = loose_dir / "index.js"
        data_file.write_text("x", encoding="utf-8")
        os.chmod(data_file, 0o664)
        exe_file = loose_dir / "cli.js"
        exe_file.write_text("#!/usr/bin/env node\n", encoding="utf-8")
        os.chmod(exe_file, 0o775)
        link = tree / "node_modules" / "link.js"
        link.symlink_to("pkg/index.js")
        MOD.normalize_tree_ownership(tree)
        assert stat.S_IMODE(loose_dir.stat().st_mode) == 0o755
        assert stat.S_IMODE(data_file.stat().st_mode) == 0o644
        assert stat.S_IMODE(exe_file.stat().st_mode) == 0o755
        assert link.is_symlink()


# ---------------------------------------------------------------------------
# PATH script idempotency
# ---------------------------------------------------------------------------


class TestProfileScript:
    def test_profile_script_written_idempotently(self, payload_env):
        log = LogStub()
        MOD.install_profile_script(log)
        first = MOD.PROFILE_SCRIPT.read_text(encoding="utf-8")
        MOD.install_profile_script(log)
        assert MOD.PROFILE_SCRIPT.read_text(encoding="utf-8") == first
        assert "already up to date" in log.text
        assert first.count("/opt/ecli/payload/bin") >= 2
        assert 'case ":$PATH:"' in first
        # Deterministic precedence: the payload directory is PREPENDED so
        # lock-pinned managed tools shadow same-named host executables.
        assert 'PATH="/opt/ecli/payload/bin:$PATH"' in first
        assert 'PATH="$PATH:' not in first
        mode = stat.S_IMODE(MOD.PROFILE_SCRIPT.stat().st_mode)
        assert mode == 0o644

    def test_profile_prepend_shadows_stale_host_tool(self, payload_env, tmp_path):
        import subprocess

        payload_like = tmp_path / "payload-bin"
        payload_like.mkdir()
        stale_dir = tmp_path / "usr-local-bin"
        stale_dir.mkdir()
        for directory, marker in ((payload_like, "managed"), (stale_dir, "stale")):
            tool = directory / "ruff"
            tool.write_bytes(_fake_tool_script(f"ruff {marker}"))
            tool.chmod(0o755)
        script = tmp_path / "ecli_payload.sh"
        script.write_text(
            MOD.PROFILE_CONTENT.replace("/opt/ecli/payload/bin", str(payload_like)),
            encoding="utf-8",
        )
        result = subprocess.run(
            [
                "/bin/sh",
                "-c",
                f'PATH="{stale_dir}:/usr/bin:/bin"; . "{script}"; ruff --version',
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        assert "ruff managed" in result.stdout

    def test_profile_guard_prevents_duplicate_path_entries(self, payload_env, tmp_path):
        import subprocess

        # The committed content guards on the canonical directory, which
        # does not exist in the test sandbox; substitute an existing
        # directory to exercise the duplicate-entry guard itself.
        existing = tmp_path / "payload-bin"
        existing.mkdir()
        script = tmp_path / "ecli_payload.sh"
        script.write_text(
            MOD.PROFILE_CONTENT.replace("/opt/ecli/payload/bin", str(existing)),
            encoding="utf-8",
        )
        result = subprocess.run(
            [
                "/bin/sh",
                "-c",
                f'PATH=/usr/bin; . "{script}"; . "{script}"; printf "%s" "$PATH"',
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        assert result.stdout.count(str(existing)) == 1


# ---------------------------------------------------------------------------
# State-file atomicity
# ---------------------------------------------------------------------------


class TestStateFile:
    def test_state_written_atomically_without_temp_residue(self, payload_env):
        MOD.write_state({"ruff": {"version": "0.15.21"}})
        state_dir = MOD.STATE_FILE.parent
        leftovers = [
            path for path in state_dir.iterdir() if path.name != MOD.STATE_FILE.name
        ]
        assert leftovers == []
        assert MOD.read_state()["ruff"]["version"] == "0.15.21"

    def test_corrupt_state_file_tolerated(self, payload_env):
        MOD.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        MOD.STATE_FILE.write_text("{ not json", encoding="utf-8")
        assert MOD.read_state() == {}


# ---------------------------------------------------------------------------
# Version probes (including stderr output) and final report
# ---------------------------------------------------------------------------


@pytest.fixture
def probe_env(tmp_path, monkeypatch):
    """Sandbox PROBE_PATH with a writable approved tool directory."""
    tools_dir = tmp_path / "probe-bin"
    tools_dir.mkdir()
    monkeypatch.setattr(MOD, "PROBE_PATH", f"{tools_dir}:/usr/bin:/bin")
    monkeypatch.setattr(
        MOD,
        "APPROVED_PATH_PREFIXES",
        (f"{tools_dir}/", "/usr/bin/", "/bin/"),
    )
    return tools_dir


def _write_probe_tool(directory: Path, name: str, body: bytes) -> Path:
    path = directory / name
    path.write_bytes(body)
    path.chmod(0o755)
    return path


class TestVersionProbes:
    def test_probe_path_prepends_payload_and_avoids_usr_local(self):
        assert MOD.PROBE_PATH.startswith(str(MOD.PAYLOAD_BIN))
        assert "/usr/local" not in MOD.PROBE_PATH
        assert not any(
            prefix.startswith("/usr/local") for prefix in MOD.APPROVED_PATH_PREFIXES
        )

    def test_probe_resolves_payload_tool_over_stale_shadow(self, tmp_path, monkeypatch):
        """A same-named stale executable later in PATH must never win."""
        payload_like = tmp_path / "payload-bin"
        stale_dir = tmp_path / "stale-bin"
        payload_like.mkdir()
        stale_dir.mkdir()
        _write_probe_tool(payload_like, "ruff", _fake_tool_script("ruff 0.15.21"))
        _write_probe_tool(stale_dir, "ruff", _fake_tool_script("ruff 0.0.1-stale"))
        monkeypatch.setattr(MOD, "PROBE_PATH", f"{payload_like}:{stale_dir}")
        monkeypatch.setattr(
            MOD, "APPROVED_PATH_PREFIXES", (f"{payload_like}/", f"{stale_dir}/")
        )
        lock = {"ruff": {"version": "0.15.21"}}
        result = MOD.probe_tool(MOD.TOOLS_BY_NUMBER[1], lock, LogStub())
        assert result.status == "OK"
        assert result.path.startswith(str(payload_like))

    def test_toolchain_split_is_eleven_managed_eight_debian(self):
        managed = [tool for tool in MOD.TOOLS if tool.kind in ("payload", "npm")]
        debian = [tool for tool in MOD.TOOLS if tool.kind == "apt"]
        assert len(managed) == 11
        assert len(debian) == 8
        assert len(MOD.TOOLS) == 19

    def test_probe_success_on_stdout(self, probe_env):
        _write_probe_tool(probe_env, "yamllint", _fake_tool_script("yamllint 1.35.1"))
        result = MOD.probe_tool(MOD.TOOLS_BY_NUMBER[4], {}, LogStub())
        assert result.status == "OK"
        assert "yamllint" in result.version

    def test_probe_success_when_version_only_on_stderr(self, probe_env):
        _write_probe_tool(
            probe_env,
            "checkstyle",
            _fake_tool_script("Checkstyle version: 10.17.0", to_stderr=True),
        )
        result = MOD.probe_tool(MOD.TOOLS_BY_NUMBER[13], {}, LogStub())
        assert result.status == "OK"

    def test_probe_fails_for_missing_executable(self, probe_env):
        result = MOD.probe_tool(MOD.TOOLS_BY_NUMBER[5], {}, LogStub())
        assert result.status == "FAILED"
        assert "not found" in result.detail

    def test_probe_fails_on_nonzero_exit(self, probe_env):
        _write_probe_tool(probe_env, "yamllint", b"#!/bin/sh\nexit 2\n")
        result = MOD.probe_tool(MOD.TOOLS_BY_NUMBER[4], {}, LogStub())
        assert result.status == "FAILED"

    def test_probe_fails_on_empty_output(self, probe_env):
        _write_probe_tool(probe_env, "yamllint", b"#!/bin/sh\nexit 0\n")
        result = MOD.probe_tool(MOD.TOOLS_BY_NUMBER[4], {}, LogStub())
        assert result.status == "FAILED"
        assert "no output" in result.detail

    def test_probe_requires_locked_version_for_managed_tools(self, probe_env):
        _write_probe_tool(probe_env, "ruff", _fake_tool_script("ruff 0.15.20"))
        lock = {"ruff": {"version": "0.15.21"}}
        result = MOD.probe_tool(MOD.TOOLS_BY_NUMBER[1], lock, LogStub())
        assert result.status == "FAILED"
        assert "0.15.21" in result.detail

    def test_probe_accepts_locked_version_for_managed_tools(self, probe_env):
        _write_probe_tool(probe_env, "ruff", _fake_tool_script("ruff 0.15.21"))
        lock = {"ruff": {"version": "0.15.21"}}
        result = MOD.probe_tool(MOD.TOOLS_BY_NUMBER[1], lock, LogStub())
        assert result.status == "OK"
        assert result.version == "0.15.21"

    def test_checkstyle_probe_falls_back_to_double_dash_version(self, probe_env):
        """Debian 13 checkstyle (picocli CLI) rejects -version; --version works."""
        _write_probe_tool(
            probe_env,
            "checkstyle",
            b'#!/bin/sh\ncase "$1" in\n'
            b'--version) echo "Checkstyle version: 8.36.1" ;;\n'
            b"*) echo \"Missing required parameter: '<files>'\" 1>&2; exit 255 ;;\n"
            b"esac\n",
        )
        result = MOD.probe_tool(MOD.TOOLS_BY_NUMBER[13], {}, LogStub())
        assert result.status == "OK"
        assert "Checkstyle version" in result.version

    def test_fallback_failure_still_fails_with_one_line_detail(self, probe_env):
        _write_probe_tool(
            probe_env,
            "checkstyle",
            b'#!/bin/sh\necho "usage line one" 1>&2\necho "line two" 1>&2\nexit 255\n',
        )
        result = MOD.probe_tool(MOD.TOOLS_BY_NUMBER[13], {}, LogStub())
        assert result.status == "FAILED"
        assert "\n" not in result.detail


class TestFinalReport:
    @staticmethod
    def _ok(tool):
        return MOD.ToolResult(tool, "OK", version="1.0", path="/usr/bin/x")

    def test_full_nineteen_tool_success_message(self):
        results = {tool.number: self._ok(tool) for tool in MOD.TOOLS}
        log = LogStub()
        rc = MOD.print_final_report(results, ALL_NUMBERS, log)
        assert rc == MOD.EXIT_OK
        assert (
            "ECLI linter installation completed successfully: "
            "19/19 tools verified." in log.text
        )

    def test_custom_selection_success_message(self):
        results = {tool.number: MOD.ToolResult(tool, "SKIPPED") for tool in MOD.TOOLS}
        for number in (1, 4, 5):
            results[number] = self._ok(MOD.TOOLS_BY_NUMBER[number])
        log = LogStub()
        rc = MOD.print_final_report(results, frozenset({1, 4, 5}), log)
        assert rc == MOD.EXIT_OK
        assert "3/3 selected tools verified" in log.text
        assert "not selected" in log.text

    def test_partial_failure_returns_nonzero_without_success_message(self):
        results = {tool.number: self._ok(tool) for tool in MOD.TOOLS}
        results[14] = MOD.ToolResult(
            MOD.TOOLS_BY_NUMBER[14],
            "FAILED",
            detail="download failed",
            stage="install",
        )
        log = LogStub()
        rc = MOD.print_final_report(results, ALL_NUMBERS, log)
        assert rc == MOD.EXIT_INSTALL_FAILED
        assert "completed successfully" not in log.text
        assert "[FAILED]" in log.text
        assert "PMD" in log.text
        assert "no APT rollback" in log.text

    def test_report_line_layout(self):
        ok_line = MOD.format_report_line(self._ok(MOD.TOOLS_BY_NUMBER[1]))
        assert ok_line.startswith("[OK]      Ruff")
        skip_line = MOD.format_report_line(
            MOD.ToolResult(MOD.TOOLS_BY_NUMBER[5], "SKIPPED")
        )
        assert skip_line.startswith("[SKIPPED] ShellCheck")
        assert skip_line.endswith("not selected")

    def test_every_required_probe_contract_is_declared(self):
        expected = {
            1: ("ruff", "--version"),
            2: ("biome", "--version"),
            3: ("markdownlint-cli2", "--version"),
            4: ("yamllint", "--version"),
            5: ("shellcheck", "--version"),
            6: ("zig", "version"),
            7: ("hadolint", "--version"),
            8: ("taplo", "--version"),
            9: ("actionlint", "-version"),
            10: ("clang-tidy", "--version"),
            11: ("cppcheck", "--version"),
            12: ("clang-format", "--version"),
            13: ("checkstyle", "-version"),
            14: ("pmd", "--version"),
            15: ("spotbugs", "-version"),
            16: ("cargo", "clippy", "--version"),
            17: ("golangci-lint", "--version"),
            18: ("sqlfluff", "--version"),
            19: ("tflint", "--version"),
        }
        for number, command in expected.items():
            assert MOD.TOOLS_BY_NUMBER[number].version_command == command


# ---------------------------------------------------------------------------
# Partial failure of the orchestrated run
# ---------------------------------------------------------------------------


class TestRunInstallation:
    def test_apt_failure_fails_all_selected_tools(self, payload_env, monkeypatch):
        monkeypatch.setattr(
            MOD,
            "apt_install",
            lambda packages, log: (_ for _ in ()).throw(
                MOD.InstallerError("mirror unreachable")
            ),
        )
        log = LogStub()
        rc = MOD.run_installation(
            frozenset({4, 5}),
            {},
            REPO_ROOT / "packaging/debian/markdownlint-cli2",
            log,
        )
        assert rc == MOD.EXIT_INSTALL_FAILED
        assert "APT stage failed" in log.text
        assert "completed successfully" not in log.text

    def test_single_tool_failure_does_not_block_others(
        self, payload_env, probe_env, monkeypatch
    ):
        _write_probe_tool(probe_env, "yamllint", _fake_tool_script("yamllint 1.35.1"))
        monkeypatch.setattr(MOD, "apt_install", lambda packages, log: None)

        def failing_install(self, tool):
            raise MOD.InstallerError("checksum mismatch")

        monkeypatch.setattr(MOD.PayloadInstaller, "install", failing_install)
        log = LogStub()
        rc = MOD.run_installation(
            frozenset({1, 4}),
            {"ruff": {"version": "0.15.21"}},
            REPO_ROOT / "packaging/debian/markdownlint-cli2",
            log,
        )
        assert rc == MOD.EXIT_INSTALL_FAILED
        assert "[FAILED]  Ruff" in log.text
        assert "[OK]      yamllint" in log.text
        assert "completed successfully" not in log.text
