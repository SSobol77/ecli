<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: docs/architecture/panel-console-stabilization.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->

# Panel Console Stabilization

## Status

Accepted for ECLI 0.2.x.

## Context

ECLI is a curses-based professional TUI workbench and editor with panels. It is
not a full terminal emulator, and its panel stack is not an xterm,
gnome-terminal, or tmux replacement.

Implementing a full PTY terminal emulator inside the ECLI panel stack would
require a materially different subsystem from the existing panel model:

- VT parsing;
- cursor addressing;
- alternate screen handling;
- raw and no-echo terminal modes;
- resize semantics;
- asynchronous stdin/stdout handling;
- job control;
- signal semantics;
- fullscreen terminal application behavior;
- terminal capability negotiation;
- many terminal-specific edge cases.

Those behaviors are out of scope for ECLI 0.2.x. Attempting to ship them inside
the existing curses panel path would create nondeterministic rendering,
input-routing, focus, cancellation, and verification risks.

## Decision

Full PTY terminal emulation is rejected for ECLI 0.2.x.

F11 must move toward an ECLI-owned PySH Console Panel. ECLI owns:

- input line state;
- cursor rendering;
- command history;
- transcript rendering;
- focus behavior;
- close behavior;
- cancellation semantics.

PySH is used as a command execution backend only. It must not be embedded as a
raw interactive shell inside curses for ECLI 0.2.x.

## Scope for v0.2.3

v0.2.3 is a panel-console stabilization release.

It may:

- define this architecture rule;
- replace the fragile F11 PTY path in a later issue;
- add regression coverage in a later issue.

It must not perform the PySH Console Panel implementation as part of this
architecture decision.

## Non-Goals

- no full terminal emulator;
- no VT parser;
- no xterm clone;
- no fullscreen terminal application support;
- no raw interactive PySH embedded inside curses;
- no PySH source migration;
- no monorepo conversion;
- no VMLab scope;
- no QEMU scope;
- no QMP scope;
- no privileged command automation.

## Follow-up Issues

- #89 refactor: replace F11 PTY terminal with PySH Console Panel.
- #90 test: add regression coverage for PySH Console Panel.

## Release Boundary

v0.2.3 must not change the VMLab roadmap and must not modify the VMLab Skeleton
milestone scope. VMLab remains in its own milestone line after v0.2.3.

> Roadmap clarification (recorded for issue #97; the v0.2.x ADR decision above is
> unchanged). The milestone numbering has since been revised, so this note is
> added to prevent misreading. The v0.3.0 milestone is now **Extensions
> Foundation**. The VMLab Skeleton was moved to a later milestone,
> **v0.3.5 — VMLab Skeleton**, and is blocked until the Extensions Foundation
> milestone (v0.3.0) is complete. This clarification changes no technical
> behavior: F11 remains the PySH Console Panel, and a generic PTY terminal
> emulator remains rejected.

## Acceptance Checklist

- full PTY terminal emulator rejected for 0.2.x;
- F11 direction documented as PySH Console Panel;
- PySH is backend only, not raw interactive embedded shell;
- no VMLab/QEMU/QMP scope added;
- no PySH monorepo/source migration;
- follow-up issues #89 and #90 referenced.
