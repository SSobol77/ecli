# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: Makefile
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

# =============================================================================
# ECLI Makefile
# =============================================================================
# Developer, validation, packaging, and release command surface for ECLI.
#
# Canonical implementations:
#   - Active build/packaging/verification logic under scripts/ is Python.
#   - Do not call deleted shell wrappers from this Makefile.
#   - scripts/build-and-package-windows.ps1 remains Windows-native PowerShell.
#   - tools/freebsd-chroot-build.sh remains a separate FreeBSD chroot helper.
#
# Active package/release matrix:
#   PyPI wheel/sdist, Linux PyInstaller/tar/DEB/RPM/openSUSE/Arch/Slackware/
#   AppImage, FreeBSD pkg/ports/chroot, macOS app/DMG, Windows portable/NSIS,
#   Nix flake/package, Docker DEB/RPM helpers, and GitHub Actions contract map.
#
# Safety:
#   Release, publish, tag, upload, and GitHub-write targets are maintainer-owned.
#   They are guarded and must not be used as default local developer commands.
# =============================================================================

PYTHON ?= python3
UV ?= uv
VERSION ?= $(PACKAGE_VERSION)
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

RELEASE_DIR := releases/$(PACKAGE_VERSION)
DIST_DIR ?= dist
BUILD_DIR ?= build
LOG_DIR ?= logs
LINUX_ARCH ?= $(ARCH_NORMALIZED)
FREEBSD_ARCH ?= $(ARCH_NORMALIZED)
MACOS_ARCH ?= universal2
WIN_ARCH ?= x86_64
RELEASE_CONFIRM_ENV ?= ECLI_ALLOW_RELEASE

-include $(RELEASE_DIR)/.linux.env
-include $(RELEASE_DIR)/.freebsd.env
-include $(RELEASE_DIR)/.macos.env
-include $(RELEASE_DIR)/.win.env

# =============================================================================
# 13. Internal helpers
# =============================================================================

define verify_sha256
	@$(PYTHON) scripts/verify_artifact.py "$(1)"
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

define block_partial_release
	@echo "Blocked partial GitHub Release upload target: $@"
	@echo "Official ECLI releases require exactly 21 canonical top-level assets."
	@echo "Run 'make validate-release-assets' and use 'make publish-all' for the aggregate GitHub Release asset set."
	@exit 64
endef

# =============================================================================
# 0. Project metadata and tool configuration
# =============================================================================

.DEFAULT_GOAL := help

FREEBSD_VM_IMAGE := ghcr.io/vmactions/freebsd-vm
FREEBSD_VM_TAGS ?= 14.2 14.1 14.0 14 latest


# =============================================================================
# 1. Help and discovery
# =============================================================================
.PHONY: help
help:
	@echo ""
	@echo "ECLI command surface"
	@echo "Version: $(PACKAGE_VERSION) | Host: $(OS)/$(ARCH_NORMALIZED) | Release dir: $(RELEASE_DIR)"
	@echo "Canonical scripts: scripts/*.py (Windows: scripts/build-and-package-windows.ps1)"
	@echo ""
	@echo "Quick start"
	@echo "  make install                  Install development dependencies"
	@echo "  make run                      Run ECLI from source"
	@echo "  make validate                 Fast local validation"
	@echo "  make doctor                   Check local tool availability"
	@echo "  make help-full                Show complete target map"
	@echo ""
	@echo "Common local commands"
	@echo "  make validate-fast            Runtime imports + Ruff"
	@echo "  make validate-full            Full local validation"
	@echo "  make validate-packaging       Packaging contract tests"
	@echo "  make show-artifacts           Inspect built artifacts"
	@echo "  make clean                    Remove local build/cache outputs"
	@echo ""
	@echo "Package groups"
	@echo "  make package-pypi             Build wheel + sdist"
	@echo "  make package-linux            Build Linux package set"
	@echo "  make package-freebsd          Build native FreeBSD .pkg"
	@echo "  make package-macos            Build macOS .app/.dmg"
	@echo "  make package-windows          Build Windows portable/NSIS artifacts"
	@echo "  make package-nix              Build Nix flake package"
	@echo ""
	@echo "Maintainer-owned release/publish targets"
	@echo "  make publish-pypi             Guarded PyPI publish helper"
	@echo "  make publish-all              Guarded exact-21 GitHub Release publisher"
	@echo "  make release-<platform>       Blocked legacy partial-release targets"
	@echo ""
	@echo "Discovery"
	@echo "  make list-targets             Print all public targets"
	@echo "  make sysinfo                  Print configured host/build variables"
	@echo "  make print-PACKAGE_VERSION    Print one Make variable"
	@echo ""
	@echo "Use 'make help-full' for every supported package, validation, artifact, and cleanup target."

