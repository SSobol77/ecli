<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: .claude/PIPELINE.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->

# ECLI Pipeline (prepare-only, maintainer-owned)

License: **GPL-2.0-only**. Supersedes the Apache-2.0 pipeline, which is obsolete.

## Authority model — read first

This is a **prepare-only** runbook. Per `AGENTS.md` Stage 1, the agent (Claude
Code) is restricted to diagnosis, verification, and drafting. **Every mutation
is maintainer-owned and executed manually by you.** Commands are tagged:

- `[AGENT]` — safe for Claude Code: read-only / diagnostic / `--check`.
- `[MAINTAINER]` — you run it by hand. The agent must never run these.

### Agent forbidden list (hard)

The agent must not run: `git add`, `git commit`, `git push`, `git tag`,
`gh pr create`, `gh issue edit/close/comment`, `gh workflow run`,
`gh run rerun/cancel`, `gh release create/upload/edit`, `twine upload`,
`make release-*`, `make publish-*`, or `--apply` on any tool unless you
explicitly instruct it in that turn. If asked, it refuses and prints the command
for you to run.

Git policy: **you commit manually.** Always `git status` before any
`git add`/`git checkout`; verify the current branch before every commit; check
that nothing intended is gitignored (silent staging failures have bitten this
repo before). Squash-merge is the merge strategy.

---

## Stage 0 — Preflight

`[AGENT]` Load the contract, report state only:

```bash
claude -p "Read AGENTS.md, CLAUDE.md, audit-report.md, docs/planning/roadmap.md, \
.claude/drift-register.md, .claude/release-runbook.md. Report: current Stage, the \
AUD findings gating Stage 2, and confirm the project license is GPL-2.0-only. Do \
not modify files. Do not run git, gh, make, or twine."
```

`[MAINTAINER]` Branch + tooling (you own all git):

```bash
git status --short --branch
git switch -c chore/gpl-guard
python3 -m pip install -e ".[release]"
```

`=== GATE 0 ===` Stage = 1, license = GPL-2.0-only confirmed.

---

## Stage A — License invariant (GPL-2.0-only verification)

The tree is already relicensed and clean (Apache scan clean, `GPL-2-only` scan
clean, 262 tests passing). This stage is now a **guard**, not a rewrite.

`[AGENT]` Verify, write a report, never edit:

```bash
python3 tools/license_guard.py --report logs/license-guard.md ; echo "exit=$?"
```

- `exit=0` → invariant holds (all project-owned files GPL-2.0-only, no Apache
  residue, no invalid `GPL-2-only`/`GPL-2.0-or-later` forms). Done.
- `exit=1` → inspect `logs/license-guard.md`:
  - *Missing header* / *Wrong SPDX* → `[MAINTAINER]` run `--apply`:
    ```bash
    python3 tools/license_guard.py --apply --report logs/license-apply.md
    ```
  - *Residual Apache tokens* (UI strings, packaging `LICENSE=`, PKGBUILD
    `license=()`, Nix `meta.license`, README prose, `pyproject` classifier) are
    **format-sensitive and not auto-rewritten** — edit by hand to the correct
    GPL token per format (`GPL-2.0-only`; `gpl2Only` for Nix; `GPL-2.0` for the
    rpm `License:` field; etc.).

`[AGENT]` Validation battery (read-only; report failures by path):

```bash
python3 -m compileall src main.py
python3 - <<'PY'
import tomllib, pathlib
for p in (pathlib.Path("pyproject.toml"), pathlib.Path("config.toml")):
    tomllib.load(p.open("rb")); print("OK:", p)
PY
find scripts tools -type f -name "*.sh" -print0 | xargs -0 -I{} bash -n "{}"
rg -n 'Apache' \
  --glob '!LICENSE' \
  --glob '!LICENCE' \
  --glob '!COPYING*' \
  --glob '!.git/**' \
  --glob '!.venv/**' \
  --glob '!venv/**' \
  --glob '!build/**' \
  --glob '!dist/**' \
  --glob '!releases/**' \
  --glob '!audit-evidence/**' \
  --glob '!logs/**' \
  --glob '!**/__pycache__/**' \
  || echo "no Apache residue"
rg -n 'GPL-2-only|GPL-2\.0-or-later|GPLv2\+|any later version' \
  --glob '!LICENSE' \
  --glob '!LICENCE' \
  --glob '!COPYING*' \
  --glob '!.git/**' \
  --glob '!.venv/**' \
  --glob '!venv/**' \
  --glob '!build/**' \
  --glob '!dist/**' \
  --glob '!releases/**' \
  --glob '!audit-evidence/**' \
  --glob '!logs/**' \
  --glob '!**/__pycache__/**' \
  || echo "no invalid GPL forms"
```

