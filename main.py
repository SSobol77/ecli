#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
#
# Project: Ecli
# File: main.py
# Website: https://www.ecli.io
# Repository: https://github.com/SSobol77/ecli
# PyPI: https://pypi.org/project/ecli-editor/0.0.1/
#
# Copyright (c) 2026 Siergej Sobolewski
#
# Licensed under the Apache License, Version 2.0.
# See the LICENSE file in the project root for full license text.

"""Development entry point. Delegates to packaged ecli.__main__."""

import sys

from ecli.__main__ import main


if __name__ == "__main__":
    sys.exit(main())
