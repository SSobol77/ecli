# =============================================================================
# Makefile for ECLI
# =============================================================================

PYTHON ?= python3
UV ?= uv

# Read version from pyproject.toml without multiline $(shell)
# We expect a line like: version = "0.1.0"
PACKAGE_VERSION := $(shell awk -F'"' '/^[[:space:]]*version[[:space:]]*=/ {print $$2; exit}' pyproject.toml 2>/dev/null || echo 0.0.0)

.DEFAULT_GOAL := help

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
.PHONY: package-deb
package-deb: clean
	./scripts/build-and-package-deb.sh

.PHONY: package-deb-docker
package-deb-docker:
	docker build -f docker/build-linux-deb.Dockerfile \
		--build-arg PYTHON_VERSION=3.11 \
		--build-arg DEBIAN_RELEASE=bullseye \
		-t ecli-deb:py311-bullseye .
	docker run --rm -v "$$(pwd):/app" -w /app ecli-deb:py311-bullseye

# ---------------------------
# Packaging (RPM)
# ---------------------------
.PHONY: package-rpm
package-rpm: clean
	./scripts/build-and-package-rpm.sh

.PHONY: package-rpm-docker
package-rpm-docker:
	docker build -f docker/build-linux-rpm.Dockerfile -t ecli-rpm:alma9 .
	docker run --rm -v "$$(pwd):/app" -w /app ecli-rpm:alma9
