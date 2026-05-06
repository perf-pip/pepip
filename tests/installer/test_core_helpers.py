"""Tests for low-level installer helpers."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from pepip.installer import (
    _create_symlink,
    _entries,
    _python_in_venv,
    _site_packages,
    _uv_executable,
)


def test_uv_executable_finds_uv_next_to_python(tmp_path: Path) -> None:
    fake_uv = tmp_path / ("uv.exe" if sys.platform == "win32" else "uv")
    fake_uv.touch()
    fake_uv.chmod(0o755)
    with patch.object(Path, "is_file", return_value=True):
        with patch("sys.executable", str(tmp_path / "python")):
            result = _uv_executable()
    assert result == str(fake_uv)


def test_uv_executable_finds_uv_on_path(tmp_path: Path) -> None:
    fake_uv = tmp_path / "uv"
    fake_uv.touch()
    with patch.object(Path, "is_file", return_value=False):
        with patch("shutil.which", return_value=str(fake_uv)):
            result = _uv_executable()
    assert result == str(fake_uv)


def test_uv_executable_finds_windows_uv_next_to_python(tmp_path: Path) -> None:
    fake_uv = tmp_path / "uv.exe"
    fake_uv.touch()
    with patch("sys.platform", "win32"):
        with patch.object(Path, "is_file", return_value=True):
            with patch("sys.executable", str(tmp_path / "python.exe")):
                result = _uv_executable()
    assert result == str(fake_uv)


def test_uv_executable_raises_when_not_found() -> None:
    with patch.object(Path, "is_file", return_value=False):
        with patch("shutil.which", return_value=None):
            with pytest.raises(FileNotFoundError, match="uv"):
                _uv_executable()


def test_python_in_venv_unix_path(tmp_path: Path) -> None:
    if sys.platform == "win32":
        pytest.skip("Unix-only test")
    result = _python_in_venv(tmp_path)
    assert result == tmp_path / "bin" / "python"


def test_python_in_venv_windows_path(tmp_path: Path) -> None:
    with patch("sys.platform", "win32"):
        result = _python_in_venv(tmp_path)
    assert result == tmp_path / "Scripts" / "python.exe"


def test_site_packages_uses_venv_python_when_available(tmp_path: Path) -> None:
    fake_python = _python_in_venv(tmp_path)
    fake_python.parent.mkdir(parents=True)
    fake_python.touch()
    expected = str(tmp_path / "resolved-site-packages")
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout=expected + "\n")
        result = _site_packages(tmp_path)
    assert result == Path(expected)


def test_site_packages_fallback_when_python_missing(tmp_path: Path) -> None:
    if sys.platform == "win32":
        expected = tmp_path / "Lib" / "site-packages"
    else:
        py_tag = f"python{sys.version_info.major}.{sys.version_info.minor}"
        expected = tmp_path / "lib" / py_tag / "site-packages"
    result = _site_packages(tmp_path)
    assert result == expected


def test_entries_returns_empty_for_missing_dir(tmp_path: Path) -> None:
    assert _entries(tmp_path / "nonexistent") == set()


def test_entries_returns_names(tmp_path: Path) -> None:
    (tmp_path / "numpy").mkdir()
    (tmp_path / "numpy-1.24.dist-info").mkdir()
    result = _entries(tmp_path)
    assert result == {"numpy", "numpy-1.24.dist-info"}


def test_create_symlink_passes_directory_flag_when_target_is_directory(
    tmp_path: Path,
) -> None:
    link_path = tmp_path / "link"
    target_path = tmp_path / "target"
    target_path.mkdir()

    with patch.object(Path, "symlink_to", autospec=True) as mock_symlink_to:
        _create_symlink(link_path, target_path)

    mock_symlink_to.assert_called_once_with(
        link_path, target_path, target_is_directory=True
    )


def test_create_symlink_passes_file_flag_when_target_is_file(tmp_path: Path) -> None:
    link_path = tmp_path / "link.py"
    target_path = tmp_path / "target.py"
    target_path.write_text("")

    with patch.object(Path, "symlink_to", autospec=True) as mock_symlink_to:
        _create_symlink(link_path, target_path)

    mock_symlink_to.assert_called_once_with(
        link_path, target_path, target_is_directory=False
    )
