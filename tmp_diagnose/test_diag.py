import sys; print(f"[diag] sys.path={sys.path[:3]}", flush=True)
print("[diag] importing diagnose_mod", flush=True)
sys.path.insert(0, __file__ and str(type(__file__)))
import diagnose_mod
_h = hasattr(diagnose_mod, "_threadcheck_tracker")
print(f"[diag] has_tracker={_h}", flush=True)
def test_diag():
    diagnose_mod.run_racy()
