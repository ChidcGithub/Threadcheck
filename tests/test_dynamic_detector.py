import ast
import os
import subprocess
import sys
import tempfile
from pathlib import Path

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


def _run_transformed_fixture(fixture_name: str) -> tuple[int, str, str]:
    source = (FIXTURES / fixture_name).read_text(encoding="utf-8")
    filename = str(FIXTURES / fixture_name)

    tree = ast.parse(source, filename=filename)
    TrackInjector(filename=filename).transform(tree)
    ast.fix_missing_locations(tree)

    # Write the transformed source to a temp file. The preamble makes
    # ``_threadcheck_tracker`` available as a regular module-level global.
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

    # The runner injects ``_threadcheck_tracker`` into builtins so that
    # functions executing in child threads can always resolve the name
    # regardless of how ``exec_module`` sets up ``__globals__``.
    runner = (
        f"import sys; sys.path.insert(0, {str(PROJECT_ROOT)!r})\n"
        "from threadcheck.dynamic.tracker import ThreadCheckTracker\n"
        "import builtins\n"
        "builtins._threadcheck_tracker = ThreadCheckTracker\n"
        f"import importlib.util\n"
        f"spec = importlib.util.spec_from_file_location('_test_fixture', {temp_path!r})\n"
        f"mod = importlib.util.module_from_spec(spec)\n"
        f"mod._threadcheck_tracker = ThreadCheckTracker\n"
        f"sys.modules['_test_fixture'] = mod\n"
        "import threading, traceback\n"
        "def _thread_hook(args):\n"
        "    traceback.print_exception(args.exc_type, args.exc_value, args.exc_tb)\n"
        "threading.excepthook = _thread_hook\n"
        "ThreadCheckTracker.start()\n"
        "try:\n"
        "    spec.loader.exec_module(mod)\n"
        "finally:\n"
        "    ThreadCheckTracker.stop()\n"
        "count = len(ThreadCheckTracker.detect_races())\n"
        "print(f'DIAG: python={{sys.version}}')\n"
        "print(f'RACES:{count}')\n"
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
        lines = result.stdout.strip().splitlines()
        count_line = next((l for l in lines if l.startswith("RACES:")), "RACES:0")
        count = int(count_line.split(":", 1)[1])
        return count, result.stdout, result.stderr
    finally:
        os.unlink(temp_path)


def test_detect_race_dynamic():
    count, stdout, stderr = _run_transformed_fixture("dynamic_race.py")
    assert count > 0, (
        f"Expected races > 0, got {count}\n"
        f"--- stdout ---\n{stdout}\n--- stderr ---\n{stderr}"
    )


def test_no_race_when_locked():
    count, _, _ = _run_transformed_fixture("dynamic_safe.py")
    assert count == 0, f"Expected 0 races, got {count}"
