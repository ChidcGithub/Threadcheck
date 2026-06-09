#!/usr/bin/env python
"""
threadcheck demo — show static scan + dynamic run.

Usage:
    python demo/run_demo.py
"""

import os
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
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    result = subprocess.run(
        [sys.executable, "-m", "threadcheck", *cmd, str(SCRIPT)],
        capture_output=True,
        encoding="utf-8",
        env=env,
        cwd=ROOT,
    )
    out = (result.stdout or "") + (result.stderr or "")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(out.strip() or "(no output)")
    if result.returncode != 0:
        print(f"  (exit code {result.returncode})")


def main():
    run(["scan"], "threadcheck scan - static analysis")
    run(["run"], "threadcheck run   - dynamic detection")


if __name__ == "__main__":
    main()
