#!/usr/bin/env sh
# Verify an artifact against its basename-only SHA256 sidecar.
#
# Exit-code contract:
#   0 verified
#   1 invalid invocation or malformed sidecar
#   2 artifact missing
#   3 sidecar missing
#   4 checksum mismatch
#   5 missing checksum tool

set -u

if [ "$#" -ne 1 ]; then
    echo "Usage: scripts/verify-artifact.sh <artifact>" >&2
    exit 1
fi

artifact=$1
sidecar="${artifact}.sha256"

if [ ! -f "$artifact" ]; then
    echo "Missing $artifact"
    exit 2
fi

if [ ! -f "$sidecar" ]; then
    echo "Missing $sidecar"
    exit 3
fi

dir=$(dirname "$artifact")
base=$(basename "$artifact")

first_line=$(head -n 1 "$sidecar")
case "$first_line" in
    *"  $base")
        ;;
    *)
        echo "Malformed checksum sidecar: $sidecar"
        exit 1
        ;;
esac

if command -v sha256sum >/dev/null 2>&1; then
    (cd "$dir" && sha256sum -c "$base.sha256") || {
        echo "checksum mismatch: $artifact"
        exit 4
    }
elif command -v shasum >/dev/null 2>&1; then
    (cd "$dir" && shasum -a 256 -c "$base.sha256") || {
        echo "checksum mismatch: $artifact"
        exit 4
    }
else
    echo "Missing SHA256 tool: sha256sum or shasum"
    exit 5
fi
