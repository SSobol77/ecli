<!--
Filename: docs/planning/gate2-phase0-report.md
Project:  ECLI
License:  MIT
Author:   Siergej Sobolewski
Copyright: (c) 2026 Siergej Sobolewski
-->

# Gate 2 Phase 0 Report

Date: 2026-05-09

Repository: `https://github.com/SSobol77/ecli`

## Summary

| PR | Merge commit | Files | Line delta | Target additions |
| --- | --- | ---: | ---: | --- |
| #9 `feat(release): canonicalize artifact naming` | `d861aa4` | 15 | +425 / -100 | Canonical artifact variables and show-target globs |
| #10 `fix(make): critical release bugfixes` | `cca38ca` | 3 | +115 / -50 | `_ensure-tag`; cleaned package prereqs |
| #11 `refactor(make+pyproject): DRY + verification + pyproject hardening` | `3ee656a` | 28 | +648 / -420 | `package-all-host`, `distclean`, checksum-backed asserts |
| #12 `feat(ci): Gate 2 contract validation` | `3990a9c` | 9 | +237 / -0 | `validate-version-consistency`, `validate-*-contract`, `validate-gate2` |

## Audit Resolution

| Finding | Status |
| --- | --- |
| B1 quoted Snap glob | Fixed in PR #10 |
| B2 literal `\n` release notes | Fixed in PR #10 |
| B3 tag creation race | Fixed in PR #10 |
| B4 tar package user install side effect | Fixed in PR #10 |
| B5 Docker package targets missing `clean` | Fixed in PR #10 |
| N1 naming inconsistency | Fixed in PR #9; tracked seed artifacts canonicalized in PR #11 |
| N2 PyPI sidecars missing | Fixed in PR #11 |
| N3 existence-only assertions | Fixed in PR #11 and hardened by PR #12 validators |
| DRY repeated version extraction | Fixed in PR #11 |
| D1 host-unaware `package-all` | Fixed in PR #11 |
| D2 `publish-all` uploads absent artifacts | Fixed in PR #11 |
| D3 predicted macOS arch | Fixed in PR #11 via generated `.env` fragments |
| D5 `clean` deletes `releases/` | Fixed in PR #11 with `distclean` split |
| D6 Snap missing `clean` prereq | Fixed in PR #10 |
| Missing Gate 2 validators | Fixed in PR #12 |
| PyPI `ecli` ownership blocker | Resolved by maintainer decision Q5: distribution name is `ecli-editor`; placeholder reservation remains maintainer-owned work |
| AppImage path mismatch | Fixed in PR #9 |
| Sidecar format inconsistency | Fixed in PR #11 |
| Stale untracked manifest/validator | Removed in PR #9 cleanup |
| License drift | Out of scope; issue #33 was not visible/open via GitHub API at report time |
| Non-English macOS comments | Touched comments translated in PR #11 |

## Maintainer Decisions

| Question | Decision | Applied in | Commit |
| --- | --- | --- | --- |
| Q1 legacy release compatibility | No published releases/tags; canonical naming approved | Makefile, packaging scripts, workflows, artifact contract | `d861aa4`, `3ee656a` |
| Q2 pyproject dependency authority | Use `pyproject.toml` dev extras for install | `Makefile`, `pyproject.toml` | `3ee656a` |
| Q3 `__version__` export | Add `version("ecli-editor")` with local fallback | `src/ecli/__init__.py` | `3ee656a` |
| Q4 protected environments | Not configured; no workflow `environment:` binding in PR #4 | validation workflows, release process docs | `3990a9c` |
| Q5 PyPI name | Distribution is `ecli-editor`; import and CLI remain `ecli` | `pyproject.toml`, `src/ecli/__init__.py`, docs | `3ee656a`, `3990a9c` |

## Verification Log

### `make sysinfo`

