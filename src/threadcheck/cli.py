import argparse
import sys
from pathlib import Path

from ._version import __version__
from .static.analyzer import analyze_path
from .reporting.formatter import format_report, format_warnings_json
from .reporting.sarif import format_sarif
from .dynamic.__main__ import run_script


def main():
    parser = argparse.ArgumentParser(
        prog="threadcheck",
        description="Data Race Detector for Python",
    )

    parser.add_argument(
        "--version", action="version", version=f"threadcheck {__version__}"
    )

    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", help="Static analysis for data races")
    scan.add_argument("path", help="File or directory to scan")
    fmt = scan.add_mutually_exclusive_group()
    fmt.add_argument("--json", action="store_true", help="Output in JSON format")
    fmt.add_argument("--sarif", action="store_true", help="Output in SARIF v2.1.0 format")
    scan.add_argument("-o", "--output", help="Write output to file (default: stdout)")

    run = sub.add_parser("run", help="Dynamic race detection")
    run.add_argument("script", help="Python script to execute")
    run_fmt = run.add_mutually_exclusive_group()
    run_fmt.add_argument("--json", action="store_true", help="Output in JSON format")
    run.add_argument("-o", "--output", help="Write output to file (default: stdout)")

    compat = sub.add_parser("check-compat", help="Check free-threading compatibility (Phase 7)")
    compat.add_argument("path", nargs="?", default=".", help="Project path")

    args = parser.parse_args()

    if args.command == "scan":
        _do_scan(args)
    elif args.command == "run":
        _do_run(args)
    elif args.command == "check-compat":
        print("Not implemented: free-threading compatibility check (Phase 7)", file=sys.stderr)
        sys.exit(1)


def _detect_format(output_path: str | None) -> str:
    if output_path:
        ext = Path(output_path).suffix.lower()
        if ext == ".json":
            return "json"
        if ext == ".sarif":
            return "sarif"
    return "text"


def _do_scan(args):
    path = Path(args.path).resolve()
    if not path.exists():
        print(f"Path does not exist: {path}", file=sys.stderr)
        sys.exit(1)

    print(f"threadcheck scan -- analysing {path}")
    print()

    warnings = analyze_path(str(path))

    fmt = _detect_format(args.output)
    if args.json:
        fmt = "json"
    elif args.sarif:
        fmt = "sarif"

    if fmt == "json":
        output = format_warnings_json(warnings)
        _write_output(args.output, output)
    elif fmt == "sarif":
        output = format_sarif(warnings)
        _write_output(args.output, output)
    else:
        text = format_report(warnings)
        _write_output(args.output, text)

    total = len(warnings)
    errors = sum(1 for w in warnings if w.severity.value == "error")
    warns = sum(1 for w in warnings if w.severity.value == "warning")
    infos = sum(1 for w in warnings if w.severity.value == "info")
    print()
    print(f"Total: {total} issue(s) ({errors} error(s), {warns} warning(s), {infos} info)")


def _do_run(args):
    fmt = "json" if args.json else _detect_format(args.output)
    run_script(args.script, output_format=fmt)


def _write_output(path_arg: str | None, content: str):
    if path_arg:
        Path(path_arg).write_text(content, encoding="utf-8")
    else:
        print(content)


if __name__ == "__main__":
    main()
