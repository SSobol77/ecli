#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
#
# Project: Ecli
# File: scripts/build_docker.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the GNU General Public License version 2 only.
# See the LICENSE file in the project root for full license text.

"""Build the ECLI ``.deb`` inside a Debian container using project scripts.

Canonical Python replacement for ``scripts/build-docker.sh``. It is the legacy
single-image DEB helper (superseded by the canonical Docker DEB/RPM helpers and
``make package-docker``); it is preserved as documented drift and still
references ``docker/build-linux.Dockerfile``. The migration keeps its behavior
identical while moving the orchestration to Python.

This script orchestrates a local Docker build only. It never publishes, uploads,
signs, tags, pushes, or triggers any workflow.

Exit codes:

* ``0`` build completed
* ``1`` missing prerequisite, bad invocation, or container execution failed
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


EXIT_OK = 0
EXIT_ERROR = 1

IMAGE_NAME = "ecli-builder-bullseye"
DOCKERFILE = "docker/build-linux.Dockerfile"
CONTAINER_NAME = "ecli-build-deb"


class _ExitOneParser(argparse.ArgumentParser):
    """ArgumentParser that maps usage errors to the legacy exit-1 contract."""

    def error(self, message: str) -> None:  # type: ignore[override]
        self.print_usage(sys.stderr)
        print(f"{self.prog}: error: {message}", file=sys.stderr)
        raise SystemExit(EXIT_ERROR)


def _container_exists(name: str, all_containers: bool) -> bool:
    flag = "-aq" if all_containers else "-q"
    result = subprocess.run(
        ["docker", "ps", flag, "-f", f"name={name}"],
        capture_output=True,
        text=True,
        check=False,
    )
    return bool(result.stdout.strip())


def _cleanup_container(name: str) -> None:
    if _container_exists(name, all_containers=True):
        subprocess.run(["docker", "stop", name], capture_output=True, check=False)
        subprocess.run(["docker", "rm", name], capture_output=True, check=False)


def check_prerequisites(root: Path) -> bool:
    if shutil.which("docker") is None:
        print("Docker is not installed or not in PATH", file=sys.stderr)
        return False
    if (
        subprocess.run(["docker", "info"], capture_output=True, check=False).returncode
        != 0
    ):
        print("Docker daemon is not running or not accessible", file=sys.stderr)
        return False
    if not (root / DOCKERFILE).is_file():
        print(f"Dockerfile not found: {DOCKERFILE}", file=sys.stderr)
        return False
    return True


def build_image_command(no_cache: bool, verbose: bool) -> list[str]:
    cmd = ["docker", "build"]
    if no_cache:
        cmd.append("--no-cache")
    cmd += ["-t", IMAGE_NAME, "-f", DOCKERFILE, "."]
    if not verbose:
        cmd.append("--quiet")
    return cmd


def docker_run_command(root: Path) -> list[str]:
    return [
        "docker",
        "run",
        "--rm",
        "-u",
        f"{os.getuid()}:{os.getgid()}",
        "-v",
        f"{root}:/app:rw",
        "-v",
        f"{root / 'releases'}:/app/releases:rw",
        "--name",
        CONTAINER_NAME,
        IMAGE_NAME,
    ]


def main(argv: list[str] | None = None) -> int:
    """Build the .deb in a Debian container; return the exit code."""
    parser = _ExitOneParser(
        prog="build_docker.py",
        description="Build ECLI .deb package in a Docker container.",
    )
    parser.add_argument(
        "-f", "--force", action="store_true", help="force rebuild image"
    )
    parser.add_argument(
        "-c", "--clean", action="store_true", help="remove existing releases"
    )
    parser.add_argument(
        "--no-cache", action="store_true", help="build image without cache"
    )
    parser.add_argument("--verbose", action="store_true", help="verbose output")
    args = parser.parse_args(argv)

    root = Path(__file__).resolve().parent.parent

    if not check_prerequisites(root):
        return EXIT_ERROR

    if args.clean:
        print("Cleaning existing releases directory")
        shutil.rmtree(root / "releases", ignore_errors=True)
    (root / "releases").mkdir(parents=True, exist_ok=True)

    image_present = (
        subprocess.run(
            ["docker", "image", "inspect", IMAGE_NAME], capture_output=True, check=False
        ).returncode
        == 0
    )
    if args.force or not image_present:
        print(f"Building Docker image: {IMAGE_NAME}")
        subprocess.run(
            build_image_command(args.no_cache, args.verbose), cwd=root, check=True
        )
    else:
        print(f"Using existing Docker image: {IMAGE_NAME}")

    if _container_exists(CONTAINER_NAME, all_containers=True):
        subprocess.run(
            ["docker", "rm", "-f", CONTAINER_NAME], capture_output=True, check=False
        )

    print("Running packaging inside container...")
    if subprocess.run(docker_run_command(root), cwd=root, check=False).returncode != 0:
        print("Container execution failed", file=sys.stderr)
        _cleanup_container(CONTAINER_NAME)
        return EXIT_ERROR

    print("Build completed successfully!")
    debs = sorted((root / "releases").rglob("*.deb"))
    if debs:
        print("Generated files:")
        for deb in debs:
            print(f"  {deb}")
    else:
        print("No .deb files found in releases directory")
    return EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
