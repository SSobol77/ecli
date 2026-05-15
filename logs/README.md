# Development Logs

This directory is the only allowed location for generated development logs,
dry-run reports, smoke outputs, test evidence, and agent-generated debug artifacts.

Generated files in this directory are ignored by default unless explicitly force-added
for review.

Do not write generated development artifacts to:

- project root
- `.ecli/`
- `.ecli/vmlab/`
- `src/`
- `tests/`
- `tmp/`
- `.tmp/`
- `.cache/`
- `$HOME`
- `/tmp`

Only persistent source files, documentation, tests, and reviewed fixtures should
live outside `logs/`.

Tracked files allowed in this directory:

- `logs/.gitkeep`
- `logs/README.md`
