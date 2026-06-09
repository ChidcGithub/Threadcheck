#!/usr/bin/env python
"""
threadcheck demo — show static scan + dynamic detection + all output formats.

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

sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")


def run(cmd: list[str], label: str):
    print(f"\n  {label}", flush=True)
    print(f"  {'─' * len(label)}\n", flush=True)
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    result = subprocess.run(
        [sys.executable, "-m", "threadcheck", *cmd, str(SCRIPT)],
        capture_output=True,
        env=env,
        cwd=ROOT,
    )
    out = result.stdout.decode("utf-8", errors="backslashreplace")
    if result.stderr:
        out += "\n" + result.stderr.decode("utf-8", errors="backslashreplace")
    print(out.strip() or "(no output)", flush=True)
    print(flush=True)


def main():
    print(BANNER, flush=True)
    print("  threadcheck demo -- Python data race detector", flush=True)
    print(BANNER, flush=True)

    run(["scan"], "1) Static analysis scan")

    run(["run"], "2) Dynamic detection (text output)")

    run(["run", "--json"], "3) Dynamic detection (JSON output)")

    run(["scan", "--sarif"], "4) Static analysis (SARIF output)")

    print(BANNER, flush=True)
    print("  Try it yourself:", flush=True)
    print(f"    python -m threadcheck scan    {SCRIPT}", flush=True)
    print(f"    python -m threadcheck run     {SCRIPT}", flush=True)
    print(f"    python -m threadcheck run --json {SCRIPT}", flush=True)
    print(BANNER, flush=True)


if __name__ == "__main__":
    main()
