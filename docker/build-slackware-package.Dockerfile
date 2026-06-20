# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: docker/build-slackware-package.Dockerfile
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

# ==============================================================================
# Dockerfile for building the ECLI Slackware .txz package.
#
# The aggregate release workflow runs on Ubuntu, which has no Slackware pkgtools,
# so the host-only `make package-slackware` target fails with
# "Missing makepkg for Slackware package build." (#93). This helper provides a
# real Slackware (-current) packaging environment: the genuine Slackware pkgtools
# (installpkg/upgradepkg/removepkg and the Slackware `makepkg`), a Python
# interpreter that satisfies the project's `requires-python = ">=3.11"` (Slackware
# -current ships Python 3.12), PyInstaller, the project runtime dependencies
# PyInstaller needs to import during analysis, and a generated UTF-8 locale the
# post-build runtime smoke check requires.
#
# Slackware `makepkg` is the traditional pkgtools packager and is normally run as
# root, so unlike the Arch helper this image does not drop to a non-root build
# user. The repository is bind-mounted at /app; raw makepkg output stays under
# build/ and only the canonical normalized artifact is written into
# releases/<version>/ (see scripts/build_and_package_slackware.py). Host-side
# ownership is reset after the run because the container writes as root (#93).
# ==============================================================================

FROM aclemons/slackware:current

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Refresh the slackpkg databases and install the development toolchain from the
# official Slackware -current tree. `python3` brings the Python 3.12 interpreter
# (>=3.11, the project floor) and `binutils` provides `strip`, which the
# PyInstaller spec requests on Linux (strip=True). Slackware has no automatic
# dependency resolution, but the base image already ships the libraries the
# interpreter links against (ssl/zlib/ncurses/...), so this curated set is
# sufficient. The GPG key import is best-effort: the key may already be present.
RUN slackpkg -batch=on -default_answer=yes update gpg || true \
 && slackpkg -batch=on -default_answer=yes update \
 && slackpkg -batch=on -default_answer=yes install python3 binutils

# Fail the image build early if the real Slackware pkgtools/makepkg environment is
# not present. makepkg ships with the base image's pkgtools; this is both a
# self-check and explicit documentation that this is a genuine Slackware
# packaging environment, not an Ubuntu host pretending to have makepkg.
RUN command -v makepkg && command -v installpkg && command -v upgradepkg

# Provide a real UTF-8 locale. The post-build runtime smoke check
# (scripts/verify_runtime.py) runs the bundled curses binary under a pseudo-TTY
# and decodes its output as UTF-8; under the C/POSIX locale ncurses/Python emit
# 8-bit latin-1 bytes (ECLI's "8 \xb7 Dark Neon" separator is U+00B7 written as a
# lone 0xB7), which breaks that decode. The DEB/RPM/Arch build images already
# ship a UTF-8 locale; `glibc-i18n` plus a generated `en_US.UTF-8` brings the
# Slackware build container to the same parity. slackpkg reuses the package
# lists fetched in the layer above.
RUN slackpkg -batch=on -default_answer=yes install glibc glibc-i18n \
 && localedef -i en_US -f UTF-8 en_US.UTF-8
ENV LANG=en_US.UTF-8 \
    LC_ALL=en_US.UTF-8

# Slackware's python3 package does not ship pip as an importable module, so
# bootstrap it from the bundled ensurepip wheels (offline) and upgrade it.
RUN python3 -m ensurepip --upgrade \
 && python3 -m pip install --no-cache-dir --root-user-action=ignore --upgrade pip

# Install PyInstaller plus the project runtime dependencies so PyInstaller can
# import them during analysis (mirrors the DEB helper). All of these resolve to
# cp312 manylinux wheels, so no C/Rust toolchain is required at build time.
RUN python3 -m pip install --no-cache-dir --root-user-action=ignore \
      pyinstaller \
      Pygments \
      pyperclip \
      wcwidth \
      chardet \
      PyYAML \
      attrs \
      typing_extensions \
      packaging \
      aiohttp \
      pygls \
      lsprotocol \
      libcst \
      cattrs \
      python-dotenv \
      toml \
      tato

WORKDIR /app

# Build the Slackware package inside the container using the canonical Python
# script. The Makefile `package-slackware-docker` target bind-mounts the repo at
# /app and runs this image as root, so the raw makepkg output lands under
# build/slackware/ and the normalized canonical artifact lands in the host
# releases/<version>/ tree; the host resets ownership and runs
# package-slackware-assert afterward (#93).
CMD ["python3", "scripts/build_and_package_slackware.py"]
