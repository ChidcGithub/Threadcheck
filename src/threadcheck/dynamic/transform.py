import ast


_LOCK_NAMES = frozenset({"Lock", "RLock", "Semaphore", "BoundedSemaphore"})


_TRACKER_IMPORT = ast.parse(
    "from threadcheck.dynamic.tracker import ThreadCheckTracker as _threadcheck_tracker"
).body[0]


class TrackInjector:
    def __init__(self, filename: str = "<unknown>"):
        self.filename = filename

    def transform(self, tree: ast.Module) -> ast.Module:
        tree.body.insert(0, _TRACKER_IMPORT)
        scopes = {}
        self._collect_scopes(tree, scopes)
        self._inject(tree, scopes)
        return tree

    def _collect_scopes(self, node, scopes):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func_id = id(node)
            info = {"globals": set(), "nonlocals": set()}
            for child in ast.walk(node):
                if isinstance(child, ast.Global):
                    info["globals"].update(child.names)
                elif isinstance(child, ast.Nonlocal):
                    info["nonlocals"].update(child.names)
            scopes[func_id] = info
            for child in ast.iter_child_nodes(node):
                self._collect_scopes(child, scopes)
        else:
            for child in ast.iter_child_nodes(node):
                self._collect_scopes(child, scopes)

    def _inject(self, node, scopes, func_id=None):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func_id = id(node)

        for field in ("body", "orelse", "finalbody"):
            old = getattr(node, field, None)
            if isinstance(old, list):
                setattr(node, field, self._transform_list(old, scopes, func_id))

        for handler in getattr(node, "handlers", []):
            handler.body = self._transform_list(handler.body, scopes, func_id)

        for child in ast.iter_child_nodes(node):
            self._inject(child, scopes, func_id)

    def _transform_list(self, stmts, scopes, func_id):
        if func_id is None or func_id not in scopes:
            return stmts

        info = scopes[func_id]
        shared = info["globals"] | info["nonlocals"]

        new: list[ast.stmt] = []
        for stmt in stmts:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                new.append(stmt)
                continue

            # Inject read_before for shared variable reads (not including write targets)
            read_names = _find_read_names(stmt, shared)
            for name in sorted(read_names):
                new.append(_make_read_before(name, self.filename, stmt.lineno))

            if isinstance(stmt, ast.Assign):
                targets = [
                    t
                    for t in stmt.targets
                    if isinstance(t, ast.Name) and t.id in shared
                ]
                for t in targets:
                    new.append(_make_write_before(t.id, self.filename, stmt.lineno))
                new.append(stmt)

            elif isinstance(stmt, ast.AugAssign):
                if isinstance(stmt.target, ast.Name) and stmt.target.id in shared:
                    new.append(
                        _make_write_before(
                            stmt.target.id, self.filename, stmt.lineno
                        )
                    )
                new.append(stmt)

            elif isinstance(stmt, ast.Delete):
                targets = [
                    t
                    for t in stmt.targets
                    if isinstance(t, ast.Name) and t.id in shared
                ]
                for t in targets:
                    new.append(
                        _make_write_before(t.id, self.filename, stmt.lineno)
                    )
                new.append(stmt)

            elif isinstance(stmt, ast.With):
                lock_names = _resolve_lock_names(stmt)
                new.append(stmt)
                for ln in lock_names:
                    stmt.body.insert(
                        0,
                        _make_lock_acquire(ln, self.filename, stmt.lineno),
                    )
                for ln in reversed(lock_names):
                    stmt.body.append(
                        _make_lock_release(ln, self.filename, stmt.lineno),
                    )
            else:
                new.append(stmt)

        return new


