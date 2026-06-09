#!/usr/bin/env python
"""
threadcheck demo — showcase static scan + dynamic run in one place.

Usage:
    python demo/run_demo.py

This runs ``threadcheck scan`` and ``threadcheck run`` on
``demo/race_example.py`` and prints the results.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "demo" / "race_example.py"
BANNER = "=" * 58


def run(cmd: list[str], label: str):
    print(f"\n{BANNER}")
    print(f"  {label}")
    print(f"{BANNER}\n")
    result = subprocess.run(
        [sys.executable, "-m", "threadcheck", *cmd, str(SCRIPT)],
        capture_output=True, text=True, cwd=ROOT,
    )
    out = (result.stdout + result.stderr).strip()
    print(out if out else "(no output)")
    if result.returncode != 0:
        print(f"  (exit code {result.returncode})")


def main():
    run(["scan"], "threadcheck scan — 静态分析竞态条件")
    run(["run"], "threadcheck run   — 动态检测竞态条件")


if __name__ == "__main__":
    main()
