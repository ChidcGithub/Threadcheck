import subprocess
import sys
import textwrap
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _run_pytest(test_name: str, code: str, extra_args: list[str] | None = None) -> subprocess.CompletedProcess:
    test_dir = PROJECT_ROOT / "tmp_test_plugin"
    test_dir.mkdir(exist_ok=True)
    test_file = test_dir / test_name
    test_file.write_text(textwrap.dedent(code), encoding="utf-8")
    args = [sys.executable, "-m", "pytest", str(test_file), "-v"]
    if extra_args:
        args.extend(extra_args)
    result = subprocess.run(
        args,
        capture_output=True,
        text=True,
        cwd=PROJECT_ROOT,
        timeout=30,
    )
    return result


def test_plugin_detects_race():
    helper = PROJECT_ROOT / "tmp_test_plugin" / "race_helpers.py"
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
    result = _run_pytest(
        "test_race.py",
        """\
        from race_helpers import run_racy_increment

        def test_race():
            run_racy_increment()
        """,
        extra_args=["--threadcheck"],
    )
    assert result.returncode != 0, (
        f"Expected test to fail due to data race.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
    assert "Data races detected" in result.stdout or "Data races detected" in result.stderr, (
        f"Expected 'Data races detected' in output.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


def test_plugin_no_race_when_locked():
    helper = PROJECT_ROOT / "tmp_test_plugin" / "safe_helpers.py"
    helper.write_text(
        textwrap.dedent("""\
            import threading

            counter = 0
            lock = threading.Lock()

            def run_safe_increment():
                global counter
                threads = []
                def inc():
                    global counter
                    for _ in range(50):
                        with lock:
                            counter += 1
                for _ in range(3):
                    t = threading.Thread(target=inc)
                    t.start()
                    threads.append(t)
                for t in threads:
                    t.join()
                return counter
        """),
        encoding="utf-8",
    )
    result = _run_pytest(
        "test_safe.py",
        """\
        from safe_helpers import run_safe_increment

        def test_safe():
            val = run_safe_increment()
            assert val == 150
        """,
        extra_args=["--threadcheck"],
    )
    assert result.returncode == 0, (
        f"Expected test to pass (lock-protected).\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


def test_plugin_inactive_without_flag():
    helper = PROJECT_ROOT / "tmp_test_plugin" / "race_helpers_noflag.py"
    helper.write_text(
        textwrap.dedent("""\
            import threading

            counter = 0

            def run_racy():
                global counter
                def inc():
                    global counter
                    for _ in range(10):
                        counter += 1
                threads = [threading.Thread(target=inc) for _ in range(2)]
                for t in threads:
                    t.start()
                for t in threads:
                    t.join()
        """),
        encoding="utf-8",
    )
    result = _run_pytest(
        "test_no_flag.py",
        """\
        from race_helpers_noflag import run_racy

        def test_no_flag():
            run_racy()
        """,
    )
    assert result.returncode == 0, (
        f"Expected test to pass without --threadcheck.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )
