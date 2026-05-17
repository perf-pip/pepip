"""Tests for link_packages behavior and invariants.

Confirms that symlink creation, replacement, and non-overwrite rules are
respected when linking packages into a local venv site-packages directory.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from pepip.installer import link_packages
from tests.installer.helpers import symlinks_supported


def test_creates_symlinks_for_new_entries(tmp_path: Path) -> None:
    if not symlinks_supported(tmp_path):
        pytest.skip("symlinks are not available in this environment")

    global_site = tmp_path / "global" / "site-packages"
    global_site.mkdir(parents=True)
    local_site = tmp_path / "local" / "site-packages"
    local_site.mkdir(parents=True)

    pkg_dir = global_site / "numpy"
    pkg_dir.mkdir()
    dist_info = global_site / "numpy-1.24.dist-info"
    dist_info.mkdir()

    link_packages(global_site, local_site, {"numpy", "numpy-1.24.dist-info"})

    assert (local_site / "numpy").is_symlink()
    assert (local_site / "numpy").resolve() == pkg_dir.resolve()
    assert (local_site / "numpy-1.24.dist-info").is_symlink()


def test_replaces_outdated_symlink(tmp_path: Path) -> None:
    if not symlinks_supported(tmp_path):
        pytest.skip("symlinks are not available in this environment")

    global_site = tmp_path / "global" / "site-packages"
    global_site.mkdir(parents=True)
    local_site = tmp_path / "local" / "site-packages"
    local_site.mkdir(parents=True)

    pkg_dir = global_site / "numpy"
    pkg_dir.mkdir()

    other = tmp_path / "other"
    other.mkdir()
    (local_site / "numpy").symlink_to(other)

    link_packages(global_site, local_site, {"numpy"})

    assert (local_site / "numpy").resolve() == pkg_dir.resolve()


def test_leaves_correct_symlink_unchanged(tmp_path: Path) -> None:
    if not symlinks_supported(tmp_path):
        pytest.skip("symlinks are not available in this environment")

    global_site = tmp_path / "global" / "site-packages"
    global_site.mkdir(parents=True)
    local_site = tmp_path / "local" / "site-packages"
    local_site.mkdir(parents=True)

    pkg_dir = global_site / "numpy"
    pkg_dir.mkdir()
    (local_site / "numpy").symlink_to(pkg_dir)

    link_packages(global_site, local_site, {"numpy"})

    assert (local_site / "numpy").resolve() == pkg_dir.resolve()


def test_does_not_overwrite_real_directory(tmp_path: Path) -> None:
    global_site = tmp_path / "global" / "site-packages"
    global_site.mkdir(parents=True)
    local_site = tmp_path / "local" / "site-packages"
    local_site.mkdir(parents=True)

    pkg_dir = global_site / "numpy"
    pkg_dir.mkdir()

    real_local = local_site / "numpy"
    real_local.mkdir()

    link_packages(global_site, local_site, {"numpy"})

    assert not real_local.is_symlink()
    assert real_local.is_dir()


def test_skips_missing_global_entry(tmp_path: Path) -> None:
    global_site = tmp_path / "global" / "site-packages"
    global_site.mkdir(parents=True)
    local_site = tmp_path / "local" / "site-packages"
    local_site.mkdir(parents=True)

    link_packages(global_site, local_site, {"ghost_package"})

    assert not (local_site / "ghost_package").exists()


def test_creates_local_site_if_missing(tmp_path: Path) -> None:
    if not symlinks_supported(tmp_path):
        pytest.skip("symlinks are not available in this environment")

    global_site = tmp_path / "global" / "site-packages"
    global_site.mkdir(parents=True)
    local_site = tmp_path / "local" / "site-packages"

    pkg_dir = global_site / "numpy"
    pkg_dir.mkdir()

    link_packages(global_site, local_site, {"numpy"})

    assert local_site.is_dir()
    assert (local_site / "numpy").is_symlink()


def test_raises_when_local_site_creation_fails(tmp_path: Path) -> None:
    global_site = tmp_path / "global" / "site-packages"
    global_site.mkdir(parents=True)
    local_site = tmp_path / "local" / "site-packages"

    with patch.object(Path, "mkdir", side_effect=PermissionError("denied")):
        with pytest.raises(RuntimeError, match="Failed to prepare local site-packages"):
            link_packages(global_site, local_site, {"numpy"})


def test_raises_when_replacing_symlink_fails(tmp_path: Path) -> None:
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
        with pytest.raises(RuntimeError, match="Failed to replace existing symlink"):
            link_packages(global_site, local_site, {"numpy"})


def test_raises_when_symlink_creation_fails(tmp_path: Path) -> None:
    global_site = tmp_path / "global" / "site-packages"
    global_site.mkdir(parents=True)
    local_site = tmp_path / "local" / "site-packages"
    local_site.mkdir(parents=True)

    pkg_dir = global_site / "numpy"
    pkg_dir.mkdir()

    with patch("pepip.installer._create_symlink", side_effect=OSError("unsupported")):
        with pytest.raises(RuntimeError, match="Failed to create symlink"):
            link_packages(global_site, local_site, {"numpy"})
