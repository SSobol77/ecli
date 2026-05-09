# -*- mode: python ; coding: utf-8 -*-
"""Compatibility wrapper for the canonical PyInstaller spec."""

from pathlib import Path


spec = Path(__file__).resolve().parent / "packaging" / "pyinstaller" / "ecli.spec"
exec(compile(spec.read_text(encoding="utf-8"), str(spec), "exec"))
