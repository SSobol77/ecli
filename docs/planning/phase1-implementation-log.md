<!--
Filename: docs/planning/phase1-implementation-log.md
Project:  ECLI
License:  MIT
Author:   Siergej Sobolewski
Copyright: (c) 2026 Siergej Sobolewski
-->

# Gate 2 Phase 1 Implementation Log

## Workstream A - macOS Universal2 Ad-Hoc DMG

Timestamp: 2026-05-10T00:59:22+02:00

Branch: `feat/phase1-macos-universal2`

Base commit:

```text
3fbbc46
```

### Verification: macOS Packaging Script Syntax

Command:

```sh
bash -n scripts/build-and-package-macos.sh
```

Output:

```text
```

Result: passed.

### Verification: PyInstaller Spec Syntax

Command:

```sh
python3 -m py_compile ecli.spec packaging/pyinstaller/ecli.spec
```

Output:

```text
```

Result: passed.

### Verification: Makefile macOS Package Dry Run

Command:

```sh
make -n package-macos
```

Output:

```text
rm -rf build/ dist/ .pytest_cache/ .ruff_cache/ .mypy_cache/ __pycache__
find . -type d -name "__pycache__" -exec rm -rf {} +
find . -type f -name "*.pyc" -delete
echo "--> Intermediate build artifacts cleaned."
./scripts/build-and-package-macos.sh
make package-macos-assert
make[1]: Entering directory '/home/ssb/Code/Ecli/ecli'
test -n "0.1.0" || (echo "MACOS_PKG_VERSION empty (pyproject.toml)"; exit 1)
scripts/verify-artifact.sh "releases/0.1.0/ecli_0.1.0_macos_universal2.dmg"
echo "--> OK: releases/0.1.0/ecli_0.1.0_macos_universal2.dmg"
echo "--> OK: releases/0.1.0/ecli_0.1.0_macos_universal2.dmg.sha256"
make[1]: Leaving directory '/home/ssb/Code/Ecli/ecli'
```

Result: passed. The Make target resolves the canonical Universal2 DMG path.

### Verification: Makefile macOS Contract Dry Run

Command:

```sh
make -n validate-macos-contract
```

Output:

```text
test -n "0.1.0" || (echo "MACOS_PKG_VERSION empty (pyproject.toml)"; exit 1)
scripts/verify-artifact.sh "releases/0.1.0/ecli_0.1.0_macos_universal2.dmg"
echo "--> OK: releases/0.1.0/ecli_0.1.0_macos_universal2.dmg"
echo "--> OK: releases/0.1.0/ecli_0.1.0_macos_universal2.dmg.sha256"
echo "--> OK: macOS contract"
```

Result: passed. The validator path continues to use `scripts/verify-artifact.sh`.

### Verification: Workflow YAML Parse

Command:

```sh
python3 - <<'PY'
from pathlib import Path
import yaml
for path in [Path(".github/workflows/macos-dmg.yml"), Path(".github/workflows/macos-validate.yml"), Path(".github/workflows/release.yml")]:
    with path.open("r", encoding="utf-8") as f:
        yaml.safe_load(f)
    print(f"OK {path}")
PY
```

Output:

```text
OK .github/workflows/macos-dmg.yml
OK .github/workflows/macos-validate.yml
OK .github/workflows/release.yml
```

Result: passed.

### Verification: Existing Smoke Tests

Command:

```sh
python3 -m pytest tests/test_smoke.py -v
```

Output:

