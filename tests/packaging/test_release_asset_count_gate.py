# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/packaging/test_release_asset_count_gate.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Exact 21 GitHub Release asset gate tests.

Public asset names are clean: they carry no numeric ordering prefix. The
``NN_label__`` prefixes (the historical v0.2.3 staging mistake) must be rejected
by the verifier, must not appear in the canonical name set, and must not be
uploaded by the release workflow.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from types import ModuleType

import pytest
from conftest import RepoReader, load_script_module


# The historical v0.2.3 numeric-prefix shape that is now forbidden in public
# release asset names.
PREFIXED_RE = re.compile(r"^[0-9]{2}_.*__")


@pytest.fixture
def release_assets(repo_root: Path) -> ModuleType:
    return load_script_module(
        repo_root, "scripts/verify_release_assets.py", "verify_release_assets"
    )


def _write_assets(directory: Path, names: tuple[str, ...]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name in names:
        (directory / name).write_text(f"{name}\n", encoding="utf-8")


def _run_probe_make(
    repo_root: Path,
    tmp_path: Path,
    body: str,
    target: str,
    *overrides: str,
) -> subprocess.CompletedProcess[str]:
    probe = tmp_path / "Probe.mk"
    probe.write_text(
        f"include {repo_root / 'Makefile'}\n\n{body}",
        encoding="utf-8",
    )
    return subprocess.run(
        ["make", "-f", str(probe), target, f"MAKE=make -f {probe}", *overrides],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )


# --------------------------------------------------------------------------- #
# Canonical name set shape
# --------------------------------------------------------------------------- #


def test_expected_canonical_list_has_exactly_twenty_one_versioned_assets(
    release_assets: ModuleType,
) -> None:
    names = release_assets.expected_asset_names("7.6.5")

    assert len(names) == 21
    assert len(set(names)) == 21
    assert all("7.6.5" in name for name in names)


def test_no_canonical_name_carries_a_numeric_prefix(
    release_assets: ModuleType,
) -> None:
    """The public asset contract contains clean names only."""
    names = release_assets.expected_asset_names("7.6.5")

    prefixed = [name for name in names if PREFIXED_RE.match(name)]
    assert prefixed == [], (
        f"numeric-prefixed public asset names are forbidden: {prefixed}"
    )
    assert all(name.startswith("ecli_") for name in names)


@pytest.mark.parametrize(
    "token",
    [
        "ecli_editor-7.6.5-py3-none-any.whl",
        "ecli_editor-7.6.5.tar.gz",
        "ecli_7.6.5_linux_x86_64.bin",
        "ecli_7.6.5_linux_x86_64.tar.gz",
        "ecli_7.6.5_linux_x86_64.deb",
        "ecli_7.6.5_linux_x86_64.rpm",
        "ecli_7.6.5_opensuse_x86_64.rpm",
        "ecli_7.6.5_arch_x86_64.pkg.tar.zst",
        "ecli_7.6.5_slackware_x86_64.txz",
        "ecli_7.6.5_linux_x86_64.AppImage",
        "ecli_7.6.5_freebsd_x86_64.pkg",
        "ecli_7.6.5_freebsd_ports_chroot_evidence.tar.gz",
        "ecli_7.6.5_macos_universal2_app_evidence.tar.gz",
        "ecli_7.6.5_macos_universal2.dmg",
        "ecli_7.6.5_win_x86_64.exe",
        "ecli_7.6.5_win_x86_64_setup.exe",
        "ecli_7.6.5_nix_flake_evidence.tar.gz",
        "ecli_7.6.5_nixos_package_evidence.tar.gz",
        "ecli_7.6.5_docker_deb_helper_evidence.tar.gz",
        "ecli_7.6.5_docker_rpm_helper_evidence.tar.gz",
        "ecli_7.6.5_workflow_contract_evidence.tar.gz",
    ],
)
def test_expected_list_includes_every_mandatory_surface(
    release_assets: ModuleType,
    token: str,
) -> None:
    assert token in release_assets.expected_asset_names("7.6.5")


# --------------------------------------------------------------------------- #
# Verifier accept / reject behavior
# --------------------------------------------------------------------------- #


def test_valid_temp_release_dir_with_exact_assets_passes(
    release_assets: ModuleType,
    tmp_path: Path,
) -> None:
    names = release_assets.expected_asset_names("1.2.3")
    _write_assets(tmp_path, names)
    (tmp_path / ".checksums").mkdir()

    assert (
        release_assets.verify_release_assets(tmp_path, "1.2.3")
        == release_assets.EXIT_OK
    )


@pytest.mark.parametrize(
    "asset",
    list(
        load_script_module(
            Path(__file__).resolve().parents[2],
            "scripts/verify_release_assets.py",
            "verify_release_assets",
        ).expected_asset_names("1.2.3")
    ),
)
def test_missing_mandatory_surface_fails(
    release_assets: ModuleType,
    tmp_path: Path,
    asset: str,
) -> None:
    names = tuple(
        name for name in release_assets.expected_asset_names("1.2.3") if name != asset
    )
    _write_assets(tmp_path, names)

    assert (
        release_assets.verify_release_assets(tmp_path, "1.2.3")
        == release_assets.EXIT_ASSET_MISMATCH
    )


def test_extra_file_fails(release_assets: ModuleType, tmp_path: Path) -> None:
    _write_assets(tmp_path, release_assets.expected_asset_names("1.2.3"))
    (tmp_path / "unexpected.txt").write_text("extra\n", encoding="utf-8")

    assert (
        release_assets.verify_release_assets(tmp_path, "1.2.3")
        == release_assets.EXIT_ASSET_MISMATCH
    )


def test_unexpected_top_level_directory_fails(
    release_assets: ModuleType,
    tmp_path: Path,
) -> None:
    _write_assets(tmp_path, release_assets.expected_asset_names("1.2.3"))
    (tmp_path / "unexpected-directory").mkdir()

    assert (
        release_assets.verify_release_assets(tmp_path, "1.2.3")
        == release_assets.EXIT_ASSET_MISMATCH
    )


def test_twenty_files_fail(release_assets: ModuleType, tmp_path: Path) -> None:
    _write_assets(tmp_path, release_assets.expected_asset_names("1.2.3")[:-1])

    assert (
        release_assets.verify_release_assets(tmp_path, "1.2.3")
        == release_assets.EXIT_ASSET_MISMATCH
    )


def test_twenty_two_files_fail(release_assets: ModuleType, tmp_path: Path) -> None:
    _write_assets(tmp_path, release_assets.expected_asset_names("1.2.3"))
    (tmp_path / "ecli_1.2.3_extra_surface.tar.gz").write_text(
        "extra\n", encoding="utf-8"
    )

    assert (
        release_assets.verify_release_assets(tmp_path, "1.2.3")
        == release_assets.EXIT_ASSET_MISMATCH
    )


# --------------------------------------------------------------------------- #
# Numeric-prefix rejection (issue #94)
# --------------------------------------------------------------------------- #


def test_prefixed_name_in_place_of_clean_fails(
    release_assets: ModuleType,
    tmp_path: Path,
) -> None:
    """Exactly 21 files but one carries a numeric prefix -> reject."""
    names = list(release_assets.expected_asset_names("1.2.3"))
    # Re-introduce the historical mistake on the wheel asset only.
    names[0] = "01_pypi_wheel__ecli_editor-1.2.3-py3-none-any.whl"
    _write_assets(tmp_path, tuple(names))

    assert len(list(tmp_path.iterdir())) == 21
    assert (
        release_assets.verify_release_assets(tmp_path, "1.2.3")
        == release_assets.EXIT_ASSET_MISMATCH
    )


@pytest.mark.parametrize(
    "prefixed_name",
    [
        "01_pypi_wheel__ecli_editor-1.2.3-py3-none-any.whl",
        "05_debian__ecli_1.2.3_linux_x86_64.deb",
        "16_windows_nsis__ecli_1.2.3_win_x86_64_setup.exe",
        "21_workflow_contract__ecli_1.2.3_workflow_contract_evidence.tar.gz",
    ],
)
def test_prefixed_name_added_as_extra_fails(
    release_assets: ModuleType,
    tmp_path: Path,
    prefixed_name: str,
) -> None:
    """A numeric-prefixed top-level file is rejected even alongside 21 clean ones."""
    _write_assets(tmp_path, release_assets.expected_asset_names("1.2.3"))
    (tmp_path / prefixed_name).write_text("prefixed\n", encoding="utf-8")

    assert PREFIXED_RE.match(prefixed_name)
    assert (
        release_assets.verify_release_assets(tmp_path, "1.2.3")
        == release_assets.EXIT_ASSET_MISMATCH
    )


def test_full_prefixed_staging_set_fails(
    release_assets: ModuleType,
    tmp_path: Path,
) -> None:
    """The complete old prefixed staging set (21 files) must not verify."""
    clean = release_assets.expected_asset_names("1.2.3")
    labels = (
        "01_pypi_wheel",
        "02_pypi_sdist",
        "03_linux_pyinstaller",
        "04_linux_tarball",
        "05_debian",
        "06_rpm",
        "07_opensuse",
        "08_arch",
        "09_slackware",
        "10_appimage",
        "11_freebsd_pkg",
        "12_freebsd_ports_chroot",
        "13_macos_app",
        "14_macos_dmg",
        "15_windows_portable",
        "16_windows_nsis",
        "17_nix_flake",
        "18_nixos_package",
        "19_docker_deb_helper",
        "20_docker_rpm_helper",
        "21_workflow_contract",
    )
    prefixed = tuple(
        f"{label}__{name}" for label, name in zip(labels, clean, strict=True)
    )
    _write_assets(tmp_path, prefixed)

    assert all(PREFIXED_RE.match(name) for name in prefixed)
    assert (
        release_assets.verify_release_assets(tmp_path, "1.2.3")
        == release_assets.EXIT_ASSET_MISMATCH
    )


# --------------------------------------------------------------------------- #
# Checksum sidecars
# --------------------------------------------------------------------------- #


def test_top_level_sha256_sidecar_fails_as_extra_asset(
    release_assets: ModuleType,
    tmp_path: Path,
) -> None:
    names = release_assets.expected_asset_names("1.2.3")
    _write_assets(tmp_path, names)
    (tmp_path / f"{names[0]}.sha256").write_text("0" * 64 + f"  {names[0]}\n")

    assert (
        release_assets.verify_release_assets(tmp_path, "1.2.3")
        == release_assets.EXIT_ASSET_MISMATCH
    )


def test_checksums_directory_is_allowed(
    release_assets: ModuleType, tmp_path: Path
) -> None:
    names = release_assets.expected_asset_names("1.2.3")
    _write_assets(tmp_path, names)
    checksums = tmp_path / ".checksums"
    checksums.mkdir()
    (checksums / f"{names[0]}.sha256").write_text(
        "0" * 64 + f"  {names[0]}\n",
        encoding="utf-8",
    )

    assert (
        release_assets.verify_release_assets(tmp_path, "1.2.3")
        == release_assets.EXIT_OK
    )


def test_checksum_sidecars_use_clean_public_filenames(
    release_assets: ModuleType,
    tmp_path: Path,
) -> None:
    """Sidecars under .checksums/ mirror the clean public asset names."""
    names = release_assets.expected_asset_names("1.2.3")
    _write_assets(tmp_path, names)
    checksums = tmp_path / ".checksums"
    checksums.mkdir()
    for name in names:
        sidecar = f"{name}.sha256"
        assert not PREFIXED_RE.match(sidecar)
        (checksums / sidecar).write_text("0" * 64 + f"  {name}\n", encoding="utf-8")

    # A full set of clean-named sidecars under .checksums/ keeps the top level at
    # exactly 21 and verifies cleanly.
    assert (
        release_assets.verify_release_assets(tmp_path, "1.2.3")
        == release_assets.EXIT_OK
    )
    assert {p.name for p in checksums.iterdir()} == {f"{n}.sha256" for n in names}


# --------------------------------------------------------------------------- #
# Makefile / workflow wiring
# --------------------------------------------------------------------------- #


def test_makefile_and_release_workflow_call_exact_asset_verifier(
    read_repo_text: RepoReader,
) -> None:
    makefile = read_repo_text("Makefile")
    release_workflow = read_repo_text(".github/workflows/release.yml")

    assert "validate-release-assets" in makefile
    assert "scripts/verify_release_assets.py" in release_workflow
    assert "files: releases/${{ steps.release_meta.outputs.version }}/ecli_*" in (
        release_workflow
    )
    assert "fail_on_unmatched_files: true" in release_workflow


def test_validate_gate2_separates_source_and_built_artifact_checks(
    read_repo_text: RepoReader,
) -> None:
    makefile = read_repo_text("Makefile")
    source_target = makefile[
        makefile.index(".PHONY: validate-pypi-source-contract") : makefile.index(
            ".PHONY: validate-pypi-contract"
        )
    ]
    built_target = makefile[
        makefile.index(".PHONY: validate-pypi-contract") : makefile.index(
            ".PHONY: validate-tar-linux-contract"
        )
    ]
    gate2 = makefile[
        makefile.index(".PHONY: validate-gate2") : makefile.index(
            ".PHONY: validate-built-artifacts",
            makefile.index(".PHONY: validate-gate2"),
        )
    ]
    built_artifacts = makefile[
        makefile.index(".PHONY: validate-built-artifacts") : makefile.index(
            "# =============================================================================",
            makefile.index(".PHONY: validate-built-artifacts"),
        )
    ]

    assert "scripts/publish_pypi.py --dry-run" in source_target
    assert "$(PYTHON) -m twine check --strict" not in source_target
    assert "$(PYTHON) -m twine check --strict" in built_target
    assert "$(call verify_sha256,$(PYPI_WHEEL_FILE))" in built_target

    assert "validate-pypi-source-contract" in gate2
    assert "$(call validate_pypi_artifacts_if_requested)" not in gate2
    assert "$(call validate_artifact_if_requested" not in gate2
    assert "$(call validate_release_assets_if_present)" not in gate2

    assert "$(call validate_pypi_artifacts_if_requested)" in built_artifacts
    assert "$(call validate_artifact_if_requested" in built_artifacts
    assert "$(call validate_release_assets_if_present)" in built_artifacts


def test_validate_gate2_requires_complete_artifact_sidecar_pairs(
    read_repo_text: RepoReader,
) -> None:
    makefile = read_repo_text("Makefile")
    generic_helper = makefile[
        makefile.index("define validate_artifact_if_requested") : makefile.index(
            "define validate_pypi_artifacts_if_requested"
        )
    ]
    pypi_helper = makefile[
        makefile.index("define validate_pypi_artifacts_if_requested") : makefile.index(
            "define validate_release_assets_if_present"
        )
    ]

    assert '[ -f "$(1)" ] && [ -f "$(1).sha256" ]' in generic_helper
    assert "Missing checksum sidecar for $(3): $(1).sha256" in generic_helper
    assert "Orphan checksum sidecar for $(3): $(1).sha256" in generic_helper
    assert "ERROR: incomplete PyPI artifact set" in pypi_helper
    assert 'echo "Missing $$required"' in pypi_helper


def test_single_artifact_helper_skips_when_absent(
    repo_root: Path,
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "artifact.bin"
    result = _run_probe_make(
        repo_root,
        tmp_path,
        (
            ".PHONY: probe fake-validator\n"
            "probe:\n"
            f"\t$(call validate_artifact_if_requested,{artifact},fake-validator,Probe)\n"
            "fake-validator:\n"
            "\t@echo SINGLE_VALIDATOR_INVOKED\n"
        ),
        "probe",
    )

    assert result.returncode == 0
    assert "SKIP: Probe artifact not built" in result.stdout
    assert "SINGLE_VALIDATOR_INVOKED" not in result.stdout


def test_single_artifact_helper_invokes_validator_when_complete(
    repo_root: Path,
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "artifact.bin"
    artifact.write_text("artifact\n", encoding="utf-8")
    artifact.with_name(f"{artifact.name}.sha256").write_text(
        "checksum\n", encoding="utf-8"
    )

    result = _run_probe_make(
        repo_root,
        tmp_path,
        (
            ".PHONY: probe fake-validator\n"
            "probe:\n"
            f"\t$(call validate_artifact_if_requested,{artifact},fake-validator,Probe)\n"
            "fake-validator:\n"
            "\t@echo SINGLE_VALIDATOR_INVOKED\n"
        ),
        "probe",
    )

    assert result.returncode == 0
    assert "SINGLE_VALIDATOR_INVOKED" in result.stdout


def test_single_artifact_helper_fails_when_sidecar_missing(
    repo_root: Path,
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "artifact.bin"
    artifact.write_text("artifact\n", encoding="utf-8")

    result = _run_probe_make(
        repo_root,
        tmp_path,
        (
            ".PHONY: probe fake-validator\n"
            "probe:\n"
            f"\t$(call validate_artifact_if_requested,{artifact},fake-validator,Probe)\n"
            "fake-validator:\n"
            "\t@echo SINGLE_VALIDATOR_INVOKED\n"
        ),
        "probe",
    )

    assert result.returncode != 0
    assert f"Missing checksum sidecar for Probe: {artifact}.sha256" in result.stdout
    assert "SINGLE_VALIDATOR_INVOKED" not in result.stdout


def test_single_artifact_helper_fails_when_sidecar_is_orphaned(
    repo_root: Path,
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "artifact.bin"
    artifact.with_name(f"{artifact.name}.sha256").write_text(
        "checksum\n", encoding="utf-8"
    )

    result = _run_probe_make(
        repo_root,
        tmp_path,
        (
            ".PHONY: probe fake-validator\n"
            "probe:\n"
            f"\t$(call validate_artifact_if_requested,{artifact},fake-validator,Probe)\n"
            "fake-validator:\n"
            "\t@echo SINGLE_VALIDATOR_INVOKED\n"
        ),
        "probe",
    )

    assert result.returncode != 0
    assert f"Orphan checksum sidecar for Probe: {artifact}.sha256" in result.stdout
    assert f"Missing artifact for Probe: {artifact}" in result.stdout
    assert "SINGLE_VALIDATOR_INVOKED" not in result.stdout


def _pypi_probe_paths(tmp_path: Path) -> dict[str, Path]:
    return {
        "wheel": tmp_path / "ecli_editor-1.2.3-py3-none-any.whl",
        "wheel_sha": tmp_path / "ecli_editor-1.2.3-py3-none-any.whl.sha256",
        "sdist": tmp_path / "ecli_editor-1.2.3.tar.gz",
        "sdist_sha": tmp_path / "ecli_editor-1.2.3.tar.gz.sha256",
    }


def _run_pypi_probe(
    repo_root: Path,
    tmp_path: Path,
) -> subprocess.CompletedProcess[str]:
    paths = _pypi_probe_paths(tmp_path)
    return _run_probe_make(
        repo_root,
        tmp_path,
        (
            ".PHONY: probe fake-pypi-validator\n"
            "probe:\n"
            "\t$(call validate_pypi_artifacts_if_requested)\n"
            "fake-pypi-validator:\n"
            "\t@echo PYPI_VALIDATOR_INVOKED\n"
        ),
        "probe",
        f"PYPI_PKG_DIR={tmp_path}",
        f"PYPI_WHEEL_FILE={paths['wheel']}",
        f"PYPI_SDIST_FILE={paths['sdist']}",
        "PYPI_ARTIFACT_VALIDATION_TARGET=fake-pypi-validator",
    )


def test_pypi_helper_skips_when_no_distribution_files(
    repo_root: Path,
    tmp_path: Path,
) -> None:
    result = _run_pypi_probe(repo_root, tmp_path)

    assert result.returncode == 0
    assert "SKIP: PyPI artifacts not built under" in result.stdout
    assert "PYPI_VALIDATOR_INVOKED" not in result.stdout


def test_pypi_helper_invokes_validator_for_complete_distribution_set(
    repo_root: Path,
    tmp_path: Path,
) -> None:
    for path in _pypi_probe_paths(tmp_path).values():
        path.write_text("x\n", encoding="utf-8")

    result = _run_pypi_probe(repo_root, tmp_path)

    assert result.returncode == 0
    assert "PYPI_VALIDATOR_INVOKED" in result.stdout


_PYPI_PARTIAL_CASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("wheel-only", ("wheel",)),
    ("wheel-and-wheel-sidecar", ("wheel", "wheel_sha")),
    ("orphan-wheel-sidecar", ("wheel_sha",)),
    ("sdist-only", ("sdist",)),
    ("orphan-sdist-sidecar", ("sdist_sha",)),
    ("wheel-and-sdist", ("wheel", "sdist")),
    ("wheel-and-orphan-sdist-sidecar", ("wheel", "sdist_sha")),
    ("wheel-sidecar-and-sdist", ("wheel_sha", "sdist")),
    ("wheel-sidecar-and-sdist-sidecar", ("wheel_sha", "sdist_sha")),
    ("sdist-pair-only", ("sdist", "sdist_sha")),
    ("missing-sdist-sidecar", ("wheel", "wheel_sha", "sdist")),
    ("missing-sdist", ("wheel", "wheel_sha", "sdist_sha")),
    ("missing-wheel-sidecar", ("wheel", "sdist", "sdist_sha")),
    ("missing-wheel", ("wheel_sha", "sdist", "sdist_sha")),
)


@pytest.mark.parametrize(("case_name", "present_keys"), _PYPI_PARTIAL_CASES)
def test_pypi_helper_fails_closed_for_partial_distribution_sets(
    repo_root: Path,
    tmp_path: Path,
    case_name: str,
    present_keys: tuple[str, ...],
) -> None:
    paths = _pypi_probe_paths(tmp_path)
    for key in present_keys:
        paths[key].write_text(f"{case_name}\n", encoding="utf-8")

    result = _run_pypi_probe(repo_root, tmp_path)

    assert result.returncode != 0
    assert "ERROR: incomplete PyPI artifact set under" in result.stdout
    assert "PYPI_VALIDATOR_INVOKED" not in result.stdout
    for key, path in paths.items():
        if key not in present_keys:
            assert f"Missing {path}" in result.stdout


def test_release_workflow_does_not_upload_prefixed_asset_names(
    read_repo_text: RepoReader,
) -> None:
    release_workflow = read_repo_text(".github/workflows/release.yml")

    # The old numeric-prefix upload glob must be gone.
    assert "/[0-9][0-9]_*" not in release_workflow
    # No prefixed staging destination remains in the assembly step.
    assert not re.search(r"release_dir\}/[0-9]{2}_[a-z0-9_]+__", release_workflow), (
        "release workflow must not stage numeric-prefixed asset names"
    )


def test_release_workflow_does_not_allow_official_freebsd_deferral(
    read_repo_text: RepoReader,
) -> None:
    release_workflow = read_repo_text(".github/workflows/release.yml")
    freebsd_workflow = read_repo_text(".github/workflows/freebsd-pkg.yml")

    forbidden_tokens = (
        "continue-on-error" + ": true",
        "freebsd" + "_note",
        "fail_on_unmatched_files" + ": false",
        "release" + "_tag",
    )
    for token in forbidden_tokens:
        assert token not in release_workflow
        assert token not in freebsd_workflow

    assert "gh release upload" not in freebsd_workflow
    assert "validation evidence only" in freebsd_workflow


# --------------------------------------------------------------------------- #
# Docs: clean names are canonical, numeric prefixes are historical only
# --------------------------------------------------------------------------- #


def test_release_docs_state_exact_physical_asset_rule(
    read_repo_text: RepoReader,
) -> None:
    release_docs = "\n".join(
        read_repo_text(path)
        for path in (
            "docs/release/artifact-contract.md",
            "docs/release/release-process.md",
            "docs/release/release-checklist.md",
            "docs/release/build-matrix.md",
            "docs/release/packaging-flows.md",
            "docs/release/v0.2.3.md",
        )
    )

    assert "exactly 21 ECLI-owned" in release_docs
    assert "Assets 23" in release_docs
    assert "Source code (zip)" in release_docs
    assert "Source code (tar.gz)" in release_docs
    assert "not part of the canonical 21 artifact contract entries" in " ".join(
        release_docs.split()
    )
    assert "not uploaded" in release_docs
    assert "scripts/verify_release_assets.py" in release_docs
    assert ".checksums/" in release_docs
    # Canonical names are clean (no numeric prefix).
    assert "ecli_<version>_freebsd_ports_chroot_evidence.tar.gz" in release_docs
    assert "ecli_<version>_workflow_contract_evidence.tar.gz" in release_docs


def test_current_release_docs_do_not_list_prefixed_canonical_names(
    read_repo_text: RepoReader,
) -> None:
    """Numeric prefixes may appear only as the documented v0.2.3 mistake."""
    current_canonical_docs = (
        "docs/release/artifact-contract.md",
        "docs/release/release-process.md",
        "docs/release/release-checklist.md",
        "docs/release/build-matrix.md",
        "docs/release/packaging-flows.md",
        "docs/release/artifact-verification.md",
        "docs/product/supported-platforms.md",
    )
    canonical_prefix_re = re.compile(r"[0-9]{2}_[a-z0-9_]+__ecli_(?:editor-)?<version>")
    for path in current_canonical_docs:
        text = read_repo_text(path)
        matches = canonical_prefix_re.findall(text)
        assert matches == [], f"{path} still lists prefixed canonical names: {matches}"
