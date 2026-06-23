# ECLI runtime logs

This directory is a volatile local runtime evidence buffer.

Rules:

- Do not commit runtime log files.
- Keep only `.gitkeep` and this README under version control.
- Run `scripts/clean_logs.sh` before manual smoke tests and debug sessions.
- Agent reports must be based on fresh logs from the current run only.
- Stale logs from previous runs are not valid evidence.
- Tests are regression guards; manual TUI behavior plus current logs are the acceptance source for runtime issues.

Expected current-run files may include:

- `editor.log`
- rotated local log files during runtime

All runtime log artifacts are ignored by Git.