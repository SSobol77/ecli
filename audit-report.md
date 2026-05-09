# ECLI Gate 2 Phase 0 Audit Report

Author: Siergej Sobolewski

Date: 2026-05-09
Repository: `/home/ssb/Code/Ecli/ecli`
Remote under review: `https://github.com/SSobol77/ecli`

## Scope

This report covers Step 0 only. No release, packaging, workflow, or runtime
code was changed. The audit read the authoritative documents in the requested
order, then inspected the Makefile, packaging scripts, workflows, version
metadata, and existing contract validator artifacts.

Authoritative order applied:

1. `AGENTS.md`
2. `docs/release/artifact-contract.md`
3. `docs/release/artifact-verification.md`
4. `docs/planning/engineering-plan.md`
5. `docs/planning/execution-sequencing.md`
6. `Makefile`
7. `pyproject.toml`
8. `scripts/build-and-package-*.{sh,ps1}`

## Blocking Observations

The requested implementation cannot safely proceed past Step 0 without
maintainer decisions because several open questions directly change the plan.

1. `docs/release/artifact-contract.md` currently defines the legacy artifact
   naming contract at `docs/release/artifact-contract.md:21-25`. The prompt
   requests replacing that contract with `ecli_<v>_<os>_<arch>.<ext>`. Per the
   priority order, this is an intentional contract change and needs explicit
   maintainer approval before PR #1.
2. The PyPI project name `ecli` is already owned by another account. Local
   verification with `python3 -m pip index versions ecli` returned published
   versions `0.0.23`, `0.0.20`, and `0.0.12`; PyPI JSON metadata reports owner
   `ihgazni` and homepage `https://github.com/ihgazni2/ecli`. This is a
   blocker for issue #30 unless the maintainer owns that PyPI project or chooses
   a different distribution name.
3. GitHub API checks showed zero releases and zero tags for
   `SSobol77/ecli` at audit time, so no legacy GitHub release artifact was found.
   This is evidence for Open Question Q1, but Q1 still requires maintainer
   confirmation because downstream artifacts may exist outside GitHub releases.
4. `src/ecli/__init__.py` is empty, so Q3 is answered as "NO" in the local tree.
   The later PR scope must add the specified `importlib.metadata` version export.
5. Q4 cannot be verified locally from repository files. GitHub protected
   environments are repository settings, not source files. Maintainer input is
   required.

## Confirmed Defects

### B-series Critical Bugs

| ID | Status | Evidence | Impact |
| --- | --- | --- | --- |
| B1 | Confirmed | `Makefile:420` uses `test -f "*.snap" && mv *.snap ... || true`. | The quoted glob never expands and `|| true` masks packaging failure. |
| B2 | Partially confirmed | Literal `\n` appears in `gh release create --notes` for DEB at `Makefile:252-254`, RPM at `Makefile:326-328`, and FreeBSD at `Makefile:581-583`. AppImage `Makefile:387-388`, macOS `Makefile:647-648`, and Windows `Makefile:708-709` currently use single-line notes and do not contain literal `\n`. | Affected release notes render literal backslash-n instead of Markdown paragraphs. |
| B3 | Confirmed | Direct tag creation and push occur in release targets: `Makefile:244-246`, `Makefile:318-320`, `Makefile:383-384`, `Makefile:573-575`, `Makefile:643-644`, `Makefile:704-705`. | Concurrent publish jobs can race on tag creation and push. |
| B4 | Confirmed | `Makefile:457` runs `python -m pip install --user -q . ... || true` inside `package-tar-linux`. | Packaging has a hidden user-environment side effect. |
| B5 | Confirmed | `Makefile:210` defines `package-deb-docker:` without `clean`; `Makefile:287` defines `package-rpm-docker:` without `clean`. | Docker package targets can consume stale intermediates. |

### N-series Naming and Checksum Defects

