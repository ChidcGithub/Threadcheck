import ast
import os
import subprocess
import sys
import tempfile
import threading
from pathlib import Path

from threadcheck.dynamic.tracker import ThreadCheckTracker
from threadcheck.dynamic.transform import TrackInjector, transform_source

FIXTURES = Path(__file__).parent / "fixtures"
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_transform_is_valid_python():
    source = (FIXTURES / "dynamic_race.py").read_text(encoding="utf-8")
    result = transform_source(source, str(FIXTURES / "dynamic_race.py"))
    try:
        ast.parse(result)
    except SyntaxError as e:
        assert False, f"Syntax error after transform: {e}"


def test_transform_injects_write_before():
    source = (FIXTURES / "dynamic_race.py").read_text(encoding="utf-8")
    result = transform_source(source, str(FIXTURES / "dynamic_race.py"))
    assert "_threadcheck_tracker.write_before" in result


def test_transform_injects_lock_acquire():
    source = (FIXTURES / "dynamic_safe.py").read_text(encoding="utf-8")
    result = transform_source(source, str(FIXTURES / "dynamic_safe.py"))
    assert "_threadcheck_tracker.lock_acquire" in result
    assert "_threadcheck_tracker.lock_release" in result


def _run_transformed_fixture(fixture_name: str) -> int:
    source = (FIXTURES / fixture_name).read_text(encoding="utf-8")
    filename = str(FIXTURES / fixture_name)

    tree = ast.parse(source, filename=filename)
    TrackInjector(filename=filename).transform(tree)
    ast.fix_missing_locations(tree)

    # Inject the tracker import at the top so that ``_threadcheck_tracker``
    # is a proper module-level global. Functions defined in this module will
    # resolve it via ``__globals__`` even when running in child threads.
    preamble = (
        "import sys\n"
        f"sys.path.insert(0, {str(PROJECT_ROOT)!r})\n"
        "from threadcheck.dynamic.tracker import ThreadCheckTracker\n"
        "_threadcheck_tracker = ThreadCheckTracker\n"
    )
    body = ast.unparse(tree)
    full_source = preamble + body

    with tempfile.NamedTemporaryFile(
        suffix=".py", delete=False, mode="w", encoding="utf-8"
    ) as f:
        f.write(full_source)
        temp_path = f.name

    runner = (
        f"import sys; sys.path.insert(0, {str(PROJECT_ROOT)!r})\n"
        "from threadcheck.dynamic.tracker import ThreadCheckTracker\n"
        f"import importlib.util\n"
        f"spec = importlib.util.spec_from_file_location('_test_fixture', {temp_path!r})\n"
        f"mod = importlib.util.module_from_spec(spec)\n"
        f"sys.modules['_test_fixture'] = mod\n"
        "ThreadCheckTracker.start()\n"
        "try:\n"
        "    spec.loader.exec_module(mod)\n"
        "finally:\n"
        "    ThreadCheckTracker.stop()\n"
        "print(len(ThreadCheckTracker.detect_races()))\n"
        "ThreadCheckTracker.reset()\n"
    )

    try:
        result = subprocess.run(
            [sys.executable, "-c", runner],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"Subprocess failed:\nstdout:{result.stdout}\nstderr:{result.stderr}"
            )
        return int(result.stdout.strip())
    finally:
        os.unlink(temp_path)


def test_detect_race_dynamic():
    count = _run_transformed_fixture("dynamic_race.py")
    assert count > 0, f"Expected races > 0, got {count}"


def test_no_race_when_locked():
    count = _run_transformed_fixture("dynamic_safe.py")
    assert count == 0, f"Expected 0 races, got {count}"


def test_tracker_direct_race_detection():
    ThreadCheckTracker.start()

    def worker():
        ThreadCheckTracker.write_before("x", "test.py", 1)

    threads = [threading.Thread(target=worker) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    ThreadCheckTracker.stop()
    races = ThreadCheckTracker.detect_races()
    assert len(races) > 0, "Expected races from direct tracker calls"
    ThreadCheckTracker.reset()


def test_tracker_no_race_same_thread():
    ThreadCheckTracker.start()

    ThreadCheckTracker.write_before("x", "test.py", 1)
    ThreadCheckTracker.write_before("x", "test.py", 2)

    ThreadCheckTracker.stop()
    races = ThreadCheckTracker.detect_races()
    assert len(races) == 0, "Same-thread accesses should not race"
    ThreadCheckTracker.reset()
