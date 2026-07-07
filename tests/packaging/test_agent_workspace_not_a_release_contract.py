# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: tests/packaging/test_agent_workspace_not_a_release_contract.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Repository hygiene invariant: agent workspace files are not a release contract.

``AGENTS.md``, ``CLAUDE.md``, ``CODEX.md``, ``CURSOR.md``, ``.claude/``,
``.codex/``, and ``.cursor/`` are workspace-local operational files. They are
not product source, not release artifacts, not packaging inputs, and not
release-contract surfaces.

This module locks in the invariants that replace the old agent-coverage-parity
checks (Claude command / Codex prompt fields on every canonical artifact):

1. The seven paths are root-anchored, ignored entries in ``.gitignore``.
2. The seven paths are not tracked by git.
3. The canonical packaging-contract registries (``CANONICAL_ARTIFACTS`` in
   ``conftest.py`` and ``WORKFLOW_CONTRACT`` in
   ``test_packaging_workflows_contract.py``) reference no path under
   ``.claude/``, ``.codex/``, or ``.cursor/``, and the ``Artifact`` dataclass
   carries no agent-command field.
4. The normative ``docs/release/artifact-contract.md`` matrix requires no
   agent workspace file as a release artifact or coverage column.
"""

from __future__ import annotations

import dataclasses
import subprocess
from pathlib import Path

from conftest import CANONICAL_ARTIFACTS, CANONICAL_CONTRACT_DOC, Artifact, RepoReader


AGENT_WORKSPACE_ROOT_GITIGNORE_ENTRIES = (
    "/AGENTS.md",
    "/CLAUDE.md",
    "/CODEX.md",
    "/CURSOR.md",
    "/.claude/",
    "/.codex/",
    "/.cursor/",
)

AGENT_WORKSPACE_TRACKED_PATHS = (
    "AGENTS.md",
    "CLAUDE.md",
    "CODEX.md",
    "CURSOR.md",
    ".claude",
    ".codex",
    ".cursor",
)

AGENT_WORKSPACE_DIR_TOKENS = (
    ".claude/",
    ".codex/",
    ".cursor/",
)


def test_gitignore_has_root_anchored_agent_workspace_entries(
    read_repo_text: RepoReader,
) -> None:
    gitignore = read_repo_text(".gitignore")
    for pattern in AGENT_WORKSPACE_ROOT_GITIGNORE_ENTRIES:
        assert pattern in gitignore, (
            f"missing root-anchored .gitignore entry: {pattern}"
        )


def test_agent_workspace_paths_are_not_git_tracked(repo_root: Path) -> None:
    result = subprocess.run(
        ["git", "ls-files", *AGENT_WORKSPACE_TRACKED_PATHS],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stdout.strip() == "", (
        f"agent workspace paths must not be tracked: {result.stdout.strip()}"
    )


def test_artifact_dataclass_has_no_agent_command_fields() -> None:
    field_names = {field.name for field in dataclasses.fields(Artifact)}
    assert "claude_command" not in field_names
    assert "codex_prompt" not in field_names


def test_canonical_artifacts_reference_no_agent_workspace_path() -> None:
    for artifact in CANONICAL_ARTIFACTS:
        haystacks = [artifact.artifact_token, artifact.test_file, *artifact.sources]
        if artifact.workflow is not None:
            haystacks.append(artifact.workflow)
        for value in haystacks:
            for token in AGENT_WORKSPACE_DIR_TOKENS:
                assert token not in value, (
                    f"canonical artifact {artifact.key!r} references "
                    f"agent workspace path via {value!r}"
                )


def test_workflow_contract_map_has_no_agent_command_field(
    read_repo_text: RepoReader,
) -> None:
    workflows_test = read_repo_text(
        "tests/packaging/test_packaging_workflows_contract.py"
    )
    assert "agent_contracts" not in workflows_test
    for token in AGENT_WORKSPACE_DIR_TOKENS:
        assert token not in workflows_test


def test_artifact_contract_matrix_has_no_agent_coverage_columns(
    read_repo_text: RepoReader,
) -> None:
    contract = read_repo_text(CANONICAL_CONTRACT_DOC)
    assert "Required Claude command coverage" not in contract
    assert "Required Codex prompt coverage" not in contract
    assert "Codex and Claude agent contracts" not in contract


def test_mandatory_release_asset_names_exclude_agent_workspace_files(
    read_repo_text: RepoReader,
) -> None:
    contract = read_repo_text(CANONICAL_CONTRACT_DOC)
    start = contract.index("Mandatory GitHub Release asset names")
    block_start = contract.index("```text", start)
    block_end = contract.index("```", block_start + len("```text"))
    asset_block = contract[block_start:block_end]

    for name in ("AGENTS.md", "CLAUDE.md", "CODEX.md", "CURSOR.md"):
        assert name not in asset_block, (
            f"{name} must not appear in the mandatory release asset list"
        )
