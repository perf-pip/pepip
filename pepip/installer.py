"""Core installer logic for pepip.

Workflow
--------
1. Ensure a shared global virtual environment exists at ``~/.pepip/global-venv``.
2. Install the requested packages into that global venv using ``uv pip install``.
3. Ensure a project-local ``.venv`` exists (created with ``uv venv``).
4. For every package entry that was added to the global site-packages, create
   a symlink inside the local site-packages directory pointing to the global one.

This mirrors the ``pnpm`` approach for Node.js: packages live in a single
content-addressable store and are accessed from projects via symlinks, saving
download time and disk space.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Configurable paths
# ---------------------------------------------------------------------------

#: Root directory for pepip's global state.
PEPIP_HOME: Path = Path(os.environ.get("PEPIP_HOME", Path.home() / ".pepip"))

#: Shared global virtual environment that stores all installed packages.
GLOBAL_VENV: Path = PEPIP_HOME / "global-venv"


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
    candidate = Path(sys.executable).parent / "uv"
    if candidate.is_file():
        return str(candidate)

    # 2. Anywhere on PATH.
    found = shutil.which("uv")
    if found:
        return found

    raise FileNotFoundError(
        "Could not find the 'uv' executable. "
        "Install it with:  pip install uv  or  curl -LsSf https://astral.sh/uv/install.sh | sh"
    )


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
    local_site.mkdir(parents=True, exist_ok=True)
    for name in entries:
        global_entry = global_site / name
        local_entry = local_site / name

        if not global_entry.exists():
            continue

        if local_entry.is_symlink():
            if local_entry.resolve() == global_entry.resolve():
                # Already correct — nothing to do.
                continue
            # Outdated or broken symlink — replace.
            local_entry.unlink()
        elif local_entry.exists():
            # A real file/directory exists here — do not overwrite it.
            continue

        local_entry.symlink_to(global_entry)


def install(
    packages: list[str] | None = None,
    requirements_file: str | None = None,
    local_venv: Path | None = None,
) -> set[str]:
    """Install packages into the global venv and symlink them into the local venv.

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
        Names of the site-packages entries that were newly added to the global
        environment and linked into the local environment.

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

    # 1. Ensure global venv exists.
    ensure_global_venv()
    global_site = _site_packages(GLOBAL_VENV)

    # 2. Snapshot site-packages before installation.
    before = _entries(global_site)

    # 3. Install packages into the global venv via uv.
    cmd: list[str] = [
        uv,
        "pip",
        "install",
        "--python",
        str(_python_in_venv(GLOBAL_VENV)),
    ]
    if packages:
        cmd.extend(packages)
    if requirements_file:
        cmd.extend(["-r", requirements_file])

    subprocess.run(cmd, check=True)

    # 4. Determine which entries are new.
    after = _entries(global_site)
    new_entries = after - before

    # 5. Ensure the local venv exists.
    ensure_local_venv(local_venv)
    local_site = _site_packages(local_venv)

    # 6. Symlink new entries into the local venv.
    link_packages(global_site, local_site, new_entries)

    return new_entries
