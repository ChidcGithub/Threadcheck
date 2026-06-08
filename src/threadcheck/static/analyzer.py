import ast
from pathlib import Path

from .models import RaceWarning
from .lock_tracker import LockTracker
from .visitors import (
    GlobalVisitor,
    NonlocalVisitor,
    ThreadVisitor,
    SharedMutableVisitor,
    ClassAttributeVisitor,
)

_SKIP_DIRS = frozenset({
    ".git", "__pycache__", ".venv", "venv", "env", ".env",
    ".mypy_cache", ".pytest_cache", "node_modules", ".tox",
    "dist", "build", ".eggs", "site-packages",
})


class AnalysisContext:
    def __init__(self, filepath: Path, tree: ast.Module):
        self.filepath = filepath
        self._thread_targets: set[str] = set()
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


def analyze_file(filepath: Path) -> list[RaceWarning]:
    try:
        source = filepath.read_text(encoding="utf-8")
    except Exception:
        return []

    try:
        tree = ast.parse(source, filename=str(filepath))
    except SyntaxError:
        return []

    context = AnalysisContext(filepath, tree)

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

    return all_warnings


def analyze_path(path: str) -> list[RaceWarning]:
    p = Path(path).resolve()
    all_warnings: list[RaceWarning] = []

    if p.is_file():
        if p.suffix == ".py":
            all_warnings.extend(analyze_file(p))
    elif p.is_dir():
        for py_file in sorted(p.rglob("*.py")):
            if _should_skip(py_file):
                continue
            all_warnings.extend(analyze_file(py_file))

    return all_warnings


def _should_skip(path: Path) -> bool:
    for part in path.parts:
        if part in _SKIP_DIRS or part.startswith("."):
            return True
    return False
