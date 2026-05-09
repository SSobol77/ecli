# =============================================================================
# Makefile for ECLI — Multi-Platform Build System
# =============================================================================
# Supports: Debian/Ubuntu, Fedora/RHEL/Rocky, FreeBSD, macOS, Windows, Python (PyPI)
# AppImage (Linux), Snap (Linux), and various archive formats
# =============================================================================

PYTHON ?= python3
UV ?= uv
OS := $(shell uname -s)
ARCH := $(shell uname -m)

# Normalize architecture
ifeq ($(ARCH),x86_64)
	ARCH_NORMALIZED := x86_64
else ifeq ($(ARCH),aarch64)
	ARCH_NORMALIZED := arm64
else ifeq ($(ARCH),arm64)
	ARCH_NORMALIZED := arm64
else
	ARCH_NORMALIZED := $(ARCH)
endif

# Read version from pyproject.toml without multiline $(shell)
# We expect a line like: version = "0.1.0"
PACKAGE_VERSION := $(shell awk -F'"' '/^[[:space:]]*version[[:space:]]*=/ {print $$2; exit}' pyproject.toml 2>/dev/null || echo 0.0.0)

# Release directory
RELEASE_DIR := releases/$(PACKAGE_VERSION)

.DEFAULT_GOAL := help

# ---- FreeBSD .pkg (via vmactions/freebsd-vm) -------------------------------
FREEBSD_VM_IMAGE := ghcr.io/vmactions/freebsd-vm
# tag order (can be changed if desired)
FREEBSD_VM_TAGS ?= 14.2 14.1 14.0 14 latest


# =============================================================================
# Help & Documentation
# =============================================================================
.PHONY: help
help:
	@echo ""
	@echo "╔═══════════════════════════════════════════════════════════════════════╗"
	@echo "║                 ECLI Multi-Platform Build System                      ║"
	@echo "║                    Version: $(PACKAGE_VERSION)                                  ║"
	@echo "╚═══════════════════════════════════════════════════════════════════════╝"
	@echo ""
	@echo "QUICK START:"
	@echo "  make install                - Install dependencies"
	@echo "  make run                    - Run from source"
	@echo "  make clean                  - Clean all build artifacts"
	@echo ""
	@echo "LINUX PACKAGES:"
	@echo "  make package-deb            - Build Debian/Ubuntu .deb (local)"
	@echo "  make package-deb-docker     - Build .deb in container (recommended)"
	@echo "  make package-rpm            - Build Fedora/RHEL .rpm (local)"
	@echo "  make package-rpm-docker     - Build .rpm in container (recommended)"
	@echo "  make package-appimage       - Build AppImage (cross-distro Linux)"
	@echo "  make package-snap           - Build Snap (Snapcraft; optional)"
	@echo "  make package-tar-linux      - Build tar.gz archive (Linux)"
	@echo ""
	@echo "UNIX PACKAGES:"
	@echo "  make package-freebsd        - Build FreeBSD .pkg (native)"
	@echo "  make package-freebsd-ci     - Trigger CI build in FreeBSD VM"
	@echo "  make package-freebsd-chroot - Build in chroot (FreeBSD host)"
	@echo "  make package-freebsd-port   - Build via FreeBSD Ports"
	@echo ""
	@echo "DESKTOP PACKAGES:"
	@echo "  make package-macos          - Build macOS .dmg (native)"
	@echo "  make package-windows        - Build Windows .exe (native, PowerShell)"
	@echo ""
	@echo "PYTHON PACKAGES:"
	@echo "  make package-pypi           - Build wheel + sdist (for PyPI)"
	@echo "  make publish-pypi           - Publish to PyPI (requires credentials)"
	@echo ""
	@echo "MULTI & META TARGETS:"
	@echo "  make package-all            - Build all platform packages (requires native tools)"
	@echo "  make package-linux          - Build all Linux packages (deb, rpm, appimage)"
	@echo "  make package-docker         - Build containers only (deb, rpm)"
	@echo "  make publish-all            - Publish all artifacts to GitHub Release"
	@echo ""
	@echo "ARTIFACT MANAGEMENT:"
	@echo "  make show-artifacts         - List all built packages"
	@echo "  make show-deb-artifacts     - List Debian artifacts"
	@echo "  make show-rpm-artifacts     - List RPM artifacts"
	@echo "  make show-appimage-artifacts- List AppImage artifacts"
	@echo "  make show-python-artifacts  - List Python package artifacts"
	@echo "  make show-freebsd-artifacts - List FreeBSD artifacts"
	@echo "  make show-macos-artifacts   - List macOS artifacts"
	@echo "  make show-windows-artifacts - List Windows artifacts"
	@echo ""
	@echo "SYSTEM INFO:"
	@echo "  make sysinfo                - Display build system info"
	@echo ""



