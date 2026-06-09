from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import IO


@dataclass
class LineSuppression:
    file_pattern: str
    start_line: int
    end_line: int


@dataclass
class ThreadCheckConfig:
    project_root: Path = Path(".")
    ignore_patterns: list[str] = field(default_factory=list)
    line_suppressions: list[LineSuppression] = field(default_factory=list)
    verbose: bool = False
    quiet: bool = False

    @classmethod
    def load(cls, project_root: Path) -> ThreadCheckConfig:
        cfg = cls(project_root=project_root)
        cfg._merge_pyproject(project_root)
        cfg._merge_ignore_file(project_root)
        return cfg

    def _merge_pyproject(self, root: Path):
        toml_path = root / "pyproject.toml"
        if not toml_path.is_file():
            return
        try:
            import tomllib
        except ImportError:
            return
        try:
            data = tomllib.loads(toml_path.read_text(encoding="utf-8"))
        except Exception:
            return
        tc = data.get("tool", {}).get("threadcheck", {})
        for pat in tc.get("ignore", []):
            self._add_pattern(pat)

    def _merge_ignore_file(self, root: Path):
        path = root / ".threadcheckignore"
        if not path.is_file():
            return
        for line in path.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            self._add_pattern(stripped)

    def _add_pattern(self, pattern: str):
        line_m = re.match(r'^(.+?):(\d+)(?:-(\d+))?$', pattern)
        if line_m:
            fp = line_m.group(1)
            start = int(line_m.group(2))
            end = int(line_m.group(3)) if line_m.group(3) else start
            self.line_suppressions.append(LineSuppression(fp, start, end))
        else:
            self.ignore_patterns.append(pattern)

    def should_ignore_file(self, path: Path, root: Path) -> bool:
        try:
            rel = path.relative_to(root).as_posix()
        except ValueError:
            return False
        result = False
        for pat in self.ignore_patterns:
            if pat.startswith("!"):
                if _match_glob(rel, pat[1:]):
                    result = False
            elif _match_glob(rel, pat):
                result = True
        return result

    def should_ignore_line(self, file_path: Path, root: Path, line: int) -> bool:
        try:
            rel = file_path.relative_to(root).as_posix()
        except ValueError:
            return False
        for s in self.line_suppressions:
            if fnmatch.fnmatch(rel, s.file_pattern) and s.start_line <= line <= s.end_line:
                return True
        return False


def _match_glob(rel_path: str, pattern: str) -> bool:
    if "**" in pattern:
        if pattern.startswith("**/"):
            sub = pattern[3:]
            if fnmatch.fnmatch(rel_path, sub):
                return True
            for part in rel_path.split("/"):
                if fnmatch.fnmatch(part, sub):
                    return True
            return False
        return fnmatch.fnmatch(rel_path, pattern)
    return fnmatch.fnmatch(rel_path, pattern)
