import ast

_LOCK_CLASSES = frozenset({"Lock", "RLock", "Semaphore", "BoundedSemaphore"})


class LockTracker(ast.NodeVisitor):
    def __init__(self):
        self.protected_regions: list[ast.With] = []
        self.lock_exprs: set[str] = set()

    def visit_With(self, node):
        for item in node.items:
            expr_name = ast.unparse(item.context_expr)
            if expr_name in self.lock_exprs or self._is_lock_creation(item.context_expr):
                self.lock_exprs.add(expr_name)
                self.protected_regions.append(node)
        self.generic_visit(node)

    def visit_Assign(self, node):
        for target in node.targets:
            if isinstance(node.value, ast.Call) and self._is_lock_creation(node.value):
                self.lock_exprs.add(ast.unparse(target))
        self.generic_visit(node)

    def is_protected_by_lock(self, line: int) -> bool:
        for region in self.protected_regions:
            start = getattr(region, "lineno", 0)
            end = getattr(region, "end_lineno", start)
            if start <= line <= end:
                return True
        return False

    @staticmethod
    def _is_lock_creation(node) -> bool:
        if not isinstance(node, ast.Call):
            return False
        func = node.func
        if isinstance(func, ast.Name):
            return func.id in _LOCK_CLASSES
        if isinstance(func, ast.Attribute):
            return func.attr in _LOCK_CLASSES
        return False
