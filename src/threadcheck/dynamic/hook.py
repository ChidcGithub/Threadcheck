import sys
import ast
import importlib.util
import importlib.abc
from pathlib import Path

from .transform import TrackInjector
from .tracker import ThreadCheckTracker


class ThreadCheckLoader(importlib.abc.Loader):
    def __init__(self, tracker=None):
        self.tracker = tracker or ThreadCheckTracker

    def create_module(self, spec):
        return None

    def exec_module(self, module):
        spec = module.__spec__
        source = self._get_source(spec)
        if source is None:
            raise ImportError(f"cannot load source for {spec.name}")

        tree = ast.parse(source, filename=spec.origin)
        TrackInjector(filename=str(spec.origin)).transform(tree)
        ast.fix_missing_locations(tree)

        code = compile(tree, spec.origin, "exec")
        globals_dict = module.__dict__
        globals_dict["_threadcheck_tracker"] = self.tracker
        exec(code, globals_dict)

    @staticmethod
    def _get_source(spec):
        if spec.origin and Path(spec.origin).suffix == ".py":
            try:
                return Path(spec.origin).read_text(encoding="utf-8")
            except Exception:
                return None
        if hasattr(spec.loader, "get_source"):
            try:
                return spec.loader.get_source(spec.name)
            except Exception:
                return None
        return None


class ThreadCheckFinder(importlib.abc.MetaPathFinder):
    def __init__(self, tracker=None, include_paths=None):
        self.tracker = tracker or ThreadCheckTracker
        self._include_paths = (
            [Path(p).resolve() for p in include_paths] if include_paths else []
        )

    def _should_instrument(self, filepath: Path) -> bool:
        if not self._include_paths:
            return True
        resolved = filepath.resolve()
        return any(_is_under(resolved, inc) for inc in self._include_paths)

    def find_spec(self, fullname, path, target=None):
        for entry in (path or sys.path):
            if entry == "":
                entry = "."
            base = Path(entry) / f"{fullname.replace('.', '/')}.py"
            if base.exists() and self._should_instrument(base):
                spec = importlib.util.spec_from_file_location(
                    fullname,
                    str(base),
                    loader=ThreadCheckLoader(self.tracker),
                )
                return spec
        return None


def install_hook(tracker=None, include_paths=None):
    hook = ThreadCheckFinder(tracker, include_paths)
    sys.meta_path.insert(0, hook)
    return hook


def uninstall_hook(hook):
    if hook in sys.meta_path:
        sys.meta_path.remove(hook)


def _is_under(child: Path, parent: Path) -> bool:
    try:
        child.relative_to(parent)
        return True
    except ValueError:
        return False
