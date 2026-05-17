"""Tests for distribution metadata and ownership discovery.

Validates normalization rules, metadata parsing from dist-info entries, and
record processing so pepip can reliably map distributions to their files.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pepip.installer import (
    _dist_name_from_info_entry,
    _metadata_from_dist_info,
    _normalize_dist_name,
    _record_roots,
    _safe_store_name,
)


def test_normalize_dist_name_collapses_pep503_separators() -> None:
    assert _normalize_dist_name("My_Pkg.Name--Extra") == "my-pkg-name-extra"


def test_safe_store_name_normalizes_name_and_sanitizes_version() -> None:
    assert _safe_store_name("My_Pkg", "1.0 local/build") == "my-pkg-1.0_local_build"


def test_metadata_from_dist_info_prefers_metadata_file(tmp_path: Path) -> None:
    dist_info = tmp_path / "bad_filename.dist-info"
    dist_info.mkdir()
    (dist_info / "METADATA").write_text(
        "Metadata-Version: 2.1\nName: Requests-Toolbelt\nVersion: 1.0.0\n",
        encoding="utf-8",
    )

    assert _metadata_from_dist_info(dist_info) == ("Requests-Toolbelt", "1.0.0")


def test_metadata_from_dist_info_falls_back_to_directory_name(tmp_path: Path) -> None:
    dist_info = tmp_path / "requests_toolbelt-1.0.0.dist-info"
    dist_info.mkdir()

    assert _metadata_from_dist_info(dist_info) == ("requests_toolbelt", "1.0.0")


def test_metadata_from_dist_info_rejects_unparseable_directory_name(
    tmp_path: Path,
) -> None:
    dist_info = tmp_path / "broken.dist-info"
    dist_info.mkdir()

    with pytest.raises(ValueError, match="Could not determine package metadata"):
        _metadata_from_dist_info(dist_info)


def test_dist_name_from_info_entry_prefers_metadata_name(tmp_path: Path) -> None:
    dist_info = tmp_path / "anything-0.dist-info"
    dist_info.mkdir()
    (dist_info / "METADATA").write_text("Name: Actual.Name\n", encoding="utf-8")

    assert _dist_name_from_info_entry(dist_info) == "Actual.Name"


def test_dist_name_from_info_entry_parses_dist_and_egg_info_names(
    tmp_path: Path,
) -> None:
    dist_info = tmp_path / "requests_toolbelt-1.0.0.dist-info"
    egg_info = tmp_path / "single_name.egg-info"
    dist_info.mkdir()
    egg_info.mkdir()

    assert _dist_name_from_info_entry(dist_info) == "requests_toolbelt"
    assert _dist_name_from_info_entry(egg_info) == "single_name"


def test_dist_name_from_info_entry_returns_none_for_unknown_entry(
    tmp_path: Path,
) -> None:
    entry = tmp_path / "requests"
    entry.mkdir()

    assert _dist_name_from_info_entry(entry) is None


def test_record_roots_includes_dist_info_top_level_packages_and_modules(
    tmp_path: Path,
) -> None:
    site = tmp_path / "site-packages"
    site.mkdir()
    (site / "package_dir").mkdir()
    (site / "module_file.py").write_text("", encoding="utf-8")
    dist_info = site / "example-1.0.dist-info"
    dist_info.mkdir()
    (dist_info / "top_level.txt").write_text(
        "package_dir\nmodule_file\nmissing_entry\n\n",
        encoding="utf-8",
    )
    (dist_info / "RECORD").write_text("", encoding="utf-8")

    assert _record_roots(dist_info, site) == {
        "example-1.0.dist-info",
        "package_dir",
        "module_file.py",
    }


def test_record_roots_filters_unsafe_generated_and_missing_record_entries(
    tmp_path: Path,
) -> None:
    site = tmp_path / "site-packages"
    site.mkdir()
    (site / "owned_pkg").mkdir()
    (site / "owned_module.py").write_text("", encoding="utf-8")
    (site / "scripts").mkdir()
    dist_info = site / "example-1.0.dist-info"
    dist_info.mkdir()
    (dist_info / "RECORD").write_text(
        "\n".join(
            [
                "owned_pkg/__init__.py,,",
                "owned_module.py,,",
                "missing_pkg/__init__.py,,",
                "bin/example,,",
                "__pycache__/owned.cpython.pyc,,",
                "example-1.0.data/scripts/example,,",
                "/absolute/path.py,,",
                "../escape.py,,",
            ]
        ),
        encoding="utf-8",
    )

    assert _record_roots(dist_info, site) == {
        "example-1.0.dist-info",
        "owned_pkg",
        "owned_module.py",
    }


def test_record_roots_handles_missing_record_file(tmp_path: Path) -> None:
    site = tmp_path / "site-packages"
    site.mkdir()
    dist_info = site / "example-1.0.dist-info"
    dist_info.mkdir()

    assert _record_roots(dist_info, site) == {"example-1.0.dist-info"}
