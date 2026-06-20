# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: docker/build-arch-package.Dockerfile
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

# ==============================================================================
# Dockerfile for building the ECLI Arch Linux .pkg.tar.zst package.
#
# The aggregate release workflow runs on Ubuntu, which has no makepkg/PKGBUILD
# toolchain, so the host-only `make package-arch` target fails with
# "Missing makepkg for Arch package build." (#93). This helper provides a real
# Arch base-devel packaging environment: makepkg, the PKGBUILD makedepends, and
# the runtime libraries the bundled binary needs.
#
# makepkg refuses to run as root, so the container drops to a non-root build user
# for the actual build. The repository is bind-mounted at /app and only the
# canonical normalized artifact is written into releases/<version>/; raw makepkg
# output stays under build/ (see scripts/build_and_package_arch.py).
# ==============================================================================

FROM archlinux:base-devel

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Refresh the package databases and install the runtime/build dependencies that
# Arch ships in the official repos, plus the runtime libraries (ncurses, libyaml)
# the bundled ECLI binary links against. These are built against Arch's current
# Python, so PyInstaller can import them during analysis. base-devel already
# provides makepkg/fakeroot/gcc; --needed keeps the layer idempotent and
# pacman -Scc trims the download cache.
RUN pacman -Syu --noconfirm --needed \
      git \
      libyaml \
      ncurses \
      python \
      python-aiohttp \
      python-attrs \
      python-cattrs \
      python-chardet \
      python-dotenv \
      python-libcst \
      python-lsprotocol \
      python-packaging \
      python-pip \
      python-pygls \
      python-pygments \
      python-pyperclip \
      python-toml \
      python-wcwidth \
      python-yaml \
  && pacman -Scc --noconfirm

# PyInstaller is not in the official Arch repos (only AUR), so install it with pip
# into the system interpreter. PEP 668 marks Arch's Python as externally managed;
# --break-system-packages is the supported override inside this throwaway build
# image. makepkg is run with --nodeps (see scripts/build_and_package_arch.py)
# because this build image - not pacman - provisions the build toolchain.
RUN python -m pip install --no-cache-dir --break-system-packages pyinstaller

# makepkg refuses to run as root. Create a non-root build user; the entrypoint
# drops to it (via runuser) after preparing the bind-mounted output directories.
RUN useradd --create-home --shell /bin/bash builder

WORKDIR /app

# Build the Arch package inside the container using the canonical Python script.
# The repo is bind-mounted at /app (host-owned). build/, dist/, and releases/ are
# created and handed to the build user so makepkg (non-root) can write its raw
# output (build/arch) and the normalized release artifact (releases/<version>/);
# host-side ownership is reset after the run (#93). The source tree itself is
# never written to: scripts/build_and_package_arch.py runs makepkg from a copy of
# the PKGBUILD under build/arch.
CMD ["bash", "-c", "set -euo pipefail; for d in build dist releases; do mkdir -p \"/app/$d\"; chown -R builder:builder \"/app/$d\"; done; exec runuser -u builder -- env HOME=/home/builder PATH=/usr/local/sbin:/usr/local/bin:/usr/bin python scripts/build_and_package_arch.py"]
