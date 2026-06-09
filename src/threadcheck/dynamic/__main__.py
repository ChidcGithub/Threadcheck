import ast
import sys
from pathlib import Path

from .tracker import ThreadCheckTracker
from .transform import TrackInjector
from ..reporting.formatter import format_dynamic_races, format_dynamic_json


def run_script(script_path: str, output_format: str = "text"):
    path = Path(script_path).resolve()
    if not path.exists():
        print(f"File not found: {path}", file=sys.stderr)
        sys.exit(1)

    source = path.read_text(encoding="utf-8")
    filename = str(path)

    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError as e:
        print(f"Syntax error: {e}", file=sys.stderr)
        sys.exit(1)

    TrackInjector(filename=filename).transform(tree)
    ast.fix_missing_locations(tree)

    code = compile(tree, filename, "exec")

    ThreadCheckTracker.start()
    try:
        exec(code, {"_threadcheck_tracker": ThreadCheckTracker, "__file__": filename})
    except SystemExit:
        pass
    finally:
        ThreadCheckTracker.stop()

    races = ThreadCheckTracker.detect_races()
    with ThreadCheckTracker._lock:
        alog = dict(ThreadCheckTracker._access_log)

    if output_format == "json":
        print(format_dynamic_json(races))
    else:
        print(format_dynamic_races(races, alog))

    ThreadCheckTracker.reset()
    return len(races) > 0
