<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: docs/release/README-release.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->
# Release Documentation

Defines canonical artifact contracts and release engineering process.

Every official ECLI release uploads exactly 21 ECLI-owned physical GitHub
Release assets, one per canonical matrix entry. Release publication is blocked
unless the exact 21 ECLI-owned assets are present under `releases/<version>/`
and verified by `scripts/verify_release_assets.py`.

The GitHub UI may show **Assets 23** because it adds `Source code (zip)` and
`Source code (tar.gz)` automatically. Those generated source archives are not
ECLI-owned uploaded artifacts and are not part of the canonical 21 artifact
contract entries. Checksum sidecars are mandatory CI/release verification
evidence under `.checksums/`, but they are not uploaded as separate GitHub
Release assets.

ECLI Full artifacts also carry the F4 linter provisioning contract. Release
readiness requires OS/artifact-context detection, detection of already-installed
required tools before provisioning, installation or bundling of missing required
linters/toolchains, executable checks, version probes, and provenance/checksum
evidence for bundled or GitHub/upstream downloaded binaries, JARs, and
tarballs. A missing required linter after ECLI Full install is a release blocker.
The provider-neutral entrypoints are `scripts/provision_f4_linters.py` and
`scripts/verify_f4_linter_provisioning.py`; they write and verify
`f4-linter-provisioning-<artifact-entry-id>.json` release evidence without
changing F4 runtime behavior.

Authoritative files:
- `artifact-contract.md`
- `build-matrix.md`
- `packaging-flows.md`
- `release-process.md`
- `release-checklist.md`
- `artifact-verification.md`
- `v0.2.4.md`
- `v0.2.3.md`
- `v0.2.2.md`
- `v0.2.1.md`
- `v0.2.0.md`