# =============================================================================
# System Information
# =============================================================================
.PHONY: sysinfo
sysinfo:
	@echo "╔═══════════════════════════════════════════════════════════════════════╗"
	@echo "║                    SYSTEM INFORMATION                                 ║"
	@echo "╚═══════════════════════════════════════════════════════════════════════╝"
	@echo "OS:               $(OS)"
	@echo "Architecture:     $(ARCH) (normalized: $(ARCH_NORMALIZED))"
	@echo "Python Version:   $$($(PYTHON) --version 2>&1)"
	@echo "ECLI Version:     $(PACKAGE_VERSION)"
	@echo "Release Dir:      $(RELEASE_DIR)"
	@echo ""
	@echo "Available Tools:"
	@command -v docker >/dev/null 2>&1 && echo "  ✓ Docker" || echo "  ✗ Docker (needed for package-deb-docker, package-rpm-docker)"
	@command -v gh >/dev/null 2>&1 && echo "  ✓ GitHub CLI (gh)" || echo "  ✗ GitHub CLI (needed for release targets)"
	@command -v pwsh >/dev/null 2>&1 && echo "  ✓ PowerShell 7+" || echo "  ✗ PowerShell 7+ (needed for Windows builds)"
	@command -v appimagetool >/dev/null 2>&1 && echo "  ✓ AppImageKit" || echo "  ✗ AppImageKit (needed for AppImage builds)"
	@command -v snapcraft >/dev/null 2>&1 && echo "  ✓ Snapcraft" || echo "  ✗ Snapcraft (needed for Snap builds)"
	@echo ""

# =============================================================================
# Development & QA
# =============================================================================
.PHONY: install
install:
	@echo "--> Installing dependencies..."
	$(UV) pip install --system -r requirements.txt
	-@[ -f requirements-dev.txt ] && $(UV) pip install --system -r requirements-dev.txt || true

.PHONY: run
run:
	$(PYTHON) main.py

.PHONY: clean
clean:
	rm -rf build/ dist/ releases/ .pytest_cache/ .ruff_cache/ .mypy_cache/ __pycache__
	-find . -type d -name "__pycache__" -exec rm -rf {} +
	-find . -type f -name "*.pyc" -delete
	@echo "--> Build artifacts cleaned."


# =============================================================================
# Packaging (Python / PyPI)
# =============================================================================
# Use:
# Build distribution packages for PyPI
#  `make package-pypi`            # Build wheel + source distribution
#
# Verify produced artifacts
#  `make show-python-artifacts`
#
# Publish to PyPI (requires ~/.pypirc or PYPI token in env)
#  `make publish-pypi`
# =============================================================================

PYPI_VERSION    ?= $(PACKAGE_VERSION)
PYPI_PKG_DIR    ?= dist
PYPI_WHEEL_FILE ?= $(PYPI_PKG_DIR)/ecli-$(PYPI_VERSION)-py3-none-any.whl
PYPI_SDIST_FILE ?= $(PYPI_PKG_DIR)/ecli-$(PYPI_VERSION).tar.gz

.PHONY: package-pypi
package-pypi: clean
	@echo "--> Building Python packages (wheel + sdist)..."
	$(PYTHON) -m build
	$(MAKE) package-pypi-assert

.PHONY: package-pypi-assert
package-pypi-assert:
	@test -n "$(PYPI_VERSION)" || (echo "PYPI_VERSION is empty"; exit 1)
	@test -f "$(PYPI_WHEEL_FILE)" || (echo "Missing $(PYPI_WHEEL_FILE)"; ls -R dist || true; exit 2)
	@test -f "$(PYPI_SDIST_FILE)" || (echo "Missing $(PYPI_SDIST_FILE)"; ls -R dist || true; exit 2)
	@echo "--> OK: $(PYPI_WHEEL_FILE)"
	@echo "--> OK: $(PYPI_SDIST_FILE)"

.PHONY: show-python-artifacts
show-python-artifacts:
	@echo "Version: $(PYPI_VERSION)"
	@ls -lh dist/ 2>/dev/null || echo "(no artifacts yet)"

.PHONY: publish-pypi
publish-pypi: package-pypi-assert
	@echo "--> Publishing to PyPI (requires credentials in ~/.pypirc or env)..."
	sh ./scripts/publish_pypi.sh
	@echo "--> Python packages published to PyPI."



# Use:
# Build and verify
#  `make package-deb`            # or: make package-deb-docker
#  `make show-deb-artifacts`
#
# Publish to GitHub Release (creates tag v<ver> if missing)
#  `make release-deb`
# ---------------------------

# Resolve version once to match [project].version in pyproject.toml.
DEB_PKG_VERSION ?= $(shell awk -F'"' '/^[[:space:]]*version[[:space:]]*=/ {print $$2; exit}' pyproject.toml 2>/dev/null)
DEB_PKG_DIR     ?= releases/$(DEB_PKG_VERSION)
DEB_PKG_FILE    ?= $(DEB_PKG_DIR)/ecli_$(DEB_PKG_VERSION)_linux_$(ARCH_NORMALIZED).deb
DEB_SHA_FILE    ?= $(DEB_PKG_FILE).sha256

.PHONY: package-deb
package-deb: clean
	./scripts/build-and-package-deb.sh
	$(MAKE) package-deb-assert

.PHONY: package-deb-docker
package-deb-docker:
	docker build -f docker/build-linux-deb.Dockerfile \
		--build-arg PYTHON_VERSION=3.11 \
		--build-arg DEBIAN_RELEASE=bullseye \
		-t ecli-deb:py311-bullseye .
	docker run --rm -v "$$(pwd):/app" -w /app ecli-deb:py311-bullseye
	$(MAKE) package-deb-assert

# --- Assertion helper: verify expected artifact names/locations ---------------
.PHONY: package-deb-assert
package-deb-assert:
	@test -n "$(DEB_PKG_VERSION)" || (echo "DEB_PKG_VERSION is empty (check pyproject.toml)"; exit 1)
	@test -f "$(DEB_PKG_FILE)" || (echo "Missing $(DEB_PKG_FILE)"; ls -R releases || true; exit 2)
	@test -f "$(DEB_SHA_FILE)" || (echo "Missing $(DEB_SHA_FILE)"; ls -R releases || true; exit 2)
	@echo "--> OK: $(DEB_PKG_FILE)"
	@echo "--> OK: $(DEB_SHA_FILE)"

