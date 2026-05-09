<!--
Filename: BUILD_SYSTEM.md
Project:  ECLI
License:  MIT
Author:   Siergej Sobolewski
Copyright: (c) 2026 Siergej Sobolewski
-->

# ECLI Multi-Platform Build System

## Overview

This document describes the enhanced Makefile-based build system for ECLI, supporting multiple distribution formats and operating systems.

**Supported Platforms:**

- **Linux**: Debian/Ubuntu (.deb), Fedora/RHEL/Rocky (.rpm), AppImage, Snap, tar.gz
- **FreeBSD**: .pkg packages (native, chroot, CI)
- **macOS**: DMG packages
- **Windows**: NSIS installers (.exe)
- **Python**: PyPI distribution (wheel + source)

---

## Quick Start

### Display help and available options

```bash
make help
```

### Display system information

```bash
make sysinfo
```

### View all built artifacts

```bash
make show-artifacts
```

---

## Build Targets by Distribution

### Python Package (PyPI)

Build distribution packages for PyPI:

```bash
make package-pypi          # Builds wheel + source distribution
make show-python-artifacts # List Python packages
make publish-pypi          # Publish to PyPI (requires credentials)
```

**Requirements:**

- Python 3.8+
- `build` package: `pip install build`
- PyPI credentials in `~/.pypirc` or `PYPI_TOKEN` env var

**Artifacts:**

- `dist/ecli-{VERSION}-py3-none-any.whl`
- `dist/ecli-{VERSION}.tar.gz`

---

### Debian/Ubuntu Packages

#### Local build

```bash
make package-deb           # Requires dpkg, fakeroot, debhelper
make show-deb-artifacts
make release-deb           # Publish to GitHub Release
```

#### Docker-based build (Recommended)

```bash
make package-deb-docker    # Builds in Debian container
make show-deb-artifacts
```

**Requirements:**

- Docker (for container builds)
- dpkg, debhelper, fakeroot (for local builds)

**Artifacts:**

- `releases/{VERSION}/ecli_{VERSION}_amd64.deb`
- `releases/{VERSION}/ecli_{VERSION}_amd64.deb.sha256`

---

### Fedora/RHEL/Rocky/CentOS Packages

#### Local build

```bash
make package-rpm           # Requires rpm-build, spectool
make show-rpm-artifacts
make release-rpm           # Publish to GitHub Release
```

#### Docker-based build (Recommended)

```bash
make package-rpm-docker    # Builds in AlmaLinux 9 container
make show-rpm-artifacts
```

**Requirements:**

- Docker (for container builds)
- rpm-build, spectool (for local builds)

**Artifacts:**

- `releases/{VERSION}/ecli_{VERSION}_amd64.rpm`
- `releases/{VERSION}/ecli_{VERSION}_amd64.rpm.sha256`

---

### AppImage (Cross-Distro Linux)

Build a portable AppImage for any Linux distribution:

```bash
make package-appimage      # Requires appimagetool
make show-appimage-artifacts
make release-appimage      # Publish to GitHub Release
```

**Requirements:**

- AppImageKit tools: <https://github.com/AppImage/AppImageKit>
- Install: Download `appimagetool` and add to PATH

**Benefits:**

- Works on any Linux distribution
- No package dependencies
- Single executable
- Auto-updatable

**Artifacts:**

- `releases/{VERSION}/ecli_{VERSION}_Linux_{ARCH}.AppImage`
- `releases/{VERSION}/ecli_{VERSION}_Linux_{ARCH}.AppImage.sha256`

---

### Snap Packages (Optional)

Build a Snap package (requires Snapcraft):

```bash
make package-snap          # Requires snapcraft
make show-snap-artifacts
make release-snap          # Publish to Snap Store
```

**Requirements:**

- Snapcraft: `sudo snap install snapcraft --classic`
- `snapcraft.yaml` in project root

**Note:** Snap building is optional; create `snapcraft.yaml` to enable.

**Artifacts:**

- `releases/{VERSION}/ecli_{VERSION}_amd64.snap`

---

### Linux Archives

Build tar.gz archives for manual installation:

