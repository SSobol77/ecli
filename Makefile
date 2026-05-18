# SPDX-License-Identifier: Apache-2.0
#
# Project: Ecli
# File: Makefile
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file in the project root for full license text.

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

PACKAGE_VERSION := $(shell $(PYTHON) -c 'import pathlib, tomllib; print(tomllib.loads(pathlib.Path("pyproject.toml").read_text())["project"]["version"])' 2>/dev/null || awk -F'"' '/^[[:space:]]*version[[:space:]]*=/ {print $$2; exit}' pyproject.toml 2>/dev/null || echo 0.0.0)

# Release directory
RELEASE_DIR := releases/$(PACKAGE_VERSION)
LINUX_ARCH ?= $(ARCH_NORMALIZED)
FREEBSD_ARCH ?= $(ARCH_NORMALIZED)
MACOS_ARCH ?= universal2
WIN_ARCH ?= x86_64

-include $(RELEASE_DIR)/.linux.env
-include $(RELEASE_DIR)/.freebsd.env
-include $(RELEASE_DIR)/.macos.env
-include $(RELEASE_DIR)/.win.env

define verify_sha256
	@scripts/verify-artifact.sh "$(1)"
endef

define validate_if_present
	@if [ -f "$(1)" ] || [ -f "$(1).sha256" ]; then \
		$(MAKE) $(2); \
	else \
		echo "SKIP: $(3) artifact not built: $(1)"; \
	fi
endef