```text
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

Result: passed.

### Verification: PyInstaller Spec Tracking

Command:

```sh
git check-ignore -v ecli.spec packaging/pyinstaller/ecli.spec
```

Output:

```text
.gitignore:61:!ecli.spec	ecli.spec
.gitignore:62:!packaging/pyinstaller/ecli.spec	packaging/pyinstaller/ecli.spec
```

Result: passed. The required spec files are explicitly unignored and trackable.

### Verification: Diff Hygiene

Command:

```sh
git diff --check
```

Output:

```text
```

Result: passed.

### macOS-Only Verification Boundary

The following acceptance checks are implemented in `.github/workflows/macos-dmg.yml`,
`.github/workflows/macos-validate.yml`, and `.github/workflows/release.yml`, but
were not executed on this Debian 13 workstation:

- `lipo -info` against the binary mounted from the DMG, asserting both `x86_64`
  and `arm64`.
- `codesign --verify --verbose` against the binary mounted from the DMG.
- `make validate-macos-contract` against a real macOS-built DMG.

These checks require a macOS runner with `lipo`, `codesign`, and `hdiutil`.

## Workstream A - PR #14 Pre-Merge Cleanup

Timestamp: 2026-05-10

Branch: `feat/phase1-macos-universal2`

### Verification: No Stale Root Spec References in Scripts

Command:

```sh
grep -rn "ecli\.spec" scripts/ | grep -v "packaging/pyinstaller/ecli.spec"
```

Output:

```text
```

Result: passed.

### Verification: Root Spec Removed

Command:

```sh
ls -la ecli.spec 2>&1
```

Output:

```text
ls: cannot access 'ecli.spec': No such file or directory
```

Result: passed.

### Verification: Gitignore Tracks Only Canonical Spec Exception

Command:

```sh
grep "ecli\.spec" .gitignore
```

Output:

```text
!packaging/pyinstaller/ecli.spec
```

Result: passed.

### Verification: README Naming Is Canonical

Command:

```sh
grep -n "ecli_0.1.0" README.md
```

Output:

```text
54:sudo apt install ./ecli_0.1.0_linux_x86_64.deb
57:sudo dnf install ./ecli_0.1.0_linux_x86_64.rpm
60:.\ecli_0.1.0_win_x86_64.exe
65:open ecli_0.1.0_macos_universal2.dmg
```

Result: passed.

### Verification: README PyPI Install Command

Command:

```sh
grep -n "pip install" README.md
```

Output:

```text
87:pip install ecli-editor
145:pip install ecli-editor
```

Result: passed.

### Verification: Stale BUILD Docs Removed

Command:

```sh
ls -la BUILD_QUICK_REFERENCE.md BUILD_SYSTEM.md MAKEFILE_UPGRADE_SUMMARY.md 2>&1
```

Output:

```text
ls: cannot access 'BUILD_QUICK_REFERENCE.md': No such file or directory
ls: cannot access 'BUILD_SYSTEM.md': No such file or directory
ls: cannot access 'MAKEFILE_UPGRADE_SUMMARY.md': No such file or directory
```

Result: passed.

### Verification: No README References to Deleted BUILD Docs

Command:

```sh
grep -n "BUILD_QUICK_REFERENCE\|BUILD_SYSTEM\|MAKEFILE_UPGRADE_SUMMARY" README.md
```

Output:

```text
```

Result: passed.

### Verification: Canonical Spec Is Tracked

Command:

```sh
git ls-files packaging/pyinstaller/ecli.spec
```

Output:

```text
packaging/pyinstaller/ecli.spec
```

Result: passed.

### Verification: Universal2 References Remain in Makefile and macOS Script

Command:

```sh
grep -n "macos_universal2" Makefile scripts/build-and-package-macos.sh
```

Output:

```text
Makefile:705:#       releases/<version>/ecli_<version>_macos_universal2.dmg
Makefile:706:#       releases/<version>/ecli_<version>_macos_universal2.dmg.sha256
scripts/build-and-package-macos.sh:6:#   releases/<version>/ecli_<version>_macos_universal2.dmg
scripts/build-and-package-macos.sh:7:#   releases/<version>/ecli_<version>_macos_universal2.dmg.sha256
scripts/build-and-package-macos.sh:75:UNIVERSAL_DIR="build/macos_universal2"
```

Result: passed.

### Verification: Smoke Tests

Command:

```sh
python3 -m pytest tests/test_smoke.py -v
```

Output:

```text
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

Result: passed.

## Workstream B - PyPI Static Token Publish and CycloneDX SBOM

Timestamp: 2026-05-10

Branch: `feat/phase1-pypi-token-sbom`

Base commit:

```text
46868b0
```

### Verification: PyPI Secret Presence

Command:

```sh
gh secret list --repo SSobol77/ecli
```

Output:

```text
PYPI_API_TOKEN	2026-05-10T00:11:02Z
```

Result: passed.

### Verification: No OIDC Permission in Release Workflow

Command:

```sh
grep -n "id-token" .github/workflows/release.yml
```

Output:

```text
```

Result: passed.

### Verification: Static PyPI Token Publish Step

Command:

