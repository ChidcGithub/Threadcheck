import json
from pathlib import Path

from ..static.models import RaceWarning, Severity, WarningCategory, Confidence
from .._version import __version__

_SCHEMA = "https://raw.githubusercontent.com/oasis-tcs/sarif-spec/master/Schemata/sarif-schema-2.1.0.json"
_TOOL_INFO_URI = "https://github.com/ChidcGithub/Threadcheck"

_SEVERITY_TO_LEVEL = {
    Severity.ERROR: "error",
    Severity.WARNING: "warning",
    Severity.INFO: "note",
}

_CATEGORY_LABELS = {
    WarningCategory.UNSAFE_GLOBAL: ("Global variable modified without lock", "Detects modifications of `global` variables inside functions without lock protection."),
    WarningCategory.UNSAFE_NONLOCAL: ("Nonlocal variable modified without lock", "Detects modifications of `nonlocal` variables inside nested functions without lock protection."),
    WarningCategory.UNPROTECTED_ACCESS: ("Unprotected shared access", "Detects shared variable access without synchronization."),
    WarningCategory.THREAD_USAGE: ("Thread creation detected", "Reports sites where `threading.Thread` objects are created."),
    WarningCategory.SHARED_MUTABLE: ("Module-level mutable object modified", "Detects modification of module-level mutable objects (lists, dicts, sets) inside functions."),
    WarningCategory.CLASS_ATTRIBUTE: ("Class attribute modified without lock", "Detects unsafe modification of instance attributes (`self.x`) without lock protection."),
}


def format_sarif(
    warnings: list[RaceWarning],
    tool_version: str = __version__,
) -> str:
    rules = _build_rules(warnings)
    results = [_warning_to_result(w) for w in warnings]

    doc = {
        "$schema": _SCHEMA,
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "threadcheck",
                        "version": tool_version,
                        "informationUri": _TOOL_INFO_URI,
                        "rules": rules,
                    }
                },
                "results": results,
            }
        ],
    }

    return json.dumps(doc, indent=2, ensure_ascii=False)


def _build_rules(warnings: list[RaceWarning]) -> list[dict]:
    seen: set[str] = set()
    rules: list[dict] = []
    for w in warnings:
        rid = w.category.value
        if rid in seen:
            continue
        seen.add(rid)
        label, desc = _CATEGORY_LABELS.get(
            w.category, (rid.replace("_", " ").title(), "")
        )
        level = _SEVERITY_TO_LEVEL.get(w.severity, "warning")
        rules.append(
            {
                "id": rid,
                "shortDescription": {"text": label},
                "fullDescription": {"text": desc},
                "defaultConfiguration": {"level": level},
                "properties": {
                    "category": "Concurrency",
                    "confidence": w.confidence.value,
                },
            }
        )
    return rules


def _warning_to_result(w: RaceWarning) -> dict:
    return {
        "ruleId": w.category.value,
        "level": _SEVERITY_TO_LEVEL.get(w.severity, "warning"),
        "message": {"text": w.message},
        "locations": [
            {
                "physicalLocation": {
                    "artifactLocation": {
                        "uri": w.file.resolve().as_uri(),
                    },
                    "region": {
                        "startLine": w.line,
                        "startColumn": w.col,
                    },
                }
            }
        ],
        "properties": {},
    }
