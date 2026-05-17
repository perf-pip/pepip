"""Tests for installer virtual environment management helpers.

Ensures that global and local venv creation is idempotent and that uv is invoked
correctly when a venv does not yet exist.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pepip.installer as installer
from pepip.installer import ensure_global_venv, ensure_local_venv


def test_ensure_global_venv_creates_when_missing(tmp_path: Path) -> None:
    fake_global = tmp_path / "global-venv"
    with patch.object(installer, "GLOBAL_VENV", fake_global):
        with patch("pepip.installer._uv_executable", return_value="uv"):
            with patch("subprocess.run") as mock_run:
                result = ensure_global_venv()
    mock_run.assert_called_once_with(["uv", "venv", str(fake_global)], check=True)
    assert result == fake_global


def test_ensure_global_venv_skips_when_exists(tmp_path: Path) -> None:
    fake_global = tmp_path / "global-venv"
    fake_global.mkdir()
    with patch.object(installer, "GLOBAL_VENV", fake_global):
        with patch("subprocess.run") as mock_run:
            result = ensure_global_venv()
    mock_run.assert_not_called()
    assert result == fake_global


def test_ensure_local_venv_creates_when_missing(tmp_path: Path) -> None:
    local_venv = tmp_path / ".venv"
    with patch("pepip.installer._uv_executable", return_value="uv"):
        with patch("subprocess.run") as mock_run:
            result = ensure_local_venv(local_venv)
    mock_run.assert_called_once_with(["uv", "venv", str(local_venv)], check=True)
    assert result == local_venv


def test_ensure_local_venv_skips_when_exists(tmp_path: Path) -> None:
    local_venv = tmp_path / ".venv"
    local_venv.mkdir()
    with patch("subprocess.run") as mock_run:
        result = ensure_local_venv(local_venv)
    mock_run.assert_not_called()
    assert result == local_venv
