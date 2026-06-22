# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/extensions/test_diagnostics_service.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Tests for the diagnostics coordinator service and bounded store (#104)."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from types import SimpleNamespace

import pytest

from ecli.extensions.ecli_integration.diagnostics import (
    CommandResult,
    Diagnostic,
    DiagnosticSeverity,
    DiagnosticsService,
    DiagnosticsState,
    DiagnosticsStatus,
    DiagnosticsStore,
    ProviderRegistry,
    ProviderResult,
    RuffDiagnosticsProvider,
)
from ecli.extensions.ecli_integration.diagnostics.provider_metadata import (
    ProviderExecutionMode,
)


class StubProvider:
    name = "stub"

    def __init__(
        self,
        *,
        available: bool = True,
        suffixes: tuple[str, ...] = (".py",),
        result: ProviderResult | None = None,
    ) -> None:
        """Configure a deterministic stub provider for service tests."""
        self._available = available
        self._suffixes = suffixes
        self._result = result
        self.calls = 0

    def applies_to(self, file_path: str) -> bool:
        return any(file_path.endswith(suffix) for suffix in self._suffixes)

    def is_available(self) -> bool:
        return self._available

    def collect(
        self, file_path: str, text: str, timeout: float = 5.0
    ) -> ProviderResult:
        self.calls += 1
        if self._result is not None:
            return self._result
        diag = Diagnostic(
            file_path=file_path,
            line=1,
            severity=DiagnosticSeverity.WARNING,
            source=self.name,
            message="stub finding",
            column=1,
            code="S001",
        )
        return ProviderResult(available=True, ok=True, diagnostics=(diag,))


def _service(provider: StubProvider, **kwargs: object) -> DiagnosticsService:
    return DiagnosticsService(providers=[provider], **kwargs)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# Explicit empty states.
# --------------------------------------------------------------------------- #


def test_disabled_config_returns_disabled_state() -> None:
    service = _service(StubProvider(), config={"linter": {"enabled": False}})
    state = service.collect("a.py", text="x = 1\n")
    assert state.status is DiagnosticsStatus.DISABLED


def test_no_file_path_returns_no_active_file() -> None:
    service = _service(StubProvider())
    assert service.collect(None).status is DiagnosticsStatus.NO_ACTIVE_FILE
    assert service.collect("").status is DiagnosticsStatus.NO_ACTIVE_FILE


def test_excluded_path_returns_disabled_state() -> None:
    service = _service(StubProvider(), config={"linter": {"exclude": [".venv"]}})
    state = service.collect(".venv/lib/mod.py", text="x = 1\n")
    assert state.status is DiagnosticsStatus.DISABLED
    assert state.detail is not None
    assert "exclude" in state.detail


def test_unsupported_file_type_is_distinct_from_provider_unavailable() -> None:
    service = _service(StubProvider(suffixes=(".py",)))
    state = service.collect("notes.txt", text="hello")
    assert state.status is DiagnosticsStatus.UNSUPPORTED
    assert state.detail is not None
    assert "No diagnostics provider" in state.detail
    # The unsupported state is NOT reported as provider-unavailable.
    assert state.status is not DiagnosticsStatus.PROVIDER_UNAVAILABLE


@pytest.mark.parametrize("suffix", [".css", ".tsx", ".json"])
def test_unsupported_messages_for_web_file_types(suffix: str) -> None:
    service = _service(StubProvider(suffixes=(".py",)))
    state = service.collect(f"asset{suffix}", text="x")
    assert state.status is DiagnosticsStatus.UNSUPPORTED
    assert state.detail == f"No diagnostics provider for {suffix} files"


def test_unsupported_state_includes_available_provider_hint() -> None:
    service = _service(StubProvider(suffixes=(".py",)))
    state = service.collect("a.css", text="x")
    assert state.hint is not None
    assert "Available provider" in state.hint


def test_missing_tool_returns_provider_unavailable_state() -> None:
    service = _service(StubProvider(available=False))
    state = service.collect("a.py", text="x = 1\n")
    assert state.status is DiagnosticsStatus.PROVIDER_UNAVAILABLE
    assert state.provider == "stub"