# --- Convenience: list produced DEB artifacts ---------------------------------
.PHONY: show-deb-artifacts
show-deb-artifacts:
	@echo "Version: $(DEB_PKG_VERSION)"
	@ls -l $(DEB_PKG_DIR)/ecli_*_linux_*.deb* 2>/dev/null || echo "(no artifacts yet)"

# --- Release publisher: upload DEB to GitHub Release --------------------------
# Requires: GitHub CLI 'gh' (gh auth login) or GH_TOKEN/GITHUB_TOKEN in env.
# Steps:
#   1) Assert artifacts exist under releases/<version>/.
#   2) Ensure tag v<version> exists (create & push if missing).
#   3) Create release if missing (title, notes).
#   4) Upload .deb and .sha256 to the release (with --clobber).
.PHONY: release-deb
release-deb: package-deb-assert
	@test -n "$$(command -v gh)" || (echo "GitHub CLI 'gh' is required. Install: https://cli.github.com/"; exit 1)
	@echo "--> Ensuring git tag v$(DEB_PKG_VERSION) exists..."
	@if ! git rev-parse "v$(DEB_PKG_VERSION)" >/dev/null 2>&1; then \
		git tag "v$(DEB_PKG_VERSION)"; \
		git push origin "v$(DEB_PKG_VERSION)"; \
	else \
		echo "Tag v$(DEB_PKG_VERSION) already exists."; \
	fi
	@echo "--> Creating GitHub Release if missing..."
	@gh release view "v$(DEB_PKG_VERSION)" >/dev/null 2>&1 || \
	gh release create "v$(DEB_PKG_VERSION)" \
		--title "ECLI v$(DEB_PKG_VERSION)" \
		--notes "Debian/Ubuntu package for ECLI v$(DEB_PKG_VERSION).\n\nArtifacts:\n- ecli_$(DEB_PKG_VERSION)_linux_$(ARCH_NORMALIZED).deb\n- ecli_$(DEB_PKG_VERSION)_linux_$(ARCH_NORMALIZED).deb.sha256"
	@echo "--> Uploading DEB artifacts to GitHub Release..."
	@gh release upload "v$(DEB_PKG_VERSION)" \
		"$(DEB_PKG_FILE)" \
		"$(DEB_SHA_FILE)" \
		--clobber
	@echo "--> Release v$(DEB_PKG_VERSION) updated with DEB artifacts."


# ---------------------------
# Packaging (RPM)
# ---------------------------
# Use:
# Build and verify
#  `make package-rpm`            # or: make package-rpm-docker
#  `make show-rpm-artifacts`
#
# Publish to GitHub Release (creates tag v<ver> if missing)
#  `make release-rpm`
# ---------------------------

# Resolve version once to match [project].version in pyproject.toml.
RPM_PKG_VERSION ?= $(shell awk -F'"' '/^[[:space:]]*version[[:space:]]*=/ {print $$2; exit}' pyproject.toml 2>/dev/null)
RPM_PKG_DIR     ?= releases/$(RPM_PKG_VERSION)
RPM_PKG_FILE    ?= $(RPM_PKG_DIR)/ecli_$(RPM_PKG_VERSION)_linux_$(ARCH_NORMALIZED).rpm
RPM_SHA_FILE    ?= $(RPM_PKG_FILE).sha256

.PHONY: package-rpm
package-rpm: clean
	./scripts/build-and-package-rpm.sh
	$(MAKE) package-rpm-assert

.PHONY: package-rpm-docker
package-rpm-docker:
	docker build -f docker/build-linux-rpm.Dockerfile -t ecli-rpm:alma9 .
	docker run --rm -v "$$(pwd):/app" -w /app ecli-rpm:alma9
	$(MAKE) package-rpm-assert

# --- Assertion helper: verify expected artifact names/locations ---------------
.PHONY: package-rpm-assert
package-rpm-assert:
	@test -n "$(RPM_PKG_VERSION)" || (echo "RPM_PKG_VERSION is empty (check pyproject.toml)"; exit 1)
	@test -f "$(RPM_PKG_FILE)" || (echo "Missing $(RPM_PKG_FILE)"; ls -R releases || true; exit 2)
	@test -f "$(RPM_SHA_FILE)" || (echo "Missing $(RPM_SHA_FILE)"; ls -R releases || true; exit 2)
	@echo "--> OK: $(RPM_PKG_FILE)"
	@echo "--> OK: $(RPM_SHA_FILE)"

# --- Convenience: list produced RPM artifacts -------------------------------
.PHONY: show-rpm-artifacts
show-rpm-artifacts:
	@echo "Version: $(RPM_PKG_VERSION)"
	@ls -l $(RPM_PKG_DIR)/ecli_*_linux_*.rpm* 2>/dev/null || echo "(no artifacts yet)"

