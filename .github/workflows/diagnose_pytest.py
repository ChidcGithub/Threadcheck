"""Diagnose the full pytest plugin flow.
- Test A: direct import (same process)
- Test B: subprocess pytest (like the real test)
"""
import subprocess
import sys
import textwrap
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent  # repo root
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "src"))

print(f"Python: {sys.version}")
print(f"REPO: {REPO}")

# ── 1. Create helper module (like test_plugin_detects_race does) ──
tmp_dir = REPO / "tmp_test_plugin"
tmp_dir.mkdir(exist_ok=True)

helper = tmp_dir / "race_helpers.py"
helper.write_text(
    textwrap.dedent("""\
        import threading
        counter = 0
        def run_racy_increment():
            global counter
            threads = []
            def inc():
                global counter
                for _ in range(50):
                    counter += 1
            for _ in range(3):
                t = threading.Thread(target=inc)
                t.start()
                threads.append(t)
            for t in threads:
                t.join()
    """),
    encoding="utf-8",
)

test_file = tmp_dir / "test_race.py"
test_file.write_text(
    textwrap.dedent("""\
        import sys
        from race_helpers import run_racy_increment
        import race_helpers as rh
        _has = "_threadcheck_tracker" in rh.__dict__
        print(f"[DBG] has_tracker={_has}", flush=True)
        if _has:
            _t = type(rh.__dict__["_threadcheck_tracker"]).__name__
            print(f"[DBG] tracker_type={_t}", flush=True)
        def test_race():
            run_racy_increment()
    """),
    encoding="utf-8",
)

# ═══════════════════════════════════════════════════════════════════
# Test A: direct import (same process)
# ═══════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("Test A: direct import (same process)")
print("=" * 60)

sys.path.insert(0, str(tmp_dir))

from threadcheck.dynamic.hook import install_hook, uninstall_hook
from threadcheck.dynamic.tracker import ThreadCheckTracker

rootpath = REPO
hook = install_hook(include_paths=[rootpath])
print(f"include_paths: {[str(p) for p in hook._include_paths]}")

ThreadCheckTracker.start()
print(f"tracker active: {ThreadCheckTracker._active}")

import importlib
try:
    test_mod = importlib.import_module("test_race")
    print(f"imported: {test_mod}")
except Exception as e:
    print(f"import failed: {e}")
    import traceback; traceback.print_exc()
    sys.exit(1)

import race_helpers as rh
has_tracker = hasattr(rh, "_threadcheck_tracker")
print(f"race_helpers has _threadcheck_tracker: {has_tracker}")
if not has_tracker:
    print("  HOOK FAILED!")
    spec = hook.find_spec("race_helpers", None, None)
    print(f"  find_spec: {spec}")
    print(f"  meta_path[0]: {type(sys.meta_path[0]).__name__}")
    sys.exit(1)

# Show instrumented source of the inc function
import ast, textwrap as _tw
_rh_source = Path(__file__).resolve().parent.parent.parent / "tmp_test_plugin" / "race_helpers.py"
_rh_text = _rh_source.read_text(encoding="utf-8")
from threadcheck.dynamic.transform import transform_source
_print_transformed = transform_source(_rh_text, str(_rh_source))
print("--- transformed source (first 30 lines) ---")
for _i, _line in enumerate(_print_transformed.splitlines()[:30]):
    print(f"  {_i+1}: {_line}")
print("--- end ---")

ThreadCheckTracker.reset_logs()
test_mod.test_race()
races = ThreadCheckTracker.detect_races()
print(f"races detected: {len(races)}")
for var, r1, r2 in races:
    print(f"  {var}: T{r1.thread_id} {r1.operation} vs T{r2.thread_id} {r2.operation}")

if not races:
    print(f"access_log: {dict((k, len(v)) for k, v in ThreadCheckTracker._access_log.items())}")
    print(f"thread_clocks: {list(ThreadCheckTracker._thread_clocks.keys())}")
    for var, recs in ThreadCheckTracker._access_log.items():
        all_tids = set(r.thread_id for r in recs)
        print(f"  thread_ids in '{var}': {len(all_tids)} unique ids: {all_tids}")
    # Plain threading test (no instrumentation)
    import threading as _th
    _plain_results = []
    _plain_lock = _th.Lock()
    _started_tids = []
    _started_nids = []
    def _plain_worker():
        with _plain_lock:
            _plain_results.append(_th.get_ident())
    _plain_threads = [_th.Thread(target=_plain_worker) for _ in range(3)]
    _started_tids = [t.ident for t in _plain_threads]
    for _t in _plain_threads:
        _t.start()
        _started_nids.append(_t.native_id)
    for _t in _plain_threads:
        _t.join()
    print(f"  before_start_tids: {_started_tids}", flush=True)
    print(f"  after_start_nids: {_started_nids}", flush=True)
    print(f"  after_join_results: {_plain_results}", flush=True)
    print(f"  unique_worker_tids: {set(_plain_results)}", flush=True)
    # Run without closures (top-level import approach)
    _simple_results2 = []
    def _simple_worker2():
        _simple_results2.append(1)
    _simple_threads2 = [_th.Thread(target=_simple_worker2) for _ in range(3)]
    for _t in _simple_threads2: _t.start()
    for _t in _simple_threads2: _t.join()
    print(f"  closure_worker_count: {len(_simple_results2)} values={_simple_results2}", flush=True)
    # Absolute simplest: function that takes no closures
    _worker3_results = []
    import builtins
    class _Worker3State:
        results = _worker3_results
    def _worker3():
        _Worker3State.results.append(_th.get_ident())
    _threads3 = [_th.Thread(target=_worker3) for _ in range(3)]
    for _t in _threads3: _t.start()
    for _t in _threads3: _t.join()
    print(f"  class_attr_results: {_worker3_results}", flush=True)

ThreadCheckTracker.reset()
uninstall_hook(hook)

# ═══════════════════════════════════════════════════════════════════
# Test B: subprocess pytest (like the real test)
# ═══════════════════════════════════════════════════════════════════
print("\n" + "=" * 60)
print("Test B: subprocess pytest (like test_plugin_detects_race)")
print("=" * 60)

# Clean up modules from Test A
for m in list(sys.modules.keys()):
    if m in ("test_race", "race_helpers"):
        sys.modules.pop(m, None)

result = subprocess.run(
    [sys.executable, "-m", "pytest", str(test_file), "-v", "-s", "--threadcheck"],
    capture_output=True, text=True, timeout=30,
    cwd=REPO,
)
print(f"returncode: {result.returncode}")
print(f"--- stdout ---")
sys.stdout.flush()
sys.stdout.write(result.stdout)
sys.stdout.flush()
if result.stderr:
    print(f"--- stderr ---")
    sys.stdout.flush()
    sys.stdout.write(result.stderr)
    sys.stdout.flush()

if result.returncode != 0:
    if "Data races detected" in result.stdout or "Data races detected" in result.stderr:
        print("\nSUCCESS: subprocess detected race!")
    else:
        print(f"\nSubprocess failed but no 'Data races detected'")
        if "Error" in result.stdout or "error" in result.stderr:
            print("  (possibly a pytest error)")
        sys.exit(1)
else:
    print("\nSUBPROCESS DID NOT DETECT RACE (exit 0)")
    sys.exit(1)

# ═══════════════════════════════════════════════════════════════════
print("\nAll tests passed!")