def test_provider_failure_is_mapped_to_error_state() -> None:
    failing = StubProvider(
        result=ProviderResult(available=True, ok=False, detail="timed out")
    )
    service = _service(failing)
    state = service.collect("a.py", text="x = 1\n")
    assert state.status is DiagnosticsStatus.ERROR
    assert state.detail == "timed out"


def test_provider_exception_does_not_propagate() -> None:
    class Boom(StubProvider):
        def collect(self, file_path: str, text: str, timeout: float = 5.0):
            raise RuntimeError("kaboom")

    service = _service(Boom())
    state = service.collect("a.py", text="x = 1\n")
    assert state.status is DiagnosticsStatus.ERROR


# --------------------------------------------------------------------------- #
# Success + counts.
# --------------------------------------------------------------------------- #


def test_successful_collection_returns_ok_with_diagnostics() -> None:
    service = _service(StubProvider())
    state = service.collect("a.py", text="import os\n")
    assert state.status is DiagnosticsStatus.OK
    assert state.total == 1
    assert state.warning_count == 1


# --------------------------------------------------------------------------- #
# Caching.
# --------------------------------------------------------------------------- #


def test_cache_serves_unchanged_buffer_without_rerunning() -> None:
    provider = StubProvider()
    service = _service(provider)
    first = service.collect("a.py", text="import os\n")
    second = service.collect("a.py", text="import os\n")
    assert provider.calls == 1
    assert second is first


def test_force_refresh_bypasses_cache() -> None:
    provider = StubProvider()
    service = _service(provider)
    service.collect("a.py", text="import os\n")
    service.collect("a.py", text="import os\n", force=True)
    assert provider.calls == 2


def test_changed_buffer_invalidates_cache() -> None:
    provider = StubProvider()
    service = _service(provider)
    service.collect("a.py", text="import os\n")
    service.collect("a.py", text="import sys\n")
    assert provider.calls == 2


def test_invalidate_clears_cache_entry() -> None:
    provider = StubProvider()
    service = _service(provider)
    service.collect("a.py", text="import os\n")
    service.invalidate("a.py")
    service.collect("a.py", text="import os\n")
    assert provider.calls == 2


# --------------------------------------------------------------------------- #
# Path validation / workspace containment.
# --------------------------------------------------------------------------- #


