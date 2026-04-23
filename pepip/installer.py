"""Core installer logic for pepip.

Workflow
--------
1. Ensure a shared build virtual environment exists at ``~/.pepip/global-venv``.
2. Install the requested packages into a temporary target directory using
   ``uv pip install`` and uv's shared cache.
3. Copy each resolved distribution version into an immutable shared package
   store under ``~/.pepip/packages`` if it is not already present.
4. Ensure a project-local ``.venv`` exists (created with ``uv venv``).
5. Symlink the resolved package entries from the immutable store into the local
   site-packages directory.

This mirrors the ``pnpm`` approach for Node.js: packages live in a single
content-addressable store and are accessed from projects via symlinks, saving
download time and disk space.
"""

from __future__ import annotations

import csv
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from email.parser import Parser
from pathlib import Path, PurePosixPath

# ---------------------------------------------------------------------------
# Configurable paths
# ---------------------------------------------------------------------------

#: Root directory for pepip's global state.
PEPIP_HOME: Path = Path(os.environ.get("PEPIP_HOME", Path.home() / ".pepip"))

#: Shared virtual environment used as the Python interpreter for target installs.
GLOBAL_VENV: Path = PEPIP_HOME / "global-venv"


@dataclass
class StoredDistribution:
    """A resolved distribution and the top-level entries it owns."""

    name: str
    version: str
    entries: set[str]
    store_path: Path


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _uv_executable() -> str:
    """Return the path to the ``uv`` executable.

    Prefers the ``uv`` binary that ships with the ``uv`` PyPI package (located
    next to this Python interpreter) so that pepip works even when ``uv`` is not
    on ``PATH``.

    Raises
    ------
    FileNotFoundError
        If ``uv`` cannot be found.
    """
    import shutil

    # 1. Same directory as the current Python interpreter (common when uv is
    #    installed inside a venv via ``pip install uv``).
    candidate_name = "uv.exe" if sys.platform == "win32" else "uv"
    candidate = Path(sys.executable).parent / candidate_name
    if candidate.is_file():
        return str(candidate)

    # 2. Anywhere on PATH.
    found = shutil.which("uv")
    if found:
        return found

    raise FileNotFoundError(
        "Could not find the 'uv' executable. "
        "Install it with:  pip install uv  or  "
        "curl -LsSf https://astral.sh/uv/install.sh | sh"
    )


def _create_symlink(link_path: Path, target_path: Path) -> None:
    """Create *link_path* pointing at *target_path* with Windows dir support."""
    target_is_directory = target_path.is_dir() and not target_path.is_symlink()
    link_path.symlink_to(target_path, target_is_directory=target_is_directory)


def _python_in_venv(venv: Path) -> Path:
    """Return the path to the Python binary inside *venv*."""
    if sys.platform == "win32":
        return venv / "Scripts" / "python.exe"
    return venv / "bin" / "python"


