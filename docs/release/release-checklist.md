<!--
SPDX-License-Identifier: Apache-2.0

Project: Ecli
File: docs/release/release-checklist.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the Apache License, Version 2.0.
See the LICENSE file in the project root for full license text.
-->
# Release Checklist

- [ ] Version in `pyproject.toml` is correct.
- [ ] Artifact contract names are configured and validated.
- [ ] `make validate-gate2` passes before any publish step.
- [ ] Required packaging scripts exist and are executable.
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