```text
╔═══════════════════════════════════════════════════════════════════════╗
║                    SYSTEM INFORMATION                                 ║
╚═══════════════════════════════════════════════════════════════════════╝
OS:               Linux
Architecture:     x86_64 (normalized: x86_64)
Python Version:   Python 3.13.5
ECLI Version:     0.1.0
Release Dir:      releases/0.1.0

Available Tools:
  ✓ Docker
  ✗ GitHub CLI (needed for release targets)
  ✗ PowerShell 7+ (needed for Windows builds)
  ✗ AppImageKit (needed for AppImage builds)
  ✗ Snapcraft (needed for Snap builds)
```

### `make clean && make package-pypi && make validate-pypi-contract`

```text
rm -rf build/ dist/ .pytest_cache/ .ruff_cache/ .mypy_cache/ __pycache__
find . -type d -name "__pycache__" -exec rm -rf {} +
find . -type f -name "*.pyc" -delete
--> Intermediate build artifacts cleaned.
--> Building Python packages (wheel + sdist)...
python3 -m build
Successfully built ecli_editor-0.1.0.tar.gz and ecli_editor-0.1.0-py3-none-any.whl
python3 -m twine check --strict dist/*.whl dist/*.tar.gz
Checking dist/ecli_editor-0.1.0-py3-none-any.whl: PASSED
Checking dist/ecli_editor-0.1.0.tar.gz: PASSED
make package-pypi-assert
ecli_editor-0.1.0-py3-none-any.whl: OK
ecli_editor-0.1.0.tar.gz: OK
--> OK: dist/ecli_editor-0.1.0-py3-none-any.whl
--> OK: dist/ecli_editor-0.1.0-py3-none-any.whl.sha256
--> OK: dist/ecli_editor-0.1.0.tar.gz
--> OK: dist/ecli_editor-0.1.0.tar.gz.sha256
Checking dist/ecli_editor-0.1.0-py3-none-any.whl: PASSED
Checking dist/ecli_editor-0.1.0.tar.gz: PASSED
ecli_editor-0.1.0-py3-none-any.whl: OK
ecli_editor-0.1.0.tar.gz: OK
--> OK: PyPI contract
```

### Wheel Sidecar

```text
$ cat dist/ecli_editor-0.1.0-py3-none-any.whl.sha256
6fedeaa397c863273bc1d07aa3fcda315a061da21edc119f1cfc57a028e4eb00  ecli_editor-0.1.0-py3-none-any.whl
```

Sidecars intentionally use basename-only coreutils format. Verification is run
from the sidecar directory:

```text
$ (cd dist && sha256sum -c ecli_editor-0.1.0-py3-none-any.whl.sha256)
ecli_editor-0.1.0-py3-none-any.whl: OK
```

### `make validate-gate2`

```text
pyproject=0.1.0 ecli.__version__=0.1.0
--> OK: PyPI contract
--> OK: DEB contract
--> OK: RPM contract
SKIP: AppImage artifact not built: releases/0.1.0/ecli_0.1.0_linux_x86_64.AppImage
--> OK: FreeBSD contract
SKIP: macOS artifact not built: releases/0.1.0/ecli_0.1.0_macos_x86_64.dmg
SKIP: Windows artifact not built: releases/0.1.0/ecli_0.1.0_win_x86_64.exe
--> OK: Gate 2 validation completed for built artifacts
```

### Deliberate Corruption Test

```text
Checking dist/ecli_editor-0.1.0-py3-none-any.whl: PASSED
Checking dist/ecli_editor-0.1.0.tar.gz: PASSED
ecli_editor-0.1.0-py3-none-any.whl: FAILED
sha256sum: WARNING: 1 computed checksum did NOT match
checksum mismatch: dist/ecli_editor-0.1.0-py3-none-any.whl
make: *** [Makefile:948: validate-pypi-contract] Error 4
make_process_exit=2
```

GNU Make returns process exit `2` for failed recipes; the recipe contract itself
reports `Error 4` for checksum mismatch.

## Repository Tree

