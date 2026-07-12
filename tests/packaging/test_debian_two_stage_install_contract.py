# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/packaging/test_debian_two_stage_install_contract.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Contract tests for the two-stage Debian installation model.

Stage 1: ``scripts/install_ecli_linters.py`` provisions the 19-tool F4
linter toolchain. Stage 2: the ECLI ``.deb`` installs ECLI itself. The
``.deb`` never deletes user data, never provisions linters, and Snap
stays outside the canonical 21-artifact release contract.
"""

from __future__ import annotations

import json
import stat
from pathlib import Path

import pytest
from conftest import CANONICAL_ARTIFACTS


REPO_ROOT = Path(__file__).resolve().parents[2]
FPM_COMMON = REPO_ROOT / "packaging" / "linux" / "fpm-common"
LOCK_PATH = REPO_ROOT / "packaging" / "debian" / "ecli-linter-lock.json"
NPM_LOCK_DIR = REPO_ROOT / "packaging" / "debian" / "markdownlint-cli2"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class TestMaintainerScriptsPreserveUserData:
    @pytest.mark.parametrize("name", ["postinst", "prerm", "postrm"])
    def test_scripts_are_posix_sh_and_executable(self, name):
        script = FPM_COMMON / name
        text = _read(script)
        assert text.startswith("#!/bin/sh\n"), f"{name} must use POSIX /bin/sh"
        mode = stat.S_IMODE(script.stat().st_mode)
        assert mode & 0o755 == 0o755, f"{name} must be mode 0755"

    @pytest.mark.parametrize("name", ["postinst", "prerm", "postrm"])
    def test_scripts_never_touch_user_configuration(self, name):
        text = _read(FPM_COMMON / name)
        assert "rm -rf" not in text, f"{name} must not recursively delete"
        assert "/home/*" not in text, f"{name} must not iterate /home/*"
        assert "for homedir" not in text, f"{name} must not enumerate homes"

    @pytest.mark.parametrize("name", ["postinst", "prerm", "postrm"])
    def test_scripts_are_offline_and_apt_free(self, name):
        text = _read(FPM_COMMON / name)
        for forbidden in ("apt-get", "apt install", "curl ", "wget ", "npm "):
            assert forbidden not in text, f"{name} must not invoke {forbidden!r}"

    def test_purge_preserves_root_and_home_configuration(self):
        text = _read(FPM_COMMON / "postrm")
        assert "preserves" in text or "never" in text.lower()
        assert ".config/ecli" not in text.replace("~/.config/ecli", "").replace(
            "/root/.config/ecli", ""
        ), "postrm must not carry deletable user-config paths"

    def test_postinst_payload_check_cannot_fail_install(self):
        text = _read(FPM_COMMON / "postinst")
        assert "/opt/ecli/payload/bin" in text
        assert text.rstrip().endswith("exit 0")
        assert "exit 1" not in text

    def test_postinst_never_references_a_repo_relative_script_path(self):
        """Postinst runs on a machine that may only ever have installed the
        .deb -- it must never point at a repository-relative script path
        that only exists inside a source checkout, since that path will
        not exist on such a machine.
        """
        text = _read(FPM_COMMON / "postinst")
        assert "scripts/install_ecli_linters.py" not in text
        assert "sudo python3 scripts/" not in text


class TestInstallerDistributionContract:
    """docs/install/debian.md must document how to obtain the standalone
    installer bundle -- copying only the .py file is not sufficient, its
    lock inputs live alongside it -- and must not assume a Python 3
    interpreter is already present on a minimal Debian 13 install.
    """

    def test_documents_the_four_file_bundle_layout(self):
        text = _read(REPO_ROOT / "docs" / "install" / "debian.md")
        for required in (
            "install_ecli_linters.py",
            "ecli-linter-lock.json",
            "markdownlint-cli2/",
            "package.json",
            "package-lock.json",
        ):
            assert required in text, required

    def test_documents_python3_prerequisite_for_minimal_debian(self):
        text = _read(REPO_ROOT / "docs" / "install" / "debian.md")
        assert "apt-get install -y python3" in text

    def test_documents_a_no_clone_bootstrap_path(self):
        """Users without a repository checkout must have a documented way
        to fetch just the four bundle files.
        """
        text = _read(REPO_ROOT / "docs" / "install" / "debian.md")
        assert "curl" in text
        assert "raw.githubusercontent.com" in text


class TestMinimalDebOnlyInstallScript:
    """The minimal .deb-only proof must run BEFORE the full two-stage
    integration test and must not run the linter installer, preinstall
    Python, or preinstall any F4 toolchain package.
    """

    SCRIPT = REPO_ROOT / "packaging" / "debian" / "verify_deb_minimal_install.sh"

    def test_script_exists_and_is_executable_posix_sh(self):
        text = _read(self.SCRIPT)
        assert text.startswith("#!/bin/sh\n")
        mode = stat.S_IMODE(self.SCRIPT.stat().st_mode)
        assert mode & 0o755 == 0o755

    def test_script_never_runs_the_linter_installer(self):
        # The header comment documents (in prose) that this script does
        # NOT run the installer -- that mention is fine. What must never
        # appear is an actual invocation of it.
        text = _read(self.SCRIPT)
        assert "python3 scripts/install_ecli_linters.py" not in text
        assert "python3 install_ecli_linters.py" not in text

    def test_script_never_preinstalls_python_or_toolchain_packages(self):
        text = _read(self.SCRIPT)
        assert "apt-get install -y python3" not in text
        assert "apt-get install -y -qq python3" not in text
        # apt-get install is invoked exactly once (against the .deb
        # argument, asserted separately below); it never names a linter
        # package, so no apt-get call can be preinstalling the toolchain.
        assert text.count("apt-get install") == 1

    def test_script_installs_only_the_deb_argument(self):
        text = _read(self.SCRIPT)
        # apt-get install is invoked exactly once, against the $DEB argv,
        # never against a package name list.
        assert 'apt-get install -y "$DEB"' in text
        assert text.count("apt-get install") == 1

    def test_script_verifies_version_and_ldd_resolution(self):
        text = _read(self.SCRIPT)
        assert "ecli --version" in text
        assert "ldd " in text
        assert "not found" in text


class TestTwoStageSeparation:
    def test_installer_exists_and_is_standalone(self):
        import ast

        installer = REPO_ROOT / "scripts" / "install_ecli_linters.py"
        text = _read(installer)
        assert "import ecli" not in text and "from ecli" not in text
        tree = ast.parse(text)
        docstrings = set()
        for node in ast.walk(tree):
            if isinstance(
                node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
            ):
                body = getattr(node, "body", [])
                if (
                    body
                    and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                ):
                    docstrings.add(id(body[0].value))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                assert all(keyword.arg != "shell" for keyword in node.keywords)
            if (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and id(node) not in docstrings
            ):
                assert "releases/latest" not in node.value, (
                    "installer code must never query releases/latest"
                )

    def test_deb_build_never_bundles_linter_payload(self):
        import ast

        text = _read(REPO_ROOT / "scripts" / "build_and_package_deb.py")
        assert "/opt/ecli/payload" not in text, (
            "the .deb must not stage or modify the linter payload"
        )
        # The package description may *mention* the stage-1 installer, but
        # the build must never execute it or pass it to any command.
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            for arg in ast.walk(node):
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                    assert "install_ecli_linters" not in arg.value, (
                        "the .deb build must not invoke the linter installer"
                    )

    def test_lock_is_committed_and_pinned(self):
        lock = json.loads(_read(LOCK_PATH))
        tools = lock["tools"]
        assert len(tools) == 11
        for tool_id, entry in tools.items():
            assert entry["asset_url"].startswith("https://"), tool_id
            assert "latest" not in entry["asset_url"], tool_id
            assert "master" not in str(entry["version"]).lower(), tool_id
            assert len(entry["sha256"]) == 64, tool_id
            assert entry["architecture"] == "amd64", tool_id

    def test_npm_lock_inputs_are_committed(self):
        manifest = json.loads(_read(NPM_LOCK_DIR / "package.json"))
        lockfile = json.loads(_read(NPM_LOCK_DIR / "package-lock.json"))
        pinned = manifest["dependencies"]["markdownlint-cli2"]
        assert (
            pinned == lockfile["packages"]["node_modules/markdownlint-cli2"]["version"]
        )
        assert not pinned.startswith(("^", "~", ">", "<", "*")), (
            "markdownlint-cli2 must be pinned exactly"
        )


class TestDebPackagingHygiene:
    def test_deb_ships_only_postinst_never_empty_maintainer_scripts(self):
        """Empty prerm/postrm must not be packaged (Debian policy).

        The files stay in packaging/linux/fpm-common for the RPM pipeline,
        but the .deb build must not attach them.
        """
        text = _read(REPO_ROOT / "scripts" / "build_and_package_deb.py")
        assert "--after-install" in text
        assert "--before-remove" not in text
        assert "--after-remove" not in text

    def test_deb_build_carries_lintian_hygiene(self):
        text = _read(REPO_ROOT / "scripts" / "build_and_package_deb.py")
        assert '"libc6",' in text, "libc.so.6 is NEEDED; libc6 must be a dependency"
        assert "debian_copyright" in text
        assert "debian_changelog" in text
        assert "strip_control_fields" in text
        assert "hardening-no-pie" in text
        assert "SOURCE_DATE_EPOCH" in text
        synopsis = text.split('DEB_DESCRIPTION = (\n    "', 1)[1].split("\\n", 1)[0]
        assert not synopsis.lower().startswith("ecli"), (
            "Debian synopsis must not start with the package name"
        )

    def test_lintian_override_is_context_free_for_cross_version_portability(
        self, repo_root
    ):
        """The override file syntax for a tag's context is not portable
        across the two lintian releases this pipeline runs (bullseye
        2.104 build gate vs. trixie 2.122 downstream validation): one
        wants a bracket-free context, the other wants brackets, and each
        rejects the other's format as a "mismatched-override" no-op. A
        context-free override (unambiguous here since the package ships
        exactly one ELF binary) works identically on both.
        """
        from conftest import load_script_module

        module = load_script_module(
            repo_root, "scripts/build_and_package_deb.py", "deb_lintian_contract"
        )
        override_lines = [
            line
            for line in module.LINTIAN_OVERRIDES.splitlines()
            if line and not line.startswith("#")
        ]
        assert override_lines == ["ecli: hardening-no-pie"]

    def test_deb_description_distinguishes_provisioned_from_registered(self):
        """The package description must never claim 19 active F4 providers;
        only 14 diagnostic providers are registered against 19 provisioned
        tool executables.
        """
        text = _read(REPO_ROOT / "scripts" / "build_and_package_deb.py")
        assert "19 provisioned" in text
        assert "14 registered provider" in text
        assert "19 providers" not in text
        assert "19 active provider" not in text

    def test_smoke_harness_covers_all_nineteen_tools(self):
        import ast
        import importlib.util
        import sys as _sys

        path = REPO_ROOT / "scripts" / "verify_f4_toolchain_smoke.py"
        text = _read(path)
        assert "import ecli" not in text and "from ecli" not in text
        tree = ast.parse(text)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                assert all(keyword.arg != "shell" for keyword in node.keywords)
        spec = importlib.util.spec_from_file_location("f4_smoke_contract", path)
        module = importlib.util.module_from_spec(spec)
        _sys.modules["f4_smoke_contract"] = module
        spec.loader.exec_module(module)
        cases = module.SMOKE_CASES
        assert len(cases) == 19
        assert len({case.tool_id for case in cases}) == 19
        for case in cases:
            assert case.marker, case.tool_id
            assert case.rc_note, case.tool_id


class TestSnapStaysOutsideReleaseContract:
    def test_canonical_contract_is_exactly_twenty_one_artifacts(self):
        assert len(CANONICAL_ARTIFACTS) == 21
        assert not any(
            ".snap" in artifact.artifact_token for artifact in CANONICAL_ARTIFACTS
        )

    def test_no_snapcraft_manifest_in_repository(self):
        assert not (REPO_ROOT / "snapcraft.yaml").exists()

    def test_makefile_snap_targets_are_hard_disabled(self):
        makefile = _read(REPO_ROOT / "Makefile")
        assert "Snap targets are disabled" in makefile
        assert "snapcraft\n" not in makefile, (
            "no live snapcraft invocation may remain in the Makefile"
        )
        for target in (
            "package-snap",
            "package-snap-assert",
            "show-snap-artifacts",
            "release-snap",
        ):
            assert target in makefile, f"refusal stub for {target} missing"