def test_outside_workspace_is_distinct_from_provider_unavailable(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    outside = tmp_path / "outside.py"
    service = _service(StubProvider(), workspace_root=workspace)
    state = service.collect(str(outside), text="x = 1\n")
    assert state.status is DiagnosticsStatus.OUTSIDE_WORKSPACE
    assert state.status is not DiagnosticsStatus.PROVIDER_UNAVAILABLE
    assert state.detail is not None
    assert "outside" in state.detail.lower()
    # The resolved path is carried so the panel can show it.
    assert state.file_path is not None


def test_workspace_allows_inside_paths(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    inside = workspace / "mod.py"
    service = _service(StubProvider(), workspace_root=workspace)
    state = service.collect(str(inside), text="import os\n")
    assert state.status is DiagnosticsStatus.OK


def test_nul_byte_path_is_unreadable() -> None:
    service = _service(StubProvider())
    state = service.collect("a\x00.py", text="x = 1\n")
    assert state.status is DiagnosticsStatus.UNREADABLE


# --------------------------------------------------------------------------- #
# Outside-workspace policy: safe current-file (stdin) providers run; project /
# workspace providers stay blocked at the boundary (#104 UX).
# --------------------------------------------------------------------------- #


def _stub_metadata(mode: ProviderExecutionMode) -> SimpleNamespace:
    # Minimal metadata shape the registry/service read for these stubs.
    return SimpleNamespace(
        execution_mode=mode,
        language_ids=("python",),
        extensions=(".py",),
    )


class _CurrentFileStub(StubProvider):
    name = "curfile"
    metadata = _stub_metadata(ProviderExecutionMode.CURRENT_FILE)


class _WorkspaceStub(StubProvider):
    name = "wsprov"
    metadata = _stub_metadata(ProviderExecutionMode.WORKSPACE)


class _RecordingRunner:
    def __init__(self, result: CommandResult) -> None:
        """Record argv/text and return a fixed command result."""
        self.result = result
        self.argv: list[str] = []
        self.text: str = ""

    def __call__(self, argv: Sequence[str], text: str, timeout: float) -> CommandResult:
        self.argv = list(argv)
        self.text = text
        return self.result


def test_outside_workspace_current_file_provider_runs_and_marks_external(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    outside = tmp_path / "outside.py"
    provider = _CurrentFileStub()
    service = _service(provider, workspace_root=workspace)

    state = service.collect(str(outside), text="x = 1\n")

    # A safe current-file provider lints the external file instead of blocking.
    assert state.status is DiagnosticsStatus.OK
    assert state.external is True
    assert provider.calls == 1
    # It receives the resolved absolute path (used as Ruff's --stdin-filename).
    assert state.diagnostics[0].file_path == str(outside.resolve())


def test_outside_workspace_blocks_workspace_provider(tmp_path: Path) -> None:
    workspace = tmp_path / "ws"
    workspace.mkdir()
    outside = tmp_path / "outside.py"
    provider = _WorkspaceStub()
    service = _service(provider, workspace_root=workspace)

    state = service.collect(str(outside), text="x = 1\n")

    # Workspace/project providers must not run outside the workspace boundary.
    assert state.status is DiagnosticsStatus.OUTSIDE_WORKSPACE
    assert provider.calls == 0
    assert state.file_path == str(outside.resolve())


def test_outside_workspace_ruff_lints_via_stdin_with_absolute_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Force Ruff to look available without depending on a real binary.
    monkeypatch.setattr(
        "ecli.extensions.ecli_integration.diagnostics.providers.ruff.shutil.which",
        lambda _executable: "/usr/bin/ruff",
    )
    runner = _RecordingRunner(CommandResult(0, "[]"))
    provider = RuffDiagnosticsProvider(runner=runner)
    registry = ProviderRegistry(
        active_providers=(provider,), labels={"python": "Python"}
    )
    workspace = tmp_path / "ws"
    workspace.mkdir()
    outside = tmp_path / "external.py"
    service = DiagnosticsService(registry=registry, workspace_root=workspace)

    state = service.collect(str(outside), text="import os\n")

    assert state.status is not DiagnosticsStatus.OUTSIDE_WORKSPACE
    assert state.status is DiagnosticsStatus.NO_DIAGNOSTICS  # ruff returned "[]"
    assert state.external is True
    # Ruff ran through stdin with the absolute path passed only as stdin-filename.
    assert "--stdin-filename" in runner.argv
    idx = runner.argv.index("--stdin-filename")
    assert runner.argv[idx + 1] == str(outside.resolve())
    assert runner.argv[-1] == "-"  # buffer read from stdin, not from disk
    assert runner.text == "import os\n"


# --------------------------------------------------------------------------- #
# Bounded store.
# --------------------------------------------------------------------------- #


def test_store_is_bounded_with_lru_eviction() -> None:
    store = DiagnosticsStore(max_entries=2)
    store.put("a", "r1", DiagnosticsState.no_active_file())
    store.put("b", "r1", DiagnosticsState.no_active_file())
    store.get("a", "r1")  # touch "a" so "b" becomes least-recently-used
    store.put("c", "r1", DiagnosticsState.no_active_file())
    assert len(store) == 2
    assert store.get("b", "r1") is None
    assert store.get("a", "r1") is not None
    assert store.get("c", "r1") is not None


def test_store_revision_mismatch_is_a_miss() -> None:
    store = DiagnosticsStore()
    store.put("a", "r1", DiagnosticsState.no_active_file())
    assert store.get("a", "r2") is None
    assert store.get("a", "r1") is None  # stale entry was dropped
