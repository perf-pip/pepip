"""Tests for pepip CLI passthrough commands."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from pepip.cli import main


def test_no_command_prints_help_and_returns_zero() -> None:
    rc = main([])
    assert rc == 0


def test_root_help_prints_and_returns_zero() -> None:
    rc = main(["--help"])
    assert rc == 0


def test_sync_all_proxies_to_uv() -> None:
    with patch("pepip.cli._uv_executable", return_value="uv"):
        with patch("pepip.cli.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            rc = main(["sync", "--all"])

    assert rc == 0
    mock_run.assert_called_once_with(["uv", "sync", "--all"], check=True)


def test_venv_proxies_to_uv() -> None:
    with patch("pepip.cli._uv_executable", return_value="uv"):
        with patch("pepip.cli.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            rc = main(["venv", ".venv", "--python", "3.12"])

    assert rc == 0
    mock_run.assert_called_once_with(
        ["uv", "venv", ".venv", "--python", "3.12"], check=True
    )


def test_run_proxies_to_uv() -> None:
    with patch("pepip.cli._uv_executable", return_value="uv"):
        with patch("pepip.cli.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            rc = main(["run", "python", "-m", "pytest"])

    assert rc == 0
    mock_run.assert_called_once_with(
        ["uv", "run", "python", "-m", "pytest"], check=True
    )


def test_pip_install_extras_proxies_to_uv() -> None:
    with patch("pepip.cli._uv_executable", return_value="uv"):
        with patch("pepip.cli.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            rc = main(["pip", "install", ".[all]"])

    assert rc == 0
    mock_run.assert_called_once_with(["uv", "pip", "install", ".[all]"], check=True)


def test_global_flag_proxies_to_uv() -> None:
    with patch("pepip.cli._uv_executable", return_value="uv"):
        with patch("pepip.cli.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            rc = main(["--version"])

    assert rc == 0
    mock_run.assert_called_once_with(["uv", "--version"], check=True)


def test_passthrough_file_not_found_error(capsys: pytest.CaptureFixture[str]) -> None:
    with patch(
        "pepip.cli._uv_executable", side_effect=FileNotFoundError("uv not found")
    ):
        rc = main(["sync", "--all"])

    assert rc == 1
    captured = capsys.readouterr()
    assert "uv not found" in captured.err


def test_passthrough_generic_error(capsys: pytest.CaptureFixture[str]) -> None:
    with patch("pepip.cli._uv_executable", return_value="uv"):
        with patch("pepip.cli.subprocess.run", side_effect=RuntimeError("sync failed")):
            rc = main(["sync", "--all"])

    assert rc == 1
    captured = capsys.readouterr()
    assert "sync failed" in captured.err


def test_passthrough_reports_subprocess_failures(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with patch("pepip.cli._uv_executable", return_value="uv"):
        with patch(
            "pepip.cli.subprocess.run", side_effect=OSError("permission denied")
        ):
            rc = main(["sync", "--all"])

    captured = capsys.readouterr()
    assert rc == 1
    assert "pepip: error: permission denied" in captured.err
