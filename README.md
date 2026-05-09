<!--
Filename: README.md
Project:  ECLI
License:  MIT
Author:   Siergej Sobolewski
Copyright: (c) 2026 Siergej Sobolewski
-->

<p align="center">
  <img src="https://github.com/SSobol77/ecli/blob/main/img/logo_m.png" alt="ecli Logo" width="200"/>
</p>

<h1 align="center"><b>ECLI</b></h1>
<p align="center">
  <b>The Next-Generation Terminal IDE</b><br/>
  <i>Modern, AI-powered, extensible code editor for the terminal</i>
</p>

<p align="center">
  <a href="https://github.com/SSobol77/ecli/releases"><img alt="Latest Release" src="https://img.shields.io/github/v/release/SSobol77/ecli?include_prereleases&style=flat-square"></a>
  <a href="https://github.com/SSobol77/ecli/blob/main/LICENSE"><img alt="License" src="https://img.shields.io/github/license/SSobol77/ecli?style=flat-square"></a>
  <a href="https://github.com/SSobol77/ecli"><img alt="Stars" src="https://img.shields.io/github/stars/SSobol77/ecli?style=flat-square"></a>
</p>

---

## 🚀 About ECLI

**ECLI** (Editor CLI) is a next-generation terminal IDE that brings the power of modern development tools into your terminal environment. It's built for developers who value speed, flexibility, and the ability to work without leaving the terminal.

### ✨ Key Features


* 🧠 **AI-Powered Assistant** - Integrated AI panel for code generation, documentation, and refactoring
* 📂 **Modern File Manager** - Seamlessly navigate and manage projects with intuitive UI
* 🌱 **Git Integration** - Stage, commit, push/pull directly in terminal
* 🌈 **Syntax Highlighting** - Powered by Tree-sitter, supports 70+ programming languages
* 📝 **LSP Integration** - Full Language Server Protocol support with autocomplete, diagnostics, go-to-definition
* 🐍 **Built-in Linters** - Ruff (Python) by default + support for external linters across 70+ languages
* ⚡ **Extensible Architecture** - Plugin and theme system for unlimited customization
* 🎨 **Professional Themes** - Dark and light themes included
* 🔄 **Cross-Platform** - Native support for Linux, macOS, FreeBSD, and Windows

---

## 📥 Quick Start

### Fastest Installation (Pre-built Packages)

Download and install a pre-compiled package for your platform:

```bash
# Debian/Ubuntu
sudo apt install ./ecli_0.1.0_amd64.deb

# Fedora/RHEL/Rocky
sudo dnf install ./ecli_0.1.0_amd64.rpm

# Windows (PowerShell)
.\ecli_0.1.0_win_x64.exe

# macOS
open ecli_0.1.0_macos_x86_64.dmg
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
pip install ecli
```

---

## 📦 Installation Guide

### Complete Installation Instructions

For detailed platform-specific installation instructions, system dependencies, and troubleshooting, see the [Installation Guide](docs/contributor/install.md).

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

- **Linux**: `.deb` (Debian/Ubuntu), `.rpm` (Fedora/RHEL), `.AppImage` (any Linux), `.tar.gz`
- **FreeBSD**: `.pkg`
- **macOS**: `.dmg`
- **Windows**: `.exe`

**Option B: PyPI (Python Package Index)**

```bash
pip install ecli
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

- **Quick Start**: Read [BUILD_QUICK_REFERENCE.md](BUILD_QUICK_REFERENCE.md) (5 minutes)
- **Complete Guide**: See [BUILD_SYSTEM.md](BUILD_SYSTEM.md) for all targets and options
- **Makefile Overview**: Check [MAKEFILE_UPGRADE_SUMMARY.md](MAKEFILE_UPGRADE_SUMMARY.md)

#### Common Build Commands

```bash
# Display all available build targets
make help

# Check system capabilities and available tools
make sysinfo

# Build for your platform
make package-linux      # All Linux packages (deb, rpm, AppImage)
make package-pypi       # Python wheel + source distribution
make package-macos      # macOS DMG
make package-windows    # Windows installer
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

### Basic Commands

| Shortcut | Action |
|----------|--------|
| `Ctrl+N` | New file |
| `Ctrl+O` | Open file |
| `Ctrl+S` | Save file |
| `Ctrl+Q` | Quit |
| `Ctrl+A` | AI assistant panel |
| `Ctrl+G` | Git panel |
| `Ctrl+F` | Search in file |
| `F1` | Help |

For comprehensive keybindings and usage guide, see [Getting Started](docs/contributor/development-setup.md).

---

## 📚 Documentation

Complete documentation is organized by audience:

### For Users
- [Installation Guide](docs/contributor/install.md) - Detailed setup instructions
- [Quick Reference](BUILD_QUICK_REFERENCE.md) - Build system quick start
- [Getting Started](docs/contributor/development-setup.md) - First steps with ECLI

### For Developers
- [Development Setup](docs/contributor/development-setup.md) - Development environment
- [Architecture Overview](docs/architecture/current-architecture.md) - System design
- [Build System](BUILD_SYSTEM.md) - Complete build documentation
- [Contributor Guide](docs/contributor/README.md) - Contributing to ECLI

### For System Administrators
- [Supported Platforms](docs/product/supported-platforms.md) - Platform matrix
- [Configuration Guide](docs/config/README.md) - Configuration options
- [Deployment Guide](docs/release/packaging-flows.md) - Production deployment

### Reference
- [API Documentation](docs/extensions/plugin-api.md) - Plugin development
- [Architecture Details](docs/architecture/README.md) - System internals
- [Release Process](docs/release/release-process.md) - Release management
- [Quality Standards](docs/quality/README.md) - Testing and quality gates

---

## 🏗️ Architecture

ECLI is built on a modern, extensible architecture:

- **Core Editor**: Python with async/await for responsive UI
- **Terminal UI**: curses-based for full terminal control
- **AI Integration**: Pluggable AI provider system (OpenAI, Anthropic, HuggingFace, Ollama)
- **LSP Client**: Language Server Protocol for IDE-like features
- **Git Integration**: Direct git repository management
- **Plugin System**: Extensible architecture for custom features

For detailed architecture information, see [Architecture Overview](docs/architecture/current-architecture.md).

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

For detailed contribution guidelines, see [CONTRIBUTING](docs/contributor/README.md).

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

See [Supported Platforms](docs/product/supported-platforms.md) for detailed compatibility matrix.

---

## 📝 License

ECLI is licensed under the [MIT License](LICENSE). See the LICENSE file for details.

---

## 🔗 Links

- **Website**: https://www.ecli.io
- **GitHub**: https://github.com/SSobol77/ecli
- **Issues**: https://github.com/SSobol77/ecli/issues
- **Discussions**: https://github.com/SSobol77/ecli/discussions
- **PyPI**: https://pypi.org/project/ecli/
- **Releases**: https://github.com/SSobol77/ecli/releases

---

## 💬 Support

- **Documentation**: Read [Build Quick Reference](BUILD_QUICK_REFERENCE.md) and [Build System Guide](BUILD_SYSTEM.md)
- **Community**: GitHub Discussions
- **Bugs**: GitHub Issues
- **Development**: See [Contributing](docs/contributor/README.md)

---

## 🎯 Roadmap

For planned features and current development status, see [Roadmap](docs/planning/roadmap.md).

---

<p align="center">
  Made with ❤️ by the ECLI community<br/>
  <a href="https://github.com/SSobol77/ecli">⭐ Star us on GitHub!</a>
</p>
