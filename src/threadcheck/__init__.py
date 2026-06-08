"""
threadcheck — Python 并发竞态检测器

检测多线程代码中的 data race (竞态条件)，
支持 AST 静态分析和运行时动态检测。

Python 3.14+ Free-Threading 专用工具。
"""

from ._version import __version__

from .static.analyzer import analyze_path, analyze_file
from .static.models import RaceWarning, Severity, WarningCategory
