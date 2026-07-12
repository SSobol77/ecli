#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: scripts/install_ecli_linters.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Interactive ECLI F4 linter toolchain installer for Debian 13 (amd64).

Stage 1 of the two-stage ECLI Debian installation:

    sudo python3 scripts/install_ecli_linters.py
    sudo apt install ./releases/<version>/ecli_<version>_linux_x86_64.deb

This script provisions the complete 19-tool F4 linter toolchain into the
operating system (APT packages) and into the managed ECLI payload tree:

    /opt/ecli/payload/bin        executable entry points (PATH surface)
    /opt/ecli/payload/packages   versioned tool distributions
    /opt/ecli/payload/state      managed installation state
    /opt/ecli/payload/cache      verified download cache / staging

and configures ``/etc/profile.d/ecli_payload.sh`` so login shells see
``/opt/ecli/payload/bin``. The ECLI ``.deb`` (stage 2) never bundles,
downloads, or installs linters; ECLI discovers them through ``PATH``.

Hard requirements enforced before any work: effective UID 0, Linux,
Debian, Debian major version 13, ``amd64`` architecture.

Standalone tools are installed exclusively from the committed production
lock ``packaging/debian/ecli-linter-lock.json`` (pinned version, HTTPS
asset URL, exact SHA-256, expected archive member). No ``releases/latest``
queries, no dynamic asset selection, no Zig ``master``. markdownlint-cli2
is installed with ``npm ci --omit=dev`` from the committed
``packaging/debian/markdownlint-cli2/package-lock.json``.

Downloads use the Python standard library only (HTTPS-only including
redirects, bounded size, bounded retries, ``.part`` staging, exact SHA-256
verification, atomic rename). Archive extraction rejects absolute paths,
traversal, device/FIFO members, setuid/setgid bits, and link escapes, and
requires exactly the locked archive member. Because the standard library
handles every locked archive type natively, no external acquisition
binaries (curl/jq/tar/gzip/unzip/xz) are required; only ``ca-certificates``
is installed for TLS trust when a standalone download is selected.

This file is standalone: it must never import ECLI application modules.

Exit codes:

* ``0`` every selected tool installed and verified
* ``1`` at least one selected tool failed to install or verify
* ``2`` invalid selection or usage
* ``3`` unsupported platform or missing root privileges
* ``4`` missing or invalid lock file / npm lock inputs
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import gzip
import hashlib
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


# --------------------------------------------------------------------------
# Canonical layout and platform contract
# --------------------------------------------------------------------------

PAYLOAD_ROOT = Path("/opt/ecli/payload")
PAYLOAD_BIN = PAYLOAD_ROOT / "bin"
PAYLOAD_PACKAGES = PAYLOAD_ROOT / "packages"
PAYLOAD_STATE = PAYLOAD_ROOT / "state"
PAYLOAD_CACHE = PAYLOAD_ROOT / "cache"
STATE_FILE = PAYLOAD_STATE / "installed-tools.json"
PROFILE_SCRIPT = Path("/etc/profile.d/ecli_payload.sh")
LOG_FILE = Path("/var/log/ecli/linter-installer.log")
# Standard root-writable tmpfs lock directory, present on every systemd or
# sysvinit Debian system regardless of whether /opt/ecli/payload has been
# created yet -- avoids a chicken-and-egg dependency on the payload tree
# this same lock is meant to protect.
INSTALLER_LOCK_FILE = Path("/run/lock/ecli-linter-installer.lock")

REQUIRED_OS_ID = "debian"
REQUIRED_DEBIAN_MAJOR = 13
REQUIRED_DPKG_ARCH = "amd64"

DIR_MODE = 0o755
EXEC_MODE = 0o755
FILE_MODE = 0o644

# Deterministic, idempotent PATH drop-in. The payload directory is
# PREPENDED so lock-pinned managed tools deterministically win over stale
# or unrelated same-named executables in /usr/local/bin, user-local
# directories, or other earlier PATH entries. The case guard prevents
# duplicate PATH entries on repeated logins and repeated installer runs.
PROFILE_CONTENT = """\
# Managed by ECLI: scripts/install_ecli_linters.py. Do not edit.
# Prepends the ECLI linter payload to PATH exactly once so lock-pinned
# managed tools take precedence over same-named host executables.
if [ -d /opt/ecli/payload/bin ]; then
    case ":$PATH:" in
        *":/opt/ecli/payload/bin:"*) ;;
        *) PATH="/opt/ecli/payload/bin:$PATH" ;;
    esac
    export PATH
fi
"""

# Internal execution environment: version verification must work in this
# process, without requiring a new login shell. Payload first: managed
# tools must shadow same-named host executables deterministically, and
# probes never resolve from /usr/local or user-local directories.
PROBE_PATH = f"{PAYLOAD_BIN}:/usr/sbin:/usr/bin:/sbin:/bin"
APPROVED_PATH_PREFIXES = (
    f"{PAYLOAD_BIN}/",
    "/usr/sbin/",
    "/usr/bin/",
    "/sbin/",
    "/bin/",
)

DOWNLOAD_CONNECT_TIMEOUT = 30.0
DOWNLOAD_TOTAL_TIMEOUT = 900.0
DOWNLOAD_RETRIES = 3
DOWNLOAD_CHUNK = 1 << 20
EXTRACT_TOTAL_SIZE_LIMIT = 1 << 30  # 1 GiB uncompressed hard cap
EXTRACT_MEMBER_LIMIT = 100_000
APT_TIMEOUT = 1800.0
NPM_TIMEOUT = 900.0
PROBE_TIMEOUT = 120.0

EXIT_OK = 0
EXIT_INSTALL_FAILED = 1
EXIT_USAGE = 2
EXIT_PLATFORM = 3
EXIT_LOCK = 4

SHA256_HEX_LENGTH = 64
MAX_INTERACTIVE_ATTEMPTS = 3

LOCK_REQUIRED_FIELDS = (
    "tool_id",
    "version",
    "source_url",
    "asset_url",
    "sha256",
    "archive_type",
    "expected_member",
    "executable_name",
    "version_command",
    "install_directory",
    "architecture",
    "license",
)
LOCK_ARCHIVE_TYPES = ("binary", "gz", "tar.gz", "tar.xz", "zip", "npm-lock")

# Base acquisition packages, installed only when at least one standalone
# (payload/npm) tool is selected. The stdlib downloader/extractor needs no
# curl/jq/tar/gzip/unzip/xz-utils; TLS trust anchors are required.
BASE_ACQUISITION_PACKAGES = ("ca-certificates",)


class InstallerError(Exception):
    """Deliberate installer failure with an operator-facing message."""


class SelectionError(InstallerError):
    """Menu selection could not be parsed."""


class LockError(InstallerError):
    """Lock file missing, unreadable, or violating the schema."""


class PlatformError(InstallerError):
    """Host does not satisfy the supported-platform contract."""


class DownloadError(InstallerError):
    """Verified download could not be completed."""


class ExtractionError(InstallerError):
    """Archive failed safety validation or expected-member checks."""


# --------------------------------------------------------------------------
# The 19-tool menu (fixed order, English)
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class ToolSpec:
    """One fixed menu entry of the 19-tool F4 toolchain."""

    number: int
    menu_name: str
    display_name: str
    kind: str  # "apt" | "payload" | "npm"
    executable_name: str
    version_command: tuple[str, ...]
    lock_id: str | None = None
    apt_packages: tuple[str, ...] = ()
    runtime_deps: tuple[str, ...] = ()
    requires_java: bool = False
    # Retried when the primary version_command fails. Debian 13's
    # checkstyle (8.36.1, picocli CLI) rejects the contract's ``-version``
    # form but answers ``--version``.
    version_fallback: tuple[str, ...] = ()


