#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: scripts/build_and_package_deb.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Build and package ECLI into a Debian/Ubuntu ``.deb``.

Canonical Python replacement for ``scripts/build-and-package-deb.sh``. It builds
a standalone executable with PyInstaller, stages a minimal FHS payload, and
produces ``releases/<version>/ecli_<version>_linux_<arch>.deb`` with FPM plus a
SHA256 sidecar. Artifact naming and output locations are preserved exactly.

The ``.deb`` itself is built, inspected, runtime-verified, and Lintian-gated
entirely in a temporary location; the final artifact and its checksum sidecar
are only ever written via one atomic promotion after every gate has passed.
A failed gate never leaves a new (partial or unverified) final artifact
behind, and never touches a previously promoted one.

This script validates ECLI packaging only. It never provisions, downloads, or
verifies the F4 linter toolchain -- that is the sole responsibility of the
standalone stage-1 installer (``scripts/install_ecli_linters.py``) and its own
clean-room validation. It never publishes, uploads, signs with external keys,
tags, pushes, or triggers any workflow.

Exit codes:

* ``0`` package built, gated, and promoted
* ``1`` missing tool, missing version, missing PyInstaller output, or a
  failed pre-promotion gate (info/contents/runtime/Lintian)
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import time
import tomllib
from pathlib import Path

from f4_linter_packaging import (
    artifact_ids_from_env,
    run_or_record_f4_linter_provisioning_for_artifacts,
)
from packaging_common import (
    filename_arch,
    gzip_file,
    install_desktop_entry,
    install_docs,
    install_file,
    install_icon,
    require_tool,
)


EXIT_OK = 0
EXIT_ERROR = 1

PACKAGE_NAME = "ecli"
MAINTAINER = "Siergej Sobolewski <s.sobolewski@hotmail.com>"
HOMEPAGE = "https://ecli.io"
LICENSE = "GPL-2.0-only"
CATEGORY = "editors"

# The PyInstaller executable dynamically links libc.so.6 and libz.so.1
# (readelf -d: NEEDED libc.so.6, NEEDED libz.so.1), so libc6 and zlib1g are
# genuine runtime dependencies; without them lintian correctly reports
# missing-dependency-on-libc / a missing zlib dependency, and a system that
# lacks zlib1g (rare, but not guaranteed present transitively) would fail
# to start the binary at all.
DEB_DEPENDS = (
    "libc6",
    "libncurses6",
    "libncursesw6",
    "libtinfo6",
    "ncurses-term",
    "libyaml-0-2",
    "zlib1g",
    "xclip | xsel",
)

# Debian policy: the synopsis must not start with the package name; the
# extended description must be non-empty. FPM folds the newline-separated
# lines into a correct multi-line Description field.
DEB_DESCRIPTION = (
    "terminal-first DevOps editor with AI and Git integration\n"
    "ECLI is a fast terminal code editor for engineering operations\n"
    "work: editing, Git integration, F4 diagnostics, and optional AI\n"
    "assistance. F4 verifies up to 19 provisioned linter/toolchain\n"
    "executables and runs diagnostics through 14 registered providers.\n"
    "The 19-tool toolchain is provisioned separately; see\n"
    "https://ecli.io and the project documentation for the linter\n"
    "installer. This package installs only ECLI itself."
)

# Deterministic release timestamp used for the Debian changelog entry, the
# staged file mtimes, and generated gzip members, and exported as
# SOURCE_DATE_EPOCH to FPM and to the post-build dpkg-deb repack step so the
# archive metadata (ar/tar member timestamps) is byte-reproducible.
# Overridable via the SOURCE_DATE_EPOCH environment variable.
RELEASE_EPOCH_DEFAULT = 1783123200  # 2026-07-04T00:00:00Z

