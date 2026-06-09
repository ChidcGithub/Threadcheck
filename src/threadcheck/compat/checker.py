from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Sequence

from .models import CExtInfo, CompatStatus, FTCompatResult

_C_EXT_RE = re.compile(r"\.(pyd|so)$", re.IGNORECASE)
_FT_TAG_RE = re.compile(r"\.(cp\d+t|cpython-\d+t)-")


def _check_single(name: str) -> FTCompatResult:
    try:
        from importlib.metadata import PackageNotFoundError, distribution
    except ImportError:
        return FTCompatResult(
            name=name,
            status=CompatStatus.NOT_INSTALLED,
            reason="importlib.metadata not available",
        )

    try:
        dist = distribution(name)
    except PackageNotFoundError:
        return FTCompatResult(
            name=name,
            status=CompatStatus.NOT_INSTALLED,
            reason="not installed",
        )
    except Exception as exc:
        return FTCompatResult(
            name=name,
            status=CompatStatus.NOT_INSTALLED,
            reason=str(exc),
        )

    c_exts: list[CExtInfo] = []
    try:
        files = dist.files or []
    except Exception:
        files = []

    for f in files:
        fname = str(f)
        if not _C_EXT_RE.search(fname):
            continue
        c_exts.append(
            CExtInfo(filename=fname, has_ft_tag=bool(_FT_TAG_RE.search(fname)))
        )

    if not c_exts:
        return FTCompatResult(
            name=name,
            status=CompatStatus.COMPATIBLE,
            reason="pure Python, no C extensions",
        )

    ft_missing = [e for e in c_exts if not e.has_ft_tag]
    if ft_missing:
        return FTCompatResult(
            name=name,
            status=CompatStatus.NEEDS_VERIFICATION,
            c_exts=c_exts,
            reason=f"{len(ft_missing)} C extension(s) not compiled for free-threading ABI",
        )

    return FTCompatResult(
        name=name,
        status=CompatStatus.COMPATIBLE,
        c_exts=c_exts,
        reason="all C extensions compiled for free-threading ABI",
    )


def check_compat(
    names: Sequence[str] | None = None,
) -> list[FTCompatResult]:
    if names is not None:
        return [_check_single(n) for n in names]

    try:
        from importlib.metadata import distributions
    except ImportError:
        return []

    results: list[FTCompatResult] = []
    for dist in distributions():
        name = dist.metadata.get("Name", "")
        if name:
            results.append(_check_single(name))

    results.sort(key=lambda r: r.name.lower())
    return results
