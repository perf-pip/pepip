"""Tests for immutable package store behavior.

Focuses on store path scoping, safe copying behavior, and distribution storage
rules to ensure the shared store remains consistent and immutable.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import pepip.installer as installer
from pepip.installer import (
    _copy_entries,
    _package_store_root,
    _store_distribution,
    _store_resolved_distributions,
)
from tests.installer.helpers import write_fake_dist


def test_package_store_root_uses_interpreter_scope_and_sanitizes_output(
    tmp_path: Path,
) -> None:
    fake_global = tmp_path / "home" / "global-venv"
    fake_python = tmp_path / "python"
    fake_python.touch()

    with patch.object(installer, "GLOBAL_VENV", fake_global):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout="cpython-314-x86_64 linux/evil\n",
            )
            result = _package_store_root(fake_python)

    assert result == fake_global.parent / "packages" / "cpython-314-x86_64_linux_evil"
    mock_run.assert_called_once()


def test_package_store_root_falls_back_when_interpreter_probe_fails(
    tmp_path: Path,
) -> None:
    fake_global = tmp_path / "home" / "global-venv"
    fake_python = tmp_path / "python"
    fake_python.touch()

    with patch.object(installer, "GLOBAL_VENV", fake_global):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=1, stdout="")
            result = _package_store_root(fake_python)

    assert result.parent == fake_global.parent / "packages"
    assert result.name


def test_copy_entries_copies_directories_files_and_preserves_existing_entries(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    (source / "pkg").mkdir()
    (source / "pkg" / "__init__.py").write_text("new", encoding="utf-8")
    (source / "module.py").write_text("new", encoding="utf-8")
    (source / "existing.py").write_text("new", encoding="utf-8")
    destination.mkdir()
    (destination / "existing.py").write_text("old", encoding="utf-8")

    _copy_entries(source, destination, {"pkg", "module.py", "existing.py", "missing"})

    assert (destination / "pkg" / "__init__.py").read_text(encoding="utf-8") == "new"
    assert (destination / "module.py").read_text(encoding="utf-8") == "new"
    assert (destination / "existing.py").read_text(encoding="utf-8") == "old"
    assert not (destination / "missing").exists()


def test_store_distribution_copies_owned_entries_once(tmp_path: Path) -> None:
    staging_site = tmp_path / "staging"
    store_root = tmp_path / "store"
    write_fake_dist(staging_site, "requests", "2.31.0")
    dist_info = staging_site / "requests-2.31.0.dist-info"

    first = _store_distribution(staging_site, dist_info, store_root)
    (first.store_path / "requests" / "__init__.py").write_text(
        "preserved", encoding="utf-8"
    )
    second = _store_distribution(staging_site, dist_info, store_root)

    assert first.name == "requests"
    assert first.version == "2.31.0"
    assert first.entries == {"requests", "requests-2.31.0.dist-info"}
    assert first.store_path == store_root / "requests-2.31.0"
    assert second.store_path == first.store_path
    assert (second.store_path / "requests" / "__init__.py").read_text(
        encoding="utf-8"
    ) == "preserved"


def test_store_distribution_handles_concurrent_create_race(tmp_path: Path) -> None:
    staging_site = tmp_path / "staging"
    store_root = tmp_path / "store"
    write_fake_dist(staging_site, "requests", "2.31.0")
    dist_info = staging_site / "requests-2.31.0.dist-info"

    with patch.object(Path, "rename", side_effect=FileExistsError):
        stored = _store_distribution(staging_site, dist_info, store_root)

    assert stored.store_path == store_root / "requests-2.31.0"


def test_store_resolved_distributions_stores_all_dist_infos(tmp_path: Path) -> None:
    staging_site = tmp_path / "staging"
    store_root = tmp_path / "store"
    write_fake_dist(staging_site, "requests", "2.31.0")
    write_fake_dist(staging_site, "urllib3", "2.0.7")

    with patch("pepip.installer._package_store_root", return_value=store_root):
        distributions = _store_resolved_distributions(staging_site)

    assert [(dist.name, dist.version) for dist in distributions] == [
        ("requests", "2.31.0"),
        ("urllib3", "2.0.7"),
    ]
    assert (store_root / "requests-2.31.0" / "requests").is_dir()
    assert (store_root / "urllib3-2.0.7" / "urllib3").is_dir()


def test_store_resolved_distributions_raises_when_install_target_is_empty(
    tmp_path: Path,
) -> None:
    staging_site = tmp_path / "staging"
    staging_site.mkdir()

    with pytest.raises(RuntimeError, match="No distributions were installed"):
        _store_resolved_distributions(staging_site)


def test_install_does_not_create_local_venv_when_uv_install_fails(
    tmp_path: Path,
) -> None:
    global_venv = tmp_path / "global-venv"
    global_venv.mkdir()
    local_venv = tmp_path / ".venv"

    with patch.object(installer, "GLOBAL_VENV", global_venv):
        with patch("pepip.installer._uv_executable", return_value="uv"):
            with patch(
                "subprocess.run",
                side_effect=subprocess.CalledProcessError(1, ["uv", "pip", "install"]),
            ):
                with patch("pepip.installer.ensure_local_venv") as mock_local:
                    with pytest.raises(subprocess.CalledProcessError):
                        installer.install(packages=["requests"], local_venv=local_venv)

    mock_local.assert_not_called()
