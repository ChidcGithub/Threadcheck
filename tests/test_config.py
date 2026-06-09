from pathlib import Path
from threadcheck.config import ThreadCheckConfig, LineSuppression
from threadcheck.static.analyzer import analyze_path


class TestThreadCheckConfig:
    def test_empty_config(self, tmp_path: Path):
        cfg = ThreadCheckConfig.load(tmp_path)
        assert cfg.ignore_patterns == []
        assert cfg.line_suppressions == []

    def test_ignore_file_pattern(self, tmp_path: Path):
        (tmp_path / ".threadcheckignore").write_text(
            "generated/*.py\n__pycache__/*\n", encoding="utf-8"
        )
        cfg = ThreadCheckConfig.load(tmp_path)
        assert "generated/*.py" in cfg.ignore_patterns
        assert "__pycache__/*" in cfg.ignore_patterns

    def test_ignore_file_comments_and_blanks(self, tmp_path: Path):
        (tmp_path / ".threadcheckignore").write_text(
            "# this is a comment\n\n*.pyc\n", encoding="utf-8"
        )
        cfg = ThreadCheckConfig.load(tmp_path)
        assert "# this is a comment" not in cfg.ignore_patterns
        assert "*.pyc" in cfg.ignore_patterns

    def test_line_suppression(self, tmp_path: Path):
        (tmp_path / ".threadcheckignore").write_text(
            "src/bad.py:42\nsrc/other.py:10-20\n", encoding="utf-8"
        )
        cfg = ThreadCheckConfig.load(tmp_path)
        assert len(cfg.line_suppressions) == 2
        assert cfg.line_suppressions[0] == LineSuppression("src/bad.py", 42, 42)
        assert cfg.line_suppressions[1] == LineSuppression("src/other.py", 10, 20)

    def test_pyproject_toml_config(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text(
            '[tool.threadcheck]\nignore = ["build/*", "dist/*"]\n', encoding="utf-8"
        )
        cfg = ThreadCheckConfig.load(tmp_path)
        assert "build/*" in cfg.ignore_patterns
        assert "dist/*" in cfg.ignore_patterns

    def test_merge_both_sources(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text(
            '[tool.threadcheck]\nignore = ["build/*"]\n', encoding="utf-8"
        )
        (tmp_path / ".threadcheckignore").write_text(
            "generated/*.py\n", encoding="utf-8"
        )
        cfg = ThreadCheckConfig.load(tmp_path)
        assert "build/*" in cfg.ignore_patterns
        assert "generated/*.py" in cfg.ignore_patterns

    def test_should_ignore_file(self, tmp_path: Path):
        (tmp_path / ".threadcheckignore").write_text("ignored/*.py\n", encoding="utf-8")
        cfg = ThreadCheckConfig.load(tmp_path)
        ignored_dir = tmp_path / "ignored"
        ignored_dir.mkdir()
        (ignored_dir / "test.py").write_text("x = 1\n", encoding="utf-8")
        assert cfg.should_ignore_file(ignored_dir / "test.py", tmp_path)
        assert not cfg.should_ignore_file(tmp_path / "keep.py", tmp_path)

    def test_should_ignore_line(self, tmp_path: Path):
        (tmp_path / ".threadcheckignore").write_text("test.py:3\n", encoding="utf-8")
        cfg = ThreadCheckConfig.load(tmp_path)
        py = tmp_path / "test.py"
        assert cfg.should_ignore_line(py, tmp_path, 3)
        assert not cfg.should_ignore_line(py, tmp_path, 1)
        assert not cfg.should_ignore_line(py, tmp_path, 5)

    def test_line_suppression_range(self, tmp_path: Path):
        (tmp_path / ".threadcheckignore").write_text("test.py:5-10\n", encoding="utf-8")
        cfg = ThreadCheckConfig.load(tmp_path)
        py = tmp_path / "test.py"
        assert cfg.should_ignore_line(py, tmp_path, 5)
        assert cfg.should_ignore_line(py, tmp_path, 7)
        assert cfg.should_ignore_line(py, tmp_path, 10)
        assert not cfg.should_ignore_line(py, tmp_path, 4)
        assert not cfg.should_ignore_line(py, tmp_path, 11)

    def test_should_ignore_file_with_config(self, tmp_path: Path):
        src = tmp_path / "src"
        src.mkdir()
        (src / "keep.py").write_text("x = 1\n", encoding="utf-8")
        gen = tmp_path / "generated"
        gen.mkdir()
        (gen / "out.py").write_text("x = 1\n", encoding="utf-8")

        (tmp_path / ".threadcheckignore").write_text("generated/*\n", encoding="utf-8")
        cfg = ThreadCheckConfig.load(tmp_path)

        # analyze_path should skip generated/out.py
        warnings = analyze_path(str(tmp_path), config=cfg)
        # Only keep.py should be analyzed; it has no issues
        assert len(warnings) == 0, f"Expected 0 warnings, got {len(warnings)}"

    def test_negation_pattern(self, tmp_path: Path):
        """! prefix should un-ignore a previously ignored pattern."""
        (tmp_path / ".threadcheckignore").write_text(
            "*.py\n!important.py\n", encoding="utf-8"
        )
        cfg = ThreadCheckConfig.load(tmp_path)
        (tmp_path / "normal.py").write_text("x = 1\n")
        (tmp_path / "important.py").write_text("x = 1\n")
        assert cfg.should_ignore_file(tmp_path / "normal.py", tmp_path)
        assert not cfg.should_ignore_file(tmp_path / "important.py", tmp_path)