.PHONY: help-full
help-full: help
	@echo ""
	@echo "Validation"
	@echo "  make validate                 Safe local validation"
	@echo "  make validate-fast            Ruff + runtime imports"
	@echo "  make validate-full            Ruff, mypy, full pytest, runtime imports"
	@echo "  make validate-packaging       Packaging contract suite"
	@echo "  make validate-release-contract Release/package matrix contract checks"
	@echo "  make validate-release-assets  Exact 21 GitHub Release asset gate"
	@echo "  make validate-version-consistency"
	@echo "  make validate-runtime-imports"
	@echo "  make validate-pypi-contract"
	@echo "  make validate-tar-linux-contract"
	@echo "  make validate-deb-contract"
	@echo "  make validate-rpm-contract"
	@echo "  make validate-appimage-contract"
	@echo "  make validate-freebsd-contract"
	@echo "  make validate-macos-contract"
	@echo "  make validate-windows-contract"
	@echo "  make validate-gate2"
	@echo ""
	@echo "Python / PyPI"
	@echo "  make package-pypi             Build wheel + sdist"
	@echo "  make publish-pypi             Maintainer-owned PyPI publish guard"
	@echo ""
	@echo "Linux packages"
	@echo "  make package-tar-linux        Linux PyInstaller tar.gz"
	@echo "  make package-deb              Local DEB build"
	@echo "  make package-deb-docker       Containerized DEB build"
	@echo "  make package-rpm              Local generic RPM build"
	@echo "  make package-rpm-docker       Containerized RPM build"
	@echo "  make package-opensuse-rpm     openSUSE/SUSE RPM build"
	@echo "  make package-arch             Arch PKGBUILD package (host, needs makepkg)"
	@echo "  make package-arch-docker      Containerized Arch package build"
	@echo "  make package-slackware        Slackware TXZ package (host, needs makepkg)"
	@echo "  make package-slackware-docker Containerized Slackware package build"
	@echo "  make package-appimage         AppImage build"
	@echo "  make package-docker           Docker DEB/RPM helpers"
	@echo "  make package-linux            Linux package group"
	@echo ""
	@echo "FreeBSD packages"
	@echo "  make package-freebsd          Native/VM FreeBSD .pkg"
	@echo "  make package-freebsd-ci       Print CI dispatch guidance"
	@echo "  make package-freebsd-chroot   FreeBSD chroot helper (root, FreeBSD host)"
	@echo "  make package-freebsd-port     FreeBSD ports skeleton path"
	@echo ""
	@echo "Desktop and Nix"
	@echo "  make package-macos            macOS .app/.dmg (macOS + hdiutil)"
	@echo "  make package-windows          Windows portable/NSIS (PowerShell + NSIS)"
	@echo "  make package-nix              Nix flake package"
	@echo "  make package-desktop          macOS + Windows group"
	@echo ""
	@echo "Artifact inspection"
	@echo "  make show-artifacts show-python-artifacts show-deb-artifacts show-rpm-artifacts"
	@echo "  make show-appimage-artifacts show-freebsd-artifacts show-macos-artifacts"
	@echo "  make show-windows-artifacts show-nix-artifacts show-tar-artifacts"
	@echo ""
	@echo "Cleanup"
	@echo "  make clean clean-build clean-cache clean-release distclean"
	@echo ""
	@echo "Release/publish targets are maintainer-owned and require $(RELEASE_CONFIRM_ENV)=1:"
	@echo "  make release-deb release-rpm release-appimage release-freebsd"
	@echo "  make release-macos release-windows publish-all"

.PHONY: list list-targets
list: list-targets

list-targets:
	@$(PYTHON) -c 'import pathlib,re; targets=[]; [targets.append(m.group(1)) for line in pathlib.Path("Makefile").read_text(encoding="utf-8").splitlines() for m in [re.match(r"^([A-Za-z0-9_.-]+):(?:\s|$$)", line)] if m and not m.group(1).startswith(("_", "."))]; print("\n".join(sorted(dict.fromkeys(targets))))'


# =============================================================================
# 2. Developer workflow
# =============================================================================
.PHONY: sysinfo
sysinfo:
	@echo "ECLI system information"
	@echo "OS:               $(OS)"
	@echo "Architecture:     $(ARCH) (normalized: $(ARCH_NORMALIZED))"
	@echo "Python Version:   $$($(PYTHON) --version 2>&1)"
	@echo "uv:               $$($(UV) --version 2>/dev/null || echo 'not found')"
	@echo "ECLI Version:     $(PACKAGE_VERSION)"
	@echo "Release Dir:      $(RELEASE_DIR)"
	@echo "Dist Dir:         $(DIST_DIR)"
	@echo "Build Dir:        $(BUILD_DIR)"
	@echo "Log Dir:          $(LOG_DIR)"
	@echo "Linux Arch:       $(LINUX_ARCH)"
	@echo "FreeBSD Arch:     $(FREEBSD_ARCH)"
	@echo "macOS Arch:       $(MACOS_ARCH)"
	@echo "Windows Arch:     $(WIN_ARCH)"
	@echo ""
	@$(MAKE) --no-print-directory doctor

