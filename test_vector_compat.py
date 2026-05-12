#!/usr/bin/env python3
"""Compatibility launcher for migrated vector compatibility test."""

from pathlib import Path
import runpy


if __name__ == "__main__":
    target = Path(__file__).parent / "tests" / "manual" / "test_vector_compat.py"
    runpy.run_path(str(target), run_name="__main__")
