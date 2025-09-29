#!/bin/sh
# ==============================================================================
# build-freebsd-pkg.sh - Local FreeBSD Package Builder for ECLI
# ==============================================================================

set -eu

# Global variables
readonly PROJECT_ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
readonly PACKAGE_NAME="ecli"
readonly MAINTAINER="Siergej Sobolewski <s.sobolewski@hotmail.com>"
readonly HOMEPAGE="https://ecli.io"
readonly LICENSE="Apache-2.0"
readonly COMMENT="Terminal DevOps editor with AI and Git integration"
readonly CATEGORY="editors"

# Color support
if [ -t 1 ]; then
    readonly GREEN="\033[32m"
    readonly BLUE="\033[34m"
    readonly BOLD="\033[1m"
    readonly RED="\033[31m"
    readonly RESET="\033[0m"
else
    readonly GREEN=""; readonly BLUE=""; readonly BOLD=""; readonly RED=""; readonly RESET=""
fi

# Runtime variables
VERSION=""
STAGING_ROOT=""
META_DIR=""
RELEASES_DIR=""
EXECUTABLE=""

# ==============================================================================
# FUNCTIONS
# ==============================================================================

print_header() {
    echo "${BLUE}${BOLD}==> $1${RESET}"
}

print_step() {
    echo "${GREEN}==> $1${RESET}"
}

print_error() {
    echo "${RED}ERROR: $1${RESET}" >&2
}

print_warning() {
    echo "${RED}WARNING: $1${RESET}" >&2
}

cleanup() {
    print_step "Cleaning up temporary directories..."
    # DON'T clean up - leave for debugging
    echo "Skipping cleanup for debugging - directories preserved:"
    echo "STAGING_ROOT: $STAGING_ROOT"
    echo "META_DIR: $META_DIR"
    # if [ -n "$STAGING_ROOT" ] && [ -d "$STAGING_ROOT" ]; then
    #     rm -rf "$STAGING_ROOT" && echo "Removed: $STAGING_ROOT"
    # fi
    # if [ -n "$META_DIR" ] && [ -d "$META_DIR" ]; then
    #     rm -rf "$META_DIR" && echo "Removed: $META_DIR"
    # fi
}

check_dependencies() {
    local deps="python3.11 pip pyinstaller pkg install git"
    local missing=""

    for dep in $deps; do
        if ! command -v "$dep" >/dev/null 2>&1; then
            missing="$missing $dep"
        fi
    done

    if [ -n "$missing" ]; then
        print_error "Missing dependencies:$missing"
        return 1
    fi
}

detect_version() {
    print_step "Reading project version from pyproject.toml..."

    if [ ! -f "$PROJECT_ROOT/pyproject.toml" ]; then
        print_error "pyproject.toml not found in $PROJECT_ROOT"
        return 1
    fi

    VERSION="$(python3.11 - <<'PY'
import sys
import os
sys.path.insert(0, os.environ.get('PROJECT_ROOT', '.'))

try:
    import tomllib
except ImportError:
    try:
        import tomli as tomllib
    except ImportError:
        print("ERROR: Neither tomllib nor tomli available")
        sys.exit(1)

try:
    with open(os.path.join(os.environ.get('PROJECT_ROOT', '.'), 'pyproject.toml'), 'rb') as f:
        data = tomllib.load(f)
        print(data["project"]["version"])
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)
PY
    )"

    if [ -z "$VERSION" ] || echo "$VERSION" | grep -q "ERROR:"; then
        print_error "Could not read version from pyproject.toml: $VERSION"
        return 1
    fi

    echo "Detected version: ${BOLD}${VERSION}${RESET}"
}

