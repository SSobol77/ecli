<p align="center">
  <img src="https://github.com/SSobol77/ecli/blob/main/img/logo_m.png" alt="ecli Logo" width="200"/>
</p>

<h1 align="center"><b>ecli</b></h1>
<p align="center">
  <b>The Next-Gen Terminal IDE www.ecli.io</b><br/>
  A modern, AI-powered, extensible code editor for the terminal.
</p>

<br>

### 🚀 About **Ecli**

**Ecli** (short for *Editor CLI*) is a next-generation terminal IDE.
It brings the power of modern development tools into your terminal - fast, extensible, AI-ready.

<br>

#### ✨ Key Features

* 🧠 **AI Panel** - integrated assistant for code, docs, and refactoring
* 📂 **File Manager** - navigate and manage projects seamlessly
* 🌱 **Git Panel** - stage, commit, push/pull directly in terminal
* 🌈 **Syntax Highlighting** - powered by Tree-sitter, supports 70+ languages
* 📝 **LSP Integration** - full Language Server Protocol support (autocomplete, diagnostics, go-to-definition)
* 🐍 **Built-in Linters** -

  * **Ruff** (Python) integrated by default
  * Support for external linters across 70+ languages
* ⚡ **Extensible Architecture** - plugins & themes
* 🎨 **Dark/Light Themes** out of the box
* 🔄 **Cross-platform**: Linux, macOS, and FreeBSD

---

### 📦 Installation

#### 1. System Dependencies

First, ensure you have the required system libraries installed. These are necessary for the terminal interface, clipboard integration, YAML acceleration, and testing with full UTF-8 support.

<details>
<summary>Click to see installation commands for your OS</summary>

##### **On Debian/Ubuntu:**

```bash
sudo apt update && sudo apt install \
  libncurses6 \
  libncursesw6 \
  libtinfo6 \
  libncurses-dev \
  libncursesw5-dev \
  ncurses-bin \
  ncurses-term \
  libyaml-dev \
  xclip \
  xsel
```

##### **On Fedora/CentOS/RHEL:**

```bash
sudo dnf install ncurses ncurses-devel libyaml-devel xclip xsel
```

##### **On Arch Linux:**

```bash
sudo pacman -S ncurses libyaml xclip xsel
```

##### **On FreeBSD:**

```bash
sudo pkg install ncurses libyaml xclip xsel
```

</details>

These dependencies ensure:

* ✅ Full **curses** (UTF-8, wide-char, colors) support
* ✅ **wcwidth** correct behavior
* ✅ **PyYAML** C bindings for faster parsing
* ✅ **Clipboard support** for `pyperclip`

<br>

#### 2. Install ECLI

You can install ECLI using a pre-compiled package (recommended) or with `pip`.

##### **Option A: From a Package (Recommended)**

Download the appropriate package for your system from the [**GitHub Releases**](https://github.com/SSobol77/ecli/releases) page, then run the command for your OS.

**On Debian/Ubuntu:**

```bash
# Replace with the actual downloaded filename
sudo apt install ./ecli-0.1.0_amd64.deb
```

**On Fedora/CentOS/RHEL:**

```bash
# Replace with the actual downloaded filename
sudo dnf install ./ecli-0.1.0-1.x86_64.rpm
```

**On FreeBSD:**

```bash
# Replace with the actual downloaded filename
sudo pkg install ./ecli-0.1.0.pkg
```

**On Arch Linux:**

The recommended method for Arch Linux is to install from the Arch User Repository (AUR). Once the package is available on the AUR, you can install it using an AUR helper like `yay`:

```bash
yay -S ecli
```

*(Note: The `ecli` package must be submitted to the AUR first.)*

<br>

##### **Option B: With pip**

This method requires you to have Python 3.11+ and `pip` installed, in addition to the system dependencies mentioned above.

```bash
pip install ecli
```