```sh
grep -n "PYPI_API_TOKEN\|pypa/gh-action-pypi-publish\|password:" .github/workflows/release.yml
```

Output:

```text
301:        uses: pypa/gh-action-pypi-publish@v1.10.3
303:          password: ${{ secrets.PYPI_API_TOKEN }}
```

Result: passed.

### Verification: SBOM Configuration References

Command:

```sh
grep -n "cyclonedx-bom\|cyclonedx_py\|ecli-editor-.*cdx\|python-sbom\|CycloneDX" .github/workflows/release.yml pyproject.toml docs/release/release-process.md
```

Output:

```text
.github/workflows/release.yml:34:          python3 -m pip install --user cyclonedx-bom
.github/workflows/release.yml:39:            --output-file "dist/ecli-editor-${VERSION}.cdx.json" \
.github/workflows/release.yml:42:          sha256sum "ecli-editor-${VERSION}.cdx.json" > "ecli-editor-${VERSION}.cdx.json.sha256"
.github/workflows/release.yml:58:          name: python-sbom
.github/workflows/release.yml:336:            This release includes a CycloneDX SBOM for the Python distribution:
.github/workflows/release.yml:337:            `ecli-editor-<version>.cdx.json`, plus a SHA256 sidecar.
.github/workflows/release.yml:339:            The SBOM is generated by the `cyclonedx-bom` package through the
.github/workflows/release.yml:340:            `cyclonedx_py` module in CycloneDX JSON schema version 1.5.
pyproject.toml:77:    "cyclonedx-bom>=4.0",
docs/release/release-process.md:95:Release builds emit a CycloneDX SBOM for the Python distribution:
docs/release/release-process.md:98:dist/ecli-editor-<version>.cdx.json
docs/release/release-process.md:99:dist/ecli-editor-<version>.cdx.json.sha256
docs/release/release-process.md:102:The SBOM is generated with the `cyclonedx-bom` Python distribution, invoked as
docs/release/release-process.md:103:`python3 -m cyclonedx_py environment`, in JSON format and CycloneDX schema
```

Result: passed.

### Verification: Release Workflow YAML Parse

Command:

```sh
python3 - <<'PY'
from pathlib import Path
import yaml
for path in [Path('.github/workflows/release.yml')]:
    with path.open('r', encoding='utf-8') as f:
        yaml.safe_load(f)
    print(f'OK {path}')
PY
```

Output:

```text
OK .github/workflows/release.yml
```

Result: passed.

### Verification: Local Wheel and Sdist Build

Command:

```sh
.phase1-b-venv/bin/python -m build
```

Output:

```text
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
```

Result: passed.

### Verification: Twine Metadata Check

Command:

```sh
.phase1-b-venv/bin/python -m twine check --strict dist/*.whl dist/*.tar.gz
```

Output:

```text
Checking dist/ecli_editor-0.1.0-py3-none-any.whl: PASSED
Checking dist/ecli_editor-0.1.0.tar.gz: PASSED
```

Result: passed.

### Verification: CycloneDX SBOM Generation

Command:

```sh
.phase1-b-venv/bin/python -m cyclonedx_py environment \
  --pyproject pyproject.toml \
  --sv 1.5 \
  --output-format json \
  --output-file dist/ecli-editor-0.1.0.cdx.json \
  --validate
```

Output:

```text
```

Result: passed. The `cyclonedx-bom` distribution provides the `cyclonedx_py`
module; `environment --validate` validates the generated SBOM before writing
output.

### Verification: SBOM SHA256 Sidecar

Command:

```sh
(cd dist && sha256sum ecli-editor-0.1.0.cdx.json > ecli-editor-0.1.0.cdx.json.sha256)
cat dist/ecli-editor-0.1.0.cdx.json.sha256
```

Output:

```text
b28a172757d564053b44b3f7c63c52ed91b375da5ba2e1f97d83b87dc3fff644  ecli-editor-0.1.0.cdx.json
```

Result: passed.

### Verification: SBOM Content Inspection

Command:

```sh
python3 - <<'PY'
import json
from pathlib import Path
p = Path("dist/ecli-editor-0.1.0.cdx.json")
d = json.loads(p.read_text())
print("bomFormat:", d.get("bomFormat"))
print("specVersion:", d.get("specVersion"))
print("components:", len(d.get("components", [])))
PY
```

Output:

```text
bomFormat: CycloneDX
specVersion: 1.5
components: 61
```

Result: passed.

### Verification: PyPI Namespace Guard Dependency

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

Result: passed.

### Verification: Install Documentation

Command:

```sh
grep -n 'pip install ecli\|import ecli\|command remains `ecli`\|pypi.org/project/ecli-editor' README.md docs/contributor/install.md
```

Output:

```text
README.md:87:pip install ecli-editor
README.md:91:`ecli`, and the installed CLI command remains `ecli`.
README.md:148:pip install ecli-editor
README.md:154:import ecli
README.md:388:- **PyPI**: https://pypi.org/project/ecli-editor/
docs/contributor/install.md:20:| Any | Python package | Fallback path | `pip install ecli-editor` | `python -m ecli` or CLI startup | distribution name is `ecli-editor`; import and CLI names remain `ecli` |
```

Result: passed.

### Verification: Smoke Tests

Command:

```sh
python3 -m pytest tests/test_smoke.py -v
```

Output:

```text
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

============================== 2 passed in 0.02s ===============================
```

Result: passed.

### Verification: Diff Hygiene

Command:

```sh
git diff --check
```

Output:

```text
```

Result: passed.

No PyPI publish, GitHub Release creation, or tag push was performed.

### CI Correction: CycloneDX Distribution Name

PR #15 CI initially failed dependency resolution because the installable PyPI
distribution was specified as `cyclonedx-py>=4.0`. The module invocation is
`cyclonedx_py`, but the maintained PyPI distribution that provides current
4.x+ releases is `cyclonedx-bom`.

Command:

```sh
python3 -m pip index versions cyclonedx-py 2>&1
```

Output:

```text
cyclonedx-py (1.0.1)
Available versions: 1.0.1, 1.0.0
```

Command:

```sh
python3 -m pip index versions cyclonedx-bom 2>&1 | sed -n '1,8p'
```

Output:

```text
cyclonedx-bom (7.3.0)
Available versions: 7.3.0, 7.2.2, 7.2.1, 7.2.0, 7.1.0, 7.0.0, 6.1.3, 6.1.2, 6.1.1, 6.1.0, 6.0.0, 5.5.0, 5.4.0, 5.3.0, 5.2.0, 5.1.2, 5.1.1, 5.1.0, 5.0.0, 4.6.1, 4.6.0, 4.5.1, 4.5.0, 4.4.3, 4.4.2, 4.4.1, 4.4.0, 4.3.0, 4.2.0, 4.1.6, 4.1.5, 4.1.4, 4.1.3, 4.1.2, 4.1.1, 4.1.0, 4.0.0, 3.11.7, 3.11.6, 3.11.5, 3.11.4, 3.11.3, 3.11.2, 3.11.1, 3.11.0, 3.10.1, 3.10.0, 3.9.0, 3.8.0, 3.7.4, 3.7.3, 3.7.2, 3.7.1, 3.7.0, 3.6.4, 3.6.3, 3.6.2, 3.6.1, 3.6.0, 3.5.0, 3.4.0, 3.3.0, 3.2.2, 3.2.1, 3.2.0, 3.1.1, 3.1.0, 3.0.0, 2.0.3, 2.0.2, 2.0.1, 2.0.0, 1.5.3, 1.5.2, 1.5.1, 1.5.0, 1.4.3, 1.4.2, 1.4.1, 1.4.0, 1.3.1, 1.3.0, 1.2.0, 1.1.0, 1.0.5, 1.0.4, 1.0.3, 1.0.2, 0.4.3, 0.4.2, 0.4.1, 0.4.0, 0.3.5, 0.3.4, 0.3.3, 0.3.2, 0.3.1, 0.3.0, 0.2.0, 0.1.0
```

Result: CI dependency defect fixed by switching the dev extra and workflow
installer to `cyclonedx-bom>=4.0` while preserving the working
`python3 -m cyclonedx_py environment` invocation.

### Verification: Post-Correction Local Build and SBOM

Command:

```sh
rm -rf .phase1-b-venv dist build && python3 -m venv .phase1-b-venv
.phase1-b-venv/bin/python -m pip install --upgrade pip build twine cyclonedx-bom
VERSION=$(.phase1-b-venv/bin/python -c 'import tomllib; print(tomllib.load(open("pyproject.toml","rb"))["project"]["version"])')
printf 'VERSION=%s\n' "$VERSION"
.phase1-b-venv/bin/python -m build
.phase1-b-venv/bin/python -m twine check --strict dist/*.whl dist/*.tar.gz
.phase1-b-venv/bin/python -m cyclonedx_py environment --pyproject pyproject.toml --sv 1.5 --output-format json --output-file "dist/ecli-editor-${VERSION}.cdx.json" --validate
(cd dist && sha256sum "ecli-editor-${VERSION}.cdx.json" > "ecli-editor-${VERSION}.cdx.json.sha256")
cat "dist/ecli-editor-${VERSION}.cdx.json.sha256"
python3 - <<'PY'
import json
from pathlib import Path
p = Path('dist/ecli-editor-0.1.0.cdx.json')
d = json.loads(p.read_text())
print('bomFormat:', d.get('bomFormat'))
print('specVersion:', d.get('specVersion'))
print('components:', len(d.get('components', [])))
PY
```

Output:

```text
VERSION=0.1.0
Successfully built ecli_editor-0.1.0.tar.gz and ecli_editor-0.1.0-py3-none-any.whl
Checking dist/ecli_editor-0.1.0-py3-none-any.whl: PASSED
Checking dist/ecli_editor-0.1.0.tar.gz: PASSED
dcd70c111a9b1bf96ed21b686b12f043b2dd3c58494c35b6c333124ecb053e87  ecli-editor-0.1.0.cdx.json
bomFormat: CycloneDX
specVersion: 1.5
components: 60
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
```

Result: passed.

### Verification: Post-Correction Workflow and Smoke Checks

Command:

```sh
python3 -m pytest tests/test_smoke.py -v
python3 - <<'PY'
from pathlib import Path
import yaml
for path in [Path('.github/workflows/release.yml')]:
    with path.open('r', encoding='utf-8') as f:
        yaml.safe_load(f)
    print(f'OK {path}')
PY
grep -n "id-token" .github/workflows/release.yml || true
grep -n "cyclonedx-bom\|cyclonedx_py\|ecli-editor-.*cdx\|python-sbom" .github/workflows/release.yml pyproject.toml docs/release/release-process.md
git diff --check
```

Output:

```text
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

============================== 2 passed in 0.02s ===============================
OK .github/workflows/release.yml
.github/workflows/release.yml:34:          python3 -m pip install --user cyclonedx-bom
.github/workflows/release.yml:35:          python3 -m cyclonedx_py environment \
.github/workflows/release.yml:39:            --output-file "dist/ecli-editor-${VERSION}.cdx.json" \
.github/workflows/release.yml:42:          sha256sum "ecli-editor-${VERSION}.cdx.json" > "ecli-editor-${VERSION}.cdx.json.sha256"
.github/workflows/release.yml:58:          name: python-sbom
.github/workflows/release.yml:337:            `ecli-editor-<version>.cdx.json`, plus a SHA256 sidecar.
.github/workflows/release.yml:339:            The SBOM is generated by the `cyclonedx-bom` package through the
.github/workflows/release.yml:340:            `cyclonedx_py` module in CycloneDX JSON schema version 1.5.
pyproject.toml:77:    "cyclonedx-bom>=4.0",
docs/release/release-process.md:98:dist/ecli-editor-<version>.cdx.json
docs/release/release-process.md:99:dist/ecli-editor-<version>.cdx.json.sha256
docs/release/release-process.md:102:The SBOM is generated with the `cyclonedx-bom` Python distribution, invoked as
docs/release/release-process.md:103:`python3 -m cyclonedx_py environment`, in JSON format and CycloneDX schema
```

Result: passed. The `id-token` grep and `git diff --check` produced empty
output.

## Workstream C - Windows Portable EXE + NSIS Installer

Timestamp: 2026-05-10T05:53:16+02:00

Branch: `feat/phase1-windows-dual-artifacts`

Base commit:

```text
73b4914
```

### Verification: Windows Tooling Boundary

Command:

```sh
command -v pwsh || true; command -v makensis || true
```

Output:

```text
```

Result: host boundary recorded. This Linux workstation does not have PowerShell
or NSIS, so the real Windows PyInstaller/NSIS build and Programs & Features
registry assertion are delegated to `windows-latest` CI.

### Verification: Single Windows Packaging Script