setup_directories() {
    RELEASES_DIR="$PROJECT_ROOT/releases/$VERSION"
    STAGING_ROOT="$PROJECT_ROOT/build/freebsd_pkg_staging"
    META_DIR="$PROJECT_ROOT/build/freebsd_pkg_meta"

    print_step "Setting up directories..."
    echo "PROJECT_ROOT: $PROJECT_ROOT"
    echo "RELEASES_DIR: $RELEASES_DIR"
    echo "STAGING_ROOT: $STAGING_ROOT"
    echo "META_DIR: $META_DIR"

    # Clean ONLY the packaging directories, NOT dist/ (needed for PyInstaller output)
    if [ -d "$STAGING_ROOT" ]; then
        rm -rf "$STAGING_ROOT"
        echo "Cleaned staging directory"
    fi

    if [ -d "$META_DIR" ]; then
        rm -rf "$META_DIR"
        echo "Cleaned meta directory"
    fi

    # Create all necessary directories
    if ! mkdir -p \
        "$STAGING_ROOT/usr/local/bin" \
        "$STAGING_ROOT/usr/local/share/applications" \
        "$STAGING_ROOT/usr/local/share/icons/hicolor/256x256/apps" \
        "$STAGING_ROOT/usr/local/share/doc/$PACKAGE_NAME" \
        "$STAGING_ROOT/usr/local/man/man1" \
        "$RELEASES_DIR" \
        "$META_DIR"; then
        print_error "Failed to create directories"
        return 1
    fi

    echo "Directories created successfully"

    # Verify directories were created
    if [ ! -d "$STAGING_ROOT/usr/local/bin" ]; then
        print_error "Staging bin directory was not created: $STAGING_ROOT/usr/local/bin"
        return 1
    fi

    if [ ! -d "$META_DIR" ]; then
        print_error "Meta directory was not created: $META_DIR"
        return 1
    fi

    if [ ! -d "$RELEASES_DIR" ]; then
        print_error "Releases directory was not created: $RELEASES_DIR"
        return 1
    fi

    echo "Directory verification successful"
}

install_system_dependencies() {
    print_header "ECLI FreeBSD Package Builder"
    print_step "Installing system build dependencies..."

    # Check if packages are already installed
    local packages="python311 py311-pip py311-setuptools py311-wheel py311-pyinstaller git gmake pkgconf ca_root_nss curl ncurses"
    local missing_packages=""

    for package in $packages; do
        if ! pkg info -e "$package" >/dev/null 2>&1; then
            missing_packages="$missing_packages $package"
        fi
    done

    if [ -n "$missing_packages" ]; then
        print_step "Installing missing packages:$missing_packages"
        if ! pkg install -y $missing_packages; then
            print_error "Failed to install system dependencies"
            return 1
        fi
    else
        print_step "All required packages already installed"
    fi
}

install_python_dependencies() {
    print_step "Installing Python runtime dependencies..."

    # Install tomli if tomllib not available
    python3.11 -c "import tomllib" 2>/dev/null || {
        print_step "Installing tomli for TOML parsing..."
        python3.11 -m pip install tomli
    }

    local pip_packages="aiohttp aiosignal yarl multidict frozenlist python-dotenv toml chardet pyperclip wcwidth pygments tato"

    if ! python3.11 -m pip install $pip_packages; then
        print_error "Failed to install Python dependencies"
        return 1
    fi
}

