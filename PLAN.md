# Threadcheck Development Plan

## Round A (Core Gap Fill) — Complete
- A1: `read_before()` injection in AST transform
- A2: Cross-module `Thread` target analysis
- A3: Exit codes (`scan` → 1 if warnings, `run` → 1 if races, `compat` → 1 if `NEEDS_VERIFICATION`)
- A4: `with lock1, lock2:` nested lock support
- A5: `executor.submit(func)` / `executor.map(func, ...)` static target extraction

## Round B (Developer Experience) — Complete
- B1: `.threadcheckignore` — gitignore-style + line suppression
- B2: `pyproject.toml` config — `[tool.threadcheck]` section
- B3: Enhanced terminal output — file grouping, severity icons, filename shortening
- B4: Output levels — `-q` / default / `-v`
- B5: HTML report — self-contained page with dark/light theme
- Config loader, static analyzer config integration, demo update, README rewrite

## Round C (Bug Fixes & Improvements) — Current

### Phase 1 — Quick Fixes
| # | Item | Status |
|---|------|--------|
| #12 | Windows output corruption — box-drawing chars in `format_dynamic_races` | Done |
| H | ThreadVisitor THREAD_USAGE dedup by target | Done |
| I | Cross-module: single-file mode needs `_collect_thread_targets` | Done |
| #11 | `_is_mutable_literal` misses `list()`/`set()`/`dict()` calls | Done |
| #10 | Remove `builtins._threadcheck_tracker` global namespace pollution | Done |
| K | TOCTOU in `_get_clock` — simplify lock pattern | Done |

### Phase 2 — Medium Changes
| # | Item | Status |
|---|------|--------|
| #14 | Inline `# threadcheck: ignore` (per-line + region) | Done |
| F | Subscript assignment (`shared_dict[key] = val`) not instrumented | Done |
| #13 | Manual `lock.acquire()`/`release()` not tracked by LockTracker | Done |
| G | ThreadPoolExecutor target not instrumented dynamically | Done |

### Phase 3 — Complex
| # | Item | Status |
|---|------|--------|
| #9 | Closure lock false positive — propagation of main thread clock to new threads | Done |

### Deferred to Round D
- #15: Call chain tracing — inter-procedural lock scope propagation
- threading.Atomic support
- Deadlock detection
- Thread.join() happens-before
- GitHub Action, pre-commit hook, VS Code integration

## Versions
- v0.0.1.2a1: Round B complete
- v0.0.1.2a5: Cross-platform CI + README rewrite
- v0.0.1.2a6: `__name__ == "__main__"` exec() fix