.PHONY: doctor
doctor:
	@echo "Local tool availability (inspection only; no builds are run)"
	@command -v $(PYTHON) >/dev/null 2>&1 && echo "  OK  $(PYTHON)" || echo "  MISS $(PYTHON) (required)"
	@command -v $(UV) >/dev/null 2>&1 && echo "  OK  $(UV)" || echo "  MISS $(UV) (recommended)"
	@command -v docker >/dev/null 2>&1 && echo "  OK  docker (DEB/RPM container helpers)" || echo "  MISS docker (package-deb-docker, package-rpm-docker)"
	@command -v fpm >/dev/null 2>&1 && echo "  OK  fpm (local DEB/RPM)" || echo "  MISS fpm (local package-deb/package-rpm)"
	@command -v appimage-builder >/dev/null 2>&1 && echo "  OK  appimage-builder" || echo "  MISS appimage-builder (package-appimage)"
	@command -v appimagetool >/dev/null 2>&1 && echo "  OK  appimagetool" || echo "  MISS appimagetool (package-appimage runtime toolchain)"
	@command -v makepkg >/dev/null 2>&1 && echo "  OK  makepkg (Arch/Slackware on matching hosts)" || echo "  MISS makepkg (package-arch/package-slackware)"
	@command -v nix >/dev/null 2>&1 && echo "  OK  nix" || echo "  MISS nix (package-nix)"
	@command -v hdiutil >/dev/null 2>&1 && echo "  OK  hdiutil (macOS DMG)" || echo "  MISS hdiutil (package-macos; expected off macOS)"
	@command -v pwsh >/dev/null 2>&1 && echo "  OK  pwsh (Windows packaging)" || echo "  MISS pwsh (package-windows)"
	@command -v makensis >/dev/null 2>&1 && echo "  OK  makensis (Windows NSIS)" || echo "  MISS makensis (Windows installer)"
	@command -v gh >/dev/null 2>&1 && echo "  OK  gh (maintainer-owned release targets)" || echo "  MISS gh (release targets only)"
	@echo "Note: release/publish targets are guarded by $(RELEASE_CONFIRM_ENV)=1."

.PHONY: print-%
print-%:
	@printf '%s=%s\n' '$*' '$($*)'

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

# =============================================================================
# 12. Cleanup
# =============================================================================

.PHONY: clean
clean: clean-build clean-cache
	@echo "--> Local build/cache outputs cleaned."

.PHONY: clean-build
clean-build:
	rm -rf "$(BUILD_DIR)/" "$(DIST_DIR)/" __pycache__
	-find . -type d -name "__pycache__" -exec rm -rf {} +
	-find . -type f -name "*.pyc" -delete
	@echo "--> Build outputs cleaned."

.PHONY: clean-cache
clean-cache:
	rm -rf .pytest_cache/ .ruff_cache/ .mypy_cache/
	@echo "--> Tool caches cleaned."

.PHONY: clean-release
clean-release:
	rm -rf releases/
	@echo "--> Release artifacts cleaned."

.PHONY: distclean
distclean: clean clean-release
	@echo "--> Distclean completed."


# =============================================================================
# 4. Python / PyPI packaging
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
	$(PYTHON) ./scripts/publish_pypi.py
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

.PHONY: _confirm-release-action
_confirm-release-action:
	@test "$${$(RELEASE_CONFIRM_ENV):-}" = "1" || ( \
		echo "Blocked maintainer-owned release/publish action."; \
		echo "Set $(RELEASE_CONFIRM_ENV)=1 only when intentionally tagging, uploading, or publishing."; \
		exit 9; \
	)



# Use:
# Build and verify
#  `make package-deb`            # or: make package-deb-docker
#  `make show-deb-artifacts`
#
# Partial GitHub Release upload is blocked by the exact 21-asset release rule.
# Use `make publish-all` after `make validate-release-assets`.
# ---------------------------

# Resolve version once to match [project].version in pyproject.toml.
DEB_PKG_VERSION ?= $(PACKAGE_VERSION)
DEB_PKG_DIR     ?= releases/$(DEB_PKG_VERSION)
DEB_PKG_FILE    ?= $(DEB_PKG_DIR)/ecli_$(DEB_PKG_VERSION)_linux_$(LINUX_ARCH).deb
DEB_SHA_FILE    ?= $(DEB_PKG_FILE).sha256

.PHONY: package-deb
package-deb: clean validate-runtime-imports
	@command -v fpm >/dev/null 2>&1 || (echo "Missing fpm for local DEB build. Use package-deb-docker or install fpm."; exit 5)
	$(PYTHON) ./scripts/build_and_package_deb.py
	$(MAKE) package-deb-assert

.PHONY: package-deb-docker
package-deb-docker: clean validate-runtime-imports
	@command -v docker >/dev/null 2>&1 || (echo "Missing docker for package-deb-docker."; exit 5)
	docker build -f docker/build-linux-deb.Dockerfile \
		--build-arg PYTHON_VERSION=3.11 \
		--build-arg DEBIAN_RELEASE=bullseye \
		-t ecli-deb:py311-bullseye .
	docker run --rm -v "$$(pwd):/app" -w /app ecli-deb:py311-bullseye
	@# Docker ran as root via the bind mount and may leave root-owned files in
	@# build/, dist/, and $(RELEASE_DIR) (e.g. .linux.env). Reset ownership so
	@# later host-side targets (clean, package-opensuse-rpm) succeed (#93).
	@# Best-effort and safe: non-interactive sudo, no-op when already user-owned
	@# or when passwordless sudo is unavailable.
	-@for d in build dist "$(RELEASE_DIR)"; do \
		[ -d "$$d" ] && sudo -n chown -R "$$(id -u):$$(id -g)" "$$d" 2>/dev/null || true; \
	done
	$(MAKE) package-deb-assert

