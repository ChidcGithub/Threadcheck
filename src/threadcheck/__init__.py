"""
threadcheck — Data-race detector for multi-threaded Python.

Supports both AST-based static analysis and runtime dynamic
detection via bytecode instrumentation.

Targets Python 3.14+ free-threading builds.
"""

from ._version import __version__

from .static.analyzer import analyze_path, analyze_file
from .static.models import RaceWarning, Severity, WarningCategory
