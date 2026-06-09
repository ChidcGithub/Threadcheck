import pytest

from .dynamic.hook import install_hook, uninstall_hook
from .dynamic.tracker import ThreadCheckTracker

_hook_instance = None


def pytest_addoption(parser):
    group = parser.getgroup("threadcheck")
    group.addoption(
        "--threadcheck",
        action="store_true",
        default=False,
        help="Run dynamic race detection via AST instrumentation",
    )


def pytest_configure(config):
    global _hook_instance
    if config.getoption("--threadcheck"):
        _hook_instance = install_hook(include_paths=[config.rootpath])
        ThreadCheckTracker.start()
        import sys
        print(f"[threadcheck] hook installed, rootpath={config.rootpath}", flush=True)
        print(f"[threadcheck] include_paths={[str(p) for p in _hook_instance._include_paths]}", flush=True)


def pytest_unconfigure(config):
    global _hook_instance
    if config.getoption("--threadcheck"):
        ThreadCheckTracker.stop()
        if _hook_instance is not None:
            uninstall_hook(_hook_instance)
            _hook_instance = None


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item):
    if item.config.getoption("--threadcheck"):
        ThreadCheckTracker.reset_logs()
    yield
    if item.config.getoption("--threadcheck"):
        races = ThreadCheckTracker.detect_races()
        if races:
            item._threadcheck_race_report = ThreadCheckTracker.format_races()
        ThreadCheckTracker.reset_logs()


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    if call.when == "call" and not call.excinfo:
        report = getattr(item, "_threadcheck_race_report", None)
        if report:
            from _pytest._code import ExceptionInfo
            try:
                raise pytest.fail.Exception(report)
            except pytest.fail.Exception:
                call.excinfo = ExceptionInfo.from_current()
    yield