# --- Assertion helper: verify expected artifact names/locations ---------------
.PHONY: package-deb-assert
package-deb-assert:
	@test -n "$(DEB_PKG_VERSION)" || (echo "DEB_PKG_VERSION is empty (check pyproject.toml)"; exit 1)
	$(call assert_current_release_file,$(DEB_PKG_FILE))
	$(call verify_sha256,$(DEB_PKG_FILE))
	@$(PYTHON) ./scripts/verify_runtime.py "$(DEB_PKG_FILE)"
	@echo "--> OK: $(DEB_PKG_FILE)"
	@echo "--> OK: $(DEB_SHA_FILE)"

# --- Convenience: list produced DEB artifacts ---------------------------------
.PHONY: show-deb-artifacts
show-deb-artifacts:
	@echo "Version: $(DEB_PKG_VERSION)"
	@ls -l $(DEB_PKG_DIR)/ecli_*_linux_*.deb* 2>/dev/null || echo "(no artifacts yet)"

# --- Legacy partial release target: blocked by exact 21-asset rule ------------
.PHONY: release-deb
release-deb: _confirm-release-action
	$(call block_partial_release)


# ---------------------------
# Packaging (RPM)
# ---------------------------
# Use:
# Build and verify
#  `make package-rpm`            # or: make package-rpm-docker
#  `make show-rpm-artifacts`
#
# Partial GitHub Release upload is blocked by the exact 21-asset release rule.
# Use `make publish-all` after `make validate-release-assets`.
# ---------------------------

# Resolve version once to match [project].version in pyproject.toml.
RPM_PKG_VERSION ?= $(PACKAGE_VERSION)
RPM_PKG_DIR     ?= releases/$(RPM_PKG_VERSION)
RPM_PKG_FILE    ?= $(RPM_PKG_DIR)/ecli_$(RPM_PKG_VERSION)_linux_$(LINUX_ARCH).rpm
RPM_SHA_FILE    ?= $(RPM_PKG_FILE).sha256

.PHONY: package-rpm
package-rpm: clean validate-runtime-imports
	@command -v fpm >/dev/null 2>&1 || (echo "Missing fpm for local RPM build. Use package-rpm-docker or install fpm."; exit 5)
	$(PYTHON) ./scripts/build_and_package_rpm.py
	$(MAKE) package-rpm-assert

.PHONY: package-rpm-docker
package-rpm-docker: clean validate-runtime-imports
	@command -v docker >/dev/null 2>&1 || (echo "Missing docker for package-rpm-docker."; exit 5)
	docker build -f docker/build-linux-rpm.Dockerfile -t ecli-rpm:alma9 .
	docker run --rm -e PYTHON=python3.11 -v "$$(pwd):/app" -w /app ecli-rpm:alma9
	@# Docker ran as root via the bind mount and may leave root-owned files in
	@# build/, dist/, and $(RELEASE_DIR) (e.g. .linux.env). Reset ownership so
	@# later host-side targets (clean, package-opensuse-rpm) succeed (#93).
	@# Best-effort and safe: non-interactive sudo, no-op when already user-owned
	@# or when passwordless sudo is unavailable.
	-@for d in build dist "$(RELEASE_DIR)"; do \
		[ -d "$$d" ] && sudo -n chown -R "$$(id -u):$$(id -g)" "$$d" 2>/dev/null || true; \
	done
	$(MAKE) package-rpm-assert

# --- Assertion helper: verify expected artifact names/locations ---------------
.PHONY: package-rpm-assert
package-rpm-assert:
	@test -n "$(RPM_PKG_VERSION)" || (echo "RPM_PKG_VERSION is empty (check pyproject.toml)"; exit 1)
	$(call assert_current_release_file,$(RPM_PKG_FILE))
	$(call verify_sha256,$(RPM_PKG_FILE))
	@$(PYTHON) ./scripts/verify_runtime.py "$(RPM_PKG_FILE)"
	@echo "--> OK: $(RPM_PKG_FILE)"
	@echo "--> OK: $(RPM_SHA_FILE)"

# --- Convenience: list produced RPM artifacts -------------------------------
.PHONY: show-rpm-artifacts
show-rpm-artifacts:
	@echo "Version: $(RPM_PKG_VERSION)"
	@ls -l $(RPM_PKG_DIR)/ecli_*_linux_*.rpm* $(RPM_PKG_DIR)/ecli_*_opensuse_*.rpm* 2>/dev/null || echo "(no artifacts yet)"

OPENSUSE_RPM_FILE ?= $(RPM_PKG_DIR)/ecli_$(RPM_PKG_VERSION)_opensuse_$(LINUX_ARCH).rpm
OPENSUSE_RPM_SHA_FILE ?= $(OPENSUSE_RPM_FILE).sha256
ARCH_PKG_VERSION ?= $(PACKAGE_VERSION)
ARCH_PKG_DIR ?= $(RELEASE_DIR)
ARCH_PKG_FILE ?= $(ARCH_PKG_DIR)/ecli_$(ARCH_PKG_VERSION)_arch_$(LINUX_ARCH).pkg.tar.zst
ARCH_SHA_FILE ?= $(ARCH_PKG_FILE).sha256
SLACKWARE_PKG_VERSION ?= $(PACKAGE_VERSION)
SLACKWARE_PKG_DIR ?= $(RELEASE_DIR)
SLACKWARE_PKG_FILE ?= $(SLACKWARE_PKG_DIR)/ecli_$(SLACKWARE_PKG_VERSION)_slackware_$(LINUX_ARCH).txz
SLACKWARE_SHA_FILE ?= $(SLACKWARE_PKG_FILE).sha256

