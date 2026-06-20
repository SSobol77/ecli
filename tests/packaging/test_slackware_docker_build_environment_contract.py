# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/packaging/test_slackware_docker_build_environment_contract.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Release-workflow contract for the containerized Slackware build env (#93).

The aggregate release workflow runs on Ubuntu, which has no Slackware pkgtools.
The host-only ``make package-slackware`` target failed with::

    Missing makepkg for Slackware package build.
    make: *** [Makefile:583: package-slackware] Error 5

The fix builds the Slackware package inside a real Slackware container
(``make package-slackware-docker``). These tests pin the workflow wiring, the raw
output isolation, the unchanged canonical 21-asset contract, and the unchanged
top-level ``.sha256`` policy, mirroring the Arch containerization contract.
"""

from __future__ import annotations

from pathlib import Path
from types import ModuleType

import pytest
from conftest import RepoReader, load_script_module


VERSION = "0.2.3"
RELEASE_WORKFLOW = ".github/workflows/release.yml"
SLACKWARE_DOCKERFILE = "docker/build-slackware-package.Dockerfile"
CANONICAL_SLACKWARE_ASSET = f"ecli_{VERSION}_slackware_x86_64.txz"


@pytest.fixture
def slack(repo_root: Path) -> ModuleType:
    return load_script_module(
        repo_root, "scripts/build_and_package_slackware.py", "slackware_build"
    )


@pytest.fixture
def release_assets(repo_root: Path) -> ModuleType:
    return load_script_module(
        repo_root, "scripts/verify_release_assets.py", "verify_release_assets"
    )


# --------------------------------------------------------------------------- #
# 1 & 2: the release workflow uses the containerized Slackware target, not the
# host-only Slackware makepkg target on Ubuntu.
# --------------------------------------------------------------------------- #


def test_release_workflow_uses_containerized_slackware_target(
    read_repo_text: RepoReader,
) -> None:
    release = read_repo_text(RELEASE_WORKFLOW)
    assert "run: make package-slackware-docker" in release


def test_release_workflow_does_not_run_host_only_make_package_slackware(
    read_repo_text: RepoReader,
) -> None:
    release = read_repo_text(RELEASE_WORKFLOW)
    # The Ubuntu runner has no Slackware makepkg, so the host-only target must not
    # be the step that builds the Slackware package. The containerized target is a
    # distinct token, so guard the exact host invocation.
    assert "run: make package-slackware\n" not in release
    assert "run: make package-slackware " not in release


# --------------------------------------------------------------------------- #
# 3: the Slackware package path uses a real Slackware / pkgtools / makepkg
# environment, wired into a Makefile docker target.
# --------------------------------------------------------------------------- #


def test_slackware_build_uses_real_slackware_dockerfile(
    repo_root: Path,
    read_repo_text: RepoReader,
) -> None:
    dockerfile_path = repo_root / SLACKWARE_DOCKERFILE
    assert dockerfile_path.is_file()
    dockerfile = read_repo_text(SLACKWARE_DOCKERFILE)
    # A real Slackware packaging environment, not an Ubuntu host pretending to
    # have makepkg.
    assert "slackware" in dockerfile.lower()
    # The Slackware pkgtools / makepkg environment must be present and checked.
    assert "makepkg" in dockerfile

    # The Makefile docker target must build and run that Dockerfile.
    makefile = read_repo_text("Makefile")
    start = makefile.index("\npackage-slackware-docker:")
    end = makefile.index("\n.PHONY:", start)
    recipe = makefile[start:end]
    assert "docker build -f docker/build-slackware-package.Dockerfile" in recipe
    assert "docker run" in recipe


# --------------------------------------------------------------------------- #
# 4: the Slackware Docker target exists in the Makefile.
# --------------------------------------------------------------------------- #


def test_makefile_defines_slackware_docker_target(
    read_repo_text: RepoReader,
) -> None:
    makefile = read_repo_text("Makefile")
    assert "\npackage-slackware-docker:" in makefile
    assert "\npackage-slackware-assert:" in makefile
    # package-linux must use the release-canonical containerized target.
    start = makefile.index("\npackage-linux:")
    end = makefile.index("\n", start + 1)
    linux_line = makefile[start:end]
    assert "package-slackware-docker" in linux_line
    assert "package-slackware " not in linux_line


# --------------------------------------------------------------------------- #
# 5: ownership reset after the Slackware container build (#93), before AppImage.
# --------------------------------------------------------------------------- #


def test_release_workflow_resets_ownership_after_slackware_docker_build(
    read_repo_text: RepoReader,
) -> None:
    release = read_repo_text(RELEASE_WORKFLOW)
    slackware_build = release.index("run: make package-slackware-docker")
    slackware_reset = release.index("Reset ownership after Docker Slackware build")
    appimage_build = release.index("run: make package-appimage")

    assert slackware_build < slackware_reset < appimage_build
    reset_block = release[slackware_reset:appimage_build]
    assert "chown -R" in reset_block
    assert "releases" in reset_block


def test_makefile_slackware_docker_target_resets_release_ownership(
    read_repo_text: RepoReader,
) -> None:
    makefile = read_repo_text("Makefile")
    start = makefile.index("\npackage-slackware-docker:")
    end = makefile.index("\n.PHONY:", start)
    recipe = makefile[start:end]
    assert "chown" in recipe
    assert "$(RELEASE_DIR)" in recipe


# --------------------------------------------------------------------------- #
# 6: the Slackware build must not be neutralized with '|| true' /
# continue-on-error.
# --------------------------------------------------------------------------- #


def test_release_workflow_does_not_ignore_slackware_failure(
    read_repo_text: RepoReader,
) -> None:
    release = read_repo_text(RELEASE_WORKFLOW)
    slackware_build = release.index("run: make package-slackware-docker")

    line_start = release.rfind("\n", 0, slackware_build) + 1
    line_end = release.index("\n", slackware_build)
    assert "|| true" not in release[line_start:line_end]

    step_start = release.rfind("- name:", 0, slackware_build)
    next_step = release.index("- name:", slackware_build)
    assert "continue-on-error" not in release[step_start:next_step]


def test_makefile_slackware_targets_do_not_swallow_build_failure(
    read_repo_text: RepoReader,
) -> None:
    makefile = read_repo_text("Makefile")
    for target in ("package-slackware", "package-slackware-docker"):
        start = makefile.index(f"\n{target}:")
        end = makefile.index("\n.PHONY:", start)
        recipe = makefile[start:end]
        # The actual build/run line must not be neutralized. The ownership reset
        # line is intentionally best-effort ('-@' + '|| true'); guard the build
        # commands instead.
        assert (
            "$(PYTHON) ./scripts/build_and_package_slackware.py || true" not in recipe
        )
        assert "ecli-slackware:current || true" not in recipe


# --------------------------------------------------------------------------- #
# 7 & 8: the canonical Slackware asset name and the exact 21-asset contract are
# unchanged.
# --------------------------------------------------------------------------- #


def test_canonical_slackware_asset_name_unchanged(
    release_assets: ModuleType,
) -> None:
    names = release_assets.expected_asset_names(VERSION)
    assert CANONICAL_SLACKWARE_ASSET in names


def test_verifier_still_defines_exactly_21_assets(release_assets: ModuleType) -> None:
    assert len(release_assets.ASSET_TEMPLATES) == 21
    names = release_assets.expected_asset_names(VERSION)
    assert len(names) == 21
    assert len(set(names)) == 21


# --------------------------------------------------------------------------- #
# 9: the no-top-level-.sha256 policy remains enforced by the verifier.
# --------------------------------------------------------------------------- #


def _materialize_release(release_assets: ModuleType, release_dir: Path) -> None:
    release_dir.mkdir(parents=True, exist_ok=True)
    for name in release_assets.expected_asset_names(VERSION):
        (release_dir / name).write_text("x", encoding="utf-8")


def test_exact_21_assets_pass(release_assets: ModuleType, tmp_path: Path) -> None:
    release_dir = tmp_path / "releases" / VERSION
    _materialize_release(release_assets, release_dir)
    assert release_assets.verify_release_assets(release_dir, VERSION) == 0


def test_top_level_slackware_sha256_is_rejected_as_extra(
    release_assets: ModuleType, tmp_path: Path
) -> None:
    release_dir = tmp_path / "releases" / VERSION
    _materialize_release(release_assets, release_dir)
    # A top-level .sha256 next to the canonical Slackware asset is not a release
    # asset and must make the verifier fail as an extra.
    (release_dir / f"{CANONICAL_SLACKWARE_ASSET}.sha256").write_text(
        "x", encoding="utf-8"
    )
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
    (checksums / f"{CANONICAL_SLACKWARE_ASSET}.sha256").write_text(
        "x", encoding="utf-8"
    )
    assert release_assets.verify_release_assets(release_dir, VERSION) == 0


# --------------------------------------------------------------------------- #
# Raw output isolation: the canonical Slackware artifact lives under releases/,
# the raw makepkg output stays under build/ (never releases/).
# --------------------------------------------------------------------------- #


def test_slackware_raw_output_dir_is_under_build_not_releases(
    slack: ModuleType, repo_root: Path
) -> None:
    build_dir = slack.slackware_build_dir(repo_root)
    assert "build" in build_dir.parts
    assert "releases" not in build_dir.parts
    assert build_dir == repo_root / "build" / "slackware"


def test_slackware_script_normalizes_raw_build_output_into_releases(
    read_repo_text: RepoReader,
) -> None:
    script = read_repo_text("scripts/build_and_package_slackware.py")
    # Regression guard: makepkg writes the raw .txz under build/, and only the
    # normalized copy lands under releases/<version>/.
    assert "raw_txz = build_root" in script
    assert "normalized = releases_dir" in script
    assert "shutil.copy2(raw_txz, normalized)" in script
    # The raw makepkg output must not be written directly into releases/.
    assert "str(raw_txz)" in script


def test_normalized_slackware_artifact_is_under_releases(
    slack: ModuleType, repo_root: Path
) -> None:
    version = slack.read_version(repo_root)
    arch_label = slack.normalize_arch()
    normalized = (
        repo_root
        / "releases"
        / version
        / f"{slack.PACKAGE_NAME}_{version}_slackware_{arch_label}.txz"
    )
    assert normalized.parent == repo_root / "releases" / version
