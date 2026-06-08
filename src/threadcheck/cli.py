import argparse
import json
import sys
from pathlib import Path

from .static.analyzer import analyze_path
from .reporting.formatter import format_report
from .dynamic.__main__ import run_script


def main():
    parser = argparse.ArgumentParser(
        prog="threadcheck",
        description="Python 并发竞态检测器 (Data Race Detector)",
        epilog="更多信息: https://github.com/your-username/threadcheck",
    )

    parser.add_argument(
        "--version", action="version", version=f"threadcheck 0.1.0"
    )

    sub = parser.add_subparsers(dest="command", required=True)

    scan = sub.add_parser("scan", help="静态分析代码中的竞态条件")
    scan.add_argument("path", help="文件或目录路径")
    scan.add_argument("--json", action="store_true", help="以 JSON 格式输出")
    scan.add_argument("-o", "--output", help="输出到文件 (默认 stdout)")

    run = sub.add_parser("run", help="动态检测竞态条件 (Phase 3)")
    run.add_argument("script", help="要执行的 Python 脚本")

    compat = sub.add_parser("check-compat", help="检查 Free-Threading 兼容性 (Phase 7)")
    compat.add_argument("path", nargs="?", default=".", help="项目路径")

    args = parser.parse_args()

    if args.command == "scan":
        _do_scan(args)
    elif args.command == "run":
        run_script(args.script)
    elif args.command == "check-compat":
        print("尚未实现: Free-Threading 兼容检查 (Phase 7)", file=sys.stderr)
        sys.exit(1)


def _do_scan(args):
    path = Path(args.path).resolve()
    if not path.exists():
        print(f"路径不存在: {path}", file=sys.stderr)
        sys.exit(1)

    print(f"threadcheck scan -- 分析 {path}")
    print()

    warnings = analyze_path(str(path))

    total = len(warnings)
    errors = sum(1 for w in warnings if w.severity.value == "error")
    warns = sum(1 for w in warnings if w.severity.value == "warning")
    infos = sum(1 for w in warnings if w.severity.value == "info")

    if args.json:
        output = json.dumps(
            [w.to_dict() for w in warnings], indent=2, ensure_ascii=False
        )
        if args.output:
            Path(args.output).write_text(output, encoding="utf-8")
        else:
            print(output)
    else:
        text = format_report(warnings)
        if args.output:
            Path(args.output).write_text(text, encoding="utf-8")
        else:
            print(text)

    print()
    print(f"总计: {total} 个问题 (错误 {errors}, 警告 {warns}, 信息 {infos})")


if __name__ == "__main__":
    main()
