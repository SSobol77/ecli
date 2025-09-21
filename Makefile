# =============================================================================
# Makefile for the ECLI Project
#
# Provides a standard interface for development, testing, and packaging tasks.
# =============================================================================

# --- Configuration ---

# Define Python interpreter. Can be overridden, e.g.: make test PYTHON=python3.13
PYTHON ?= python3

# Define uv.
UV ?= uv

# Automatically extract version from pyproject.toml
PACKAGE_VERSION := $(shell grep "^version =" pyproject.toml | cut -d '"' -f 2)

# Set default target. If just `make` is run, it executes `make help`.
.DEFAULT_GOAL := help

# --- Main Commands ---

.PHONY: help
help:
	@echo "ECLI Makefile"
	@echo "---------------"
	@echo "Usage: make <command>"
	@echo ""
	@echo "Development:"
	@echo "  install        - Install dependencies using uv pip sync."
	@echo "  run            - Run ECLI from source."
	@echo "  clean          - Remove all build artifacts and cache files."
	@echo ""
	@echo "Quality Assurance:"
	@echo "  lint           - Check code for style issues with Ruff."
	@echo "  format         - Automatically format code with Ruff."
	@echo "  test           - Run tests with pytest and generate coverage report."
	@echo "  check          - Run lint and test targets together."
	@echo ""
	@echo "Packaging & Distribution:"
	@echo "  build          - Build sdist and wheel packages."
	@echo "  package-deb    - Create a .deb package for Debian/Ubuntu."
	@echo ""


# =============================================================================
# DEVELOPMENT
# =============================================================================

.PHONY: install
install:
	@echo "--> Installing dependencies from requirements files..."
	$(UV) pip sync requirements.txt requirements-dev.txt

.PHONY: run
run:
	@echo "--> Running ECLI..."
	$(PYTHON) main.py

.PHONY: clean
clean:
	@echo "--> Cleaning up build artifacts and cache files..."
	@find . -type f -name "*.pyc" -delete
	@find . -type d -name "__pycache__" -delete
	@rm -rf build/ dist/ .coverage htmlcov/ .pytest_cache/ ecli.egg-info/ releases/
	@rm -f ecli_*.deb


# =============================================================================
# QUALITY ASSURANCE
# =============================================================================

.PHONY: lint
lint:
	@echo "--> Running linter (Ruff)..."
	$(UV) run ruff check src tests

.PHONY: format
format:
	@echo "--> Formatting code (Ruff)..."
	$(UV) run ruff format src tests

.PHONY: test
test:
	@echo "--> Running tests (pytest)..."
	$(UV) run pytest --cov=src/ecli --cov-report=term-missing

.PHONY: check
check: lint test


# =============================================================================
# PACKAGING & DISTRIBUTION
# =============================================================================

.PHONY: build
build: clean
	@echo "--> Building source distribution and wheel..."
	$(PYTHON) -m build

.PHONY: package-deb
package-deb: clean
	@echo "--> Building Debian package for version $(PACKAGE_VERSION)..."
	@./scripts/package_fpm_deb.sh
	@echo "--> Build process finished. See output above for details."
