#!/usr/bin/env python3
"""Development entry point. Delegates to packaged ecli.__main__."""

from ecli.__main__ import main
import sys


if __name__ == "__main__":
    sys.exit(main())
