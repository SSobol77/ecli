<!--
SPDX-License-Identifier: Apache-2.0

Project: Ecli
File: docs/quality/performance-and-benchmarks.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the Apache License, Version 2.0.
See the LICENSE file in the project root for full license text.
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