# --- Release publisher: upload RPM to GitHub Release --------------------------
# Requires: GitHub CLI 'gh' (gh auth login) or GH_TOKEN/GITHUB_TOKEN in env.
# Steps:
#   1) Assert artifacts exist under releases/<version>/.
#   2) Ensure tag v<version> exists (create & push if missing).
#   3) Create release if missing (title, notes).
#   4) Upload .rpm and .sha256 to the release (with --clobber).
.PHONY: release-rpm
release-rpm: package-rpm-assert
	@test -n "$$(command -v gh)" || (echo "GitHub CLI 'gh' is required. Install: https://cli.github.com/"; exit 1)
	@echo "--> Ensuring git tag v$(RPM_PKG_VERSION) exists..."
	@if ! git rev-parse "v$(RPM_PKG_VERSION)" >/dev/null 2>&1; then \
		git tag "v$(RPM_PKG_VERSION)"; \
		git push origin "v$(RPM_PKG_VERSION)"; \
	else \
		echo "Tag v$(RPM_PKG_VERSION) already exists."; \
	fi
	@echo "--> Creating GitHub Release if missing..."
	@gh release view "v$(RPM_PKG_VERSION)" >/dev/null 2>&1 || \
	gh release create "v$(RPM_PKG_VERSION)" \
		--title "ECLI v$(RPM_PKG_VERSION)" \
		--notes "RHEL/AlmaLinux/Rocky/Fedora package for ECLI v$(RPM_PKG_VERSION).\n\nArtifacts:\n- ecli_$(RPM_PKG_VERSION)_linux_$(ARCH_NORMALIZED).rpm\n- ecli_$(RPM_PKG_VERSION)_linux_$(ARCH_NORMALIZED).rpm.sha256"
	@echo "--> Uploading RPM artifacts to GitHub Release..."
	@gh release upload "v$(RPM_PKG_VERSION)" \
		"$(RPM_PKG_FILE)" \
		"$(RPM_SHA_FILE)" \
		--clobber
	@echo "--> Release v$(RPM_PKG_VERSION) updated with RPM artifacts."


# ---------------------------
# Packaging (AppImage)
# ---------------------------
# Use:
# Build an AppImage (works on any Linux distro)
#  `make package-appimage`        # Build AppImage
#
# Verify produced artifacts
#  `make show-appimage-artifacts`
#
# Publish to GitHub Release
#  `make release-appimage`
# ---------------------------

APPIMAGE_VERSION ?= $(PACKAGE_VERSION)
APPIMAGE_PKG_DIR ?= $(RELEASE_DIR)
APPIMAGE_FILE    ?= $(APPIMAGE_PKG_DIR)/ecli_$(APPIMAGE_VERSION)_linux_$(ARCH_NORMALIZED).AppImage
APPIMAGE_SHA_FILE?= $(APPIMAGE_FILE).sha256

.PHONY: package-appimage
package-appimage: clean
	@command -v appimagetool >/dev/null 2>&1 || (echo "appimagetool not found. Install AppImageKit: https://github.com/AppImage/AppImageKit"; exit 1)
	@echo "--> Building AppImage..."
	bash ./scripts/package_appimage.sh "$(APPIMAGE_VERSION)" "$(ARCH_NORMALIZED)"
	@mkdir -p $(APPIMAGE_PKG_DIR)
	@test -f "$(APPIMAGE_FILE)" || (echo "AppImage build may have failed"; exit 1)
	@echo "--> Generating checksum..."
	cd $(APPIMAGE_PKG_DIR) && sha256sum $$(basename $(APPIMAGE_FILE)) > $$(basename $(APPIMAGE_SHA_FILE))
	$(MAKE) package-appimage-assert

.PHONY: package-appimage-assert
package-appimage-assert:
	@test -n "$(APPIMAGE_VERSION)" || (echo "APPIMAGE_VERSION is empty"; exit 1)
	@test -f "$(APPIMAGE_FILE)" || (echo "Missing $(APPIMAGE_FILE)"; ls -R $(RELEASE_DIR) || true; exit 2)
	@test -f "$(APPIMAGE_SHA_FILE)" || (echo "Missing $(APPIMAGE_SHA_FILE)"; ls -R $(RELEASE_DIR) || true; exit 2)
	@echo "--> OK: $(APPIMAGE_FILE)"
	@echo "--> OK: $(APPIMAGE_SHA_FILE)"

.PHONY: show-appimage-artifacts
show-appimage-artifacts:
	@echo "Version: $(APPIMAGE_VERSION) Arch: $(ARCH_NORMALIZED)"
	@ls -lh $(APPIMAGE_PKG_DIR)/ecli_*_linux_*.AppImage* 2>/dev/null || echo "(no artifacts yet)"

.PHONY: release-appimage
release-appimage: package-appimage-assert
	@test -n "$$(command -v gh)" || (echo "GitHub CLI 'gh' is required"; exit 1)
	@if ! git rev-parse "v$(APPIMAGE_VERSION)" >/dev/null 2>&1; then \
		git tag "v$(APPIMAGE_VERSION)"; git push origin "v$(APPIMAGE_VERSION)"; \
	fi
	@gh release view "v$(APPIMAGE_VERSION)" >/dev/null 2>&1 || \
	  gh release create "v$(APPIMAGE_VERSION)" --title "ECLI v$(APPIMAGE_VERSION)" \
	    --notes "AppImage (cross-distro) for Linux $(ARCH_NORMALIZED) - ECLI v$(APPIMAGE_VERSION)."
	@gh release upload "v$(APPIMAGE_VERSION)" "$(APPIMAGE_FILE)" "$(APPIMAGE_SHA_FILE)" --clobber
	@echo "--> Release v$(APPIMAGE_VERSION) updated with AppImage artifacts."


