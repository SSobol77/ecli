<!--
SPDX-License-Identifier: Apache-2.0

Project: Ecli
File: README.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the Apache License, Version 2.0.
See the LICENSE file in the project root for full license text.
-->
<p align="center">
  <img src="https://raw.githubusercontent.com/SSobol77/ecli/main/img/logo_m.png" alt="ecli Logo" width="200"/>
</p>

<h1 align="center"><b>ECLI</b></h1>
<p align="center">
  <b>Terminal-First Engineering Operations Workbench</b><br/>
  <i>Panel-driven editor, diagnostics surface, and service foundation for controlled operational workflows</i>
</p>

<p align="center">
  <a href="https://pypi.org/project/ecli-editor/">
    <img alt="PyPI Version" src="https://img.shields.io/pypi/v/ecli-editor?style=flat-square&logo=pypi&logoColor=white">
  </a>
  <a href="https://pypi.org/project/ecli-editor/">
    <img alt="Python Versions" src="https://img.shields.io/pypi/pyversions/ecli-editor?style=flat-square&logo=python&logoColor=white">
  </a>
  <a href="https://github.com/SSobol77/ecli/releases">
    <img alt="Release" src="https://img.shields.io/github/v/release/SSobol77/ecli?include_prereleases&style=flat-square&label=release">
  </a>
  <a href="https://github.com/SSobol77/ecli/blob/main/LICENSE">
    <img alt="License" src="https://img.shields.io/github/license/SSobol77/ecli?style=flat-square">
  </a>
  <a href="https://www.ecli.io">
    <img alt="Website" src="https://img.shields.io/badge/website-ecli.io-blue?style=flat-square">
  </a>
</p>

<p align="center">
  <img alt="Linux" src="https://img.shields.io/badge/Linux-supported-success?style=flat-square&logo=linux&logoColor=white">
  <img alt="macOS" src="https://img.shields.io/badge/macOS-supported-success?style=flat-square&logo=apple&logoColor=white">
  <img alt="FreeBSD" src="https://img.shields.io/badge/FreeBSD-supported-success?style=flat-square&logo=freebsd&logoColor=white">
  <img alt="Windows" src="https://img.shields.io/badge/Windows-supported-success?style=flat-square&logo=windows&logoColor=white">
</p>

---

## 🚀 About ECLI

**ECLI** (Editor CLI) is a terminal-first engineering operations workbench. It
combines a curses-based editor with right-side workflow panels and a typed
service foundation for configuration, project discovery, command-plan previews,
policy checks, audit logging, privileged-action refusal paths, and read-only
system diagnostics.

The v0.2.0 Services Foundation release keeps the editor as the default product
surface while making the new services visible through TUI panels and a minimal
read-only CLI. It does not execute remediation, apply command plans, launch
VMLab runtimes, or perform real privileged operations.

### ✨ Key Features


* 🧠 **AI Code Assistant** - F7 panel for code-generation and refactoring help when a user-provided API key is configured
* 🩺 **System Doctor** - F8 read-only diagnostics panel with structured findings and preview-only remediation plans
* 🧭 **Services Panel** - right-side visibility into the Phase 1 service composition root
* 📋 **Command Plan Preview** - draft plans from eligible diagnostics, exportable as JSON or Markdown without execution
* 📂 **File Manager** - F10 project navigation and file preview workflow
* 🌱 **Git Panel** - F9 repository panel for existing Git workflows
* 🔎 **Diagnostics/Lint** - F4 diagnostics and lint panel
* ❓ **Help** - F1 help panel with current keybindings
* 🌈 **Syntax Highlighting** - terminal highlighting for common source formats
* 📝 **LSP Integration** - Language Server Protocol support where configured
* 🔄 **Cross-Platform Packaging** - PyPI, Linux, FreeBSD, macOS, and Windows release artifacts

---

## 📥 Quick Start

### Fastest Installation (Pre-built Packages)

Download and install a pre-compiled package for your platform:

```bash
# Debian/Ubuntu
sudo apt install ./ecli_0.2.0_linux_x86_64.deb

# Fedora/RHEL/Rocky
sudo dnf install ./ecli_0.2.0_linux_x86_64.rpm

# Windows (PowerShell)
.\ecli_0.2.0_win_x86_64_setup.exe
# Portable alternative: .\ecli_0.2.0_win_x86_64.exe
# See docs/install/windows.md for checksum verification and SmartScreen notes.

# macOS
open ecli_0.2.0_macos_universal2.dmg
# First launch is blocked by Gatekeeper; see docs/install/macos.md
# for the one-time "Open Anyway" or xattr workaround.
```

