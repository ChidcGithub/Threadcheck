import json
from pathlib import Path

from threadcheck.reporting.sarif import format_sarif
from threadcheck.static.models import (
    RaceWarning,
    Severity,
    WarningCategory,
    Confidence,
)


def test_empty_list_produces_valid_sarif():
    raw = format_sarif([])
    doc = json.loads(raw)
    assert doc["$schema"].startswith("https://")
    assert doc["version"] == "2.1.0"
    assert doc["runs"][0]["results"] == []


def test_single_warning():
    w = RaceWarning(
        file=Path("/fake/demo.py"),
        line=11,
        col=8,
        severity=Severity.WARNING,
        category=WarningCategory.UNSAFE_GLOBAL,
        message="Global variable `counter` modified without lock",
        suggestion="Use `threading.Lock()` to protect `counter`",
        confidence=Confidence.HIGH,
    )
    raw = format_sarif([w])
    doc = json.loads(raw)

    results = doc["runs"][0]["results"]
    assert len(results) == 1
    r = results[0]
    assert r["ruleId"] == "unsafe_global"
    assert r["level"] == "warning"
    assert r["message"]["text"] == "Global variable `counter` modified without lock"

    loc = r["locations"][0]["physicalLocation"]
    assert loc["artifactLocation"]["uri"].endswith("fake/demo.py")
    assert loc["region"]["startLine"] == 11
    assert loc["region"]["startColumn"] == 8


def test_level_mapping():
    cases = [
        (Severity.ERROR, "error"),
        (Severity.WARNING, "warning"),
        (Severity.INFO, "note"),
    ]
    for sev, expected_level in cases:
        w = RaceWarning(
            file=Path("/f.py"),
            line=1,
            col=1,
            severity=sev,
            category=WarningCategory.THREAD_USAGE,
            message="test",
        )
        doc = json.loads(format_sarif([w]))
        assert doc["runs"][0]["results"][0]["level"] == expected_level


def test_rules_are_deduplicated():
    warnings = [
        RaceWarning(
            file=Path("/a.py"), line=1, col=1,
            severity=Severity.WARNING, category=WarningCategory.UNSAFE_GLOBAL,
            message="g1",
        ),
        RaceWarning(
            file=Path("/b.py"), line=2, col=1,
            severity=Severity.WARNING, category=WarningCategory.UNSAFE_GLOBAL,
            message="g2",
        ),
        RaceWarning(
            file=Path("/c.py"), line=3, col=1,
            severity=Severity.WARNING, category=WarningCategory.CLASS_ATTRIBUTE,
            message="c1",
        ),
    ]
    doc = json.loads(format_sarif(warnings))
    rules = doc["runs"][0]["tool"]["driver"]["rules"]
    rule_ids = [r["id"] for r in rules]
    assert rule_ids == ["unsafe_global", "class_attribute"]
    assert len(rules) == 2


def test_tool_info():
    doc = json.loads(format_sarif([]))
    driver = doc["runs"][0]["tool"]["driver"]
    assert driver["name"] == "threadcheck"
    assert "version" in driver
