# Build Matrix

## Platform Matrix (Current Observed)

- Linux: DEB/RPM/AppImage scripts and workflows
- FreeBSD: native `.pkg` via script and VM workflow
- macOS: DMG build workflow and script
- Windows: NSIS installer workflow and script

## Build Environment Notes

- Linux packaging relies on FPM and platform-specific dependencies.
- FreeBSD packaging requires native FreeBSD runtime context (host/VM/chroot pattern).
- Windows installer path requires NSIS (`makensis`).
- macOS DMG path relies on `hdiutil` and Python tooling.

## Validation State

- Actual flow support is bounded by current CI behavior and script/workflow drift.
- Any platform marked release-ready must satisfy artifact contract checks.