# Build openSUSE/SUSE RPM using the shared canonical Python RPM flow.
.PHONY: package-opensuse-rpm
package-opensuse-rpm: clean validate-runtime-imports
	@command -v fpm >/dev/null 2>&1 || (echo "Missing fpm for local openSUSE RPM build."; exit 5)
	$(PYTHON) ./scripts/build_and_package_opensuse_rpm.py
	$(call assert_current_release_file,$(OPENSUSE_RPM_FILE))
	$(call verify_sha256,$(OPENSUSE_RPM_FILE))
	@$(PYTHON) ./scripts/verify_runtime.py "$(OPENSUSE_RPM_FILE)"
	@echo "--> OK: $(OPENSUSE_RPM_FILE)"
	@echo "--> OK: $(OPENSUSE_RPM_SHA_FILE)"

# Build Arch package through packaging/arch/PKGBUILD and canonical Python helper.
# Host-only: requires a real Arch base-devel toolchain (makepkg). The Ubuntu
# release runner has no makepkg, so the release-canonical path is
# package-arch-docker, which runs the same script inside a real Arch container
# (docker/build-arch-package.Dockerfile) (#93).
.PHONY: package-arch
package-arch: clean validate-runtime-imports
	@command -v makepkg >/dev/null 2>&1 || (echo "Missing makepkg for Arch package build. Use package-arch-docker or build on an Arch host."; exit 5)
	$(PYTHON) ./scripts/build_and_package_arch.py
	$(MAKE) package-arch-assert

# Build the Arch package inside a real Arch base-devel container (release path).
.PHONY: package-arch-docker
package-arch-docker: clean validate-runtime-imports
	@command -v docker >/dev/null 2>&1 || (echo "Missing docker for package-arch-docker."; exit 5)
	docker build -f docker/build-arch-package.Dockerfile -t ecli-arch:base-devel .
	docker run --rm -v "$$(pwd):/app" -w /app ecli-arch:base-devel
	@# makepkg refuses to run as root, so the container builds as a non-root user
	@# and leaves build-user-owned files in build/, dist/, and $(RELEASE_DIR). Reset
	@# ownership so later host-side targets (clean, package-slackware) succeed (#93).
	@# Best-effort and safe: non-interactive sudo, no-op when already user-owned
	@# or when passwordless sudo is unavailable.
	-@for d in build dist "$(RELEASE_DIR)"; do \
		[ -d "$$d" ] && sudo -n chown -R "$$(id -u):$$(id -g)" "$$d" 2>/dev/null || true; \
	done
	$(MAKE) package-arch-assert

# --- Assertion helper: verify expected artifact names/locations ---------------
.PHONY: package-arch-assert
package-arch-assert:
	@test -n "$(ARCH_PKG_VERSION)" || (echo "ARCH_PKG_VERSION is empty (check pyproject.toml)"; exit 1)
	$(call assert_current_release_file,$(ARCH_PKG_FILE))
	$(call verify_sha256,$(ARCH_PKG_FILE))
	@echo "--> OK: $(ARCH_PKG_FILE)"
	@echo "--> OK: $(ARCH_SHA_FILE)"

# Build Slackware TXZ package using the canonical Python helper.
# Host-only: requires a real Slackware pkgtools toolchain (makepkg). The Ubuntu
# release runner has no Slackware makepkg, so the release-canonical path is
# package-slackware-docker, which runs the same script inside a real Slackware
# container (docker/build-slackware-package.Dockerfile) (#93).
.PHONY: package-slackware
package-slackware: clean validate-runtime-imports
	@command -v makepkg >/dev/null 2>&1 || (echo "Missing makepkg for Slackware package build. Use package-slackware-docker or build on a Slackware host."; exit 5)
	$(PYTHON) ./scripts/build_and_package_slackware.py
	$(MAKE) package-slackware-assert

# Build the Slackware package inside a real Slackware container (release path).
.PHONY: package-slackware-docker
package-slackware-docker: clean validate-runtime-imports
	@command -v docker >/dev/null 2>&1 || (echo "Missing docker for package-slackware-docker."; exit 5)
	docker build -f docker/build-slackware-package.Dockerfile -t ecli-slackware:current .
	docker run --rm --user 0:0 -v "$$(pwd):/app" -w /app ecli-slackware:current
	@# Slackware makepkg runs as root inside the container and leaves root-owned
	@# files in build/, dist/, and $(RELEASE_DIR). The next host-side steps run as
	@# the runner user (package-appimage writes releases/), so reset ownership of
	@# every Docker-touched output path (#93). Best-effort and safe: non-interactive
	@# sudo, no-op when already user-owned or when passwordless sudo is unavailable.
	-@for d in build dist "$(RELEASE_DIR)"; do \
		[ -d "$$d" ] && sudo -n chown -R "$$(id -u):$$(id -g)" "$$d" 2>/dev/null || true; \
	done
	$(MAKE) package-slackware-assert

# --- Assertion helper: verify expected artifact names/locations ---------------
.PHONY: package-slackware-assert
package-slackware-assert:
	@test -n "$(SLACKWARE_PKG_VERSION)" || (echo "SLACKWARE_PKG_VERSION is empty (check pyproject.toml)"; exit 1)
	$(call assert_current_release_file,$(SLACKWARE_PKG_FILE))
	$(call verify_sha256,$(SLACKWARE_PKG_FILE))
	@echo "--> OK: $(SLACKWARE_PKG_FILE)"
	@echo "--> OK: $(SLACKWARE_SHA_FILE)"

