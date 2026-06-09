"""Diagnose import hook pipeline on this Python version.

Tests:
1. Direct import through hook (proven to work)
2. Import via spec_from_file_location (mimics pytest import_path)
"""
import sys
import textwrap
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent  # repo root
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "src"))

print(f"Python: {sys.version}")

# ── prepare helpers ──────────────────────────────────────────────
tmp_dir = REPO / "tmp_diagnose"
tmp_dir.mkdir(exist_ok=True)

(new_module := tmp_dir / "diagnose_mod.py").write_text(
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

(new_test := tmp_dir / "test_diag.py").write_text(
    textwrap.dedent("""\
        import sys; print(f"[diag] sys.path={sys.path[:3]}", flush=True)
        print("[diag] importing diagnose_mod", flush=True)
        sys.path.insert(0, __file__ and str(type(__file__)))
        import diagnose_mod
        _h = hasattr(diagnose_mod, "_threadcheck_tracker")
        print(f"[diag] has_tracker={_h}", flush=True)
        def test_diag():
            diagnose_mod.run_racy()
    """),
    encoding="utf-8",
)

sys.path.insert(0, str(tmp_dir))

from threadcheck.dynamic.hook import install_hook, uninstall_hook
from threadcheck.dynamic.tracker import ThreadCheckTracker
import importlib.util


# ── Test A: direct import (like diagnose_hook did before) ────────
print("\n=== Test A: direct import through hook ===")
hook = install_hook(include_paths=[REPO])
try:
    ThreadCheckTracker.start()
    sys.path.insert(0, str(tmp_dir))
    import diagnose_mod
    ok = hasattr(diagnose_mod, "_threadcheck_tracker")
    print(f"  has _threadcheck_tracker: {ok}")
    if ok:
        diagnose_mod.run_racy()
        races = ThreadCheckTracker.detect_races()
        print(f"  races detected: {len(races)}")
    else:
        # fallback: check meta_path
        print(f"  sys.meta_path[0]: {type(sys.meta_path[0]).__name__}")
finally:
    ThreadCheckTracker.reset()
    uninstall_hook(hook)
    sys.modules.pop("diagnose_mod", None)


# ── Test B: import via spec_from_file_location (mimics pytest) ───
print("\n=== Test B: import via spec_from_file_location (pytest-style) ===")
hook = install_hook(include_paths=[REPO])
try:
    ThreadCheckTracker.start()

    # pytest adds test file's parent dir to sys.path
    sys.path.insert(0, str(tmp_dir))

    # pytest imports test file via spec_from_file_location
    spec = importlib.util.spec_from_file_location(
        "test_diag", str(new_test),
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["test_diag"] = mod
    spec.loader.exec_module(mod)

    # now check if diagnose_mod was instrumented
    diag_mod = sys.modules.get("diagnose_mod")
    if diag_mod is None:
        print("  diagnose_mod NOT in sys.modules (hook may not have been called)")
    else:
        ok = hasattr(diag_mod, "_threadcheck_tracker")
        print(f"  diagnose_mod has _threadcheck_tracker: {ok}")
        if ok:
            # run the test
            mod.test_diag()
            races = ThreadCheckTracker.detect_races()
            print(f"  races detected: {len(races)}")
            for var, r1, r2 in races:
                print(f"    {var}: T{r1.thread_id} {r1.operation} vs T{r2.thread_id} {r2.operation}")
        else:
            print("  hook did not instrument diagnose_mod!")
            print(f"  sys.meta_path[0]: {type(sys.meta_path[0]).__name__}")
finally:
    ThreadCheckTracker.reset()
    uninstall_hook(hook)
    for m in list(sys.modules.keys()):
        if m.startswith("diagnose_mod") or m.startswith("test_diag"):
            sys.modules.pop(m, None)


print("\n=== Done ===")
