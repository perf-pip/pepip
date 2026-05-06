"""Tests for pepip.cli venv command."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from pepip.cli import main


def test_venv_proxies_to_uv_venv() -> None:
    with patch("pepip.cli._uv_executable", return_value="uv"):
        with patch("pepip.cli.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            rc = main(["venv", ".venv", "--python", "3.12"])

    assert rc == 0
    mock_run.assert_called_once_with(
        ["uv", "venv", ".venv", "--python", "3.12"], check=True
    )


def test_venv_file_not_found_error(capsys: pytest.CaptureFixture[str]) -> None:
    with patch(
        "pepip.cli._uv_executable", side_effect=FileNotFoundError("uv not found")
    ):
        rc = main(["venv"])
    assert rc == 1
    captured = capsys.readouterr()
    assert "uv not found" in captured.err


def test_venv_generic_error(capsys: pytest.CaptureFixture[str]) -> None:
    with patch("pepip.cli._uv_executable", return_value="uv"):
        with patch("pepip.cli.subprocess.run", side_effect=RuntimeError("venv failed")):
            rc = main(["venv"])
    assert rc == 1
    captured = capsys.readouterr()
    assert "venv failed" in captured.err


def test_venv_forwards_unknown_options_to_uv() -> None:
    with patch("pepip.cli._uv_executable", return_value="uv"):
        with patch("pepip.cli.subprocess.run") as mock_run:
            rc = main(["venv", ".venv", "--seed", "--clear"])

    assert rc == 0
    mock_run.assert_called_once_with(
        ["uv", "venv", ".venv", "--seed", "--clear"],
        check=True,
    )


def test_venv_reports_subprocess_failures(capsys: pytest.CaptureFixture[str]) -> None:
    with patch("pepip.cli._uv_executable", return_value="uv"):
        with patch(
            "pepip.cli.subprocess.run", side_effect=OSError("permission denied")
        ):
            rc = main(["venv"])

    captured = capsys.readouterr()
    assert rc == 1
    assert "pepip: error: permission denied" in captured.err
