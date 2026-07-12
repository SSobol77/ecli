# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/linters/core/toolchain_check.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Non-fatal F4 toolchain availability check.

Reports which first-class F4 linter executables (catalog tiers ``core`` and
``recommended`` -- the 19-tool toolchain provisioned by
``scripts/install_ecli_linters.py``) are missing from ``PATH``. The check is
purely informational: it never raises for a missing tool, never mutates
editor state, and providers keep degrading per-file via
``missing_executable_result`` exactly as before. Its purpose is a clear
startup/F4 diagnostics log line listing missing executables instead of the
user discovering them one crash-free failure at a time.
"""

from __future__ import annotations

import logging
import shutil
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from ecli.extensions.linters.core.registry import LinterDefinition


TOOLCHAIN_TIERS: tuple[str, ...] = ("core", "recommended")

# Delivery contract for the 19-tool toolchain on Debian 13: exactly 11
# ECLI-managed executables (installed under /opt/ecli/payload/bin by
# scripts/install_ecli_linters.py from the committed lock) and exactly 8
# Debian-packaged executables (installed by APT under /usr/bin).
# ``ecli --f4-check`` fails when these counts drift.
MANAGED_EXECUTABLES: frozenset[str] = frozenset(
    {
        "ruff",
        "biome",
        "markdownlint-cli2",
        "zig",
        "hadolint",
        "taplo",
        "actionlint",
        "pmd",
        "spotbugs",
        "golangci-lint",
        "tflint",
    }
)
SYSTEM_EXECUTABLES: frozenset[str] = frozenset(
    {
        "yamllint",
        "shellcheck",
        "clang-tidy",
        "cppcheck",
        "clang-format",
        "checkstyle",
        "cargo",
        "sqlfluff",
    }
)
MANAGED_TOOL_COUNT = 11
SYSTEM_TOOL_COUNT = 8
TOOLCHAIN_TOTAL = 19

MANAGED_PATH_PREFIX = "/opt/ecli/payload/bin/"
SYSTEM_PATH_PREFIXES: tuple[str, ...] = (
    "/usr/sbin/",
    "/usr/bin/",
    "/sbin/",
    "/bin/",
)


def toolchain_definitions() -> tuple["LinterDefinition", ...]:
    """Return the first-class 19-tool toolchain catalog entries."""
    from ecli.extensions.linters import iter_linters

    return tuple(
        definition
        for definition in iter_linters()
        if definition.tier in TOOLCHAIN_TIERS
    )


def missing_toolchain_executables(
    path: str | None = None,
) -> tuple["LinterDefinition", ...]:
    """Return toolchain entries whose executable is absent from ``PATH``.

    Args:
        path: Optional explicit search path for ``shutil.which`` (used by
            tests); ``None`` searches the process environment ``PATH``.
    """
    missing: list[LinterDefinition] = []
    seen: set[str] = set()
    for definition in toolchain_definitions():
        executable = definition.executable
        if executable in seen:
            continue
        seen.add(executable)
        if shutil.which(executable, path=path) is None:
            missing.append(definition)
    return tuple(missing)


def log_toolchain_availability(
    logger: logging.Logger, path: str | None = None
) -> None:
    """Log a clear, non-fatal report of missing F4 toolchain executables.

    Never raises: any unexpected error is logged and swallowed so a
    diagnostics convenience can never break editor startup.
    """
    try:
        missing = missing_toolchain_executables(path=path)
        if not missing:
            logger.info("F4 toolchain check: all linter executables found.")
            return
        listing = ", ".join(
            f"{definition.display_name} ({definition.executable})"
            for definition in missing
        )
        logger.warning(
            "F4 toolchain check: %d linter executable(s) missing from "
            "PATH: %s. Affected linters stay disabled per file; install "
            "them with: sudo python3 scripts/install_ecli_linters.py "
            "(Debian 13).",
            len(missing),
            listing,
        )
    except Exception:  # noqa: BLE001 - diagnostics must never crash startup
        logger.exception("F4 toolchain check failed (non-fatal)")


def _register_f4_providers() -> int:
    """Instantiate the F4 provider layer exactly as LinterBridge does.

    Returns the number of registered providers. Imports are deliberately
    lazy: this only runs for ``ecli --f4-check``.
    """
    from ecli.extensions.linters.actionlint.provider import (
        ActionlintDiagnosticProvider,
    )
    from ecli.extensions.linters.biome.provider import BiomeDiagnosticProvider
    from ecli.extensions.linters.cargo_clippy.provider import (
        CargoClippyDiagnosticProvider,
    )
    from ecli.extensions.linters.clang_tidy.provider import (
        ClangTidyDiagnosticProvider,
    )
    from ecli.extensions.linters.core.service import DiagnosticsService
    from ecli.extensions.linters.cppcheck.provider import (
        CppcheckDiagnosticProvider,
    )
    from ecli.extensions.linters.hadolint.provider import (
        HadolintDiagnosticProvider,
    )
    from ecli.extensions.linters.java_checkstyle.provider import (
        JavaCheckstyleDiagnosticProvider,
    )
    from ecli.extensions.linters.java_pmd.provider import (
        JavaPmdDiagnosticProvider,
    )
    from ecli.extensions.linters.markdownlint.provider import (
        MarkdownlintDiagnosticProvider,
    )
    from ecli.extensions.linters.ruff.provider import RuffDiagnosticProvider
    from ecli.extensions.linters.shellcheck.provider import (
        ShellCheckDiagnosticProvider,
    )
    from ecli.extensions.linters.taplo.provider import TaploDiagnosticProvider
    from ecli.extensions.linters.yamllint.provider import (
        YamllintDiagnosticProvider,
    )
    from ecli.extensions.linters.zig.provider import ZigDiagnosticProvider

    service = DiagnosticsService()
    for provider in (
        RuffDiagnosticProvider(enabled=True),
        BiomeDiagnosticProvider(),
        ZigDiagnosticProvider(),
        ClangTidyDiagnosticProvider(),
        CppcheckDiagnosticProvider(),
        JavaCheckstyleDiagnosticProvider(),
        JavaPmdDiagnosticProvider(),
        ShellCheckDiagnosticProvider(),
        MarkdownlintDiagnosticProvider(),
        YamllintDiagnosticProvider(),
        ActionlintDiagnosticProvider(),
        HadolintDiagnosticProvider(),
        TaploDiagnosticProvider(),
        CargoClippyDiagnosticProvider(),
    ):
        service.register_provider(provider)
    return len(service.provider_states())


def f4_check_main(path: str | None = None) -> int:
    """Headless F4 toolchain verification for ``ecli --f4-check``.

    This command reports three DIFFERENT, non-interchangeable counts.
    They are never conflated:

    * PROVISIONED/VERIFIED EXECUTABLE (up to 19): a toolchain executable
      that resolves on ``PATH`` from its approved managed or system
      location. Provisioning is done by the stage-1 installer
      (``scripts/install_ecli_linters.py``) or by APT; this command only
      verifies the result.
    * REGISTERED DIAGNOSTIC PROVIDER (14, fixed): the number of
      ``DiagnosticProvider`` classes the F4 runtime layer actually wires
      into ``DiagnosticsService`` (mirrors ``LinterBridge.__init__``
      exactly). Five provisioned/verified tools currently have no
      registered provider (SpotBugs, golangci-lint, SQLFluff, TFLint,
      clang-format) -- they are installed and on PATH, but F4 does not yet
      run diagnostics through them. This is not a defect this command
      reports on; it is the accurate current state.

    Never describe all 19 provisioned executables as "19 active F4
    providers" -- only 14 providers are registered.

    Resolves every toolchain executable through ``PATH`` and enforces the
    Debian delivery contract: 11 ECLI-managed tools under
    ``/opt/ecli/payload/bin``, 8 Debian tools under system directories, 19
    total, and no resolution from unapproved locations such as
    ``/usr/local`` or user-local directories. Returns 0 only when every
    requirement holds.
    """
    provider_count = _register_f4_providers()
    print(f"F4 registered diagnostic providers: {provider_count} (fixed; see docstring)")
    managed = system = 0
    failures: list[str] = []
    for definition in toolchain_definitions():
        executable = definition.executable
        resolved = shutil.which(executable, path=path)
        if resolved is None:
            failures.append(f"{definition.display_name}: executable not found")
            print(f"[MISSING]    {definition.display_name:<20} {executable}")
            continue
        if executable in MANAGED_EXECUTABLES:
            expected = "managed"
            location_ok = resolved.startswith(MANAGED_PATH_PREFIX)
        else:
            expected = "system"
            location_ok = any(
                resolved.startswith(prefix) for prefix in SYSTEM_PATH_PREFIXES
            )
        if not location_ok:
            failures.append(
                f"{definition.display_name}: resolved outside the approved "
                f"{expected} location: {resolved}"
            )
            print(f"[DISALLOWED] {definition.display_name:<20} {resolved}")
            continue
        if expected == "managed":
            managed += 1
        else:
            system += 1
        print(f"[OK] {expected:<8}{definition.display_name:<20} -> {resolved}")
    detected = managed + system
    print(
        f"F4 toolchain: {detected}/{TOOLCHAIN_TOTAL} executables "
        f"provisioned and verified ({managed} managed, {system} system) "
        f"-- distinct from the {provider_count} registered diagnostic "
        "providers above"
    )
    if managed != MANAGED_TOOL_COUNT:
        failures.append(
            f"managed tool count {managed} != required {MANAGED_TOOL_COUNT}"
        )
    if system != SYSTEM_TOOL_COUNT:
        failures.append(
            f"Debian tool count {system} != required {SYSTEM_TOOL_COUNT}"
        )
    for failure in failures:
        print(f"[FAIL] {failure}")
    return 0 if not failures else 1
