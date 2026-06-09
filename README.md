# Threadcheck

[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Platform](https://img.shields.io/badge/platform-linux%20%7C%20windows%20%7C%20macos-lightgrey)]()
[![CI](https://github.com/ChidcGithub/Threadcheck/actions/workflows/test.yml/badge.svg)](https://github.com/ChidcGithub/Threadcheck/actions/workflows/test.yml)
[![Ruff](https://img.shields.io/badge/code%20style-ruff-000000)](https://github.com/astral-sh/ruff)

Python data race detector for the free-threading (no-GIL) era. Detects concurrent access to shared mutable state in multi-threaded Python programs through static analysis and runtime instrumentation.

---

## Problem

Python 3.14 (2026) introduces free-threading, removing the Global Interpreter Lock (GIL). This enables true parallel execution of multi-threaded code, but the ecosystem lacks debugging tools for concurrency bugs. Go has `-race`, C++ has ThreadSanitizer, Java has SpotBugs. Python has nothing comparable without recompiling the interpreter with Clang and TSan.

threadcheck is a pure-Python race detector that installs with `pip` and works out of the box across Linux, Windows, and macOS.

---

## Features

- **Static analysis** -- scans AST for shared mutable state (`global`, `nonlocal`, class attributes, module-level lists/dicts) and missing lock protection
- **Runtime detection** -- instruments code via AST transformation at import time; tracks memory accesses with vector clocks and detects happens-before violations (read-write and write-write races)
- **Lock-aware suppression** -- understands `threading.Lock`/`RLock` and `with`-based synchronization; supports nested locks (`with lock1, lock2:`) with automatic per-lock vector clock tracking
- **Cross-module analysis** -- two-pass scan collects `Thread(target=...)` and `executor.submit/map` targets across all files in a directory
- **Confidence scoring** -- each warning tagged HIGH / MEDIUM / LOW based on thread context and lock coverage
- **Configuration** -- `.threadcheckignore` file (gitignore-style patterns + `file:line` suppression) and `[tool.threadcheck]` section in `pyproject.toml`
- **Multiple output formats** -- terminal (grouped by file, colorized), JSON, SARIF v2.1.0, and self-contained HTML report
- **pytest plugin** -- automatic race detection during test execution via `--threadcheck` flag
- **Free-threading compatibility checker** -- `threadcheck compat` scans installed packages for C extensions and checks FT ABI tags

---

## Installation

```bash
pip install threadcheck
```

Requires Python 3.12+. Python 3.14+ is recommended for free-threading features.

---

## Quick Start

### Static Analysis

Scan a file or directory for potential race conditions without running any code:

```bash
threadcheck scan my_project/
```

Output (grouped by file, with severity icons and per-file summary):

```
  [1/2] my_project/counter.py
  --------------------------------
    [!] HIGH [unsafe_global] line 8:8
          Global variable `counter` modified without lock
          suggestion: Use `threading.Lock()` to protect `counter`
    [i] LOW [thread_usage] line 10:11
          Thread creation detected (target=increment)

  [2/2] my_project/worker.py
  --------------------------------
    [!] HIGH [shared_mutable] line 15:8
          Module-level mutable object `results.append()` called from multiple threads

Total: 2 issue(s) in 2 file(s) (0 error(s), 2 warning(s), 0 info(s))
```

### Runtime Detection

Execute a script with instrumentation to detect actual data races:

```bash
threadcheck run my_script.py
```

Output for a racing script:

```
Data races detected:

  [!] `counter`
    |-- Thread-28928 (write) at my_script.py:8
    |-- Thread-9888 (write) at my_script.py:8
    \-- No happens-before relationship between accesses
       (10000 overlapping accesses)
```

A script protected with locks reports:

```
No data races detected
```

### Free-threading Compatibility Check

Check whether your project's dependencies support free-threading:

```bash
threadcheck compat
```

Output:

```
threadcheck compat - Free-threading compatibility check
Python 3.13.10

  [OK] numpy                 C extension has free-threading tag (cp313t-)
  [??] torch                 C extension without free-threading tag
  [OK] pytest                pure Python, no C extensions

Total: 3 package(s) - 2 compatible, 1 need verification, 0 not installed
```

### HTML Report

```bash
threadcheck scan my_project/ -o report.html
```

Generates a self-contained HTML report with dark/light theme, sortable table, and summary cards.

### Quiet / Verbose Modes

```bash
threadcheck scan my_project/ -q     # one-line summary only
threadcheck scan my_project/ -v     # include source code snippets
threadcheck scan my_project/        # default grouped output
```

---

## Configuration

### `.threadcheckignore`

Create a `.threadcheckignore` file in your project root (gitignore-style patterns):

```
# Ignore generated files
generated/*.py
build/*.py

# Ignore specific lines in a specific file
src/legacy.py:42          # suppress line 42
src/legacy.py:50-60       # suppress lines 50-60

# Negation (do not ignore)
*.py
!important.py
```

### `pyproject.toml`

```toml
[tool.threadcheck]
ignore = [
    "build/*",
    "generated/*.py",
]
```

Both sources are merged automatically.

---

## Output Formats

| Flag | Format | Use Case |
|---|---|---|
| *(default)* | Terminal (colorized, grouped) | Interactive use |
| `-q` | One-line summary | Quick status |
| `-v` | Terminal + source snippets | Debugging |
| `--json` | JSON | CI pipelines |
| `--sarif` | SARIF v2.1.0 | GitHub CodeQL integration |
| `-o report.html` | Self-contained HTML | Team reports |

---

## Commands

| Command | Description |
|---|---|
| `scan <path>` | Static race analysis of file or directory |
| `run <script>` | Execute script with runtime race detection |
| `compat [path]` | Check free-threading compatibility of dependencies |

---

## Library Usage

```python
from threadcheck import analyze_file, analyze_path

warnings = analyze_file("my_module.py")
warnings = analyze_path("src/")

for w in warnings:
    print(f"{w.file}:{w.line} [{w.confidence.value}] {w.message}")
```

```python
from threadcheck.dynamic.tracker import ThreadCheckTracker
from threadcheck.dynamic.transform import transform_and_compile

code = transform_and_compile(source, "script.py")
ThreadCheckTracker.start()
exec(code, {"_threadcheck_tracker": ThreadCheckTracker})
ThreadCheckTracker.stop()

print(ThreadCheckTracker.format_races())
ThreadCheckTracker.reset()
```

### pytest Integration

```bash
python -m pytest tests/ --threadcheck
```

The plugin hooks into `pytest_runtest_call` and reports race warnings as test failures.

---

## Architecture

### Static Analysis Pipeline

1. Parse source into AST
2. Identify shared mutable state: globals, nonlocals, class attributes (`self.x`), module-level mutable objects (lists, dicts, sets)
3. Detect thread creation sites (`threading.Thread`, `executor.submit/map`)
4. Cross-reference with lock usage (`with lock:`, nested `with lock1, lock2:`)
5. Assign confidence: HIGH (thread target, no lock), MEDIUM (thread present, no lock), LOW (suspicious pattern, no thread context)
6. Report findings with repair suggestions

### Runtime Detection Pipeline

1. Parse source into AST
2. Identify shared variables per function scope (`global`, `nonlocal` declarations)
3. Transform AST: inject `read_before()` for reads and `write_before()` for writes of shared variables; inject `lock_acquire()`/`lock_release()` around `with` blocks
4. Compile and execute transformed code under a tracker that maintains per-thread vector clocks
5. On lock acquire, merge the lock's clock into the thread's clock (happens-before)
6. On lock release, save the thread's clock to the lock
7. After execution, scan access log for conflicting operations (concurrent writes OR write-read pairs with no happens-before relationship)
8. Report detected races with thread IDs, source locations, and overlap counts

### Free-threading Compatibility Check

1. Parse project dependencies from `pyproject.toml` or `requirements.txt`
2. For each installed package, scan for C extension files (`.pyd`/`.so`)
3. If no C extensions found -> COMPATIBLE
4. If C extension filename contains free-threading ABI tag (`cp313t-`/`cpython-313t-`) -> COMPATIBLE
5. Otherwise -> NEEDS_VERIFICATION

---

## Project Structure

```
threadcheck/
|-- pyproject.toml
|-- src/threadcheck/
|   |-- __init__.py
|   |-- __main__.py
|   |-- _version.py           # single version source
|   |-- _tid.py               # platform thread ID (swapped per-platform in CI)
|   |-- cli.py                # argument parsing + dispatch
|   |-- config.py             # .threadcheckignore + pyproject.toml loader
|   |-- pytest_plugin.py      # --threadcheck flag for pytest
|   |-- static/
|   |   |-- analyzer.py       # static analysis entry point
|   |   |-- visitors.py       # 5 AST visitors
|   |   |-- lock_tracker.py   # lock usage analysis
|   |   \-- models.py         # RaceWarning, Severity, Confidence
|   |-- dynamic/
|   |   |-- __main__.py       # run_script entry point
|   |   |-- transform.py      # AST transformation engine
|   |   |-- tracker.py        # runtime tracker with vector clocks
|   |   |-- clock.py          # vector clock implementation
|   |   \-- hook.py           # sys.meta_path import hook
|   |-- compat/
|   |   |-- checker.py        # C extension FT tag scanner
|   |   \-- models.py         # FTCompatResult, CompatStatus
|   \-- reporting/
|       |-- formatter.py      # terminal / JSON output
|       |-- sarif.py          # SARIF v2.1.0 output
|       \-- html.py           # HTML report output
|-- tests/
|   |-- fixtures/             # 11 fixture files with known races
|   |-- test_static_analyzer.py
|   |-- test_dynamic_detector.py
|   |-- test_formatter.py
|   |-- test_sarif.py
|   |-- test_compat.py
|   |-- test_config.py
|   \-- test_pytest_plugin.py
|-- demo/
|   |-- race_example.py       # sample with intentional races
|   \-- run_demo.py           # demo runner for all output formats
\-- README.md
```

---

## Platform Support

| Platform | Python | CI |
|---|---|---|
| Linux (x86_64) | 3.12, 3.13, 3.14 | ubuntu-latest |
| Windows (amd64) | 3.12, 3.13, 3.14 | windows-latest |
| macOS (ARM64) | 3.12, 3.13, 3.14 | macos-latest |

Thread IDs: uses `native_id` (gettid) on Linux/macOS, `threading.get_ident()` on Windows.

---

## Roadmap

- **v0.0.1.2a1** (current): Round A (core gap fill) + Round B (DX) -- static and dynamic analysis, lock tracking, cross-module analysis, pytest plugin, FT compat checker, HTML reports, configuration, enhanced output
- **v0.2.0** (next): Round C -- `Thread.join()` happens-before, `threading.Atomic` support, function call chain tracking, deadlock detection
- **v1.0.0** (future): Round D -- GitHub Action, pre-commit hook, VS Code integration, stable API

---

## Limitations

- Static analysis may produce false positives (reports a race that cannot occur at runtime) and false negatives (misses races involving indirect sharing through aliases or containers)
- Runtime detection modifies the AST before execution; code that introspects its own source or frame objects may behave differently
- Runtime instrumentation incurs overhead (approximately 2-5x slowdown for typical code)
- Lock tracking supports `threading.Lock`, `threading.RLock`, and standard `with`-based patterns; other synchronization primitives (`threading.Event`, `threading.Condition`, third-party libraries) are not tracked
- Cross-module analysis handles `Thread(target=...)` and `executor.submit/map` but does not perform full inter-procedural data-flow analysis

---

## License

MIT

---

## Contributing

Contributions are welcome. Please open an issue or submit a pull request on GitHub.
