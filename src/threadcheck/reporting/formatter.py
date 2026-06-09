from __future__ import annotations

import json
import os
import sys
from collections import Counter, defaultdict
from typing import Any

from ..static.models import RaceWarning, Severity, Confidence


def _use_color() -> bool:
    if not sys.stdout.isatty():
        return False
    term = os.environ.get("TERM", "")
    if "dumb" in term.lower():
        return False
    return True


_COLOR = _use_color()

_STYLES: dict[str, str] = {}
if _COLOR:
    _STYLES["reset"] = "\033[0m"
    _STYLES["bold"] = "\033[1m"
    _STYLES["red"] = "\033[91m"
    _STYLES["green"] = "\033[92m"
    _STYLES["yellow"] = "\033[93m"
    _STYLES["blue"] = "\033[94m"
    _STYLES["magenta"] = "\033[95m"
    _STYLES["cyan"] = "\033[96m"
    _STYLES["dim"] = "\033[2m"


def _s(name: str, text: str = "") -> str:
    s = _STYLES.get(name, "")
    r = _STYLES.get("reset", "")
    return f"{s}{text}{r}"


_SEVERITY_COLOR = {
    Severity.ERROR: "red",
    Severity.WARNING: "yellow",
    Severity.INFO: "cyan",
}

_CONFIDENCE_TAG = {
    Confidence.HIGH: "HIGH",
    Confidence.MEDIUM: "MED",
    Confidence.LOW: "LOW",
}

_SEVERITY_TAG = {
    Severity.ERROR: "ERROR",
    Severity.WARNING: "WARNING",
    Severity.INFO: "INFO",
}

_SEVERITY_ICON = {
    Severity.ERROR: ("\u2716", "X"),
    Severity.WARNING: ("\u26a0", "!"),
    Severity.INFO: ("\u2139", "i"),
}


def format_report(warnings: list[RaceWarning], verbose: bool = False) -> str:
    can_emoji = _use_color() and _can_print_emoji()
    if not warnings:
        return _s("green", "No data-race issues detected") if _COLOR else "No data-race issues detected"

    by_file: dict[str, list[RaceWarning]] = defaultdict(list)
    for w in warnings:
        by_file[str(w.file)].append(w)

    lines: list[str] = []
    file_count = len(by_file)

    for file_idx, (filepath, file_warnings) in enumerate(sorted(by_file.items())):
        short_path = _shorten_path(filepath)
        lines.append("")
        lines.append(f"  {_s('bold', _s('blue', f'[{file_idx+1}/{file_count}] {short_path}'))}")
        lines.append(f"  {_s('dim', '\u2500' * min(60, len(short_path) + 4))}")

        for w in file_warnings:
            sc = _SEVERITY_COLOR.get(w.severity, "")
            icon, fallback = _SEVERITY_ICON.get(w.severity, ("", ""))
            icon_str = _s(sc, icon) if can_emoji else _s(sc, f"[{fallback}]")
            lines.append(
                f"    {icon_str} "
                f"{_s('bold', _CONFIDENCE_TAG.get(w.confidence, ''))} "
                f"[{w.category.value}] line {w.line}:{w.col}"
            )
            lines.append(f"          {w.message}")
            if w.suggestion:
                lines.append(f"          {_s('dim', 'suggestion:')} {w.suggestion}")

            if verbose:
                snippet = _get_source_snippet(filepath, w.line)
                if snippet:
                    for sline in snippet:
                        lines.append(f"          {sline}")

        fe = sum(1 for w in file_warnings if w.severity == Severity.ERROR)
        fw = sum(1 for w in file_warnings if w.severity == Severity.WARNING)
        fi = sum(1 for w in file_warnings if w.severity == Severity.INFO)
        parts = []
        if fe:
            parts.append(f"{fe} error(s)")
        if fw:
            parts.append(f"{fw} warning(s)")
        if fi:
            parts.append(f"{fi} info")
        lines.append(f"  {_s('dim', f'  {len(file_warnings)} issue(s) in this file ({", ".join(parts)})')}")

    lines.append("")
    lines.append(f"{_s('dim', '\u2500' * 40)}")
    total = len(warnings)
    errors = sum(1 for w in warnings if w.severity == Severity.ERROR)
    warns = sum(1 for w in warnings if w.severity == Severity.WARNING)
    infos = sum(1 for w in warnings if w.severity == Severity.INFO)
    lines.append(f"Total: {total} issue(s) in {file_count} file(s) ({errors} error(s), {warns} warning(s), {infos} info(s))")
    return "\n".join(lines)