Command:

```sh
find scripts -maxdepth 1 -name '*windows*.ps1' -print | sort
```

Output:

```text
scripts/build-and-package-windows.ps1
```

Result: passed. The duplicate `scripts/build_pyinstaller_windows.ps1` was
removed after merging its superior root/build-dir and strict-output behavior
into the Makefile-wired script.

### Verification: Workflow YAML Parse

Command:

```sh
python3 - <<'PY'
from pathlib import Path
import yaml
for path in [Path('.github/workflows/windows-installer.yml'), Path('.github/workflows/windows-validate.yml'), Path('.github/workflows/release.yml')]:
    with path.open('r', encoding='utf-8') as f:
        yaml.safe_load(f)
    print(f'OK {path}')
PY
```

Output:

```text
OK .github/workflows/windows-installer.yml
OK .github/workflows/windows-validate.yml
OK .github/workflows/release.yml
```

Result: passed.

### Verification: Makefile Windows Package Dry Run

Command:

```sh
make -n package-windows
```

Output:

```text
rm -rf build/ dist/ .pytest_cache/ .ruff_cache/ .mypy_cache/ __pycache__
find . -type d -name "__pycache__" -exec rm -rf {} +
find . -type f -name "*.pyc" -delete
echo "--> Intermediate build artifacts cleaned."
pwsh -File ./scripts/build-and-package-windows.ps1
make package-windows-assert
make[1]: Entering directory '/home/ssb/Code/Ecli/ecli'
test -n "0.1.0" || (echo "WIN_PKG_VERSION empty (pyproject.toml)"; exit 1)
scripts/verify-artifact.sh "releases/0.1.0/ecli_0.1.0_win_x86_64.exe"
scripts/verify-artifact.sh "releases/0.1.0/ecli_0.1.0_win_x86_64_setup.exe"
echo "--> OK: releases/0.1.0/ecli_0.1.0_win_x86_64.exe"
echo "--> OK: releases/0.1.0/ecli_0.1.0_win_x86_64.exe.sha256"
echo "--> OK: releases/0.1.0/ecli_0.1.0_win_x86_64_setup.exe"
echo "--> OK: releases/0.1.0/ecli_0.1.0_win_x86_64_setup.exe.sha256"
make[1]: Leaving directory '/home/ssb/Code/Ecli/ecli'
```

Result: passed. The package target asserts both Windows artifacts.

### Verification: Makefile Windows Contract Dry Run

Command:

```sh
make -n validate-windows-contract
```

Output:

```text
test -n "0.1.0" || (echo "WIN_PKG_VERSION empty (pyproject.toml)"; exit 1)
scripts/verify-artifact.sh "releases/0.1.0/ecli_0.1.0_win_x86_64.exe"
scripts/verify-artifact.sh "releases/0.1.0/ecli_0.1.0_win_x86_64_setup.exe"
echo "--> OK: releases/0.1.0/ecli_0.1.0_win_x86_64.exe"
echo "--> OK: releases/0.1.0/ecli_0.1.0_win_x86_64.exe.sha256"
echo "--> OK: releases/0.1.0/ecli_0.1.0_win_x86_64_setup.exe"
echo "--> OK: releases/0.1.0/ecli_0.1.0_win_x86_64_setup.exe.sha256"
echo "--> OK: Windows contract"
```

Result: passed. The simpler path was chosen: extend
`validate-windows-contract` through `package-windows-assert` rather than adding
a parallel installer-only target.

### Verification: Dual Artifact Contract with Generated Test Files

Command:

```sh
set -e
version=$(python3 -c 'import pathlib, tomllib; print(tomllib.loads(pathlib.Path("pyproject.toml").read_text())["project"]["version"])')
dir="releases/$version"
portable="ecli_${version}_win_x86_64.exe"
installer="ecli_${version}_win_x86_64_setup.exe"
printf 'portable-test-artifact\n' > "$dir/$portable"
printf 'installer-test-artifact\n' > "$dir/$installer"
(cd "$dir" && sha256sum "$portable" > "$portable.sha256" && sha256sum "$installer" > "$installer.sha256")
printf 'WIN_ARCH=x86_64\nWIN_PORTABLE_FILENAME=%s\nWIN_INSTALLER_FILENAME=%s\n' "$portable" "$installer" > "$dir/.win.env"
make validate-windows-contract
file "$dir/$portable.sha256" "$dir/$installer.sha256"
hexdump -C "$dir/$portable.sha256"
hexdump -C "$dir/$installer.sha256"
rm -f "$dir/$portable" "$dir/$portable.sha256" "$dir/$installer" "$dir/$installer.sha256" "$dir/.win.env"
```

