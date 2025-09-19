#!/usr/bin/env bash
set -euo pipefail

# Этот скрипт:
# 1) строит бинарь ecli (PyInstaller) для Linux,
# 2) укладывает его в AppDir,
# 3) запускает appimage-builder для изготовления .AppImage

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="${1:-0.1.0}"
OUT_DIR="$PROJECT_ROOT/dist"
APPDIR="$PROJECT_ROOT/packaging/linux/appimage/AppDir"

mkdir -p "$OUT_DIR"
# 1) Собираем PyInstaller бинарь (если еще не собран)
bash "$PROJECT_ROOT/scripts/build_pyinstaller_linux.sh"

# 2) Кладём бинарь в AppDir/usr/bin/ecli
install -Dm755 "$PROJECT_ROOT/build/linux/dist/ecli" "$APPDIR/usr/bin/ecli"

# 3) Обновим версию в appimage-builder.yml (на лету)
sed -i "s/version: \".*\"/version: \"${VERSION}\"/" "$PROJECT_ROOT/packaging/linux/appimage/appimage-builder.yml"

# 4) Установим appimage-builder локально, если нет (для CI делаем в job)
if ! command -v appimage-builder >/dev/null 2>&1; then
  python3 -m pip install --user appimage-builder
  export PATH="$HOME/.local/bin:$PATH"
fi

# 5) Собираем AppImage
pushd "$PROJECT_ROOT"
appimage-builder --recipe packaging/linux/appimage/appimage-builder.yml --skip-test
popd

# Выходной файл будет в PROJECT_ROOT (по умолчанию appimage-builder кладёт рядом)
# Переименуем и переместим в dist
find "$PROJECT_ROOT" -maxdepth 1 -type f -name "*.AppImage" -print0 | while IFS= read -r -d '' f; do
  NEW="$OUT_DIR/ECLI-${VERSION}-x86_64.AppImage"
  mv "$f" "$NEW"
  echo "Created AppImage: $NEW"
done

# zsync (опционально для AppImageUpdate)
if command -v appimagetool >/dev/null 2>&1; then
  (cd "$OUT_DIR" && appimagetool --sign -v ECLI-${VERSION}-x86_64.AppImage || true)
fi
