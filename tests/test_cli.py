"""Tests for pepip.cli."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from pepip.cli import main


class TestCLIInstall:
    def test_no_args_prints_help_and_returns_nonzero(self, capsys):
        with pytest.raises(SystemExit):
            main(["install"])

    def test_install_packages_success(self):
        with patch(
            "pepip.cli.install", return_value={"numpy", "numpy-2.0.dist-info"}
        ) as mock_install:
            rc = main(["install", "numpy"])
        assert rc == 0
        mock_install.assert_called_once_with(
            packages=["numpy"],
            requirements_file=None,
            local_venv=Path(".venv"),
        )

    def test_install_requirements_file(self, tmp_path):
        req = tmp_path / "requirements.txt"
        req.write_text("numpy\n")
        with patch("pepip.cli.install", return_value=set()) as mock_install:
            rc = main(["install", "-r", str(req)])
        assert rc == 0
        mock_install.assert_called_once_with(
            packages=None,
            requirements_file=str(req),
            local_venv=Path(".venv"),
        )

    def test_install_custom_venv(self):
        with patch("pepip.cli.install", return_value=set()) as mock_install:
            rc = main(["install", "numpy", "--venv", "/tmp/myvenv"])
        assert rc == 0
        mock_install.assert_called_once_with(
            packages=["numpy"],
            requirements_file=None,
            local_venv=Path("/tmp/myvenv"),
        )

    def test_install_file_not_found_error(self, capsys):
        with patch("pepip.cli.install", side_effect=FileNotFoundError("uv not found")):
            rc = main(["install", "numpy"])
        assert rc == 1
        captured = capsys.readouterr()
        assert "uv not found" in captured.err

    def test_install_generic_error(self, capsys):
        with patch(
            "pepip.cli.install", side_effect=RuntimeError("something went wrong")
        ):
            rc = main(["install", "numpy"])
        assert rc == 1
        captured = capsys.readouterr()
        assert "something went wrong" in captured.err

    def test_no_command_prints_help_and_returns_zero(self, capsys):
        rc = main([])
        assert rc == 0

    def test_install_singular_entry_message(self, capsys):
        with patch("pepip.cli.install", return_value={"numpy"}):
            rc = main(["install", "numpy"])
        captured = capsys.readouterr()
        assert "1 new entry" in captured.out
        assert rc == 0

    def test_install_plural_entries_message(self, capsys):
        with patch("pepip.cli.install", return_value={"numpy", "numpy-2.0.dist-info"}):
            rc = main(["install", "numpy"])
        captured = capsys.readouterr()
        assert "2 new entries" in captured.out
        assert rc == 0