```text
.
├── AGENTS.md
├── audit-report.md
├── BUILD_QUICK_REFERENCE.md
├── BUILD_SYSTEM.md
├── CLAUDE.md
├── CODE_REVIEW_REPORT.md
├── CODEX.md
├── config.toml
├── CURSOR.md
├── docker
│   ├── build-linux-deb.Dockerfile
│   └── build-linux-rpm.Dockerfile
├── docs
│   ├── architecture
│   ├── archive
│   ├── config
│   ├── contributor
│   ├── extensions
│   ├── planning
│   ├── product
│   ├── quality
│   ├── README.md
│   ├── REFAKTORING.pdf
│   ├── release
│   └── tree.pdf
├── ecli.spec
├── editor.log
├── editorlog.txt
├── img
│   ├── background.jpg
│   ├── favicon.ico
│   ├── favicon.png
│   ├── logo_m.ico
│   ├── logo_m.png
│   └── logo.png
├── LICENSE
├── main.py
├── Makefile
├── MAKEFILE_UPGRADE_SUMMARY.md
├── packaging
│   ├── linux
│   ├── pyinstaller
│   └── windows
├── progress.log
├── pyproject.toml
├── pyrightconfig.json
├── README.md
├── requirements-dev.txt
├── scripts
│   ├── build-and-package-deb.sh
│   ├── build-and-package-freebsd.sh
│   ├── build-and-package-macos.sh
│   ├── build-and-package-rpm.sh
│   ├── build-and-package-windows.ps1
│   ├── build-docker.sh
│   ├── build-freebsd-pkg.sh
│   ├── build_freebsd_port.sh
│   ├── build_pyinstaller_linux.sh
│   ├── build_pyinstaller_windows.ps1
│   ├── package_appimage.sh
│   ├── publish_pypi.sh
│   ├── sign_checksums.sh
│   └── verify_runtime.sh
├── setup.cfg
├── sonar-project.properties
├── src
│   └── ecli
│       ├── core
│       ├── __init__.py
│       ├── integrations
│       ├── __main__.py
│       ├── py.typed
│       ├── ui
│       └── utils
├── tests
│   └── test_smoke.py
├── thirdparty.lock
├── tools
│   ├── freebsd-chroot-build.sh
│   ├── re-commit-config.yaml
│   ├── rename-freebsd-pkg.sh
│   └── Taskfile.yml
└── uv.lock
```

New files of note:

- `.github/workflows/pypi-validate.yml`
- `.github/workflows/macos-validate.yml`
- `.github/workflows/windows-validate.yml`
- `src/ecli/__main__.py`
- `src/ecli/py.typed`
- `tests/test_smoke.py`
- `docs/planning/gate2-phase0-report.md`

## PyPI Reservation Status

```text
$ python -m pip index versions ecli-editor
ERROR: No matching distribution found for ecli-editor
pip_index_exit=1
```

Maintainer reserves placeholder; PR #4 publish flow remains gated behind tag
push. No PyPI publication was performed by the agent.

## CI Status

| PR | Green evidence |
| --- | --- |
| #9 | Head `df821c7`: SonarCloud success and project automation success on https://github.com/SSobol77/ecli/pull/9 |
| #10 | Head `9a784d8`: SonarCloud success and project automation success on https://github.com/SSobol77/ecli/pull/10 |
| #11 | Head `fd45f30`: CI `test` success, SonarCloud success, project automation success on https://github.com/SSobol77/ecli/pull/11 |
| #12 | Head `88126c4`: CI success, PyPI/macOS/Windows validation success, SonarCloud success on https://github.com/SSobol77/ecli/pull/12 |

## Known Debt

- License drift remains out of scope: `pyproject.toml` uses Apache-2.0 metadata
  while `LICENSE` and source headers are MIT. Issue #33 was not open/visible at
  report time.
- The root `main.py` shim is retained for contributor workflow compatibility.
- Notarization, code signing, NSIS audit, MSI packaging, SBOM generation, SLSA
  provenance, and reproducible build attestation remain Phase 1+ work.
- GNU Make cannot propagate arbitrary recipe exit codes as its own process exit;
  failed recipes return make process exit `2` while reporting the recipe error
  code in the log.
