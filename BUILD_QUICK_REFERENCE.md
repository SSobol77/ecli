# ECLI Build System Quick Reference

## Most Common Commands

### Show help
```bash
make help              # Complete help and all options
make sysinfo           # System info and available tools
```

### Build packages
```bash
make clean             # Remove all build artifacts
make install           # Install dependencies
make run               # Run from source
```

### Build for distribution

**Linux (Recommended - uses Docker):**
```bash
make package-linux     # Builds .deb, .rpm, AppImage, tar.gz
make show-artifacts    # View all built packages
```

**Individual platforms:**
```bash
make package-deb-docker    # Debian/Ubuntu .deb
make package-rpm-docker    # Fedora/RHEL .rpm
make package-appimage      # AppImage (portable Linux)
make package-pypi          # Python wheel + sdist (for PyPI)
```

**Native builds (must run on target OS):**
```bash
make package-macos         # macOS .dmg (run on macOS)
make package-windows       # Windows .exe (run in PowerShell)
make package-freebsd       # FreeBSD .pkg (run on FreeBSD)
```

### Release to GitHub

**All packages:**
```bash
make publish-all       # Creates tag, release, uploads artifacts
```

**Individual releases:**
```bash
make release-deb       # Release .deb to GitHub
make release-rpm       # Release .rpm to GitHub
make release-appimage  # Release AppImage
make release-macos     # Release macOS .dmg
make release-windows   # Release Windows .exe
make release-freebsd   # Release FreeBSD .pkg
make publish-pypi      # Publish to PyPI
```

### View artifacts

```bash
make show-artifacts              # All packages summary
make show-python-artifacts       # PyPI packages
make show-deb-artifacts          # Debian packages
make show-rpm-artifacts          # Fedora packages
make show-appimage-artifacts     # AppImage
make show-macos-artifacts        # macOS packages
make show-windows-artifacts      # Windows packages
```

---

## Supported Distributions

| Distribution | Package | Command | Docker? |
|---|---|---|---|
| Debian/Ubuntu | .deb | `make package-deb-docker` | ✅ Yes |
| Fedora/RHEL/Rocky | .rpm | `make package-rpm-docker` | ✅ Yes |
| Any Linux | AppImage | `make package-appimage` | - |
| Any Linux | tar.gz | `make package-tar-linux` | - |
| Linux Snap | .snap | `make package-snap` | - |
| FreeBSD | .pkg | `make package-freebsd` | - |
| macOS | .dmg | `make package-macos` | - |
| Windows | .exe | `make package-windows` | - |
| PyPI | wheel + sdist | `make package-pypi` | - |

---

## Typical Release Workflow

```bash
# 1. Build all Linux packages (Docker)
make package-linux

# 2. Verify they were created
make show-artifacts

# 3. (On macOS) Build macOS package
make package-macos

# 4. (On Windows) Build Windows package
make package-windows

# 5. Build Python package for PyPI
make package-pypi

# 6. Publish everything to GitHub and PyPI
make publish-all              # Uploads to GitHub Release
make publish-pypi             # Uploads to PyPI

# 7. Verify releases
make show-artifacts
```

---

## Prerequisites

### For Docker builds (Linux packages)
```bash
# Ubuntu/Debian
sudo apt install docker.io

# Install Docker Desktop on Mac/Windows
```

### For GitHub releases
```bash
# Install GitHub CLI
# https://cli.github.com/

# Authenticate
gh auth login
```

### For PyPI publishing
```bash
# Create account at https://pypi.org
# Create ~/.pypirc with credentials
# Or set PYPI_TOKEN environment variable
```

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Docker not found | Install Docker: https://docs.docker.com/install/ |
| `gh` not found | Install GitHub CLI: https://cli.github.com/ |
| Permission denied | Use `sudo` for FreeBSD chroot builds |
| AppImage not built | Install appimagetool; check `make sysinfo` |
| Release fails | Run `gh auth login` to authenticate |

---

## Environment Variables

```bash
# Override default version (from pyproject.toml)
make PACKAGE_VERSION=1.0.0 package-deb

# Override Python interpreter
make PYTHON=python3.11 install

# Override release directory
make RELEASE_DIR=custom/path package-deb
```

---

See [BUILD_SYSTEM.md](BUILD_SYSTEM.md) for complete documentation.
