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


def _helper_path(name: str) -> Path:
    d = PROJECT_ROOT / "tmp_test_plugin"
    d.mkdir(exist_ok=True)
    return d / name


def test_plugin_detects_race():
    helper = _helper_path("race_helpers.py")
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
        """,
        extra_args=["--threadcheck", "-s"],
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
    helper = _helper_path("safe_helpers.py")
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


def test_hook_includes_path():
    """Verify that include_paths filtering does not block files under rootpath."""
    mod = _helper_path("dummy_mod.py")
    mod.write_text("SENTINEL = 42\n", encoding="utf-8")
    runner = _helper_path("check_hook.py")
    runner.write_text(
        textwrap.dedent(f"""\
            import sys, os
            sys.path.insert(0, {str(mod.parent)!r})
            from threadcheck.dynamic.hook import install_hook, uninstall_hook
            from pathlib import Path
            install_hook(include_paths=[Path({str(PROJECT_ROOT)!r})])

            # Attempt import via the hook
            import dummy_mod
            ok = hasattr(dummy_mod, "_threadcheck_tracker")
            if not ok:
                # Fallback: import via default PathFinder (our hook rejected it)
                # Remove our hook from meta_path and check if import works
                print("HOOK_IMPORT_FAILED", flush=True)
                print(f"sys.meta_path[0]={{type(sys.meta_path[0]).__name__}}", flush=True)
                import importlib
                spec = importlib.util.spec_from_file_location(
                    "dummy_mod2", {str(mod)!r}
                )
                if spec:
                    print(f"spec.origin={{spec.origin}}", flush=True)
                # Check sys.path
                print(f"sys.path[0]={{sys.path[0]}}", flush=True)

            uninstall_hook(sys.meta_path[0] if sys.meta_path else None)
            sys.exit(0 if ok else 1)
        """),
        encoding="utf-8",
    )
    result = subprocess.run(
        [sys.executable, str(runner)],
        capture_output=True, text=True, timeout=10,
    )
    print(f"[debug] hook_includes_path stdout:\n{result.stdout}")
    print(f"[debug] hook_includes_path stderr:\n{result.stderr}")
    assert result.returncode == 0, (
        f"Hook did not inject _threadcheck_tracker into helper module.\n"
        f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    )


def test_plugin_inactive_without_flag():
    helper = _helper_path("race_helpers_noflag.py")
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