| ID | Status | Evidence | Impact |
| --- | --- | --- | --- |
| N1 | Confirmed | Current contract uses legacy names at `docs/release/artifact-contract.md:21-25`; Makefile uses `_amd64` at `Makefile:199-202`, `Makefile:276-279`, `Makefile:495-498`, `win_x64` at `Makefile:676-679`, and `Linux_<arch>` at `Makefile:351-354` and `Makefile:451`. | Artifact names are inconsistent across platforms and conflict with the requested hardened schema. |
| N2 | Confirmed | `package-pypi` builds wheel and sdist at `Makefile:157-160`; `package-pypi-assert` checks only `dist/ecli-*.tar.gz` and `dist/ecli-*.whl` at `Makefile:169-174`. | PyPI artifacts have no `.sha256` sidecars. |
| N3 | Confirmed | Assert targets check file existence only: PyPI `Makefile:169-174`, DEB `Makefile:221-225`, RPM `Makefile:295-299`, AppImage `Makefile:369-373`, Snap `Makefile:424-426`, FreeBSD `Makefile:538-542`, macOS `Makefile:628-632`, Windows `Makefile:689-693`. | Stale or tampered checksum sidecars pass release assertions. |

### D-series DRY and Release Flow Defects

| ID | Status | Evidence | Impact |
| --- | --- | --- | --- |
| DRY | Confirmed | Version extraction via `awk -F'"'` is repeated at `Makefile:26`, `Makefile:199`, `Makefile:276`, `Makefile:495`, `Makefile:615`, `Makefile:676`. | Version source is duplicated and more likely to drift. |
| D1 | Confirmed | `package-all` depends on mutually exclusive host targets at `Makefile:719-725`. | A single host cannot build Linux, FreeBSD, macOS, and Windows packages reliably. |
| D2 | Confirmed | `publish-all` unconditionally depends on all release targets and PyPI at `Makefile:747-752`. | Publish orchestration tries to upload artifacts that may not exist on the host. |
| D3 | Confirmed | `MACOS_ARCH ?= $(shell uname -m)` is defined at `Makefile:616`; no `.macos.env` include was found. | The Makefile predicts artifact architecture instead of consuming build evidence. |
| D5 | Confirmed | `clean` deletes `releases/` at `Makefile:137`. | Routine cleanup can destroy release outputs. |
| D6 | Confirmed | `package-snap:` at `Makefile:414` has no `clean` prerequisite. | Snap packaging is inconsistent with peer package targets. |

### Missing Gate 2 Deliverables

The Makefile does not currently define the requested Gate 2 validation targets:

- `validate-pypi-contract`
- `validate-windows-contract`
- `validate-macos-contract`
- `validate-deb-contract`
- `validate-rpm-contract`
- `validate-appimage-contract`
- `validate-freebsd-contract`
- `validate-version-consistency`
- `validate-gate2`

An untracked validator exists at `scripts/validate_artifact_contract.py`, but it
is not wired into `Makefile` targets and has contract mismatches documented below.

## Defects Already Fixed or Not Reproduced

| Item | Result | Evidence |
| --- | --- | --- |
| GitHub releases already published with legacy names | Not reproduced from GitHub API | API checks for `SSobol77/ecli` returned zero releases and zero tags during this audit. Maintainer confirmation is still required for Q1. |
| Q2 pyproject dependency source | Already present | `pyproject.toml` contains `[project.dependencies]` and `[project.optional-dependencies] dev`; PR #3 can move `install` away from `requirements.txt` if approved. |
| Q3 `__version__` export | Not present | `src/ecli/__init__.py` is empty. The required change is still needed. |

## New Defects Discovered

### Critical

1. **PyPI distribution-name ownership blocker**
   - Evidence: `python3 -m pip index versions ecli` reports existing releases;
     PyPI JSON metadata reports the owner as `ihgazni`.
   - Impact: PR #4 must not ship a real `ecli` PyPI publish workflow unless the
     maintainer confirms ownership/control or changes the distribution name.

2. **AppImage script and Makefile artifact paths do not agree**
   - Evidence: `scripts/package_appimage.sh:38` emits
     `dist/ECLI-${VERSION}-x86_64.AppImage`, while `Makefile:351-354` expects
     `releases/<version>/ecli_<version>_Linux_<arch>.AppImage`.
   - Impact: `make package-appimage` can fail even if the AppImage script
     itself produces an artifact.

### High

1. **Current artifact contract contradicts requested canonicalization**
   - Evidence: `docs/release/artifact-contract.md:21-25` defines legacy names.
   - Impact: PR #1 is a contract migration, not only an implementation cleanup.

