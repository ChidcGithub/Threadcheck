from __future__ import annotations

import argparse
import json as _json
import re
import sys
from pathlib import Path

from ._version import __version__
from .config import ThreadCheckConfig
from .static.analyzer import analyze_path
from .reporting.formatter import format_report, format_warnings_json
from .reporting.sarif import format_sarif
from .reporting.html import format_html
from .dynamic.__main__ import run_script
from .compat import check_compat
from .compat.models import CompatStatus


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
    scan.add_argument("-q", "--quiet", action="store_true", help="Suppress banner and per-file output, show only summary")
    scan.add_argument("-v", "--verbose", action="store_true", help="Show source snippets for each issue")

    run = sub.add_parser("run", help="Dynamic race detection")
    run.add_argument("script", help="Python script to execute")
    run_fmt = run.add_mutually_exclusive_group()
    run_fmt.add_argument("--json", action="store_true", help="Output in JSON format")
    run.add_argument("-o", "--output", help="Write output to file (default: stdout)")
    run.add_argument("-q", "--quiet", action="store_true", help="Suppress banner")
    run.add_argument("-v", "--verbose", action="store_true", help="Show verbose output")

    compat = sub.add_parser("compat", help="Check free-threading compatibility")
    compat.add_argument("path", nargs="?", default=".", help="Project path")
    compat.add_argument("--json", action="store_true", help="Output in JSON format")

    args = parser.parse_args()

    if args.command == "scan":
        _do_scan(args)
    elif args.command == "run":
        _do_run(args)
    elif args.command == "compat":
        _do_compat(args)


def _detect_format(output_path: str | None) -> str:
    if output_path:
        ext = Path(output_path).suffix.lower()
        if ext == ".json":
            return "json"
        if ext == ".sarif":
            return "sarif"
        if ext == ".html":
            return "html"
    return "text"


def _do_scan(args):
    path = Path(args.path).resolve()
    if not path.exists():
        print(f"Path does not exist: {path}", file=sys.stderr)
        sys.exit(1)

    root = path if path.is_dir() else path.parent
    config = ThreadCheckConfig.load(root)

    if not args.quiet:
        print(f"threadcheck scan -- analysing {path}")
        print()

    warnings = analyze_path(str(path), config=config)

    fmt = _detect_format(args.output)
    if args.json:
        fmt = "json"
    elif args.sarif:
        fmt = "sarif"

    if fmt == "html":
        output = format_html(warnings, title=f"threadcheck Report - {path}")
        _write_output(args.output, output)
    elif fmt == "json":
        output = format_warnings_json(warnings)
        _write_output(args.output, output)
    elif fmt == "sarif":
        output = format_sarif(warnings)
        _write_output(args.output, output)
    else:
        if args.quiet:
            text = _format_summary_only(warnings)
        else:
            text = format_report(warnings, verbose=args.verbose)
        _write_output(args.output, text)


def _format_summary_only(warnings: list) -> str:
    total = len(warnings)
    errors = sum(1 for w in warnings if w.severity.value == "error")
    warns = sum(1 for w in warnings if w.severity.value == "warning")
    infos = sum(1 for w in warnings if w.severity.value == "info")
    if total == 0:
        return "No data-race issues detected."
    return f"{total} issue(s): {errors} error(s), {warns} warning(s), {infos} info"


def _do_run(args):
    fmt = "json" if args.json else _detect_format(args.output)
    has_race = run_script(args.script, output_format=fmt)
    if has_race:
        sys.exit(1)


def _do_compat(args):
    path = Path(args.path).resolve()
    names: list[str] | None = None
    toml = path / "pyproject.toml"
    req = path / "requirements.txt"
    if path.is_dir() and toml.is_file():
        names = _read_deps_from_pyproject(toml)
    elif path.is_file() and path.suffix == ".txt":
        names = _read_deps_from_requirements(path)
    elif path.is_file() and path.name == "pyproject.toml":
        names = _read_deps_from_pyproject(path)

    results = check_compat(names)

    if args.json:
        obj = [r.to_dict() for r in results]
        print(_json.dumps(obj, indent=2, ensure_ascii=False))
        return

    print(f"threadcheck compat - Free-threading compatibility check")
    print(f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    print()

    can_emoji = _can_print_emoji()
    for r in results:
        if r.status.value == "compatible":
            icon = _icon("\u2705", "[OK]", can_emoji)
        elif r.status.value == "needs_verification":
            icon = _icon("\u26a0\ufe0f", "[??]", can_emoji)
        else:
            icon = _icon("\u274c", "[--]", can_emoji)
        print(f"  {icon}  {r.name:<20} {r.reason}")

    print()
    total = len(results)
    compat_count = sum(1 for r in results if r.status == CompatStatus.COMPATIBLE)
    needs_v = sum(1 for r in results if r.status == CompatStatus.NEEDS_VERIFICATION)
    not_inst = sum(1 for r in results if r.status == CompatStatus.NOT_INSTALLED)
    print(f"Total: {total} package(s) - {compat_count} compatible, {needs_v} need verification, {not_inst} not installed")

    if needs_v > 0:
        sys.exit(1)


def _read_deps_from_pyproject(path: Path) -> list[str]:
    try:
        import tomllib
    except ImportError:
        return []

    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []

    deps: list[str] = []
    for key in ("dependencies", "optional-dependencies"):
        section = data.get("project", {}).get(key, {})
        if isinstance(section, dict):
            for group in section.values():
                deps.extend(_extract_names(group))
        elif isinstance(section, list):
            deps.extend(_extract_names(section))
    return sorted(set(deps))


def _read_deps_from_requirements(path: Path) -> list[str]:
    names: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith(("#", "-", "git+", "http")):
            continue
        name = re.split(r"[<>=!~@;]", line, maxsplit=1)[0].strip()
        if name:
            names.append(name)
    return sorted(set(names))


def _extract_names(entries: list) -> list[str]:
    import re as _re

    names: list[str] = []
    for entry in entries:
        if not isinstance(entry, str):
            continue
        name = _re.split(r"[<>=!~@;]", entry, maxsplit=1)[0].strip()
        if name:
            names.append(name)
    return names


def _can_print_emoji() -> bool:
    try:
        "\u2705".encode(sys.stdout.encoding)
        return True
    except (UnicodeEncodeError, UnicodeDecodeError, AttributeError):
        return False


def _icon(emoji: str, fallback: str, can_emoji: bool) -> str:
    return emoji if can_emoji else fallback


def _write_output(path_arg: str | None, content: str):
    if path_arg:
        Path(path_arg).write_text(content, encoding="utf-8")
    else:
        print(content)


if __name__ == "__main__":
    main()
