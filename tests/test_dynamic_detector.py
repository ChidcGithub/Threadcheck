import ast
from pathlib import Path

from threadcheck.dynamic.tracker import ThreadCheckTracker
from threadcheck.dynamic.transform import TrackInjector, transform_source

FIXTURES = Path(__file__).parent / "fixtures"


def test_transform_is_valid_python():
    source = (FIXTURES / "dynamic_race.py").read_text(encoding="utf-8")
    result = transform_source(source, str(FIXTURES / "dynamic_race.py"))
    try:
        ast.parse(result)
    except SyntaxError as e:
        assert False, f"转换后语法错误: {e}"


def test_transform_injects_write_before():
    source = (FIXTURES / "dynamic_race.py").read_text(encoding="utf-8")
    result = transform_source(source, str(FIXTURES / "dynamic_race.py"))
    assert "_threadcheck_tracker.write_before" in result


def test_transform_injects_lock_acquire():
    source = (FIXTURES / "dynamic_safe.py").read_text(encoding="utf-8")
    result = transform_source(source, str(FIXTURES / "dynamic_safe.py"))
    assert "_threadcheck_tracker.lock_acquire" in result
    assert "_threadcheck_tracker.lock_release" in result


def _exec_in_module(code, filename):
    """Execute compiled code in a synthetic module so that defined
    functions always have the correct ``__globals__``."""
    import sys
    import types

    mod = types.ModuleType("_test_dynamic_module")
    mod.__file__ = filename
    mod._threadcheck_tracker = ThreadCheckTracker
    sys.modules["_test_dynamic_module"] = mod
    try:
        exec(code, mod.__dict__)
    finally:
        sys.modules.pop("_test_dynamic_module", None)


def test_detect_race_dynamic():
    source = (FIXTURES / "dynamic_race.py").read_text(encoding="utf-8")
    filename = str(FIXTURES / "dynamic_race.py")

    tree = ast.parse(source, filename=filename)
    TrackInjector(filename=filename).transform(tree)
    ast.fix_missing_locations(tree)
    code = compile(tree, filename, "exec")

    ThreadCheckTracker.start()
    try:
        _exec_in_module(code, filename)
    finally:
        ThreadCheckTracker.stop()

    races = ThreadCheckTracker.detect_races()
    assert len(races) > 0, "应该检测到 data race"

    ThreadCheckTracker.reset()


def test_no_race_when_locked():
    source = (FIXTURES / "dynamic_safe.py").read_text(encoding="utf-8")
    filename = str(FIXTURES / "dynamic_safe.py")

    tree = ast.parse(source, filename=filename)
    TrackInjector(filename=filename).transform(tree)
    ast.fix_missing_locations(tree)
    code = compile(tree, filename, "exec")

    ThreadCheckTracker.start()
    try:
        _exec_in_module(code, filename)
    finally:
        ThreadCheckTracker.stop()

    races = ThreadCheckTracker.detect_races()
    assert len(races) == 0, "有锁保护时不应该检测到 data race"

    ThreadCheckTracker.reset()