build_binary() {
    print_step "Building standalone binary with PyInstaller..."

    local pyinstaller_success=false

    if [ -f "$PROJECT_ROOT/ecli.spec" ]; then
        print_step "Using ecli.spec for build configuration..."
        if pyinstaller "$PROJECT_ROOT/ecli.spec" --clean --noconfirm; then
            pyinstaller_success=true
        else
            print_warning "ecli.spec build failed, trying direct method..."
        fi
    fi

    if [ "$pyinstaller_success" = "false" ]; then
        print_step "Using direct PyInstaller parameters..."
        if ! pyinstaller "$PROJECT_ROOT/main.py" \
            --name "$PACKAGE_NAME" \
            --onefile --clean --noconfirm --strip \
            --paths "$PROJECT_ROOT/src" \
            --add-data "$PROJECT_ROOT/config.toml:." \
            --hidden-import=ecli \
            --hidden-import=curses \
            --hidden-import=_curses \
            --hidden-import=_curses_panel \
            --hidden-import=locale \
            --hidden-import=signal \
            --hidden-import=queue \
            --hidden-import=threading \
            --hidden-import=subprocess \
            --hidden-import=shlex \
            --hidden-import=tempfile \
            --hidden-import=unicodedata \
            --hidden-import=json \
            --hidden-import=importlib.util \
            --hidden-import=traceback \
            --hidden-import=types \
            --hidden-import=shutil \
            --hidden-import=textwrap \
            --hidden-import=re \
            --hidden-import=functools \
            --hidden-import=logging \
            --hidden-import=time \
            --hidden-import=pathlib \
            --hidden-import=asyncio \
            --hidden-import=dotenv --collect-all=dotenv \
            --hidden-import=toml --collect-all=toml \
            --hidden-import=aiohttp --collect-all=aiohttp \
            --hidden-import=aiosignal --collect-all=aiosignal \
            --hidden-import=yarl --collect-all=yarl \
            --hidden-import=multidict --collect-all=multidict \
            --hidden-import=frozenlist --collect-all=frozenlist \
            --hidden-import=chardet --collect-all=chardet \
            --hidden-import=pyperclip --collect-all=pyperclip \
            --hidden-import=wcwidth --collect-all=wcwidth \
            --hidden-import=pygments --collect-all=pygments \
            --collect-binaries=_curses \
            --collect-binaries=_curses_panel \
            --collect-data=pygments \
            --collect-data=wcwidth \
            --runtime-hook "$PROJECT_ROOT/packaging/pyinstaller/rthooks/force_imports.py"; then
            print_error "PyInstaller build failed"
            return 1
        fi
    fi

    # Verify build output
    if [ -x "dist/$PACKAGE_NAME/$PACKAGE_NAME" ]; then
        EXECUTABLE="dist/$PACKAGE_NAME/$PACKAGE_NAME"
    elif [ -x "dist/$PACKAGE_NAME" ]; then
        EXECUTABLE="dist/$PACKAGE_NAME"
    else
        print_error "PyInstaller output not found in dist/"
        return 1
    fi

    print_step "Binary built successfully: $EXECUTABLE"
}

stage_package_files() {
    print_step "Creating FreeBSD package structure..."

    # Debug: Check if executable exists and is accessible
    echo "Executable path: $EXECUTABLE"
    if [ ! -f "$EXECUTABLE" ]; then
        print_error "Executable not found: $EXECUTABLE"
        return 1
    fi

    if [ ! -x "$EXECUTABLE" ]; then
        print_error "Executable not executable: $EXECUTABLE"
        return 1
    fi

    echo "Staging directory: $STAGING_ROOT"
    echo "Target binary path: $STAGING_ROOT/usr/local/bin/$PACKAGE_NAME"

    # Ensure target directory exists
    if [ ! -d "$STAGING_ROOT/usr/local/bin" ]; then
        print_error "Target directory does not exist: $STAGING_ROOT/usr/local/bin"
        return 1
    fi

    # Install binary with absolute paths
    if ! install -m 755 "$PROJECT_ROOT/$EXECUTABLE" "$STAGING_ROOT/usr/local/bin/$PACKAGE_NAME"; then
        print_error "Failed to install binary"
        echo "install command failed. Checking permissions and paths..."
        ls -la "$PROJECT_ROOT/$EXECUTABLE"
        ls -la "$STAGING_ROOT/usr/local/bin/"
        return 1
    fi

    # Verify binary was installed correctly
    if [ ! -f "$STAGING_ROOT/usr/local/bin/$PACKAGE_NAME" ]; then
        print_error "Binary was not created in staging area"
        return 1
    fi

    if [ ! -x "$STAGING_ROOT/usr/local/bin/$PACKAGE_NAME" ]; then
        print_error "Binary in staging area is not executable"
        return 1
    fi

    echo "Binary installed successfully: $(ls -la "$STAGING_ROOT/usr/local/bin/$PACKAGE_NAME")"

    # Desktop entry
    local desktop_source="$PROJECT_ROOT/packaging/linux/fpm-common/$PACKAGE_NAME.desktop"
    if [ -f "$desktop_source" ]; then
        install -m 644 "$desktop_source" \
            "$STAGING_ROOT/usr/local/share/applications/$PACKAGE_NAME.desktop"
    else
        cat > "$STAGING_ROOT/usr/local/share/applications/$PACKAGE_NAME.desktop" <<EOF
[Desktop Entry]
Name=ECLI
Comment=Fast terminal code editor
Exec=$PACKAGE_NAME
Icon=$PACKAGE_NAME
Terminal=true
Type=Application
Categories=Development;TextEditor;
StartupNotify=false
EOF
    fi

    # Application icon
    if [ -f "$PROJECT_ROOT/img/logo_m.png" ]; then
        install -m 644 "$PROJECT_ROOT/img/logo_m.png" \
            "$STAGING_ROOT/usr/local/share/icons/hicolor/256x256/apps/$PACKAGE_NAME.png"
    else
        print_warning "Application icon not found: $PROJECT_ROOT/img/logo_m.png"
    fi

    # Documentation
    if [ -f "$PROJECT_ROOT/LICENSE" ]; then
        install -m 644 "$PROJECT_ROOT/LICENSE" "$STAGING_ROOT/usr/local/share/doc/$PACKAGE_NAME/LICENSE"
    fi
    if [ -f "$PROJECT_ROOT/README.md" ]; then
        install -m 644 "$PROJECT_ROOT/README.md" "$STAGING_ROOT/usr/local/share/doc/$PACKAGE_NAME/README.md"
    fi

    # Manual page
    if [ ! -f "$PROJECT_ROOT/man/$PACKAGE_NAME.1" ]; then
        local manfile="$STAGING_ROOT/usr/local/man/man1/$PACKAGE_NAME.1"
        cat > "$manfile" <<EOF
.TH $PACKAGE_NAME 1 "$(date +"%B %Y")" "$PACKAGE_NAME $VERSION" "User Commands"
.SH NAME
$PACKAGE_NAME - Terminal code editor
.SH SYNOPSIS
.B $PACKAGE_NAME
[\\fIOPTIONS\\fR] [\\fIFILE\\fR...]
.SH DESCRIPTION
$PACKAGE_NAME is a fast terminal code editor with AI and Git integration.
.SH OPTIONS
\\fB--help\\fR     Show help
\\fB--version\\fR  Show version
.SH AUTHOR
$MAINTAINER
.SH HOMEPAGE
$HOMEPAGE
EOF
        gzip -f "$manfile"
    else
        install -m 644 "$PROJECT_ROOT/man/$PACKAGE_NAME.1" "$STAGING_ROOT/usr/local/man/man1/$PACKAGE_NAME.1"
        gzip -f "$STAGING_ROOT/usr/local/man/man1/$PACKAGE_NAME.1"
    fi
}