def _shorten_path(filepath: str) -> str:
    parts = filepath.replace("\\", "/").split("/")
    if len(parts) <= 3:
        return filepath
    return "/".join(parts[:1] + ["..."] + parts[-2:])


def _get_source_snippet(filepath: str, line: int, context: int = 2) -> list[str]:
    try:
        with open(filepath, encoding="utf-8") as f:
            source_lines = f.readlines()
    except Exception:
        return []

    start = max(0, line - context - 1)
    end = min(len(source_lines), line + context)
    result: list[str] = []
    for i in range(start, end):
        prefix = ">" if i == line - 1 else " "
        result.append(f"{prefix} {_s('dim', str(i+1).rjust(4))} | {source_lines[i].rstrip()}" if _COLOR else f"{prefix} {str(i+1).rjust(4)} | {source_lines[i].rstrip()}")
    return result


def _can_print_emoji() -> bool:
    try:
        "\u2716".encode(sys.stdout.encoding)
        return True
    except (UnicodeEncodeError, UnicodeDecodeError, AttributeError):
        return False


def format_dynamic_races(
    races: list[tuple[str, Any, Any]],
    access_log: dict[str, list] | None = None,
) -> str:
    if not races:
        return _s("green", "No data races detected") if _COLOR else "No data races detected"

    overlap = Counter()
    if access_log:
        for var_name, records in access_log.items():
            for i, r1 in enumerate(records):
                for r2 in records[i + 1 :]:
                    if r1.thread_id != r2.thread_id:
                        if r1.operation == "write" or r2.operation == "write":
                            if r1.clock.conflicts_with(r2.clock):
                                key = _race_key(r1, r2)
                                overlap[key] += 1

    lines: list[str] = [
        _s("red", _s("bold", "Data races detected:")) if _COLOR else "Data races detected:",
        "",
    ]

    for var_name, r1, r2 in races:
        f1, l1 = r1.location
        f2, l2 = r2.location
        key = _race_key(r1, r2)
        count = overlap.get(key, 0)
        marker = _s("red", " [!]") if _COLOR else " [!]"

        lines.append(f"{marker} {_s('bold', f'`{var_name}`')}")
        lines.append(
            f"  {'├─' if count > 0 else '└─'} "
            f"Thread-{r1.thread_id} ({_s('magenta', r1.operation)}) "
            f"at {f1}:{l1}"
        )
        lines.append(
            f"  {'├─' if count > 1 else '└─'} "
            f"Thread-{r2.thread_id} ({_s('magenta', r2.operation)}) "
            f"at {f2}:{l2}"
        )
        lines.append(
            f"  └─ No happens-before relationship between accesses"
        )
        if count > 1:
            lines.append(f"     ({count} overlapping accesses)")
        lines.append("")

    total_unique = len(races)
    total_overlap = sum(overlap.values())
    summary = f"Summary: {total_unique} unique race pair(s), {total_overlap} total overlapping access(es)"
    lines.append(_s("dim", summary) if _COLOR else summary)
    return "\n".join(lines)


def _race_key(r1, r2) -> tuple:
    tid1, tid2 = sorted([r1.thread_id, r2.thread_id])
    loc1, loc2 = sorted([r1.location, r2.location])
    return (r1.var_name, tid1, tid2, loc1, loc2)


def format_warnings_json(warnings: list[RaceWarning]) -> str:
    return json.dumps(
        [w.to_dict() for w in warnings],
        indent=2,
        ensure_ascii=False,
    )


def format_dynamic_json(
    races: list[tuple[str, Any, Any]],
) -> str:
    entries = []
    for var_name, r1, r2 in races:
        entries.append({
            "var_name": var_name,
            "thread_1": {
                "id": r1.thread_id,
                "operation": r1.operation,
                "location": f"{r1.location[0]}:{r1.location[1]}",
            },
            "thread_2": {
                "id": r2.thread_id,
                "operation": r2.operation,
                "location": f"{r2.location[0]}:{r2.location[1]}",
            },
        })
    return json.dumps(entries, indent=2, ensure_ascii=False)