Output:

```text
ecli_0.1.0_win_x86_64.exe: OK
ecli_0.1.0_win_x86_64_setup.exe: OK
--> OK: releases/0.1.0/ecli_0.1.0_win_x86_64.exe
--> OK: releases/0.1.0/ecli_0.1.0_win_x86_64.exe.sha256
--> OK: releases/0.1.0/ecli_0.1.0_win_x86_64_setup.exe
--> OK: releases/0.1.0/ecli_0.1.0_win_x86_64_setup.exe.sha256
--> OK: Windows contract
releases/0.1.0/ecli_0.1.0_win_x86_64.exe.sha256:       ASCII text
releases/0.1.0/ecli_0.1.0_win_x86_64_setup.exe.sha256: ASCII text
00000000  30 62 63 39 34 39 31 63  64 34 35 33 66 37 30 36  |0bc9491cd453f706|
00000010  31 32 33 33 30 61 35 35  32 63 38 33 64 66 30 38  |12330a552c83df08|
00000020  39 37 62 32 38 39 34 62  66 37 32 39 36 62 37 39  |97b2894bf7296b79|
00000030  36 65 61 34 61 37 61 32  32 62 30 33 64 62 62 30  |6ea4a7a22b03dbb0|
00000040  20 20 65 63 6c 69 5f 30  2e 31 2e 30 5f 77 69 6e  |  ecli_0.1.0_win|
00000050  5f 78 38 36 5f 36 34 2e  65 78 65 0a              |_x86_64.exe.|
0000005c
00000000  35 63 62 30 32 64 36 37  62 63 64 63 63 62 32 32  |5cb02d67bcdccb22|
00000010  39 66 61 30 65 32 61 37  37 36 32 36 61 64 35 35  |9fa0e2a77626ad55|
00000020  36 37 32 65 30 34 65 61  30 38 38 66 33 34 30 61  |672e04ea088f340a|
00000030  65 32 61 63 39 38 66 31  33 61 63 65 65 62 66 62  |e2ac98f13aceebfb|
00000040  20 20 65 63 6c 69 5f 30  2e 31 2e 30 5f 77 69 6e  |  ecli_0.1.0_win|
00000050  5f 78 38 36 5f 36 34 5f  73 65 74 75 70 2e 65 78  |_x86_64_setup.ex|
00000060  65 0a                                             |e.|
00000062
```

Result: passed. Test artifacts were removed after validation.

### Verification: PyInstaller Spec Syntax

Command:

```sh
python3 -m py_compile packaging/pyinstaller/ecli.spec
```

Output:

```text
```

Result: passed.

### Verification: Existing Smoke Tests

Command:

```sh
python3 -m pytest tests/test_smoke.py -v
```

Output:

```text
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

============================== 2 passed in 0.02s ===============================
```

Result: passed.

### Verification: Diff Hygiene

Command:

```sh
git diff --check
```

Output:

```text
```

Result: passed.

### Windows-Only Verification Boundary

The following checks are implemented in `.github/workflows/windows-installer.yml`
and `.github/workflows/windows-validate.yml`, but were not executed on this
Linux workstation:

- Build the portable PyInstaller EXE from `packaging/pyinstaller/ecli.spec`.
- Build the unsigned NSIS installer that bundles the portable EXE.
- Verify both EXEs are non-empty and return an Authenticode status without
  running the portable curses application.
- Verify both `.sha256` sidecars are ASCII, BOM-free, LF-terminated, and match
  `Get-FileHash`.
- Run `make validate-windows-contract` against the real Windows-built outputs.
- Silent-install the NSIS installer and assert Programs & Features registry
  values under `HKLM\Software\Microsoft\Windows\CurrentVersion\Uninstall\ECLI`,
  including `DisplayName`, `DisplayVersion`, `Publisher`, `InstallLocation`,
  `UninstallString`, and the registered uninstaller.

No PyPI publish, tag push, GitHub Release creation, or real GitHub Release asset
upload was performed.

