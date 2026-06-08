import ast
import sys
from pathlib import Path

from .tracker import ThreadCheckTracker
from .transform import TrackInjector


def run_script(script_path: str):
    path = Path(script_path).resolve()
    if not path.exists():
        print(f"文件不存在: {path}", file=sys.stderr)
        sys.exit(1)

    source = path.read_text(encoding="utf-8")
    filename = str(path)

    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError as e:
        print(f"语法错误: {e}", file=sys.stderr)
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

    print(ThreadCheckTracker.format_races())
    ThreadCheckTracker.reset()