# ---------------------------
# Packaging (Snap)
# ---------------------------
# Use:
# Build a Snap package
#  `make package-snap`            # Build snap (requires snapcraft)
#
# Verify produced artifacts
#  `make show-snap-artifacts`
#
# Publish to Snap Store (requires authentication)
#  `make release-snap`
#
# Note: Snap building requires snapcraft tool and assumes snapcraft.yaml exists
# ---------------------------

SNAP_VERSION  ?= $(PACKAGE_VERSION)
SNAP_PKG_DIR  ?= .
SNAP_FILE     ?= $(SNAP_PKG_DIR)/ecli_$(SNAP_VERSION)_linux_$(ARCH_NORMALIZED).snap

.PHONY: package-snap
package-snap:
	@command -v snapcraft >/dev/null 2>&1 || (echo "snapcraft not found. Install: sudo snap install snapcraft --classic"; exit 1)
	@test -f snapcraft.yaml || (echo "snapcraft.yaml not found in project root"; exit 1)
	@echo "--> Building Snap..."
	snapcraft
	@mkdir -p $(RELEASE_DIR)
	@test -f "*.snap" && mv *.snap $(RELEASE_DIR)/ecli_$(SNAP_VERSION)_linux_$(ARCH_NORMALIZED).snap || true
	$(MAKE) package-snap-assert

.PHONY: package-snap-assert
package-snap-assert:
	@test -f "$(RELEASE_DIR)/ecli_$(SNAP_VERSION)_linux_$(ARCH_NORMALIZED).snap" || (echo "Snap build may have failed"; ls -R $(RELEASE_DIR) || true; exit 1)
	@echo "--> OK: $(RELEASE_DIR)/ecli_$(SNAP_VERSION)_linux_$(ARCH_NORMALIZED).snap"

