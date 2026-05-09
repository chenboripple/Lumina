#!/usr/bin/env python3
"""Compatibility launcher for migrated quick start script."""

from pathlib import Path
import runpy


if __name__ == "__main__":
    target = Path(__file__).parent / "scripts" / "dev" / "quick_start.py"
    runpy.run_path(str(target), run_name="__main__")
