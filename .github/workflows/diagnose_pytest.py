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

ThreadCheckTracker.reset_logs()
test_mod.test_race()
races = ThreadCheckTracker.detect_races()
print(f"races detected: {len(races)}")
for var, r1, r2 in races:
    print(f"  {var}: T{r1.thread_id} {r1.operation} vs T{r2.thread_id} {r2.operation}")

if not races:
    print(f"access_log: {dict((k, len(v)) for k, v in ThreadCheckTracker._access_log.items())}")
    print(f"thread_clocks: {list(ThreadCheckTracker._thread_clocks.keys())}")

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