2. **Checksum sidecar format is inconsistent across platforms**
   - Evidence: `scripts/build-and-package-deb.sh:184-187` writes a coreutils
     `hash filename` sidecar; `scripts/build-and-package-freebsd.sh:371-374`,
     `scripts/build-and-package-macos.sh:162-164`, and
     `scripts/build-and-package-windows.ps1:118` write bare hashes.
   - Impact: A single validator cannot enforce one sidecar contract without
     either normalizing sidecar generation or accepting multiple formats.

3. **Untracked manifest conflicts with current and requested artifact names**
   - Evidence: `releases/manifest.toml` contains legacy `_amd64`, `win_x64`, and
     an AppImage pattern `ecli_<ver>_amd64.AppImage` that matches neither the
     Makefile nor the requested schema.
   - Impact: If this manifest becomes authoritative, validators will reject
     artifacts or silently validate the wrong target.

4. **Validator exit-code contract conflicts with acceptance criteria**
   - Evidence: `scripts/validate_artifact_contract.py` defines checksum failures
     as exit `3` and version mismatch as exit `4`; the prompt requires missing
     sidecar exit `3` and tampered hash exit `4`.
   - Impact: CI tests written to the requested acceptance criteria will fail
     unless the validator contract is adjusted.

### Medium

1. **Release contract documentation is stale about RPM implementation**
   - Evidence: `docs/release/artifact-contract.md:39-41` says no `ecli.spec`
     exists, but `ecli.spec` exists in the repository.
   - Impact: The contract no longer accurately represents the packaging state.

2. **License metadata conflicts**
   - Evidence: `pyproject.toml:61` declares `Apache-2.0`; the repository
     `LICENSE` file is MIT; existing Markdown headers also identify MIT.
   - Impact: Package metadata and repository licensing are inconsistent. This
     is release-significant but outside the requested PR scope unless the
     maintainer explicitly expands scope.

3. **`install` target references a missing requirements file**
   - Evidence: `Makefile:128` runs `uv pip install --system -r requirements.txt`;
     no `requirements.txt` exists in the repository root.
   - Impact: `make install` is currently broken. This aligns with the requested
     PR #3 migration to `pyproject.toml`.

### Low

1. **Non-English comments exist in macOS packaging script**
   - Evidence: `scripts/build-and-package-macos.sh` contains non-English
     comments around the DMG creation flow.
   - Impact: This conflicts with the requested English-only artifact constraint
     if the file is modified later.

## Open Questions Requiring Maintainer Decision

### Q1. Legacy release compatibility

Local GitHub evidence shows no existing tags or releases for `SSobol77/ecli`,
but this does not prove that no preview artifact was distributed elsewhere.

Decision required:

- If legacy artifacts were published to downstream users, defer the naming
  migration to a later milestone and document legacy naming as known debt.
- If not, approve PR #1 to change the artifact contract and all emitters.

### Q2. pyproject dependency authority

Local answer: YES. `pyproject.toml` defines project dependencies and the dev
optional dependency group.

Decision required:

- Confirm that PR #3 may replace the `requirements.txt` install path with
  `uv pip install --system -e ".[dev]"`.

### Q3. `src/ecli.__version__`

Local answer: NO. `src/ecli/__init__.py` is empty.

Decision required:

- Confirm that PR #3 or PR #4 should add the specified
  `importlib.metadata.version("ecli")` based `__version__` export.

### Q4. GitHub protected environments

Local repository files cannot prove whether GitHub Environments such as `pypi`
or `production` are configured.

Decision required:

- If environments exist, provide their exact names for workflow binding.
- If not, approve documenting the recommendation without binding workflows.

### Q5. PyPI project name ownership

Local answer: the public PyPI name `ecli` is already owned by another account.

Decision required:

- If the maintainer controls that PyPI project, confirm the account/control
  model before PR #4.
- If not, choose a different distribution name or block issue #30 Phase 0.

## Recommended Stop Point

Stop here before implementation. The next action should be maintainer review of
the open decisions above, especially Q1 and Q5. Proceeding without those answers
would risk changing a published artifact contract or shipping a CI path for a
PyPI project name not controlled by this repository owner.
