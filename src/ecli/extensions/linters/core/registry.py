# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: src/ecli/extensions/linters/core/registry.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Shared registry types for the ECLI Linter Pack microservices.

This module is **data only**: it declares the ``LinterDefinition`` and
``PackageContract`` shapes every linter microservice's ``manifest.py`` and
``package_contract.py`` build an instance of, plus small generic lookup
helpers over an explicit catalog tuple. It does not know about any
specific linter and does not import any ``ecli.extensions.linters.<name>``
package -- that would invert the dependency direction (each microservice
depends on ``core``, not the other way around).

The concrete, ordered catalog of every microservice's manifest lives in
``ecli.extensions.linters`` (the top-level package), which imports each
microservice's ``manifest.MANIFEST`` and aggregates them using the helpers
here. See ``docs/architecture/ecli-f4-linter-microservices-design.md``
section 6 ("Microservice Internal Contract") and
``docs/extensions/diagnostics-linter-layer.md``.

This module does **not** execute any linter binary or parse any linter
output; it is metadata only, exactly like the ``linter_catalog.py`` module
it replaces.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


# Whether a linter can read the buffer contents from stdin instead of (or in
# addition to) a real file on disk:
#   "unsupported" -- must be given a real file path; no stdin support.
#   "optional"    -- can read from stdin, but a file path also works.
#   "required"    -- only reads from stdin; there is no file-path invocation.
StdinMode = Literal["unsupported", "optional", "required"]

# What a linter integration can eventually do with a given definition.
#   "lint" -- produce diagnostics.
#   "fix"  -- apply the linter's own autofix/rewrite mode.
Capability = Literal["lint", "fix"]

# Output-shape identifier for a *future* parser, not implemented here.
#   "json_generic" -- a flat JSON array/object of offense records.
#   "eslint_json"  -- ESLint's specific `[{filePath, messages: [...]}]` shape.
#   "cargo_json"   -- Cargo's newline-delimited JSON message stream.
#   "biome_json"   -- Biome's `--reporter=json` diagnostics shape.
#   "xml_generic"  -- a generic XML offense report (Checkstyle, SpotBugs, ...).
#   "text_lines"   -- line-oriented plain text, one offense per line.
#   "zig_text"     -- `zig fmt --check` line-oriented plain text output.
ParserId = Literal[
    "json_generic",
    "eslint_json",
    "cargo_json",
    "biome_json",
    "xml_generic",
    "text_lines",
    "zig_text",
]

# Explicit allow-list. LinterDefinition.__post_init__ rejects any parser
# identifier not in this set, so the catalog can never reference a parser
# that does not (yet) exist.
ALLOWED_PARSERS: frozenset[str] = frozenset(
    {
        "json_generic",
        "eslint_json",
        "cargo_json",
        "biome_json",
        "xml_generic",
        "text_lines",
        "zig_text",
    }
)

# Curation level within the ECLI Linter Pack:
#   "core"        -- bundled with the editor itself (no external binary),
#                    e.g. Ruff. Always available, never gated on $PATH.
#   "recommended" -- the modern, curated default for its language/ecosystem;
#                    enabled by default when the executable is present.
#   "optional"    -- a specialist or power-user tool a user can opt into;
#                    never enabled by default.
#   "legacy"      -- superseded by a "recommended" entry; kept only for
#                    backward-compatible/opt-in use, never a default.
Tier = Literal["core", "recommended", "optional", "legacy"]

ALLOWED_TIERS: frozenset[str] = frozenset({"core", "recommended", "optional", "legacy"})

# Packaging/profile bucket used by the future "ECLI Linter Pack" installer
# to group tools that make sense to install together:
#   "core"     -- cross-language essentials (config/docs formats) bundled
#                 with every Full install regardless of what languages a
#                 user works in.
#   "web"      -- JS/TS/JSON/CSS/GraphQL tooling.
#   "systems"  -- ECLI's systems-programming identity: Rust, Zig, C/C++.
#   "devops"   -- shell scripts, CI workflows, container build tooling.
#   "data"     -- data/query languages, e.g. SQL.
#   "infra"    -- infrastructure-as-code, e.g. Terraform.
#   "language" -- other single-language profiles/specialists (Go, Java,
#                 deep Python lint, ...).
#   "prose"    -- natural-language/writing tooling (future profile; no
#                 entries yet).
InstallGroup = Literal[
    "core", "web", "systems", "devops", "data", "infra", "language", "prose"
]

