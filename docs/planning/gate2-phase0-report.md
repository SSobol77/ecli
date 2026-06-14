<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: docs/planning/gate2-phase0-report.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
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
$ python3 -m pip index versions ecli-editor
ecli-editor (0.0.1)
Available versions: 0.0.1
  INSTALLED: 0.1.0
  LATEST:    0.0.1
```

PyPI namespace `ecli-editor` was reserved by the maintainer on 2026-05-09 with
placeholder version 0.0.1. No PyPI publication was performed by the agent.

## CI Status

| PR | Green evidence |
| --- | --- |
| #9 | Head `df821c7`: SonarCloud success and project automation success on https://github.com/SSobol77/ecli/pull/9 |
| #10 | Head `9a784d8`: SonarCloud success and project automation success on https://github.com/SSobol77/ecli/pull/10 |
| #11 | Head `fd45f30`: CI `test` success, SonarCloud success, project automation success on https://github.com/SSobol77/ecli/pull/11 |
| #12 | Head `88126c4`: CI success, PyPI/macOS/Windows validation success, SonarCloud success on https://github.com/SSobol77/ecli/pull/12 |

## Post-Merge Verification

Timestamp: 2026-05-09T23:15:08+02:00

### A.2.1 Smoke Tests

Initial amended command:

```sh
cd $(git rev-parse --show-toplevel)
python3 -m pip install --user -e ".[dev]" --quiet
python3 -m pytest tests/test_smoke.py -v
```

Output:

```text
error: externally-managed-environment

× This environment is externally managed
╰─> To install Python packages system-wide, try apt install
    python3-xyz, where xyz is the package you are trying to
    install.

    If you wish to install a non-Debian-packaged Python package,
    create a virtual environment using python3 -m venv path/to/venv.
    Then use path/to/venv/bin/python and path/to/venv/bin/pip. Make
    sure you have python3-full installed.

    If you wish to install a non-Debian packaged Python application,
    it may be easiest to use pipx install xyz, which will manage a
    virtual environment for you. Make sure you have pipx installed.

    See /usr/share/doc/python3.13/README.venv for more information.

note: If you believe this is a mistake, please contact your Python installation or OS distribution provider. You can override this, at the risk of breaking your Python installation or OS, by passing --break-system-packages.
hint: See PEP 668 for the detailed specification.
```

Debian 13 PEP 668 handling was triggered. Per maintainer amendment, the
developer-workstation verification reran with `--break-system-packages`. CI must
use a virtualenv instead of this override.

Rerun command:

```sh
cd $(git rev-parse --show-toplevel)
python3 -m pip install --user --break-system-packages -e ".[dev]" --quiet
python3 -m pytest tests/test_smoke.py -v
```

Output:

```text
  WARNING: The script dotenv is installed in '/home/ssb/.local/bin' which is not on PATH.
  Consider adding this directory to PATH or, if you prefer to suppress this warning, use --no-warn-script-location.
  WARNING: The script pygmentize is installed in '/home/ssb/.local/bin' which is not on PATH.
  Consider adding this directory to PATH or, if you prefer to suppress this warning, use --no-warn-script-location.
  WARNING: The scripts docutils, rst2html, rst2html4, rst2html5, rst2latex, rst2man, rst2odt, rst2pseudoxml, rst2s5, rst2xetex and rst2xml are installed in '/home/ssb/.local/bin' which is not on PATH.
  Consider adding this directory to PATH or, if you prefer to suppress this warning, use --no-warn-script-location.
  WARNING: The scripts coverage, coverage-3.13 and coverage3 are installed in '/home/ssb/.local/bin' which is not on PATH.
  Consider adding this directory to PATH or, if you prefer to suppress this warning, use --no-warn-script-location.
  WARNING: The scripts py.test and pytest are installed in '/home/ssb/.local/bin' which is not on PATH.
  Consider adding this directory to PATH or, if you prefer to suppress this warning, use --no-warn-script-location.
  WARNING: The scripts pyi-archive_viewer, pyi-bindepend, pyi-grab_version, pyi-makespec, pyi-set_version and pyinstaller are installed in '/home/ssb/.local/bin' which is not on PATH.
  Consider adding this directory to PATH or, if you prefer to suppress this warning, use --no-warn-script-location.
  WARNING: The scripts dmypy, mypy, mypyc, stubgen and stubtest are installed in '/home/ssb/.local/bin' which is not on PATH.
  Consider adding this directory to PATH or, if you prefer to suppress this warning, use --no-warn-script-location.
  WARNING: The script pyproject-build is installed in '/home/ssb/.local/bin' which is not on PATH.
  Consider adding this directory to PATH or, if you prefer to suppress this warning, use --no-warn-script-location.
  WARNING: The script tato is installed in '/home/ssb/.local/bin' which is not on PATH.
  Consider adding this directory to PATH or, if you prefer to suppress this warning, use --no-warn-script-location.
  WARNING: The script keyring is installed in '/home/ssb/.local/bin' which is not on PATH.
  Consider adding this directory to PATH or, if you prefer to suppress this warning, use --no-warn-script-location.
  WARNING: The script ecli is installed in '/home/ssb/.local/bin' which is not on PATH.
  Consider adding this directory to PATH or, if you prefer to suppress this warning, use --no-warn-script-location.
  WARNING: The script twine is installed in '/home/ssb/.local/bin' which is not on PATH.
  Consider adding this directory to PATH or, if you prefer to suppress this warning, use --no-warn-script-location.
