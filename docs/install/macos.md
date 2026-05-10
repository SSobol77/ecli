<!--
Filename: docs/install/macos.md
Project:  ECLI
License:  MIT
Author:   Siergej Sobolewski
Copyright: (c) 2026 Siergej Sobolewski
-->

# Installing on macOS

ECLI v0.1.0 ships a Universal2 DMG for macOS 12 and newer:

```text
ecli_<version>_macos_universal2.dmg
ecli_<version>_macos_universal2.dmg.sha256
```

The Universal2 binary contains both `x86_64` and `arm64` slices, so the same
DMG is used on Intel Macs and Apple Silicon Macs.

## Install

1. Download `ecli_<version>_macos_universal2.dmg` and its `.sha256` sidecar from
   GitHub Releases.

2. Verify the checksum before mounting:

   ```sh
   shasum -a 256 -c ecli_<version>_macos_universal2.dmg.sha256
   ```

3. Mount the DMG:

   ```sh
   open ecli_<version>_macos_universal2.dmg
   ```

4. Run `ecli` from the mounted volume, or copy it to a directory on your `PATH`,
   such as `~/bin`.

## First Launch and Gatekeeper

ECLI v0.1.0 is ad-hoc signed but not notarized. On first launch, macOS
Gatekeeper may block it with a message similar to:

```text
ecli cannot be opened because the developer cannot be verified
```

Use one of these first-launch paths.

GUI path:

1. Open the mounted DMG in Finder.
2. Right-click `ecli`.
3. Choose **Open**.
4. Choose **Open** again in the warning dialog.

CLI path:

```sh
xattr -d com.apple.quarantine /Volumes/ECLI-<version>/ecli
```

If you copied the binary before first launch, remove quarantine from the copied
path instead:

```sh
xattr -d com.apple.quarantine ~/bin/ecli
```

## Why Is the Binary Unsigned?

ECLI v0.1.0 is an early release intended for early adopters and project
visibility. Apple Developer Program enrollment is not yet available for this
project, so v0.1.0 uses ad-hoc signing without notarization.

Developer ID signing, notarization, and stapling are planned for v0.2.
