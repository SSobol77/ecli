#!/usr/bin/env bash
# ==============================================================================
# Build and Package ECLI into a .deb file (inside container or locally)
#
# Do NOT touch $HOME — the app (utils.py) creates ~/.config/ecli on first run.
# We embed config.toml and bundle required runtime deps.
# ==============================================================================

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${PROJECT_ROOT}"

PACKAGE_NAME="ecli"
MAINTAINER="Siergej Sobolewski <s.sobolewski@hotmail.com>"
HOMEPAGE="https://ecli.io"
LICENSE="MIT"
CATEGORY="editors"

VERSION="$(python - <<'PY'
import tomllib
with open("pyproject.toml","rb") as f:
    print(tomllib.load(f)["project"]["version"])
PY
)"
[ -n "${VERSION}" ] || { echo "Cannot read version from pyproject.toml"; exit 1; }

ARCH_DEB="amd64"
RELEASES_DIR="releases/${VERSION}"
FINAL_DEB_PATH="${RELEASES_DIR}/${PACKAGE_NAME}_${VERSION}_${ARCH_DEB}.deb"
STAGING_DIR="build/deb_staging"

echo "==> Version: ${VERSION}"
rm -rf build/ dist/

echo "==> Building executable with PyInstaller"
if [[ -f "ecli.spec" ]]; then
  pyinstaller ecli.spec --clean --noconfirm
else
  # Fallback: force src layout and critical deps
  pyinstaller main.py \
    --name "${PACKAGE_NAME}" \
    --onefile --clean --noconfirm --strip \
    --paths "src" \
    --add-data "config.toml:." \
    --hidden-import=ecli \
    --hidden-import=dotenv --collect-all=dotenv \
    --hidden-import=toml \
    --hidden-import=aiohttp     --collect-all=aiohttp \
    --hidden-import=aiosignal   --collect-all=aiosignal \
    --hidden-import=yarl        --collect-all=yarl \
    --hidden-import=multidict   --collect-all=multidict \
    --hidden-import=frozenlist  --collect-all=frozenlist \
    --hidden-import=chardet     --collect-all=chardet \
    --runtime-hook packaging/pyinstaller/rthooks/force_imports.py
fi

# Detect PyInstaller output
EXECUTABLE=""
if [[ -x "dist/${PACKAGE_NAME}/${PACKAGE_NAME}" ]]; then
  EXECUTABLE="dist/${PACKAGE_NAME}/${PACKAGE_NAME}"
elif [[ -x "dist/${PACKAGE_NAME}" ]]; then
  EXECUTABLE="dist/${PACKAGE_NAME}"
fi
[ -n "${EXECUTABLE}" ] || { echo "PyInstaller output not found"; exit 1; }

echo "==> Preparing staging (FHS)"
rm -rf "${STAGING_DIR}"
mkdir -p \
  "${STAGING_DIR}/usr/bin" \
  "${STAGING_DIR}/usr/share/applications" \
  "${STAGING_DIR}/usr/share/icons/hicolor/256x256/apps" \
  "${STAGING_DIR}/usr/share/doc/${PACKAGE_NAME}" \
  "${STAGING_DIR}/usr/share/man/man1" \
  "${RELEASES_DIR}"

install -m 755 "${EXECUTABLE}" "${STAGING_DIR}/usr/bin/${PACKAGE_NAME}"

# Desktop entry
if [[ -f "packaging/linux/fpm-common/${PACKAGE_NAME}.desktop" ]]; then
  install -m 644 "packaging/linux/fpm-common/${PACKAGE_NAME}.desktop" \
    "${STAGING_DIR}/usr/share/applications/${PACKAGE_NAME}.desktop"
else
  cat > "${STAGING_DIR}/usr/share/applications/${PACKAGE_NAME}.desktop" <<EOF
[Desktop Entry]
Name=ECLI
Comment=Fast terminal code editor
Exec=${PACKAGE_NAME}
Icon=${PACKAGE_NAME}
Terminal=true
Type=Application
Categories=Development;TextEditor;
StartupNotify=false
EOF
fi

# Icon
if [[ -f "img/logo_m.png" ]]; then
  install -m 644 "img/logo_m.png" \
    "${STAGING_DIR}/usr/share/icons/hicolor/256x256/apps/${PACKAGE_NAME}.png"
fi

# Docs
[[ -f "LICENSE"   ]] && install -m 644 "LICENSE"   "${STAGING_DIR}/usr/share/doc/${PACKAGE_NAME}/LICENSE"
[[ -f "README.md" ]] && install -m 644 "README.md" "${STAGING_DIR}/usr/share/doc/${PACKAGE_NAME}/README.md"
[[ -f "${STAGING_DIR}/usr/share/doc/${PACKAGE_NAME}/README.md" ]] && gzip -9fn "${STAGING_DIR}/usr/share/doc/${PACKAGE_NAME}/README.md" || true
[[ -f "${STAGING_DIR}/usr/share/doc/${PACKAGE_NAME}/LICENSE"   ]] && gzip -9fn "${STAGING_DIR}/usr/share/doc/${PACKAGE_NAME}/LICENSE"   || true

# Minimal man page, if missing
if [[ ! -f "man/${PACKAGE_NAME}.1" ]]; then
  cat > "${STAGING_DIR}/usr/share/man/man1/${PACKAGE_NAME}.1" <<EOF
.TH ${PACKAGE_NAME^^} 1 "$(date +"%B %Y")" "${PACKAGE_NAME} ${VERSION}" "User Commands"
.SH NAME
${PACKAGE_NAME} - Terminal code editor
.SH SYNOPSIS
.B ${PACKAGE_NAME}
[\\fIOPTIONS\\fR] [\\fIFILE\\fR...]
.SH DESCRIPTION
${PACKAGE_NAME^^} is a fast terminal code editor.
.SH OPTIONS
\\fB--help\\fR     Show help
\\fB--version\\fR  Show version
.SH AUTHOR
${MAINTAINER%% <*}
.SH REPORTING BUGS
${HOMEPAGE}
EOF
  gzip -f "${STAGING_DIR}/usr/share/man/man1/${PACKAGE_NAME}.1"
else
  install -m 644 "man/${PACKAGE_NAME}.1" "${STAGING_DIR}/usr/share/man/man1/${PACKAGE_NAME}.1"
  gzip -f "${STAGING_DIR}/usr/share/man/man1/${PACKAGE_NAME}.1"
fi

echo "==> Building .deb with FPM"
fpm -s dir -t deb \
  -n "${PACKAGE_NAME}" -v "${VERSION}" -a "amd64" \
  --maintainer "${MAINTAINER}" \
  --description "Ecli — terminal DevOps editor with AI and Git integration" \
  --url "${HOMEPAGE}" --license "${LICENSE}" --category "${CATEGORY}" \
  --deb-priority optional --deb-compression xz \
  --after-install "packaging/linux/fpm-common/postinst" \
  --before-remove "packaging/linux/fpm-common/prerm" \
  --after-remove  "packaging/linux/fpm-common/postrm" \
  --package "${FINAL_DEB_PATH}" \
  -C "${STAGING_DIR}" usr

echo "==> Verify"
dpkg-deb --info "${FINAL_DEB_PATH}" >/dev/null || true
dpkg-deb --contents "${FINAL_DEB_PATH}" | head -20 || true
echo "✅ DONE: ${FINAL_DEB_PATH}"
