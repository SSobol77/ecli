## Quick build from source (Linux)

```bash
# 1) Clone
git clone https://github.com/SSobol77/ecli
cd ecli

# 2) Dependencies
pipx install uv
uv sync

# 3) Run from source
uv run python -m ecli --help

# 4) Build binary
bash scripts/build_pyinstaller_linux.sh

# 5) Package .deb/.rpm
bash scripts/package_fpm_deb.sh 0.1.0
bash scripts/package_fpm_rpm.sh 0.1.0
```
