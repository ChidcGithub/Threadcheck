from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class CompatStatus(Enum):
    COMPATIBLE = "compatible"
    NEEDS_VERIFICATION = "needs_verification"
    NOT_INSTALLED = "not_installed"


@dataclass
class CExtInfo:
    filename: str
    has_ft_tag: bool

    @property
    def tag(self) -> str:
        match = re.search(r"\.(cpython-\d+t?|cp\d+t?)-", self.filename)
        if match:
            return match.group(1)
        return ""


@dataclass
class FTCompatResult:
    name: str
    status: CompatStatus
    c_exts: list[CExtInfo] = field(default_factory=list)
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "status": self.status.value,
            "c_exts": [{"filename": e.filename, "has_ft_tag": e.has_ft_tag} for e in self.c_exts],
            "reason": self.reason,
        }
