from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import TYPE_CHECKING

from .models import RaceWarning
from .lock_tracker import LockTracker
from .visitors import (
    GlobalVisitor,
    NonlocalVisitor,
    ThreadVisitor,
    SharedMutableVisitor,
    ClassAttributeVisitor,
)

_INLINE_IGNORE_RE = re.compile(
    r"#\s*threadcheck:\s*ignore\b(?!-start\b)(?!-end\b)", re.IGNORECASE
)
_INLINE_IGNORE_START_RE = re.compile(
    r"#\s*threadcheck:\s*ignore-start\b", re.IGNORECASE
)
_INLINE_IGNORE_END_RE = re.compile(
    r"#\s*threadcheck:\s*ignore-end\b", re.IGNORECASE
)

if TYPE_CHECKING:
    from ..config import ThreadCheckConfig

_SKIP_DIRS = frozenset({
    ".git", "__pycache__", ".venv", "venv", "env", ".env",
    ".mypy_cache", ".pytest_cache", "node_modules", ".tox",
    "dist", "build", ".eggs", "site-packages",
})


class AnalysisContext:
    def __init__(self, filepath: Path, tree: ast.Module, global_thread_targets: set[str] | None = None):
        self.filepath = filepath
        self._thread_targets: set[str] = set(global_thread_targets or ())
        self._has_thread = False
        self._find_thread_targets(tree)
        self.lock_tracker = LockTracker()
        self.lock_tracker.visit(tree)

    def is_protected(self, line: int) -> bool:
        return self.lock_tracker.is_protected_by_lock(line)

    def is_thread_target(self, func_name: str) -> bool:
        return func_name in self._thread_targets

    def has_any_thread(self) -> bool:
        return self._has_thread

    def _find_thread_targets(self, tree):
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute) and node.func.attr == "Thread":
                    self._has_thread = True
                    for kw in node.keywords:
                        if kw.arg == "target":
                            if isinstance(kw.value, ast.Name):
                                self._thread_targets.add(kw.value.id)
                            elif isinstance(kw.value, ast.Attribute):
                                self._thread_targets.add(kw.value.attr)
                attr_name = getattr(node.func, "attr", None)
                if attr_name in ("submit", "map"):
                    self._has_thread = True
                    args = node.args
                    if args and isinstance(args[0], ast.Name):
                        self._thread_targets.add(args[0].id)


def _get_inline_ignored_lines(source: str) -> set[int]:
    lines = source.splitlines()
    ignored: set[int] = set()
    region_active = False
    region_start = 0

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        if _INLINE_IGNORE_END_RE.search(stripped):
            if region_active:
                for j in range(region_start, i + 1):
                    ignored.add(j)
                region_active = False
            continue
        if _INLINE_IGNORE_START_RE.search(stripped):
            region_active = True
            region_start = i
            continue
        if region_active:
            continue
        if _INLINE_IGNORE_RE.search(stripped):
            ignored.add(i)

    if region_active:
        for j in range(region_start, len(lines) + 1):
            ignored.add(j)

    return ignored


def analyze_file(filepath: Path, global_thread_targets: set[str] | None = None, config: ThreadCheckConfig | None = None) -> list[RaceWarning]:
    try:
        source = filepath.read_text(encoding="utf-8")
    except Exception:
        return []

    try:
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError:
        return []

    context = AnalysisContext(filepath, tree, global_thread_targets)

    all_warnings: list[RaceWarning] = []

    for visitor_cls in (
        GlobalVisitor,
        NonlocalVisitor,
        ThreadVisitor,
        SharedMutableVisitor,
        ClassAttributeVisitor,
    ):
        visitor = visitor_cls(filepath, context)
        visitor.visit(tree)
        all_warnings.extend(visitor.warnings)

    if all_warnings:
        ignored_lines = _get_inline_ignored_lines(source)
        all_warnings = [w for w in all_warnings if w.line not in ignored_lines]

    if config is not None:
        root = config.project_root if hasattr(config, 'project_root') else filepath.parent
        all_warnings = [
            w for w in all_warnings
            if not config.should_ignore_line(filepath, root, w.line)
        ]

    return all_warnings


def _collect_thread_targets(files: list[Path]) -> set[str]:
    targets: set[str] = set()
    for py_file in files:
        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(py_file))
        except Exception:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute) and node.func.attr == "Thread":
                    for kw in node.keywords:
                        if kw.arg == "target":
                            if isinstance(kw.value, ast.Name):
                                targets.add(kw.value.id)
                            elif isinstance(kw.value, ast.Attribute):
                                targets.add(kw.value.attr)
                attr_name = getattr(node.func, "attr", None)
                if attr_name in ("submit", "map"):
                    args = node.args
                    if args and isinstance(args[0], ast.Name):
                        targets.add(args[0].id)
    return targets


def analyze_path(path: str, config: ThreadCheckConfig | None = None) -> list[RaceWarning]:
    p = Path(path).resolve()
    all_warnings: list[RaceWarning] = []

    root = p if p.is_dir() else p.parent

    if p.is_file():
        if p.suffix == ".py":
            if config is None or not config.should_ignore_file(p, root):
                global_targets = _collect_thread_targets([p])
                all_warnings.extend(analyze_file(p, global_targets, config=config))
    elif p.is_dir():
        py_files = [f for f in sorted(p.rglob("*.py")) if not _should_skip(f, config, root)]
        global_targets = _collect_thread_targets(py_files)
        total = len(py_files)
        for idx, py_file in enumerate(py_files):
            all_warnings.extend(analyze_file(py_file, global_targets, config))

    return all_warnings


def _should_skip(path: Path, config: ThreadCheckConfig | None = None, root: Path | None = None) -> bool:
    for part in path.parts:
        if part in _SKIP_DIRS or part.startswith("."):
            return True
    if config is not None and root is not None:
        if config.should_ignore_file(path, root):
            return True
    return False
