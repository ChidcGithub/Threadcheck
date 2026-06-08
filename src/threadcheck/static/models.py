from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class Severity(Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class WarningCategory(Enum):
    UNSAFE_GLOBAL = "unsafe_global"
    UNSAFE_NONLOCAL = "unsafe_nonlocal"
    UNPROTECTED_ACCESS = "unprotected_access"
    THREAD_USAGE = "thread_usage"
    SHARED_MUTABLE = "shared_mutable"
    CLASS_ATTRIBUTE = "class_attribute"


class Confidence(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class RaceWarning:
    file: Path
    line: int
    col: int
    severity: Severity
    category: WarningCategory
    message: str
    suggestion: str | None = None
    confidence: Confidence = Confidence.MEDIUM

    def to_dict(self) -> dict:
        return {
            "file": str(self.file),
            "line": self.line,
            "col": self.col,
            "severity": self.severity.value,
            "category": self.category.value,
            "message": self.message,
            "suggestion": self.suggestion,
            "confidence": self.confidence.value,
        }
