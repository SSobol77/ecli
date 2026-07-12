#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: scripts/verify_f4_toolchain_smoke.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Real diagnostic smoke coverage for the complete 19-tool F4 toolchain.

For every tool this harness creates a known-bad fixture, runs the real
linter against it, and asserts the documented diagnostic contract:

* exact command (argv array, never a shell, never a pipe);
* resolved executable path (payload-first PATH);
* observed version;
* fixture path;
* real exit code taken directly from ``subprocess.run``;
* a normalized expected diagnostic marker in stdout+stderr.

Exit codes are asserted per tool: several linters (clang-tidy with
warnings, SpotBugs textui) document exit code 0 with findings on the
output streams; most others document a specific non-zero code
(PMD ``4`` for violations, cargo ``101`` on denied warnings, TFLint ``2``
for issues found, Checkstyle "number of errors"). The harness prints one
PASS/FAIL record per tool and returns 0 only when all 19 pass.

Standalone: stdlib only, no ECLI imports. Intended for the Debian 13
clean-room validation after ``install_ecli_linters.py --select A``.
"""

from __future__ import annotations

import argparse
import base64
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


PAYLOAD_BIN = "/opt/ecli/payload/bin"
DEFAULT_TIMEOUT = 180.0
BUILD_TIMEOUT = 600.0  # cargo-clippy / golangci-lint compile first

# Precompiled fixture for SpotBugs (bytecode analyzer): javac --release 11,
# source EqualsNoHashCode.java — a class overriding equals() without
# hashCode(), triggering the always-on HE_EQUALS_NO_HASHCODE detector.
EQUALS_NO_HASHCODE_CLASS_B64 = (
    "yv66vgAAADcAFQoAAgADBwAEDAAFAAYBABBqYXZhL2xhbmcvT2JqZWN0AQAGPGluaXQ+"
    "AQADKClWCQAIAAkHAAoMAAsADAEAEEVxdWFsc05vSGFzaENvZGUBAAV2YWx1ZQEAAUkB"
    "AAQoSSlWAQAEQ29kZQEAD0xpbmVOdW1iZXJUYWJsZQEABmVxdWFscwEAFShMamF2YS9s"
    "YW5nL09iamVjdDspWgEADVN0YWNrTWFwVGFibGUBAApTb3VyY2VGaWxlAQAVRXF1YWxz"
    "Tm9IYXNoQ29kZS5qYXZhACEACAACAAAAAQASAAsADAAAAAIAAQAFAA0AAQAOAAAAKgAC"
    "AAIAAAAKKrcAASobtQAHsQAAAAEADwAAAA4AAwAAAAQABAAFAAkABgABABAAEQABAA4A"
    "AAA+AAIAAgAAABsrwQAImQAVK8AACLQAByq0AAegAAcEpwAEA6wAAAACAA8AAAAGAAEA"
    "AAAKABIAAAAFAAIZQAEAAQATAAAAAgAU"
)


@dataclass
class SmokeCase:
    """One tool's real-diagnostic fixture contract."""

    tool_id: str
    display_name: str
    executable: str
    version_command: tuple[str, ...]
    build: Callable[[Path], tuple[list[str], Path]]
    expected_rc: tuple[int, ...] | None  # None => documented "any non-zero"
    rc_note: str
    marker: str
    timeout: float = DEFAULT_TIMEOUT
    env_extra: Callable[[Path], dict[str, str]] | None = None
    # Subdirectory of the workdir to run in (golangci-lint must run
    # inside the Go module).
    workdir_subpath: str | None = None