### CI Correction: NSIS Relative INPUT_EXE Resolution

First PR CI attempt: 1 failure. The Windows validate workflow built the
PyInstaller portable EXE, then NSIS failed to resolve the relative
`INPUT_EXE=releases\...` path from the NSIS script context. The fix is to pass
absolute `OUTFILE` and `INPUT_EXE` defines to `makensis` while preserving the
same release artifact basenames.

Command:

```sh
gh run view 25619232222 --job 75202713888 --log
```

Relevant output excerpt:

```text
validate	Build Windows artifacts	2026-05-10T03:57:36.4758623Z OK  Portable executable: releases\0.1.0\ecli_0.1.0_win_x86_64.exe
validate	Build Windows artifacts	2026-05-10T03:57:36.4765009Z ==> Writing portable SHA256...
validate	Build Windows artifacts	2026-05-10T03:57:36.5482125Z ==> Building NSIS installer...
validate	Build Windows artifacts	2026-05-10T03:57:36.6157253Z Command line defined: "VERSION=0.1.0"
validate	Build Windows artifacts	2026-05-10T03:57:36.6157955Z Command line defined: "OUTFILE=releases\0.1.0\ecli_0.1.0_win_x86_64_setup.exe"
validate	Build Windows artifacts	2026-05-10T03:57:36.6158458Z Command line defined: "INPUT_EXE=releases\0.1.0\ecli_0.1.0_win_x86_64.exe"
validate	Build Windows artifacts	2026-05-10T03:57:36.6158893Z Processing config: C:\Program Files (x86)\NSIS\nsisconf.nsh
validate	Build Windows artifacts	2026-05-10T03:57:36.6224026Z Processing script file: "D:\a\ecli\ecli\packaging\windows\nsis\ecli.nsi" (ACP)
validate	Build Windows artifacts	2026-05-10T03:57:36.7124262Z File: "releases\0.1.0\ecli_0.1.0_win_x86_64.exe" -> no files found.
validate	Build Windows artifacts	2026-05-10T03:57:36.7125141Z Usage: File [/nonfatal] [/a] ([/r] [/x filespec [...]] filespec [...] |
validate	Build Windows artifacts	2026-05-10T03:57:36.7125814Z    /oname=outfile one_file_only)
validate	Build Windows artifacts	2026-05-10T03:57:36.7126624Z Error in script "D:\a\ecli\ecli\packaging\windows\nsis\ecli.nsi" on line 51 -- aborting creation process
validate	Build Windows artifacts	2026-05-10T03:57:36.7204222Z ERR Installer not produced at releases\0.1.0\ecli_0.1.0_win_x86_64_setup.exe
validate	Build Windows artifacts	2026-05-10T03:57:36.7371401Z make: *** [Makefile:793: package-windows] Error 2
validate	Build Windows artifacts	2026-05-10T03:57:36.8291801Z ##[error]Process completed with exit code 1.
```

### Verification: Post-Correction Makefile Windows Package Dry Run

Command:

```sh
make -n package-windows
```

Output:

```text
rm -rf build/ dist/ .pytest_cache/ .ruff_cache/ .mypy_cache/ __pycache__
find . -type d -name "__pycache__" -exec rm -rf {} +
find . -type f -name "*.pyc" -delete
echo "--> Intermediate build artifacts cleaned."
pwsh -File ./scripts/build-and-package-windows.ps1
make package-windows-assert
make[1]: Entering directory '/home/ssb/Code/Ecli/ecli'
test -n "0.1.0" || (echo "WIN_PKG_VERSION empty (pyproject.toml)"; exit 1)
scripts/verify-artifact.sh "releases/0.1.0/ecli_0.1.0_win_x86_64.exe"
scripts/verify-artifact.sh "releases/0.1.0/ecli_0.1.0_win_x86_64_setup.exe"
echo "--> OK: releases/0.1.0/ecli_0.1.0_win_x86_64.exe"
echo "--> OK: releases/0.1.0/ecli_0.1.0_win_x86_64.exe.sha256"
echo "--> OK: releases/0.1.0/ecli_0.1.0_win_x86_64_setup.exe"
echo "--> OK: releases/0.1.0/ecli_0.1.0_win_x86_64_setup.exe.sha256"
make[1]: Leaving directory '/home/ssb/Code/Ecli/ecli'
```

Result: passed.