All packages available at [GitHub Releases](https://github.com/SSobol77/ecli/releases)

### Run from Source

```bash
# Clone the repository
git clone https://github.com/SSobol77/ecli.git
cd ecli

# Install dependencies and run
make install
make run
```

### Install via Python Package Manager

```bash
pip install ecli-editor
```

The Python distribution name is `ecli-editor`; the import package remains
`ecli`, and the installed CLI command remains `ecli`.

---

## 📦 Installation Guide

### Complete Installation Instructions

For detailed platform-specific installation instructions, system dependencies, and troubleshooting, see the [Installation Guide](https://github.com/SSobol77/ecli/blob/main/docs/contributor/install.md).

#### 1. System Dependencies

These dependencies are required for terminal UI, clipboard integration, YAML acceleration, and UTF-8 support.

**Debian/Ubuntu:**
```bash
sudo apt update && sudo apt install \
  libncurses6 libncursesw6 libtinfo6 \
  libncurses-dev libncursesw5-dev \
  ncurses-bin ncurses-term \
  libyaml-dev xclip xsel
```

**Fedora/CentOS/RHEL:**
```bash
sudo dnf install ncurses ncurses-devel libyaml-devel xclip xsel
```

**Arch Linux:**
```bash
sudo pacman -S ncurses libyaml xclip xsel
```

**FreeBSD:**
```bash
sudo pkg install ncurses libyaml xclip xsel
```

**macOS:**
```bash
brew install ncurses libyaml
```

#### 2. Install ECLI

**Option A: Pre-built Packages (Recommended)**

Download from [GitHub Releases](https://github.com/SSobol77/ecli/releases):

- **Linux**: `.deb` (Debian/Ubuntu), `.rpm` (Fedora/RHEL), `.tar.gz`
- **FreeBSD**: `.pkg`
- **macOS**: `.dmg` ([install notes](https://github.com/SSobol77/ecli/blob/main/docs/install/macos.md))
- **Windows**: `.exe` installer or portable executable ([install notes](https://github.com/SSobol77/ecli/blob/main/docs/install/windows.md))
- **Release metadata**: CycloneDX SBOM and SHA256 sidecars for release artifacts

**Option B: PyPI (Python Package Index)**

```bash
pip install ecli-editor
```

Import and launch names are unchanged:

```python
import ecli
```

```bash
ecli
```

Requires Python 3.11+ and system dependencies listed above.

---

## 🔨 Building from Source

### Prerequisites

- Python 3.11+
- Git
- System dependencies (see above)
- `uv` package manager (optional, for faster builds)

### Build Steps

```bash
# Clone the repository
git clone https://github.com/SSobol77/ecli.git
cd ecli

# Install dependencies
make install

# Run from source
make run

# Build packages for distribution
make help              # See all available build targets
```

### Build System

ECLI features a comprehensive multi-platform build system. For detailed information:

- **Build from Source**: Read [docs/contributor/build-from-source.md](https://github.com/SSobol77/ecli/blob/main/docs/contributor/build-from-source.md)
- **Packaging Flows**: See [docs/release/packaging-flows.md](https://github.com/SSobol77/ecli/blob/main/docs/release/packaging-flows.md)

#### Common Build Commands

```bash
# Display all available build targets
make help

# Check system capabilities and available tools
make sysinfo

# Build for your platform
make package-linux      # Linux package targets supported by the local toolchain
make package-pypi       # Python wheel + source distribution
make package-macos      # macOS DMG
make package-windows    # Windows portable EXE + installer
make package-freebsd    # FreeBSD package

# Release to GitHub (requires GitHub CLI)
make publish-all
```

---

## 🚀 Usage

### Launch ECLI

```bash
ecli [options] [file]
```

### Keyboard Shortcuts

Master ECLI with these essential keyboard shortcuts. Press `F1` anytime inside
the editor to open the help screen.

#### Basic Editing

| Shortcut | Action |
|----------|--------|
| `Backspace` | Delete character left / delete selection |
| `Tab` | Smart indent / indent block |
| `Shift+Tab` | Smart unindent |
| `Ctrl+\` | Toggle comment (line/block) |
| `Ctrl+C` | Copy |
| `Ctrl+X` | Cut |
| `Ctrl+V` | Paste |
| `Ctrl+A` | Select all |
| `Ctrl+Z` | Undo |
| `Ctrl+Y` | Redo |

#### Navigation & Search

| Shortcut | Action |
|----------|--------|
| `Ctrl+G` | Go to line |
| `Ctrl+F` | Find |
| `F3` | Find next |
| `F6` | Search & Replace with regex support |
| `Arrow keys` / `Home` / `End` | Cursor movement |
| `Page Up` / `Page Down` | Scroll by page |
| `Shift` + `Arrow keys` | Extend selection |

#### File Operations

| Shortcut | Action |
|----------|--------|
| `F2` | New file |
| `Ctrl+O` | Open file |
| `Ctrl+S` | Save |
| `F5` | Save as... |
| `Ctrl+Q` | Quit editor |

#### Tools & Panels

| Shortcut | Action |
|----------|--------|
| `F10` | File Explorer |
| `F4` | Diagnostics / Linter panel |
| `F9` | Git menu |
| `F7` | AI Assistant panel |
| `F8` | System Doctor |
| `F1` | Show Keyboard Shortcuts |
| `Esc` | Close current panel |
| `Insert` | Toggle Insert / Overwrite mode |
| `F12` | Switch focus between editor windows and panels |

The right side of the editor hosts workflow panels. The v0.2.0 service panels
are read-only or preview-only: System Doctor does not mutate host state, Command
Plan previews do not execute, and the Services panel reports composition status.

### Minimal Service CLI

The default CLI path still launches the editor:

```bash
python3 -m ecli
python3 -m ecli pyproject.toml
```

The explicit service flags provide read-only inspection without bypassing the
TUI model:

```bash
python3 -m ecli --services
python3 -m ecli --doctor
python3 -m ecli --plan-preview
```

Use `--json` for deterministic JSON output where supported. These commands are
inspection and preview surfaces only; they do not execute plans, run privileged
commands, install packages, start VMLab, or apply remediation.

### AI Configuration

AI features require user-provided provider credentials. API keys belong in:

```text
~/.config/ecli/.env
```

Provider selection belongs in `config.toml`, not in `.env`. If a selected
provider key is missing, the AI panel reports a normal configuration message
instead of a Python traceback.

For comprehensive keybindings and usage guide, see [Getting Started](https://github.com/SSobol77/ecli/blob/main/docs/contributor/development-setup.md).

---

## 📚 Documentation

Complete documentation is organized by audience:

### For Users
- [Installation Guide](https://github.com/SSobol77/ecli/blob/main/docs/contributor/install.md) - Detailed setup instructions
- [Build from Source](https://github.com/SSobol77/ecli/blob/main/docs/contributor/build-from-source.md) - Build system quick start
- [Getting Started](https://github.com/SSobol77/ecli/blob/main/docs/contributor/development-setup.md) - First steps with ECLI

### For Developers
- [Development Setup](https://github.com/SSobol77/ecli/blob/main/docs/contributor/development-setup.md) - Development environment
- [Architecture Overview](https://github.com/SSobol77/ecli/blob/main/docs/architecture/current-architecture.md) - System design
- [Packaging Flows](https://github.com/SSobol77/ecli/blob/main/docs/release/packaging-flows.md) - Release packaging overview
- [Build from Source](https://github.com/SSobol77/ecli/blob/main/docs/contributor/build-from-source.md) - Local build commands
- [Contributor Guide](https://github.com/SSobol77/ecli/blob/main/docs/contributor/README.md) - Contributing to ECLI

### For System Administrators
- [Supported Platforms](https://github.com/SSobol77/ecli/blob/main/docs/product/supported-platforms.md) - Platform matrix
- [Configuration Guide](https://github.com/SSobol77/ecli/blob/main/docs/config/README.md) - Configuration options
- [Deployment Guide](https://github.com/SSobol77/ecli/blob/main/docs/release/packaging-flows.md) - Production deployment

### Reference
- [API Documentation](https://github.com/SSobol77/ecli/blob/main/docs/extensions/plugin-api.md) - Plugin development
- [Architecture Details](https://github.com/SSobol77/ecli/blob/main/docs/architecture/README.md) - System internals
- [Release Process](https://github.com/SSobol77/ecli/blob/main/docs/release/release-process.md) - Release management
- [Quality Standards](https://github.com/SSobol77/ecli/blob/main/docs/quality/README.md) - Testing and quality gates

---

## 🏗️ Architecture

ECLI v0.2.0 keeps the existing editor/TUI behavior and introduces the Services
Foundation as typed, testable service-layer infrastructure:

- **Core Editor**: curses-based terminal editor with async task integration
- **Right-Side Panels**: Help, Diagnostics/Lint, AI Code Assistant, System Doctor, Git, File Manager, Services, and Command Plan previews
- **ConfigService**: typed layered configuration loading
- **ProjectService**: deterministic project discovery and path normalization
- **CommandPlanService**: draft command-plan models and preview/export behavior
- **BuiltInPolicyEngine**: deterministic built-in policy evaluation rules
- **AuditLogService**: append-only JSONL audit records with mandatory redaction
- **PrivilegedActionService**: refusal-only/dry-run-only skeleton for future elevated operations
- **SystemDoctor**: read-only diagnostic skeleton with draft remediation-plan generation
- **ServiceRegistry**: explicit composition root without global service-locator state

Safety boundaries for v0.2.0:

- SystemDoctor is read-only.
- CommandPlan output is draft/preview-only.
- PrivilegedActionService refuses real execution in this release.
- Service panels are visible in the UI but do not execute remediation.
- VMLab runtime behavior is not included in v0.2.0.

For detailed architecture information, see [Architecture Overview](https://github.com/SSobol77/ecli/blob/main/docs/architecture/current-architecture.md).

---

## 🤝 Contributing

We welcome contributions! Here's how to get started:

1. **Fork** the repository
2. **Clone** your fork: `git clone https://github.com/YOUR_USERNAME/ecli.git`
3. **Create** a feature branch: `git checkout -b feature/your-feature`
4. **Make** your changes
5. **Test** your changes: `make clean && make install && make run`
6. **Commit** with clear messages
7. **Push** to your fork
8. **Open** a Pull Request

For detailed contribution guidelines, see [CONTRIBUTING](https://github.com/SSobol77/ecli/blob/main/docs/contributor/README.md).

---

## ⚙️ Development

### Setting Up Development Environment

```bash
# Clone and setup
git clone https://github.com/SSobol77/ecli.git
cd ecli

# Install dev dependencies
make install

# Run tests
python -m pytest

# Run linter
ruff check src/

# Format code
black src/
```

### Project Structure

```
ecli/
├── src/ecli/              # Main source code
│   ├── core/              # Core editor functionality
│   ├── ui/                # Terminal UI components
│   ├── integrations/      # AI, Git, LSP integrations
│   └── utils/             # Utilities and helpers
├── docs/                  # Documentation
├── tests/                 # Test suite
├── scripts/               # Build and utility scripts
└── Makefile               # Multi-platform build system
```

---

## 🐛 Issues & Bug Reports

Found a bug? Please help us by opening an issue on GitHub:

- [Issue Tracker](https://github.com/SSobol77/ecli/issues)
- Include: OS, Python version, ECLI version, and reproduction steps
- Check [Known Issues](https://github.com/SSobol77/ecli/issues?q=label%3Aknown-issue) first

---

## 📋 Requirements

### Minimum Requirements
- **OS**: Linux, macOS, FreeBSD, or Windows
- **Python**: 3.11 or higher
- **Terminal**: Supports 256 colors and UTF-8

### Supported Platforms
- Ubuntu 20.04 LTS and newer
- Debian 11 and newer
- Fedora 36 and newer
- RHEL/CentOS/Rocky 8.0 and newer
- Arch Linux (current)
- FreeBSD 14.0 and newer
- macOS 12 and newer
- Windows 10/11

See [Supported Platforms](https://github.com/SSobol77/ecli/blob/main/docs/product/supported-platforms.md) for detailed compatibility matrix.

---

## 📝 License

ECLI is licensed under the [Apache License 2.0](https://github.com/SSobol77/ecli/blob/main/LICENSE). See the LICENSE file for details.

---

## 🔗 Links

- **Website**: https://www.ecli.io
- **GitHub**: https://github.com/SSobol77/ecli
- **Issues**: https://github.com/SSobol77/ecli/issues
- **Discussions**: https://github.com/SSobol77/ecli/discussions
- **PyPI**: https://pypi.org/project/ecli-editor/
- **Releases**: https://github.com/SSobol77/ecli/releases

---

## 💬 Support

- **Documentation**: Read [Build from Source](https://github.com/SSobol77/ecli/blob/main/docs/contributor/build-from-source.md) and [Packaging Flows](https://github.com/SSobol77/ecli/blob/main/docs/release/packaging-flows.md)
- **Community**: GitHub Discussions
- **Bugs**: GitHub Issues
- **Development**: See [Contributing](https://github.com/SSobol77/ecli/blob/main/docs/contributor/README.md)

---

## 🎯 Roadmap

For planned features and current development status, see [Roadmap](https://github.com/SSobol77/ecli/blob/main/docs/planning/roadmap.md).

---

<p align="center">
  Made with ❤️ by the ECLI community<br/>
  <a href="https://github.com/SSobol77/ecli">⭐ Star us on GitHub!</a>
</p>
