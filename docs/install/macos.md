<!--
SPDX-License-Identifier: GPL-2.0-only

Project: Ecli
File: docs/install/macos.md
Website: https://www.ecli.io
Repository: https://github.com/SSobol77/ecli
PyPI: https://pypi.org/project/ecli-editor/0.0.1/

Copyright (c) 2026 Siergej Sobolewski

Licensed under the GNU General Public License version 2 only.
See the LICENSE file in the project root for full license text.
-->
# Installing on macOS

ECLI ships a Universal2 DMG for macOS 12 and newer:

```text
ecli_<version>_macos_universal2.dmg
ecli_<version>_macos_universal2.dmg.sha256
```

The Universal2 binary contains both `x86_64` and `arm64` slices, so the same
DMG is used on Intel Macs and Apple Silicon Macs.

For ECLI Full, the macOS `.app`/`.dmg` artifact must provision required F4
linter tools inside app resources or a managed runtime directory, detect
already-installed tools before adding missing ones, and verify executable/version
probes. Homebrew is acceptable for developer checkout, minimal install, repair,
or advanced administration, but a normal Full DMG/app install must not require a
post-install Homebrew linter setup step.

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

Current ECLI macOS artifacts are ad-hoc signed but not notarized. On first launch, macOS
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

ECLI is an early release intended for early adopters and project visibility.
Apple Developer Program enrollment is not yet available for this project, so
current artifacts use ad-hoc signing without notarization.

Developer ID signing, notarization, and stapling are planned for a later
release.
