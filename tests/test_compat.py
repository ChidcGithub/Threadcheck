from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from threadcheck.compat import check_compat
from threadcheck.compat.models import CompatStatus, FTCompatResult


def _make_mock_distro(
    name: str,
    files: list[str] | None = None,
    raises: type[Exception] | None = None,
):
    dist = MagicMock()
    dist.metadata = {"Name": name}
    if raises:
        dist.files = raises
    elif files is not None:
        dist.files = [_make_package_path(f) for f in files]
    else:
        dist.files = None
    return dist


def _make_package_path(path: str):
    return MagicMock(
        suffix=Path(path).suffix,
        __str__=lambda self, _p=path: _p,
    )


class TestCheckSingle:
    @patch("importlib.metadata.distribution")
    def test_pure_python(self, mock_distribution):
        mock_distribution.return_value = _make_mock_distro("purepkg", files=[])
        results = check_compat(names=["purepkg"])
        assert len(results) == 1
        assert results[0].name == "purepkg"
        assert results[0].status == CompatStatus.COMPATIBLE
        assert "pure Python" in results[0].reason

    @patch("importlib.metadata.distribution")
    def test_c_ext_without_ft(self, mock_distribution):
        mock_distribution.return_value = _make_mock_distro(
            "cpkg",
            files=["_module.cp313-win_amd64.pyd"],
        )
        results = check_compat(names=["cpkg"])
        assert len(results) == 1
        assert results[0].status == CompatStatus.NEEDS_VERIFICATION
        assert len(results[0].c_exts) == 1
        assert not results[0].c_exts[0].has_ft_tag

    @patch("importlib.metadata.distribution")
    def test_c_ext_with_ft(self, mock_distribution):
        mock_distribution.return_value = _make_mock_distro(
            "ftpkg",
            files=["_module.cp313t-win_amd64.pyd"],
        )
        results = check_compat(names=["ftpkg"])
        assert len(results) == 1
        assert results[0].status == CompatStatus.COMPATIBLE
        assert results[0].c_exts[0].has_ft_tag

    @patch("importlib.metadata.distribution")
    def test_c_ext_linux_with_ft(self, mock_distribution):
        mock_distribution.return_value = _make_mock_distro(
            "ftpkg",
            files=["_module.cpython-313t-x86_64-linux-gnu.so"],
        )
        results = check_compat(names=["ftpkg"])
        assert results[0].status == CompatStatus.COMPATIBLE
        assert results[0].c_exts[0].has_ft_tag

    @patch("importlib.metadata.distribution")
    def test_not_installed(self, mock_distribution):
        from importlib.metadata import PackageNotFoundError

        mock_distribution.side_effect = PackageNotFoundError
        results = check_compat(names=["missingpkg"])
        assert len(results) == 1
        assert results[0].status == CompatStatus.NOT_INSTALLED

    @patch("importlib.metadata.distribution")
    def test_no_c_exts_in_relevant_files(self, mock_distribution):
        mock_distribution.return_value = _make_mock_distro(
            "pkg",
            files=["pkg/__init__.py", "pkg/utils.py"],
        )
        results = check_compat(names=["pkg"])
        assert results[0].status == CompatStatus.COMPATIBLE

    @patch("importlib.metadata.distribution")
    def test_mixed_c_exts(self, mock_distribution):
        mock_distribution.return_value = _make_mock_distro(
            "mixedpkg",
            files=[
                "_safe.cp313t-win_amd64.pyd",
                "_unsafe.cp313-win_amd64.pyd",
            ],
        )
        results = check_compat(names=["mixedpkg"])
        assert results[0].status == CompatStatus.NEEDS_VERIFICATION
        ft_count = sum(1 for e in results[0].c_exts if e.has_ft_tag)
        non_ft_count = sum(1 for e in results[0].c_exts if not e.has_ft_tag)
        assert ft_count == 1
        assert non_ft_count == 1


class TestCheckCompatAPI:
    def test_check_compat_with_empty_names(self):
        results = check_compat(names=[])
        assert results == []


class TestFTCompatResult:
    def test_to_dict(self):
        from threadcheck.compat.models import CExtInfo

        result = FTCompatResult(
            name="testpkg",
            status=CompatStatus.NEEDS_VERIFICATION,
            c_exts=[CExtInfo(filename="_m.cp313-win.pyd", has_ft_tag=False)],
            reason="1 C extension(s) not compiled for free-threading ABI",
        )
        d = result.to_dict()
        assert d["name"] == "testpkg"
        assert d["status"] == "needs_verification"
        assert len(d["c_exts"]) == 1
        assert not d["c_exts"][0]["has_ft_tag"]


class TestCliCompat:
    def test_compat_subcommand_registered(self):
        from threadcheck.cli import main

        parser = _get_parser()
        args = parser.parse_args(["compat"])
        assert args.command == "compat"
        assert args.path == "."

    def test_compat_subcommand_with_path(self):
        parser = _get_parser()
        args = parser.parse_args(["compat", "/some/project"])
        assert args.command == "compat"
        assert args.path == "/some/project"

    def test_compat_subcommand_with_json(self):
        parser = _get_parser()
        args = parser.parse_args(["compat", "--json"])
        assert args.command == "compat"
        assert args.json


def _get_parser():
    from threadcheck.cli import main

    for cls in type(main).__mro__:
        if hasattr(cls, "parse_args"):
            return cls()
    import argparse

    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    compat = sub.add_parser("compat", help="Check free-threading compatibility")
    compat.add_argument("path", nargs="?", default=".")
    compat.add_argument("--json", action="store_true")
    return parser