# Narrow, documented lintian overrides shipped by the package. Only tags
# that are investigated and unavoidable belong here.
#
# Deliberately context-free (no "[usr/bin/ecli]" suffix): the override
# file syntax for a tag's context is NOT portable across the two lintian
# releases this pipeline runs -- bullseye's lintian 2.104 (the build-time
# gate) prints/matches contexts as bare "usr/bin/ecli", while trixie's
# lintian 2.122 (the downstream clean-room validation) prints/matches
# "[usr/bin/ecli]" with brackets; each rejects the other's format with
# "mismatched-override", turning the override into a no-op and failing
# the build. Evidence: both formats were verified empirically against
# both lintian versions (see the packaging round-3 evidence archive). A
# context-free override matches the tag regardless of that formatting
# difference and remains unambiguous in practice, since this package
# ships exactly one ELF binary the "hardening-no-pie" tag could ever fire
# against.
LINTIAN_OVERRIDES = (
    "# The executable is produced by PyInstaller, whose precompiled Linux\n"
    "# bootloader is a non-PIE ELF (readelf -h: Type EXEC). Rebuilding the\n"
    "# PyInstaller bootloader as PIE is not supported by this packaging\n"
    "# pipeline. This package ships exactly one ELF binary (usr/bin/ecli),\n"
    "# so this override is unambiguous even without a context suffix; a\n"
    "# context is deliberately omitted because its required syntax is not\n"
    "# portable across the lintian versions this pipeline runs (bullseye\n"
    "# 2.104 build-time gate vs. trixie 2.122 downstream validation).\n"
    "ecli: hardening-no-pie\n"
)
# Exactly this many lintian overrides are expected; any other count means
# either the override is missing or an unexpected additional one appeared.
EXPECTED_LINTIAN_OVERRIDE_COUNT = 1


class GateError(RuntimeError):
    """A mandatory pre-promotion gate failed; never promote on this."""


def python_bin() -> str:
    return os.environ.get("PYTHON", "python3")


def read_version(root: Path) -> str:
    with (root / "pyproject.toml").open("rb") as handle:
        data = tomllib.load(handle)
    return str(data["project"]["version"])


def release_epoch() -> int:
    """Deterministic build timestamp (SOURCE_DATE_EPOCH env or default)."""
    raw = os.environ.get("SOURCE_DATE_EPOCH", "")
    return int(raw) if raw.isdigit() else RELEASE_EPOCH_DEFAULT


def deterministic_env(epoch: int) -> dict[str, str]:
    """Process environment with SOURCE_DATE_EPOCH pinned for every child
    tool that participates in producing archive bytes (FPM, dpkg-deb).
    """
    env = dict(os.environ)
    env["SOURCE_DATE_EPOCH"] = str(epoch)
    return env


def desktop_entry() -> str:
    return (
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=ECLI\n"
        "Comment=Terminal-first engineering operations workbench\n"
        f"Exec={PACKAGE_NAME}\n"
        f"Icon={PACKAGE_NAME}\n"
        "Terminal=true\n"
        "Categories=Development;IDE;Utility;\n"
        "StartupNotify=false\n"
    )


def man_page(version: str, epoch: int = RELEASE_EPOCH_DEFAULT) -> str:
    """Render the man page. The date is derived only from ``epoch`` (never
    from wall-clock time) so the rendered text is reproducible.
    """
    date_str = time.strftime("%B %Y", time.gmtime(epoch))
    author = MAINTAINER.split(" <", 1)[0]
    return (
        f'.TH {PACKAGE_NAME.upper()} 1 "{date_str}" "{PACKAGE_NAME} {version}" '
        '"User Commands"\n'
        ".SH NAME\n"
        f"{PACKAGE_NAME} - Terminal code editor\n"
        ".SH SYNOPSIS\n"
        f".B {PACKAGE_NAME}\n"
        "[\\fIOPTIONS\\fR] [\\fIFILE\\fR...]\n"
        ".SH DESCRIPTION\n"
        f"{PACKAGE_NAME.upper()} is a fast terminal code editor.\n"
        ".SH OPTIONS\n"
        "\\fB--help\\fR     Show help\n"
        "\\fB--version\\fR  Show version\n"
        ".SH AUTHOR\n"
        f"{author}\n"
        ".SH REPORTING BUGS\n"
        f"{HOMEPAGE}\n"
    )


def debian_changelog(version: str, epoch: int) -> str:
    """Render a minimal valid Debian changelog for this native package."""
    stamp = time.strftime("%a, %d %b %Y %H:%M:%S +0000", time.gmtime(epoch))
    return (
        f"{PACKAGE_NAME} ({version}) unstable; urgency=medium\n"
        "\n"
        f"  * ECLI release {version}. See README.md and the project\n"
        "    changelog for details.\n"
        "\n"
        f" -- {MAINTAINER}  {stamp}\n"
    )