```bash
make package-tar-linux     # Creates portable tar.gz
make show-tar-artifacts
```

**Artifacts:**

- `releases/{VERSION}/ecli_{VERSION}_Linux_{ARCH}.tar.gz`
- `releases/{VERSION}/ecli_{VERSION}_Linux_{ARCH}.tar.gz.sha256`

---

### FreeBSD Packages

#### Option 1: Native build on FreeBSD host

```bash
make package-freebsd       # Native build
make show-freebsd-artifacts
make release-freebsd       # Publish to GitHub Release
```

#### Option 2: Chroot build (requires root on FreeBSD)

```bash
make package-freebsd-chroot # Creates clean 14.3 rootfs
make show-freebsd-artifacts
```

#### Option 3: Via FreeBSD Ports (requires root)

```bash
make package-freebsd-port  # Uses local port skeleton
make show-freebsd-artifacts
```

#### Option 4: GitHub Actions CI

```bash
make package-freebsd-ci    # Triggers FreeBSD VM in GitHub Actions
```

**Requirements:**

- FreeBSD 14.x or later
- Root access (for chroot/port builds)
- GitHub Actions (for CI builds)

**Artifacts:**

- `releases/{VERSION}/ecli_{VERSION}_amd64.pkg`
- `releases/{VERSION}/ecli_{VERSION}_amd64.pkg.sha256`

---

### macOS Packages

Build a DMG installer for macOS:

```bash
make package-macos         # Requires Xcode tools on macOS
make show-macos-artifacts
make release-macos         # Publish to GitHub Release
```

**Requirements:**

- macOS 12+
- Xcode Command Line Tools: `xcode-select --install`

**Artifacts:**

- `releases/{VERSION}/ecli_{VERSION}_macos_{ARCH}.dmg`
- `releases/{VERSION}/ecli_{VERSION}_macos_{ARCH}.dmg.sha256`

---

### Windows Packages

Build a Windows installer (NSIS):

```bash
# Run in PowerShell on Windows
make package-windows       # Requires PowerShell 7+
make show-windows-artifacts
make release-windows       # Publish to GitHub Release
```

**Requirements:**

- Windows 10/11 x64
- PowerShell 7+
- NSIS installer

**Artifacts:**

- `releases/{VERSION}/ecli_{VERSION}_win_x64.exe`
- `releases/{VERSION}/ecli_{VERSION}_win_x64.exe.sha256`

---

## Meta Targets (Build Multiple Packages)

### Build all packages

```bash
make package-all           # Requires all native tools and Docker
```

Builds: Python, Debian, Fedora, AppImage, FreeBSD, macOS, Windows

**Note:** Requires native build tools on all platforms; intended for CI/CD or multi-platform environments.

### Build all Linux packages

```bash
make package-linux         # Uses Docker + native tools
```

Builds: Debian (.deb), Fedora (.rpm), AppImage, tar.gz

### Build only Docker-based packages

```bash
make package-docker        # Fastest; uses containers
```

Builds: Debian (.deb), Fedora (.rpm)

### Build desktop packages

```bash
make package-desktop       # Requires macOS and/or Windows native tools
```

Builds: macOS (.dmg), Windows (.exe)

---

## Release Management

### Publish all packages to GitHub Release

```bash
make publish-all           # Creates tag, release, uploads all artifacts
```

**Requirements:**

- GitHub CLI (`gh`) installed and authenticated
- `gh auth login` to authorize

**Steps:**

1. Ensures git tag `v{VERSION}` exists
2. Creates GitHub Release with version info
3. Uploads all artifacts with checksums
4. Supports multiple re-uploads with `--clobber`

### Publish individual platform releases

```bash
make release-deb           # Publish Debian artifacts
make release-rpm           # Publish Fedora artifacts
make release-appimage      # Publish AppImage
make release-freebsd       # Publish FreeBSD
make release-macos         # Publish macOS
make release-windows       # Publish Windows
make publish-pypi          # Publish to PyPI
```

---

## Artifact Management

### View all artifacts

```bash
make show-artifacts        # Summary of all built packages
```

### View artifacts by platform

