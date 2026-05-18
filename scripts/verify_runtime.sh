#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
#
# Project: Ecli
# File: scripts/verify_runtime.sh
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file in the project root for full license text.

# Cross-artifact launcher validation for packaged ECLI release outputs.
#
# Modes:
#   --mode native      execute the staged launcher on this host
#   --mode structural  verify package structure only; no execution claim
#   --mode auto        execute when host/artifact ABI is compatible, otherwise
#                      perform structural validation

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${PROJECT_ROOT}"

MODE="auto"
ARTIFACT=""
ALLOW_NONRELEASE=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --mode)
      MODE="${2:-}"
      shift 2
      ;;
    --mode=*)
      MODE="${1#--mode=}"
      shift
      ;;
    --allow-nonrelease)
      ALLOW_NONRELEASE=1
      shift
      ;;
    -h|--help)
      cat <<'EOF'
Usage: scripts/verify_runtime.sh [--mode auto|native|structural] [--allow-nonrelease] ARTIFACT

Validates packaged ECLI launchers. Native mode executes --help, --version, and
a bounded pseudo-TTY startup. Structural mode verifies expected package payload
paths when the artifact cannot run on the current host.
EOF
      exit 0
      ;;
    *)
      ARTIFACT="$1"
      shift
      ;;
  esac
done

case "$MODE" in
  auto|native|structural) ;;
  *) echo "Invalid mode: $MODE" >&2; exit 2 ;;
esac

find_python() {
  if [ -n "${PYTHON:-}" ] && command -v "$PYTHON" >/dev/null 2>&1; then
    printf '%s\n' "$PYTHON"
    return 0
  fi

  for candidate in python3 python3.12 python3.11 python3.10 python; do
    if command -v "$candidate" >/dev/null 2>&1; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done

  echo "ERR: Python interpreter not found for runtime verification" >&2
  return 1
}

PYTHON_BIN="$(find_python)"

VERSION="$("$PYTHON_BIN" - <<'PY'
import tomllib
with open("pyproject.toml", "rb") as f:
    print(tomllib.load(f)["project"]["version"])
PY
)"
EXPECTED_VERSION_OUTPUT="ecli ${VERSION}"

if [ -z "$ARTIFACT" ]; then
  raw_arch="$(uname -m 2>/dev/null || echo x86_64)"
  case "$raw_arch" in
    amd64|x86_64) arch="x86_64" ;;
    aarch64|arm64) arch="arm64" ;;
    *) arch="$raw_arch" ;;
  esac
  ARTIFACT="releases/${VERSION}/ecli_${VERSION}_linux_${arch}.deb"
fi

if [ ! -e "$ARTIFACT" ]; then
  echo "Runtime artifact not found: $ARTIFACT" >&2
  exit 3
fi