TOOLS: tuple[ToolSpec, ...] = (
    ToolSpec(1, "Ruff", "Ruff", "payload", "ruff", ("ruff", "--version"), "ruff"),
    ToolSpec(2, "Biome", "Biome", "payload", "biome", ("biome", "--version"), "biome"),
    ToolSpec(
        3,
        "markdownlint-cli2",
        "markdownlint-cli2",
        "npm",
        "markdownlint-cli2",
        ("markdownlint-cli2", "--version"),
        "markdownlint-cli2",
        runtime_deps=("nodejs", "npm"),
    ),
    ToolSpec(
        4,
        "yamllint",
        "yamllint",
        "apt",
        "yamllint",
        ("yamllint", "--version"),
        apt_packages=("yamllint",),
    ),
    ToolSpec(
        5,
        "shellcheck",
        "ShellCheck",
        "apt",
        "shellcheck",
        ("shellcheck", "--version"),
        apt_packages=("shellcheck",),
    ),
    ToolSpec(6, "Zig", "Zig", "payload", "zig", ("zig", "version"), "zig"),
    ToolSpec(
        7,
        "Hadolint",
        "Hadolint",
        "payload",
        "hadolint",
        ("hadolint", "--version"),
        "hadolint",
    ),
    ToolSpec(8, "Taplo", "Taplo", "payload", "taplo", ("taplo", "--version"), "taplo"),
    ToolSpec(
        9,
        "actionlint",
        "actionlint",
        "payload",
        "actionlint",
        ("actionlint", "-version"),
        "actionlint",
    ),
    ToolSpec(
        10,
        "clang-tidy",
        "clang-tidy",
        "apt",
        "clang-tidy",
        ("clang-tidy", "--version"),
        apt_packages=("clang-tidy",),
    ),
    ToolSpec(
        11,
        "cppcheck",
        "Cppcheck",
        "apt",
        "cppcheck",
        ("cppcheck", "--version"),
        apt_packages=("cppcheck",),
    ),
    ToolSpec(
        12,
        "clang-format",
        "clang-format",
        "apt",
        "clang-format",
        ("clang-format", "--version"),
        apt_packages=("clang-format",),
    ),
    ToolSpec(
        13,
        "Checkstyle",
        "Checkstyle",
        "apt",
        "checkstyle",
        ("checkstyle", "-version"),
        apt_packages=("checkstyle",),
        version_fallback=("checkstyle", "--version"),
    ),
    ToolSpec(
        14,
        "PMD",
        "PMD",
        "payload",
        "pmd",
        ("pmd", "--version"),
        "pmd",
        runtime_deps=("default-jre-headless",),
        requires_java=True,
    ),
    ToolSpec(
        15,
        "SpotBugs",
        "SpotBugs",
        "payload",
        "spotbugs",
        ("spotbugs", "-version"),
        "spotbugs",
        runtime_deps=("default-jre-headless",),
        requires_java=True,
    ),
    ToolSpec(
        16,
        "cargo-clippy",
        "cargo-clippy",
        "apt",
        "cargo",
        ("cargo", "clippy", "--version"),
        apt_packages=("cargo", "rust-clippy"),
    ),
    ToolSpec(
        17,
        "golangci-lint",
        "golangci-lint",
        "payload",
        "golangci-lint",
        ("golangci-lint", "--version"),
        "golangci-lint",
        runtime_deps=("golang-go",),
    ),
    ToolSpec(
        18,
        "SQLFluff",
        "SQLFluff",
        "apt",
        "sqlfluff",
        ("sqlfluff", "--version"),
        apt_packages=("sqlfluff",),
    ),
    ToolSpec(
        19,
        "TFLint",
        "TFLint",
        "payload",
        "tflint",
        ("tflint", "--version"),
        "tflint",
    ),
)

TOOLS_BY_NUMBER: dict[int, ToolSpec] = {tool.number: tool for tool in TOOLS}
ALL_TOOL_NUMBERS: frozenset[int] = frozenset(TOOLS_BY_NUMBER)


# --------------------------------------------------------------------------
# Logging
# --------------------------------------------------------------------------


class InstallerLog:
    """Root-owned timestamped file log that also echoes to stdout."""

    def __init__(self, path: Path | None, echo: bool = True) -> None:
        """Open (append) the log file, creating its directory as needed."""
        self.path = path
        self.echo = echo
        self._handle = None
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
            os.chmod(path.parent, DIR_MODE)
            self._handle = path.open("a", encoding="utf-8")
            os.chmod(path, 0o640)

    def log(self, message: str, *, echo: bool | None = None) -> None:
        """Write one timestamped line to the log, echoing per configuration."""
        timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        if self._handle is not None:
            self._handle.write(f"{timestamp} {message}\n")
            self._handle.flush()
        if echo if echo is not None else self.echo:
            print(message, flush=True)

    def detail(self, message: str) -> None:
        """Write to the log file only (no stdout echo)."""
        self.log(message, echo=False)

    def close(self) -> None:
        """Close the underlying file handle."""
        if self._handle is not None:
            self._handle.close()
            self._handle = None


# --------------------------------------------------------------------------
# Shared secure command runner
# --------------------------------------------------------------------------


def command_environment(extra: dict[str, str] | None = None) -> dict[str, str]:
    """Minimal controlled subprocess environment (never inherits secrets)."""
    env = {
        "PATH": PROBE_PATH,
        "HOME": "/root",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
        "DEBIAN_FRONTEND": "noninteractive",
    }
    if extra:
        env.update(extra)
    return env