ERROR: pip's dependency resolver does not currently take into account all the packages that are installed. This behaviour is the source of the following dependency conflicts.
jupyterlab 4.0.11 requires jupyter-lsp>=2.0.0, which is not installed.
============================= test session starts ==============================
platform linux -- Python 3.13.5, pytest-9.0.3, pluggy-1.5.0 -- /usr/bin/python3
cachedir: .pytest_cache
rootdir: /home/ssb/Code/Ecli/ecli
configfile: pyproject.toml
plugins: mock-3.15.1, asyncio-1.3.0, aiohttp-1.1.0, cov-7.1.0, anyio-4.8.0, typeguard-4.4.2
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 2 items

tests/test_smoke.py::test_package_imports PASSED                         [ 50%]
tests/test_smoke.py::test_version_format PASSED                          [100%]

============================== 2 passed in 0.01s ===============================
```

### A.2.2 Entry Point Smoke

Command:

```sh
python3 -c "from ecli.__main__ import main; print('OK', type(main).__name__)"
```

Output:

```text
Could not parse user config '/home/ssb/.config/ecli/config.toml': Unbalanced quotes (line 18 column 34 char 258). Using defaults.
OK function
```

### A.2.3-Revised Editable Install Entry Point Linkage Check

Command:

```sh
ls -la ~/.local/bin/ecli
```

Output:

```text
-rwxrwxr-x 1 ssb ssb 212 May  9 23:03 /home/ssb/.local/bin/ecli
```

Command:

```sh
file ~/.local/bin/ecli
```

Output:

```text
/home/ssb/.local/bin/ecli: Python script, ASCII text executable
```

Command:

```sh
python3 -c "import ecli; print('ecli', ecli.__version__)"
```

Output:

```text
ecli 0.1.0
```

Command:

```sh
python3 -c "from ecli.__main__ import main; print('entry point importable:', main.__name__)"
```

Output:

```text
Could not parse user config '/home/ssb/.config/ecli/config.toml': Unbalanced quotes (line 18 column 34 char 258). Using defaults.
entry point importable: main
```

The user-local config parse warning is outside the Gate 2 artifact contract; the
module import succeeds and falls back to defaults.

### A.2.4 Per-Platform Sidecar Format Spot Check

Command:

```sh
for f in $(find releases dist -name '*.sha256' 2>/dev/null); do
  line=$(head -1 "$f")
  if echo "$line" | grep -qE '^[0-9a-f]{64}  [^ /]+$'; then
    echo "OK   $f"
  else
    echo "FAIL $f -> $line"
  fi
done
```

Output:

```text
OK   releases/0.1.0/ecli_0.1.0_linux_x86_64.deb.sha256
OK   releases/0.1.0/ecli_0.1.0_linux_x86_64.rpm.sha256
OK   releases/0.1.0/ecli_0.1.0_freebsd_x86_64.pkg.sha256
OK   dist/ecli_editor-0.1.0-py3-none-any.whl.sha256
OK   dist/ecli_editor-0.1.0.tar.gz.sha256
```

### A.2.5 PyProject Windows-Deps Verification

Command:

```sh
python3 -c "
import tomllib
with open('pyproject.toml','rb') as f:
    d = tomllib.load(f)
deps = d['project']['dependencies']
bad = [x for x in deps if 'sys_platform != ' in x and 'win32' in x]
good_win = [x for x in deps if 'sys_platform == ' in x and 'win32' in x]
print('Excluding-Windows markers (must be 0):', len(bad))
for x in bad: print(' ', x)
print('Windows-only markers (must be >=1):', len(good_win))
for x in good_win: print(' ', x)
"
```

Output:

```text
Excluding-Windows markers (must be 0): 0
Windows-only markers (must be >=1): 1
  windows-curses>=2.4.0; sys_platform == 'win32'
```

### A.2.6 PyPI Namespace Verification

Command:

```sh
python3 -m pip index versions ecli-editor
```

Output:

```text
ecli-editor (0.0.1)
Available versions: 0.0.1
  INSTALLED: 0.1.0
  LATEST:    0.0.1
