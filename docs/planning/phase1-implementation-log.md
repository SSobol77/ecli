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
grep -n "cyclonedx-py\|ecli-editor-.*cdx\|python-sbom\|CycloneDX" .github/workflows/release.yml pyproject.toml docs/release/release-process.md
```

Output:

```text
.github/workflows/release.yml:34:          python3 -m pip install --user cyclonedx-py
.github/workflows/release.yml:39:            --output-file "dist/ecli-editor-${VERSION}.cdx.json" \
.github/workflows/release.yml:42:          sha256sum "ecli-editor-${VERSION}.cdx.json" > "ecli-editor-${VERSION}.cdx.json.sha256"
.github/workflows/release.yml:58:          name: python-sbom
.github/workflows/release.yml:336:            This release includes a CycloneDX SBOM for the Python distribution:
.github/workflows/release.yml:337:            `ecli-editor-<version>.cdx.json`, plus a SHA256 sidecar.
.github/workflows/release.yml:339:            The SBOM is generated by `cyclonedx-py` in CycloneDX JSON schema
pyproject.toml:77:    "cyclonedx-py>=4.0",
docs/release/release-process.md:95:Release builds emit a CycloneDX SBOM for the Python distribution:
docs/release/release-process.md:98:dist/ecli-editor-<version>.cdx.json
docs/release/release-process.md:99:dist/ecli-editor-<version>.cdx.json.sha256
docs/release/release-process.md:102:The SBOM is generated with `cyclonedx-py environment` in JSON format and
docs/release/release-process.md:103:CycloneDX schema version 1.5. The workflow invokes `cyclonedx-py` with
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

Result: passed. `cyclonedx-py environment --validate` validates the generated
SBOM before writing output.

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
