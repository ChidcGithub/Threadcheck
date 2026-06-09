"""Diagnose import hook pipeline on this Python version."""

import sys
import textwrap
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent  # repo root
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "src"))

print(f"Python: {sys.version}")
print(f"sys.path[0]: {sys.path[0]}")
print(f"sys.path[1]: {sys.path[1]}")

# Step 1: create a helper module
tmp_dir = REPO / "tmp_diagnose"
tmp_dir.mkdir(exist_ok=True)
helper = tmp_dir / "diagnose_mod.py"
helper.write_text(
    textwrap.dedent("""\
        import threading
        counter = 0
        def run_racy():
            global counter
            def inc():
                global counter
                for _ in range(50):
                    counter += 1
            threads = [threading.Thread(target=inc) for _ in range(2)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
    """),
    encoding="utf-8",
)

# Step 2: install hook
sys.path.insert(0, str(tmp_dir))
from threadcheck.dynamic.hook import install_hook, uninstall_hook, ThreadCheckFinder, ThreadCheckLoader
from threadcheck.dynamic.tracker import ThreadCheckTracker

hook = install_hook(include_paths=[REPO])
print(f"\n--- Hook installed: {type(hook).__name__} ---")
print(f"include_paths: {[str(p) for p in hook._include_paths]}")
print(f"sys.meta_path[0]: {type(sys.meta_path[0]).__name__}")

# Step 3: check _should_instrument
print(f"\n--- _should_instrument ---")
for p in [helper, REPO / "setup.py", REPO / "tmp_diagnose" / "nonexistent.py"]:
    exists = p.exists()
    should = hook._should_instrument(p)
    print(f"  {p} exists={exists} should_instrument={should}")

# Step 4: try import through hook
print(f"\n--- Import through hook ---")
print(f"  Calling find_spec('diagnose_mod', None, None)")
spec = hook.find_spec("diagnose_mod", None, None)
if spec is None:
    print("  find_spec returned None!")
else:
    print(f"  spec.name: {spec.name}")
    print(f"  spec.origin: {spec.origin}")
    print(f"  spec.loader: {type(spec.loader).__name__}")
    print(f"  spec.has_location: {spec.has_location}")
    if hasattr(spec, "_set_fileattr"):
        print(f"  spec._set_fileattr: {spec._set_fileattr}")

# Step 5: load module through importlib
print(f"\n--- Full import ---")
import importlib.util
mod = importlib.util.module_from_spec(spec)
sys.modules["diagnose_mod"] = mod
print(f"  module created: {type(mod).__name__}")
print(f"  module.__file__ before exec_module: {mod.__file__}")
print(f"  module.__dict__ keys before: {[k for k in mod.__dict__.keys() if not k.startswith('__')]}")

ThreadCheckTracker.start()
try:
    spec.loader.exec_module(mod)
    print(f"  module.__file__ after exec_module: {mod.__file__}")
    print(f"  module has _threadcheck_tracker: {'_threadcheck_tracker' in mod.__dict__}")
    if "_threadcheck_tracker" in mod.__dict__:
        t = mod.__dict__["_threadcheck_tracker"]
        print(f"  tracker type: {type(t).__name__}")
        print(f"  tracker is ThreadCheckTracker class: {t is ThreadCheckTracker}")
        print(f"  ThreadCheckTracker._active: {ThreadCheckTracker._active}")
    print(f"  module has run_racy: {hasattr(mod, 'run_racy')}")

    # Step 6: run the race
    print(f"\n--- Run race ---")
    ThreadCheckTracker.reset_logs()
    mod.run_racy()
    races = ThreadCheckTracker.detect_races()
    print(f"  races detected: {len(races)}")
    for var, r1, r2 in races:
        loc1 = f"{r1.location[0]}:{r1.location[1]}"
        loc2 = f"{r2.location[0]}:{r2.location[1]}"
        print(f"  race: {var} (T{r1.thread_id} {r1.operation}@{loc1} vs T{r2.thread_id} {r2.operation}@{loc2})")
    if not races:
        print(f"  access_log keys: {list(ThreadCheckTracker._access_log.keys())}")
        for var, recs in ThreadCheckTracker._access_log.items():
            print(f"  {var}: {len(recs)} records")
            for r in recs[:5]:
                print(f"    T{r.thread_id} {r.operation} @{r.location}")
finally:
    ThreadCheckTracker.stop()
    ThreadCheckTracker.reset()
    uninstall_hook(hook)

print(f"\n--- Done ---")