```

### A.3 Validator Implementation Review

The `validate-*-contract` targets are Makefile shell logic. Checksum validation
was originally implemented by the inline Make `verify_sha256` macro pattern.
This has been extracted to `scripts/verify-artifact.sh`; Make targets continue
to call the script, while CI consumers that require granular exit-code handling
can invoke it directly.

Direct invocation:

```sh
scripts/verify-artifact.sh <artifact-path>
```

### A.3 Direct Tamper Test

Command:

```sh
make clean && make package-pypi
WHL_SIDECAR=$(ls dist/ecli_editor-*.whl.sha256)
cp "$WHL_SIDECAR" "${WHL_SIDECAR}.bak"
ORIG=$(cat "$WHL_SIDECAR")
echo "ffff${ORIG:4}" > "$WHL_SIDECAR"
set +e
scripts/verify-artifact.sh "${WHL_SIDECAR%.sha256}"
rc=$?
set -e
echo "Direct invocation exit code: $rc"
mv "${WHL_SIDECAR}.bak" "$WHL_SIDECAR"
```

Output:

```text
rm -rf build/ dist/ .pytest_cache/ .ruff_cache/ .mypy_cache/ __pycache__
find . -type d -name "__pycache__" -exec rm -rf {} +
find . -type f -name "*.pyc" -delete
--> Intermediate build artifacts cleaned.
rm -rf build/ dist/ .pytest_cache/ .ruff_cache/ .mypy_cache/ __pycache__
find . -type d -name "__pycache__" -exec rm -rf {} +
find . -type f -name "*.pyc" -delete
--> Intermediate build artifacts cleaned.
--> Building Python packages (wheel + sdist)...
python3 -m build
* Creating isolated environment: venv+pip...
* Installing packages in isolated environment:
  - hatchling>=1.27
* Getting build dependencies for sdist...
* Building sdist...
* Building wheel from sdist
* Creating isolated environment: venv+pip...
* Installing packages in isolated environment:
  - hatchling>=1.27
* Getting build dependencies for wheel...
* Building wheel...
Successfully built ecli_editor-0.1.0.tar.gz and ecli_editor-0.1.0-py3-none-any.whl
python3 -m twine check --strict dist/*.whl dist/*.tar.gz
Checking dist/ecli_editor-0.1.0-py3-none-any.whl: [32mPASSED[0m
Checking dist/ecli_editor-0.1.0.tar.gz: [32mPASSED[0m
make package-pypi-assert
make[1]: Entering directory '/home/ssb/Code/Ecli/ecli'
ecli_editor-0.1.0-py3-none-any.whl: OK
ecli_editor-0.1.0.tar.gz: OK
--> OK: dist/ecli_editor-0.1.0-py3-none-any.whl
--> OK: dist/ecli_editor-0.1.0-py3-none-any.whl.sha256
--> OK: dist/ecli_editor-0.1.0.tar.gz
--> OK: dist/ecli_editor-0.1.0.tar.gz.sha256
make[1]: Leaving directory '/home/ssb/Code/Ecli/ecli'
ecli_editor-0.1.0-py3-none-any.whl: FAILED
sha256sum: WARNING: 1 computed checksum did NOT match
checksum mismatch: dist/ecli_editor-0.1.0-py3-none-any.whl
Direct invocation exit code: 4
```

### A.4 PyPI Publish Workflow Guard

Namespace ownership checks were added to:

- `.github/workflows/pypi-validate.yml`
- `.github/workflows/release.yml` `publish-pypi` job

The release workflow PyPI environment URL was corrected to
`https://pypi.org/p/ecli-editor` to match `pyproject.toml` and the reserved PyPI
project.

## Known Debt

- License drift remains out of scope: `pyproject.toml` uses GPL-2.0-only metadata
  while legacy license metadata disagreed with the GPL-2.0-only project license. Issue #33 was not open/visible at
  report time.
- PyPI namespace `ecli-editor` reserved on 2026-05-09 with placeholder version
  0.0.1. Verified at https://pypi.org/project/ecli-editor/0.0.1/. Maintainer
  rotated the API token used for the placeholder upload to a project-scoped
  token after that operation.

  Open Phase 1 follow-up: migrate to PyPI Trusted Publishers (OIDC) per issue
  #34 (if open). This will eliminate the static-token requirement entirely;
  until then, publish workflow uses scoped API token from GitHub Secrets.
- The root `main.py` shim is retained for contributor workflow compatibility.
- Notarization, code signing, NSIS audit, MSI packaging, SBOM generation, SLSA
  provenance, and reproducible build attestation remain Phase 1+ work.
- GNU Make cannot propagate arbitrary recipe exit codes as its own process exit;
  failed recipes return make process exit `2` while reporting the recipe error
  code in the log.
