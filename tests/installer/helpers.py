"""Shared test helpers for installer-focused tests.

Provides utilities for symlink capability detection, test site-packages setup,
and generation of fake distributions used across the installer test suite.
"""

from __future__ import annotations

from pathlib import Path

from pepip.installer import _create_symlink, _site_packages


def symlinks_supported(tmp_path: Path) -> bool:
    probe_target = tmp_path / "symlink-target"
    probe_target.mkdir()
    probe_link = tmp_path / "symlink-link"
    try:
        _create_symlink(probe_link, probe_target)
    except OSError:
        return False
    probe_link.unlink()
    return True


def make_global_site(base: Path) -> Path:
    site = _site_packages(base / "global-venv")
    site.mkdir(parents=True)
    return site


def write_fake_dist(
    site: Path, name: str, version: str, module_name: str | None = None
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
