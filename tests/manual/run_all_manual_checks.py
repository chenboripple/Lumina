#!/usr/bin/env python3
"""
Run all manual validation scripts in a deterministic order.

These checks are intentionally script-style and are not part of pytest auto collection.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


SCRIPTS = [
    "verify_imports.py",
    "validate_flask_json.py",
    "validate_file_edit_tool.py",
    "validate_optimizations.py",
]


def run_script(script_path: Path) -> int:
    print("=" * 72)
    print(f"Running: {script_path.name}")
    print("=" * 72)

    result = subprocess.run([sys.executable, str(script_path)], check=False)
    if result.returncode == 0:
        print(f"PASS: {script_path.name}\n")
    else:
        print(f"FAIL: {script_path.name} (exit={result.returncode})\n")
    return result.returncode


def main() -> int:
    manual_dir = Path(__file__).resolve().parent
    exit_codes = []

    for script_name in SCRIPTS:
        script_path = manual_dir / script_name
        if not script_path.exists():
            print(f"SKIP: missing {script_name}")
            continue
        exit_codes.append(run_script(script_path))

    failures = sum(1 for code in exit_codes if code != 0)
    print("=" * 72)
    print(f"Manual checks complete. total={len(exit_codes)} failures={failures}")
    print("=" * 72)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
