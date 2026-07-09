#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: scripts/provision_f4_linters.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Plan or verify F4 linter provisioning for canonical release artifacts.

Default execution is automation-safe: no network, no upstream downloads, and no
package-manager calls. ``dry-run`` writes deterministic provisioning evidence
that packaging and release tests can validate. ``verify-only`` checks existing
executables and version probes. ``provision`` intentionally fails closed for
missing required tools until an artifact-specific installer implementation wires
in a concrete, provenance-aware install path.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from ecli.extensions.linters.core.provisioning import (  # noqa: E402
    build_component_model,
    build_provisioning_plan,
    component_model_to_dict,
    evidence_to_dict,
    plan_has_release_blocking_failure,
    plan_to_evidence,
    read_project_version,
    write_evidence,
)
from ecli.extensions.linters.core.provisioning_registry import (  # noqa: E402
    ARTIFACT_CONTRACT_ENTRIES,
    get_artifact_entry,
    load_linter_tool_contracts,
)


EXIT_OK = 0
EXIT_INVALID = 1
EXIT_PROVISIONING_FAILED = 2


class _ContractArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:  # type: ignore[override]
        self.print_usage(sys.stderr)
        print(f"{self.prog}: error: {message}", file=sys.stderr)
        raise SystemExit(EXIT_INVALID)


def _bool_arg(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise argparse.ArgumentTypeError(f"expected boolean, got {value!r}")


def build_parser() -> argparse.ArgumentParser:
    parser = _ContractArgumentParser(
        prog="provision_f4_linters.py",
        description="Build F4 linter provisioning plans and evidence.",
    )
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--artifact", help="canonical artifact entry id, e.g. deb")
    target.add_argument(
        "--all-artifacts",
        action="store_true",
        help="process all 21 canonical artifact entries",
    )
    parser.add_argument("--target-dir", required=True, help="managed tools target dir")
    parser.add_argument("--evidence-dir", required=True, help="evidence output dir")
    parser.add_argument(
        "--mode",
        choices=("dry-run", "verify-only", "provision"),
        default="dry-run",
        help="execution mode; default is dry-run",
    )
    parser.add_argument(
        "--allow-network",
        type=_bool_arg,
        default=False,
        help="allow network actions; default false",
    )
    parser.add_argument(
        "--allow-upstream-downloads",
        type=_bool_arg,
        default=False,
        help="allow upstream/GitHub downloads; default false",
    )
    parser.add_argument(
        "--profile",
        choices=("full", "custom", "minimal"),
        default="full",
        help="selection profile; default full",
    )
    parser.add_argument(
        "--include-tool",
        action="append",
        default=(),
        help="include one tool id; repeatable",
    )
    parser.add_argument(
        "--exclude-tool",
        action="append",
        default=(),
        help="exclude one tool id; repeatable",
    )
    parser.add_argument(
        "--selection-json",
        help="JSON selection file with include/exclude/tools data",
    )
    parser.add_argument(
        "--list-selection-options",
        action="store_true",
        help="print installer component-selection model instead of evidence",
    )
    parser.add_argument("--json", action="store_true", help="print JSON output")
    return parser


def _artifact_ids(args: argparse.Namespace) -> tuple[str, ...]:
    if args.all_artifacts:
        return tuple(entry.artifact_entry_id for entry in ARTIFACT_CONTRACT_ENTRIES)
    return (args.artifact,)


def _print_human(paths: list[Path], failed: bool) -> None:
    for path in paths:
        print(f"wrote {path}")
    if failed:
        print("F4 linter provisioning contract failed", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    contracts = load_linter_tool_contracts()
    target_dir = Path(args.target_dir)
    evidence_dir = Path(args.evidence_dir)
    selection_path = Path(args.selection_json) if args.selection_json else None
    artifact_ids = _artifact_ids(args)

    if args.list_selection_options:
        models: list[dict[str, Any]] = []
        for artifact_id in artifact_ids:
            artifact = get_artifact_entry(artifact_id)
            models.append(
                component_model_to_dict(
                    build_component_model(
                        artifact,
                        args.profile,
                        contracts,
                    )
                )
            )
        if args.json:
            print(json.dumps({"artifacts": models}, indent=2, sort_keys=True))
        else:
            for model in models:
                print(f"{model['artifact_entry_id']}: {model['full_label']}")
                for option in model["options"]:
                    mark = "x" if option["selected_by_default"] else " "
                    required = (
                        "required" if option["required_for_full"] else option["tier"]
                    )
                    print(f"  [{mark}] {option['tool_id']} ({required})")
        return EXIT_OK

    version = read_project_version(ROOT)
    output: list[dict[str, Any]] = []
    paths: list[Path] = []
    failed = False
    for artifact_id in artifact_ids:
        plan = build_provisioning_plan(
            artifact_entry_id=artifact_id,
            target_dir=target_dir,
            evidence_dir=evidence_dir,
            mode=args.mode,
            profile=args.profile,
            include_tools=args.include_tool,
            exclude_tools=args.exclude_tool,
            selection_json=selection_path,
            allow_network=args.allow_network,
            allow_upstream_downloads=args.allow_upstream_downloads,
            contracts=contracts,
        )
        paths.append(write_evidence(plan, ecli_version=version))
        output.append(evidence_to_dict(plan_to_evidence(plan, ecli_version=version)))
        failed = failed or plan_has_release_blocking_failure(plan)

    if args.json:
        print(json.dumps({"artifacts": output}, indent=2, sort_keys=True))
    else:
        _print_human(paths, failed)
    return EXIT_PROVISIONING_FAILED if failed else EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