.PHONY: show-snap-artifacts
show-snap-artifacts:
	@echo "Version: $(SNAP_VERSION)"
	@ls -lh $(RELEASE_DIR)/*.snap 2>/dev/null || echo "(no snap artifacts yet)"

.PHONY: release-snap
release-snap: package-snap-assert
	@echo "--> Publishing to Snap Store (requires authentication)..."
	@echo "    Run: snapcraft login"
	@echo "    Then: snapcraft upload --release=stable $(RELEASE_DIR)/ecli_*.snap"


# ---------------------------
# Packaging (Archives)
# ---------------------------
# Use:
# Build tar.gz archive
#  `make package-tar-linux`       # Build Linux tar.gz
#
# ---------------------------

TAR_VERSION   ?= $(PACKAGE_VERSION)
TAR_PKG_DIR   ?= $(RELEASE_DIR)
TAR_LINUX_FILE?= $(TAR_PKG_DIR)/ecli_$(TAR_VERSION)_linux_$(ARCH_NORMALIZED).tar.gz

.PHONY: package-tar-linux
package-tar-linux: clean
	@echo "--> Creating Linux tar.gz archive..."
	@mkdir -p $(TAR_PKG_DIR)
	@$(PYTHON) -m pip install --user -q . 2>/dev/null || true
	@echo "ECLI v$(TAR_VERSION)" > RELEASE_NOTES.txt
	@tar --exclude='.git' --exclude='.venv' --exclude='build' --exclude='dist' \
		--exclude='__pycache__' --exclude='.pytest_cache' \
		-czf "$(TAR_LINUX_FILE)" . \
		--transform 's,^,ecli-$(TAR_VERSION)/,'
	@rm -f RELEASE_NOTES.txt
	@cd $(TAR_PKG_DIR) && sha256sum $$(basename $(TAR_LINUX_FILE)) > $$(basename $(TAR_LINUX_FILE)).sha256
	@echo "--> OK: $(TAR_LINUX_FILE)"
	@echo "--> OK: $(TAR_LINUX_FILE).sha256"

.PHONY: show-tar-artifacts
show-tar-artifacts:
	@echo "Version: $(TAR_VERSION) Arch: $(ARCH_NORMALIZED)"
	@ls -lh $(TAR_PKG_DIR)/*.tar.gz* 2>/dev/null || echo "(no tar artifacts yet)"



# Use:
# Build (choose one):
#  - Native on a FreeBSD 14.x host/VM:
#       `make package-freebsd`
#  - Reproducible chroot (Docker-like, requires root on FreeBSD):
#       `make package-freebsd-chroot`
#  - Via FreeBSD Ports (local port skeleton, requires root on FreeBSD):
#       `make package-freebsd-port`
#  - In CI (GitHub Actions FreeBSD VM):
#       `make package-freebsd-ci`
#
# Verify produced artifacts:
#   make show-freebsd-artifacts
#
# Publish to GitHub Release (creates tag v<version> if missing, then uploads):
#   make release-freebsd
# ---------------------------

# Resolve version once (fallback to parsing pyproject.toml if not set above).
# This must match [project].version in pyproject.toml.
FREEBSD_PKG_VERSION ?= $(shell awk -F'"' '/^[[:space:]]*version[[:space:]]*=/ {print $$2; exit}' pyproject.toml 2>/dev/null)
FREEBSD_PKG_DIR     ?= releases/$(FREEBSD_PKG_VERSION)
FREEBSD_PKG_FILE    ?= $(FREEBSD_PKG_DIR)/ecli_$(FREEBSD_PKG_VERSION)_freebsd_$(ARCH_NORMALIZED).pkg
FREEBSD_SHA_FILE    ?= $(FREEBSD_PKG_FILE).sha256

# --- CI (GitHub Actions) ------------------------------------------------------
# Builds .pkg inside a FreeBSD 14.3 VM using vmactions/freebsd-vm.
.PHONY: package-freebsd-ci
package-freebsd-ci:
	@echo "--> Triggering GitHub Actions workflow for FreeBSD .pkg build..."
	@echo "    Open: https://github.com/ssobol77/ecli/actions/workflows/freebsd-pkg.yml"
	@echo "    Click: 'Run workflow' (branch: main)."
	@echo "    Result: artifact in Actions and committed into releases/<version>/ if enabled."
	@echo ""
	@echo "Optional via GitHub CLI:"
	@echo "  gh workflow run freebsd-pkg.yml"

# --- Local build on a real FreeBSD host/VM ------------------------------------
# Runs the native packager script (PyInstaller -> stage -> pkg create).
.PHONY: package-freebsd
package-freebsd: clean
	sh ./scripts/build-and-package-freebsd.sh
	$(MAKE) package-freebsd-assert

# --- "Docker-like" reproducible build via chroot (on FreeBSD host) ------------
# Creates a clean 14.3 rootfs (base.txz), installs deps, runs the same build.
# Requires root; keeps the host clean and returns artifacts into ./releases/.
.PHONY: package-freebsd-chroot
package-freebsd-chroot: clean
	sudo tools/freebsd-chroot-build.sh
	$(MAKE) package-freebsd-assert

# --- Build via FreeBSD Ports (local port skeleton) ----------------------------
# Uses scripts/build_freebsd_port.sh to create a local port and `make package`.
# Produces the same artifact names under releases/<version>/.
.PHONY: package-freebsd-port
package-freebsd-port: clean
	sudo sh ./scripts/build_freebsd_port.sh
	$(MAKE) package-freebsd-assert

# --- Assertion helper: verify expected artifact names/locations ----------------
.PHONY: package-freebsd-assert
package-freebsd-assert:
	@test -n "$(FREEBSD_PKG_VERSION)" || (echo "FREEBSD_PKG_VERSION is empty (check pyproject.toml)"; exit 1)
	@test -f "$(FREEBSD_PKG_FILE)" || (echo "Missing $(FREEBSD_PKG_FILE)"; ls -R releases || true; exit 2)
	@test -f "$(FREEBSD_SHA_FILE)" || (echo "Missing $(FREEBSD_SHA_FILE)"; ls -R releases || true; exit 2)
	@echo "--> OK: $(FREEBSD_PKG_FILE)"
	@echo "--> OK: $(FREEBSD_SHA_FILE)"

# --- Convenience: list produced FreeBSD artifacts -----------------------------
.PHONY: show-freebsd-artifacts
show-freebsd-artifacts:
	@echo "Version: $(FREEBSD_PKG_VERSION)"
	@ls -l $(FREEBSD_PKG_DIR)/ecli_*_freebsd_*.pkg* 2>/dev/null || echo "(no artifacts yet)"

# --- Not supported via Docker --------------------------------------------------
# FreeBSD userland cannot be containerized on a Linux kernel Docker host.
.PHONY: package-freebsd-docker
package-freebsd-docker:
	@echo "Local FreeBSD VM via Docker is not possible on Linux:"
	@echo "  vmactions/freebsd-vm requires a GA runner; Docker uses a Linux kernel."
	@echo "Use: 'make package-freebsd-ci' (CI VM) or build on a real FreeBSD host:"
	@echo "  - make package-freebsd"
	@echo "  - make package-freebsd-chroot"
	@echo "  - make package-freebsd-port"
	@exit 125

# --- Release publisher: upload FreeBSD pkg to GitHub Release ------------------
# Requires: GitHub CLI 'gh' (gh auth login) and access to push tags/releases.
# Steps:
#   1) Assert artifacts exist under releases/<version>/.
#   2) Ensure tag v<version> exists (create & push if missing).
#   3) Create release if missing (title, notes).
#   4) Upload .pkg and .sha256 to the release (with --clobber).
.PHONY: release-freebsd
release-freebsd: package-freebsd-assert
	@test -n "$$(command -v gh)" || (echo "GitHub CLI 'gh' is required. Install: https://cli.github.com/"; exit 1)
	@echo "--> Ensuring git tag v$(FREEBSD_PKG_VERSION) exists..."
	@if ! git rev-parse "v$(FREEBSD_PKG_VERSION)" >/dev/null 2>&1; then \
		git tag "v$(FREEBSD_PKG_VERSION)"; \
		git push origin "v$(FREEBSD_PKG_VERSION)"; \
	else \
		echo "Tag v$(FREEBSD_PKG_VERSION) already exists."; \
	fi
	@echo "--> Creating GitHub Release if missing..."
	@gh release view "v$(FREEBSD_PKG_VERSION)" >/dev/null 2>&1 || \
	gh release create "v$(FREEBSD_PKG_VERSION)" \
		--title "ECLI v$(FREEBSD_PKG_VERSION)" \
		--notes "FreeBSD package for ECLI v$(FREEBSD_PKG_VERSION).\n\nArtifacts:\n- ecli_$(FREEBSD_PKG_VERSION)_freebsd_$(ARCH_NORMALIZED).pkg\n- ecli_$(FREEBSD_PKG_VERSION)_freebsd_$(ARCH_NORMALIZED).pkg.sha256"
	@echo "--> Uploading artifacts to GitHub Release..."
	@gh release upload "v$(FREEBSD_PKG_VERSION)" \
		"$(FREEBSD_PKG_FILE)" \
		"$(FREEBSD_SHA_FILE)" \
		--clobber
	@echo "--> Release v$(FREEBSD_PKG_VERSION) updated with FreeBSD artifacts."


# ---------------------------
# Packaging (macOS)
# ---------------------------
# Use:
# Build (choose one):
#  - Local on macOS 12+ with Python 3.11:
#       `make package-macos`
#    (Produces a DMG via PyInstaller .app → hdiutil)
#
# Verify produced artifacts (strict naming & location):
#   `make show-macos-artifacts`
#
# Publish to GitHub Release (creates tag v<version> if missing, then uploads):
#   `make release-macos`
#
# Notes:
#  - Output files (strict):
#       releases/<version>/ecli_<version>_macos_<arch>.dmg
#       releases/<version>/ecli_<version>_macos_<arch>.dmg.sha256
#  - <arch> is normalized from the host (x86_64 or arm64).
#  - For CI builds, see `.github/workflows/macos-dmg.yml`.
# ---------------------------

MACOS_PKG_VERSION ?= $(shell awk -F'"' '/^[[:space:]]*version[[:space:]]*=/ {print $$2; exit}' pyproject.toml 2>/dev/null)
MACOS_ARCH        ?= $(shell uname -m)
MACOS_PKG_DIR     ?= releases/$(MACOS_PKG_VERSION)
MACOS_PKG_FILE    ?= $(MACOS_PKG_DIR)/ecli_$(MACOS_PKG_VERSION)_macos_$(MACOS_ARCH).dmg
MACOS_SHA_FILE    ?= $(MACOS_PKG_FILE).sha256

.PHONY: package-macos
package-macos: clean
	sh ./scripts/build-and-package-macos.sh
	$(MAKE) package-macos-assert

.PHONY: package-macos-assert
package-macos-assert:
	@test -n "$(MACOS_PKG_VERSION)" || (echo "MACOS_PKG_VERSION empty (pyproject.toml)"; exit 1)
	@test -f "$(MACOS_PKG_FILE)"    || (echo "Missing $(MACOS_PKG_FILE)"; ls -R releases || true; exit 2)
	@test -f "$(MACOS_SHA_FILE)"    || (echo "Missing $(MACOS_SHA_FILE)"; ls -R releases || true; exit 3)
	@echo "--> OK: $(MACOS_PKG_FILE)"
	@echo "--> OK: $(MACOS_SHA_FILE)"

.PHONY: show-macos-artifacts
show-macos-artifacts:
	@echo "Version: $(MACOS_PKG_VERSION) Arch: $(MACOS_ARCH)"
	@ls -l $(MACOS_PKG_DIR)/ecli_*_macos_* 2>/dev/null || echo "(no artifacts yet)"

# Publish to GitHub Release
.PHONY: release-macos
release-macos: package-macos-assert
	@test -n "$$(command -v gh)" || (echo "GitHub CLI 'gh' required"; exit 1)
	@if ! git rev-parse "v$(MACOS_PKG_VERSION)" >/dev/null 2>&1; then \
		git tag "v$(MACOS_PKG_VERSION)"; git push origin "v$(MACOS_PKG_VERSION)"; \
	fi
	@gh release view "v$(MACOS_PKG_VERSION)" >/dev/null 2>&1 || \
	  gh release create "v$(MACOS_PKG_VERSION)" --title "ECLI v$(MACOS_PKG_VERSION)" \
	    --notes "macOS package (DMG) for ECLI v$(MACOS_PKG_VERSION)."
	@gh release upload "v$(MACOS_PKG_VERSION)" "$(MACOS_PKG_FILE)" "$(MACOS_SHA_FILE)" --clobber
	@echo "--> Release v$(MACOS_PKG_VERSION) updated with macOS artifacts."


# ---------------------------
# Packaging (Windows)
# ---------------------------
# Use:
# Build (local, PowerShell 7+ on Windows 10/11 x64):
#   `make package-windows`
#   (PyInstaller → NSIS; produces a signed or unsigned installer depending on your setup)
#
# Verify produced artifacts (strict naming & location):
#   `make show-windows-artifacts`
#
# Publish to GitHub Release (creates tag v<version> if missing, then uploads):
#   `make release-windows`
#
# Notes:
#  - Output files (strict):
#       releases/<version>/ecli_<version>_win_x86_64.exe
#       releases/<version>/ecli_<version>_win_x86_64.exe.sha256
#  - For CI builds, see `.github/workflows/windows-installer.yml`.
#  - If code signing is required, integrate `signtool` before checksum generation.
# ---------------------------


WIN_PKG_VERSION ?= $(shell awk -F'"' '/^[[:space:]]*version[[:space:]]*=/ {print $$2; exit}' pyproject.toml 2>/dev/null)
WIN_PKG_DIR     ?= releases/$(WIN_PKG_VERSION)
WIN_PKG_FILE    ?= $(WIN_PKG_DIR)/ecli_$(WIN_PKG_VERSION)_win_x86_64.exe
WIN_SHA_FILE    ?= $(WIN_PKG_FILE).sha256

# Local Windows build (run in PowerShell on Windows host)
.PHONY: package-windows
package-windows: clean
	pwsh -File ./scripts/build-and-package-windows.ps1
	$(MAKE) package-windows-assert

.PHONY: package-windows-assert
package-windows-assert:
	@test -n "$(WIN_PKG_VERSION)" || (echo "WIN_PKG_VERSION empty (pyproject.toml)"; exit 1)
	@test -f "$(WIN_PKG_FILE)"    || (echo "Missing $(WIN_PKG_FILE)"; ls -R releases || true; exit 2)
	@test -f "$(WIN_SHA_FILE)"    || (echo "Missing $(WIN_SHA_FILE)"; ls -R releases || true; exit 3)
	@echo "--> OK: $(WIN_PKG_FILE)"
	@echo "--> OK: $(WIN_SHA_FILE)"

.PHONY: show-windows-artifacts
show-windows-artifacts:
	@echo "Version: $(WIN_PKG_VERSION)"
	@ls -l $(WIN_PKG_DIR)/ecli_*_win_*.exe* 2>/dev/null || echo "(no artifacts yet)"

# Publish to GitHub Release
.PHONY: release-windows
release-windows: package-windows-assert
	@test -n "$$(command -v gh)" || (echo "GitHub CLI 'gh' required"; exit 1)
	@if ! git rev-parse "v$(WIN_PKG_VERSION)" >/dev/null 2>&1; then \
		git tag "v$(WIN_PKG_VERSION)"; git push origin "v$(WIN_PKG_VERSION)"; \
	fi
	@gh release view "v$(WIN_PKG_VERSION)" >/dev/null 2>&1 || \
	  gh release create "v$(WIN_PKG_VERSION)" --title "ECLI v$(WIN_PKG_VERSION)" \
	    --notes "Windows x64 installer for ECLI v$(WIN_PKG_VERSION)."
	@gh release upload "v$(WIN_PKG_VERSION)" "$(WIN_PKG_FILE)" "$(WIN_SHA_FILE)" --clobber
	@echo "--> Release v$(WIN_PKG_VERSION) updated with Windows artifacts."


# =============================================================================
# Meta Targets - Build Multiple Packages
# =============================================================================

# Build all platform packages (requires all native tools)
.PHONY: package-all
package-all: package-pypi package-deb-docker package-rpm-docker package-appimage package-freebsd package-macos package-windows
	@echo ""
	@echo "╔═══════════════════════════════════════════════════════════════════════╗"
	@echo "║                  ALL PACKAGES BUILT SUCCESSFULLY                      ║"
	@echo "╚═══════════════════════════════════════════════════════════════════════╝"
	@$(MAKE) show-artifacts

# Build all Linux packages (Docker containers)
.PHONY: package-docker
package-docker: package-deb-docker package-rpm-docker
	@echo "--> All Linux packages built via Docker."

# Build all Linux packages (including AppImage and tar.gz)
.PHONY: package-linux
package-linux: package-deb-docker package-rpm-docker package-appimage package-tar-linux
	@echo ""
	@echo "╔═══════════════════════════════════════════════════════════════════════╗"
	@echo "║                 ALL LINUX PACKAGES BUILT SUCCESSFULLY                 ║"
	@echo "╚═══════════════════════════════════════════════════════════════════════╝"
	@$(MAKE) show-artifacts

# Build all desktop packages (macOS and Windows)
.PHONY: package-desktop
package-desktop: package-macos package-windows
	@echo "--> All desktop packages built."

# Publish all packages to GitHub Release
.PHONY: publish-all
publish-all: release-deb release-rpm release-appimage release-freebsd release-macos release-windows publish-pypi
	@echo ""
	@echo "╔═══════════════════════════════════════════════════════════════════════╗"
	@echo "║              ALL PACKAGES PUBLISHED TO GITHUB RELEASE                 ║"
	@echo "╚═══════════════════════════════════════════════════════════════════════╝"


# =============================================================================
# Artifact Inspection
# =============================================================================

.PHONY: show-artifacts
show-artifacts:
	@echo ""
	@echo "╔═══════════════════════════════════════════════════════════════════════╗"
	@echo "║                     BUILT ARTIFACTS SUMMARY                           ║"
	@echo "╚═══════════════════════════════════════════════════════════════════════╝"
	@echo ""
	@echo "Python (PyPI):"
	@ls -lh dist/*.whl dist/*.tar.gz 2>/dev/null || echo "  (not built)"
	@echo ""
	@echo "Linux (Debian/Ubuntu):"
	@ls -lh $(RELEASE_DIR)/ecli_*_linux_*.deb* 2>/dev/null || echo "  (not built)"
	@echo ""
	@echo "Linux (Fedora/RHEL/Rocky):"
	@ls -lh $(RELEASE_DIR)/ecli_*_linux_*.rpm* 2>/dev/null || echo "  (not built)"
	@echo ""
	@echo "Linux (AppImage):"
	@ls -lh $(RELEASE_DIR)/ecli_*_linux_*.AppImage* 2>/dev/null || echo "  (not built)"
	@echo ""
	@echo "Linux (Archives):"
	@ls -lh $(RELEASE_DIR)/*.tar.gz* 2>/dev/null || echo "  (not built)"
	@echo ""
	@echo "FreeBSD:"
	@ls -lh $(RELEASE_DIR)/ecli_*_freebsd_*.pkg* 2>/dev/null || echo "  (not built)"
	@echo ""
	@echo "macOS:"
	@ls -lh $(RELEASE_DIR)/ecli_*_macos_*.dmg* 2>/dev/null || echo "  (not built)"
	@echo ""
	@echo "Windows:"
	@ls -lh $(RELEASE_DIR)/ecli_*_win_*.exe* 2>/dev/null || echo "  (not built)"
	@echo ""

# =============================================================================