def _site_packages(venv: Path) -> Path:
    """Return the ``site-packages`` directory inside *venv*.

    The directory is discovered by running the venv's own Python interpreter so
    the result is always correct regardless of platform or Python version.  If
    the interpreter is not yet available (venv not yet created) we fall back to
    a best-effort constructed path.
    """
    python = _python_in_venv(venv)
    if python.exists():
        result = subprocess.run(
            [
                str(python),
                "-c",
                "import sysconfig; print(sysconfig.get_path('purelib'))",
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            return Path(result.stdout.strip())

    # Fallback for when the venv does not yet exist.
    if sys.platform == "win32":
        return venv / "Lib" / "site-packages"
    py_tag = f"python{sys.version_info.major}.{sys.version_info.minor}"
    return venv / "lib" / py_tag / "site-packages"


def _entries(site_packages: Path) -> set[str]:
    """Return the set of directory/file names inside *site_packages*."""
    if not site_packages.exists():
        return set()
    return {entry.name for entry in site_packages.iterdir()}


def _normalize_dist_name(name: str) -> str:
    """Return a normalized package name per PEP 503."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _package_store_root(python: Path | None = None) -> Path:
    """Return the Python/platform-specific root for immutable package entries."""
    scope = None
    if python and python.exists():
        result = subprocess.run(
            [
                str(python),
                "-c",
                (
                    "import platform, sys; "
                    "print(f'{sys.implementation.cache_tag}-"
                    "{sys.platform}-{platform.machine() or \"unknown\"}')"
                ),
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0 and result.stdout.strip():
            scope = result.stdout.strip()

    if scope is None:
        cache_tag = sys.implementation.cache_tag or (
            f"py{sys.version_info.major}{sys.version_info.minor}"
        )
        try:
            machine = platform.machine() or "unknown"
        except Exception:  # noqa: BLE001
            machine = "unknown"
        scope = f"{cache_tag}-{sys.platform}-{machine}"

    safe_scope = re.sub(r"[^A-Za-z0-9_.-]+", "_", scope)
    return GLOBAL_VENV.parent / "packages" / safe_scope


def _safe_store_name(name: str, version: str) -> str:
    normalized = _normalize_dist_name(name)
    safe_version = re.sub(r"[^A-Za-z0-9_.!+-]+", "_", version)
    return f"{normalized}-{safe_version}"


def _metadata_from_dist_info(dist_info: Path) -> tuple[str, str]:
    """Read distribution name/version from a ``.dist-info`` directory."""
    metadata = dist_info / "METADATA"
    if metadata.exists():
        message = Parser().parsestr(
            metadata.read_text(encoding="utf-8", errors="replace")
        )
        name = message.get("Name")
        version = message.get("Version")
        if name and version:
            return name, version

    stem = dist_info.name[: -len(".dist-info")]
    name, separator, version = stem.rpartition("-")
    if not separator or not name or not version:
        raise ValueError(f"Could not determine package metadata for {dist_info}")
    return name, version


def _record_roots(dist_info: Path, site_packages: Path) -> set[str]:
    """Return top-level site-package entries owned by a distribution."""
    entries = {dist_info.name}

    top_level = dist_info / "top_level.txt"
    if top_level.exists():
        top_level_text = top_level.read_text(encoding="utf-8", errors="replace")
        for line in top_level_text.splitlines():
            name = line.strip()
            if not name:
                continue
            for candidate in (name, f"{name}.py"):
                if (site_packages / candidate).exists():
                    entries.add(candidate)

    record = dist_info / "RECORD"
    if not record.exists():
        return entries

    with record.open(encoding="utf-8", errors="replace", newline="") as record_file:
        for row in csv.reader(record_file):
            if not row:
                continue

            path = PurePosixPath(row[0])
            if path.is_absolute() or ".." in path.parts or not path.parts:
                continue

            root = path.parts[0]
            if root in {"bin", "__pycache__"} or root.endswith(".data"):
                continue
            if (site_packages / root).exists():
                entries.add(root)

    return entries


def _copy_entries(source_site: Path, destination_site: Path, entries: set[str]) -> None:
    """Copy selected top-level entries from one site-packages tree to another."""
    destination_site.mkdir(parents=True, exist_ok=True)
    for name in sorted(entries):
        source = source_site / name
        destination = destination_site / name
        if not source.exists() or destination.exists():
            continue
        if source.is_dir() and not source.is_symlink():
            shutil.copytree(source, destination, symlinks=True)
        else:
            shutil.copy2(source, destination, follow_symlinks=False)


def _store_distribution(
    staging_site: Path, dist_info: Path, store_root: Path
) -> StoredDistribution:
    """Ensure one resolved distribution is present in the immutable store."""
    name, version = _metadata_from_dist_info(dist_info)
    entries = _record_roots(dist_info, staging_site)
    store_path = store_root / _safe_store_name(name, version)

    if not store_path.exists():
        store_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(
            dir=store_path.parent, prefix=f".{store_path.name}."
        ) as tmp_dir:
            candidate = Path(tmp_dir) / "package"
            _copy_entries(staging_site, candidate, entries)
            try:
                candidate.rename(store_path)
            except FileExistsError:
                # Another pepip process stored the same immutable package first.
                pass

    return StoredDistribution(
        name=name, version=version, entries=entries, store_path=store_path
    )


def _store_resolved_distributions(
    staging_site: Path, python: Path | None = None
) -> list[StoredDistribution]:
    """Store every resolved distribution from a target install."""
    store_root = _package_store_root(python)
    distributions = []

    for dist_info in sorted(staging_site.glob("*.dist-info")):
        distributions.append(_store_distribution(staging_site, dist_info, store_root))

    if not distributions:
        raise RuntimeError(f"No distributions were installed into {staging_site}")

    return distributions


def _dist_name_from_info_entry(entry: Path) -> str | None:
    metadata = entry / "METADATA"
    if metadata.exists():
        message = Parser().parsestr(
            metadata.read_text(encoding="utf-8", errors="replace")
        )
        name = message.get("Name")
        if name:
            return name

    for suffix in (".dist-info", ".egg-info"):
        if entry.name.endswith(suffix):
            stem = entry.name[: -len(suffix)]
            name, separator, _version = stem.rpartition("-")
            return name if separator else stem

    return None


def _remove_stale_distribution_links(
    local_site: Path, dist_names: set[str], keep_entries: set[str]
) -> None:
    """Remove old symlinked metadata for distributions being relinked."""
    if not local_site.exists():
        return

    normalized_names = {_normalize_dist_name(name) for name in dist_names}
    for entry in local_site.iterdir():
        if entry.name in keep_entries or not entry.is_symlink():
            continue
        if not (entry.name.endswith(".dist-info") or entry.name.endswith(".egg-info")):
            continue

        dist_name = _dist_name_from_info_entry(entry)
        if dist_name and _normalize_dist_name(dist_name) in normalized_names:
            entry.unlink()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def ensure_global_venv() -> Path:
    """Create the global virtual environment if it does not already exist.

    Returns
    -------
    Path
        The path to the global virtual environment.
    """
    if not GLOBAL_VENV.exists():
        GLOBAL_VENV.parent.mkdir(parents=True, exist_ok=True)
        uv = _uv_executable()
        subprocess.run([uv, "venv", str(GLOBAL_VENV)], check=True)
    return GLOBAL_VENV


def ensure_local_venv(local_venv: Path) -> Path:
    """Create the local virtual environment if it does not already exist.

    Parameters
    ----------
    local_venv:
        Path to the project-local ``.venv`` directory.

    Returns
    -------
    Path
        The resolved path to the local virtual environment.
    """
    if not local_venv.exists():
        uv = _uv_executable()
        subprocess.run([uv, "venv", str(local_venv)], check=True)
    return local_venv


def link_packages(global_site: Path, local_site: Path, entries: set[str]) -> None:
    """Create symlinks in *local_site* pointing to entries in *global_site*.

    Existing symlinks that already point to the correct global entry are left
    unchanged.  Broken or outdated symlinks are replaced.  Regular files and
    directories that are not symlinks are never touched.

    Parameters
    ----------
    global_site:
        The ``site-packages`` directory of the global virtual environment.
    local_site:
        The ``site-packages`` directory of the project-local virtual
        environment.
    entries:
        Names of entries (directories / files) inside *global_site* to link.
    """
    try:
        local_site.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise RuntimeError(f"Failed to prepare local site-packages at {local_site}") from exc

    for name in sorted(entries):
        global_entry = global_site / name
        local_entry = local_site / name

        if not global_entry.exists():
            continue

        if local_entry.is_symlink():
            if local_entry.resolve() == global_entry.resolve():
                # Already correct — nothing to do.
                continue
            # Outdated or broken symlink — replace.
            try:
                local_entry.unlink()
            except OSError as exc:
                raise RuntimeError(
                    f"Failed to replace existing symlink at {local_entry}"
                ) from exc
        elif local_entry.exists():
            # A real file/directory exists here — do not overwrite it.
            continue

        try:
            _create_symlink(local_entry, global_entry)
        except OSError as exc:
            raise RuntimeError(
                f"Failed to create symlink from {local_entry} to {global_entry}"
            ) from exc


def install(
    packages: list[str] | None = None,
    requirements_file: str | None = None,
    local_venv: Path | None = None,
) -> set[str]:
    """Install packages into the shared store and symlink them into the local venv.

    Parameters
    ----------
    packages:
        List of package specifiers, e.g. ``["numpy", "pandas>=2.0"]``.
    requirements_file:
        Path to a ``requirements.txt``-style file.
    local_venv:
        Path to the project-local virtual environment directory.  Defaults to
        ``.venv`` in the current working directory.

    Returns
    -------
    set[str]
        Names of the site-packages entries that were linked into the local
        environment.

    Raises
    ------
    ValueError
        If neither *packages* nor *requirements_file* is provided.
    FileNotFoundError
        If the ``uv`` executable cannot be found.
    subprocess.CalledProcessError
        If ``uv pip install`` exits with a non-zero status.
    """
    if not packages and not requirements_file:
        raise ValueError("Provide at least one package name or a requirements file.")

    if local_venv is None:
        local_venv = Path(".venv")

    uv = _uv_executable()

    # 1. Ensure the shared build venv exists.
    ensure_global_venv()

    GLOBAL_VENV.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=GLOBAL_VENV.parent) as staging_dir:
        staging_site = Path(staging_dir) / "site-packages"

        # 2. Resolve and install packages into an isolated target directory.
        cmd: list[str] = [
            uv,
            "pip",
            "install",
            "--python",
            str(_python_in_venv(GLOBAL_VENV)),
            "--target",
            str(staging_site),
        ]
        if packages:
            cmd.extend(packages)
        if requirements_file:
            cmd.extend(["-r", requirements_file])

        subprocess.run(cmd, check=True)

        # 3. Store each resolved distribution version immutably.
        distributions = _store_resolved_distributions(
            staging_site, _python_in_venv(GLOBAL_VENV)
        )

        # 4. Ensure the local venv exists.
        ensure_local_venv(local_venv)
        local_site = _site_packages(local_venv)

        # 5. Symlink resolved entries into the local venv.
        linked_entries: set[str] = set()
        dist_names = {distribution.name for distribution in distributions}
        for distribution in distributions:
            linked_entries.update(distribution.entries)

        _remove_stale_distribution_links(local_site, dist_names, linked_entries)
        for distribution in distributions:
            link_packages(distribution.store_path, local_site, distribution.entries)

    return linked_entries
