<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: docs/product/supported-platforms.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->
# Supported Platforms

## Runtime Platforms (Current State)

- Linux (primary)
- FreeBSD
- macOS
- Windows

## Packaging Targets (Current Tooling)

- PyPI: wheel and source distribution
- Linux: PyInstaller executable, release tarball, DEB, RPM, openSUSE/SUSE RPM,
  Arch package, Slackware package, AppImage
- FreeBSD: `.pkg`
- macOS: `.app` / `.dmg`
- Windows: portable `.exe` and NSIS installer `.exe`
- Nix / NixOS: flake package and app
- Docker build helpers: Debian and RPM build containers

## Canonical 21-Item Artifact Coverage

The normative artifact list is the `Canonical 21-Item Platform & Packaging
Artifact Matrix` in `docs/release/artifact-contract.md`. Every entry below must
remain covered by tests under `tests/packaging/`, by `.claude/commands/`, by
`.codex/prompts/`, and (where relevant) by a GitHub workflow:

1. PyPI wheel
2. PyPI source distribution
3. Linux generic PyInstaller executable
4. Linux release tarball
5. Debian / Ubuntu `.deb`
6. generic RPM `.rpm`
7. openSUSE / SUSE RPM
8. Arch Linux `PKGBUILD`
9. Slackware `.txz`
10. AppImage
11. FreeBSD `.pkg`
12. FreeBSD ports/chroot build path
13. macOS `.app`
14. macOS `.dmg`
15. Windows portable `.exe`
16. Windows NSIS installer `.exe`
17. Nix flake
18. Nix/NixOS package expression
19. Docker DEB build helper
20. Docker RPM build helper
21. GitHub Actions release/workflow contract map

## Support Stance

- Current state indicates cross-platform packaging intent.
- Support quality is bounded by CI/workflow coverage and artifact contract compliance.
- The normative release-contract surface list lives in
  `docs/release/artifact-contract.md`. A platform/package surface is not
  release-ready unless it is represented in product/release docs, agent
  contracts, runbooks, and validation tests or contract checks.

### Support Status Definitions

- **Fully supported**: CI workflow passes, artifacts are produced and verified, and platform is recommended for production use.
- **Failing or unverified**: Build failures, test failures, or absence of CI workflow coverage; artifact may not be available or tested; not recommended for release.
- **Degraded**: Best-effort support with known issues or limited testing; not recommended for production until issues are resolved.

### Platform Status and Incident Management

- Live platform status: check CI dashboard and release notes for current status of each platform.
- Incident triage: degraded platforms are reviewed with each release cycle; maintainers assess whether to restore, drop, or stabilize the platform.
- Expected communication: major changes to platform status (removal, restoration, degradation) are noted in release documentation.
