"""Integration-style installer tests with subprocess mocked.

Exercises the end-to-end install flow, including staging, linking, and error
handling, without invoking real uv commands.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import pepip.installer as installer
from pepip.installer import _site_packages, install
from tests.installer.helpers import symlinks_supported, write_fake_dist


def test_install_raises_without_packages_or_requirements(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Provide at least one"):
        install(local_venv=tmp_path / ".venv")


def test_install_creates_symlinks(tmp_path: Path) -> None:
    if not symlinks_supported(tmp_path):
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
            write_fake_dist(target, "numpy", "2.0")
        return MagicMock(returncode=0)

    with patch.object(installer, "GLOBAL_VENV", global_venv):
        with patch("pepip.installer._uv_executable", return_value="uv"):
            with patch("pepip.installer._site_packages") as mock_sp:
                mock_sp.return_value = local_site
                with patch("subprocess.run", side_effect=fake_run):
                    linked_entries = install(packages=["numpy"], local_venv=local_venv)

    assert "numpy" in linked_entries
    assert "numpy-2.0.dist-info" in linked_entries
    assert (local_site / "numpy").is_symlink()
    assert (local_site / "numpy-2.0.dist-info").is_symlink()


def test_install_links_resolved_dependencies(tmp_path: Path) -> None:
    if not symlinks_supported(tmp_path):
        pytest.skip("symlinks are not available in this environment")

    global_venv = tmp_path / "global-venv"
    global_venv.mkdir()

    local_venv = tmp_path / ".venv"
    local_site = _site_packages(local_venv)
    local_site.mkdir(parents=True)

    def fake_run(cmd, **kwargs):
        if "install" in cmd:
            target = Path(cmd[cmd.index("--target") + 1])
            write_fake_dist(
                target,
                "agent-action-guard",
                "1.1.4",
                module_name="agent_action_guard",
            )
            write_fake_dist(target, "numpy", "2.4.4")
        return MagicMock(returncode=0)

    with patch.object(installer, "GLOBAL_VENV", global_venv):
        with patch("pepip.installer._uv_executable", return_value="uv"):
            with patch("pepip.installer._site_packages", return_value=local_site):
                with patch("subprocess.run", side_effect=fake_run):
                    linked_entries = install(
                        packages=["agent-action-guard"],
                        local_venv=local_venv,
                    )

    assert "agent_action_guard" in linked_entries
    assert "numpy" in linked_entries
    assert (local_site / "agent_action_guard").is_symlink()
    assert (local_site / "numpy").is_symlink()


def test_install_calls_uv_with_requirements_file(tmp_path: Path) -> None:
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
            write_fake_dist(target, "requests", "2.26.0")
        return MagicMock(returncode=0)

    with patch.object(installer, "GLOBAL_VENV", global_venv):
        with patch("pepip.installer._uv_executable", return_value="uv"):
            with patch("pepip.installer._site_packages") as mock_sp:
                mock_sp.return_value = global_site
                with patch("subprocess.run", side_effect=fake_run):
                    install(requirements_file=str(req_file), local_venv=local_venv)

    install_call = next(c for c in run_calls if "install" in c)
    assert "-r" in install_call
    assert str(req_file) in install_call
    assert "--target" in install_call


def test_install_reuses_existing_uv_environment(tmp_path: Path) -> None:
    if not symlinks_supported(tmp_path):
        pytest.skip("symlinks are not available in this environment")

    global_venv = tmp_path / "global-venv"
    global_venv.mkdir()

    local_venv = tmp_path / ".venv"
    local_venv.mkdir()
    local_site = _site_packages(local_venv)
    local_site.mkdir(parents=True)

    run_calls = []

    def fake_run(cmd, **kwargs):
        run_calls.append(cmd)
        if "install" in cmd:
            target = Path(cmd[cmd.index("--target") + 1])
            write_fake_dist(target, "requests", "2.26.0")
        return MagicMock(returncode=0)

    with patch.object(installer, "GLOBAL_VENV", global_venv):
        with patch("pepip.installer._uv_executable", return_value="uv"):
            with patch("pepip.installer._site_packages", return_value=local_site):
                with patch("subprocess.run", side_effect=fake_run):
                    linked_entries = install(
                        packages=["requests"], local_venv=local_venv
                    )

    assert "requests" in linked_entries
    assert (local_site / "requests").is_symlink()
    assert ["uv", "venv", str(local_venv)] not in run_calls


def test_install_prefers_existing_local_venv_python_for_resolution(
    tmp_path: Path,
) -> None:
    if not symlinks_supported(tmp_path):
        pytest.skip("symlinks are not available in this environment")

    global_venv = tmp_path / "global-venv"
    global_venv.mkdir()

    local_venv = tmp_path / ".venv"
    local_venv.mkdir()
    local_site = _site_packages(local_venv)
    local_site.mkdir(parents=True)

    local_python = installer._python_in_venv(local_venv)
    local_python.parent.mkdir(parents=True, exist_ok=True)
    local_python.touch()

    global_python = installer._python_in_venv(global_venv)
    global_python.parent.mkdir(parents=True, exist_ok=True)
    global_python.touch()

    run_calls = []

    def fake_run(cmd, **kwargs):
        run_calls.append(cmd)
        if "install" in cmd:
            target = Path(cmd[cmd.index("--target") + 1])
            write_fake_dist(target, "numpy", "2.0")
        return MagicMock(returncode=0, stdout="cpython-310-linux-x86_64\n")

    with patch.object(installer, "GLOBAL_VENV", global_venv):
        with patch("pepip.installer._uv_executable", return_value="uv"):
            with patch("pepip.installer._site_packages", return_value=local_site):
                with patch("subprocess.run", side_effect=fake_run):
                    install(packages=["numpy"], local_venv=local_venv)

    install_call = next(c for c in run_calls if "install" in c)
    python_arg = install_call[install_call.index("--python") + 1]
    assert Path(python_arg) == local_python
    assert Path(python_arg) != global_python


def test_install_in_existing_uv_environment_is_importable(tmp_path: Path) -> None:
    if not symlinks_supported(tmp_path):
        pytest.skip("symlinks are not available in this environment")

    global_venv = tmp_path / "global-venv"
    global_venv.mkdir()

    local_venv = tmp_path / ".venv"
    local_venv.mkdir()
    local_site = _site_packages(local_venv)
    local_site.mkdir(parents=True)

    def fake_run(cmd, **kwargs):
        if "install" in cmd:
            target = Path(cmd[cmd.index("--target") + 1])
            write_fake_dist(target, "requests", "2.26.0")
        return MagicMock(returncode=0)

    with patch.object(installer, "GLOBAL_VENV", global_venv):
        with patch("pepip.installer._uv_executable", return_value="uv"):
            with patch("pepip.installer._site_packages", return_value=local_site):
                with patch("subprocess.run", side_effect=fake_run):
                    install(packages=["requests"], local_venv=local_venv)

    import_env = dict(os.environ)
    existing_pythonpath = import_env.get("PYTHONPATH")
    import_env["PYTHONPATH"] = (
        str(local_site)
        if not existing_pythonpath
        else os.pathsep.join([str(local_site), existing_pythonpath])
    )
    import_check = subprocess.run(
        [sys.executable, "-c", "import requests; print(requests.__version__)"],
        capture_output=True,
        text=True,
        env=import_env,
        check=True,
    )
    assert import_check.stdout.strip() == "2.26.0"


def test_different_projects_keep_different_package_versions(tmp_path: Path) -> None:
    if not symlinks_supported(tmp_path):
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
            write_fake_dist(target, "requests", version)
        return MagicMock(returncode=0)

    def fake_site_packages(venv):
        return project_a_site if venv == project_a_venv else project_b_site

    with patch.object(installer, "GLOBAL_VENV", global_venv):
        with patch("pepip.installer._uv_executable", return_value="uv"):
            with patch(
                "pepip.installer._site_packages", side_effect=fake_site_packages
            ):
                with patch("subprocess.run", side_effect=fake_run):
                    install(packages=["requests==2.25.1"], local_venv=project_a_venv)
                    install(packages=["requests==2.26.0"], local_venv=project_b_venv)

    project_a_requests = project_a_site / "requests"
    project_b_requests = project_b_site / "requests"

    assert project_a_requests.is_symlink()
    assert project_b_requests.is_symlink()
    assert project_a_requests.resolve() != project_b_requests.resolve()
    assert "2.25.1" in (project_a_requests / "__init__.py").read_text()
    assert "2.26.0" in (project_b_requests / "__init__.py").read_text()
    assert (project_a_site / "requests-2.25.1.dist-info").is_symlink()
    assert (project_b_site / "requests-2.26.0.dist-info").is_symlink()


def test_reinstalling_project_replaces_stale_version_metadata(tmp_path: Path) -> None:
    if not symlinks_supported(tmp_path):
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
            write_fake_dist(target, "requests", version)
        return MagicMock(returncode=0)

    with patch.object(installer, "GLOBAL_VENV", global_venv):
        with patch("pepip.installer._uv_executable", return_value="uv"):
            with patch("pepip.installer._site_packages", return_value=local_site):
                with patch("subprocess.run", side_effect=fake_run):
                    install(packages=["requests==2.25.1"], local_venv=local_venv)
                    install(packages=["requests==2.26.0"], local_venv=local_venv)

    assert "2.26.0" in ((local_site / "requests") / "__init__.py").read_text()
    assert not (local_site / "requests-2.25.1.dist-info").exists()
    assert (local_site / "requests-2.26.0.dist-info").is_symlink()