if [ "$ALLOW_NONRELEASE" -eq 0 ]; then
  case "$ARTIFACT" in
    releases/"$VERSION"/*|releases/"$VERSION") ;;
    "$PROJECT_ROOT"/releases/"$VERSION"/*|"$PROJECT_ROOT"/releases/"$VERSION") ;;
    *)
      echo "Artifact is outside current project version directory releases/${VERSION}: $ARTIFACT" >&2
      exit 4
      ;;
  esac
fi

tmpdir="$(mktemp -d)"
mountpoint=""
dmg_device=""

private_var_path() {
  case "$1" in
    /var/*) printf '/private%s\n' "$1" ;;
    *) printf '%s\n' "$1" ;;
  esac
}

is_mountpoint_mounted() {
  local path="$1"
  local private_path
  private_path="$(private_var_path "$path")"
  mount | awk -v mp="$path" -v private_mp="$private_path" '
    $3 == mp || $3 == private_mp { found = 1 }
    END { exit found ? 0 : 1 }
  '
}

is_dmg_device_attached() {
  [ -n "$dmg_device" ] || return 1
  hdiutil info 2>/dev/null | grep -F "$dmg_device" >/dev/null 2>&1
}

wait_for_mountpoint() {
  local path="$1"
  local attempt
  for attempt in 1 2 3 4 5; do
    if is_mountpoint_mounted "$path"; then
      return 0
    fi
    sleep 1
  done
  return 1
}

wait_for_detach() {
  local path="$1"
  local attempt
  for attempt in 1 2 3 4 5 6 7 8 9 10; do
    if ! is_mountpoint_mounted "$path" && ! is_dmg_device_attached; then
      return 0
    fi
    sleep 1
  done
  return 1
}

detach_dmg() {
  local target
  local attempt
  local output
  local rc

  set +e
  if [ -z "$mountpoint" ]; then
    set -e
    return 0
  fi
  if ! is_mountpoint_mounted "$mountpoint" && ! is_dmg_device_attached; then
    dmg_device=""
    set -e
    return 0
  fi

  target="${dmg_device:-$mountpoint}"
  for attempt in 1 2 3; do
    output="$(hdiutil detach "$target" 2>&1)"
    rc=$?
    if [ "$rc" -eq 0 ] && wait_for_detach "$mountpoint"; then
      dmg_device=""
      set -e
      return 0
    fi
    echo "WARNING: hdiutil detach retry ${attempt}/3 failed or did not settle for ${target}." >&2
    [ -z "$output" ] || printf '%s\n' "$output" >&2
    sleep 1
  done

  output="$(hdiutil detach -force "$target" 2>&1)"
  rc=$?
  if [ "$rc" -ne 0 ]; then
    echo "WARNING: hdiutil detach -force failed for ${target}." >&2
    [ -z "$output" ] || printf '%s\n' "$output" >&2
  fi
  if ! wait_for_detach "$mountpoint"; then
    echo "WARNING: DMG mount/device did not fully detach before cleanup: ${mountpoint}" >&2
  fi
  dmg_device=""
  set -e
}

attach_dmg() {
  local artifact="$1"
  local output_file="$tmpdir/hdiutil-attach.out"
  local attempt
  local rc

  for attempt in 1 2 3 4 5; do
    : >"$output_file"
    set +e
    hdiutil attach -readonly -nobrowse -mountpoint "$mountpoint" "$artifact" >"$output_file" 2>&1
    rc=$?
    set -e

    if [ "$rc" -eq 0 ]; then
      dmg_device="$(awk '/^\/dev\/disk/ { print $1; exit }' "$output_file")"
      if wait_for_mountpoint "$mountpoint"; then
        return 0
      fi
      echo "WARNING: hdiutil attach succeeded but mountpoint did not settle: ${mountpoint}" >&2
      detach_dmg
    else
      echo "WARNING: hdiutil attach failed for ${artifact} (attempt ${attempt}/5, rc=${rc})." >&2
      sed 's/^/hdiutil: /' "$output_file" >&2
    fi

    if [ "$attempt" -lt 5 ]; then
      sleep 2
    fi
  done

  echo "ERR: failed to attach DMG: ${artifact}" >&2
  sed 's/^/hdiutil: /' "$output_file" >&2
  return 6
}

cleanup() {
  set +e
  if [ -n "$mountpoint" ] && command -v hdiutil >/dev/null 2>&1; then
    detach_dmg
  fi
  rm -rf "$tmpdir" >/dev/null 2>&1 || true
  return 0
}
trap cleanup EXIT

host_os="$(uname -s 2>/dev/null || echo unknown)"

can_execute_artifact() {
  case "$1" in
    *.deb|*.rpm|*.AppImage|*.tar.gz|*.tgz|*.txz|*.pkg.tar.zst)
      [ "$host_os" = "Linux" ]
      ;;
    *.pkg)
      [ "$host_os" = "FreeBSD" ]
      ;;
    *.dmg)
      [ "$host_os" = "Darwin" ]
      ;;
    *.exe)
      case "$host_os" in MINGW*|MSYS*|CYGWIN*) return 0 ;; *) return 1 ;; esac
      ;;
    *)
      [ -x "$1" ]
      ;;
  esac
}

extract_artifact() {
  local artifact="$1"
  local root="$tmpdir/root"
  mkdir -p "$root"

  if [ -d "$artifact" ]; then
    printf '%s\n' "$artifact"
    return 0
  fi

  case "$artifact" in
    *.deb)
      command -v dpkg-deb >/dev/null 2>&1 || {
        echo "dpkg-deb is required to extract $artifact" >&2
        return 1
      }
      dpkg-deb -x "$artifact" "$root"
      ;;
    *.rpm)
      if command -v rpm2cpio >/dev/null 2>&1 && command -v cpio >/dev/null 2>&1; then
        case "$artifact" in
          /*) rpm_input="$artifact" ;;
          *) rpm_input="$PROJECT_ROOT/$artifact" ;;
        esac
        (cd "$root" && rpm2cpio "$rpm_input" | cpio -idm --quiet)
      elif command -v bsdtar >/dev/null 2>&1; then
        bsdtar -xf "$artifact" -C "$root"
      else
        echo "rpm2cpio+cpio or bsdtar is required to extract $artifact" >&2
        return 1
      fi
      ;;
    *.pkg)
      tar -xf "$artifact" -C "$root"
      ;;
    *.tar.gz|*.tgz)
      tar -xzf "$artifact" -C "$root"
      ;;
    *.txz|*.pkg.tar.zst)
      tar -xf "$artifact" -C "$root"
      ;;
    *.dmg)
      if [ "$host_os" != "Darwin" ]; then
        echo "DMG structural inspection requires macOS; CI must run native macOS smoke." >&2
        return 2
      fi
      mountpoint="$tmpdir/dmg"
      mkdir -p "$mountpoint"
      attach_dmg "$artifact" || return $?
      printf '%s\n' "$mountpoint"
      return 0
      ;;
    *.AppImage|*.exe)
      install -m 0755 "$artifact" "$root/ecli"
      ;;
    *)
      if [ -x "$artifact" ]; then
        install -m 0755 "$artifact" "$root/ecli"
      else
        echo "Unsupported artifact type: $artifact" >&2
        return 1
      fi
      ;;
  esac

  printf '%s\n' "$root"
}

find_launcher() {
  local root="$1"
  for candidate in \
    "$root/usr/bin/ecli" \
    "$root/usr/local/bin/ecli" \
    "$root/ecli" \
    "$root/ECLI.app/Contents/MacOS/ecli"; do
    if [ -x "$candidate" ]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  find "$root" -maxdepth 5 -type f \( -name ecli -o -name ecli.exe \) -perm -111 -print | head -n 1
}

scan_logs() {
  local home="$1"
  local log_file="$home/.config/ecli/logs/editor.log"
  [ -f "$log_file" ] || return 0
  if grep -E "ModuleNotFoundError|No module named 'unittest'|CRITICAL - ecli - Failed to import a critical application component" "$log_file" >/dev/null; then
    echo "Runtime smoke created forbidden startup log entries:" >&2
    cat "$log_file" >&2
    return 1
  fi
}

run_command() {
  local home="$1"
  shift
  HOME="$home" TERM="${TERM:-xterm-256color}" "$@"
}

run_native_smoke() {
  local binary="$1"
  local home="$tmpdir/home"
  local out="$tmpdir/stdout"
  local err="$tmpdir/stderr"
  mkdir -p "$home"

  run_command "$home" "$binary" --help >"$out" 2>"$err"
  [ -s "$out" ] || {
    echo "Runtime smoke --help produced no stdout." >&2
    cat "$err" >&2 || true
    return 1
  }

  run_command "$home" "$binary" --version >"$out" 2>"$err"
  version_output="$(tr -d '\r' <"$out" | sed -n '1p')"
  if [ "$version_output" != "$EXPECTED_VERSION_OUTPUT" ]; then
    echo "Unexpected --version output: '$version_output' (expected '$EXPECTED_VERSION_OUTPUT')" >&2
    cat "$err" >&2 || true
    return 1
  fi

  if command -v timeout >/dev/null 2>&1 && command -v script >/dev/null 2>&1; then
    set +e
    timeout 3s script -q -c "HOME='$home' TERM='${TERM:-xterm-256color}' '$binary'" /dev/null \
      >"$tmpdir/tty.stdout" 2>"$tmpdir/tty.stderr"
    tty_rc=$?
    set -e
    case "$tty_rc" in
      0|124) ;;
      *)
        echo "Bare ECLI pseudo-TTY startup exited unexpectedly with status $tty_rc" >&2
        cat "$tmpdir/tty.stderr" >&2 || true
        return 1
        ;;
    esac
  else
    echo "WARNING: timeout or script unavailable; skipping bounded pseudo-TTY startup." >&2
  fi

  scan_logs "$home"
}

run_structural_check() {
  local artifact="$1"
  local root="$2"

  case "$artifact" in
    *.rpm)
      if command -v rpm >/dev/null 2>&1; then
        rpm -qpl "$artifact" | grep -E '(^|/)usr/bin/ecli$' >/dev/null
      else
        [ -n "$(find_launcher "$root")" ]
      fi
      ;;
    *.pkg)
      tar -tf "$artifact" | grep -E '(^|/)usr/local/bin/ecli$' >/dev/null
      ;;
    *.dmg)
      if [ "$host_os" = "Darwin" ]; then
        [ -n "$(find_launcher "$root")" ]
      else
        [ -s "$artifact" ]
      fi
      ;;
    *.exe)
      [ -s "$artifact" ]
      ;;
    *)
      [ -n "$(find_launcher "$root")" ]
      ;;
  esac
}

report_structural_pass() {
  echo "--> OK: structural package contract passed for $1 (runtime execution was not performed)"
}

root=""
extract_rc=0
root="$(extract_artifact "$ARTIFACT")" || extract_rc=$?

if [ "$extract_rc" -ne 0 ]; then
  if [ "$MODE" = "native" ] || { [ "$host_os" = "Darwin" ] && [ "${ARTIFACT##*.}" = "dmg" ]; }; then
    exit "$extract_rc"
  fi
  run_structural_check "$ARTIFACT" "$tmpdir/root"
  report_structural_pass "$ARTIFACT"
  exit 0
fi

binary="$(find_launcher "$root")"

if [ "$MODE" = "structural" ]; then
  run_structural_check "$ARTIFACT" "$root"
  report_structural_pass "$ARTIFACT"
  exit 0
fi

if [ "$MODE" = "native" ] || can_execute_artifact "$ARTIFACT"; then
  if [ -z "$binary" ] || [ ! -x "$binary" ]; then
    echo "Runtime launcher is missing or not executable under $root" >&2
    exit 5
  fi
  run_native_smoke "$binary"
  echo "--> OK: native runtime smoke passed for $ARTIFACT"
else
  run_structural_check "$ARTIFACT" "$root"
  report_structural_pass "$ARTIFACT"
fi