`[MAINTAINER]` Commit if anything changed:

```bash
git status --short
git add -A && git commit -m "chore: enforce GPL-2.0-only license invariant"
```

`=== GATE A ===` Guard green, validation green. You decide the commit.

---

## Stage B — Issues & milestones (agent drafts, you execute)

`[AGENT]` Inspect only:

```bash
gh issue list --state open --limit 100 --json number,title,labels,milestone \
  --jq '.[] | "\(.number)\t\(.milestone.title // "—")\t\(.title)"'
gh api repos/SSobol77/ecli/milestones --jq \
  '.[] | "\(.title)\tclosed=\(.closed_issues)\topen=\(.open_issues)"'
```

`[AGENT]` Produce a disposition table (no writes). Known open set:

| Issue | Milestone | Suggested disposition (you decide) |
|---|---|---|
| `#70` publish v0.2.0 w/ TUI panels | v0.2.0 (m2) | reconcile vs released v0.2.2 → close-as-delivered OR keep as next-tag tracker |
| `#53` reduce `Ecli.py` by service delegation | v0.2.0 (m2) | keep open; **no agent split of `Ecli.py`** (contract-forbidden) |
| `#54` finalize VMLab contracts (`status:contract-drift`) | v0.3.0 (m3) | clear contract-drift BEFORE #55/#56 |
| `#55/#56/#57` VMLab discovery/argv/CLI | v0.3.0 (m3) | keep `status:blocked` until m2 closes; order 54→55→56→57 |

`[MAINTAINER]` Execute the chosen actions yourself (examples):

```bash
gh issue comment 70 --body "v0.2.0 scope delivered in v0.2.2; closing as delivered."
gh issue close 70 --reason completed
gh issue edit 54 --remove-label "status:contract-drift"
gh api -X PATCH repos/SSobol77/ecli/milestones/2 -f state=closed
```

`=== GATE B ===` Issue graph consistent; VMLab order preserved.

---

## Stage C — Windows rendering (Stage-2-LOCKED: inventory + failing test only)

Unchanged by the relicense. Broad rendering rewrites stay locked until
AUD-001/002/003 are closed/waived and you approve Stage 2 (`render-stabilizer.md`).
Windows instability maps to `DRIFT-007` (direct `curses` outside `src/ecli/ui/`)
plus the display-width hypothesis (`len()` vs terminal cell width).

`[AGENT]` Inventory (read-only):

```bash
claude -p "Act as render-stabilizer under Stage 1 rules. Do NOT edit production \
rendering code, do NOT run git/gh. Inventory direct curses/stdscr/refresh/ \
noutrefresh/doupdate outside src/ecli/ui/, all len()-based column/width/wrap/ \
clipping geometry, KEY_RESIZE/SIGWINCH paths, and async callbacks that trigger \
redraw. Classify each baseline|new-drift|needs-review|candidate-Stage2-fix and \
write logs/render-inventory.md."
```

`[AGENT]` One failing test encoding the display-width contract (no production edits):

```bash
claude -p "Write ONE failing pytest tests/test_display_width.py asserting column \
geometry uses terminal display width (CJK=2 cells, zero-width combining=0, \
emoji=2), not len(). xfail with reason 'DRIFT-007 display-width' if no helper \
exists yet. Do not modify src/ecli. Run pytest -k display_width and paste output."
```

> Native-Windows note: the real fix needs a `windows-latest` CI job running
> pty/golden render tests. Debian cannot reproduce the Windows console path.

`=== GATE C ===` Stage 2 unlock is your explicit decision. No GO here ships code.

---

## Stage D — Release (prepare-only; you push the tag)

`[AGENT]` Prepare-only validation:

```bash
python3 -c 'import tomllib;print(tomllib.load(open("pyproject.toml","rb"))["project"]["version"])'
python3 -m pip index versions ecli-editor || true
make validate-gate2
```

`[AGENT]` Emit the prepare-only release summary per `release-runbook.md`.
**No publishing.**

`[MAINTAINER]` The irreversible trigger is yours alone (forward-only — never
yank, never manual PyPI upload):

```bash
git tag v<next>
git push origin v<next>        # triggers release.yml build/publish
gh workflow run freebsd-pkg.yml --ref main -f release_tag=v<next>   # if FreeBSD leg deferred
```

`=== GATE D ===` Forward-only confirmed. Tag push is maintainer-only.

---

## What is intentionally NOT here

- No agent-owned `git commit/push/PR`, no `gh` writes, no `gh workflow run`, no
  tag push, no `gh release`, no `twine upload`. All `[MAINTAINER]`.
- No Apache-2.0 material. License target is GPL-2.0-only, project-owned code
  only; third-party Apache-2.0 code is never relabeled as project-owned.
