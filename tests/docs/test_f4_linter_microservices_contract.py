# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/docs/test_f4_linter_microservices_contract.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Docs contract tests for the F4 linter microservices design.

docs/architecture/ecli-f4-linter-microservices-design.md is the
authoritative architecture contract for F4 Linter Microservices. These
tests guard that other tracked documentation does not reintroduce the
stale claims it replaced (ESLint-as-default, "install the linter pack"
as a normal post-install step) and that OS-aware Full provisioning remains
documented as a release contract, not a runtime/UI workaround.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DESIGN_DOC = "docs/architecture/ecli-f4-linter-microservices-design.md"
LINTER_LAYER_DOC = "docs/extensions/diagnostics-linter-layer.md"
MANUAL_INSTALL_DOC = "docs/extensions/f4-linter-manual-installation.md"
ARTIFACT_CONTRACT_DOC = "docs/release/artifact-contract.md"
ARTIFACT_VERIFICATION_DOC = "docs/release/artifact-verification.md"
PACKAGING_FLOWS_DOC = "docs/release/packaging-flows.md"
README_RELEASE_DOC = "docs/release/README-release.md"
RELEASE_023_DOC = "docs/release/v0.2.3.md"
INSTALL_DOC = "docs/INSTALL.md"
README_DOC = "README.md"

_STALE_PHRASES: tuple[str, ...] = (
    "doctor --install-linter-pack",
    "eslint is the default",
    "eslint as the default",
    "release surfaces",
)

_CONTRACT_DOCS: tuple[str, ...] = (
    DESIGN_DOC,
    LINTER_LAYER_DOC,
    MANUAL_INSTALL_DOC,
    ARTIFACT_CONTRACT_DOC,
    ARTIFACT_VERIFICATION_DOC,
    PACKAGING_FLOWS_DOC,
    README_RELEASE_DOC,
    RELEASE_023_DOC,
    INSTALL_DOC,
    README_DOC,
)

_MANUAL_OS_SECTIONS: tuple[str, ...] = (
    "## Windows 10/11",
    "## Debian / Ubuntu",
    "## Fedora / RHEL",
    "## openSUSE",
    "## Arch Linux",
    "## Slackware",
    "## FreeBSD",
    "## Nix / NixOS",
    "## macOS",
    "## Linux generic tarball / PyInstaller / AppImage",
    "## PyPI wheel / sdist",
)

_FIRST_CLASS_TOOLS: tuple[str, ...] = (
    "Ruff",
    "Biome",
    "markdownlint-cli2",
    "yamllint",
    "ShellCheck",
    "Zig",
    "Hadolint",
    "Taplo",
    "actionlint",
    "clang-tidy",
    "cppcheck",
    "Checkstyle",
    "PMD",
    "Cargo Clippy",
    "clang-format",
    "SpotBugs",
    "golangci-lint",
    "SQLFluff",
    "TFLint",
)

_VERSION_PROBES: tuple[str, ...] = (
    "ruff --version",
    "biome --version",
    "markdownlint-cli2 --version",
    "yamllint --version",
    "shellcheck --version",
    "zig version",
    "hadolint --version",
    "taplo --version",
    "actionlint --version",
    "clang-tidy --version",
    "cppcheck --version",
    "java -jar checkstyle.jar --version",
    "pmd --version",
    "cargo clippy -V",
    "clang-format --version",
    "spotbugs -version",
    "golangci-lint --version",
    "sqlfluff --version",
    "tflint --version",
)


def _tracked_markdown_files() -> list[str]:
    completed = subprocess.run(
        ["git", "ls-files", "*.md"],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    return [line for line in completed.stdout.splitlines() if line]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _combined_contract_text() -> str:
    return "\n".join(_read(path) for path in _CONTRACT_DOCS)


def test_f4_linter_microservices_design_doc_exists() -> None:
    assert (ROOT / DESIGN_DOC).is_file()


def test_f4_linter_manual_installation_reference_exists() -> None:
    assert (ROOT / MANUAL_INSTALL_DOC).is_file()


def test_diagnostics_linter_layer_doc_references_the_authoritative_contract() -> None:
    text = _read(LINTER_LAYER_DOC)
    assert DESIGN_DOC in text


def test_no_doc_reintroduces_stale_linter_pack_or_eslint_default_claims() -> None:
    offenders: list[tuple[str, str]] = []
    for path in _tracked_markdown_files():
        candidate = ROOT / path
        if not candidate.is_file():
            continue
        text = candidate.read_text(encoding="utf-8").lower()
        for phrase in _STALE_PHRASES:
            if phrase in text:
                offenders.append((path, phrase))
    assert offenders == []


def test_design_doc_treats_biome_zig_cpp_and_java_as_first_class() -> None:
    text = _read(DESIGN_DOC)
    for marker in ("Biome", "Zig", "C/C++", "Java"):
        assert marker in text, f"{marker!r} missing from the design doc"


def test_docs_define_os_aware_full_linter_provisioning_contract() -> None:
    text = _combined_contract_text()
    required = (
        "OS-aware",
        "exactly 21 artifact contract entries",
        "Full installer must detect the operating system and artifact context",
        "already-installed required linters/toolchains",
        "Manual linter installation is not the normal Full path",
        "source URL",
        "version pin",
        "checksum/provenance",
        "A missing required linter after ECLI Full install is a release blocker",
    )
    for marker in required:
        assert marker in text, f"{marker!r} missing from F4 provisioning docs"


def test_docs_preserve_f4_linter_namespace_contract() -> None:
    text = _read(DESIGN_DOC) + "\n" + _read(LINTER_LAYER_DOC)
    assert "src/ecli/extensions/linters/" in text
    assert "not under `src/ecli/diagnostics/`" in text
    assert "reserved for future general/system diagnostics" in text
    assert "`src/ecli/diagnostics/` is" in text


def test_docs_preserve_biome_default_and_eslint_legacy_policy() -> None:
    text = _read(DESIGN_DOC) + "\n" + _read(LINTER_LAYER_DOC)
    assert "Biome is the default ECLI web linter" in text
    assert "ESLint | Legacy/optional" in text
    assert "ESLint is legacy/optional" in text


def test_docs_preserve_first_class_systems_and_java_profiles() -> None:
    text = _read(DESIGN_DOC)
    for marker in (
        "| C/C++ | Clang-Tidy, Cppcheck, Clang-Format check |",
        "| Java | Checkstyle, PMD, SpotBugs |",
        "| Zig | Zig toolchain |",
    ):
        assert marker in text


def test_manual_installation_reference_has_required_os_sections() -> None:
    text = _read(MANUAL_INSTALL_DOC)
    for heading in _MANUAL_OS_SECTIONS:
        assert heading in text


def test_manual_installation_reference_lists_tools_and_version_probes() -> None:
    text = _read(MANUAL_INSTALL_DOC)
    for marker in _FIRST_CLASS_TOOLS:
        assert marker in text, f"{marker!r} missing from manual reference"
    for marker in _VERSION_PROBES:
        assert marker in text, f"{marker!r} missing from manual reference"


def test_release_docs_distinguish_uploaded_assets_from_github_source_archives() -> None:
    text = " ".join(
        (_read(ARTIFACT_CONTRACT_DOC) + "\n" + _read(README_RELEASE_DOC)).split()
    )
    required = (
        "21 ECLI-owned uploaded physical GitHub Release assets",
        "Assets 23",
        "Source code (zip)",
        "Source code (tar.gz)",
        "not part of the canonical 21 artifact contract entries",
        "not uploaded as separate GitHub Release assets",
    )
    for marker in required:
        assert marker in text, f"{marker!r} missing from release count contract"
