"""Tests for pepip.installer."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

import pepip.installer as installer
from pepip.installer import (GLOBAL_VENV, _entries, _python_in_venv,
                             _site_packages, _uv_executable,
                             ensure_global_venv, ensure_local_venv, install,
                             link_packages)

# ---------------------------------------------------------------------------
# _uv_executable
# ---------------------------------------------------------------------------


class TestUvExecutable:
    def test_finds_uv_next_to_python(self, tmp_path):
        fake_uv = tmp_path / "uv"
        fake_uv.touch()
        fake_uv.chmod(0o755)
        with patch.object(Path, "is_file", return_value=True):
            with patch("sys.executable", str(tmp_path / "python")):
                result = _uv_executable()
        assert result.endswith("uv")

    def test_finds_uv_on_path(self, tmp_path):
        fake_uv = tmp_path / "uv"
        fake_uv.touch()
        with patch.object(Path, "is_file", return_value=False):
            with patch("shutil.which", return_value=str(fake_uv)):
                result = _uv_executable()
        assert result == str(fake_uv)

    def test_raises_when_not_found(self):
        with patch.object(Path, "is_file", return_value=False):
            with patch("shutil.which", return_value=None):
                with pytest.raises(FileNotFoundError, match="uv"):
                    _uv_executable()


# ---------------------------------------------------------------------------
# _python_in_venv
# ---------------------------------------------------------------------------


class TestPythonInVenv:
    def test_unix_path(self, tmp_path):
        if sys.platform == "win32":
            pytest.skip("Unix-only test")
        result = _python_in_venv(tmp_path)
        assert result == tmp_path / "bin" / "python"

    def test_windows_path(self, tmp_path):
        with patch("sys.platform", "win32"):
            result = _python_in_venv(tmp_path)
        assert result == tmp_path / "Scripts" / "python.exe"


# ---------------------------------------------------------------------------
# _site_packages
# ---------------------------------------------------------------------------


class TestSitePackages:
    def test_uses_venv_python_when_available(self, tmp_path):
        fake_python = tmp_path / "bin" / "python"
        fake_python.parent.mkdir(parents=True)
        fake_python.touch()
        expected = "/some/path/site-packages"
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout=expected + "\n")
            result = _site_packages(tmp_path)
        assert result == Path(expected)

    def test_fallback_when_python_missing(self, tmp_path):
        if sys.platform == "win32":
            expected = tmp_path / "Lib" / "site-packages"
        else:
            py_tag = f"python{sys.version_info.major}.{sys.version_info.minor}"
            expected = tmp_path / "lib" / py_tag / "site-packages"
        result = _site_packages(tmp_path)
        assert result == expected


# ---------------------------------------------------------------------------
# _entries
# ---------------------------------------------------------------------------


class TestEntries:
    def test_returns_empty_for_missing_dir(self, tmp_path):
        assert _entries(tmp_path / "nonexistent") == set()

    def test_returns_names(self, tmp_path):
        (tmp_path / "numpy").mkdir()
        (tmp_path / "numpy-1.24.dist-info").mkdir()
        result = _entries(tmp_path)
        assert result == {"numpy", "numpy-1.24.dist-info"}


# ---------------------------------------------------------------------------
# ensure_global_venv
# ---------------------------------------------------------------------------


class TestEnsureGlobalVenv:
    def test_creates_venv_when_missing(self, tmp_path):
        fake_global = tmp_path / "global-venv"
        with patch.object(installer, "GLOBAL_VENV", fake_global):
            with patch("pepip.installer._uv_executable", return_value="uv"):
                with patch("subprocess.run") as mock_run:
                    result = ensure_global_venv()
        mock_run.assert_called_once_with(["uv", "venv", str(fake_global)], check=True)
        assert result == fake_global

    def test_skips_creation_when_exists(self, tmp_path):
        fake_global = tmp_path / "global-venv"
        fake_global.mkdir()
        with patch.object(installer, "GLOBAL_VENV", fake_global):
            with patch("subprocess.run") as mock_run:
                result = ensure_global_venv()
        mock_run.assert_not_called()
        assert result == fake_global


# ---------------------------------------------------------------------------
# ensure_local_venv
# ---------------------------------------------------------------------------


class TestEnsureLocalVenv:
    def test_creates_venv_when_missing(self, tmp_path):
        local_venv = tmp_path / ".venv"
        with patch("pepip.installer._uv_executable", return_value="uv"):
            with patch("subprocess.run") as mock_run:
                result = ensure_local_venv(local_venv)
        mock_run.assert_called_once_with(["uv", "venv", str(local_venv)], check=True)
        assert result == local_venv

    def test_skips_creation_when_exists(self, tmp_path):
        local_venv = tmp_path / ".venv"
        local_venv.mkdir()
        with patch("subprocess.run") as mock_run:
            result = ensure_local_venv(local_venv)
        mock_run.assert_not_called()
        assert result == local_venv


# ---------------------------------------------------------------------------
# link_packages
# ---------------------------------------------------------------------------


class TestLinkPackages:
    def test_creates_symlinks_for_new_entries(self, tmp_path):
        global_site = tmp_path / "global" / "site-packages"
        global_site.mkdir(parents=True)
        local_site = tmp_path / "local" / "site-packages"
        local_site.mkdir(parents=True)

        # Create a fake package in the global site-packages.
        pkg_dir = global_site / "numpy"
        pkg_dir.mkdir()
        dist_info = global_site / "numpy-1.24.dist-info"
        dist_info.mkdir()

        link_packages(global_site, local_site, {"numpy", "numpy-1.24.dist-info"})

        assert (local_site / "numpy").is_symlink()
        assert (local_site / "numpy").resolve() == pkg_dir.resolve()
        assert (local_site / "numpy-1.24.dist-info").is_symlink()

    def test_replaces_outdated_symlink(self, tmp_path):
        global_site = tmp_path / "global" / "site-packages"
        global_site.mkdir(parents=True)
        local_site = tmp_path / "local" / "site-packages"
        local_site.mkdir(parents=True)

        pkg_dir = global_site / "numpy"
        pkg_dir.mkdir()

        # Pre-existing symlink to a different location.
        other = tmp_path / "other"
        other.mkdir()
        (local_site / "numpy").symlink_to(other)

        link_packages(global_site, local_site, {"numpy"})

        assert (local_site / "numpy").resolve() == pkg_dir.resolve()

    def test_leaves_correct_symlink_unchanged(self, tmp_path):
        global_site = tmp_path / "global" / "site-packages"
        global_site.mkdir(parents=True)
        local_site = tmp_path / "local" / "site-packages"
        local_site.mkdir(parents=True)

        pkg_dir = global_site / "numpy"
        pkg_dir.mkdir()

        # Correct symlink already exists.
        (local_site / "numpy").symlink_to(pkg_dir)

        link_packages(global_site, local_site, {"numpy"})

        # Should still be there and pointing to the same place.
        assert (local_site / "numpy").resolve() == pkg_dir.resolve()

    def test_does_not_overwrite_real_directory(self, tmp_path):
        global_site = tmp_path / "global" / "site-packages"
        global_site.mkdir(parents=True)
        local_site = tmp_path / "local" / "site-packages"
        local_site.mkdir(parents=True)

        pkg_dir = global_site / "numpy"
        pkg_dir.mkdir()

        # Real directory already exists in local (e.g. editable install).
        real_local = local_site / "numpy"
        real_local.mkdir()

        link_packages(global_site, local_site, {"numpy"})

        assert not real_local.is_symlink()
        assert real_local.is_dir()

    def test_skips_missing_global_entry(self, tmp_path):
        global_site = tmp_path / "global" / "site-packages"
        global_site.mkdir(parents=True)
        local_site = tmp_path / "local" / "site-packages"
        local_site.mkdir(parents=True)

        # Entry exists in set but not on disk.
        link_packages(global_site, local_site, {"ghost_package"})

        assert not (local_site / "ghost_package").exists()

    def test_creates_local_site_if_missing(self, tmp_path):
        global_site = tmp_path / "global" / "site-packages"
        global_site.mkdir(parents=True)
        local_site = tmp_path / "local" / "site-packages"
        # Do NOT create local_site — link_packages should create it.

        pkg_dir = global_site / "numpy"
        pkg_dir.mkdir()

        link_packages(global_site, local_site, {"numpy"})

        assert local_site.is_dir()
        assert (local_site / "numpy").is_symlink()


# ---------------------------------------------------------------------------
# install (integration-style with subprocess mocked)
# ---------------------------------------------------------------------------


class TestInstall:
    def _make_global_site(self, tmp_path: Path) -> Path:
        py_tag = f"python{sys.version_info.major}.{sys.version_info.minor}"
        site = tmp_path / "global-venv" / "lib" / py_tag / "site-packages"
        site.mkdir(parents=True)
        return site

    def test_raises_without_packages_or_requirements(self, tmp_path):
        with pytest.raises(ValueError, match="Provide at least one"):
            install(local_venv=tmp_path / ".venv")

    def test_install_creates_symlinks(self, tmp_path):
        global_venv = tmp_path / "global-venv"
        global_venv.mkdir()
        py_tag = f"python{sys.version_info.major}.{sys.version_info.minor}"
        global_site = global_venv / "lib" / py_tag / "site-packages"
        global_site.mkdir(parents=True)

        local_venv = tmp_path / ".venv"
        local_venv.mkdir()
        local_site = local_venv / "lib" / py_tag / "site-packages"
        local_site.mkdir(parents=True)

        def fake_run(cmd, **kwargs):
            # Simulate uv installing numpy into the global site-packages.
            if "install" in cmd:
                (global_site / "numpy").mkdir(exist_ok=True)
                (global_site / "numpy-2.0.dist-info").mkdir(exist_ok=True)
            return MagicMock(returncode=0)

        with patch.object(installer, "GLOBAL_VENV", global_venv):
            with patch("pepip.installer._uv_executable", return_value="uv"):
                with patch("pepip.installer._site_packages") as mock_sp:
                    mock_sp.side_effect = lambda v: (
                        global_site if v == global_venv else local_site
                    )
                    with patch("subprocess.run", side_effect=fake_run):
                        new_entries = install(packages=["numpy"], local_venv=local_venv)

        assert "numpy" in new_entries
        assert "numpy-2.0.dist-info" in new_entries
        assert (local_site / "numpy").is_symlink()
        assert (local_site / "numpy-2.0.dist-info").is_symlink()

    def test_install_calls_uv_with_requirements_file(self, tmp_path):
        global_venv = tmp_path / "global-venv"
        global_venv.mkdir()
        py_tag = f"python{sys.version_info.major}.{sys.version_info.minor}"
        global_site = global_venv / "lib" / py_tag / "site-packages"
        global_site.mkdir(parents=True)

        local_venv = tmp_path / ".venv"
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("requests\n")

        run_calls = []

        def fake_run(cmd, **kwargs):
            run_calls.append(cmd)
            return MagicMock(returncode=0)

        with patch.object(installer, "GLOBAL_VENV", global_venv):
            with patch("pepip.installer._uv_executable", return_value="uv"):
                with patch("pepip.installer._site_packages") as mock_sp:
                    mock_sp.return_value = global_site
                    with patch("subprocess.run", side_effect=fake_run):
                        install(
                            requirements_file=str(req_file),
                            local_venv=local_venv,
                        )

        install_call = next(c for c in run_calls if "install" in c)
        assert "-r" in install_call
        assert str(req_file) in install_call
