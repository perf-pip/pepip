"""Tests for pepip.installer."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import pepip.installer as installer
from pepip.installer import (
    _create_symlink,
    _entries,
    _python_in_venv,
    _site_packages,
    _uv_executable,
    ensure_global_venv,
    ensure_local_venv,
    install,
    link_packages,
)


def _symlinks_supported(tmp_path: Path) -> bool:
    probe_target = tmp_path / "symlink-target"
    probe_target.mkdir()
    probe_link = tmp_path / "symlink-link"
    try:
        _create_symlink(probe_link, probe_target)
    except OSError:
        return False
    probe_link.unlink()
    return True

# ---------------------------------------------------------------------------
# _uv_executable
# ---------------------------------------------------------------------------


class TestUvExecutable:
    def test_finds_uv_next_to_python(self, tmp_path):
        fake_uv = tmp_path / ("uv.exe" if sys.platform == "win32" else "uv")
        fake_uv.touch()
        fake_uv.chmod(0o755)
        with patch.object(Path, "is_file", return_value=True):
            with patch("sys.executable", str(tmp_path / "python")):
                result = _uv_executable()
        assert result == str(fake_uv)

    def test_finds_uv_on_path(self, tmp_path):
        fake_uv = tmp_path / "uv"
        fake_uv.touch()
        with patch.object(Path, "is_file", return_value=False):
            with patch("shutil.which", return_value=str(fake_uv)):
                result = _uv_executable()
        assert result == str(fake_uv)

    def test_finds_windows_uv_next_to_python(self, tmp_path):
        fake_uv = tmp_path / "uv.exe"
        fake_uv.touch()
        with patch("sys.platform", "win32"):
            with patch.object(Path, "is_file", return_value=True):
                with patch("sys.executable", str(tmp_path / "python.exe")):
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
        fake_python = _python_in_venv(tmp_path)
        fake_python.parent.mkdir(parents=True)
        fake_python.touch()
        expected = str(tmp_path / "resolved-site-packages")
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
        if not _symlinks_supported(tmp_path):
            pytest.skip("symlinks are not available in this environment")

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
        if not _symlinks_supported(tmp_path):
            pytest.skip("symlinks are not available in this environment")

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
        if not _symlinks_supported(tmp_path):
            pytest.skip("symlinks are not available in this environment")

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
        if not _symlinks_supported(tmp_path):
            pytest.skip("symlinks are not available in this environment")

        global_site = tmp_path / "global" / "site-packages"
        global_site.mkdir(parents=True)
        local_site = tmp_path / "local" / "site-packages"
        # Do NOT create local_site — link_packages should create it.

        pkg_dir = global_site / "numpy"
        pkg_dir.mkdir()

        link_packages(global_site, local_site, {"numpy"})

        assert local_site.is_dir()
        assert (local_site / "numpy").is_symlink()

    def test_raises_when_local_site_creation_fails(self, tmp_path):
        global_site = tmp_path / "global" / "site-packages"
        global_site.mkdir(parents=True)
        local_site = tmp_path / "local" / "site-packages"

        with patch.object(Path, "mkdir", side_effect=PermissionError("denied")):
            with pytest.raises(
                RuntimeError, match="Failed to prepare local site-packages"
            ):
                link_packages(global_site, local_site, {"numpy"})

    def test_raises_when_replacing_symlink_fails(self, tmp_path):
        global_site = tmp_path / "global" / "site-packages"
        global_site.mkdir(parents=True)
        local_site = tmp_path / "local" / "site-packages"
        local_site.mkdir(parents=True)

        pkg_dir = global_site / "numpy"
        pkg_dir.mkdir()

        other = tmp_path / "other"
        other.mkdir()
        local_entry = local_site / "numpy"
        local_entry.symlink_to(other)

        with patch.object(Path, "unlink", side_effect=PermissionError("denied")):
            with pytest.raises(
                RuntimeError, match="Failed to replace existing symlink"
            ):
                link_packages(global_site, local_site, {"numpy"})

    def test_raises_when_symlink_creation_fails(self, tmp_path):
        global_site = tmp_path / "global" / "site-packages"
        global_site.mkdir(parents=True)
        local_site = tmp_path / "local" / "site-packages"
        local_site.mkdir(parents=True)

        pkg_dir = global_site / "numpy"
        pkg_dir.mkdir()

        with patch(
            "pepip.installer._create_symlink", side_effect=OSError("unsupported")
        ):
            with pytest.raises(
                RuntimeError, match="Failed to create symlink"
            ):
                link_packages(global_site, local_site, {"numpy"})

    def test_passes_directory_flag_when_creating_directory_symlink(self, tmp_path):
        link_path = tmp_path / "link"
        target_path = tmp_path / "target"
        target_path.mkdir()

        with patch.object(Path, "symlink_to", autospec=True) as mock_symlink_to:
            _create_symlink(link_path, target_path)

        mock_symlink_to.assert_called_once_with(
            link_path, target_path, target_is_directory=True
        )

    def test_passes_file_flag_when_creating_file_symlink(self, tmp_path):
        link_path = tmp_path / "link.py"
        target_path = tmp_path / "target.py"
        target_path.write_text("")

        with patch.object(Path, "symlink_to", autospec=True) as mock_symlink_to:
            _create_symlink(link_path, target_path)

        mock_symlink_to.assert_called_once_with(
            link_path, target_path, target_is_directory=False
        )


# ---------------------------------------------------------------------------
# install (integration-style with subprocess mocked)
# ---------------------------------------------------------------------------


class TestInstall:
    def _make_global_site(self, tmp_path: Path) -> Path:
        site = _site_packages(tmp_path / "global-venv")
        site.mkdir(parents=True)
        return site

    def _write_fake_dist(
        self, site: Path, name: str, version: str, module_name: str | None = None
    ) -> None:
        module_name = module_name or name.replace("-", "_")

        package_dir = site / module_name
        package_dir.mkdir(parents=True, exist_ok=True)
        (package_dir / "__init__.py").write_text(f"__version__ = '{version}'\n")

        dist_info = site / f"{name.replace('-', '_')}-{version}.dist-info"
        dist_info.mkdir(parents=True, exist_ok=True)
        (dist_info / "METADATA").write_text(
            f"Name: {name}\nVersion: {version}\n",
            encoding="utf-8",
        )
        (dist_info / "RECORD").write_text(
            "\n".join(
                [
                    f"{module_name}/__init__.py,,",
                    f"{dist_info.name}/METADATA,,",
                    f"{dist_info.name}/RECORD,,",
                ]
            ),
            encoding="utf-8",
        )

    def test_raises_without_packages_or_requirements(self, tmp_path):
        with pytest.raises(ValueError, match="Provide at least one"):
            install(local_venv=tmp_path / ".venv")

    def test_install_creates_symlinks(self, tmp_path):
        if not _symlinks_supported(tmp_path):
            pytest.skip("symlinks are not available in this environment")

        global_venv = tmp_path / "global-venv"
        global_venv.mkdir()
        global_site = _site_packages(global_venv)
        global_site.mkdir(parents=True)

        local_venv = tmp_path / ".venv"
        local_venv.mkdir()
        local_site = _site_packages(local_venv)
        local_site.mkdir(parents=True)

        def fake_run(cmd, **kwargs):
            if "install" in cmd:
                target = Path(cmd[cmd.index("--target") + 1])
                self._write_fake_dist(target, "numpy", "2.0")
            return MagicMock(returncode=0)

        with patch.object(installer, "GLOBAL_VENV", global_venv):
            with patch("pepip.installer._uv_executable", return_value="uv"):
                with patch("pepip.installer._site_packages") as mock_sp:
                    mock_sp.return_value = local_site
                    with patch("subprocess.run", side_effect=fake_run):
                        linked_entries = install(
                            packages=["numpy"], local_venv=local_venv
                        )

        assert "numpy" in linked_entries
        assert "numpy-2.0.dist-info" in linked_entries
        assert (local_site / "numpy").is_symlink()
        assert (local_site / "numpy-2.0.dist-info").is_symlink()

    def test_install_calls_uv_with_requirements_file(self, tmp_path):
        global_venv = tmp_path / "global-venv"
        global_venv.mkdir()
        global_site = _site_packages(global_venv)
        global_site.mkdir(parents=True)

        local_venv = tmp_path / ".venv"
        req_file = tmp_path / "requirements.txt"
        req_file.write_text("requests\n")

        run_calls = []

        def fake_run(cmd, **kwargs):
            run_calls.append(cmd)
            if "install" in cmd:
                target = Path(cmd[cmd.index("--target") + 1])
                self._write_fake_dist(target, "requests", "2.26.0")
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
        assert "--target" in install_call

    def test_different_projects_keep_different_package_versions(self, tmp_path):
        if not _symlinks_supported(tmp_path):
            pytest.skip("symlinks are not available in this environment")

        global_venv = tmp_path / "pepip-home" / "global-venv"
        global_venv.mkdir(parents=True)

        project_a_venv = tmp_path / "project-a" / ".venv"
        project_a_site = _site_packages(project_a_venv)
        project_a_site.mkdir(parents=True)

        project_b_venv = tmp_path / "project-b" / ".venv"
        project_b_site = _site_packages(project_b_venv)
        project_b_site.mkdir(parents=True)

        def fake_run(cmd, **kwargs):
            if "install" in cmd:
                target = Path(cmd[cmd.index("--target") + 1])
                version = "2.26.0" if "requests==2.26.0" in cmd else "2.25.1"
                self._write_fake_dist(target, "requests", version)
            return MagicMock(returncode=0)

        def fake_site_packages(venv):
            return project_a_site if venv == project_a_venv else project_b_site

        with patch.object(installer, "GLOBAL_VENV", global_venv):
            with patch("pepip.installer._uv_executable", return_value="uv"):
                with patch(
                    "pepip.installer._site_packages",
                    side_effect=fake_site_packages,
                ):
                    with patch("subprocess.run", side_effect=fake_run):
                        install(
                            packages=["requests==2.25.1"],
                            local_venv=project_a_venv,
                        )
                        install(
                            packages=["requests==2.26.0"],
                            local_venv=project_b_venv,
                        )

        project_a_requests = project_a_site / "requests"
        project_b_requests = project_b_site / "requests"

        assert project_a_requests.is_symlink()
        assert project_b_requests.is_symlink()
        assert project_a_requests.resolve() != project_b_requests.resolve()
        assert "2.25.1" in (project_a_requests / "__init__.py").read_text()
        assert "2.26.0" in (project_b_requests / "__init__.py").read_text()
        assert (project_a_site / "requests-2.25.1.dist-info").is_symlink()
        assert (project_b_site / "requests-2.26.0.dist-info").is_symlink()

    def test_reinstalling_project_replaces_stale_version_metadata(self, tmp_path):
        if not _symlinks_supported(tmp_path):
            pytest.skip("symlinks are not available in this environment")

        global_venv = tmp_path / "pepip-home" / "global-venv"
        global_venv.mkdir(parents=True)

        local_venv = tmp_path / ".venv"
        local_site = _site_packages(local_venv)
        local_site.mkdir(parents=True)

        def fake_run(cmd, **kwargs):
            if "install" in cmd:
                target = Path(cmd[cmd.index("--target") + 1])
                version = "2.26.0" if "requests==2.26.0" in cmd else "2.25.1"
                self._write_fake_dist(target, "requests", version)
            return MagicMock(returncode=0)

        with patch.object(installer, "GLOBAL_VENV", global_venv):
            with patch("pepip.installer._uv_executable", return_value="uv"):
                with patch("pepip.installer._site_packages", return_value=local_site):
                    with patch("subprocess.run", side_effect=fake_run):
                        install(
                            packages=["requests==2.25.1"],
                            local_venv=local_venv,
                        )
                        install(
                            packages=["requests==2.26.0"],
                            local_venv=local_venv,
                        )

        assert "2.26.0" in ((local_site / "requests") / "__init__.py").read_text()
        assert not (local_site / "requests-2.25.1.dist-info").exists()
        assert (local_site / "requests-2.26.0.dist-info").is_symlink()
