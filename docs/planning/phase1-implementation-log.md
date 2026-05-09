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
