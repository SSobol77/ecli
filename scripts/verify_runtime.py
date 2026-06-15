#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: scripts/verify_runtime.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Cross-artifact launcher validation for packaged ECLI release outputs.

Canonical Python replacement for ``scripts/verify_runtime.sh``. It validates a
packaged ECLI launcher either by executing it (native mode) or by verifying the
package payload structure (structural mode); ``auto`` executes when the
host/artifact ABI is compatible and falls back to structural otherwise.

This is a local, read-only validator. It never publishes, uploads, signs, tags,
pushes, or triggers any workflow.

Exit codes (stable; callers branch on these):

* ``0`` validation passed (native smoke or structural contract)
* ``2`` invalid ``--mode`` value
* ``3`` artifact not found
* ``4`` artifact outside the current ``releases/<version>/`` directory
* ``5`` runtime launcher missing or not executable
* ``6`` failed to attach a DMG (macOS only)
* a structural/native failure propagates a non-zero status
"""

from __future__ import annotations

import argparse
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path


EXIT_OK = 0
EXIT_INVALID_MODE = 2
EXIT_ARTIFACT_MISSING = 3
EXIT_OUTSIDE_RELEASE = 4
EXIT_LAUNCHER_MISSING = 5
EXIT_DMG_ATTACH = 6

VALID_MODES = ("auto", "native", "structural")

FORBIDDEN_LOG_PATTERNS = (
    "ModuleNotFoundError",
    "No module named 'unittest'",
    "CRITICAL - ecli - Failed to import a critical application component",
)
LOG_EXCERPT_CONTEXT = 2

ArtifactExtractor = Callable[[Path, Path, Path, str, Path], tuple[Path | None, int]]


def normalize_arch(raw: str) -> str:
    """Map ``uname -m`` output to the release-contract arch label (arm64 form)."""
    if raw in ("amd64", "x86_64"):
        return "x86_64"
    if raw in ("aarch64", "arm64"):
        return "arm64"
    return raw


def read_version(root: Path) -> str | None:
    """Read ``[project].version`` from pyproject.toml using the legacy regex."""
    text = (root / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'(?m)^[ \t]*version[ \t]*=[ \t]*"([^"]+)"[ \t]*$', text)
    return match.group(1) if match else None


def default_artifact(root: Path, version: str) -> Path:
    arch = normalize_arch(platform.machine() or "x86_64")
    return root / "releases" / version / f"ecli_{version}_linux_{arch}.deb"


def is_within_release(artifact: Path, root: Path, version: str) -> bool:
    """True if ``artifact`` lives under ``releases/<version>/`` (rel or abs)."""
    release_dir = root / "releases" / version
    candidates = [artifact]
    if not artifact.is_absolute():
        candidates.append((root / artifact).resolve())
    else:
        candidates.append(artifact.resolve())
    release_resolved = release_dir.resolve()
    for candidate in candidates:
        try:
            resolved = candidate if candidate.is_absolute() else (root / candidate)
            resolved = resolved.resolve()
        except OSError:
            continue
        if resolved == release_resolved or release_resolved in resolved.parents:
            return True
    return False


def find_launcher(root: Path) -> Path | None:
    """Return the staged ``ecli`` launcher under ``root``, or None."""
    for candidate in (
        root / "usr" / "bin" / "ecli",
        root / "usr" / "local" / "bin" / "ecli",
        root / "ecli",
        root / "ECLI.app" / "Contents" / "MacOS" / "ecli",
    ):
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
    for path in sorted(root.rglob("*")):
        if path.name in ("ecli", "ecli.exe") and path.is_file():
            try:
                depth = len(path.relative_to(root).parts)
            except ValueError:
                continue
            if depth <= 5 and os.access(path, os.X_OK):
                return path
    return None


def can_execute_artifact(artifact: Path, host_os: str) -> bool:
    """True if an artifact of this kind can run natively on ``host_os``."""
    name = artifact.name
    linux_exts = (".deb", ".rpm", ".AppImage", ".tar.gz", ".tgz", ".txz")
    if name.endswith(linux_exts) or name.endswith(".pkg.tar.zst"):
        return host_os == "Linux"
    if name.endswith(".pkg"):
        return host_os == "FreeBSD"
    if name.endswith(".dmg"):
        return host_os == "Darwin"
    if name.endswith(".exe"):
        return host_os.startswith(("MINGW", "MSYS", "CYGWIN"))
    return os.access(artifact, os.X_OK)


def _run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=True, **kwargs)  # type: ignore[arg-type]


def _extract_rpm(artifact: Path, payload: Path, root: Path) -> int:
    if shutil.which("rpm2cpio") and shutil.which("cpio"):
        rpm_input = artifact if artifact.is_absolute() else root / artifact
        cpio = subprocess.Popen(
            ["cpio", "-idm", "--quiet"],
            cwd=payload,
            stdin=subprocess.PIPE,
        )
        extractor = subprocess.Popen(["rpm2cpio", str(rpm_input)], stdout=cpio.stdin)
        if cpio.stdin is not None:
            cpio.stdin.close()
        extractor_rc = extractor.wait()
        cpio_rc = cpio.wait()
        if extractor_rc != 0 or cpio_rc != 0:
            print(
                f"RPM extraction failed for {artifact} "
                f"(rpm2cpio={extractor_rc}, cpio={cpio_rc}).",
                file=sys.stderr,
            )
            return 1
        return 0
    if shutil.which("bsdtar"):
        _run(["bsdtar", "-xf", str(artifact), "-C", str(payload)])
        return 0
    print(
        f"rpm2cpio+cpio or bsdtar is required to extract {artifact}",
        file=sys.stderr,
    )
    return 1


def _copy_executable_artifact(artifact: Path, payload: Path) -> None:
    target = payload / "ecli"
    shutil.copy2(artifact, target)
    target.chmod(0o755)


def _extract_deb_artifact(
    artifact: Path, payload: Path, tmpdir: Path, host_os: str, root: Path
) -> tuple[Path | None, int]:
    if shutil.which("dpkg-deb") is None:
        print(f"dpkg-deb is required to extract {artifact}", file=sys.stderr)
        return None, 1
    _run(["dpkg-deb", "-x", str(artifact), str(payload)])
    return payload, 0


def _extract_rpm_artifact(
    artifact: Path, payload: Path, tmpdir: Path, host_os: str, root: Path
) -> tuple[Path | None, int]:
    if _extract_rpm(artifact, payload, root) != 0:
        return None, 1
    return payload, 0


def _extract_tar_artifact(
    artifact: Path, payload: Path, tmpdir: Path, host_os: str, root: Path
) -> tuple[Path | None, int]:
    _run(["tar", "-xf", str(artifact), "-C", str(payload)])
    return payload, 0


def _extract_gzip_tar_artifact(
    artifact: Path, payload: Path, tmpdir: Path, host_os: str, root: Path
) -> tuple[Path | None, int]:
    _run(["tar", "-xzf", str(artifact), "-C", str(payload)])
    return payload, 0


def _extract_dmg_artifact(
    artifact: Path, payload: Path, tmpdir: Path, host_os: str, root: Path
) -> tuple[Path | None, int]:
    if host_os != "Darwin":
        print(
            "DMG structural inspection requires macOS; CI must run native macOS smoke.",
            file=sys.stderr,
        )
        return None, 2
    mountpoint = tmpdir / "dmg"
    mountpoint.mkdir(parents=True, exist_ok=True)
    rc = _attach_dmg(artifact, mountpoint)
    if rc != 0:
        return None, rc
    return mountpoint, 0


def _extract_executable_artifact(
    artifact: Path, payload: Path, tmpdir: Path, host_os: str, root: Path
) -> tuple[Path | None, int]:
    _copy_executable_artifact(artifact, payload)
    return payload, 0


def _artifact_extractor(artifact: Path) -> ArtifactExtractor | None:
    name = artifact.name
    extractors: tuple[tuple[tuple[str, ...], ArtifactExtractor], ...] = (
        ((".deb",), _extract_deb_artifact),
        ((".rpm",), _extract_rpm_artifact),
        ((".pkg",), _extract_tar_artifact),
        ((".tar.gz", ".tgz"), _extract_gzip_tar_artifact),
        ((".txz", ".pkg.tar.zst"), _extract_tar_artifact),
        ((".dmg",), _extract_dmg_artifact),
        ((".AppImage", ".exe"), _extract_executable_artifact),
    )
    for suffixes, extractor in extractors:
        if name.endswith(suffixes):
            return extractor
    if os.access(artifact, os.X_OK):
        return _extract_executable_artifact
    return None


def extract_artifact(
    artifact: Path, tmpdir: Path, host_os: str, root: Path
) -> tuple[Path | None, int]:
    """Extract ``artifact`` into a temp tree; return ``(payload_root, rc)``."""
    payload = tmpdir / "root"
    payload.mkdir(parents=True, exist_ok=True)

    if artifact.is_dir():
        return artifact, 0

    extractor = _artifact_extractor(artifact)
    if extractor is None:
        print(f"Unsupported artifact type: {artifact}", file=sys.stderr)
        return None, 1

    return extractor(artifact, payload, tmpdir, host_os, root)


def _attach_dmg(artifact: Path, mountpoint: Path) -> int:
    """Attach a DMG read-only on macOS; return 0 or EXIT_DMG_ATTACH."""
    for attempt in range(1, 6):
        result = subprocess.run(
            [
                "hdiutil",
                "attach",
                "-readonly",
                "-nobrowse",
                "-mountpoint",
                str(mountpoint),
                str(artifact),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return 0
        print(
            f"WARNING: hdiutil attach failed for {artifact} "
            f"(attempt {attempt}/5, rc={result.returncode}).",
            file=sys.stderr,
        )
    print(f"ERR: failed to attach DMG: {artifact}", file=sys.stderr)
    return EXIT_DMG_ATTACH


def _detach_dmg(mountpoint: Path) -> None:
    if shutil.which("hdiutil") is None:
        return
    subprocess.run(
        ["hdiutil", "detach", str(mountpoint)],
        capture_output=True,
        text=True,
        check=False,
    )


def run_structural_check(artifact: Path, payload_root: Path, host_os: str) -> bool:
    """Verify the package payload exposes the ECLI launcher; return True/False."""
    name = artifact.name
    if name.endswith(".rpm"):
        if shutil.which("rpm"):
            result = subprocess.run(
                ["rpm", "-qpl", str(artifact)],
                capture_output=True,
                text=True,
                check=True,
            )
            return any(
                re.search(r"(^|/)usr/bin/ecli$", line)
                for line in result.stdout.splitlines()
            )
        return find_launcher(payload_root) is not None
    if name.endswith(".pkg"):
        result = subprocess.run(
            ["tar", "-tf", str(artifact)], capture_output=True, text=True, check=True
        )
        return any(
            re.search(r"(^|/)usr/local/bin/ecli$", line)
            for line in result.stdout.splitlines()
        )
    if name.endswith(".dmg"):
        if host_os == "Darwin":
            return find_launcher(payload_root) is not None
        return artifact.is_file() and artifact.stat().st_size > 0
    if name.endswith(".exe"):
        return artifact.is_file() and artifact.stat().st_size > 0
    return find_launcher(payload_root) is not None


def report_launcher_missing(payload_root: Path) -> None:
    print(
        f"Runtime launcher is missing or not executable under {payload_root}",
        file=sys.stderr,
    )
    print("Extracted artifact payload:", file=sys.stderr)
    for path in sorted(payload_root.rglob("*")):
        print(f"  {path}", file=sys.stderr)


def scan_logs(home: Path) -> bool:
    """Return True if startup logs are clean, False if forbidden entries exist."""
    log_file = home / ".config" / "ecli" / "logs" / "editor.log"
    if not log_file.is_file():
        return True
    text = log_file.read_text(encoding="utf-8", errors="replace")
    if any(pattern in text for pattern in FORBIDDEN_LOG_PATTERNS):
        print("Runtime smoke created forbidden startup log entries:", file=sys.stderr)
        print(_forbidden_log_excerpt(text), file=sys.stderr)
        return False
    return True


def _redact_log_line(line: str) -> str:
    for marker in ("Bearer ", "api_key=", "token=", "password="):
        if marker in line:
            return f"{line.split(marker, 1)[0]}{marker}<redacted>"
    return line


def _forbidden_log_excerpt(text: str) -> str:
    lines = text.splitlines()
    selected: list[str] = []
    for index, line in enumerate(lines):
        if any(pattern in line for pattern in FORBIDDEN_LOG_PATTERNS):
            start = max(0, index - LOG_EXCERPT_CONTEXT)
            end = min(len(lines), index + LOG_EXCERPT_CONTEXT + 1)
            selected.extend(lines[start:end])
            break
    if not selected:
        selected = lines[: 2 * LOG_EXCERPT_CONTEXT + 1]
    excerpt = "\n".join(_redact_log_line(line) for line in selected)
    omitted = len(lines) - len(selected)
    if omitted > 0:
        excerpt = f"{excerpt}\n... omitted {omitted} log lines ..."
    return excerpt


def run_native_smoke(binary: Path, tmpdir: Path, expected_version: str) -> bool:
    """Execute --help/--version and a bounded pseudo-TTY startup; return success."""
    home = tmpdir / "home"
    home.mkdir(parents=True, exist_ok=True)
    env = {
        **os.environ,
        "HOME": str(home),
        "TERM": os.environ.get("TERM", "xterm-256color"),
    }

    help_result = subprocess.run(
        [str(binary), "--help"], env=env, capture_output=True, text=True, check=False
    )
    if not help_result.stdout:
        print("Runtime smoke --help produced no stdout.", file=sys.stderr)
        print(help_result.stderr, file=sys.stderr)
        return False

    version_result = subprocess.run(
        [str(binary), "--version"], env=env, capture_output=True, text=True, check=False
    )
    version_output = version_result.stdout.replace("\r", "").splitlines()
    first_line = version_output[0] if version_output else ""
    if first_line != expected_version:
        print(
            f"Unexpected --version output: '{first_line}' "
            f"(expected '{expected_version}')",
            file=sys.stderr,
        )
        print(version_result.stderr, file=sys.stderr)
        return False

    if shutil.which("timeout") and shutil.which("script"):
        flavor = subprocess.run(
            ["script", "--help"], capture_output=True, text=True, check=False
        )
        if "-c, --command" in (flavor.stdout + flavor.stderr):
            tty_cmd = [
                "timeout",
                "3s",
                "env",
                f"HOME={home}",
                f"TERM={env['TERM']}",
                "script",
                "-q",
                "-c",
                str(binary),
                "/dev/null",
            ]
        else:
            tty_cmd = [
                "timeout",
                "3s",
                "env",
                f"HOME={home}",
                f"TERM={env['TERM']}",
                "script",
                "-q",
                "/dev/null",
                str(binary),
            ]
        tty = subprocess.run(tty_cmd, capture_output=True, text=True, check=False)
        if tty.returncode not in (0, 124):
            print(
                f"Bare ECLI pseudo-TTY startup exited unexpectedly with status "
                f"{tty.returncode}",
                file=sys.stderr,
            )
            print(tty.stderr, file=sys.stderr)
            return False
    else:
        print(
            "WARNING: timeout or script unavailable; skipping bounded pseudo-TTY "
            "startup.",
            file=sys.stderr,
        )

    return scan_logs(home)


def report_structural_pass(artifact: Path) -> None:
    print(
        f"--> OK: structural package contract passed for {artifact} "
        "(runtime execution was not performed)"
    )


def resolve_artifact(
    artifact_arg: str | None, root: Path, version: str
) -> tuple[Path | None, int]:
    artifact = (
        default_artifact(root, version) if artifact_arg is None else Path(artifact_arg)
    )
    if not (artifact.exists() or (root / artifact).exists()):
        print(f"Runtime artifact not found: {artifact}", file=sys.stderr)
        return None, EXIT_ARTIFACT_MISSING
    if not artifact.exists():
        artifact = root / artifact
    return artifact, EXIT_OK


def handle_extract_failure(
    artifact: Path, tmpdir: Path, host_os: str, mode: str, extract_rc: int
) -> int:
    if mode == "native" or (host_os == "Darwin" and artifact.name.endswith(".dmg")):
        return extract_rc
    if run_structural_check(artifact, tmpdir / "root", host_os):
        report_structural_pass(artifact)
        return EXIT_OK
    return 1


def run_payload_validation(
    artifact: Path,
    payload_root: Path,
    tmpdir: Path,
    host_os: str,
    mode: str,
    expected_version: str,
) -> int:
    if mode == "structural":
        if run_structural_check(artifact, payload_root, host_os):
            report_structural_pass(artifact)
            return EXIT_OK
        return 1

    if mode == "native" or can_execute_artifact(artifact, host_os):
        binary = find_launcher(payload_root)
        if binary is None or not os.access(binary, os.X_OK):
            report_launcher_missing(payload_root)
            return EXIT_LAUNCHER_MISSING
        if not run_native_smoke(binary, tmpdir, expected_version):
            return 1
        print(f"--> OK: native runtime smoke passed for {artifact}")
        return EXIT_OK

    if run_structural_check(artifact, payload_root, host_os):
        report_structural_pass(artifact)
        return EXIT_OK
    return 1


def validate_artifact(
    artifact: Path, host_os: str, mode: str, expected_version: str
) -> int:
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        mountpoint = tmpdir / "dmg"
        try:
            payload_root, extract_rc = extract_artifact(
                artifact, tmpdir, host_os, Path(__file__).resolve().parent.parent
            )
            if extract_rc != 0:
                return handle_extract_failure(
                    artifact, tmpdir, host_os, mode, extract_rc
                )
            assert payload_root is not None
            return run_payload_validation(
                artifact,
                payload_root,
                tmpdir,
                host_os,
                mode,
                expected_version,
            )
        finally:
            if mountpoint.is_dir():
                _detach_dmg(mountpoint)


def main(argv: list[str] | None = None) -> int:
    """Validate a packaged ECLI launcher; return the exit code."""
    parser = argparse.ArgumentParser(
        prog="verify_runtime.py",
        description="Validate packaged ECLI launchers (native or structural).",
    )
    parser.add_argument("--mode", default="auto", help="auto|native|structural")
    parser.add_argument("--allow-nonrelease", action="store_true")
    parser.add_argument("artifact", nargs="?", default=None)
    args = parser.parse_args(argv)

    if args.mode not in VALID_MODES:
        print(f"Invalid mode: {args.mode}", file=sys.stderr)
        return EXIT_INVALID_MODE

    root = Path(__file__).resolve().parent.parent
    version = read_version(root)
    if not version:
        print("ERR: cannot read [project].version from pyproject.toml", file=sys.stderr)
        return 1
    expected_version_output = f"ecli {version}"

    artifact, rc = resolve_artifact(args.artifact, root, version)
    if artifact is None:
        return rc

    if not args.allow_nonrelease and not is_within_release(artifact, root, version):
        print(
            "Artifact is outside current project version directory "
            f"releases/{version}: {artifact}",
            file=sys.stderr,
        )
        return EXIT_OUTSIDE_RELEASE

    host_os = platform.system() or "unknown"
    return validate_artifact(artifact, host_os, args.mode, expected_version_output)


if __name__ == "__main__":
    raise SystemExit(main())