# --- Legacy partial release target: blocked by exact 21-asset rule ------------
.PHONY: release-rpm
release-rpm: _confirm-release-action
	$(call block_partial_release)


# =============================================================================
# 5. Linux packages
# =============================================================================
# Use:
# Build an AppImage (works on any Linux distro)
#  `make package-appimage`        # Build AppImage
#
# Verify produced artifacts
#  `make show-appimage-artifacts`
#
# Partial GitHub Release upload is blocked by the exact 21-asset release rule.
# Use `make publish-all` after `make validate-release-assets`.
# ---------------------------

APPIMAGE_VERSION ?= $(PACKAGE_VERSION)
APPIMAGE_PKG_DIR ?= $(RELEASE_DIR)
APPIMAGE_FILE    ?= $(APPIMAGE_PKG_DIR)/ecli_$(APPIMAGE_VERSION)_linux_$(LINUX_ARCH).AppImage
APPIMAGE_SHA_FILE?= $(APPIMAGE_FILE).sha256

.PHONY: package-appimage
package-appimage: clean validate-runtime-imports
	@command -v appimage-builder >/dev/null 2>&1 || (echo "appimage-builder not found. Install appimage-builder for package-appimage."; exit 1)
	@command -v appimagetool >/dev/null 2>&1 || (echo "appimagetool not found. Install AppImageKit: https://github.com/AppImage/AppImageKit"; exit 1)
	@echo "--> Building AppImage..."
	$(PYTHON) ./scripts/package_appimage.py "$(APPIMAGE_VERSION)" "$(LINUX_ARCH)"
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
	@$(PYTHON) ./scripts/verify_runtime.py "$(APPIMAGE_FILE)"
	@echo "--> OK: $(APPIMAGE_FILE)"
	@echo "--> OK: $(APPIMAGE_SHA_FILE)"

.PHONY: show-appimage-artifacts
show-appimage-artifacts:
	@echo "Version: $(APPIMAGE_VERSION) Arch: $(LINUX_ARCH)"
	@ls -lh $(APPIMAGE_PKG_DIR)/ecli_*_linux_*.AppImage* 2>/dev/null || echo "(no artifacts yet)"

.PHONY: release-appimage
release-appimage: _confirm-release-action
	$(call block_partial_release)


# Optional Linux Snap package surface.
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


# Linux archive package surface.
# =============================================================================
# 6. FreeBSD packages
# =============================================================================
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
	$(PYTHON) ./scripts/build_pyinstaller_linux.py
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
	@$(PYTHON) ./scripts/verify_runtime.py "$(TAR_LINUX_FILE)"
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
# Partial GitHub Release upload is blocked by the exact 21-asset release rule.
# Use `make publish-all` after `make validate-release-assets`.
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
	@test "$(OS)" = "FreeBSD" || (echo "package-freebsd requires a FreeBSD host/VM. Use package-freebsd-ci for CI guidance."; exit 5)
	$(PYTHON) ./scripts/build_and_package_freebsd.py
	$(MAKE) package-freebsd-assert

# --- "Docker-like" reproducible build via chroot (on FreeBSD host) ------------
# Creates a clean 14.3 rootfs (base.txz), installs deps, runs the same build.
# Requires root; keeps the host clean and returns artifacts into ./releases/.
.PHONY: package-freebsd-chroot
package-freebsd-chroot: clean validate-runtime-imports
	@test "$(OS)" = "FreeBSD" || (echo "package-freebsd-chroot requires a FreeBSD host with root/chroot support."; exit 5)
	sudo tools/freebsd-chroot-build.sh
	$(MAKE) package-freebsd-assert

# --- Build via FreeBSD Ports (local port skeleton) ----------------------------
# Uses scripts/build_freebsd_port.py to create a local port and `make package`.
# Produces the same artifact names under releases/<version>/.
.PHONY: package-freebsd-port
package-freebsd-port: clean validate-runtime-imports
	@test "$(OS)" = "FreeBSD" || (echo "package-freebsd-port requires a FreeBSD ports-capable host."; exit 5)
	sudo $(PYTHON) ./scripts/build_freebsd_port.py
	$(MAKE) package-freebsd-assert

# --- Assertion helper: verify expected artifact names/locations ----------------
.PHONY: package-freebsd-assert
package-freebsd-assert:
	@test -n "$(FREEBSD_PKG_VERSION)" || (echo "FREEBSD_PKG_VERSION is empty (check pyproject.toml)"; exit 1)
	$(call assert_current_release_file,$(FREEBSD_PKG_FILE))
	$(call verify_sha256,$(FREEBSD_PKG_FILE))
	@$(PYTHON) ./scripts/verify_runtime.py "$(FREEBSD_PKG_FILE)"
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

# --- Legacy partial release target: blocked by exact 21-asset rule ------------
.PHONY: release-freebsd
release-freebsd: _confirm-release-action
	$(call block_partial_release)