def debian_copyright() -> str:
    """Render the machine-readable (DEP-5) Debian copyright file."""
    return (
        "Format: https://www.debian.org/doc/packaging-manuals/"
        "copyright-format/1.0/\n"
        f"Upstream-Name: {PACKAGE_NAME}\n"
        "Source: https://github.com/SSobol77/ecli\n"
        "\n"
        "Files: *\n"
        "Copyright: 2026 Siergej Sobolewski <s.sobolewski@hotmail.com>\n"
        "License: GPL-2\n"
        " This package is free software; you can redistribute it and/or\n"
        " modify it under the terms of the GNU General Public License\n"
        " version 2 only, as published by the Free Software Foundation.\n"
        " .\n"
        " This package is distributed in the hope that it will be useful,\n"
        " but WITHOUT ANY WARRANTY; without even the implied warranty of\n"
        " MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the\n"
        " GNU General Public License for more details.\n"
        " .\n"
        " On Debian systems, the complete text of the GNU General Public\n"
        ' License version 2 can be found in "/usr/share/common-licenses/'
        'GPL-2".\n'
    )


def normalize_tree_mtime(root: Path, epoch: int) -> None:
    """Pin every file/dir mtime under ``root`` to ``epoch``.

    ``shutil.copy2`` (used by ``install_file``) preserves the source file's
    original mtime, and a fresh git checkout's mtimes are "now" -- both
    vary between machines and between runs on the same machine. Content
    that is byte-identical across two builds must also have identical
    metadata for the packaged archive to be byte-identical; this removes
    mtime as a source of nondeterminism independent of whatever tar/ar
    timestamp handling the downstream packaging tools apply on their own.
    """
    for dirpath, dirnames, filenames in os.walk(root):
        base = Path(dirpath)
        for name in (*dirnames, *filenames):
            path = base / name
            os.utime(path, (epoch, epoch), follow_symlinks=False)
    os.utime(root, (epoch, epoch))


def strip_control_fields(deb_path: Path, fields: tuple[str, ...], epoch: int) -> None:
    """Rebuild the .deb without FPM's non-policy control fields.

    fpm's deb control template emits ``License:`` unconditionally (and a
    default ``Vendor:``); Debian policy keeps license data in
    ``usr/share/doc/<pkg>/copyright`` and lintian flags both as
    ``unknown-field``. dpkg-deb re-packs with ``--root-owner-group`` so
    file ownership stays root:root, ``-Zxz`` preserves the xz compression
    contract, and the same ``SOURCE_DATE_EPOCH`` used for the FPM build is
    passed through so the rebuilt ar container members stay reproducible.
    """
    env = deterministic_env(epoch)
    with tempfile.TemporaryDirectory(dir=str(deb_path.parent)) as tmp:
        extract = Path(tmp) / "pkg"
        subprocess.run(
            ["dpkg-deb", "-R", str(deb_path), str(extract)], check=True, env=env
        )
        control = extract / "DEBIAN" / "control"
        kept = [
            line
            for line in control.read_text(encoding="utf-8").splitlines(keepends=True)
            if not any(line.startswith(f"{field}:") for field in fields)
        ]
        control.write_text("".join(kept), encoding="utf-8")
        normalize_tree_mtime(extract, epoch)
        rebuilt = Path(tmp) / deb_path.name
        subprocess.run(
            [
                "dpkg-deb",
                "-b",
                "--root-owner-group",
                "-Zxz",
                str(extract),
                str(rebuilt),
            ],
            check=True,
            env=env,
        )
        os.replace(rebuilt, deb_path)


