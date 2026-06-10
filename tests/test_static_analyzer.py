from pathlib import Path

from threadcheck.static.analyzer import analyze_file, analyze_path
from threadcheck.static.models import WarningCategory, Confidence

FIXTURES = Path(__file__).parent / "fixtures"


def test_detect_global_race():
    warnings = analyze_file(FIXTURES / "simple_global.py")
    categories = {w.category for w in warnings}
    assert WarningCategory.UNSAFE_GLOBAL in categories


def test_detect_nonlocal_race():
    warnings = analyze_file(FIXTURES / "nonlocal_race.py")
    categories = {w.category for w in warnings}
    assert WarningCategory.UNSAFE_NONLOCAL in categories
    assert WarningCategory.THREAD_USAGE in categories


def test_detect_shared_mutable():
    warnings = analyze_file(FIXTURES / "shared_list.py")
    categories = {w.category for w in warnings}
    assert WarningCategory.SHARED_MUTABLE in categories


def test_detect_thread_usage():
    warnings = analyze_file(FIXTURES / "simple_global.py")
    categories = {w.category for w in warnings}
    assert WarningCategory.THREAD_USAGE in categories


def test_no_false_positive_local_only():
    warnings = analyze_file(FIXTURES / "no_race_simple.py")
    real_warnings = [w for w in warnings if w.severity.value == "warning"]
    assert len(real_warnings) == 0


def test_protected_global_suppressed():
    warnings = analyze_file(FIXTURES / "safe_with_lock.py")
    unsafe_global = [w for w in warnings if w.category == WarningCategory.UNSAFE_GLOBAL]
    assert len(unsafe_global) == 0


def test_protected_shared_mutable_suppressed():
    warnings = analyze_file(FIXTURES / "class_attribute_safe.py")
    shared_warnings = [w for w in warnings if w.category == WarningCategory.SHARED_MUTABLE]
    assert len(shared_warnings) == 0


def test_analyze_path_directory():
    warnings = analyze_path(str(FIXTURES))
    assert len(warnings) >= 4


def test_warning_fields():
    warnings = analyze_file(FIXTURES / "simple_global.py")
    w = next(w for w in warnings if w.category == WarningCategory.UNSAFE_GLOBAL)
    assert w.file.name == "simple_global.py"
    assert w.line > 0
    assert w.col >= 0
    assert w.severity.value == "warning"
    assert w.suggestion is not None


def test_confidence_global_race():
    warnings = analyze_file(FIXTURES / "simple_global.py")
    unsafe = [w for w in warnings if w.category == WarningCategory.UNSAFE_GLOBAL]
    assert len(unsafe) > 0
    assert all(w.confidence == Confidence.HIGH for w in unsafe)


def test_detect_class_attribute_race():
    warnings = analyze_file(FIXTURES / "class_race.py")
    categories = {w.category for w in warnings}
    assert WarningCategory.CLASS_ATTRIBUTE in categories


def test_protected_class_attribute_suppressed():
    warnings = analyze_file(FIXTURES / "class_safe.py")
    class_attr = [w for w in warnings if w.category == WarningCategory.CLASS_ATTRIBUTE]
    assert len(class_attr) == 0


def test_thread_subclass_detection():
    warnings = analyze_file(FIXTURES / "thread_subclass_race.py")
    categories = {w.category for w in warnings}
    assert WarningCategory.CLASS_ATTRIBUTE in categories


def test_confidence_class_in_thread():
    warnings = analyze_file(FIXTURES / "class_race.py")
    class_attr = [w for w in warnings if w.category == WarningCategory.CLASS_ATTRIBUTE]
    assert len(class_attr) > 0
    assert all(w.confidence == Confidence.HIGH for w in class_attr)


def test_global_race_is_high_confidence():
    warnings = analyze_file(FIXTURES / "simple_global.py")
    warns = [w for w in warnings if w.severity.value == "warning"]
    assert len(warns) > 0
    assert all(w.confidence == Confidence.HIGH for w in warns)


def test_confidence_nonlocal_race():
    warnings = analyze_file(FIXTURES / "nonlocal_race.py")
    nonlocal_warns = [w for w in warnings if w.category == WarningCategory.UNSAFE_NONLOCAL]
    assert len(nonlocal_warns) > 0
    assert all(w.confidence == Confidence.HIGH for w in nonlocal_warns)


def test_cross_module_race_detected():
    """Thread target in one file, function in another — should detect race with HIGH confidence."""
    from threadcheck.static.analyzer import _collect_thread_targets, analyze_file

    main = FIXTURES / "cross_module_main.py"
    worker = FIXTURES / "cross_module_worker.py"
    files = [main, worker]
    global_targets = _collect_thread_targets(files)
    assert "run" in global_targets, f"Expected 'run' in targets, got {global_targets}"

    warnings = analyze_file(worker, global_targets)
    categories = {w.category for w in warnings}
    assert WarningCategory.UNSAFE_GLOBAL in categories, (
        f"Expected UNSAFE_GLOBAL in worker, got {categories}"
    )
    unsafe = [w for w in warnings if w.category == WarningCategory.UNSAFE_GLOBAL]
    assert all(w.confidence == Confidence.HIGH for w in unsafe)


def test_nested_locks_suppress_global_race():
    warnings = analyze_file(FIXTURES / "nested_locks.py")
    unsafe_global = [w for w in warnings if w.category == WarningCategory.UNSAFE_GLOBAL]
    assert len(unsafe_global) == 0, (
        f"Expected 0 UNSAFE_GLOBAL warnings with nested locks, got {len(unsafe_global)}"
    )


def test_executor_submit_target_detected():
    """executor.submit(func) should extract func as a thread target."""
    warnings = analyze_file(FIXTURES / "futures_race.py")
    categories = {w.category for w in warnings}
    assert WarningCategory.UNSAFE_GLOBAL in categories, (
        f"Expected UNSAFE_GLOBAL for futures_race, got {categories}"
    )
    unsafe = [w for w in warnings if w.category == WarningCategory.UNSAFE_GLOBAL]
    assert all(w.confidence == Confidence.HIGH for w in unsafe)


def test_inline_ignore_suppresses_line():
    """# threadcheck: ignore on a line should suppress that warning."""
    warnings = analyze_file(FIXTURES / "inline_ignore.py")
    unsafe = [w for w in warnings if w.category == WarningCategory.UNSAFE_GLOBAL]
    unsafe_lines = {w.line for w in unsafe}
    assert 9 not in unsafe_lines, "Line with `# threadcheck: ignore` was not suppressed"
    assert 20 in unsafe_lines, "Line without ignore was incorrectly suppressed"


def test_protected_by_manual_lock():
    """lock.acquire()/release() should suppress UNSAFE_GLOBAL between them."""
    warnings = analyze_file(FIXTURES / "manual_lock.py")
    unsafe = [w for w in warnings if w.category == WarningCategory.UNSAFE_GLOBAL]
    unsafe_lines = {w.line for w in unsafe}
    assert 10 not in unsafe_lines, "Line inside manual acquire/release was not protected"
    assert 16 in unsafe_lines, "Line outside lock was incorrectly protected"


def test_inline_ignore_region():
    """# threadcheck: ignore-start/ignore-end should suppress all lines in range."""
    warnings = analyze_file(FIXTURES / "inline_ignore.py")
    unsafe = [w for w in warnings if w.category == WarningCategory.UNSAFE_GLOBAL]
    unsafe_lines = {w.line for w in unsafe}
    assert 26 not in unsafe_lines, "Line inside ignore region was not suppressed"
    assert 32 in unsafe_lines, "Line after ignore region was incorrectly suppressed"