def _write(path: Path, content: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _ruff(work: Path) -> tuple[list[str], Path]:
    fixture = _write(work / "ruff" / "bad.py", "import os,sys\nx=1\n")
    return ["ruff", "check", "--no-cache", str(fixture)], fixture


def _biome(work: Path) -> tuple[list[str], Path]:
    fixture = _write(work / "biome" / "bad.js", "var a = 1;\na = a;\n")
    return ["biome", "lint", str(fixture)], fixture


def _markdownlint(work: Path) -> tuple[list[str], Path]:
    fixture = _write(work / "mdl" / "bad.md", "# Heading\n\n\n\ntext\n")
    return ["markdownlint-cli2", str(fixture)], fixture


def _yamllint(work: Path) -> tuple[list[str], Path]:
    fixture = _write(work / "yaml" / "bad.yaml", "a:\n  b: 1\n   c: 2\n")
    return ["yamllint", str(fixture)], fixture


def _shellcheck(work: Path) -> tuple[list[str], Path]:
    fixture = _write(work / "sh" / "bad.sh", "#!/bin/sh\necho $UNQUOTED\n")
    return ["shellcheck", str(fixture)], fixture


def _zig(work: Path) -> tuple[list[str], Path]:
    fixture = _write(work / "zig" / "bad.zig", "const x = ;\n")
    return ["zig", "ast-check", str(fixture)], fixture


def _hadolint(work: Path) -> tuple[list[str], Path]:
    fixture = _write(work / "docker" / "Dockerfile", "FROM debian\nRUN cd /tmp\n")
    return ["hadolint", str(fixture)], fixture


def _taplo(work: Path) -> tuple[list[str], Path]:
    fixture = _write(work / "toml" / "bad.toml", "a =\n")
    return ["taplo", "lint", str(fixture)], fixture


def _actionlint(work: Path) -> tuple[list[str], Path]:
    fixture = _write(
        work / "gha" / "workflow.yml",
        "on: push\njobs:\n  test:\n    steps:\n      - run: echo hi\n",
    )
    return ["actionlint", str(fixture)], fixture


def _clang_tidy(work: Path) -> tuple[list[str], Path]:
    fixture = _write(work / "ctidy" / "bad.c", "int main(void) { int x; return x; }\n")
    return ["clang-tidy", "--quiet", str(fixture), "--"], fixture


def _cppcheck(work: Path) -> tuple[list[str], Path]:
    fixture = _write(
        work / "cppcheck" / "bad.c",
        "int f(void) { int a[3]; return a[5]; }\n",
    )
    return ["cppcheck", "--error-exitcode=1", str(fixture)], fixture


def _clang_format(work: Path) -> tuple[list[str], Path]:
    fixture = _write(work / "cfmt" / "ugly.c", "int   main( ){return 0 ;}\n")
    return ["clang-format", "--dry-run", "--Werror", str(fixture)], fixture


def _checkstyle(work: Path) -> tuple[list[str], Path]:
    fixture = _write(work / "checkstyle" / "Bad.java", "public class Bad { int x; }\n")
    return ["checkstyle", "-c", "/sun_checks.xml", str(fixture)], fixture


def _pmd(work: Path) -> tuple[list[str], Path]:
    fixture = _write(
        work / "pmd" / "Bad2.java",
        "public class Bad2 {\n"
        "    public int f() {\n"
        "        int unused = 1;\n"
        "        return 2;\n"
        "    }\n"
        "}\n",
    )
    return [
        "pmd",
        "check",
        "--no-progress",
        "-d",
        str(fixture),
        "-R",
        "rulesets/java/quickstart.xml",
        "-f",
        "text",
    ], fixture


def _spotbugs(work: Path) -> tuple[list[str], Path]:
    classes = work / "spotbugs" / "classes"
    classes.mkdir(parents=True, exist_ok=True)
    fixture = classes / "EqualsNoHashCode.class"
    fixture.write_bytes(base64.b64decode(EQUALS_NO_HASHCODE_CLASS_B64))
    return ["spotbugs", "-textui", "-low", str(classes)], fixture


def _cargo_clippy(work: Path) -> tuple[list[str], Path]:
    project = work / "clippy_proj"
    _write(
        project / "Cargo.toml",
        '[package]\nname = "smoke"\nversion = "0.1.0"\nedition = "2021"\n',
    )
    fixture = _write(
        project / "src" / "main.rs",
        'fn main() {\n    let x = true;\n    if x == true { println!("y"); }\n}\n',
    )
    return [
        "cargo",
        "clippy",
        "--offline",
        "--quiet",
        "--manifest-path",
        str(project / "Cargo.toml"),
        "--",
        "-D",
        "warnings",
    ], fixture


def _golangci_lint(work: Path) -> tuple[list[str], Path]:
    project = work / "golint_proj"
    _write(project / "go.mod", "module smoke\n\ngo 1.24\n")
    fixture = _write(
        project / "main.go",
        "package main\n\n"
        'import "fmt"\n\n'
        "func main() {\n"
        '\tfmt.Printf("%d\\n", "not-a-number")\n'
        "}\n",
    )
    return ["golangci-lint", "run", "./..."], fixture


def _sqlfluff(work: Path) -> tuple[list[str], Path]:
    fixture = _write(work / "sql" / "bad.sql", "SELECT a from b\n")
    return ["sqlfluff", "lint", "--dialect", "ansi", str(fixture)], fixture


def _tflint(work: Path) -> tuple[list[str], Path]:
    project = work / "tf"
    fixture = _write(project / "main.tf", 'variable "unused" { default = 1 }\n')
    return ["tflint", f"--chdir={project}"], fixture


def _go_env(work: Path) -> dict[str, str]:
    return {
        "GOCACHE": str(work / ".gocache"),
        "GOPATH": str(work / ".gopath"),
        "GOLANGCI_LINT_CACHE": str(work / ".golangci-cache"),
    }


def _cargo_env(work: Path) -> dict[str, str]:
    return {"CARGO_HOME": str(work / ".cargo")}


SMOKE_CASES: tuple[SmokeCase, ...] = (
    SmokeCase(
        "ruff",
        "Ruff",
        "ruff",
        ("ruff", "--version"),
        _ruff,
        (1,),
        "documented: 1 when violations are found",
        "E401",
    ),
    SmokeCase(
        "biome",
        "Biome",
        "biome",
        ("biome", "--version"),
        _biome,
        (1,),
        "documented: 1 when lint diagnostics are emitted",
        "noSelfAssign",
    ),
    SmokeCase(
        "markdownlint-cli2",
        "markdownlint-cli2",
        "markdownlint-cli2",
        ("markdownlint-cli2", "--version"),
        _markdownlint,
        (1,),
        "documented: 1 when errors are found (direct subprocess, no pipe)",
        "MD012",
    ),
    SmokeCase(
        "yamllint",
        "yamllint",
        "yamllint",
        ("yamllint", "--version"),
        _yamllint,
        (1,),
        "documented: 1 when errors are found",
        "syntax",
    ),
    SmokeCase(
        "shellcheck",
        "ShellCheck",
        "shellcheck",
        ("shellcheck", "--version"),
        _shellcheck,
        (1,),
        "documented: 1 when issues are found",
        "SC2086",
    ),
    SmokeCase(
        "zig",
        "Zig",
        "zig",
        ("zig", "version"),
        _zig,
        (1,),
        "documented: 1 on AST errors",
        "error",
    ),
    SmokeCase(
        "hadolint",
        "Hadolint",
        "hadolint",
        ("hadolint", "--version"),
        _hadolint,
        (1,),
        "documented: 1 when rule violations are found",
        "DL3003",
    ),
    SmokeCase(
        "taplo",
        "Taplo",
        "taplo",
        ("taplo", "--version"),
        _taplo,
        (1,),
        "documented: 1 on lint/parse errors",
        "error",
    ),
    SmokeCase(
        "actionlint",
        "actionlint",
        "actionlint",
        ("actionlint", "-version"),
        _actionlint,
        (1,),
        "documented: 1 when problems are found",
        "runs-on",
    ),
    SmokeCase(
        "clang-tidy",
        "clang-tidy",
        "clang-tidy",
        ("clang-tidy", "--version"),
        _clang_tidy,
        (0,),
        "documented: 0 when only warnings are emitted (no compile error)",
        "warning:",
    ),
    SmokeCase(
        "cppcheck",
        "Cppcheck",
        "cppcheck",
        ("cppcheck", "--version"),
        _cppcheck,
        (1,),
        "documented: --error-exitcode=1 forces 1 when errors are found",
        "arrayIndexOutOfBounds",
    ),
    SmokeCase(
        "clang-format",
        "clang-format",
        "clang-format",
        ("clang-format", "--version"),
        _clang_format,
        (1,),
        "documented: --dry-run --Werror exits 1 on formatting violations",
        "clang-format-violations",
    ),
    SmokeCase(
        "checkstyle",
        "Checkstyle",
        "checkstyle",
        ("checkstyle", "--version"),
        _checkstyle,
        None,
        "documented: exit code is the audit error count (non-zero here)",
        "[ERROR]",
    ),
    SmokeCase(
        "pmd",
        "PMD",
        "pmd",
        ("pmd", "--version"),
        _pmd,
        (4,),
        "documented: 4 when violations are found",
        "NoPackage",
    ),
    SmokeCase(
        "spotbugs",
        "SpotBugs",
        "spotbugs",
        ("spotbugs", "-version"),
        _spotbugs,
        (0,),
        "documented: textui exits 0; findings are reported on stdout",
        "hashCode",
    ),
    SmokeCase(
        "cargo-clippy",
        "cargo-clippy",
        "cargo",
        ("cargo", "clippy", "--version"),
        _cargo_clippy,
        (101,),
        "documented: cargo exits 101 when -D warnings denies a lint",
        "bool_comparison",
        timeout=BUILD_TIMEOUT,
        env_extra=_cargo_env,
    ),
    SmokeCase(
        "golangci-lint",
        "golangci-lint",
        "golangci-lint",
        ("golangci-lint", "--version"),
        _golangci_lint,
        (1,),
        "documented: 1 when issues are found",
        "printf",
        timeout=BUILD_TIMEOUT,
        env_extra=_go_env,
        workdir_subpath="golint_proj",
    ),
    SmokeCase(
        "sqlfluff",
        "SQLFluff",
        "sqlfluff",
        ("sqlfluff", "--version"),
        _sqlfluff,
        (1,),
        "documented: 1 when lint violations are found",
        "CP01",
    ),
    SmokeCase(
        "tflint",
        "TFLint",
        "tflint",
        ("tflint", "--version"),
        _tflint,
        (2,),
        "documented: 2 when issues are found",
        "terraform_unused_declarations",
    ),
)


def smoke_environment(work: Path, extra: dict[str, str] | None) -> dict[str, str]:
    """Deterministic execution environment (payload-first PATH)."""
    env = {
        "PATH": f"{PAYLOAD_BIN}:/usr/local/sbin:/usr/local/bin:"
        "/usr/sbin:/usr/bin:/sbin:/bin",
        "HOME": str(work),
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
    }
    if extra:
        env.update(extra)
    return env


def run_case(case: SmokeCase, work: Path) -> bool:
    """Run one smoke case and print its full evidence record."""
    env = smoke_environment(work, case.env_extra(work) if case.env_extra else None)
    resolved = shutil.which(case.executable, path=env["PATH"])
    if resolved is None:
        print(f"[FAIL] {case.display_name}: executable not found on PATH")
        return False
    version_probe = subprocess.run(
        [resolved, *case.version_command[1:]],
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
        check=False,
    )
    version_line = next(
        (
            line.strip()
            for line in (
                (version_probe.stdout or "") + "\n" + (version_probe.stderr or "")
            ).splitlines()
            if line.strip() and any(ch.isdigit() for ch in line)
        ),
        "unknown",
    )
    argv, fixture = case.build(work)
    run_cwd = work / case.workdir_subpath if case.workdir_subpath else work
    try:
        result = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=case.timeout,
            env=env,
            cwd=str(run_cwd),
            check=False,
        )
    except subprocess.TimeoutExpired:
        print(f"[FAIL] {case.display_name}: timed out after {case.timeout:.0f}s")
        return False
    output = (result.stdout or "") + (result.stderr or "")
    rc_ok = (
        result.returncode != 0
        if case.expected_rc is None
        else result.returncode in case.expected_rc
    )
    marker_ok = case.marker in output
    status = "PASS" if (rc_ok and marker_ok) else "FAIL"
    expected_rc_text = "non-zero" if case.expected_rc is None else str(case.expected_rc)
    print(f"[{status}] {case.display_name}")
    print(f"    command:  {' '.join(argv)}")
    print(f"    path:     {resolved}")
    print(f"    version:  {version_line}")
    print(f"    fixture:  {fixture}")
    print(
        f"    exit:     {result.returncode} "
        f"(expected {expected_rc_text}; {case.rc_note})"
    )
    print(
        f"    expected diagnostic marker: {case.marker!r} "
        f"({'found' if marker_ok else 'NOT FOUND'})"
    )
    if status == "FAIL":
        tail = output.strip()[-1200:]
        print(f"    output tail:\n{tail}")
    return status == "PASS"


def main(argv: list[str] | None = None) -> int:
    """Run all 19 smoke cases; return 0 only when every one passes."""
    parser = argparse.ArgumentParser(
        prog="verify_f4_toolchain_smoke.py",
        description=(
            "Run real diagnostic fixtures against the complete 19-tool "
            "F4 toolchain (Debian 13 clean-room validation)."
        ),
    )
    parser.add_argument(
        "--workdir",
        type=Path,
        default=Path("/tmp/ecli-f4-smoke"),
        help="fixture/working directory (created if absent)",
    )
    args = parser.parse_args(argv)
    work = args.workdir
    work.mkdir(parents=True, exist_ok=True)
    passed = 0
    for case in SMOKE_CASES:
        if run_case(case, work):
            passed += 1
    total = len(SMOKE_CASES)
    print(f"F4 diagnostics smoke: {passed}/{total} tools verified")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
