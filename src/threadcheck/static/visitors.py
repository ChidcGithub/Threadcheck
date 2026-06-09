import ast
from pathlib import Path

from .models import RaceWarning, Severity, WarningCategory, Confidence


def _calc_confidence(context, func_name: str | None) -> Confidence:
    if func_name and context.is_thread_target(func_name):
        return Confidence.HIGH
    if context.has_any_thread():
        return Confidence.MEDIUM
    return Confidence.LOW


class GlobalVisitor(ast.NodeVisitor):
    def __init__(self, filepath: Path, context):
        self.filepath = filepath
        self.context = context
        self.warnings: list[RaceWarning] = []
        self._globals_in_function: set[str] = set()
        self._current_func: str | None = None

    def visit_FunctionDef(self, node):
        old = self._globals_in_function, self._current_func
        self._globals_in_function = set()
        self._current_func = node.name
        self.generic_visit(node)
        self._globals_in_function, self._current_func = old

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Global(self, node):
        for name in node.names:
            self._globals_in_function.add(name)

    def _check_name(self, node):
        if isinstance(node, ast.Name) and node.id in self._globals_in_function:
            if self.context.is_protected(node.lineno):
                return
            confidence = _calc_confidence(self.context, self._current_func)
            self.warnings.append(
                RaceWarning(
                    file=self.filepath,
                    line=node.lineno,
                    col=node.col_offset,
                    severity=Severity.WARNING,
                    category=WarningCategory.UNSAFE_GLOBAL,
                    message=f"Global variable `{node.id}` modified without lock",
                    suggestion=f"Use `threading.Lock()` to protect `{node.id}`",
                    confidence=confidence,
                )
            )

    def visit_Assign(self, node):
        for target in node.targets:
            if isinstance(target, ast.Name):
                self._check_name(target)
            elif isinstance(target, (ast.Tuple, ast.List)):
                for elt in target.elts:
                    if isinstance(elt, ast.Name):
                        self._check_name(elt)
        self.generic_visit(node)

    def visit_AugAssign(self, node):
        self._check_name(node.target)
        self.generic_visit(node)

    def visit_Delete(self, node):
        for target in node.targets:
            if isinstance(target, ast.Name):
                self._check_name(target)
        self.generic_visit(node)


class NonlocalVisitor(ast.NodeVisitor):
    def __init__(self, filepath: Path, context):
        self.filepath = filepath
        self.context = context
        self.warnings: list[RaceWarning] = []
        self._nonlocals_in_function: set[str] = set()
        self._current_func: str | None = None

    def visit_FunctionDef(self, node):
        old = self._nonlocals_in_function, self._current_func
        self._nonlocals_in_function = set()
        self._current_func = node.name
        self.generic_visit(node)
        self._nonlocals_in_function, self._current_func = old

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Nonlocal(self, node):
        for name in node.names:
            self._nonlocals_in_function.add(name)

    def _check_name(self, node):
        if isinstance(node, ast.Name) and node.id in self._nonlocals_in_function:
            if self.context.is_protected(node.lineno):
                return
            confidence = _calc_confidence(self.context, self._current_func)
            self.warnings.append(
                RaceWarning(
                    file=self.filepath,
                    line=node.lineno,
                    col=node.col_offset,
                    severity=Severity.WARNING,
                    category=WarningCategory.UNSAFE_NONLOCAL,
                    message=f"Nonlocal variable `{node.id}` modified without lock",
                    suggestion=f"Use `threading.Lock()` to protect `{node.id}`",
                    confidence=confidence,
                )
            )

    def visit_Assign(self, node):
        for target in node.targets:
            if isinstance(target, ast.Name):
                self._check_name(target)
            elif isinstance(target, (ast.Tuple, ast.List)):
                for elt in target.elts:
                    if isinstance(elt, ast.Name):
                        self._check_name(elt)
        self.generic_visit(node)

    def visit_AugAssign(self, node):
        self._check_name(node.target)
        self.generic_visit(node)

    def visit_Delete(self, node):
        for target in node.targets:
            if isinstance(target, ast.Name):
                self._check_name(target)
        self.generic_visit(node)


class ThreadVisitor(ast.NodeVisitor):
    def __init__(self, filepath: Path, context):
        self.filepath = filepath
        self.context = context
        self.warnings: list[RaceWarning] = []

    def visit_Call(self, node):
        if isinstance(node.func, ast.Attribute) and node.func.attr == "Thread":
            if isinstance(node.func.value, ast.Name) and node.func.value.id == "threading":
                target = None
                for kw in node.keywords:
                    if kw.arg == "target":
                        if isinstance(kw.value, ast.Name):
                            target = kw.value.id
                        elif isinstance(kw.value, (ast.Lambda, ast.FunctionDef)):
                            target = "<lambda>"
                        elif isinstance(kw.value, ast.Attribute):
                            target = ast.unparse(kw.value)
                label = f" (target={target})" if target else ""
                self.warnings.append(
                    RaceWarning(
                        file=self.filepath,
                        line=node.lineno,
                        col=node.col_offset,
                        severity=Severity.INFO,
                        category=WarningCategory.THREAD_USAGE,
                        message=f"Thread creation detected{label}",
                        suggestion="Ensure shared variable access in thread functions is lock-protected",
                        confidence=Confidence.LOW,
                    )
                )
        self.generic_visit(node)