def run_lintian_gate(deb_path: Path, root: Path) -> None:
    """Mandatory pre-promotion Lintian gate.

    Fail-closed: any Lintian error, any warning, or a number of overrides
    other than exactly ``EXPECTED_LINTIAN_OVERRIDE_COUNT`` aborts the build
    before the candidate artifact is ever promoted to its final path.
    """
    result = subprocess.run(
        ["lintian", "--tag-display-limit", "0", "--show-overrides", str(deb_path)],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    output = result.stdout + result.stderr
    print(output)
    errors = [line for line in output.splitlines() if line.startswith("E:")]
    warnings = [line for line in output.splitlines() if line.startswith("W:")]
    overrides = [line for line in output.splitlines() if line.startswith("O:")]
    if errors or warnings or len(overrides) != EXPECTED_LINTIAN_OVERRIDE_COUNT:
        raise GateError(
            "lintian gate failed: "
            f"{len(errors)} error(s), {len(warnings)} warning(s), "
            f"{len(overrides)} override(s) "
            f"(expected exactly {EXPECTED_LINTIAN_OVERRIDE_COUNT})"
        )


def sha256_sidecar_text(artifact: Path) -> str:
    r"""Coreutils-format ``sha256sum`` sidecar text: ``<hex>  <basename>\n``."""
    digest = hashlib.sha256()
    with artifact.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return f"{digest.hexdigest()}  {artifact.name}\n"


def find_executable(root: Path) -> Path | None:
    onedir = root / "dist" / PACKAGE_NAME / PACKAGE_NAME
    onefile = root / "dist" / PACKAGE_NAME
    if onedir.is_file() and os.access(onedir, os.X_OK):
        return onedir
    if onefile.is_file() and os.access(onefile, os.X_OK):
        return onefile
    return None


def run_pyinstaller(root: Path, epoch: int) -> None:
    # PYTHONHASHSEED pins Python's hash randomization (affects iteration
    # order of any set/dict PyInstaller's own module-collection code uses
    # internally); SOURCE_DATE_EPOCH is passed through in case PyInstaller
    # or its bootloader honors it for embedded build metadata. Neither is
    # a complete reproducibility guarantee for PyInstaller output on its
    # own -- see the reproducibility evidence in the release report.
    env = deterministic_env(epoch)
    env["PYTHONHASHSEED"] = "0"
    spec = root / "packaging" / "pyinstaller" / "ecli.spec"
    if spec.is_file():
        subprocess.run(
            [
                "pyinstaller",
                "packaging/pyinstaller/ecli.spec",
                "--clean",
                "--noconfirm",
            ],
            cwd=root,
            check=True,
            env=env,
        )
        return
    subprocess.run(
        [
            "pyinstaller",
            "main.py",
            "--name",
            PACKAGE_NAME,
            "--onefile",
            "--clean",
            "--noconfirm",
            "--strip",
            "--paths",
            "src",
            "--add-data",
            "config.toml:.",
            "--add-data",
            "pyproject.toml:.",
            "--hidden-import=ecli",
            "--hidden-import=dotenv",
            "--collect-all=dotenv",
            "--hidden-import=toml",
            "--hidden-import=aiohttp",
            "--collect-all=aiohttp",
            "--hidden-import=aiosignal",
            "--collect-all=aiosignal",
            "--hidden-import=yarl",
            "--collect-all=yarl",
            "--hidden-import=multidict",
            "--collect-all=multidict",
            "--hidden-import=frozenlist",
            "--collect-all=frozenlist",
            "--hidden-import=chardet",
            "--collect-all=chardet",
            "--runtime-hook",
            "packaging/pyinstaller/rthooks/force_imports.py",
        ],
        cwd=root,
        check=True,
        env=env,
    )


def stage_payload(
    root: Path, staging: Path, executable: Path, version: str, epoch: int
) -> None:
    """Stage the FHS payload tree under ``staging`` (matches the shell layout)."""
    shutil.rmtree(staging, ignore_errors=True)
    for sub in (
        "usr/bin",
        "usr/share/applications",
        "usr/share/pixmaps",
        f"usr/share/doc/{PACKAGE_NAME}",
        "usr/share/man/man1",
    ):
        (staging / sub).mkdir(parents=True, exist_ok=True)

    install_file(executable, staging / "usr/bin" / PACKAGE_NAME, 0o755)

    install_desktop_entry(
        root,
        staging / "usr/share/applications" / f"{PACKAGE_NAME}.desktop",
        PACKAGE_NAME,
        desktop_entry(),
    )
    # The project icon is 200x199; installing it under a hicolor size
    # directory triggers lintian icon-size-and-directory-name-mismatch.
    # /usr/share/pixmaps has no size contract and the desktop entry's
    # Icon=ecli resolves there.
    install_icon(root, staging / "usr/share/pixmaps" / f"{PACKAGE_NAME}.png")

    doc_dir = staging / "usr/share/doc" / PACKAGE_NAME
    install_docs(root, doc_dir)
    for name in ("LICENSE", "README.md"):
        if (doc_dir / name).is_file():
            gzip_file(doc_dir / name, mtime=epoch)
    # Debian policy requires an uncompressed copyright file.
    (doc_dir / "copyright").write_text(debian_copyright(), encoding="utf-8")
    os.chmod(doc_dir / "copyright", 0o644)

    overrides_dir = staging / "usr/share/lintian/overrides"
    overrides_dir.mkdir(parents=True, exist_ok=True)
    (overrides_dir / PACKAGE_NAME).write_text(LINTIAN_OVERRIDES, encoding="utf-8")
    os.chmod(overrides_dir / PACKAGE_NAME, 0o644)

    man_dst = staging / "usr/share/man/man1" / f"{PACKAGE_NAME}.1"
    repo_man = root / "man" / f"{PACKAGE_NAME}.1"
    if repo_man.is_file():
        install_file(repo_man, man_dst, 0o644)
    else:
        man_dst.write_text(man_page(version, epoch), encoding="utf-8")
    gzip_file(man_dst, mtime=epoch)

    # Reproducibility: pin every staged file/dir mtime to the release
    # epoch. Applied last so it also covers the executable, desktop entry,
    # icon, and gzip members copied/written above.
    normalize_tree_mtime(staging, epoch)


def build_fpm_command(
    staging: Path, version: str, final_deb: Path, changelog: Path | None = None
) -> list[str]:
    """Construct the FPM .deb command array (deterministic, no shell).

    prerm/postrm are intentionally not packaged: they perform no work for
    this package (user configuration is never touched), and Debian policy
    forbids shipping empty maintainer scripts
    (lintian maintainer-script-empty).
    """
    cmd = [
        "fpm",
        "-s",
        "dir",
        "-t",
        "deb",
        "-n",
        PACKAGE_NAME,
        "-v",
        version,
        "-a",
        "amd64",
        "--maintainer",
        MAINTAINER,
        "--description",
        DEB_DESCRIPTION,
        "--url",
        HOMEPAGE,
        "--license",
        LICENSE,
        "--category",
        CATEGORY,
        "--deb-priority",
        "optional",
        "--deb-compression",
        "xz",
    ]
    if changelog is not None:
        cmd += ["--deb-changelog", str(changelog)]
    for dep in DEB_DEPENDS:
        cmd += ["--depends", dep]
    cmd += [
        "--after-install",
        "packaging/linux/fpm-common/postinst",
        "--package",
        str(final_deb),
        "-C",
        str(staging),
        "usr",
    ]
    return cmd


def build_deb_atomic(
    root: Path,
    staging: Path,
    version: str,
    releases_dir: Path,
    final_deb: Path,
    final_sha: Path,
    epoch: int,
) -> None:
    """Build, gate, and atomically promote the ``.deb`` and its sidecar.

    Everything up to and including the checksum is produced in a temporary
    directory on the SAME filesystem as ``releases_dir`` (so the final
    ``os.replace`` promotions are atomic). ``final_deb``/``final_sha`` are
    never written to, touched, or partially created until every mandatory
    gate -- ``dpkg-deb --info``, ``dpkg-deb --contents``,
    ``verify_runtime.py``, and Lintian -- has passed. Any failure raises
    out of the ``with`` block, and ``TemporaryDirectory`` removes every
    scratch file; a previously promoted artifact at ``final_deb`` is never
    touched by a failed run.
    """
    releases_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=str(releases_dir)) as tmp:
        tmp_path = Path(tmp)
        candidate_deb = tmp_path / final_deb.name
        changelog = tmp_path / "debian-changelog"
        changelog.write_text(debian_changelog(version, epoch), encoding="utf-8")

        print("==> Building candidate .deb with FPM (temporary location)")
        subprocess.run(
            build_fpm_command(staging, version, candidate_deb, changelog),
            cwd=root,
            check=True,
            env=deterministic_env(epoch),
        )

        print("==> Normalizing control fields (License/Vendor are not policy fields)")
        strip_control_fields(candidate_deb, ("License", "Vendor"), epoch)

        print("==> Mandatory pre-promotion gates")
        subprocess.run(["dpkg-deb", "--info", str(candidate_deb)], cwd=root, check=True)
        subprocess.run(
            ["dpkg-deb", "--contents", str(candidate_deb)], cwd=root, check=True
        )
        subprocess.run(
            [sys.executable, "scripts/verify_runtime.py", str(candidate_deb)],
            cwd=root,
            check=True,
        )
        run_lintian_gate(candidate_deb, root)

        print("==> All gates passed: generating checksum and promoting atomically")
        candidate_sha = tmp_path / f"{final_deb.name}.sha256"
        candidate_sha.write_text(sha256_sidecar_text(candidate_deb), encoding="utf-8")

        # Same filesystem as final_deb/final_sha (both created with
        # dir=str(releases_dir)), so these renames are atomic: there is no
        # window where a partial or unverified file is visible at the
        # final path.
        os.replace(candidate_deb, final_deb)
        os.replace(candidate_sha, final_sha)


