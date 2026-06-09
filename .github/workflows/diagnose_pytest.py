"""Diagnose the full pytest plugin flow directly (not in subprocess)."""
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

sys.path.insert(0, str(tmp_dir))

# ── 2. Install hook & start tracker (like pytest_configure) ──────
from threadcheck.dynamic.hook import install_hook, uninstall_hook
from threadcheck.dynamic.tracker import ThreadCheckTracker

rootpath = REPO
hook = install_hook(include_paths=[rootpath])
print(f"\ninclude_paths: {[str(p) for p in hook._include_paths]}")

ThreadCheckTracker.start()
print(f"tracker active: {ThreadCheckTracker._active}")

# ── 3. Import test module (like collection, via importlib.import_module) ──
import importlib

print(f"\nsys.path before import: {[p for p in sys.path if 'tmp_test' in p]}")

try:
    test_mod = importlib.import_module("test_race")
    print(f"imported: {test_mod}")
    print(f"test_race module __file__: {test_mod.__file__}")
except Exception as e:
    print(f"import failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# ── 4. Check if race_helpers was instrumented ────────────────────
import race_helpers as rh
has_tracker = hasattr(rh, "_threadcheck_tracker")
print(f"\nrace_helpers has _threadcheck_tracker: {has_tracker}")
if has_tracker:
    print(f"  type: {type(rh.__dict__['_threadcheck_tracker']).__name__}")
else:
    print("  HOOK FAILED TO INSTRUMENT race_helpers!")
    print(f"  sys.meta_path[0]: {type(sys.meta_path[0]).__name__}")
    print(f"  checking find_spec...")
    spec = hook.find_spec("race_helpers", None, None)
    print(f"  find_spec returned: {spec}")
    if spec:
        print(f"    loader: {type(spec.loader).__name__}")
        print(f"    origin: {spec.origin}")
    sys.exit(1)

# ── 5. Run the test (like pytest_runtest_call) ───────────────────
print(f"\n--- Running test ---")
ThreadCheckTracker.reset_logs()

# Actually call the test function
test_mod.test_race()

races = ThreadCheckTracker.detect_races()
print(f"races detected: {len(races)}")
for var, r1, r2 in races:
    print(f"  {var}: T{r1.thread_id} {r1.operation} vs T{r2.thread_id} {r2.operation}")

if not races:
    # Debug: check access log
    print(f"  access_log: {dict((k, len(v)) for k, v in ThreadCheckTracker._access_log.items())}")
    print(f"  thread_clocks: {list(ThreadCheckTracker._thread_clocks.keys())}")
else:
    print(f"\nSUCCESS: race detected as expected!")

# ── 6. Cleanup ───────────────────────────────────────────────────
ThreadCheckTracker.reset()
uninstall_hook(hook)