create_package() {
    print_step "Creating FreeBSD package manifest..."

    local abi
    abi="$(pkg config ABI 2>/dev/null || echo 'FreeBSD:14:amd64')"
    local manifest_file="$META_DIR/+MANIFEST"

    # Ensure releases directory exists
    mkdir -p "$RELEASES_DIR"

    # Debug: verify staging area has our binary
    echo "Verifying staging area before package creation:"
    ls -la "$STAGING_ROOT/usr/local/bin/"

    if [ ! -f "$STAGING_ROOT/usr/local/bin/$PACKAGE_NAME" ]; then
        print_error "Binary not found in staging area: $STAGING_ROOT/usr/local/bin/$PACKAGE_NAME"
        return 1
    fi

    # Create proper FreeBSD manifest format with explicit file list
    cat > "$manifest_file" <<EOF
name: "$PACKAGE_NAME"
version: "$VERSION"
origin: "$CATEGORY/$PACKAGE_NAME"
comment: "$COMMENT"
desc: "$COMMENT"
maintainer: "$MAINTAINER"
www: "$HOMEPAGE"
abi: "$abi"
prefix: "/usr/local"
categories: ["$CATEGORY"]
licenses: ["$LICENSE"]
deps: {
  ncurses: {origin: "devel/ncurses", version: ">=6.0"}
}
files: {
  /usr/local/bin/$PACKAGE_NAME: {uname: root, gname: wheel, perm: 0755},
  /usr/local/share/applications/$PACKAGE_NAME.desktop: {uname: root, gname: wheel, perm: 0644},
  /usr/local/share/icons/hicolor/256x256/apps/$PACKAGE_NAME.png: {uname: root, gname: wheel, perm: 0644},
  /usr/local/share/doc/$PACKAGE_NAME/LICENSE: {uname: root, gname: wheel, perm: 0644},
  /usr/local/share/doc/$PACKAGE_NAME/README.md: {uname: root, gname: wheel, perm: 0644},
  /usr/local/man/man1/$PACKAGE_NAME.1.gz: {uname: root, gname: wheel, perm: 0644}
}
EOF

    # Alternative UCL format with explicit file list
    local ucl_manifest="$META_DIR/+MANIFEST.ucl"
    cat > "$ucl_manifest" <<EOF
name = "$PACKAGE_NAME";
version = "$VERSION";
origin = "$CATEGORY/$PACKAGE_NAME";
comment = "$COMMENT";
desc = "$COMMENT";
maintainer = "$MAINTAINER";
www = "$HOMEPAGE";
abi = "$abi";
prefix = "/usr/local";
categories = ["$CATEGORY"];
licenses = ["$LICENSE"];
files = {
  "/usr/local/bin/$PACKAGE_NAME" = {uname = "root"; gname = "wheel"; perm = 0755;};
  "/usr/local/share/applications/$PACKAGE_NAME.desktop" = {uname = "root"; gname = "wheel"; perm = 0644;};
  "/usr/local/share/icons/hicolor/256x256/apps/$PACKAGE_NAME.png" = {uname = "root"; gname = "wheel"; perm = 0644;};
  "/usr/local/share/doc/$PACKAGE_NAME/LICENSE" = {uname = "root"; gname = "wheel"; perm = 0644;};
  "/usr/local/share/doc/$PACKAGE_NAME/README.md" = {uname = "root"; gname = "wheel"; perm = 0644;};
  "/usr/local/man/man1/$PACKAGE_NAME.1.gz" = {uname = "root"; gname = "wheel"; perm = 0644;};
};
EOF

    echo "Created YAML manifest:"
    cat "$manifest_file"
    echo ""
    echo "Created UCL manifest:"
    cat "$ucl_manifest"

    print_step "Building .pkg package..."

    # Debug: show what we're trying to create
    echo "Manifest file: $manifest_file"
    echo "Staging root: $STAGING_ROOT"
    echo "Output directory: $RELEASES_DIR"
    echo "Working directory: $(pwd)"

    # Try different pkg create approaches
    local pkg_created=false
    local error_log="$META_DIR/pkg_create_error.log"

    # Method 1: Direct output to releases directory (try UCL first)
    print_step "Trying Method 1a: UCL format"
    echo "Command: pkg create -M \"$ucl_manifest\" -r \"$STAGING_ROOT\" -o \"$RELEASES_DIR\""

    if pkg create -M "$ucl_manifest" -r "$STAGING_ROOT" -o "$RELEASES_DIR" 2>&1 | tee "$error_log"; then
        pkg_created=true
        print_step "Method 1a (UCL) successful"
    else
        print_step "Trying Method 1b: YAML format"
        echo "Command: pkg create -M \"$manifest_file\" -r \"$STAGING_ROOT\" -o \"$RELEASES_DIR\""

        if pkg create -M "$manifest_file" -r "$STAGING_ROOT" -o "$RELEASES_DIR" 2>&1 | tee "$error_log"; then
            pkg_created=true
            print_step "Method 1b (YAML) successful"
        else
            print_warning "Both UCL and YAML direct methods failed. Error details:"
            cat "$error_log" || echo "Could not read error log"

            # Method 2: Create in current directory, then move
            print_step "Trying Method 2: Create in current directory"
            cd "$PROJECT_ROOT"
            echo "Changed to directory: $(pwd)"
            echo "Command: pkg create -M \"$ucl_manifest\" -r \"$STAGING_ROOT\""

            if pkg create -M "$ucl_manifest" -r "$STAGING_ROOT" 2>&1 | tee "$error_log"; then
                local created_pkg="${PACKAGE_NAME}-${VERSION}.pkg"
                echo "Looking for created package: $created_pkg"
                if [ -f "$created_pkg" ]; then
                    print_step "Moving package to releases directory"
                    mv "$created_pkg" "$RELEASES_DIR/"
                    pkg_created=true
                    print_step "Method 2 successful"
                else
                    print_error "Package file not found after creation: $created_pkg"
                    echo "Files in current directory:"
                    ls -la *.pkg 2>/dev/null || echo "No .pkg files found"
                fi
            else
                print_error "Method 2 also failed. Error details:"
                cat "$error_log" || echo "Could not read error log"
            fi
        fi
    fi

    if [ "$pkg_created" = "false" ]; then
        print_error "All pkg create methods failed"
        print_step "Diagnostic information:"
        echo "Manifest file contents:"
        cat "$manifest_file" || echo "Could not read manifest"
        echo "Staging directory contents:"
        find "$STAGING_ROOT" -type f | head -20 || echo "Could not list staging contents"
        echo "Working directory: $(pwd)"
        echo "pkg version: $(pkg --version)"
        return 1
    fi

    # Find and verify the created package
    local pkg_path
    pkg_path="$(find "$RELEASES_DIR" -name "${PACKAGE_NAME}-${VERSION}*.pkg" | head -1)"

    if [ -z "$pkg_path" ] || [ ! -f "$pkg_path" ]; then
        print_error "pkg create did not produce a .pkg file"
        print_step "Contents of releases directory:"
        ls -la "$RELEASES_DIR" || true
        return 1
    fi

    print_step "Package created successfully: $(basename "$pkg_path")"

    # Save manifest and staging info for debugging
    cp "$manifest_file" "$RELEASES_DIR/manifest.txt" 2>/dev/null || true
    cp "$ucl_manifest" "$RELEASES_DIR/manifest.ucl" 2>/dev/null || true
    find "$STAGING_ROOT" -type f > "$RELEASES_DIR/staged_files.txt" 2>/dev/null || true

    # Generate checksum
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$pkg_path" > "${pkg_path}.sha256"
    elif command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$pkg_path" > "${pkg_path}.sha256"
    else
        print_warning "No checksum utility found (sha256sum or shasum)"
    fi

    # Return just the path without any print statements
    printf '%s\n' "$pkg_path"
}

