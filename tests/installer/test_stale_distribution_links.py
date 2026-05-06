"""Tests for cleanup of stale distribution metadata links."""

from __future__ import annotations

from pathlib import Path

import pytest

from pepip.installer import _remove_stale_distribution_links
from tests.installer.helpers import symlinks_supported


def test_remove_stale_distribution_links_removes_matching_old_metadata(
    tmp_path: Path,
) -> None:
    if not symlinks_supported(tmp_path):
        pytest.skip("symlinks are not available in this environment")

    local_site = tmp_path / "site-packages"
    local_site.mkdir()
    old_target = tmp_path / "old-target"
    old_target.mkdir()
    stale = local_site / "Requests_Toolbelt-0.9.dist-info"
    stale.symlink_to(old_target)
    (old_target / "METADATA").write_text("Name: requests-toolbelt\n", encoding="utf-8")

    _remove_stale_distribution_links(
        local_site,
        dist_names={"requests.toolbelt"},
        keep_entries=set(),
    )

    assert not stale.exists()


def test_remove_stale_distribution_links_preserves_safe_entries(
    tmp_path: Path,
) -> None:
    if not symlinks_supported(tmp_path):
        pytest.skip("symlinks are not available in this environment")

    local_site = tmp_path / "site-packages"
    local_site.mkdir()
    target = tmp_path / "target"
    target.mkdir()
    keep = local_site / "requests-2.31.dist-info"
    unrelated = local_site / "urllib3-2.dist-info"
    real = local_site / "requests-1.dist-info"
    keep.symlink_to(target)
    unrelated.symlink_to(target)
    real.mkdir()

    _remove_stale_distribution_links(
        local_site,
        dist_names={"requests"},
        keep_entries={"requests-2.31.dist-info"},
    )

    assert keep.is_symlink()
    assert unrelated.is_symlink()
    assert real.is_dir()


def test_remove_stale_distribution_links_is_noop_when_site_missing(
    tmp_path: Path,
) -> None:
    _remove_stale_distribution_links(
        tmp_path / "missing",
        dist_names={"requests"},
        keep_entries=set(),
    )
