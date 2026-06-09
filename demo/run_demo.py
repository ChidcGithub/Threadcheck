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
    print(f"  {'-' * len(label)}\n", flush=True)
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


def run_raw(cmd: list[str], label: str):
    print(f"\n  {label}", flush=True)
    print(f"  {'-' * len(label)}\n", flush=True)
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    result = subprocess.run(
        [sys.executable, "-m", "threadcheck", *cmd],
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

    run(["scan"], "1) Static analysis scan (default)")
    run(["scan", "-q"], "2) Static analysis (quiet mode)")
    run(["scan", "-v"], "3) Static analysis (verbose with source snippets)")
    run(["scan", "--json"], "4) Static analysis (JSON output)")
    run(["scan", "--sarif"], "5) Static analysis (SARIF output)")
    run(["run"], "6) Dynamic detection (text output)")
    run(["run", "--json"], "7) Dynamic detection (JSON output)")

    report_path = ROOT / "demo" / "report.html"
    subprocess.run(
        [sys.executable, "-m", "threadcheck", "scan", "-o", str(report_path), str(SCRIPT)],
        capture_output=True, env={**os.environ, "PYTHONIOENCODING": "utf-8"}, cwd=ROOT,
    )
    print(f"\n  8) HTML report saved to: {report_path}", flush=True)
    print(f"     Open in browser to view the interactive report.\n", flush=True)

    run_raw(["compat"], "9) Free-threading compatibility check")

    print(BANNER, flush=True)
    print("  Try it yourself:", flush=True)
    print(f"    python -m threadcheck scan    {SCRIPT}", flush=True)
    print(f"    python -m threadcheck run     {SCRIPT}", flush=True)
    print(f"    python -m threadcheck compat", flush=True)
    print(BANNER, flush=True)


if __name__ == "__main__":
    main()
