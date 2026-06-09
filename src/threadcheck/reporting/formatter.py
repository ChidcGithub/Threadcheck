from ..static.models import RaceWarning, Severity, Confidence

_CONFIDENCE_TAG = {
    Confidence.HIGH: "[HIGH]",
    Confidence.MEDIUM: "[MED]",
    Confidence.LOW: "[LOW]",
}

_SEVERITY_TAG = {
    Severity.ERROR: "[ERROR]",
    Severity.WARNING: "[WARNING]",
    Severity.INFO: "[INFO]",
}


def format_report(warnings: list[RaceWarning]) -> str:
    if not warnings:
        return "No data-race issues detected"

    lines: list[str] = []

    for w in warnings:
        sev = _SEVERITY_TAG.get(w.severity, "[?]")
        conf = _CONFIDENCE_TAG.get(w.confidence, "")
        lines.append(
            f"{sev} {conf} [{w.category.value}] {w.file}:{w.line}:{w.col}"
        )
        lines.append(f"       {w.message}")
        if w.suggestion:
            lines.append(f"       suggestion: {w.suggestion}")
        lines.append("")

    return "\n".join(lines)
