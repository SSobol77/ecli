# =============================================================================
# Makefile for ECLI
# =============================================================================

PYTHON ?= python3
UV ?= uv

# Read version from pyproject.toml without multiline $(shell)
# We expect a line like: version = "0.1.0"
PACKAGE_VERSION := $(shell awk -F'"' '/^[[:space:]]*version[[:space:]]*=/ {print $$2; exit}' pyproject.toml 2>/dev/null || echo 0.0.0)

.DEFAULT_GOAL := help

# ---- FreeBSD .pkg (via vmactions/freebsd-vm) -------------------------------
FREEBSD_VM_IMAGE := ghcr.io/vmactions/freebsd-vm
# tag order (can be changed if desired)
FREEBSD_VM_TAGS ?= 14.2 14.1 14.0 14 latest


# ---------------------------
# Help
# ---------------------------
.PHONY: help
help:
	@echo "ECLI Makefile (version: $(PACKAGE_VERSION))"
	@echo "  install               - Install dependencies with uv"
	@echo "  run                   - Run from source"
	@echo "  clean                 - Remove build artifacts"
	@echo "  package-deb           - Build .deb locally (uses scripts/build-and-package-deb.sh)"
	@echo "  package-deb-docker    - Build .deb inside Debian 11 container (recommended)"
	@echo "  package-rpm           - Build .rpm locally (uses scripts/build-and-package-rpm.sh)"
	@echo "  package-rpm-docker    - Build .rpm inside AlmaLinux 9 container (recommended)"

# ---------------------------
# Dev & QA
# ---------------------------
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


# ---------------------------
# Packaging (DEB)
# ---------------------------
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
DEB_PKG_FILE    ?= $(DEB_PKG_DIR)/ecli_$(DEB_PKG_VERSION)_amd64.deb
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
	@ls -l $(DEB_PKG_DIR)/ecli_*_amd64.deb* 2>/dev/null || echo "(no artifacts yet)"

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
		--notes "Debian/Ubuntu package for ECLI v$(DEB_PKG_VERSION).\n\nArtifacts:\n- ecli_$(DEB_PKG_VERSION)_amd64.deb\n- ecli_$(DEB_PKG_VERSION)_amd64.deb.sha256"
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
RPM_PKG_FILE    ?= $(RPM_PKG_DIR)/ecli_$(RPM_PKG_VERSION)_amd64.rpm
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
	@ls -l $(RPM_PKG_DIR)/ecli_*_amd64.rpm* 2>/dev/null || echo "(no artifacts yet)"

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
		--notes "RHEL/AlmaLinux/Rocky/Fedora package for ECLI v$(RPM_PKG_VERSION).\n\nArtifacts:\n- ecli_$(RPM_PKG_VERSION)_amd64.rpm\n- ecli_$(RPM_PKG_VERSION)_amd64.rpm.sha256"
	@echo "--> Uploading RPM artifacts to GitHub Release..."
	@gh release upload "v$(RPM_PKG_VERSION)" \
		"$(RPM_PKG_FILE)" \
		"$(RPM_SHA_FILE)" \
		--clobber
	@echo "--> Release v$(RPM_PKG_VERSION) updated with RPM artifacts."


# ---------------------------
# Packaging (PKG) — FreeBSD
# ---------------------------
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
FREEBSD_PKG_FILE    ?= $(FREEBSD_PKG_DIR)/ecli_$(FREEBSD_PKG_VERSION)_amd64.pkg
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
	@ls -l $(FREEBSD_PKG_DIR)/ecli_*_amd64.pkg* 2>/dev/null || echo "(no artifacts yet)"

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
		--notes "FreeBSD amd64 package for ECLI v$(FREEBSD_PKG_VERSION).\n\nArtifacts:\n- ecli_$(FREEBSD_PKG_VERSION)_amd64.pkg\n- ecli_$(FREEBSD_PKG_VERSION)_amd64.pkg.sha256"
	@echo "--> Uploading artifacts to GitHub Release..."
	@gh release upload "v$(FREEBSD_PKG_VERSION)" \
		"$(FREEBSD_PKG_FILE)" \
		"$(FREEBSD_SHA_FILE)" \
		--clobber
	@echo "--> Release v$(FREEBSD_PKG_VERSION) updated with FreeBSD artifacts."

