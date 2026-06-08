# threadcheck

[![Python](https://img.shields.io/badge/python-3.12%2B-blue)](https://www.python.org)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![PyPI](https://img.shields.io/badge/pypi-v0.1.0-orange)](https://pypi.org/project/threadcheck/)
[![Tests](https://img.shields.io/badge/tests-21%2F21-passing-brightgreen)]()

Python data race detector for the free-threading (no-GIL) era. Detects concurrent access to shared mutable state in multi-threaded Python programs through static analysis and runtime instrumentation.

---

## Problem

Python 3.14 (2026) introduces free-threading, removing the Global Interpreter Lock (GIL). This enables true parallel execution of multi-threaded code, but the ecosystem lacks debugging tools for concurrency bugs. Go has `-race`, C++ has ThreadSanitizer, Java has SpotBugs. Python has nothing comparable without recompiling the interpreter with Clang and TSan.

threadcheck is a pure-Python race detector that installs with `pip` and works out of the box.

---

## Features

- **Static analysis** -- scans AST for shared mutable state (global, nonlocal, class attributes) and missing lock protection
- **Runtime detection** -- instruments code via AST transformation at import time; tracks memory accesses with vector clocks and detects happens-before violations
- **Lock-aware suppression** -- understands `threading.Lock`, `threading.RLock`, and `with`-based synchronization; raises confidence when locks are missing and suppresses warnings when they are present
- **Confidence scoring** -- each warning tagged HIGH / MEDIUM / LOW based on thread context and lock coverage
- **CLI tool** -- single-command static scan or instrumented execution
- **JSON and SARIF output** -- suitable for CI/CD pipeline integration

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

Output:

```
[WARNING] [HIGH] [unsafe_global] my_project/counter.py:8:8
       Global variable `counter` modified without lock in thread
       Suggestion: use `threading.Lock()` to protect access
```

JSON output:

```bash
threadcheck scan my_project/ --json -o report.json
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
      Thread-28928 (write) at my_script.py:8
      Thread-9888 (write) at my_script.py:8
```

A script protected with locks reports:

```
No data races detected
```

### CI Integration

```bash
pip install threadcheck
threadcheck scan src/ --json -o threadcheck_report.json
```

---

## Commands

| Command | Description | Status |
|---|---|---|
| `scan <path>` | Static race analysis of file or directory | Stable |
| `run <script>` | Execute script with runtime race detection | Beta |
| `check-compat <path>` | Free-threading compatibility check | Planned |

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

---

## Architecture

### Static Analysis Pipeline

1. Parse source into AST
2. Identify shared mutable state: globals, nonlocals, class attributes (`self.x`), module-level mutable objects
3. Detect thread creation sites (`threading.Thread`)
4. Cross-reference with lock usage (`with lock:`, `lock.acquire()`)
5. Assign confidence: HIGH (thread target, no lock), MEDIUM (thread present, no lock), LOW (suspicious pattern, no thread context)
6. Report findings with repair suggestions

### Runtime Detection Pipeline

1. Parse source into AST
2. Identify shared variables per function scope
3. Transform AST: inject `write_before()`, `lock_acquire()`, `lock_release()` calls around shared variable accesses
4. Compile and execute transformed code under a tracker that maintains per-thread vector clocks
5. On lock acquire, synchronize clocks (happens-before merge)
6. After execution, scan access log for conflicting operations (concurrent writes or write-read pairs with no happens-before relationship)
7. Report detected races with thread IDs and source locations

---

## Roadmap

| Phase | Feature | Status |
|---|---|---|
| 1 | CLI, static analysis (globals/nonlocals) | Done |
| 2 | Class attributes, lock suppression, confidence scoring | Done |
| 3 | AST import hook, runtime instrumentation, vector clocks | Done |
| 4 | Race report deduplication, enhanced happens-before analysis | Planned |
| 5 | SARIF output, JSON reporting | Planned |
| 6 | pytest plugin | Planned |
| 7 | Free-threading compatibility checker | Planned |

---

## Limitations

- Static analysis may produce false positives (reports race that cannot occur at runtime) and false negatives (misses races that involve indirect sharing through aliases or containers)
- Runtime detection modifies the AST before execution; code that introspects its own source or frame objects may behave differently
- Runtime instrumentation incurs overhead (approximately 2-5x slowdown for typical code)
- Lock tracking supports `threading.Lock`, `threading.RLock`, and standard `with`-based patterns; other synchronization primitives (`threading.Event`, `threading.Condition`, third-party libraries) are not tracked

---

## License

MIT

---

## Contributing

Contributions are welcome. Please open an issue or submit a pull request on GitHub.