# =============================================================================
# 7. macOS packages
# =============================================================================
# Use:
# Build (choose one):
#  - Local on macOS 12+ with Python 3.11:
#       `make package-macos`
#    (Produces a DMG via PyInstaller .app → hdiutil)
#
# Verify produced artifacts (strict naming & location):
#   `make show-macos-artifacts`
#
# Partial GitHub Release upload is blocked by the exact 21-asset release rule.
# Use `make publish-all` after `make validate-release-assets`.
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
MACOS_ASSERT_MODE ?= native

.PHONY: package-macos
package-macos: clean validate-runtime-imports
	@test "$(OS)" = "Darwin" || (echo "package-macos requires macOS with hdiutil."; exit 5)
	@command -v hdiutil >/dev/null 2>&1 || (echo "Missing hdiutil for macOS DMG build."; exit 5)
	$(PYTHON) ./scripts/build_and_package_macos.py
	$(MAKE) package-macos-assert MACOS_ASSERT_MODE=structural

.PHONY: package-macos-assert
package-macos-assert:
	@test -n "$(MACOS_PKG_VERSION)" || (echo "MACOS_PKG_VERSION empty (pyproject.toml)"; exit 1)
	$(call assert_current_release_file,$(MACOS_PKG_FILE))
	$(call verify_sha256,$(MACOS_PKG_FILE))
ifeq ($(MACOS_ASSERT_MODE),native)
	@$(PYTHON) ./scripts/verify_runtime.py "$(MACOS_PKG_FILE)"
	@echo "--> OK: macOS native runtime artifact contract"
else ifeq ($(MACOS_ASSERT_MODE),structural)
	@test -s "$(MACOS_PKG_FILE)" || (echo "Missing or empty $(MACOS_PKG_FILE)"; exit 2)
	@test -s "$(MACOS_SHA_FILE)" || (echo "Missing or empty $(MACOS_SHA_FILE)"; exit 3)
	@echo "--> OK: macOS structural artifact contract"
	@echo "--> INFO: native DMG runtime smoke already completed during build script"
else
	@echo "Invalid MACOS_ASSERT_MODE=$(MACOS_ASSERT_MODE) (expected native or structural)"; exit 2
endif
	@echo "--> OK: $(MACOS_PKG_FILE)"
	@echo "--> OK: $(MACOS_SHA_FILE)"

.PHONY: show-macos-artifacts
show-macos-artifacts:
	@echo "Version: $(MACOS_PKG_VERSION) Arch: $(MACOS_ARCH)"
	@ls -l $(MACOS_PKG_DIR)/ecli_*_macos_* 2>/dev/null || echo "(no artifacts yet)"

.PHONY: release-macos
release-macos: _confirm-release-action
	$(call block_partial_release)


# =============================================================================
# 8. Windows packages
# =============================================================================
# Use:
# Build (local, PowerShell on Windows 10/11 x64):
#   `make package-windows`
#   (PyInstaller portable EXE → unsigned NSIS installer)
#
# Verify produced artifacts (strict naming & location):
#   `make show-windows-artifacts`
#
# Partial GitHub Release upload is blocked by the exact 21-asset release rule.
# Use `make publish-all` after `make validate-release-assets`.
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
	@command -v pwsh >/dev/null 2>&1 || (echo "package-windows requires PowerShell 7+ and Windows packaging tools."; exit 5)
	pwsh -File ./scripts/build-and-package-windows.ps1
	$(MAKE) package-windows-assert

.PHONY: package-windows-assert
package-windows-assert:
	@test -n "$(WIN_PKG_VERSION)" || (echo "WIN_PKG_VERSION empty (pyproject.toml)"; exit 1)
	$(call assert_current_release_file,$(WIN_PORTABLE_FILE))
	$(call assert_current_release_file,$(WIN_INSTALLER_FILE))
	$(call verify_sha256,$(WIN_PORTABLE_FILE))
	$(call verify_sha256,$(WIN_INSTALLER_FILE))
	@$(PYTHON) ./scripts/verify_runtime.py --mode structural "$(WIN_PORTABLE_FILE)"
	@$(PYTHON) ./scripts/verify_runtime.py --mode structural "$(WIN_INSTALLER_FILE)"
	@echo "--> OK: $(WIN_PORTABLE_FILE)"
	@echo "--> OK: $(WIN_PORTABLE_SHA_FILE)"
	@echo "--> OK: $(WIN_INSTALLER_FILE)"
	@echo "--> OK: $(WIN_INSTALLER_SHA_FILE)"

.PHONY: show-windows-artifacts
show-windows-artifacts:
	@echo "Version: $(WIN_PKG_VERSION)"
	@ls -l $(WIN_PKG_DIR)/ecli_*_win_*.exe* 2>/dev/null || echo "(no artifacts yet)"

.PHONY: release-windows
release-windows: _confirm-release-action
	$(call block_partial_release)


# =============================================================================
# 9. Nix / NixOS packages
# =============================================================================

.PHONY: package-nix
package-nix:
	@command -v nix >/dev/null 2>&1 || (echo "nix not found. Install Nix to build flake/package outputs."; exit 5)
	@test -f flake.nix || (echo "flake.nix missing"; exit 2)
	@test -f packaging/nix/package.nix || (echo "packaging/nix/package.nix missing"; exit 2)
	nix build .
	@echo "--> Nix build completed. Inspect ./result with make show-nix-artifacts."

