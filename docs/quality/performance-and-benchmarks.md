<!--
Filename: docs/quality/performance-and-benchmarks.md
Project:  ECLI
License:  MIT
Author:   Siergej Sobolewski
Copyright: (c) 2026 Siergej Sobolewski
-->

# Performance and Benchmarks

## Scope

This project currently has no formal benchmark harness committed in the repository.

## Recommended Baseline Benchmarks

- startup time to first interactive frame
- redraw latency under large file navigation
- key input to render latency under active lint/ai background tasks

## Policy

- Performance metrics are non-release-blocking until baseline exists.
- After baseline establishment, regressions above agreed threshold must be reviewed.
