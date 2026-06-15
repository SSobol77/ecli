<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: docs/release/release-checklist.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->
# Release Checklist

- [ ] Version in `pyproject.toml` is correct.
- [ ] `docs/release/artifact-contract.md` lists all 21 entries in the
      `Canonical 21-Item Platform & Packaging Artifact Matrix`, and every active
      platform/package surface in the `Platform & Packaging Release Contract
      Matrix`.
- [ ] Each of the 21 canonical entries has a `tests/packaging/` test file, a
      Claude command mapping, a Codex prompt mapping, and (where relevant) a
      mapped GitHub workflow; `uv run pytest -q tests/packaging` passes.
- [ ] Every active platform/package surface is represented in docs, Codex and
      Claude agent contracts, build/release runbooks, and validation tests or
      contract checks.
- [ ] Empty, stale, decorative, or unused packaging files have been removed from
      active workflows/scripts or wired into the matrix.
- [ ] Artifact contract names are configured and validated.
- [ ] `make help`, `make help-full`, `make list-targets`, `make doctor`, and
      `make sysinfo` match current package surfaces and canonical Python
      scripts.
- [ ] `make validate-gate2` passes before any publish step.
- [ ] Required packaging scripts exist and are executable.
- [ ] Active shell wrappers under `scripts/` are absent; Python entrypoints under
      `scripts/` are canonical. Windows PowerShell packaging
      (`scripts/build-and-package-windows.ps1`), the Claude hook
      (`.claude/hooks/block-mutations.sh`), and the FreeBSD chroot helper
      (`tools/freebsd-chroot-build.sh`) are classified separately.
- [ ] Confirm the removed FreeBSD package-renaming shell helper remains absent unless a future
      dedicated tools migration restores equivalent Python tooling.
- [ ] Workflow references are valid (no missing files such as packaging specs).
- [ ] Checksums are generated for all release artifacts.
- [ ] Contributor docs match actual release/build commands.
- [ ] FreeBSD governance policy reviewed for artifact handling.
- [ ] Release notes include known limitations and degraded flows.
- [ ] FreeBSD `.pkg` leg is **best-effort**: a failure of `build-freebsd` in
      `release.yml` does not block `publish-github-release`. If FreeBSD failed,
      attach the `.pkg` out-of-band by dispatching the standalone
      `FreeBSD 14 .pkg` workflow with `release_tag=v<version>` once the leg is
      green.
- [ ] Confirm vmactions/freebsd-vm is still pinned to a known-good commit SHA
      in both `release.yml` and `freebsd-pkg.yml`.