.PHONY: show-nix-artifacts
show-nix-artifacts:
	@echo "Nix artifacts:"
	@if [ -L result ] || [ -e result ]; then \
		ls -lh result; \
		find result -maxdepth 3 -type f 2>/dev/null | sort | sed 's/^/  /'; \
	else \
		echo "  (not built)"; \
	fi


# =============================================================================
# 10. Release orchestration and package groups
# =============================================================================

# Build packages supported by the current host OS.
.PHONY: package-all-host
package-all-host:
	@case "$(OS)" in \
		Linux) \
			$(MAKE) package-linux package-pypi; \
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
package-linux: package-deb-docker package-rpm-docker package-opensuse-rpm package-arch-docker package-slackware-docker package-appimage package-tar-linux
	@echo ""
	@echo "╔═══════════════════════════════════════════════════════════════════════╗"
	@echo "║                 ALL LINUX PACKAGES BUILT SUCCESSFULLY                 ║"
	@echo "╚═══════════════════════════════════════════════════════════════════════╝"
	@$(MAKE) show-artifacts

# Build all desktop packages (macOS and Windows)
.PHONY: package-desktop
package-desktop: package-macos package-windows
	@echo "--> All desktop packages built."

# Publish exactly the 21 canonical GitHub Release assets.
# Checksum sidecars remain verification evidence and are not uploaded here.
.PHONY: publish-all
publish-all: _confirm-release-action validate-release-assets
	@test -n "$$(command -v gh)" || (echo "GitHub CLI 'gh' is required"; exit 1)
	@$(MAKE) _ensure-tag VERSION="$(PACKAGE_VERSION)"
	@tmpfile="$$(mktemp)"; \
	trap 'rm -f "$$tmpfile"' EXIT; \
	printf '%s\n' \
		"ECLI v$(PACKAGE_VERSION) official release assets." \
		"" \
		"This release publishes exactly 21 physical GitHub Release assets." \
		"Checksum sidecars are verification evidence and are not uploaded as GitHub Release assets." > "$$tmpfile"; \
	gh release view "v$(PACKAGE_VERSION)" >/dev/null 2>&1 || \
	gh release create "v$(PACKAGE_VERSION)" \
		--title "ECLI v$(PACKAGE_VERSION)" \
		--notes-file "$$tmpfile"
	@assets="$$(find "$(RELEASE_DIR)" -maxdepth 1 -type f | sort)"; \
	count="$$(printf '%s\n' "$$assets" | sed '/^$$/d' | wc -l)"; \
	test "$$count" = "21" || (echo "Expected exactly 21 assets, found $$count"; exit 3); \
	echo "--> Uploading exactly 21 GitHub Release assets"; \
	printf '%s\n' "$$assets"; \
	gh release upload "v$(PACKAGE_VERSION)" $$assets --clobber
	@echo ""
	@echo "╔═══════════════════════════════════════════════════════════════════════╗"
	@echo "║          EXACT 21 GITHUB RELEASE ASSETS PUBLISH FLOW COMPLETED         ║"
	@echo "╚═══════════════════════════════════════════════════════════════════════╝"


# =============================================================================
# 3. Validation and quality gates
# =============================================================================

.PHONY: validate
validate: validate-fast

.PHONY: validate-fast
validate-fast: validate-runtime-imports
	@$(UV) run ruff format --check .
	@$(UV) run ruff check . --output-format=concise
	@echo "--> OK: fast validation"

.PHONY: validate-full
validate-full: validate-version-consistency validate-runtime-imports
	@$(UV) run ruff format --check .
	@$(UV) run ruff check . --output-format=concise
	@$(UV) run mypy src/ecli tests
	@$(UV) run pytest -ra -q
	@echo "--> OK: full validation"

.PHONY: validate-packaging
validate-packaging:
	@$(UV) run pytest -q tests/packaging
	@echo "--> OK: packaging contract tests"

.PHONY: validate-release-contract
validate-release-contract:
	@$(UV) run pytest -q tests/packaging/test_packaging_release_contract.py
	@$(UV) run pytest -q tests/packaging/test_packaging_workflows_contract.py
	@$(UV) run pytest -q tests/packaging/test_scripts_python_migration_contract.py
	@$(UV) run pytest -q tests/packaging/test_release_asset_count_gate.py
	@echo "--> OK: release contract tests"

.PHONY: validate-release-assets
validate-release-assets:
	@$(PYTHON) scripts/verify_release_assets.py
	@echo "--> OK: exact 21 GitHub Release asset gate"

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
	$(MAKE) validate-release-assets
	@echo "--> OK: Gate 2 validation completed for built artifacts"


# =============================================================================
# 11. Artifact inspection
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
	@ls -lh $(RELEASE_DIR)/ecli_*_linux_*.rpm* $(RELEASE_DIR)/ecli_*_opensuse_*.rpm* 2>/dev/null || echo "  (not built)"
	@echo ""
	@echo "Linux (Arch):"
	@ls -lh $(RELEASE_DIR)/ecli_*_arch_*.pkg.tar.zst* 2>/dev/null || echo "  (not built)"
	@echo ""
	@echo "Linux (Slackware):"
	@ls -lh $(RELEASE_DIR)/ecli_*_slackware_*.txz* 2>/dev/null || echo "  (not built)"
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
	@$(MAKE) --no-print-directory show-nix-artifacts
	@echo ""

# =============================================================================