def main(argv: list[str] | None = None) -> int:
    """Build the Debian package and verify it; return the exit code."""
    parser = argparse.ArgumentParser(
        prog="build_and_package_deb.py",
        description="Build and package ECLI into a Debian/Ubuntu .deb.",
    )
    parser.parse_args(argv)

    root = Path(__file__).resolve().parent.parent
    version = read_version(root)
    epoch = release_epoch()

    print("==> Checking production runtime imports")
    subprocess.run(
        [python_bin(), "scripts/check_runtime_imports.py"], cwd=root, check=True
    )

    if not (
        require_tool("pyinstaller")
        and require_tool("fpm")
        and require_tool("dpkg-deb")
        and require_tool("lintian")
    ):
        return EXIT_ERROR

    arch = filename_arch()
    releases_dir = root / "releases" / version
    final_deb = releases_dir / f"{PACKAGE_NAME}_{version}_linux_{arch}.deb"
    final_sha = releases_dir / f"{final_deb.name}.sha256"
    staging = root / "build" / "deb_staging"

    print(f"==> Version: {version}  SOURCE_DATE_EPOCH: {epoch}")
    shutil.rmtree(root / "build", ignore_errors=True)
    shutil.rmtree(root / "dist", ignore_errors=True)

    print("==> Building executable with PyInstaller")
    run_pyinstaller(root, epoch)
    executable = find_executable(root)
    if executable is None:
        print("PyInstaller output not found", file=sys.stderr)
        return EXIT_ERROR

    print("==> Preparing staging (FHS)")
    stage_payload(root, staging, executable, version, epoch)
    releases_dir.mkdir(parents=True, exist_ok=True)
    (releases_dir / ".linux.env").write_text(
        f"LINUX_ARCH := {arch}\n", encoding="utf-8"
    )

    try:
        build_deb_atomic(
            root, staging, version, releases_dir, final_deb, final_sha, epoch
        )
    except (subprocess.CalledProcessError, GateError) as exc:
        print(f"ERROR: pre-promotion gate failed: {exc}", file=sys.stderr)
        print(
            f"No new artifact was promoted; {final_deb} is unchanged.",
            file=sys.stderr,
        )
        return EXIT_ERROR

    print(f"DONE: {final_deb}")
    record_f4_evidence_non_gating(root, final_deb)
    return EXIT_OK