def _find_read_names(stmt: ast.AST, shared_set: set[str]) -> set[str]:
    write_targets: set[str] = set()
    if isinstance(stmt, ast.Assign):
        for t in stmt.targets:
            if isinstance(t, ast.Name) and t.id in shared_set:
                write_targets.add(t.id)
    elif isinstance(stmt, ast.AugAssign):
        if isinstance(stmt.target, ast.Name) and stmt.target.id in shared_set:
            write_targets.add(stmt.target.id)
    elif isinstance(stmt, ast.Delete):
        for t in stmt.targets:
            if isinstance(t, ast.Name) and t.id in shared_set:
                write_targets.add(t.id)

    reads: set[str] = set()
    _collect_read_names(stmt, shared_set, reads)
    return reads - write_targets


_STMT_WITH_BODY = (
    ast.With, ast.For, ast.AsyncFor, ast.While, ast.If,
    ast.Try, ast.TryStar,
    ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef,
)


def _collect_read_names(node: ast.AST, shared_set: set[str], out: set[str]):
    if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load):
        if node.id in shared_set:
            out.add(node.id)
    if isinstance(node, _STMT_WITH_BODY):
        return
    for child in ast.iter_child_nodes(node):
        _collect_read_names(child, shared_set, out)


def _make_read_before(var_name: str, filename: str, lineno: int) -> ast.Expr:
    return ast.Expr(
        value=ast.Call(
            func=ast.Attribute(
                value=ast.Name(id="_threadcheck_tracker", ctx=ast.Load()),
                attr="read_before",
                ctx=ast.Load(),
            ),
            args=[
                ast.Constant(value=var_name),
                ast.Constant(value=filename),
                ast.Constant(value=lineno),
            ],
            keywords=[],
        ),
    )


def _make_write_before(var_name: str, filename: str, lineno: int) -> ast.Expr:
    return ast.Expr(
        value=ast.Call(
            func=ast.Attribute(
                value=ast.Name(id="_threadcheck_tracker", ctx=ast.Load()),
                attr="write_before",
                ctx=ast.Load(),
            ),
            args=[
                ast.Constant(value=var_name),
                ast.Constant(value=filename),
                ast.Constant(value=lineno),
            ],
            keywords=[],
        ),
    )


def _make_lock_acquire(lock_name: str, filename: str, lineno: int) -> ast.Expr:
    return ast.Expr(
        value=ast.Call(
            func=ast.Attribute(
                value=ast.Name(id="_threadcheck_tracker", ctx=ast.Load()),
                attr="lock_acquire",
                ctx=ast.Load(),
            ),
            args=[
                ast.Constant(value=lock_name),
                ast.Constant(value=filename),
                ast.Constant(value=lineno),
            ],
            keywords=[],
        ),
    )


def _make_lock_release(lock_name: str, filename: str, lineno: int) -> ast.Expr:
    return ast.Expr(
        value=ast.Call(
            func=ast.Attribute(
                value=ast.Name(id="_threadcheck_tracker", ctx=ast.Load()),
                attr="lock_release",
                ctx=ast.Load(),
            ),
            args=[
                ast.Constant(value=lock_name),
                ast.Constant(value=filename),
                ast.Constant(value=lineno),
            ],
            keywords=[],
        ),
    )


def _resolve_lock_names(with_stmt: ast.With) -> list[str]:
    names: list[str] = []
    for item in with_stmt.items:
        expr = item.context_expr
        if isinstance(expr, ast.Name):
            names.append(expr.id)
        elif isinstance(expr, ast.Call):
            if isinstance(expr.func, ast.Name) and expr.func.id in _LOCK_NAMES:
                names.append(ast.unparse(expr))
            elif isinstance(expr.func, ast.Attribute) and expr.func.attr in _LOCK_NAMES:
                names.append(ast.unparse(expr))
    return names


def transform_source(source: str, filename: str = "<unknown>") -> str:
    tree = ast.parse(source, filename=filename)
    TrackInjector(filename=filename).transform(tree)
    return ast.unparse(tree)


def transform_and_compile(source: str, filename: str = "<unknown>") -> str:
    tree = ast.parse(source, filename=filename)
    TrackInjector(filename=filename).transform(tree)
    ast.fix_missing_locations(tree)
    return compile(tree, filename, "exec")
