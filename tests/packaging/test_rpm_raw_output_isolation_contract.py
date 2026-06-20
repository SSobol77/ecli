# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/packaging/test_rpm_raw_output_isolation_contract.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Regression contract for the RPM/openSUSE raw FPM output collision (#93).

The generic RPM target and the openSUSE RPM target once shared the same raw FPM
output path ``releases/<version>/ecli-<version>.rpm``. When the generic RPM build
ran first it left that raw file behind, so FPM refused to continue during the
openSUSE build ("File already exists, refusing to continue").

These tests pin the fix: raw/intermediate FPM output lives under ``build/`` (never
``releases/``), the two flows use distinct raw output paths, and the canonical
21-asset release contract is unchanged.
"""

from __future__ import annotations

from pathlib import Path
from types import ModuleType

import pytest
from conftest import RepoReader, load_script_module


VERSION = "0.2.3"


@pytest.fixture
def rpm(repo_root: Path) -> ModuleType:
    return load_script_module(
        repo_root, "scripts/build_and_package_rpm.py", "rpm_build"
    )


@pytest.fixture
def release_assets(repo_root: Path) -> ModuleType:
    return load_script_module(
        repo_root, "scripts/verify_release_assets.py", "verify_release_assets"
    )


def _legacy_collision_path(repo_root: Path) -> Path:
    return repo_root / "releases" / VERSION / f"ecli-{VERSION}.rpm"


def test_generic_raw_output_lives_under_build_not_releases(
    rpm: ModuleType, repo_root: Path
) -> None:
    _, _, raw = rpm.fpm_output_layout(repo_root, "ecli", VERSION, "linux")
    assert "build" in raw.parts
    assert "releases" not in raw.parts
    assert raw != _legacy_collision_path(repo_root)


def test_opensuse_raw_output_lives_under_build_not_releases(
    rpm: ModuleType, repo_root: Path
) -> None:
    _, _, raw = rpm.fpm_output_layout(repo_root, "ecli", VERSION, "opensuse")
    assert "build" in raw.parts
    assert "releases" not in raw.parts
    assert raw != _legacy_collision_path(repo_root)


def test_generic_and_opensuse_raw_outputs_are_distinct(
    rpm: ModuleType, repo_root: Path
) -> None:
    _, _, generic = rpm.fpm_output_layout(repo_root, "ecli", VERSION, "linux")
    _, _, opensuse = rpm.fpm_output_layout(repo_root, "ecli", VERSION, "opensuse")
    assert generic != opensuse
    # Distinctness is guaranteed by separate per-target build subdirectories,
    # not only by the raw filename.
    assert generic.parent != opensuse.parent


def test_raw_output_paths_match_documented_layout(
    rpm: ModuleType, repo_root: Path
) -> None:
    _, _, generic = rpm.fpm_output_layout(repo_root, "ecli", VERSION, "linux")
    _, _, opensuse = rpm.fpm_output_layout(repo_root, "ecli", VERSION, "opensuse")
    assert generic == repo_root / "build" / "rpm" / "fpm" / f"ecli-{VERSION}.rpm"
    assert (
        opensuse
        == repo_root
        / "build"
        / "opensuse-rpm"
        / "fpm"
        / f"ecli-{VERSION}-opensuse.rpm"
    )


def test_staging_dirs_are_also_target_specific(
    rpm: ModuleType, repo_root: Path
) -> None:
    _, generic_staging, _ = rpm.fpm_output_layout(repo_root, "ecli", VERSION, "linux")
    _, opensuse_staging, _ = rpm.fpm_output_layout(
        repo_root, "ecli", VERSION, "opensuse"
    )
    assert generic_staging != opensuse_staging
    assert "releases" not in generic_staging.parts
    assert "releases" not in opensuse_staging.parts


def test_script_does_not_assemble_raw_fpm_output_in_releases(
    read_repo_text: RepoReader,
) -> None:
    script = read_repo_text("scripts/build_and_package_rpm.py")
    # The historic buggy raw path inside releases/<version>/ must stay gone.
    assert 'releases_dir / f"{package_name}-{version}.rpm"' not in script
    # The target-specific build/ layout must drive the FPM --package path.
    assert "fpm_output_layout(" in script
    # The canonical normalized release name must remain unchanged.
    assert (
        'f"{package_name}_{version}_{platform_label}_{arch}.rpm"' in script
    )


def test_canonical_release_asset_names_unchanged(
    release_assets: ModuleType,
) -> None:
    names = release_assets.expected_asset_names(VERSION)
    assert f"06_rpm__ecli_{VERSION}_linux_x86_64.rpm" in names
    assert f"07_opensuse__ecli_{VERSION}_opensuse_x86_64.rpm" in names


def test_raw_fpm_basenames_are_never_release_assets(
    rpm: ModuleType, release_assets: ModuleType, repo_root: Path
) -> None:
    names = set(release_assets.expected_asset_names(VERSION))
    _, _, generic = rpm.fpm_output_layout(repo_root, "ecli", VERSION, "linux")
    _, _, opensuse = rpm.fpm_output_layout(repo_root, "ecli", VERSION, "opensuse")
    assert generic.name not in names
    assert opensuse.name not in names
    # The historic collision filename is not a top-level release asset either.
    assert f"ecli-{VERSION}.rpm" not in names


def test_verifier_still_defines_exactly_21_assets(
    release_assets: ModuleType,
) -> None:
    assert len(release_assets.ASSET_TEMPLATES) == 21
    names = release_assets.expected_asset_names(VERSION)
    assert len(names) == 21
    assert len(set(names)) == 21