def record_f4_evidence_non_gating(root: Path, final_deb: Path) -> None:
    """Record legacy F4 linter provisioning compatibility evidence.

    LEGACY, non-gating compatibility evidence only -- callers must invoke
    this strictly AFTER ``final_deb`` and its checksum sidecar have
    already been atomically promoted. It records facts about the BUILD
    HOST's linter environment for the repository-wide canonical-21
    -artifact release contract (docs/release/artifact-contract.md); it is
    NOT proof that the ``.deb`` installs or bundles the F4 linter
    payload -- it never does, that is the sole responsibility of the
    standalone stage-1 installer (``scripts/install_ecli_linters.py``).

    This function never raises and never returns a value a caller could
    branch on: neither a non-zero return code nor any exception from the
    underlying hook may ever change the build's exit code or touch the
    already-promoted artifact. Every non-success outcome is caught here
    and reported as a visible, non-fatal warning only.
    """
    print("==> Recording F4 linter provisioning evidence (legacy, non-gating)")
    try:
        f4_rc = run_or_record_f4_linter_provisioning_for_artifacts(
            root,
            artifact_ids_from_env(("deb",), root=root),
        )
    except Exception as exc:  # noqa: BLE001 - must never affect the build outcome
        print(
            "WARNING: F4 linter provisioning evidence recording raised "
            f"{exc!r}; the already-promoted .deb at {final_deb} is "
            "unaffected. See docs/release/artifact-contract.md.",
            file=sys.stderr,
        )
        return
    if f4_rc != EXIT_OK:
        print(
            "WARNING: F4 linter provisioning evidence recording failed "
            f"(exit {f4_rc}); the already-promoted .deb at {final_deb} is "
            "unaffected. See docs/release/artifact-contract.md.",
            file=sys.stderr,
        )


if __name__ == "__main__":
    raise SystemExit(main())
