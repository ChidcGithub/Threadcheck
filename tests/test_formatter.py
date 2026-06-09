from pathlib import Path
from threadcheck.static.models import RaceWarning, Severity, WarningCategory, Confidence
from threadcheck.reporting.formatter import (
    format_report,
    format_warnings_json,
    format_dynamic_races,
    format_dynamic_json,
)
from threadcheck.dynamic.clock import VectorClock
from threadcheck.dynamic.tracker import AccessRecord


def _make_warning(severity=Severity.WARNING, confidence=Confidence.MEDIUM, line=1):
    return RaceWarning(
        file=Path("test.py"),
        line=line,
        col=1,
        severity=severity,
        category=WarningCategory.UNSAFE_GLOBAL,
        message="Global variable 'counter' modified without lock",
        suggestion="Use threading.Lock() to protect access",
        confidence=confidence,
    )


class TestFormatReport:
    def test_empty(self):
        result = format_report([])
        assert "No data-race issues detected" in result

    def test_single_warning(self):
        w = _make_warning()
        result = format_report([w])
        assert "test.py:1:1" in result
        assert "unsafe_global" in result
        assert "Global variable" in result
        assert "suggestion:" in result

    def test_multiple_warnings(self):
        ws = [_make_warning(line=i) for i in range(1, 4)]
        result = format_report(ws)
        assert "test.py:1:1" in result
        assert "test.py:2:1" in result
        assert "test.py:3:1" in result
        assert "3 issue(s)" in result

    def test_severity_colors_not_included_when_no_tty(self):
        w = _make_warning(severity=Severity.ERROR)
        result = format_report([w])
        assert "\033[" not in result


class TestFormatWarningsJson:
    def test_empty(self):
        result = format_warnings_json([])
        assert result == "[]"

    def test_single(self):
        w = _make_warning()
        result = format_warnings_json([w])
        assert "test.py" in result
        assert "unsafe_global" in result
        assert "Global variable" in result

    def test_valid_json(self):
        import json
        ws = [_make_warning(line=42)]
        result = format_warnings_json(ws)
        parsed = json.loads(result)
        assert len(parsed) == 1
        assert parsed[0]["line"] == 42


class TestFormatDynamicRaces:
    def _make_record(self, tid: int, operation: str, file: str, line: int) -> AccessRecord:
        clock = VectorClock()
        clock.tick(tid)
        return AccessRecord(
            var_name="counter",
            operation=operation,
            thread_id=tid,
            clock=clock.copy(),
            location=(file, line),
        )

    def test_empty(self):
        result = format_dynamic_races([])
        assert "No data races detected" in result

    def test_single_race(self):
        r1 = self._make_record(1, "write", "a.py", 10)
        r2 = self._make_record(2, "write", "a.py", 20)
        r1.clock.tick(1)
        races = [("counter", r1, r2)]
        result = format_dynamic_races(races)
        assert "Data races detected" in result
        assert "`counter`" in result
        assert "Thread-1" in result
        assert "Thread-2" in result


class TestFormatDynamicJson:
    def test_empty(self):
        result = format_dynamic_json([])
        assert result == "[]"

    def test_single_race(self):
        from threadcheck.dynamic.clock import VectorClock
        from threadcheck.dynamic.tracker import AccessRecord
        r1 = AccessRecord(
            var_name="counter", operation="write",
            thread_id=1, clock=VectorClock(), location=("a.py", 10),
        )
        r2 = AccessRecord(
            var_name="counter", operation="write",
            thread_id=2, clock=VectorClock(), location=("a.py", 20),
        )
        result = format_dynamic_json([("counter", r1, r2)])
        import json
        parsed = json.loads(result)
        assert len(parsed) == 1
        assert parsed[0]["var_name"] == "counter"
        assert parsed[0]["thread_1"]["id"] == 1
        assert parsed[0]["thread_2"]["id"] == 2
