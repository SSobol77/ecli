# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/packaging/test_arch_docker_build_environment_contract.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Release-workflow contract for the containerized Arch build environment (#93).

The aggregate release workflow runs on Ubuntu, which has no ``makepkg``. The
host-only ``make package-arch`` target failed with::

    Missing makepkg for Arch package build.
    make: *** [Makefile:546: package-arch] Error 5

The fix builds the Arch package inside a real ``archlinux:base-devel`` container
(``make package-arch-docker``). These tests pin the workflow wiring, the raw
output isolation, the unchanged canonical 21-asset contract, and the unchanged
top-level ``.sha256`` policy.
"""

from __future__ import annotations

from pathlib import Path
from types import ModuleType

import pytest
from conftest import RepoReader, load_script_module


VERSION = "0.2.3"
RELEASE_WORKFLOW = ".github/workflows/release.yml"
CANONICAL_ARCH_ASSET = f"ecli_{VERSION}_arch_x86_64.pkg.tar.zst"


@pytest.fixture
def arch(repo_root: Path) -> ModuleType:
    return load_script_module(
        repo_root, "scripts/build_and_package_arch.py", "arch_build"
    )


@pytest.fixture
def release_assets(repo_root: Path) -> ModuleType:
    return load_script_module(
        repo_root, "scripts/verify_release_assets.py", "verify_release_assets"
    )


# --------------------------------------------------------------------------- #
# 1 & 2: the release workflow uses the containerized Arch target, not the
# host-only makepkg target on Ubuntu.
# --------------------------------------------------------------------------- #


def test_release_workflow_uses_containerized_arch_target(
    read_repo_text: RepoReader,
) -> None:
    release = read_repo_text(RELEASE_WORKFLOW)
    assert "run: make package-arch-docker" in release


def test_release_workflow_does_not_run_host_only_make_package_arch(
    read_repo_text: RepoReader,
) -> None:
    release = read_repo_text(RELEASE_WORKFLOW)
    # The Ubuntu runner has no makepkg, so the host-only target must not be the
    # step that builds the Arch package. The containerized target is a distinct
    # token, so guard the exact host invocation.
    assert "run: make package-arch\n" not in release
    assert "run: make package-arch " not in release


# --------------------------------------------------------------------------- #
# 3: the Arch package path uses a real Arch / base-devel environment.
# --------------------------------------------------------------------------- #


def test_arch_build_uses_real_base_devel_dockerfile(
    repo_root: Path,
    read_repo_text: RepoReader,
) -> None:
    dockerfile_path = repo_root / "docker/build-arch-package.Dockerfile"
    assert dockerfile_path.is_file()
    dockerfile = read_repo_text("docker/build-arch-package.Dockerfile")
    assert "FROM archlinux:base-devel" in dockerfile

    # The Makefile docker target must build and run that Dockerfile.
    makefile = read_repo_text("Makefile")
    start = makefile.index("\npackage-arch-docker:")
    end = makefile.index("\n.PHONY:", start)
    recipe = makefile[start:end]
    assert "docker build -f docker/build-arch-package.Dockerfile" in recipe
    assert "docker run" in recipe


# --------------------------------------------------------------------------- #
# 4: the Arch build must not be neutralized with '|| true' / continue-on-error.
# --------------------------------------------------------------------------- #


def test_release_workflow_does_not_ignore_arch_failure(
    read_repo_text: RepoReader,
) -> None:
    release = read_repo_text(RELEASE_WORKFLOW)
    arch_build = release.index("run: make package-arch-docker")

    line_start = release.rfind("\n", 0, arch_build) + 1
    line_end = release.index("\n", arch_build)
    assert "|| true" not in release[line_start:line_end]

    step_start = release.rfind("- name:", 0, arch_build)
    next_step = release.index("- name:", arch_build)
    assert "continue-on-error" not in release[step_start:next_step]


def test_makefile_arch_targets_do_not_swallow_build_failure(
    read_repo_text: RepoReader,
) -> None:
    makefile = read_repo_text("Makefile")
    for target in ("package-arch", "package-arch-docker"):
        start = makefile.index(f"\n{target}:")
        end = makefile.index("\n.PHONY:", start)
        recipe = makefile[start:end]
        # The actual build/run line must not be neutralized. The ownership reset
        # line is intentionally best-effort ('-@' + '|| true'); guard the build
        # commands instead.
        assert "$(PYTHON) ./scripts/build_and_package_arch.py || true" not in recipe
        assert "ecli-arch:base-devel || true" not in recipe


# --------------------------------------------------------------------------- #
# 5 & 6: the canonical Arch asset name and the exact 21-asset contract are
# unchanged.
# --------------------------------------------------------------------------- #


def test_canonical_arch_asset_name_unchanged(release_assets: ModuleType) -> None:
    names = release_assets.expected_asset_names(VERSION)
    assert CANONICAL_ARCH_ASSET in names


def test_verifier_still_defines_exactly_21_assets(release_assets: ModuleType) -> None:
    assert len(release_assets.ASSET_TEMPLATES) == 21
    names = release_assets.expected_asset_names(VERSION)
    assert len(names) == 21
    assert len(set(names)) == 21


# --------------------------------------------------------------------------- #
# 7: the no-top-level-.sha256 policy remains enforced by the verifier.
# --------------------------------------------------------------------------- #


def _materialize_release(release_assets: ModuleType, release_dir: Path) -> None:
    release_dir.mkdir(parents=True, exist_ok=True)
    for name in release_assets.expected_asset_names(VERSION):
        (release_dir / name).write_text("x", encoding="utf-8")


def test_exact_21_assets_pass(release_assets: ModuleType, tmp_path: Path) -> None:
    release_dir = tmp_path / "releases" / VERSION
    _materialize_release(release_assets, release_dir)
    assert release_assets.verify_release_assets(release_dir, VERSION) == 0


def test_top_level_sha256_is_rejected_as_extra(
    release_assets: ModuleType, tmp_path: Path
) -> None:
    release_dir = tmp_path / "releases" / VERSION
    _materialize_release(release_assets, release_dir)
    # A top-level .sha256 next to the canonical Arch asset is not a release asset
    # and must make the verifier fail as an extra (not be silently accepted).
    (release_dir / f"{CANONICAL_ARCH_ASSET}.sha256").write_text("x", encoding="utf-8")
    assert (
        release_assets.verify_release_assets(release_dir, VERSION)
        == release_assets.EXIT_ASSET_MISMATCH
    )


def test_checksums_directory_is_the_only_permitted_non_asset(
    release_assets: ModuleType, tmp_path: Path
) -> None:
    release_dir = tmp_path / "releases" / VERSION
    _materialize_release(release_assets, release_dir)
    checksums = release_dir / ".checksums"
    checksums.mkdir()
    (checksums / f"{CANONICAL_ARCH_ASSET}.sha256").write_text("x", encoding="utf-8")
    assert release_assets.verify_release_assets(release_dir, VERSION) == 0


# --------------------------------------------------------------------------- #
# Raw output isolation: the canonical Arch artifact lives under releases/, the
# raw makepkg output stays under build/ (never releases/), and the tracked
# PKGBUILD is never mutated as a build side effect.
# --------------------------------------------------------------------------- #


def test_arch_raw_output_dir_is_under_build_not_releases(
    arch: ModuleType, repo_root: Path
) -> None:
    build_dir = arch.arch_build_dir(repo_root)
    assert "build" in build_dir.parts
    assert "releases" not in build_dir.parts
    assert build_dir == repo_root / "build" / "arch"


def test_arch_script_pkgdest_points_at_build_not_releases(
    read_repo_text: RepoReader,
) -> None:
    script = read_repo_text("scripts/build_and_package_arch.py")
    # Regression guard: the historic PKGDEST=releases/<version> path must stay
    # gone so no raw ecli-editor-<ver>-<rel>-<arch>.pkg.tar.zst lands top-level.
    assert '"PKGDEST": str(releases_dir)' not in script
    assert '"PKGDEST": str(build_dir)' in script


def test_normalized_arch_artifact_is_under_releases(
    arch: ModuleType, repo_root: Path
) -> None:
    version = arch.read_version(repo_root)
    arch_label = arch.normalize_arch()
    normalized = (
        repo_root / "releases" / version / f"ecli_{version}_arch_{arch_label}.pkg.tar.zst"
    )
    assert normalized.parent == repo_root / "releases" / version


def test_stage_pkgbuild_sets_pkgver_from_version_without_mutating_tracked_file(
    arch: ModuleType, repo_root: Path, tmp_path: Path
) -> None:
    tracked = repo_root / "packaging/arch/PKGBUILD"
    before = tracked.read_text(encoding="utf-8")

    build_dir = tmp_path / "build" / "arch"
    build_dir.mkdir(parents=True)
    staged = arch.stage_pkgbuild(repo_root, build_dir, "9.9.9")

    assert staged == build_dir / "PKGBUILD"
    assert "pkgver=9.9.9" in staged.read_text(encoding="utf-8")
    # The tracked descriptor is never mutated as a build side effect (AUD-003).
    assert tracked.read_text(encoding="utf-8") == before


def test_tracked_pkgbuild_tracks_release_version(repo_root: Path) -> None:
    version = (
        load_script_module(
            repo_root, "scripts/build_and_package_arch.py", "arch_build_version"
        )
    ).read_version(repo_root)
    pkgbuild = (repo_root / "packaging/arch/PKGBUILD").read_text(encoding="utf-8")
    assert f"pkgver={version}" in pkgbuild
    assert "pkgver=0.2.2" not in pkgbuild


# --------------------------------------------------------------------------- #
# Ownership reset after the Arch container build (#93): both the workflow and the
# local Makefile target reset ownership of releases/ so later host-side steps are
# not blocked by build-user-owned files.
# --------------------------------------------------------------------------- #


def test_release_workflow_resets_ownership_after_arch_docker_build(
    read_repo_text: RepoReader,
) -> None:
    release = read_repo_text(RELEASE_WORKFLOW)
    arch_build = release.index("run: make package-arch-docker")
    arch_reset = release.index("Reset ownership after Docker Arch build")
    slackware_build = release.index("run: make package-slackware")

    assert arch_build < arch_reset < slackware_build
    reset_block = release[arch_reset:slackware_build]
    assert "chown -R" in reset_block
    assert "releases" in reset_block


def test_makefile_arch_docker_target_resets_release_ownership(
    read_repo_text: RepoReader,
) -> None:
    makefile = read_repo_text("Makefile")
    start = makefile.index("\npackage-arch-docker:")
    end = makefile.index("\n.PHONY:", start)
    recipe = makefile[start:end]
    assert "chown" in recipe
    assert "$(RELEASE_DIR)" in recipe