def run_command(
    argv: list[str] | tuple[str, ...],
    log: InstallerLog,
    *,
    timeout: float,
    env: dict[str, str] | None = None,
    cwd: Path | None = None,
    check: bool = True,
    echo: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run one argv-array command with logging, timeout, and rc checking.

    Never uses ``shell=True`` and never interpolates user-controlled text
    into a shell. Output is recorded in the installer log; failures raise
    :class:`InstallerError` with clear diagnostics.
    """
    if not argv or not all(isinstance(item, str) for item in argv):
        raise InstallerError(f"invalid command argv: {argv!r}")
    printable = shlex.join(argv)
    log.log(f"  -> Executing: {printable}", echo=echo)
    try:
        result = subprocess.run(
            list(argv),
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env if env is not None else command_environment(),
            cwd=str(cwd) if cwd is not None else None,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise InstallerError(
            f"command timed out after {timeout:.0f}s: {printable}"
        ) from exc
    except FileNotFoundError as exc:
        raise InstallerError(f"executable not found: {argv[0]}") from exc
    if result.stdout:
        log.detail(f"  [stdout] {result.stdout.strip()[-8000:]}")
    if result.stderr:
        log.detail(f"  [stderr] {result.stderr.strip()[-8000:]}")
    if check and result.returncode != 0:
        stderr_tail = (result.stderr or result.stdout or "").strip()[-2000:]
        raise InstallerError(
            f"command failed (exit {result.returncode}): {printable}\n{stderr_tail}"
        )
    return result


# --------------------------------------------------------------------------
# Platform validation
# --------------------------------------------------------------------------


def parse_os_release(text: str) -> dict[str, str]:
    """Parse ``/etc/os-release`` key=value content."""
    values: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, raw = line.partition("=")
        values[key.strip()] = raw.strip().strip('"').strip("'")
    return values


def platform_errors(
    *,
    euid: int,
    sys_platform: str,
    os_release: dict[str, str],
    dpkg_arch: str | None,
) -> list[str]:
    """Return every supported-platform violation (empty when supported)."""
    errors: list[str] = []
    if euid != 0:
        errors.append("root privileges are required (effective UID 0); run with sudo")
    if not sys_platform.startswith("linux"):
        errors.append(f"unsupported platform {sys_platform!r}; Linux is required")
    if os_release.get("ID") != REQUIRED_OS_ID:
        errors.append(
            f"unsupported distribution {os_release.get('ID')!r}; Debian is required"
        )
    version_id = os_release.get("VERSION_ID", "")
    major = version_id.split(".", 1)[0]
    if major != str(REQUIRED_DEBIAN_MAJOR):
        errors.append(
            f"unsupported Debian version {version_id!r}; "
            f"Debian {REQUIRED_DEBIAN_MAJOR} (trixie) is required"
        )
    if dpkg_arch != REQUIRED_DPKG_ARCH:
        errors.append(
            f"unsupported architecture {dpkg_arch!r}; {REQUIRED_DPKG_ARCH} is required"
        )
    return errors


def detect_dpkg_architecture() -> str | None:
    """Return ``dpkg --print-architecture`` output, or None."""
    dpkg = shutil.which("dpkg")
    if dpkg is None:
        return None
    try:
        result = subprocess.run(
            [dpkg, "--print-architecture"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def validate_platform() -> dict[str, str]:
    """Enforce the platform contract; return os-release data on success."""
    os_release_path = Path("/etc/os-release")
    os_release: dict[str, str] = {}
    if os_release_path.is_file():
        os_release = parse_os_release(
            os_release_path.read_text(encoding="utf-8", errors="replace")
        )
    errors = platform_errors(
        euid=os.geteuid(),
        sys_platform=sys.platform,
        os_release=os_release,
        dpkg_arch=detect_dpkg_architecture(),
    )
    if errors:
        for error in errors:
            print(f"[ERROR] {error}", file=sys.stderr)
        raise PlatformError(
            "this installer supports only Debian "
            f"{REQUIRED_DEBIAN_MAJOR} (trixie) on amd64, run as root"
        )
    return os_release


# --------------------------------------------------------------------------
# Menu and selection parsing
# --------------------------------------------------------------------------


def render_menu() -> str:
    """Render the fixed 19-entry English menu."""
    lines = [
        "=" * 45,
        "         ECLI LINTER INSTALLER",
        "=" * 45,
        "[ A ] - Install All Linters",
        "",
    ]
    for tool in TOOLS:
        lines.append(f"{tool.number}.".ljust(4) + tool.menu_name)
    lines.append("")
    lines.append(
        "Enter 'A' to install all, or a comma-separated list of numbers (e.g., 1,4,5):"
    )
    return "\n".join(lines)


def parse_selection(raw: str) -> frozenset[int]:
    """Parse a menu selection; raise :class:`SelectionError` when malformed.

    Accepts ``A``/``a`` for all tools, single numbers, comma-separated
    numbers, whitespace around values, and duplicate values (deduplicated).
    Every malformed token is rejected explicitly, never silently ignored.
    """
    text = raw.strip()
    if not text:
        raise SelectionError("empty selection; enter 'A' or numbers 1-19")
    if text.lower() == "a":
        return ALL_TOOL_NUMBERS
    selected: set[int] = set()
    for raw_token in text.split(","):
        token = raw_token.strip()
        if not token:
            raise SelectionError(
                f"invalid selection {raw!r}: empty entry between commas"
            )
        if not token.isdigit():
            raise SelectionError(
                f"invalid selection token {token!r}: expected 'A' or a "
                "number between 1 and 19"
            )
        number = int(token)
        if number not in ALL_TOOL_NUMBERS:
            raise SelectionError(
                f"invalid selection token {token!r}: tool numbers run from 1 to 19"
            )
        selected.add(number)
    return frozenset(selected)


def prompt_selection(input_fn: Any = input) -> frozenset[int]:
    """Interactively prompt for a selection with clear rejection messages."""
    print(render_menu())
    for attempt in range(1, MAX_INTERACTIVE_ATTEMPTS + 1):
        try:
            raw = input_fn(">> ")
        except EOFError as exc:
            raise SelectionError("no selection provided (end of input)") from exc
        try:
            return parse_selection(raw)
        except SelectionError as exc:
            print(f"[ERROR] {exc}", file=sys.stderr)
            if attempt < MAX_INTERACTIVE_ATTEMPTS:
                print("Please try again.", file=sys.stderr)
    raise SelectionError(
        f"no valid selection after {MAX_INTERACTIVE_ATTEMPTS} attempts"
    )


# --------------------------------------------------------------------------
# Lock file loading and validation
# --------------------------------------------------------------------------


def default_lock_path() -> Path:
    """Locate the committed lock file relative to this script."""
    script_dir = Path(__file__).resolve().parent
    candidates = (
        script_dir.parent / "packaging" / "debian" / "ecli-linter-lock.json",
        script_dir / "ecli-linter-lock.json",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0]


def default_npm_lock_dir() -> Path:
    """Locate the committed markdownlint-cli2 npm lock directory."""
    script_dir = Path(__file__).resolve().parent
    candidates = (
        script_dir.parent / "packaging" / "debian" / "markdownlint-cli2",
        script_dir / "markdownlint-cli2",
    )
    for candidate in candidates:
        if candidate.is_dir():
            return candidate
    return candidates[0]


# Every character allowed in a single trusted path segment: no "/", no
# NUL, no shell metacharacters (`$ ` \" \` ; | & < > ( ) { } [ ] * ? ~ ! #
# whitespace), no control characters. This charset is deliberately small
# enough that any string built from it is always safe to embed inside a
# double-quoted POSIX shell string with no further escaping.
_SAFE_SEGMENT_RE = re.compile(r"[A-Za-z0-9._-]+")


def is_safe_basename(name: str) -> bool:
    r"""True when ``name`` is a plain, single-segment, shell-safe basename.

    Rejects empty strings, ``.``/``..``, any ``/`` or ``\\``, NUL bytes,
    and any character outside the trusted segment charset.
    """
    if not isinstance(name, str) or not name:
        return False
    if "/" in name or "\\" in name or "\x00" in name:
        return False
    if name in (".", ".."):
        return False
    return bool(_SAFE_SEGMENT_RE.fullmatch(name))


def is_safe_relative_member(member: str) -> bool:
    """True when ``member`` is a safe ``/``-separated relative path.

    Every individual path segment must independently satisfy
    :func:`is_safe_basename`; this rejects traversal (``..``), absolute
    paths, empty segments (``//``), NUL bytes, backslashes, and shell
    metacharacters anywhere in the path -- while still allowing the
    legitimate multi-segment archive members this installer extracts
    (for example ``node_modules/.bin/markdownlint-cli2``).
    """
    if not isinstance(member, str) or not member:
        return False
    if "\x00" in member or "\\" in member:
        return False
    if member.startswith("/") or member.startswith("~"):
        return False
    return all(is_safe_basename(part) for part in member.split("/"))


def is_strictly_within_payload(candidate: str) -> bool:
    """True when ``candidate`` resolves strictly below :data:`PAYLOAD_ROOT`.

    Uses ``Path.resolve()`` (lexically normalizing ``..``/``.`` and
    resolving symlinks for whatever prefix already exists on disk,
    without requiring the target to exist yet) so a value like
    ``/opt/ecli/payload-evil`` -- a string-prefix match but not an actual
    descendant -- or ``/opt/ecli/payload/../../etc`` is correctly
    rejected. Equal to the payload root itself is also rejected: entries
    must live *below* it, never install directly onto it.
    """
    if not isinstance(candidate, str) or not candidate:
        return False
    path = Path(candidate)
    if not path.is_absolute():
        return False
    try:
        resolved = path.resolve()
        root_resolved = PAYLOAD_ROOT.resolve()
    except (OSError, RuntimeError):
        return False
    if resolved == root_resolved:
        return False
    try:
        resolved.relative_to(root_resolved)
    except ValueError:
        return False
    return True


def has_mutable_reference(url: str) -> bool:
    """True when ``url`` points at a mutable/unpinned upstream reference.

    Catches GitHub ``/releases/latest/...`` download links and any
    Zig ``master`` development-channel reference; production installation
    must always use a specific pinned version.
    """
    lowered = url.lower()
    return "/latest" in lowered or "master" in lowered


def validate_lock_entry(tool_id: str, entry: Any) -> list[str]:
    """Return schema violations for one lock entry."""
    errors: list[str] = []
    if not isinstance(entry, dict):
        return [f"{tool_id}: lock entry must be an object"]
    for fieldname in LOCK_REQUIRED_FIELDS:
        if fieldname not in entry:
            errors.append(f"{tool_id}: missing required field {fieldname!r}")
    if errors:
        return errors
    if entry["tool_id"] != tool_id:
        errors.append(f"{tool_id}: tool_id mismatch {entry['tool_id']!r}")
    for url_field in ("source_url", "asset_url"):
        url = entry[url_field]
        if not isinstance(url, str) or not url.startswith("https://"):
            errors.append(f"{tool_id}: {url_field} must be an https:// URL")
        elif has_mutable_reference(url):
            errors.append(
                f"{tool_id}: {url_field} references a mutable/unpinned "
                f"target ('latest' or 'master'): {url!r}"
            )
    sha256 = entry["sha256"]
    if (
        not isinstance(sha256, str)
        or len(sha256) != SHA256_HEX_LENGTH
        or not re.fullmatch(r"[0-9a-f]{64}", sha256)
    ):
        errors.append(f"{tool_id}: sha256 must be 64 lowercase hex characters")
    if entry["archive_type"] not in LOCK_ARCHIVE_TYPES:
        errors.append(
            f"{tool_id}: archive_type {entry['archive_type']!r} not in "
            f"{LOCK_ARCHIVE_TYPES}"
        )
    if entry["architecture"] != REQUIRED_DPKG_ARCH:
        errors.append(f"{tool_id}: architecture must be {REQUIRED_DPKG_ARCH!r}")
    member = entry["expected_member"]
    if not is_safe_relative_member(member):
        errors.append(
            f"{tool_id}: expected_member must be a safe relative path built "
            f"only from [A-Za-z0-9._-] segments, no '..', no NUL, no shell "
            f"metacharacters: {member!r}"
        )
    executable_name = entry["executable_name"]
    if not is_safe_basename(executable_name):
        errors.append(
            f"{tool_id}: executable_name must be a plain shell-safe "
            f"basename (no '/', no '..', no shell metacharacters): "
            f"{executable_name!r}"
        )
    if "master" in str(entry["version"]).lower():
        errors.append(f"{tool_id}: development 'master' versions are forbidden")
    version_command = entry["version_command"]
    if (
        not isinstance(version_command, list)
        or not version_command
        or not all(isinstance(item, str) for item in version_command)
    ):
        errors.append(f"{tool_id}: version_command must be a list of strings")
    install_directory = entry["install_directory"]
    if not is_strictly_within_payload(install_directory):
        errors.append(
            f"{tool_id}: install_directory must resolve strictly below "
            f"{PAYLOAD_ROOT} (not equal to it, no traversal, no "
            f"string-prefix-only lookalikes): {install_directory!r}"
        )
    max_bytes = entry.get("max_download_bytes")
    if not isinstance(max_bytes, int) or max_bytes <= 0:
        errors.append(f"{tool_id}: max_download_bytes must be a positive integer")
    return errors


def load_lock(path: Path) -> dict[str, dict[str, Any]]:
    """Load and validate the production lock; raise :class:`LockError`."""
    if not path.is_file():
        raise LockError(f"lock file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise LockError(f"lock file unreadable: {path}: {exc}") from exc
    tools = data.get("tools")
    if not isinstance(tools, dict):
        raise LockError(f"lock file {path} has no 'tools' object")
    required_ids = {tool.lock_id for tool in TOOLS if tool.kind in ("payload", "npm")}
    errors: list[str] = []
    missing = sorted(required_ids - set(tools))
    if missing:
        errors.append(f"missing lock entries: {', '.join(missing)}")
    for tool_id in sorted(required_ids & set(tools)):
        errors.extend(validate_lock_entry(tool_id, tools[tool_id]))
    if errors:
        raise LockError(
            f"lock file {path} failed validation:\n  " + "\n  ".join(errors)
        )
    return tools


def validate_npm_lock_dir(path: Path, locked_version: str) -> None:
    """Require committed package.json + package-lock.json pinning the lock."""
    package_json = path / "package.json"
    package_lock = path / "package-lock.json"
    for required in (package_json, package_lock):
        if not required.is_file():
            raise LockError(f"required npm lock input not found: {required}")
    try:
        manifest = json.loads(package_json.read_text(encoding="utf-8"))
        lockfile = json.loads(package_lock.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise LockError(f"invalid npm lock JSON under {path}: {exc}") from exc
    pinned = manifest.get("dependencies", {}).get("markdownlint-cli2")
    if pinned != locked_version:
        raise LockError(
            f"package.json pins markdownlint-cli2 {pinned!r}, lock file "
            f"requires {locked_version!r}"
        )
    locked_pkg = lockfile.get("packages", {}).get("node_modules/markdownlint-cli2", {})
    if locked_pkg.get("version") != locked_version:
        raise LockError(
            f"package-lock.json does not lock markdownlint-cli2 {locked_version!r}"
        )


# --------------------------------------------------------------------------
# APT stage
# --------------------------------------------------------------------------


def resolve_apt_packages(selected: frozenset[int]) -> tuple[str, ...]:
    """Resolve the complete APT package set for one selection."""
    packages: set[str] = set()
    standalone_selected = False
    for number in selected:
        tool = TOOLS_BY_NUMBER[number]
        packages.update(tool.apt_packages)
        packages.update(tool.runtime_deps)
        if tool.kind in ("payload", "npm"):
            standalone_selected = True
    if standalone_selected:
        packages.update(BASE_ACQUISITION_PACKAGES)
    return tuple(sorted(packages))


def apt_install(packages: tuple[str, ...], log: InstallerLog) -> None:
    """Install the resolved package set in one APT transaction."""
    if not packages:
        log.log("  No APT packages required for this selection.")
        return
    log.log(f"  APT packages: {', '.join(packages)}")
    run_command(["apt-get", "update"], log, timeout=APT_TIMEOUT)
    run_command(
        ["apt-get", "install", "--yes", "--no-install-recommends", *packages],
        log,
        timeout=APT_TIMEOUT,
    )


# --------------------------------------------------------------------------
# Payload directories and permissions
# --------------------------------------------------------------------------


def ensure_directory(path: Path) -> None:
    """Create ``path`` (and parents) with 0755 root:root, by type."""
    path.mkdir(parents=True, exist_ok=True)
    current = path
    while True:
        os.chmod(current, DIR_MODE)
        if os.geteuid() == 0:
            os.chown(current, 0, 0)
        if current in (PAYLOAD_ROOT.parent, current.parent):
            break
        if not str(current).startswith(str(PAYLOAD_ROOT.parent)):
            break
        current = current.parent


def ensure_payload_layout() -> None:
    """Create the canonical payload directory tree."""
    for directory in (PAYLOAD_BIN, PAYLOAD_PACKAGES, PAYLOAD_STATE, PAYLOAD_CACHE):
        ensure_directory(directory)


def set_mode_by_type(path: Path, *, executable: bool) -> None:
    """Apply the by-type permission policy to one regular file."""
    os.chmod(path, EXEC_MODE if executable else FILE_MODE)
    if os.geteuid() == 0:
        os.chown(path, 0, 0)


def normalize_tree_ownership(root: Path) -> None:
    """Apply the by-type ownership/permission policy to a whole tree.

    Required after ``npm ci``: npm running as root preserves the uid/gid
    recorded in upstream tarball headers, leaving node_modules files owned
    by arbitrary users. Everything staged into the payload must be
    root:root with 0755 directories and 0644/0755 files; symlinks are
    re-owned without following their targets.
    """
    as_root = os.geteuid() == 0
    for dirpath, dirnames, filenames in os.walk(root):
        base = Path(dirpath)
        os.chmod(base, DIR_MODE)
        if as_root:
            os.chown(base, 0, 0)
        for name in dirnames:
            path = base / name
            if path.is_symlink() and as_root:
                os.lchown(path, 0, 0)
        for name in filenames:
            path = base / name
            if path.is_symlink():
                if as_root:
                    os.lchown(path, 0, 0)
                continue
            mode = stat.S_IMODE(path.stat().st_mode)
            set_mode_by_type(path, executable=bool(mode & 0o111))


# --------------------------------------------------------------------------
# Managed installation state
# --------------------------------------------------------------------------


def read_state(path: Path | None = None) -> dict[str, dict[str, Any]]:
    """Read managed state; tolerate absent or corrupt state files."""
    path = path if path is not None else STATE_FILE
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def write_state(state: dict[str, dict[str, Any]], path: Path | None = None) -> None:
    """Atomically persist managed state (temp file + rename)."""
    path = path if path is not None else STATE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(
        prefix=".installed-tools.", suffix=".tmp", dir=str(path.parent)
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2, sort_keys=True)
            handle.write("\n")
        os.chmod(temp_name, FILE_MODE)
        os.replace(temp_name, path)
    except BaseException:
        with contextlib.suppress(FileNotFoundError):
            os.unlink(temp_name)
        raise


def sha256_of_file(path: Path) -> str:
    """Return the SHA-256 hex digest of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(DOWNLOAD_CHUNK), b""):
            digest.update(chunk)
    return digest.hexdigest()


# --------------------------------------------------------------------------
# Verified HTTPS download
# --------------------------------------------------------------------------


class _HttpsOnlyRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Redirect handler that refuses any redirect to a non-HTTPS URL."""

    def redirect_request(
        self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> Any:
        if urllib.parse.urlsplit(newurl).scheme != "https":
            raise DownloadError(
                f"refusing insecure redirect to non-HTTPS URL: {newurl}"
            )
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def download_verified(
    url: str,
    destination: Path,
    expected_sha256: str,
    max_bytes: int,
    log: InstallerLog,
    *,
    retries: int = DOWNLOAD_RETRIES,
) -> Path:
    """Download ``url`` to ``destination`` with full verification.

    HTTPS-only (including redirects), bounded size, bounded retries,
    ``.part`` staging, exact SHA-256 verification, atomic rename, and
    partial-file cleanup on every failure path.
    """
    if urllib.parse.urlsplit(url).scheme != "https":
        raise DownloadError(f"refusing non-HTTPS download URL: {url}")
    if destination.is_file() and sha256_of_file(destination) == expected_sha256:
        log.log(f"  Reusing verified cached download: {destination.name}")
        return destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    part = destination.with_name(destination.name + ".part")
    opener = urllib.request.build_opener(_HttpsOnlyRedirectHandler())
    last_error: Exception | None = None
    for attempt in range(1, retries + 1):
        digest = hashlib.sha256()
        received = 0
        try:
            log.log(f"  Downloading ({attempt}/{retries}): {url}")
            request = urllib.request.Request(  # noqa: S310 - scheme enforced
                url, headers={"User-Agent": "ecli-linter-installer/0.2.4"}
            )
            started = datetime.now(UTC)
            with (
                opener.open(request, timeout=DOWNLOAD_CONNECT_TIMEOUT) as response,
                part.open("wb") as sink,
            ):
                status = getattr(response, "status", 200)
                if status != 200:
                    raise DownloadError(f"HTTP error {status} for {url}")
                while True:
                    elapsed = (datetime.now(UTC) - started).total_seconds()
                    if elapsed > DOWNLOAD_TOTAL_TIMEOUT:
                        raise DownloadError(
                            f"transfer exceeded {DOWNLOAD_TOTAL_TIMEOUT:.0f}s: {url}"
                        )
                    chunk = response.read(DOWNLOAD_CHUNK)
                    if not chunk:
                        break
                    received += len(chunk)
                    if received > max_bytes:
                        raise DownloadError(
                            f"download exceeded the maximum expected size "
                            f"({max_bytes} bytes): {url}"
                        )
                    digest.update(chunk)
                    sink.write(chunk)
            actual = digest.hexdigest()
            if actual != expected_sha256:
                part.unlink(missing_ok=True)
                raise DownloadError(
                    f"SHA-256 mismatch for {url}\n"
                    f"  expected: {expected_sha256}\n"
                    f"  actual:   {actual}"
                )
            log.log(f"  Verified SHA-256 ({received} bytes): {expected_sha256}")
            os.replace(part, destination)
            set_mode_by_type(destination, executable=False)
            return destination
        except DownloadError as exc:
            part.unlink(missing_ok=True)
            if "SHA-256 mismatch" in str(exc) or "maximum expected" in str(exc):
                raise
            last_error = exc
            log.log(f"  [WARN] download attempt {attempt} failed: {exc}")
        except (urllib.error.URLError, OSError) as exc:
            part.unlink(missing_ok=True)
            last_error = exc
            log.log(f"  [WARN] download attempt {attempt} failed: {exc}")
    raise DownloadError(f"download failed after {retries} attempts: {last_error}")


# --------------------------------------------------------------------------
# Safe archive extraction
# --------------------------------------------------------------------------


def _validated_target(destination: Path, member_name: str) -> Path:
    """Validate one member path and return its extraction target."""
    if not member_name or member_name.startswith("/") or "\\" in member_name:
        raise ExtractionError(f"unsafe archive member path: {member_name!r}")
    parts = Path(member_name).parts
    if any(part in ("..", "") for part in parts) or Path(member_name).is_absolute():
        raise ExtractionError(f"archive member escapes destination: {member_name!r}")
    target = destination / member_name
    resolved_destination = destination.resolve()
    if not target.resolve().is_relative_to(resolved_destination):
        raise ExtractionError(f"archive member escapes destination: {member_name!r}")
    return target


def _validate_link(
    destination: Path, member_name: str, link_target: str, *, hardlink: bool
) -> None:
    """Reject symlinks/hardlinks whose targets escape the destination."""
    kind = "hardlink" if hardlink else "symlink"
    if not link_target:
        raise ExtractionError(f"{kind} member {member_name!r} has empty target")
    if hardlink or not os.path.isabs(link_target):
        base = os.path.dirname(member_name) if not hardlink else ""
        joined = os.path.normpath(os.path.join(base, link_target))
        if joined.startswith("..") or os.path.isabs(joined):
            raise ExtractionError(
                f"{kind} member {member_name!r} escapes destination "
                f"(target {link_target!r})"
            )
        resolved = (destination / joined).resolve()
        if not resolved.is_relative_to(destination.resolve()):
            raise ExtractionError(
                f"{kind} member {member_name!r} escapes destination "
                f"(target {link_target!r})"
            )
    else:
        raise ExtractionError(
            f"{kind} member {member_name!r} uses absolute target {link_target!r}"
        )


def safe_extract_tar(archive: Path, destination: Path) -> None:
    """Safely extract a tar archive with full member validation."""
    destination.mkdir(parents=True, exist_ok=True)
    total = 0
    count = 0
    seen: set[str] = set()
    with tarfile.open(archive) as handle:
        for member in handle:
            count += 1
            if count > EXTRACT_MEMBER_LIMIT:
                raise ExtractionError(f"archive has too many members: {archive}")
            normalized = os.path.normpath(member.name)
            if normalized in seen:
                raise ExtractionError(
                    f"archive member {member.name!r} is duplicated; a repeated "
                    "path could silently overwrite an already-validated entry"
                )
            seen.add(normalized)
            target = _validated_target(destination, member.name)
            if member.mode & (stat.S_ISUID | stat.S_ISGID):
                raise ExtractionError(
                    f"archive member {member.name!r} carries setuid/setgid bits"
                )
            if member.isdev() or member.ischr() or member.isblk() or member.isfifo():
                raise ExtractionError(
                    f"archive member {member.name!r} is a device or FIFO"
                )
            if member.issym():
                _validate_link(
                    destination, member.name, member.linkname, hardlink=False
                )
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.is_symlink() or target.exists():
                    target.unlink()
                os.symlink(member.linkname, target)
                continue
            if member.islnk():
                _validate_link(destination, member.name, member.linkname, hardlink=True)
                source = destination / os.path.normpath(member.linkname)
                if not source.is_file():
                    raise ExtractionError(
                        f"hardlink member {member.name!r} references "
                        f"unextracted target {member.linkname!r}"
                    )
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                continue
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                os.chmod(target, DIR_MODE)
                continue
            if not member.isfile():
                raise ExtractionError(
                    f"archive member {member.name!r} has unsupported type"
                )
            total += member.size
            if total > EXTRACT_TOTAL_SIZE_LIMIT:
                raise ExtractionError(f"archive expands beyond limit: {archive}")
            source_obj = handle.extractfile(member)
            if source_obj is None:
                raise ExtractionError(f"cannot read archive member {member.name!r}")
            target.parent.mkdir(parents=True, exist_ok=True)
            with source_obj, target.open("wb") as sink:
                shutil.copyfileobj(source_obj, sink, DOWNLOAD_CHUNK)
            set_mode_by_type(target, executable=bool(member.mode & 0o111))


def safe_extract_zip(archive: Path, destination: Path) -> None:
    """Safely extract a zip archive with full member validation."""
    destination.mkdir(parents=True, exist_ok=True)
    total = 0
    seen: set[str] = set()
    with zipfile.ZipFile(archive) as handle:
        infos = handle.infolist()
        if len(infos) > EXTRACT_MEMBER_LIMIT:
            raise ExtractionError(f"archive has too many members: {archive}")
        for info in infos:
            normalized = os.path.normpath(info.filename)
            if normalized in seen:
                raise ExtractionError(
                    f"archive member {info.filename!r} is duplicated; a "
                    "repeated path could silently overwrite an "
                    "already-validated entry"
                )
            seen.add(normalized)
            mode = info.external_attr >> 16
            target = _validated_target(destination, info.filename)
            if mode & (stat.S_ISUID | stat.S_ISGID):
                raise ExtractionError(
                    f"archive member {info.filename!r} carries setuid/setgid bits"
                )
            if stat.S_ISBLK(mode) or stat.S_ISCHR(mode) or stat.S_ISFIFO(mode):
                raise ExtractionError(
                    f"archive member {info.filename!r} is a device or FIFO"
                )
            if stat.S_ISLNK(mode):
                link_target = handle.read(info).decode("utf-8", "replace")
                _validate_link(destination, info.filename, link_target, hardlink=False)
                target.parent.mkdir(parents=True, exist_ok=True)
                os.symlink(link_target, target)
                continue
            if info.is_dir():
                target.mkdir(parents=True, exist_ok=True)
                os.chmod(target, DIR_MODE)
                continue
            total += info.file_size
            if total > EXTRACT_TOTAL_SIZE_LIMIT:
                raise ExtractionError(f"archive expands beyond limit: {archive}")
            target.parent.mkdir(parents=True, exist_ok=True)
            with handle.open(info) as source_obj, target.open("wb") as sink:
                shutil.copyfileobj(source_obj, sink, DOWNLOAD_CHUNK)
            set_mode_by_type(target, executable=bool(mode & 0o111))


def extract_gz_single(archive: Path, destination_file: Path) -> None:
    """Decompress a single-file ``.gz`` payload with a size cap."""
    destination_file.parent.mkdir(parents=True, exist_ok=True)
    total = 0
    with gzip.open(archive, "rb") as source_obj, destination_file.open("wb") as sink:
        while True:
            chunk = source_obj.read(DOWNLOAD_CHUNK)
            if not chunk:
                break
            total += len(chunk)
            if total > EXTRACT_TOTAL_SIZE_LIMIT:
                raise ExtractionError(f"gz payload expands beyond limit: {archive}")
            sink.write(chunk)


_ELF_MAGIC = b"\x7fELF"
# ELF e_machine values (little-endian, offset 18-19 of the ELF header).
_EM_X86_64 = 0x3E
_ARCH_TO_EM_MACHINE = {"amd64": _EM_X86_64}


def verify_elf_architecture(path: Path, required_arch: str) -> None:
    """Reject a staged executable whose ELF architecture doesn't match.

    Non-ELF files (POSIX shell launcher scripts such as PMD/SpotBugs's
    ``bin/`` wrappers, which start with ``#!``) are not covered by this
    check: their correctness is enforced by the mandatory post-install
    version probe instead. Truncated or corrupt ELF headers are rejected
    outright rather than silently skipped.
    """
    expected_machine = _ARCH_TO_EM_MACHINE.get(required_arch)
    if expected_machine is None:
        return
    with path.open("rb") as handle:
        header = handle.read(20)
    if header[:4] != _ELF_MAGIC:
        return
    if len(header) < 20:
        raise ExtractionError(f"{path}: truncated ELF header")
    e_machine = int.from_bytes(header[18:20], byteorder="little")
    if e_machine != expected_machine:
        raise ExtractionError(
            f"{path}: ELF e_machine {e_machine:#06x} does not match the "
            f"required architecture {required_arch!r} "
            f"(expected {expected_machine:#06x})"
        )


def stage_archive(entry: dict[str, Any], archive: Path, staging: Path) -> Path:
    """Extract one verified archive into ``staging`` and locate the member.

    Requires exactly the locked ``expected_member`` (no wildcards, no
    ambiguity). Returns the absolute staged path of the expected member.
    """
    archive_type = entry["archive_type"]
    expected_member = entry["expected_member"]
    if archive_type == "binary":
        staged = staging / expected_member
        staging.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(archive, staged)
    elif archive_type == "gz":
        staged = staging / expected_member
        extract_gz_single(archive, staged)
    elif archive_type in ("tar.gz", "tar.xz"):
        safe_extract_tar(archive, staging)
        staged = staging / expected_member
    elif archive_type == "zip":
        safe_extract_zip(archive, staging)
        staged = staging / expected_member
    else:
        raise ExtractionError(f"unsupported archive_type {archive_type!r}")
    if not staged.is_file():
        raise ExtractionError(
            f"expected archive member {expected_member!r} not found in {archive.name}"
        )
    verify_elf_architecture(staged, entry["architecture"])
    set_mode_by_type(staged, executable=True)
    return staged


# --------------------------------------------------------------------------
# Managed install / upgrade primitives
# --------------------------------------------------------------------------


def guard_unmanaged_target(
    target: Path, tool_id: str, state: dict[str, dict[str, Any]]
) -> None:
    """Refuse to overwrite files this installer does not manage."""
    if (target.exists() or target.is_symlink()) and tool_id not in state:
        raise InstallerError(
            f"refusing to overwrite unmanaged file {target}; remove it "
            "manually if it should be managed by this installer"
        )


def atomic_replace_file(staged: Path, target: Path) -> None:
    """Atomically move a staged regular file onto its final path."""
    temp = target.with_name(f".{target.name}.new-{os.getpid()}")
    shutil.move(str(staged), str(temp))
    set_mode_by_type(temp, executable=True)
    os.replace(temp, target)


def atomic_replace_symlink(link_target: str, link_path: Path) -> None:
    """Atomically (re)create a deterministic executable symlink."""
    temp = link_path.with_name(f".{link_path.name}.new-{os.getpid()}")
    if temp.is_symlink() or temp.exists():
        temp.unlink()
    os.symlink(link_target, temp)
    os.replace(temp, link_path)


# Characters that would be dangerous if interpolated, unescaped, inside a
# double-quoted POSIX shell string: double-quote (ends the string early),
# backtick and dollar-sign (command/parameter substitution), backslash
# (escape reinterpretation), and any control character including NUL/CR/LF.
_WRAPPER_UNSAFE_CHARS = frozenset('"`$\\')


def wrapper_script_content(target: Path) -> str:
    """Deterministic exec-wrapper for versioned tree-tool entry points.

    A plain symlink is not safe for every tree tool: PMD's ``bin/pmd``
    resolves its distribution home from an unresolved ``$0``, so invoking
    it through a symlink in ``payload/bin`` fails (`can't cd to
    ../packages/pmd/<version>/bin/..`). An exec wrapper keeps ``$0`` at
    the real script for every tool.

    ``target`` is never interpolated unescaped: every path component that
    reaches this function has already been validated against
    :func:`is_safe_basename` / :func:`is_strictly_within_payload` by the
    lock loader, and the final concrete string is independently
    re-checked here immediately before it is embedded in generated shell
    text, so a validation gap anywhere upstream can never turn into shell
    injection in the wrapper.
    """
    if not target.is_absolute():
        raise InstallerError(f"wrapper target must be an absolute path: {target}")
    target_str = str(target)
    for character in target_str:
        if character in _WRAPPER_UNSAFE_CHARS or ord(character) < 0x20:
            raise InstallerError(
                "wrapper target cannot be represented safely in a "
                f"double-quoted shell string (unsafe character {character!r}): "
                f"{target_str!r}"
            )
    return (
        "#!/bin/sh\n"
        "# Managed by ECLI: scripts/install_ecli_linters.py. Do not edit.\n"
        f'exec "{target_str}" "$@"\n'
    )


def atomic_replace_wrapper(content: str, link_path: Path) -> None:
    """Atomically (re)write a deterministic executable wrapper script."""
    temp = link_path.with_name(f".{link_path.name}.new-{os.getpid()}")
    temp.write_text(content, encoding="utf-8")
    set_mode_by_type(temp, executable=True)
    os.replace(temp, link_path)


def atomic_replace_tree(staged_root: Path, final_root: Path) -> None:
    """Atomically swap a staged directory tree into its final location.

    The previous tree is retained until the new one is in place, then
    removed. Requires ``staged_root`` on the same filesystem.
    """
    final_root.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(final_root.parent, DIR_MODE)
    backup = final_root.with_name(f".{final_root.name}.old-{os.getpid()}")
    if final_root.exists():
        os.rename(final_root, backup)
    try:
        os.rename(staged_root, final_root)
    except OSError:
        if backup.exists():
            os.rename(backup, final_root)
        raise
    if backup.exists():
        shutil.rmtree(backup, ignore_errors=True)


def probe_staged_executable(
    executable: Path, version_args: tuple[str, ...], log: InstallerLog
) -> str:
    """Run a staged executable's version probe before promoting it."""
    result = run_command(
        [str(executable), *version_args],
        log,
        timeout=PROBE_TIMEOUT,
        echo=False,
    )
    output = (result.stdout or "") + (result.stderr or "")
    if not output.strip():
        raise InstallerError(
            f"staged executable produced no version output: {executable}"
        )
    return output.strip()


@dataclass
class ToolResult:
    """Final per-tool outcome for the report."""

    tool: ToolSpec
    status: str  # "OK" | "SKIPPED" | "FAILED"
    detail: str = ""
    version: str = ""
    path: str = ""
    stage: str = ""


class PayloadInstaller:
    """Installs the lock-pinned standalone tools into the payload tree."""

    def __init__(
        self,
        lock: dict[str, dict[str, Any]],
        state: dict[str, dict[str, Any]],
        log: InstallerLog,
        npm_lock_dir: Path,
    ) -> None:
        """Bind the lock, managed state, log, and npm lock inputs."""
        self.lock = lock
        self.state = state
        self.log = log
        self.npm_lock_dir = npm_lock_dir
        self._staging_dirs: list[Path] = []

    def cleanup(self) -> None:
        """Remove temporary staging directories."""
        for staging in self._staging_dirs:
            shutil.rmtree(staging, ignore_errors=True)
        self._staging_dirs = []

    def _new_staging(self) -> Path:
        staging = Path(tempfile.mkdtemp(prefix="stage-", dir=str(PAYLOAD_CACHE)))
        os.chmod(staging, 0o700)
        self._staging_dirs.append(staging)
        return staging

    # -- idempotency ------------------------------------------------------

    def _installed_and_current(self, tool: ToolSpec) -> bool:
        """True when the exact locked version is installed and verified."""
        entry = self.lock[tool.lock_id or ""]
        record = self.state.get(tool.lock_id or "")
        if not record or record.get("version") != entry["version"]:
            return False
        executable = PAYLOAD_BIN / entry["executable_name"]
        if not executable.exists():
            return False
        installed_sha = record.get("installed_sha256")
        if installed_sha and executable.is_file() and not executable.is_symlink():
            if sha256_of_file(executable) != installed_sha:
                self.log.log(
                    f"  Managed binary {executable} does not match recorded "
                    "checksum; reinstalling."
                )
                return False
        try:
            output = probe_staged_executable(
                executable, tuple(entry["version_command"][1:]), self.log
            )
        except InstallerError:
            self.log.log(
                f"  Managed executable {executable} failed its version "
                "probe; reinstalling."
            )
            return False
        if str(entry["version"]) not in output:
            return False
        self.log.log(
            f"  {tool.display_name} {entry['version']} already installed "
            "and verified; skipping reinstall."
        )
        return True

    # -- installers -------------------------------------------------------

    def install(self, tool: ToolSpec) -> None:
        """Install one payload/npm tool from the lock (idempotent)."""
        if tool.kind == "npm":
            self._install_npm(tool)
            return
        entry = self.lock[tool.lock_id or ""]
        if self._installed_and_current(tool):
            return
        guard_unmanaged_target(
            PAYLOAD_BIN / entry["executable_name"],
            tool.lock_id or "",
            self.state,
        )
        archive_name = urllib.parse.urlsplit(entry["asset_url"]).path.rsplit("/", 1)[-1]
        archive = download_verified(
            entry["asset_url"],
            PAYLOAD_CACHE / f"{entry['tool_id']}-{entry['version']}-{archive_name}",
            entry["sha256"],
            int(entry["max_download_bytes"]),
            self.log,
        )
        staging = self._new_staging()
        staged_member = stage_archive(entry, archive, staging)
        install_directory = Path(entry["install_directory"])
        if install_directory == PAYLOAD_BIN:
            self._promote_single_binary(tool, entry, staged_member)
        else:
            self._promote_tree(tool, entry, staged_member, install_directory)

    def _promote_single_binary(
        self, tool: ToolSpec, entry: dict[str, Any], staged_member: Path
    ) -> None:
        """Verify then atomically promote a single-file executable."""
        probe_staged_executable(
            staged_member, tuple(entry["version_command"][1:]), self.log
        )
        target = PAYLOAD_BIN / entry["executable_name"]
        installed_sha = sha256_of_file(staged_member)
        atomic_replace_file(staged_member, target)
        self._record(tool, entry, target, installed_sha256=installed_sha)

    def _promote_tree(
        self,
        tool: ToolSpec,
        entry: dict[str, Any],
        staged_member: Path,
        install_directory: Path,
    ) -> None:
        """Verify then atomically promote a versioned distribution tree."""
        member_relative = Path(entry["expected_member"])
        staged_root = staged_member.parents[len(member_relative.parts) - 2]
        probe_staged_executable(
            staged_member, tuple(entry["version_command"][1:]), self.log
        )
        # Versioned trees live under packages/<tool_id>/<version>: that
        # namespace is owned by this installer, so a stale tree there (for
        # example after a lost state file) is replaced atomically rather
        # than treated as an unmanaged foreign file.
        atomic_replace_tree(staged_root, install_directory)
        inner = install_directory / Path(*member_relative.parts[1:])
        link_path = PAYLOAD_BIN / entry["executable_name"]
        atomic_replace_wrapper(wrapper_script_content(inner), link_path)
        self._record(tool, entry, link_path)

    def _install_npm(self, tool: ToolSpec) -> None:
        """Install markdownlint-cli2 from the committed npm lock."""
        entry = self.lock[tool.lock_id or ""]
        if self._installed_and_current(tool):
            return
        validate_npm_lock_dir(self.npm_lock_dir, str(entry["version"]))
        guard_unmanaged_target(
            PAYLOAD_BIN / entry["executable_name"],
            tool.lock_id or "",
            self.state,
        )
        final_root = PAYLOAD_PACKAGES / "nodejs"
        if final_root.exists() and (tool.lock_id or "") not in self.state:
            raise InstallerError(
                f"refusing to overwrite unmanaged directory {final_root}"
            )
        staging = self._new_staging()
        build_root = staging / "nodejs"
        build_root.mkdir(parents=True)
        for name in ("package.json", "package-lock.json"):
            shutil.copyfile(self.npm_lock_dir / name, build_root / name)
            set_mode_by_type(build_root / name, executable=False)
        npm_cache = PAYLOAD_CACHE / "npm-cache"
        npm_cache.mkdir(parents=True, exist_ok=True)
        run_command(
            [
                "npm",
                "ci",
                "--omit=dev",
                "--ignore-scripts",
                "--no-audit",
                "--no-fund",
                "--loglevel=error",
            ],
            self.log,
            timeout=NPM_TIMEOUT,
            cwd=build_root,
            env=command_environment({"npm_config_cache": str(npm_cache)}),
        )
        normalize_tree_ownership(build_root)
        staged_shim = build_root / entry["expected_member"]
        if not (staged_shim.is_file() or staged_shim.is_symlink()):
            raise InstallerError(
                f"npm ci did not produce expected member {entry['expected_member']!r}"
            )
        probe_staged_executable(
            staged_shim, tuple(entry["version_command"][1:]), self.log
        )
        atomic_replace_tree(build_root, final_root)
        link_path = PAYLOAD_BIN / entry["executable_name"]
        link_target = os.path.relpath(
            final_root / entry["expected_member"], PAYLOAD_BIN
        )
        atomic_replace_symlink(link_target, link_path)
        self._record(tool, entry, link_path)

    def _record(
        self,
        tool: ToolSpec,
        entry: dict[str, Any],
        executable_path: Path,
        *,
        installed_sha256: str | None = None,
    ) -> None:
        """Persist one successful managed installation atomically."""
        record: dict[str, Any] = {
            "tool_id": entry["tool_id"],
            "version": str(entry["version"]),
            "asset_url": entry["asset_url"],
            "asset_sha256": entry["sha256"],
            "executable_path": str(executable_path),
            "install_directory": entry["install_directory"],
            "installed_at": datetime.now(UTC).isoformat(),
        }
        if installed_sha256:
            record["installed_sha256"] = installed_sha256
        self.state[entry["tool_id"]] = record
        write_state(self.state)
        self.log.log(
            f"  Installed {tool.display_name} {entry['version']} -> {executable_path}"
        )


# --------------------------------------------------------------------------
# PATH configuration
# --------------------------------------------------------------------------


def install_profile_script(log: InstallerLog) -> None:
    """Write the deterministic, idempotent PATH drop-in atomically."""
    if PROFILE_SCRIPT.is_file():
        current = PROFILE_SCRIPT.read_text(encoding="utf-8", errors="replace")
        if current == PROFILE_CONTENT:
            log.log(f"  {PROFILE_SCRIPT} already up to date.")
            return
    PROFILE_SCRIPT.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(
        prefix=".ecli_payload.", suffix=".tmp", dir=str(PROFILE_SCRIPT.parent)
    )
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        handle.write(PROFILE_CONTENT)
    os.chmod(temp_name, FILE_MODE)
    if os.geteuid() == 0:
        os.chown(temp_name, 0, 0)
    os.replace(temp_name, PROFILE_SCRIPT)
    log.log(f"  Wrote {PROFILE_SCRIPT} (mode 0644, world-readable).")


# --------------------------------------------------------------------------
# Verification and reporting
# --------------------------------------------------------------------------


def probe_tool(
    tool: ToolSpec,
    lock: dict[str, dict[str, Any]],
    log: InstallerLog,
) -> ToolResult:
    """Run one tool's version probe against the final environment."""
    executable = shutil.which(tool.executable_name, path=PROBE_PATH)
    if executable is None:
        return ToolResult(
            tool,
            "FAILED",
            detail=f"executable {tool.executable_name!r} not found on PATH",
            stage="verify",
        )
    real = os.path.realpath(executable)
    if not any(executable.startswith(prefix) for prefix in APPROVED_PATH_PREFIXES):
        return ToolResult(
            tool,
            "FAILED",
            detail=f"executable resolved outside approved paths: {executable}",
            stage="verify",
        )
    if tool.requires_java:
        try:
            run_command(["java", "-version"], log, timeout=PROBE_TIMEOUT, echo=False)
        except InstallerError as exc:
            return ToolResult(
                tool,
                "FAILED",
                detail=f"java runtime probe failed: {exc}",
                stage="verify",
            )
    try:
        result = run_command(
            [executable, *tool.version_command[1:]],
            log,
            timeout=PROBE_TIMEOUT,
            echo=False,
        )
    except InstallerError as exc:
        if not tool.version_fallback:
            return ToolResult(tool, "FAILED", detail=one_line(str(exc)), stage="verify")
        log.detail(
            f"  primary version probe failed for {tool.executable_name}; "
            f"retrying with fallback {tool.version_fallback[1:]}"
        )
        try:
            result = run_command(
                [executable, *tool.version_fallback[1:]],
                log,
                timeout=PROBE_TIMEOUT,
                echo=False,
            )
        except InstallerError as fallback_exc:
            return ToolResult(
                tool, "FAILED", detail=one_line(str(fallback_exc)), stage="verify"
            )
    # Several tools (java -version style) print version data to stderr.
    output = ((result.stdout or "") + " " + (result.stderr or "")).strip()
    if not output:
        return ToolResult(
            tool,
            "FAILED",
            detail="version probe produced no output",
            stage="verify",
        )
    first_line = next(
        (line.strip() for line in output.splitlines() if line.strip()), ""
    )
    if tool.kind in ("payload", "npm"):
        locked_version = str(lock[tool.lock_id or ""]["version"])
        if locked_version not in output:
            return ToolResult(
                tool,
                "FAILED",
                detail=(
                    f"expected locked version {locked_version} in probe "
                    f"output {first_line!r}"
                ),
                stage="verify",
            )
        version = locked_version
    else:
        version = first_line[:60]
    log.detail(f"  probe {tool.executable_name}: {first_line} ({real})")
    return ToolResult(tool, "OK", version=version, path=executable)


def one_line(text: str, limit: int = 240) -> str:
    """Collapse whitespace for single-line report output (log keeps full text)."""
    collapsed = " ".join(text.split())
    return collapsed[:limit] + ("..." if len(collapsed) > limit else "")


def format_report_line(result: ToolResult) -> str:
    """Format one aligned final-report line."""
    tag = f"[{result.status}]".ljust(10)
    name = result.tool.display_name.ljust(20)
    if result.status == "OK":
        return f"{tag}{name}version {result.version} path {result.path}"
    if result.status == "SKIPPED":
        return f"{tag}{name}not selected"
    stage = f" [stage: {result.stage}]" if result.stage else ""
    return f"{tag}{name}reason {result.detail}{stage}"


def print_final_report(
    results: dict[int, ToolResult],
    selected: frozenset[int],
    log: InstallerLog,
) -> int:
    """Print the per-tool report and the honest final summary."""
    log.log("")
    log.log("=" * 72)
    log.log("FINAL REPORT")
    log.log("=" * 72)
    for tool in TOOLS:
        log.log(format_report_line(results[tool.number]))
    log.log("=" * 72)
    ok = sum(1 for number in selected if results[number].status == "OK")
    failed = sorted(
        results[number].tool.display_name
        for number in selected
        if results[number].status != "OK"
    )
    total = len(selected)
    if failed:
        log.log(
            f"ECLI linter installation FAILED: {ok}/{total} selected tools "
            f"verified; failed: {', '.join(failed)}."
        )
        log.log(
            "Note: APT packages already installed by this run remain "
            "installed; no APT rollback is performed."
        )
        return EXIT_INSTALL_FAILED
    if selected == ALL_TOOL_NUMBERS:
        log.log(
            "ECLI linter installation completed successfully: 19/19 tools verified."
        )
    else:
        log.log(
            "ECLI linter installation completed successfully: "
            f"{total}/{total} selected tools verified."
        )
    log.log("")
    log.log(
        "Open a new login shell (or 'source /etc/profile.d/ecli_payload.sh') "
        "so PATH includes /opt/ecli/payload/bin."
    )
    log.log("You can now install ECLI itself, for example:")
    log.log("  sudo apt install ./releases/0.2.4/ecli_0.2.4_linux_x86_64.deb")
    return EXIT_OK


# --------------------------------------------------------------------------
# Main flow
# --------------------------------------------------------------------------


class InstallerLockHeldError(InstallerError):
    """Another installer instance already holds the payload lock."""


@contextlib.contextmanager
def installer_process_lock(lock_path: Path = INSTALLER_LOCK_FILE):
    """Exclusive, non-blocking process lock guarding all payload mutation.

    Two concurrently running root instances of this installer must never
    mutate ``/opt/ecli/payload`` at the same time -- interleaved atomic
    promotions, state-file writes, or APT transactions could otherwise
    corrupt the managed tree or the state file. Uses ``flock(2)`` on a
    fixed path under ``/run/lock`` (always present, root-writable, and
    independent of whether the payload tree itself exists yet). Fails
    immediately with a clear message rather than blocking indefinitely if
    another instance already holds it; the lock is released automatically
    on process exit even if the process is killed (kernel-held, not a
    stale on-disk marker that could be forgotten).
    """
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(lock_path, "w")  # noqa: SIM115 - held for the whole block
    try:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise InstallerLockHeldError(
                f"another instance of this installer is already running "
                f"(lock held: {lock_path}); wait for it to finish and "
                "retry"
            ) from exc
        handle.write(f"{os.getpid()}\n")
        handle.flush()
        yield
    finally:
        fcntl.flock(handle, fcntl.LOCK_UN)
        handle.close()


def build_arg_parser() -> argparse.ArgumentParser:
    """Build the CLI parser."""
    parser = argparse.ArgumentParser(
        prog="install_ecli_linters.py",
        description=(
            "Interactive ECLI F4 linter toolchain installer for Debian 13 "
            "(amd64). Stage 1 of the two-stage ECLI installation; run it "
            "before installing the ECLI .deb."
        ),
    )
    parser.add_argument(
        "--select",
        metavar="SELECTION",
        help=(
            "non-interactive selection: 'A' for all tools or a "
            "comma-separated list of menu numbers (e.g. '1,4,5')"
        ),
    )
    parser.add_argument(
        "--lock-file",
        type=Path,
        default=None,
        help="override the production lock file location",
    )
    parser.add_argument(
        "--npm-lock-dir",
        type=Path,
        default=None,
        help=(
            "override the committed markdownlint-cli2 "
            "package.json/package-lock.json directory"
        ),
    )
    return parser


def run_installation(
    selected: frozenset[int],
    lock: dict[str, dict[str, Any]],
    npm_lock_dir: Path,
    log: InstallerLog,
) -> int:
    """Execute the full installation flow for one validated selection."""
    results: dict[int, ToolResult] = {
        tool.number: ToolResult(tool, "SKIPPED") for tool in TOOLS
    }
    selected_tools = [TOOLS_BY_NUMBER[number] for number in sorted(selected)]
    log.log(
        "Selected tools: " + ", ".join(tool.display_name for tool in selected_tools)
    )

    log.log("")
    log.log("[STEP 1/5] Resolving APT dependencies...")
    apt_packages = resolve_apt_packages(selected)
    log.log("")
    log.log("[STEP 2/5] Installing APT packages (single transaction)...")
    try:
        apt_install(apt_packages, log)
    except InstallerError as exc:
        log.log(f"[ERROR] APT stage failed: {exc}")
        for tool in selected_tools:
            results[tool.number] = ToolResult(
                tool,
                "FAILED",
                detail="APT stage failed; tool not installed",
                stage="apt-install",
            )
        return print_final_report(results, selected, log)

    log.log("")
    log.log("[STEP 3/5] Preparing payload directories under /opt/ecli/payload...")
    ensure_payload_layout()

    log.log("")
    log.log("[STEP 4/5] Installing standalone payload linters from the lock...")
    state = read_state()
    installer = PayloadInstaller(lock, state, log, npm_lock_dir)
    install_failures: dict[int, str] = {}
    try:
        for tool in selected_tools:
            if tool.kind not in ("payload", "npm"):
                continue
            log.log(f"--- {tool.display_name} ---")
            try:
                installer.install(tool)
            except InstallerError as exc:
                install_failures[tool.number] = str(exc)
                log.log(f"[ERROR] {tool.display_name} failed during install: {exc}")
    finally:
        installer.cleanup()

    log.log("")
    log.log("[STEP 5/5] Configuring global PATH...")
    install_profile_script(log)

    log.log("")
    log.log("Verifying selected tools (version probes)...")
    for tool in selected_tools:
        if tool.number in install_failures:
            results[tool.number] = ToolResult(
                tool,
                "FAILED",
                detail=install_failures[tool.number],
                stage="install",
            )
            continue
        results[tool.number] = probe_tool(tool, lock, log)
    return print_final_report(results, selected, log)


def main(argv: list[str] | None = None) -> int:
    """Entry point; returns the process exit code."""
    args = build_arg_parser().parse_args(argv)
    try:
        validate_platform()
    except PlatformError as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return EXIT_PLATFORM

    log = InstallerLog(LOG_FILE)
    try:
        os_release = parse_os_release(
            Path("/etc/os-release").read_text(encoding="utf-8", errors="replace")
        )
        log.detail("==== ECLI linter installer session start ====")
        log.detail(
            f"Debian: {os_release.get('PRETTY_NAME', 'unknown')} "
            f"arch: {detect_dpkg_architecture()}"
        )

        lock_path = args.lock_file or default_lock_path()
        npm_lock_dir = args.npm_lock_dir or default_npm_lock_dir()
        try:
            lock = load_lock(lock_path)
        except LockError as exc:
            log.log(f"[ERROR] {exc}")
            return EXIT_LOCK
        log.detail(f"Lock file: {lock_path}")

        try:
            if args.select is not None:
                selected = parse_selection(args.select)
            else:
                selected = prompt_selection()
        except SelectionError as exc:
            log.log(f"[ERROR] {exc}")
            return EXIT_USAGE

        if any(TOOLS_BY_NUMBER[number].kind == "npm" for number in selected):
            try:
                validate_npm_lock_dir(
                    npm_lock_dir,
                    str(lock["markdownlint-cli2"]["version"]),
                )
            except LockError as exc:
                log.log(f"[ERROR] {exc}")
                return EXIT_LOCK

        with installer_process_lock():
            return run_installation(selected, lock, npm_lock_dir, log)
    except InstallerError as exc:
        log.log(f"[ERROR] installation aborted: {exc}")
        return EXIT_INSTALL_FAILED
    finally:
        log.detail("==== ECLI linter installer session end ====")
        log.close()


if __name__ == "__main__":
    raise SystemExit(main())