ALLOWED_INSTALL_GROUPS: frozenset[str] = frozenset(
    {"core", "web", "systems", "devops", "data", "infra", "language", "prose"}
)

# Whether a definition describes a binary ECLI would shell out to on $PATH
# ("external", the default) or a capability ECLI already embeds/ships
# in-process ("internal", e.g. Ruff). Internal entries exist here purely so
# the registry is a single source of truth for "what lints Python" -- they
# are never dispatched through a future generic external-command provider.
ProviderKind = Literal["internal", "external"]


CANONICAL_ARTIFACT_ENTRY_IDS: tuple[str, ...] = (
    "pypi-wheel",
    "pypi-sdist",
    "linux-pyinstaller",
    "linux-tarball",
    "deb",
    "rpm",
    "opensuse-rpm",
    "arch-pkgbuild",
    "slackware-txz",
    "appimage",
    "freebsd-pkg",
    "freebsd-ports-chroot",
    "macos-app",
    "macos-dmg",
    "windows-portable-exe",
    "windows-nsis-installer",
    "nix-flake",
    "nixos-package",
    "docker-deb-helper",
    "docker-rpm-helper",
    "gha-release-contract",
)

InstallMechanism = Literal[
    "artifact-policy",
    "bundled-binary",
    "bundled-internal",
    "ecli-managed-tools",
    "jar-shim",
    "language-package-manager",
    "nix-derivation",
    "os-package-manager",
    "toolchain-component",
    "verified-upstream-download",
]

ALLOWED_INSTALL_MECHANISMS: frozenset[str] = frozenset(
    {
        "artifact-policy",
        "bundled-binary",
        "bundled-internal",
        "ecli-managed-tools",
        "jar-shim",
        "language-package-manager",
        "nix-derivation",
        "os-package-manager",
        "toolchain-component",
        "verified-upstream-download",
    }
)

ProvenanceRequirement = Literal[
    "artifact-entry-id",
    "checksum-or-ecli-provenance-when-downloaded",
    "deterministic-install-log",
    "ecli-version",
    "executable-permission",
    "pinned-version-when-downloaded",
    "source-url-when-downloaded",
    "version-probe",
]

ALLOWED_PROVENANCE_REQUIREMENTS: frozenset[str] = frozenset(
    {
        "artifact-entry-id",
        "checksum-or-ecli-provenance-when-downloaded",
        "deterministic-install-log",
        "ecli-version",
        "executable-permission",
        "pinned-version-when-downloaded",
        "source-url-when-downloaded",
        "version-probe",
    }
)


@dataclass(frozen=True)
class LinterDefinition:
    """Immutable declarative metadata for one ECLI Linter Pack entry.

    ``argv_template`` is always a tuple of individual argv tokens (never a
    shell string) suitable for a future ``subprocess.run(argv, shell=False)``
    call. The literal token ``"{file}"`` marks where a target file path will
    eventually be substituted; project-scoped tools (for example Cargo
    Clippy or golangci-lint, which lint a whole crate/module) omit it. A
    few multi-argument tools (for example Checkstyle, PMD) also use
    ``"{config}"`` / ``"{ruleset}"`` placeholders their own microservice
    provider resolves; this is metadata only, no template is executed here.

    Each linter microservice's ``manifest.py`` builds exactly one
    ``LinterDefinition`` instance for its tool.
    """

    name: str
    display_name: str
    languages: tuple[str, ...]
    file_extensions: tuple[str, ...]
    executable: str
    argv_template: tuple[str, ...]
    stdin_mode: StdinMode
    parser: ParserId
    config_files: tuple[str, ...]
    capabilities: tuple[Capability, ...]
    tier: Tier
    install_group: InstallGroup
    install_hint: str
    homepage_url: str
    enabled_by_default: bool = True
    bundled_with_full_install: bool = False
    provider_kind: ProviderKind = "external"
    package_hints: tuple[str, ...] = field(default_factory=tuple)
    supersedes: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        """Validate declarative invariants at construction time."""
        if self.parser not in ALLOWED_PARSERS:
            raise ValueError(
                f"linter {self.name!r} uses unknown parser {self.parser!r}; "
                f"must be one of {sorted(ALLOWED_PARSERS)}"
            )
        if self.tier not in ALLOWED_TIERS:
            raise ValueError(
                f"linter {self.name!r} uses unknown tier {self.tier!r}; "
                f"must be one of {sorted(ALLOWED_TIERS)}"
            )
        if self.install_group not in ALLOWED_INSTALL_GROUPS:
            raise ValueError(
                f"linter {self.name!r} uses unknown install_group "
                f"{self.install_group!r}; must be one of "
                f"{sorted(ALLOWED_INSTALL_GROUPS)}"
            )
        if self.provider_kind not in ("internal", "external"):
            raise ValueError(
                f"linter {self.name!r} uses unknown provider_kind "
                f"{self.provider_kind!r}; must be 'internal' or 'external'"
            )
        if not self.languages and not self.file_extensions:
            raise ValueError(
                f"linter {self.name!r} must declare at least one language "
                "or file extension"
            )
        if not self.executable:
            raise ValueError(f"linter {self.name!r} must declare an executable name")
        for token in self.argv_template:
            if any(ch in token for ch in ("&&", "||", "|", ";", ">", "<")):
                raise ValueError(
                    f"linter {self.name!r} argv_template token {token!r} looks "
                    "like shell syntax; argv_template must be a plain argv list"
                )