class SharedMutableVisitor(ast.NodeVisitor):
    def __init__(self, filepath: Path, context):
        self.filepath = filepath
        self.context = context
        self.warnings: list[RaceWarning] = []
        self._module_level_assigns: set[str] = set()
        self._in_function = False
        self._current_func: str | None = None

    def visit_Module(self, node):
        for item in node.body:
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name) and _is_mutable_literal(item.value):
                        self._module_level_assigns.add(target.id)
        self.generic_visit(node)

    def visit_FunctionDef(self, node):
        self._in_function = True
        self._current_func = node.name
        self.generic_visit(node)
        self._current_func = None
        self._in_function = False

    visit_AsyncFunctionDef = visit_FunctionDef

    def _add_warning(self, node, var_name: str, detail: str = ""):
        if self.context.is_protected(node.lineno):
            return
        confidence = _calc_confidence(self.context, self._current_func)
        msg = f"Module-level mutable object `{var_name}` modified inside function"
        if detail:
            msg = f"Module-level mutable object `{detail}` called from multiple threads"
        self.warnings.append(
            RaceWarning(
                file=self.filepath,
                line=node.lineno,
                col=node.col_offset,
                severity=Severity.WARNING,
                category=WarningCategory.SHARED_MUTABLE,
                message=msg,
                suggestion="Consider using thread-safe data structures or add lock protection",
                confidence=confidence,
            )
        )

    def visit_Assign(self, node):
        if self._in_function:
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id in self._module_level_assigns:
                    self._add_warning(node, target.id)
        self.generic_visit(node)

    def visit_AugAssign(self, node):
        if self._in_function and isinstance(node.target, ast.Name):
            if node.target.id in self._module_level_assigns:
                self._add_warning(node, node.target.id)
        self.generic_visit(node)

    def visit_Call(self, node):
        if self._in_function:
            if isinstance(node.func, ast.Attribute) and node.func.attr in (
                "append", "extend", "pop", "remove", "clear",
                "insert", "sort", "reverse", "update", "add", "discard",
            ):
                if isinstance(node.func.value, ast.Name) and node.func.value.id in self._module_level_assigns:
                    detail = f"{node.func.value.id}.{node.func.attr}()"
                    self._add_warning(node, node.func.value.id, detail)
        self.generic_visit(node)


class ClassAttributeVisitor(ast.NodeVisitor):
    def __init__(self, filepath: Path, context):
        self.filepath = filepath
        self.context = context
        self.warnings: list[RaceWarning] = []
        self._current_class: str | None = None
        self._current_method: str | None = None
        self._class_is_thread = False

    def visit_ClassDef(self, node):
        old = self._current_class, self._class_is_thread
        self._current_class = node.name
        self._class_is_thread = any(
            _is_name_or_attr(base, "Thread") for base in node.bases
        )
        self.generic_visit(node)
        self._current_class, self._class_is_thread = old

    def visit_FunctionDef(self, node):
        old = self._current_method
        if node.name in ("__init__", "__new__", "__class_getitem__"):
            self._current_method = None
            self.generic_visit(node)
            self._current_method = old
            return
        self._current_method = node.name
        self.generic_visit(node)
        self._current_method = old

    visit_AsyncFunctionDef = visit_FunctionDef

    def _check_attr(self, node, attr_name: str):
        if self.context.is_protected(node.lineno):
            return
        in_thread_target = self._current_method and self.context.is_thread_target(
            self._current_method
        )
        if in_thread_target or self._class_is_thread:
            confidence = Confidence.HIGH
        elif self.context.has_any_thread():
            confidence = Confidence.MEDIUM
        else:
            confidence = Confidence.LOW
        self.warnings.append(
            RaceWarning(
                file=self.filepath,
                line=node.lineno,
                col=node.col_offset,
                severity=Severity.WARNING,
                category=WarningCategory.CLASS_ATTRIBUTE,
                message=(
                    f"Attribute `{attr_name}` of class `{self._current_class}` "
                    f"modified without lock in method `{self._current_method}`"
                ),
                suggestion="Use `threading.Lock()` to protect class attribute access",
                confidence=confidence,
            )
        )

    def visit_Assign(self, node):
        if self._current_class and self._current_method:
            for target in node.targets:
                if isinstance(target, ast.Attribute):
                    if isinstance(target.value, ast.Name) and target.value.id == "self":
                        self._check_attr(node, target.attr)
        self.generic_visit(node)

    def visit_AugAssign(self, node):
        if self._current_class and self._current_method:
            if isinstance(node.target, ast.Attribute):
                if isinstance(node.target.value, ast.Name) and node.target.value.id == "self":
                    self._check_attr(node, node.target.attr)
        self.generic_visit(node)


def _is_mutable_literal(node):
    return isinstance(node, (ast.List, ast.Dict, ast.Set, ast.ListComp, ast.SetComp, ast.DictComp))


def _is_name_or_attr(node, name: str) -> bool:
    if isinstance(node, ast.Name):
        return node.id == name
    if isinstance(node, ast.Attribute):
        return node.attr == name
    return False
