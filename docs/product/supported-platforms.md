<!--
SPDX-License-Identifier: Apache-2.0

Project: Ecli
File: docs/product/supported-platforms.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the Apache License, Version 2.0.
See the LICENSE file in the project root for full license text.
-->
# Supported Platforms

## Runtime Platforms (Current State)

- Linux (primary)
- FreeBSD
- macOS
- Windows

## Packaging Targets (Current Tooling)

- Linux: DEB, RPM, AppImage
- FreeBSD: `.pkg`
- macOS: `.dmg`
- Windows: NSIS `.exe`

## Support Stance

- Current state indicates cross-platform packaging intent.
- Support quality is bounded by CI/workflow coverage and artifact contract compliance.

### Support Status Definitions

- **Fully supported**: CI workflow passes, artifacts are produced and verified, and platform is recommended for production use.
- **Failing or unverified**: Build failures, test failures, or absence of CI workflow coverage; artifact may not be available or tested; not recommended for release.
- **Degraded**: Best-effort support with known issues or limited testing; not recommended for production until issues are resolved.

### Platform Status and Incident Management

- Live platform status: check CI dashboard and release notes for current status of each platform.
- Incident triage: degraded platforms are reviewed with each release cycle; maintainers assess whether to restore, drop, or stabilize the platform.
- Expected communication: major changes to platform status (removal, restoration, degradation) are noted in release documentation.
