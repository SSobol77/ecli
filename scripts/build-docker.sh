#!/usr/bin/env bash
# ==============================================================================
# scripts/build-docker.sh
# Build ECLI .deb in Debian 11 container using YOUR existing scripts.
# Result .deb appears under ./releases/<version> on the host.
# ==============================================================================

set -euo pipefail

# ==============================================================================
# Configuration
# ==============================================================================

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE_NAME="ecli-builder-bullseye"
DOCKERFILE="docker/build-linux.Dockerfile"
CONTAINER_NAME="ecli-build-deb"

# Colors for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m' # No Color

# ==============================================================================
# Helper Functions
# ==============================================================================

log() {
    echo -e "${BLUE}==>${NC} $*"
}

log_success() {
    echo -e "${GREEN}✅${NC} $*"
}

log_warning() {
    echo -e "${YELLOW}⚠️${NC} $*"
}

log_error() {
    echo -e "${RED}❌${NC} $*" >&2
}

cleanup() {
    local exit_code=$?
    if [ ${exit_code} -ne 0 ]; then
        log_error "Build failed with exit code ${exit_code}"

        # Clean up any running containers
        if docker ps -q -f name="${CONTAINER_NAME}" | grep -q .; then
            log "Cleaning up container: ${CONTAINER_NAME}"
            docker stop "${CONTAINER_NAME}" >/dev/null 2>&1 || true
            docker rm "${CONTAINER_NAME}" >/dev/null 2>&1 || true
        fi
    fi
}

check_prerequisites() {
    # Check if Docker is installed and running
    if ! command -v docker >/dev/null 2>&1; then
        log_error "Docker is not installed or not in PATH"
        exit 1
    fi

    if ! docker info >/dev/null 2>&1; then
        log_error "Docker daemon is not running or not accessible"
        exit 1
    fi

    # Check if Dockerfile exists
    if [ ! -f "${PROJECT_ROOT}/${DOCKERFILE}" ]; then
        log_error "Dockerfile not found: ${DOCKERFILE}"
        exit 1
    fi
}

show_usage() {
    cat <<EOF
Usage: $0 [OPTIONS]

Build ECLI .deb package in Docker container.

OPTIONS:
    -h, --help              Show this help message
    -f, --force             Force rebuild Docker image
    -c, --clean             Clean build (remove existing releases)
    --no-cache              Build Docker image without cache
    --verbose               Enable verbose output

EXAMPLES:
    $0                      # Standard build
    $0 --force              # Force rebuild image
    $0 --clean --no-cache   # Clean build without cache

EOF
}

# ==============================================================================
# Argument Parsing
# ==============================================================================

FORCE_REBUILD=false
CLEAN_BUILD=false
NO_CACHE=""
VERBOSE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_usage
            exit 0
            ;;
        -f|--force)
            FORCE_REBUILD=true
            shift
            ;;
        -c|--clean)
            CLEAN_BUILD=true
            shift
            ;;
        --no-cache)
            NO_CACHE="--no-cache"
            shift
            ;;
        --verbose)
            VERBOSE=true
            set -x  # Enable bash debugging
            shift
            ;;
        *)
            log_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# ==============================================================================
# Main Script
# ==============================================================================

main() {
    # Set up error handling
    trap cleanup EXIT

    # Change to project root
    cd "${PROJECT_ROOT}"

    log "Starting ECLI .deb build process"
    log "Project root: ${PROJECT_ROOT}"

    # Check prerequisites
    check_prerequisites

    # Clean build if requested
    if [ "${CLEAN_BUILD}" = true ]; then
        log_warning "Cleaning existing releases directory"
        rm -rf "${PROJECT_ROOT}/releases"
    fi

    # Create releases directory on the host
    mkdir -p "${PROJECT_ROOT}/releases"

    # Check if image exists and should be rebuilt
    if [ "${FORCE_REBUILD}" = true ] || ! docker image inspect "${IMAGE_NAME}" >/dev/null 2>&1; then
        log "Building Docker image: ${IMAGE_NAME}"
        if [ "${VERBOSE}" = true ]; then
            docker build ${NO_CACHE} -t "${IMAGE_NAME}" -f "${DOCKERFILE}" .
        else
            docker build ${NO_CACHE} -t "${IMAGE_NAME}" -f "${DOCKERFILE}" . --quiet
        fi
        log_success "Docker image built successfully"
    else
        log "Using existing Docker image: ${IMAGE_NAME}"
    fi

    # Get host UID/GID for proper file ownership
    HOST_UID="$(id -u)"
    HOST_GID="$(id -g)"

    log "Running packaging inside container..."
    log "Host UID:GID = ${HOST_UID}:${HOST_GID}"

    # Remove any existing container with the same name
    if docker ps -aq -f name="${CONTAINER_NAME}" | grep -q .; then
        log_warning "Removing existing container: ${CONTAINER_NAME}"
        docker rm -f "${CONTAINER_NAME}" >/dev/null 2>&1 || true
    fi

    # Build arguments
    DOCKER_ARGS=(
        --rm
        -u "${HOST_UID}:${HOST_GID}"
        -v "${PROJECT_ROOT}:/app:rw"
        -v "${PROJECT_ROOT}/releases:/app/releases:rw"
        --name "${CONTAINER_NAME}"
    )

    # Add additional environment variables if needed
    # DOCKER_ARGS+=(-e "BUILD_VERSION=${BUILD_VERSION:-}")

    # Run the container
    if docker run "${DOCKER_ARGS[@]}" "${IMAGE_NAME}"; then
        log_success "Build completed successfully!"

        # Show what was created
        if [ -d "${PROJECT_ROOT}/releases" ] && [ "$(ls -A "${PROJECT_ROOT}/releases" 2>/dev/null)" ]; then
            log "Generated files:"
            find "${PROJECT_ROOT}/releases" -name "*.deb" -type f -exec ls -lh {} \;
        else
            log_warning "No .deb files found in releases directory"
        fi
    else
        log_error "Container execution failed"
        exit 1
    fi
}

# ==============================================================================
# Script Entry Point
# ==============================================================================

# Only run main if script is executed directly (not sourced)
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