define assert_current_release_file
	@case "$(1)" in \
		releases/$(PACKAGE_VERSION)/*) ;; \
		*) echo "Artifact path is outside current release directory releases/$(PACKAGE_VERSION): $(1)"; exit 8 ;; \
	esac
endef

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
	@echo "  make clean                  - Clean intermediate build artifacts"
	@echo "  make distclean              - Clean intermediates and release outputs"
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
	@echo "  make package-windows        - Build Windows EXE artifacts (native, PowerShell)"
	@echo ""
	@echo "PYTHON PACKAGES:"
	@echo "  make package-pypi           - Build wheel + sdist (for PyPI)"
	@echo "  make publish-pypi           - Publish to PyPI (requires credentials)"
	@echo ""
	@echo "MULTI & META TARGETS:"
	@echo "  make package-all-host       - Build packages supported by this host OS"
	@echo "  make package-all            - Alias for package-all-host"
	@echo "  make package-linux          - Build all Linux packages (deb, rpm, appimage)"
	@echo "  make package-docker         - Build containers only (deb, rpm)"
	@echo "  make publish-all            - Publish all artifacts to GitHub Release"
	@echo "  make validate-gate2         - Validate built Gate 2 release contracts"
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
	@$(UV) pip install --system -e ".[dev]" || \
		( \
			echo "--> System Python rejected install; syncing local uv environment instead."; \
			$(UV) sync --extra dev; \
		)

.PHONY: run
run:
	$(PYTHON) main.py

.PHONY: clean
clean:
	rm -rf build/ dist/ .pytest_cache/ .ruff_cache/ .mypy_cache/ __pycache__
	-find . -type d -name "__pycache__" -exec rm -rf {} +
	-find . -type f -name "*.pyc" -delete
	@echo "--> Intermediate build artifacts cleaned."

.PHONY: distclean
distclean: clean
	rm -rf releases/
	@echo "--> Release artifacts cleaned."


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
PYPI_PKG_DIR    ?= $(RELEASE_DIR)
PYPI_DIST_NAME   ?= ecli_editor
PYPI_WHEEL_FILE ?= $(PYPI_PKG_DIR)/$(PYPI_DIST_NAME)-$(PYPI_VERSION)-py3-none-any.whl
PYPI_SDIST_FILE ?= $(PYPI_PKG_DIR)/$(PYPI_DIST_NAME)-$(PYPI_VERSION).tar.gz

.PHONY: package-pypi
package-pypi: clean validate-runtime-imports
	@echo "--> Building Python packages (wheel + sdist)..."
	@mkdir -p "$(PYPI_PKG_DIR)"
	@rm -f "$(PYPI_WHEEL_FILE)" "$(PYPI_WHEEL_FILE).sha256" "$(PYPI_SDIST_FILE)" "$(PYPI_SDIST_FILE).sha256"
	$(PYTHON) -m build --outdir "$(PYPI_PKG_DIR)"
	$(PYTHON) -m twine check --strict "$(PYPI_WHEEL_FILE)" "$(PYPI_SDIST_FILE)"
	@for artifact in "$(PYPI_WHEEL_FILE)" "$(PYPI_SDIST_FILE)"; do \
		dir="$$(dirname "$$artifact")"; \
		base="$$(basename "$$artifact")"; \
		if command -v sha256sum >/dev/null 2>&1; then \
			(cd "$$dir" && sha256sum "$$base" > "$$base.sha256"); \
		elif command -v shasum >/dev/null 2>&1; then \
			(cd "$$dir" && shasum -a 256 "$$base" > "$$base.sha256"); \
		else \
			echo "Missing SHA256 tool: sha256sum or shasum"; \
			exit 5; \
		fi; \
	done
	$(MAKE) package-pypi-assert

.PHONY: package-pypi-assert
package-pypi-assert:
	@test -n "$(PYPI_VERSION)" || (echo "PYPI_VERSION is empty"; exit 1)
	$(call assert_current_release_file,$(PYPI_WHEEL_FILE))
	$(call assert_current_release_file,$(PYPI_SDIST_FILE))
	$(call verify_sha256,$(PYPI_WHEEL_FILE))
	$(call verify_sha256,$(PYPI_SDIST_FILE))
	@echo "--> OK: $(PYPI_WHEEL_FILE)"
	@echo "--> OK: $(PYPI_WHEEL_FILE).sha256"
	@echo "--> OK: $(PYPI_SDIST_FILE)"
	@echo "--> OK: $(PYPI_SDIST_FILE).sha256"

.PHONY: show-python-artifacts
show-python-artifacts:
	@echo "Version: $(PYPI_VERSION)"
	@ls -lh "$(PYPI_PKG_DIR)"/*.whl "$(PYPI_PKG_DIR)"/*.tar.gz 2>/dev/null || echo "(no artifacts yet)"

.PHONY: publish-pypi
publish-pypi: package-pypi-assert
	@echo "--> Publishing to PyPI (requires credentials in ~/.pypirc or env)..."
	sh ./scripts/publish_pypi.sh
	@echo "--> Python packages published to PyPI."

.PHONY: _ensure-tag
_ensure-tag:
	@test -n "$(VERSION)" || (echo "VERSION is required"; exit 1)
	@tag="v$(VERSION)"; \
	echo "--> Ensuring git tag $$tag exists..."; \
	git fetch --tags origin "$$tag" >/dev/null 2>&1 || true; \
	if git show-ref --tags --verify --quiet "refs/tags/$$tag"; then \
		echo "Tag $$tag already exists locally."; \
		exit 0; \
	fi; \
	if git ls-remote --exit-code --tags origin "refs/tags/$$tag" >/dev/null 2>&1; then \
		echo "Tag $$tag exists on origin; fetching it."; \
		git fetch origin "refs/tags/$$tag:refs/tags/$$tag"; \
		exit 0; \
	fi; \
	git tag "$$tag"; \
	if ! git push origin "$$tag"; then \
		echo "Tag push raced or failed; fetching origin tag for $$tag."; \
		git fetch origin "refs/tags/$$tag:refs/tags/$$tag" >/dev/null 2>&1 || true; \
		git show-ref --tags --verify --quiet "refs/tags/$$tag" || (echo "Unable to ensure tag $$tag"; exit 1); \
	fi



# Use:
# Build and verify
#  `make package-deb`            # or: make package-deb-docker
#  `make show-deb-artifacts`
#
# Publish to GitHub Release (creates tag v<ver> if missing)
#  `make release-deb`
# ---------------------------

# Resolve version once to match [project].version in pyproject.toml.
DEB_PKG_VERSION ?= $(PACKAGE_VERSION)
DEB_PKG_DIR     ?= releases/$(DEB_PKG_VERSION)
DEB_PKG_FILE    ?= $(DEB_PKG_DIR)/ecli_$(DEB_PKG_VERSION)_linux_$(LINUX_ARCH).deb
DEB_SHA_FILE    ?= $(DEB_PKG_FILE).sha256

.PHONY: package-deb
package-deb: clean validate-runtime-imports
	./scripts/build-and-package-deb.sh
	$(MAKE) package-deb-assert

.PHONY: package-deb-docker
package-deb-docker: clean validate-runtime-imports
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
	$(call assert_current_release_file,$(DEB_PKG_FILE))
	$(call verify_sha256,$(DEB_PKG_FILE))
	@./scripts/verify_runtime.sh "$(DEB_PKG_FILE)"
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
	@$(MAKE) _ensure-tag VERSION="$(DEB_PKG_VERSION)"
	@echo "--> Creating GitHub Release if missing..."
	@tmpfile="$$(mktemp)"; \
	trap 'rm -f "$$tmpfile"' EXIT; \
	printf '%s\n' \
		"Debian/Ubuntu package for ECLI v$(DEB_PKG_VERSION)." \
		"" \
		"Artifacts:" \
		"- $$(basename "$(DEB_PKG_FILE)")" \
		"- $$(basename "$(DEB_SHA_FILE)")" > "$$tmpfile"; \
	gh release view "v$(DEB_PKG_VERSION)" >/dev/null 2>&1 || \
	gh release create "v$(DEB_PKG_VERSION)" \
		--title "ECLI v$(DEB_PKG_VERSION)" \
		--notes-file "$$tmpfile"
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
RPM_PKG_VERSION ?= $(PACKAGE_VERSION)
RPM_PKG_DIR     ?= releases/$(RPM_PKG_VERSION)
RPM_PKG_FILE    ?= $(RPM_PKG_DIR)/ecli_$(RPM_PKG_VERSION)_linux_$(LINUX_ARCH).rpm
RPM_SHA_FILE    ?= $(RPM_PKG_FILE).sha256

.PHONY: package-rpm
package-rpm: clean validate-runtime-imports
	./scripts/build-and-package-rpm.sh
	$(MAKE) package-rpm-assert

.PHONY: package-rpm-docker
package-rpm-docker: clean validate-runtime-imports
	docker build -f docker/build-linux-rpm.Dockerfile -t ecli-rpm:alma9 .
	docker run --rm -v "$$(pwd):/app" -w /app ecli-rpm:alma9
	$(MAKE) package-rpm-assert

# --- Assertion helper: verify expected artifact names/locations ---------------
.PHONY: package-rpm-assert
package-rpm-assert:
	@test -n "$(RPM_PKG_VERSION)" || (echo "RPM_PKG_VERSION is empty (check pyproject.toml)"; exit 1)
	$(call assert_current_release_file,$(RPM_PKG_FILE))
	$(call verify_sha256,$(RPM_PKG_FILE))
	@./scripts/verify_runtime.sh "$(RPM_PKG_FILE)"
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
	@$(MAKE) _ensure-tag VERSION="$(RPM_PKG_VERSION)"
	@echo "--> Creating GitHub Release if missing..."
	@tmpfile="$$(mktemp)"; \
	trap 'rm -f "$$tmpfile"' EXIT; \
	printf '%s\n' \
		"RHEL/AlmaLinux/Rocky/Fedora package for ECLI v$(RPM_PKG_VERSION)." \
		"" \
		"Artifacts:" \
		"- $$(basename "$(RPM_PKG_FILE)")" \
		"- $$(basename "$(RPM_SHA_FILE)")" > "$$tmpfile"; \
	gh release view "v$(RPM_PKG_VERSION)" >/dev/null 2>&1 || \
	gh release create "v$(RPM_PKG_VERSION)" \
		--title "ECLI v$(RPM_PKG_VERSION)" \
		--notes-file "$$tmpfile"
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
APPIMAGE_FILE    ?= $(APPIMAGE_PKG_DIR)/ecli_$(APPIMAGE_VERSION)_linux_$(LINUX_ARCH).AppImage
APPIMAGE_SHA_FILE?= $(APPIMAGE_FILE).sha256

.PHONY: package-appimage
package-appimage: clean validate-runtime-imports
	@command -v appimagetool >/dev/null 2>&1 || (echo "appimagetool not found. Install AppImageKit: https://github.com/AppImage/AppImageKit"; exit 1)
	@echo "--> Building AppImage..."
	bash ./scripts/package_appimage.sh "$(APPIMAGE_VERSION)" "$(LINUX_ARCH)"
	@mkdir -p $(APPIMAGE_PKG_DIR)
	@test -f "$(APPIMAGE_FILE)" || (echo "AppImage build may have failed"; exit 1)
	@echo "--> Generating checksum..."
	cd $(APPIMAGE_PKG_DIR) && sha256sum $$(basename $(APPIMAGE_FILE)) > $$(basename $(APPIMAGE_SHA_FILE))
	$(MAKE) package-appimage-assert

.PHONY: package-appimage-assert
package-appimage-assert:
	@test -n "$(APPIMAGE_VERSION)" || (echo "APPIMAGE_VERSION is empty"; exit 1)
	$(call assert_current_release_file,$(APPIMAGE_FILE))
	$(call verify_sha256,$(APPIMAGE_FILE))
	@./scripts/verify_runtime.sh "$(APPIMAGE_FILE)"
	@echo "--> OK: $(APPIMAGE_FILE)"
	@echo "--> OK: $(APPIMAGE_SHA_FILE)"

.PHONY: show-appimage-artifacts
show-appimage-artifacts:
	@echo "Version: $(APPIMAGE_VERSION) Arch: $(LINUX_ARCH)"
	@ls -lh $(APPIMAGE_PKG_DIR)/ecli_*_linux_*.AppImage* 2>/dev/null || echo "(no artifacts yet)"

.PHONY: release-appimage
release-appimage: package-appimage-assert
	@test -n "$$(command -v gh)" || (echo "GitHub CLI 'gh' is required"; exit 1)
	@$(MAKE) _ensure-tag VERSION="$(APPIMAGE_VERSION)"
	@tmpfile="$$(mktemp)"; \
	trap 'rm -f "$$tmpfile"' EXIT; \
	printf '%s\n' \
		"AppImage package for Linux $(LINUX_ARCH) - ECLI v$(APPIMAGE_VERSION)." \
		"" \
		"Artifacts:" \
		"- $$(basename "$(APPIMAGE_FILE)")" \
		"- $$(basename "$(APPIMAGE_SHA_FILE)")" > "$$tmpfile"; \
	gh release view "v$(APPIMAGE_VERSION)" >/dev/null 2>&1 || \
	gh release create "v$(APPIMAGE_VERSION)" \
		--title "ECLI v$(APPIMAGE_VERSION)" \
		--notes-file "$$tmpfile"
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
SNAP_PKG_DIR  ?= $(RELEASE_DIR)
SNAP_FILE     ?= $(SNAP_PKG_DIR)/ecli_$(SNAP_VERSION)_linux_$(LINUX_ARCH).snap
SNAP_SHA_FILE ?= $(SNAP_FILE).sha256

.PHONY: package-snap
package-snap: clean validate-runtime-imports
	@command -v snapcraft >/dev/null 2>&1 || (echo "snapcraft not found. Install: sudo snap install snapcraft --classic"; exit 1)
	@test -f snapcraft.yaml || (echo "snapcraft.yaml not found in project root"; exit 1)
	@echo "--> Building Snap..."
	snapcraft
	@mkdir -p $(RELEASE_DIR)
	@set -- *.snap; \
	if [ "$$1" = "*.snap" ]; then \
		echo "Snap build did not produce a .snap artifact"; \
		exit 1; \
	fi; \
	if [ "$$#" -ne 1 ]; then \
		echo "Expected exactly one .snap artifact, found $$#"; \
		printf '%s\n' "$$@"; \
		exit 1; \
	fi; \
	mv "$$1" "$(SNAP_FILE)"
	@cd "$(SNAP_PKG_DIR)" && sha256sum "$$(basename "$(SNAP_FILE)")" > "$$(basename "$(SNAP_SHA_FILE)")"
	$(MAKE) package-snap-assert

.PHONY: package-snap-assert
package-snap-assert:
	$(call assert_current_release_file,$(SNAP_FILE))
	$(call verify_sha256,$(SNAP_FILE))
	@echo "--> OK: $(SNAP_FILE)"
	@echo "--> OK: $(SNAP_SHA_FILE)"

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
TAR_LINUX_FILE?= $(TAR_PKG_DIR)/ecli_$(TAR_VERSION)_linux_$(LINUX_ARCH).tar.gz
TAR_SHA_FILE  ?= $(TAR_LINUX_FILE).sha256

.PHONY: package-tar-linux
package-tar-linux: clean validate-runtime-imports
	@echo "--> Building Linux binary tar.gz archive..."
	@mkdir -p $(TAR_PKG_DIR)
	@rm -f "$(TAR_LINUX_FILE)" "$(TAR_SHA_FILE)"
	./scripts/build_pyinstaller_linux.sh
	@rm -rf build/package-tar-linux
	@mkdir -p build/package-tar-linux/ecli-$(TAR_VERSION)
	@install -m 0755 dist/ecli build/package-tar-linux/ecli-$(TAR_VERSION)/ecli
	@install -m 0644 README.md build/package-tar-linux/ecli-$(TAR_VERSION)/README.md
	@install -m 0644 LICENSE build/package-tar-linux/ecli-$(TAR_VERSION)/LICENSE
	@install -m 0644 CHANGELOG.md build/package-tar-linux/ecli-$(TAR_VERSION)/CHANGELOG.md
	@tar -czf "$(TAR_LINUX_FILE)" -C build/package-tar-linux ecli-$(TAR_VERSION)
	@cd $(TAR_PKG_DIR) && sha256sum $$(basename $(TAR_LINUX_FILE)) > $$(basename $(TAR_SHA_FILE))
	$(MAKE) package-tar-linux-assert

.PHONY: package-tar-linux-assert
package-tar-linux-assert:
	@test -n "$(TAR_VERSION)" || (echo "TAR_VERSION is empty"; exit 1)
	$(call assert_current_release_file,$(TAR_LINUX_FILE))
	$(call verify_sha256,$(TAR_LINUX_FILE))
	@./scripts/verify_runtime.sh "$(TAR_LINUX_FILE)"
	@echo "--> OK: $(TAR_LINUX_FILE)"
	@echo "--> OK: $(TAR_SHA_FILE)"

.PHONY: show-tar-artifacts
show-tar-artifacts:
	@echo "Version: $(TAR_VERSION) Arch: $(LINUX_ARCH)"
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
FREEBSD_PKG_VERSION ?= $(PACKAGE_VERSION)
FREEBSD_PKG_DIR     ?= releases/$(FREEBSD_PKG_VERSION)
FREEBSD_PKG_FILE    ?= $(FREEBSD_PKG_DIR)/ecli_$(FREEBSD_PKG_VERSION)_freebsd_$(FREEBSD_ARCH).pkg
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
package-freebsd: clean validate-runtime-imports
	sh ./scripts/build-and-package-freebsd.sh
	$(MAKE) package-freebsd-assert

# --- "Docker-like" reproducible build via chroot (on FreeBSD host) ------------
# Creates a clean 14.3 rootfs (base.txz), installs deps, runs the same build.
# Requires root; keeps the host clean and returns artifacts into ./releases/.
.PHONY: package-freebsd-chroot
package-freebsd-chroot: clean validate-runtime-imports
	sudo tools/freebsd-chroot-build.sh
	$(MAKE) package-freebsd-assert

# --- Build via FreeBSD Ports (local port skeleton) ----------------------------
# Uses scripts/build_freebsd_port.sh to create a local port and `make package`.
# Produces the same artifact names under releases/<version>/.
.PHONY: package-freebsd-port
package-freebsd-port: clean validate-runtime-imports
	sudo sh ./scripts/build_freebsd_port.sh
	$(MAKE) package-freebsd-assert

# --- Assertion helper: verify expected artifact names/locations ----------------
.PHONY: package-freebsd-assert
package-freebsd-assert:
	@test -n "$(FREEBSD_PKG_VERSION)" || (echo "FREEBSD_PKG_VERSION is empty (check pyproject.toml)"; exit 1)
	$(call assert_current_release_file,$(FREEBSD_PKG_FILE))
	$(call verify_sha256,$(FREEBSD_PKG_FILE))
	@./scripts/verify_runtime.sh "$(FREEBSD_PKG_FILE)"
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
	@$(MAKE) _ensure-tag VERSION="$(FREEBSD_PKG_VERSION)"
	@echo "--> Creating GitHub Release if missing..."
	@tmpfile="$$(mktemp)"; \
	trap 'rm -f "$$tmpfile"' EXIT; \
	printf '%s\n' \
		"FreeBSD package for ECLI v$(FREEBSD_PKG_VERSION)." \
		"" \
		"Artifacts:" \
		"- $$(basename "$(FREEBSD_PKG_FILE)")" \
		"- $$(basename "$(FREEBSD_SHA_FILE)")" > "$$tmpfile"; \
	gh release view "v$(FREEBSD_PKG_VERSION)" >/dev/null 2>&1 || \
	gh release create "v$(FREEBSD_PKG_VERSION)" \
		--title "ECLI v$(FREEBSD_PKG_VERSION)" \
		--notes-file "$$tmpfile"
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
#       releases/<version>/ecli_<version>_macos_universal2.dmg
#       releases/<version>/ecli_<version>_macos_universal2.dmg.sha256
#  - MACOS_ARCH defaults to universal2 for Phase 1.
#  - For CI builds, see `.github/workflows/macos-dmg.yml`.
# ---------------------------

MACOS_PKG_VERSION ?= $(PACKAGE_VERSION)
MACOS_PKG_DIR     ?= releases/$(MACOS_PKG_VERSION)
MACOS_PKG_FILE    ?= $(MACOS_PKG_DIR)/ecli_$(MACOS_PKG_VERSION)_macos_$(MACOS_ARCH).dmg
MACOS_SHA_FILE    ?= $(MACOS_PKG_FILE).sha256

.PHONY: package-macos
package-macos: clean validate-runtime-imports
	./scripts/build-and-package-macos.sh
	$(MAKE) package-macos-assert

.PHONY: package-macos-assert
package-macos-assert:
	@test -n "$(MACOS_PKG_VERSION)" || (echo "MACOS_PKG_VERSION empty (pyproject.toml)"; exit 1)
	$(call assert_current_release_file,$(MACOS_PKG_FILE))
	$(call verify_sha256,$(MACOS_PKG_FILE))
	@./scripts/verify_runtime.sh "$(MACOS_PKG_FILE)"
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
	@$(MAKE) _ensure-tag VERSION="$(MACOS_PKG_VERSION)"
	@tmpfile="$$(mktemp)"; \
	trap 'rm -f "$$tmpfile"' EXIT; \
	printf '%s\n' \
		"macOS package (DMG) for ECLI v$(MACOS_PKG_VERSION)." \
		"" \
		"Artifacts:" \
		"- $$(basename "$(MACOS_PKG_FILE)")" \
		"- $$(basename "$(MACOS_SHA_FILE)")" > "$$tmpfile"; \
	gh release view "v$(MACOS_PKG_VERSION)" >/dev/null 2>&1 || \
	gh release create "v$(MACOS_PKG_VERSION)" \
		--title "ECLI v$(MACOS_PKG_VERSION)" \
		--notes-file "$$tmpfile"
	@gh release upload "v$(MACOS_PKG_VERSION)" "$(MACOS_PKG_FILE)" "$(MACOS_SHA_FILE)" --clobber
	@echo "--> Release v$(MACOS_PKG_VERSION) updated with macOS artifacts."


# ---------------------------
# Packaging (Windows)
# ---------------------------
# Use:
# Build (local, PowerShell on Windows 10/11 x64):
#   `make package-windows`
#   (PyInstaller portable EXE → unsigned NSIS installer)
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
#       releases/<version>/ecli_<version>_win_x86_64_setup.exe
#       releases/<version>/ecli_<version>_win_x86_64_setup.exe.sha256
#  - For CI builds, see `.github/workflows/windows-installer.yml`.
#  - If code signing is required, integrate `signtool` before checksum generation.
# ---------------------------


WIN_PKG_VERSION ?= $(PACKAGE_VERSION)
WIN_PKG_DIR     ?= releases/$(WIN_PKG_VERSION)
WIN_PORTABLE_FILENAME ?= ecli_$(WIN_PKG_VERSION)_win_$(WIN_ARCH).exe
WIN_INSTALLER_FILENAME ?= ecli_$(WIN_PKG_VERSION)_win_$(WIN_ARCH)_setup.exe
WIN_PORTABLE_FILE ?= $(WIN_PKG_DIR)/$(WIN_PORTABLE_FILENAME)
WIN_INSTALLER_FILE ?= $(WIN_PKG_DIR)/$(WIN_INSTALLER_FILENAME)
WIN_PORTABLE_SHA_FILE ?= $(WIN_PORTABLE_FILE).sha256
WIN_INSTALLER_SHA_FILE ?= $(WIN_INSTALLER_FILE).sha256
WIN_PKG_FILE    ?= $(WIN_PORTABLE_FILE)
WIN_SHA_FILE    ?= $(WIN_PORTABLE_SHA_FILE)

# Local Windows build (run in PowerShell on Windows host)
.PHONY: package-windows
package-windows: clean validate-runtime-imports
	pwsh -File ./scripts/build-and-package-windows.ps1
	$(MAKE) package-windows-assert

.PHONY: package-windows-assert
package-windows-assert:
	@test -n "$(WIN_PKG_VERSION)" || (echo "WIN_PKG_VERSION empty (pyproject.toml)"; exit 1)
	$(call assert_current_release_file,$(WIN_PORTABLE_FILE))
	$(call assert_current_release_file,$(WIN_INSTALLER_FILE))
	$(call verify_sha256,$(WIN_PORTABLE_FILE))
	$(call verify_sha256,$(WIN_INSTALLER_FILE))
	@./scripts/verify_runtime.sh --mode structural "$(WIN_PORTABLE_FILE)"
	@./scripts/verify_runtime.sh --mode structural "$(WIN_INSTALLER_FILE)"
	@echo "--> OK: $(WIN_PORTABLE_FILE)"
	@echo "--> OK: $(WIN_PORTABLE_SHA_FILE)"
	@echo "--> OK: $(WIN_INSTALLER_FILE)"
	@echo "--> OK: $(WIN_INSTALLER_SHA_FILE)"

.PHONY: show-windows-artifacts
show-windows-artifacts:
	@echo "Version: $(WIN_PKG_VERSION)"
	@ls -l $(WIN_PKG_DIR)/ecli_*_win_*.exe* 2>/dev/null || echo "(no artifacts yet)"

# Publish to GitHub Release
.PHONY: release-windows
release-windows: package-windows-assert
	@test -n "$$(command -v gh)" || (echo "GitHub CLI 'gh' required"; exit 1)
	@$(MAKE) _ensure-tag VERSION="$(WIN_PKG_VERSION)"
	@tmpfile="$$(mktemp)"; \
	trap 'rm -f "$$tmpfile"' EXIT; \
	printf '%s\n' \
		"Windows x86_64 portable executable and unsigned NSIS installer for ECLI v$(WIN_PKG_VERSION)." \
		"" \
		"Artifacts:" \
		"- $$(basename "$(WIN_PORTABLE_FILE)")" \
		"- $$(basename "$(WIN_PORTABLE_SHA_FILE)")" \
		"- $$(basename "$(WIN_INSTALLER_FILE)")" \
		"- $$(basename "$(WIN_INSTALLER_SHA_FILE)")" > "$$tmpfile"; \
	gh release view "v$(WIN_PKG_VERSION)" >/dev/null 2>&1 || \
	gh release create "v$(WIN_PKG_VERSION)" \
		--title "ECLI v$(WIN_PKG_VERSION)" \
		--notes-file "$$tmpfile"
	@gh release upload "v$(WIN_PKG_VERSION)" "$(WIN_PORTABLE_FILE)" "$(WIN_PORTABLE_SHA_FILE)" "$(WIN_INSTALLER_FILE)" "$(WIN_INSTALLER_SHA_FILE)" --clobber
	@echo "--> Release v$(WIN_PKG_VERSION) updated with Windows artifacts."


# =============================================================================
# Meta Targets - Build Multiple Packages
# =============================================================================

# Build packages supported by the current host OS.
.PHONY: package-all-host
package-all-host:
	@case "$(OS)" in \
		Linux) \
			$(MAKE) package-deb-docker package-rpm-docker package-appimage package-tar-linux package-pypi; \
			;; \
		FreeBSD) \
			$(MAKE) package-freebsd package-tar-linux package-pypi; \
			;; \
		Darwin) \
			$(MAKE) package-pypi package-macos; \
			;; \
		MINGW*|MSYS*|CYGWIN*) \
			$(MAKE) package-pypi package-windows; \
			;; \
		*) \
			echo "Unsupported host OS for package-all-host: $(OS)"; \
			exit 1; \
			;; \
	esac
	@echo ""
	@echo "╔═══════════════════════════════════════════════════════════════════════╗"
	@echo "║              HOST-SUPPORTED PACKAGES BUILT SUCCESSFULLY               ║"
	@echo "╚═══════════════════════════════════════════════════════════════════════╝"
	@$(MAKE) show-artifacts

# Backward-compatible alias.
.PHONY: package-all
package-all: package-all-host

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

# Publish artifacts that already exist; skip absent platform artifacts.
.PHONY: publish-all
publish-all:
	@if [ -f "$(DEB_PKG_FILE)" ]; then \
		$(MAKE) release-deb; \
	else \
		echo "SKIP: DEB artifact not found: $(DEB_PKG_FILE)"; \
	fi
	@if [ -f "$(RPM_PKG_FILE)" ]; then \
		$(MAKE) release-rpm; \
	else \
		echo "SKIP: RPM artifact not found: $(RPM_PKG_FILE)"; \
	fi
	@if [ -f "$(APPIMAGE_FILE)" ]; then \
		$(MAKE) release-appimage; \
	else \
		echo "SKIP: AppImage artifact not found: $(APPIMAGE_FILE)"; \
	fi
	@if [ -f "$(FREEBSD_PKG_FILE)" ]; then \
		$(MAKE) release-freebsd; \
	else \
		echo "SKIP: FreeBSD artifact not found: $(FREEBSD_PKG_FILE)"; \
	fi
	@if [ -f "$(MACOS_PKG_FILE)" ]; then \
		$(MAKE) release-macos; \
	else \
		echo "SKIP: macOS artifact not found: $(MACOS_PKG_FILE)"; \
	fi
	@if [ -f "$(WIN_PKG_FILE)" ]; then \
		$(MAKE) release-windows; \
	else \
		echo "SKIP: Windows artifact not found: $(WIN_PKG_FILE)"; \
	fi
	@if [ -f "$(PYPI_WHEEL_FILE)" ] && [ -f "$(PYPI_SDIST_FILE)" ]; then \
		$(MAKE) publish-pypi; \
	else \
		echo "SKIP: PyPI artifacts not found under $(PYPI_PKG_DIR)"; \
	fi
	@echo ""
	@echo "╔═══════════════════════════════════════════════════════════════════════╗"
	@echo "║             AVAILABLE ARTIFACTS PUBLISH FLOW COMPLETED                ║"
	@echo "╚═══════════════════════════════════════════════════════════════════════╝"


# =============================================================================
# Gate 2 Contract Validation
# =============================================================================

.PHONY: validate-version-consistency
validate-version-consistency:
	@$(PYTHON) -c 'import pathlib, sys, tomllib; root=pathlib.Path.cwd().resolve(); sys.path.insert(0, str(root / "src")); import ecli; pyproject=tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]; expected=pyproject["version"]; actual=ecli.__version__; imported=pathlib.Path(ecli.__file__).resolve(); source_root=root / "src" / "ecli"; print(f"pyproject={expected} ecli.__version__={actual}"); ok=(actual == expected and imported.is_relative_to(source_root)); sys.exit(0 if ok else 1)'

.PHONY: validate-runtime-imports
validate-runtime-imports:
	@$(PYTHON) scripts/check_runtime_imports.py
	@echo "--> OK: production runtime imports"

.PHONY: validate-pypi-contract
validate-pypi-contract:
	@test -f "$(PYPI_WHEEL_FILE)" || (echo "Missing $(PYPI_WHEEL_FILE)"; exit 2)
	@test -f "$(PYPI_SDIST_FILE)" || (echo "Missing $(PYPI_SDIST_FILE)"; exit 2)
	@test -f "$(PYPI_WHEEL_FILE).sha256" || (echo "Missing $(PYPI_WHEEL_FILE).sha256"; exit 3)
	@test -f "$(PYPI_SDIST_FILE).sha256" || (echo "Missing $(PYPI_SDIST_FILE).sha256"; exit 3)
	$(call assert_current_release_file,$(PYPI_WHEEL_FILE))
	$(call assert_current_release_file,$(PYPI_SDIST_FILE))
	@$(PYTHON) -m twine --version >/dev/null 2>&1 || (echo "Missing tooling: twine"; exit 5)
	@$(PYTHON) -m twine check --strict "$(PYPI_WHEEL_FILE)" "$(PYPI_SDIST_FILE)" || exit 1
	$(call verify_sha256,$(PYPI_WHEEL_FILE))
	$(call verify_sha256,$(PYPI_SDIST_FILE))
	@echo "--> OK: PyPI contract"

.PHONY: validate-tar-linux-contract
validate-tar-linux-contract: package-tar-linux-assert
	@echo "--> OK: Linux tar contract"

.PHONY: validate-deb-contract
validate-deb-contract: package-deb-assert
	@echo "--> OK: DEB contract"

.PHONY: validate-rpm-contract
validate-rpm-contract: package-rpm-assert
	@echo "--> OK: RPM contract"

.PHONY: validate-appimage-contract
validate-appimage-contract: package-appimage-assert
	@echo "--> OK: AppImage contract"

.PHONY: validate-freebsd-contract
validate-freebsd-contract: package-freebsd-assert
	@echo "--> OK: FreeBSD contract"

.PHONY: validate-macos-contract
validate-macos-contract: package-macos-assert
	@echo "--> OK: macOS contract"

.PHONY: validate-windows-contract
validate-windows-contract: package-windows-assert
	@echo "--> OK: Windows contract"

.PHONY: validate-gate2
validate-gate2: validate-version-consistency validate-runtime-imports
	@if [ -f "$(PYPI_WHEEL_FILE)" ] || [ -f "$(PYPI_WHEEL_FILE).sha256" ] || [ -f "$(PYPI_SDIST_FILE)" ] || [ -f "$(PYPI_SDIST_FILE).sha256" ]; then \
		$(MAKE) validate-pypi-contract; \
	else \
		echo "SKIP: PyPI artifacts not built under $(PYPI_PKG_DIR)"; \
	fi
	$(call validate_if_present,$(DEB_PKG_FILE),validate-deb-contract,DEB)
	$(call validate_if_present,$(RPM_PKG_FILE),validate-rpm-contract,RPM)
	$(call validate_if_present,$(APPIMAGE_FILE),validate-appimage-contract,AppImage)
	$(call validate_if_present,$(TAR_LINUX_FILE),validate-tar-linux-contract,Linux tar)
	$(call validate_if_present,$(FREEBSD_PKG_FILE),validate-freebsd-contract,FreeBSD)
	$(call validate_if_present,$(MACOS_PKG_FILE),validate-macos-contract,macOS)
	$(call validate_if_present,$(WIN_PKG_FILE),validate-windows-contract,Windows)
	@echo "--> OK: Gate 2 validation completed for built artifacts"


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
	@ls -lh "$(PYPI_PKG_DIR)"/*.whl "$(PYPI_PKG_DIR)"/*.tar.gz 2>/dev/null || echo "  (not built)"
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
