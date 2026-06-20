# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/packaging/test_scripts_python_migration_contract.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Contract guard for the completed shell-to-Python script migration.

The active packaging, build, verification, and release-helper implementations
under the scripts directory are Python-only. Windows PowerShell packaging and
FreeBSD tools outside the scripts directory are classified separately.
"""

from __future__ import annotations

import re
from pathlib import Path

from conftest import CANONICAL_ARTIFACTS, RELEASE_DOC_FILES, RepoReader


SPDX_HEADER = "SPDX-License-Identifier: GPL-2.0-only"

FORBIDDEN_RELEASE_TOKENS = (
    "twine upload",
    "uv publish",
    "python -m twine",
    "gh release",
    "gh workflow run",
    "gh run cancel",
    "gh run rerun",
    "git push",
    "git tag",
    "git commit",
    "git reset",
    "git clean",
)

REQUIRED_PYTHON_TARGETS = (
    "scripts/build_pyinstaller_linux.py",
    "scripts/build_and_package_arch.py",
    "scripts/build_and_package_deb.py",
    "scripts/build_and_package_freebsd.py",
    "scripts/build_and_package_macos.py",
    "scripts/build_and_package_opensuse_rpm.py",
    "scripts/build_and_package_rpm.py",
    "scripts/build_and_package_slackware.py",
    "scripts/build_docker.py",
    "scripts/build_freebsd_pkg.py",
    "scripts/build_freebsd_port.py",
    "scripts/check_log_invariant.py",
    "scripts/package_appimage.py",
    "scripts/publish_pypi.py",
    "scripts/sign_checksums.py",
    "scripts/verify_release_assets.py",
    "scripts/verify_runtime.py",
    "scripts/verify_artifact.py",
)

LIVE_EMPTY_FILE_ROOTS = (
    "scripts",
    "docs/release",
    "docs/contributor",
    "docs/product",
    "tests",
    ".claude",
    ".codex",
    ".github/workflows",
)

LIVE_REFERENCE_ROOTS = (
    "Makefile",
    "pyproject.toml",
    ".github/workflows",
    "docker",
    "docs/release",
    "docs/contributor",
    "docs/product",
    ".claude",
    ".codex",
    "tests",
)

SCRIPT_REFERENCE_RE = re.compile(
    r"(?P<path>(?:\./)?(?:scripts|tools)/[A-Za-z0-9_./-]+"
    r"(?:\.py|\.sh|\.ps1|\.Dockerfile|\.yml))"
)

ACTIVE_SCRIPT_SHELL_REFERENCE_RE = re.compile(
    re.escape("scripts/") + r"[^`\"'\s)>,;]+" + re.escape(".sh")
)

TEXT_SUFFIXES = {
    "",
    ".cfg",
    ".Dockerfile",
    ".ini",
    ".json",
    ".md",
    ".nsi",
    ".ps1",
    ".py",
    ".sh",
    ".toml",
    ".txt",
    ".yml",
    ".yaml",
}


def _live_files(repo_root: Path, roots: tuple[str, ...]) -> list[Path]:
    files: list[Path] = []
    for root in roots:
        path = repo_root / root
        if path.is_file():
            files.append(path)
        elif path.is_dir():
            files.extend(
                child
                for child in path.rglob("*")
                if child.is_file()
                and "__pycache__" not in child.parts
                and child.suffix in TEXT_SUFFIXES
            )
    return sorted(files)


def test_no_shell_files_remain_under_scripts(repo_root: Path) -> None:
    shell_files = sorted((repo_root / "scripts").rglob("*.sh"))
    assert shell_files == []


def test_no_empty_files_exist_in_live_contract_surfaces(repo_root: Path) -> None:
    empty_files = [
        str(path.relative_to(repo_root))
        for path in _live_files(repo_root, LIVE_EMPTY_FILE_ROOTS)
        if path.stat().st_size == 0
    ]

    assert empty_files == []


def test_script_references_in_live_surfaces_exist(repo_root: Path) -> None:
    missing: list[str] = []
    for file_path in _live_files(repo_root, LIVE_REFERENCE_ROOTS):
        text = file_path.read_text(encoding="utf-8")
        for match in SCRIPT_REFERENCE_RE.finditer(text):
            referenced = match.group("path").removeprefix("./")
            if not (repo_root / referenced).exists():
                missing.append(f"{file_path.relative_to(repo_root)} -> {referenced}")

    assert missing == []


def test_live_contracts_do_not_reference_removed_script_shell_files(
    repo_root: Path,
) -> None:
    offenders: list[str] = []
    for file_path in _live_files(repo_root, LIVE_REFERENCE_ROOTS):
        text = file_path.read_text(encoding="utf-8")
        for match in ACTIVE_SCRIPT_SHELL_REFERENCE_RE.finditer(text):
            offenders.append(f"{file_path.relative_to(repo_root)} -> {match.group(0)}")

    assert offenders == []


def test_required_python_targets_exist_and_are_non_empty(repo_root: Path) -> None:
    for target in REQUIRED_PYTHON_TARGETS:
        path = repo_root / target
        assert path.is_file(), f"missing required Python target: {target}"
        text = path.read_text(encoding="utf-8")
        assert text.strip(), f"empty target: {target}"
        assert SPDX_HEADER in text, f"missing SPDX header: {target}"
        assert text.startswith("#!/usr/bin/env python3"), (
            f"missing python3 shebang: {target}"
        )
        assert "def main(" in text, f"missing main() entrypoint: {target}"


def test_canonical_artifact_sources_are_python_for_migrated_scripts() -> None:
    shell_sources = [
        source
        for artifact in CANONICAL_ARTIFACTS
        for source in artifact.sources
        if source.startswith("scripts/") and source.endswith(".sh")
    ]

    assert shell_sources == []


def test_live_contract_surfaces_name_python_entrypoints(
    read_repo_text: RepoReader,
) -> None:
    live_blob = "\n".join(
        read_repo_text(path)
        for path in (
            "Makefile",
            "AGENTS.md",
            "CODEX.md",
            "CLAUDE.md",
            "docs/release/artifact-contract.md",
            "docs/release/packaging-flows.md",
            "docs/release/build-matrix.md",
            "docs/release/release-process.md",
            "docs/release/release-checklist.md",
            "docs/release/artifact-verification.md",
            *RELEASE_DOC_FILES,
            ".claude/build-runbook.md",
            ".claude/release-runbook.md",
            ".claude/validation-runbook.md",
            ".codex/runbooks/build.md",
            ".codex/runbooks/release.md",
            ".codex/runbooks/validation.md",
        )
    )

    for target in REQUIRED_PYTHON_TARGETS:
        assert target in live_blob, f"missing live contract reference: {target}"


def test_non_migrated_shell_surfaces_are_explicitly_classified(
    repo_root: Path,
    read_repo_text: RepoReader,
) -> None:
    hook = repo_root / ".claude" / "hooks" / "block-mutations.sh"
    chroot_tool = repo_root / "tools" / "freebsd-chroot-build.sh"
    removed_rename_tool = repo_root / "tools" / "rename-freebsd-pkg"
    removed_rename_tool = removed_rename_tool.with_suffix(".sh")
    windows_packager = repo_root / "scripts" / "build-and-package-windows.ps1"

    assert hook.is_file()
    assert chroot_tool.is_file()
    assert not removed_rename_tool.exists()
    assert windows_packager.is_file()

    docs = "\n".join(
        read_repo_text(path)
        for path in (
            "docs/release/artifact-contract.md",
            "docs/release/packaging-flows.md",
            "docs/contributor/build-from-source.md",
            "docs/contributor/development-setup.md",
            "AGENTS.md",
            "CODEX.md",
            "CLAUDE.md",
        )
    )
    assert ".claude/hooks/block-mutations.sh" in docs
    assert "tools/freebsd-chroot-build.sh" in docs
    assert "removed FreeBSD package-renaming shell helper" in docs
    assert "scripts/build-and-package-windows.ps1" in docs


def test_migration_does_not_change_active_artifact_names(
    read_repo_text: RepoReader,
) -> None:
    contract = read_repo_text("docs/release/artifact-contract.md")
    for artifact in CANONICAL_ARTIFACTS:
        assert artifact.artifact_token in contract, (
            f"active artifact token changed/missing: {artifact.artifact_token}"
        )


def test_migrated_python_scripts_have_no_release_commands(repo_root: Path) -> None:
    for target in REQUIRED_PYTHON_TARGETS:
        source = (repo_root / target).read_text(encoding="utf-8")
        for token in FORBIDDEN_RELEASE_TOKENS:
            assert token not in source, (
                f"{target} must not embed release/publish command {token!r}"
            )
