#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
#
# Project: Ecli
# File: scripts/build-and-package-arch.sh
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file in the project root for full license text.

# Build an Arch Linux package from packaging/arch/PKGBUILD.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${PROJECT_ROOT}"

PACKAGE_NAME="ecli-editor"
VERSION="$(awk -F'"' '/^[[:space:]]*version[[:space:]]*=/ {print $2; exit}' pyproject.toml)"
[[ -n "${VERSION}" ]] || {
  echo "ERROR: Cannot read version from pyproject.toml" >&2
  exit 1
}
python3 scripts/check_runtime_imports.py

RAW_ARCH="$(uname -m 2>/dev/null || echo x86_64)"
case "${RAW_ARCH}" in
  amd64|x86_64) ARCH="x86_64" ;;
  aarch64|arm64) ARCH="aarch64" ;;
  *) ARCH="${RAW_ARCH}" ;;
esac

command -v makepkg >/dev/null 2>&1 || {
  echo "Arch makepkg is required to build pkg.tar.zst packages." >&2
  exit 5
}
command -v sha256sum >/dev/null 2>&1 || {
  echo "sha256sum is required to write package checksums." >&2
  exit 5
}

RELEASES_DIR="${PROJECT_ROOT}/releases/${VERSION}"
mkdir -p "${RELEASES_DIR}"
NORMALIZED_ARTIFACT="${RELEASES_DIR}/ecli_${VERSION}_arch_${ARCH}.pkg.tar.zst"

echo "==> Building Arch package"
(
  cd "${PROJECT_ROOT}/packaging/arch"
  ECLI_REPO_ROOT="${PROJECT_ROOT}" \
  PKGDEST="${RELEASES_DIR}" \
    makepkg --clean --force --noconfirm
)

raw_artifact="$(find "${RELEASES_DIR}" -maxdepth 1 -type f -name "${PACKAGE_NAME}-${VERSION}-*.pkg.tar.*" | sort | head -1)"
[[ -n "${raw_artifact}" && -f "${raw_artifact}" ]] || {
  echo "ERROR: Arch package artifact not found under ${RELEASES_DIR}." >&2
  exit 1
}

echo "==> Normalizing release artifact"
rm -f "${NORMALIZED_ARTIFACT}" "${NORMALIZED_ARTIFACT}.sha256"
cp -f "${raw_artifact}" "${NORMALIZED_ARTIFACT}"

echo "==> Writing checksum"
(cd "${RELEASES_DIR}" && sha256sum "$(basename "${NORMALIZED_ARTIFACT}")" > "$(basename "${NORMALIZED_ARTIFACT}").sha256")
scripts/verify_runtime.sh "${NORMALIZED_ARTIFACT}"

echo "Raw makepkg artifact: ${raw_artifact}"
echo "DONE: ${NORMALIZED_ARTIFACT}"
