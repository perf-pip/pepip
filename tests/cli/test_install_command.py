"""Tests for the pepip install CLI command.

Covers argument parsing, package and requirements handling, venv selection,
and user-facing error reporting for the install subcommand.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from pepip.cli import main


def test_no_args_prints_help_and_returns_nonzero() -> None:
    with pytest.raises(SystemExit):
        main(["install"])


def test_install_packages_success() -> None:
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


def test_install_accepts_extras_style_package_specifier() -> None:
    with patch("pepip.cli.install", return_value={"project"}) as mock_install:
        rc = main(["install", ".[all]"])

    assert rc == 0
    mock_install.assert_called_once_with(
        packages=[".[all]"],
        requirements_file=None,
        local_venv=Path(".venv"),
    )


def test_install_requirements_file(tmp_path: Path) -> None:
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


def test_install_custom_venv() -> None:
    with patch("pepip.cli.install", return_value=set()) as mock_install:
        rc = main(["install", "numpy", "--venv", "/tmp/myvenv"])
    assert rc == 0
    mock_install.assert_called_once_with(
        packages=["numpy"],
        requirements_file=None,
        local_venv=Path("/tmp/myvenv"),
    )


def test_install_file_not_found_error(capsys: pytest.CaptureFixture[str]) -> None:
    with patch("pepip.cli.install", side_effect=FileNotFoundError("uv not found")):
        rc = main(["install", "numpy"])
    assert rc == 1
    captured = capsys.readouterr()
    assert "uv not found" in captured.err


def test_install_generic_error(capsys: pytest.CaptureFixture[str]) -> None:
    with patch("pepip.cli.install", side_effect=RuntimeError("something went wrong")):
        rc = main(["install", "numpy"])
    assert rc == 1
    captured = capsys.readouterr()
    assert "something went wrong" in captured.err


def test_no_command_prints_help_and_returns_zero() -> None:
    rc = main([])
    assert rc == 0


def test_install_singular_entry_message(capsys: pytest.CaptureFixture[str]) -> None:
    with patch("pepip.cli.install", return_value={"numpy"}):
        rc = main(["install", "numpy"])
    captured = capsys.readouterr()
    assert "1 entry" in captured.out
    assert rc == 0


def test_install_plural_entries_message(capsys: pytest.CaptureFixture[str]) -> None:
    with patch("pepip.cli.install", return_value={"numpy", "numpy-2.0.dist-info"}):
        rc = main(["install", "numpy"])
    captured = capsys.readouterr()
    assert "2 entries" in captured.out
    assert rc == 0


def test_install_packages_and_requirements_are_forwarded_together(
    tmp_path: Path,
) -> None:
    req = tmp_path / "requirements.txt"
    req.write_text("urllib3\n", encoding="utf-8")

    with patch("pepip.cli.install", return_value={"requests"}) as mock_install:
        rc = main(["install", "requests", "-r", str(req), "--venv", "env"])

    assert rc == 0
    mock_install.assert_called_once_with(
        packages=["requests"],
        requirements_file=str(req),
        local_venv=Path("env"),
    )


def test_install_rejects_unknown_arguments_before_calling_installer() -> None:
    with patch("pepip.cli.install") as mock_install:
        with pytest.raises(SystemExit) as exc_info:
            main(["install", "requests", "--unknown"])

    assert exc_info.value.code == 2
    mock_install.assert_not_called()


def test_install_reports_subprocess_style_failures(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with patch("pepip.cli.install", side_effect=OSError("permission denied")):
        rc = main(["install", "requests"])

    captured = capsys.readouterr()
    assert rc == 1
    assert "pepip: error: permission denied" in captured.err


def test_top_level_unknown_command_is_forwarded_to_uv() -> None:
    with patch("pepip.cli._run_uv", return_value=0) as mock_run_uv:
        rc = main(["unknown"])

    assert rc == 0
    mock_run_uv.assert_called_once_with(["unknown"])