@dataclass(frozen=True)
class PackageContract:
    """Per-microservice packaging-delivery skeleton (metadata only).

    Mirrors ``docs/architecture/ecli-f4-linter-microservices-design.md``
    section 6.4. This is declarative metadata only: no packaging logic, no
    installer commands, no artifact generation. Real packaging
    implementation is out of scope for this migration.
    """

    service_name: str
    mandatory_for_full_install: bool
    bundled_with_full_install: bool
    binary_names: tuple[str, ...]
    version_probe: tuple[str, ...]
    delivery_notes: str
    allowed_install_mechanisms: tuple[InstallMechanism, ...] = (
        "artifact-policy",
    )
    provenance_requirements: tuple[ProvenanceRequirement, ...] = (
        "artifact-entry-id",
        "version-probe",
        "deterministic-install-log",
        "checksum-or-ecli-provenance-when-downloaded",
    )
    source_url: str | None = None
    pinned_version: str | None = None
    checksum_required_for_downloads: bool = True
    artifact_entry_ids: tuple[str, ...] = field(
        default_factory=lambda: CANONICAL_ARTIFACT_ENTRY_IDS
    )

    def __post_init__(self) -> None:
        """Validate declarative package/provisioning metadata."""
        if not self.service_name:
            raise ValueError("package contract service_name must be non-empty")
        if not self.binary_names:
            raise ValueError(
                f"package contract {self.service_name!r} must name a binary"
            )
        if not self.version_probe:
            raise ValueError(
                f"package contract {self.service_name!r} must name a version probe"
            )
        unknown_mechanisms = sorted(
            set(self.allowed_install_mechanisms) - ALLOWED_INSTALL_MECHANISMS
        )
        if unknown_mechanisms:
            raise ValueError(
                f"package contract {self.service_name!r} uses unknown install "
                f"mechanism(s): {unknown_mechanisms}"
            )
        unknown_provenance = sorted(
            set(self.provenance_requirements) - ALLOWED_PROVENANCE_REQUIREMENTS
        )
        if unknown_provenance:
            raise ValueError(
                f"package contract {self.service_name!r} uses unknown provenance "
                f"requirement(s): {unknown_provenance}"
            )
        if tuple(self.artifact_entry_ids) != CANONICAL_ARTIFACT_ENTRY_IDS:
            raise ValueError(
                f"package contract {self.service_name!r} must cover exactly "
                "the canonical 21 artifact entry ids"
            )


def get_linter(catalog: tuple[LinterDefinition, ...], name: str) -> LinterDefinition:
    """Return the entry named ``name`` from ``catalog``.

    Raises:
        KeyError: if no entry in ``catalog`` is registered under ``name``.
    """
    for entry in catalog:
        if entry.name == name:
            return entry
    raise KeyError(f"unknown linter in catalog: {name!r}")


def iter_linters(catalog: tuple[LinterDefinition, ...]) -> tuple[LinterDefinition, ...]:
    """Return every entry in ``catalog``, in declaration order."""
    return catalog


def linters_for_language(
    catalog: tuple[LinterDefinition, ...], language: str
) -> tuple[LinterDefinition, ...]:
    """Return entries in ``catalog`` that declare support for ``language``."""
    return tuple(entry for entry in catalog if language in entry.languages)
