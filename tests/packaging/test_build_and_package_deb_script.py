# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/packaging/test_build_and_package_deb_script.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Behavior tests for scripts/build_and_package_deb.py command construction."""

from __future__ import annotations

from pathlib import Path
from types import ModuleType

import pytest
from conftest import load_script_module


@pytest.fixture
def deb(repo_root: Path) -> ModuleType:
    return load_script_module(
        repo_root, "scripts/build_and_package_deb.py", "deb_build"
    )


def test_filename_arch(deb: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    import os

    monkeypatch.setattr(
        deb.filename_arch.__globals__["os"],
        "uname",
        lambda: os.uname_result(("Linux", "h", "r", "v", "aarch64")),
    )
    assert deb.filename_arch() == "arm64"


def test_fpm_command_naming_and_deps(deb: ModuleType, tmp_path: Path) -> None:
    final = tmp_path / "releases" / "1.2.3" / "ecli_1.2.3_linux_x86_64.deb"
    cmd = deb.build_fpm_command(tmp_path / "stage", "1.2.3", final)
    assert cmd[:5] == ["fpm", "-s", "dir", "-t", "deb"]
    assert "-a" in cmd and cmd[cmd.index("-a") + 1] == "amd64"
    assert "--package" in cmd and cmd[cmd.index("--package") + 1] == str(final)
    # Dependency set is preserved exactly.
    for dep in deb.DEB_DEPENDS:
        assert dep in cmd
    assert cmd[-1] == "usr"


def test_man_page_and_desktop(deb: ModuleType) -> None:
    man = deb.man_page("9.9.9")
    assert ".TH ECLI 1" in man
    assert "ecli 9.9.9" in man
    desktop = deb.desktop_entry()
    assert "Exec=ecli" in desktop and "Terminal=true" in desktop


def test_find_executable_missing(deb: ModuleType, tmp_path: Path) -> None:
    assert deb.find_executable(tmp_path) is None


# ---------------------------------------------------------------------------
# Legacy F4 evidence hook: must be strictly post-promotion and non-gating.
#
# record_f4_evidence_non_gating() is called from main() only AFTER
# build_deb_atomic() has already atomically promoted final_deb/final_sha
# (see main()'s source: the call sits directly after `print(f"DONE:
# {final_deb}")`, which itself only executes once build_deb_atomic()
# returned without raising). These tests cover the function's own
# contract in isolation: neither a non-zero return nor a raised exception
# from the underlying hook may ever propagate, and the promoted artifact
# and its sidecar must be left byte-for-byte unchanged either way.
# ---------------------------------------------------------------------------


@pytest.fixture
def promoted_artifact(tmp_path: Path) -> tuple[Path, Path, bytes, bytes]:
    """A fake already-promoted .deb + sidecar, as record_f4_evidence_non_gating
    would find them: written and stable before the hook ever runs.
    """
    final_deb = tmp_path / "ecli_0.2.4_linux_x86_64.deb"
    final_sha = tmp_path / "ecli_0.2.4_linux_x86_64.deb.sha256"
    deb_bytes = b"promoted-deb-bytes-do-not-touch"
    sha_bytes = b"0" * 64 + b"  ecli_0.2.4_linux_x86_64.deb\n"
    final_deb.write_bytes(deb_bytes)
    final_sha.write_bytes(sha_bytes)
    return final_deb, final_sha, deb_bytes, sha_bytes


def test_f4_hook_nonzero_return_is_fully_non_gating(
    deb: ModuleType,
    tmp_path: Path,
    promoted_artifact: tuple[Path, Path, bytes, bytes],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    final_deb, final_sha, deb_bytes, sha_bytes = promoted_artifact
    monkeypatch.setattr(
        deb, "run_or_record_f4_linter_provisioning_for_artifacts", lambda *a, **k: 1
    )

    deb.record_f4_evidence_non_gating(tmp_path, final_deb)  # must not raise

    assert final_deb.read_bytes() == deb_bytes, "promoted artifact must be unchanged"
    assert final_sha.read_bytes() == sha_bytes, "sidecar must be unchanged"
    stderr = capsys.readouterr().err
    assert "WARNING" in stderr
    assert "F4 linter provisioning" in stderr


def test_f4_hook_exception_is_fully_non_gating(
    deb: ModuleType,
    tmp_path: Path,
    promoted_artifact: tuple[Path, Path, bytes, bytes],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    final_deb, final_sha, deb_bytes, sha_bytes = promoted_artifact

    def _raise(*_args: object, **_kwargs: object) -> int:
        raise RuntimeError("boom: simulated hook crash")

    monkeypatch.setattr(
        deb, "run_or_record_f4_linter_provisioning_for_artifacts", _raise
    )

    deb.record_f4_evidence_non_gating(tmp_path, final_deb)  # must not raise

    assert final_deb.read_bytes() == deb_bytes, "promoted artifact must be unchanged"
    assert final_sha.read_bytes() == sha_bytes, "sidecar must be unchanged"
    stderr = capsys.readouterr().err
    assert "WARNING" in stderr
    assert "boom: simulated hook crash" in stderr


def test_f4_hook_success_prints_no_warning(
    deb: ModuleType,
    tmp_path: Path,
    promoted_artifact: tuple[Path, Path, bytes, bytes],
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    final_deb, _final_sha, _deb_bytes, _sha_bytes = promoted_artifact
    monkeypatch.setattr(
        deb, "run_or_record_f4_linter_provisioning_for_artifacts", lambda *a, **k: 0
    )

    deb.record_f4_evidence_non_gating(tmp_path, final_deb)

    assert "WARNING" not in capsys.readouterr().err


def test_main_calls_hook_only_after_done_and_unconditionally_returns_ok(
    deb: ModuleType,
) -> None:
    """Structural guard: main() must call the hook strictly after promotion
    (after the "DONE:" print) and must return EXIT_OK unconditionally
    afterward, with nothing branching on the hook's outcome.
    """
    import ast
    import inspect

    source = inspect.getsource(deb.main)
    tree = ast.parse(source)
    (main_func,) = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    body = main_func.body
    hook_index = next(
        i
        for i, node in enumerate(body)
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and getattr(node.value.func, "id", "") == "record_f4_evidence_non_gating"
    )
    done_print_index = next(
        i
        for i, node in enumerate(body)
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Call)
        and getattr(node.value.func, "id", "") == "print"
        and any(
            isinstance(arg, ast.JoinedStr)
            and any(
                isinstance(v, ast.Constant) and "DONE:" in str(v.value)
                for v in arg.values
                if isinstance(v, ast.Constant)
            )
            for arg in node.value.args
        )
    )
    assert done_print_index < hook_index, (
        "the hook must be called after the DONE: promotion message"
    )
    # Nothing after the hook call may be an `if`/branch on its result --
    # main() must fall straight through to an unconditional `return EXIT_OK`.
    remainder = body[hook_index + 1 :]
    assert len(remainder) == 1
    assert isinstance(remainder[0], ast.Return)
    assert getattr(remainder[0].value, "id", "") == "EXIT_OK"


def test_hook_is_documented_as_legacy_non_gating_evidence(deb: ModuleType) -> None:
    doc = deb.record_f4_evidence_non_gating.__doc__ or ""
    assert "LEGACY" in doc or "legacy" in doc
    assert "non-gating" in doc
    assert "NOT proof" in doc or "not proof" in doc.lower()