verify_package() {
    local pkg_path="$1"

    print_step "Verifying package..."

    if ! pkg info -F "$pkg_path" >/dev/null 2>&1; then
        print_warning "Package verification failed, but continuing..."
        return 0
    fi

    echo "Package contents:"
    pkg info -l -F "$pkg_path" | head -10
}

# ==============================================================================
# MAIN EXECUTION
# ==============================================================================

main() {
    local pkg_path=""

    # Set trap for cleanup on any exit
    trap cleanup EXIT

    # Check if running as root, if not, restart with sudo
    if [ "$(id -u)" -ne 0 ]; then
        echo "This script requires root privileges. Restarting with sudo..."
        exec sudo PROJECT_ROOT="$PROJECT_ROOT" "$0" "$@"
    fi

    cd "$PROJECT_ROOT"
    export PROJECT_ROOT

    # Execute build steps with error handling and debugging
    print_step "Starting build process..."

    print_step "Step 1: Checking dependencies..."
    check_dependencies || { print_error "Dependencies check failed"; exit 1; }

    print_step "Step 2: Installing system dependencies..."
    install_system_dependencies || { print_error "System dependencies failed"; exit 1; }

    print_step "Step 3: Installing Python dependencies..."
    install_python_dependencies || { print_error "Python dependencies failed"; exit 1; }

    print_step "Step 4: Detecting version..."
    detect_version || { print_error "Version detection failed"; exit 1; }

    print_step "Step 5: Building binary..."
    build_binary || { print_error "Binary build failed"; exit 1; }

    print_step "Step 6: Setting up directories..."
    setup_directories || { print_error "Directory setup failed"; exit 1; }

    print_step "Step 7: Staging package files..."
    stage_package_files || { print_error "Package staging failed"; exit 1; }

    print_step "Step 8: Creating package..."
    # Capture the package path properly
    if ! pkg_path=$(create_package); then
        print_error "Package creation failed"
        exit 1
    fi

    if [ -z "$pkg_path" ]; then
        print_error "Package path is empty"
        exit 1
    fi

    print_step "Step 9: Verifying package..."
    verify_package "$pkg_path" || { print_warning "Package verification failed, but continuing..."; }

    # Final output
    print_header "BUILD COMPLETE"
    echo "Package: ${BOLD}$pkg_path${RESET}"
    if [ -f "${pkg_path}.sha256" ]; then
        echo "Checksum: ${BOLD}${pkg_path}.sha256${RESET}"
    fi

    print_header "INSTALLATION"
    echo "To install locally: ${BOLD}pkg install $pkg_path${RESET}"
    if [ -f "${pkg_path}.sha256" ]; then
        echo "To verify checksum: ${BOLD}sha256sum -c ${pkg_path}.sha256${RESET}"
    fi

    # Cleanup will be called automatically by trap
}

# Run main function only if script is executed directly
main "$@"