```bash
make show-python-artifacts     # PyPI packages
make show-deb-artifacts        # Debian packages
make show-rpm-artifacts        # Fedora packages
make show-appimage-artifacts   # AppImage
make show-snap-artifacts       # Snap packages
make show-tar-artifacts        # Linux archives
make show-freebsd-artifacts    # FreeBSD packages
make show-macos-artifacts      # macOS packages
make show-windows-artifacts    # Windows packages
```

---

## Build System Features

### Automatic Architecture Detection

- Detects system architecture (x86_64, arm64, etc.)
- Normalizes architecture names across platforms
- Includes architecture in package names

### Version Management

- Reads version from `pyproject.toml` automatically
- Consistent versioning across all packages
- Version available as `$(PACKAGE_VERSION)` variable

### Checksum Generation

- Automatically generates SHA256 checksums
- Files: `{PACKAGE}.sha256`
- Enables verification of downloaded packages

### Directory Organization

- All artifacts stored in `releases/{VERSION}/`
- Clean separation by platform
- Easy to identify missing artifacts

### Help System

```bash
make help       # Comprehensive help with all options
make sysinfo    # System information and tool availability
```

---

## System Requirements by Platform

| Platform | Tool | Requirements |
|----------|------|--------------|
| Debian/Ubuntu | Local | dpkg, debhelper, fakeroot |
| Debian/Ubuntu | Docker | Docker |
| Fedora/RHEL | Local | rpm-build, spectool |
| Fedora/RHEL | Docker | Docker |
| AppImage | - | appimagetool |
| Snap | - | snapcraft |
| FreeBSD | Native | FreeBSD 14.x, Python 3.11+ |
| FreeBSD | Chroot | FreeBSD host, root access |
| macOS | - | macOS 12+, Xcode tools |
| Windows | - | Windows 10/11, PowerShell 7+ |
| PyPI | - | Python 3.8+, build package |
| GitHub Release | - | GitHub CLI (gh) |

---

## Workflow Examples

### Build and release for Linux distributions

```bash
make package-linux         # Build all Linux packages (Docker)
make publish-all          # Publish to GitHub Release
```

### Build for a single platform

```bash
make package-deb-docker   # Debian package
make release-deb          # Release to GitHub
```

### Prepare for PyPI release

```bash
make package-pypi         # Build wheel + sdist
make show-python-artifacts # Verify artifacts
make publish-pypi         # Publish to PyPI
```

### Build everything (CI/CD environment)

```bash
make clean                # Clean old artifacts
make package-all          # Build all platforms
make publish-all          # Release everything
```

---

## Troubleshooting

### Missing tools

```bash
make sysinfo              # Shows which tools are missing
```

### Docker not available (for Linux builds)

- Install Docker: <https://docs.docker.com/install/>
- Or use local build: `make package-deb` (requires native tools)

### Permission denied on FreeBSD chroot

- Requires root: `sudo make package-freebsd-chroot`

### GitHub Release publish fails

- Check authentication: `gh auth login`
- Verify token has `repo` scope

### Architecture not recognized

- Check `make sysinfo` output
- Edit `ARCH_NORMALIZED` in Makefile if needed

---

## Advanced Configuration

### Custom version

```bash
make package-pypi PYPI_VERSION=1.0.0
```

### Custom release directory

```bash
make package-deb RELEASE_DIR=custom/path
```

### Custom Python interpreter

```bash
make install PYTHON=python3.11
```

### Custom uv installation

```bash
make install UV=/path/to/uv
```

---

## CI/CD Integration

### GitHub Actions

All release targets automatically:

1. Create git tag `v{VERSION}` if missing
2. Create GitHub Release if missing
3. Upload artifacts with checksums
4. Support re-uploading with `--clobber`

### Manual Release Process

```bash
# 1. Build packages
make clean && make package-linux

# 2. Verify artifacts
make show-artifacts

# 3. Create release and upload
make publish-all
```

---

## License & Attribution

Build system designed for ECLI project. Based on pypa/build, PyInstaller, and standard distribution tools.

For issues or improvements, visit: <https://github.com/SSobol77/ecli>
