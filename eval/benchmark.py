"""Evaluation: pepip vs plain uv — latency and storage comparison.

This script simulates multiple projects each needing the same set of packages.
It measures and compares:

  1. **Installation latency** — total wall-clock time to set up N projects.
  2. **Disk storage** — total bytes consumed on disk after all projects are set
     up.

Two strategies are benchmarked side-by-side:

* **uv (baseline)** — each project gets its own isolated virtual environment
  created by ``uv venv`` with packages installed via ``uv pip install``.
  This is the standard workflow most developers use today.

* **pepip** — packages are installed once into a shared global environment;
  each project's ``.venv`` contains only cheap symlinks to the global copy.

Usage
-----
Run from the repository root::

    python eval/benchmark.py

Optional flags::

    --projects N      Number of simulated projects (default: 3)
    --packages PKG…   Space-separated package list (default: tomli packaging)
    --no-cleanup      Keep temporary directories after the run for inspection

Output example::

    ┌─────────────────────────────────────────────────────────────────────┐
    │  pepip vs uv — evaluation (3 projects, packages: tomli packaging)   │
    ├──────────────┬──────────────────┬──────────────────┬───────────────┤
    │  Metric      │  uv (baseline)   │  pepip            │  Improvement  │
    ├──────────────┼──────────────────┼──────────────────┼───────────────┤
    │  Latency     │  4.12 s          │  2.07 s  ★        │  -49.8 %      │
    │  Disk usage  │  12.34 MB        │  5.67 MB ★        │  -54.1 %      │
    └──────────────┴──────────────────┴──────────────────┴───────────────┘

Notes
-----
* Latency includes venv creation and package installation for all N projects.
  The pepip figure benefits from downloading packages only once.
* Disk usage is measured with ``du -sb`` (apparent bytes) so it is comparable
  across platforms and filesystem block sizes.
* For a fair comparison both strategies use the same ``uv`` backend for actual
  downloads.  The *only* difference is whether each project stores real copies
  of the package files or symlinks.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import NamedTuple


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _uv() -> str:
    """Return the path to the uv binary (raises if not found)."""
    candidate = Path(sys.executable).parent / "uv"
    if candidate.is_file():
        return str(candidate)
    found = shutil.which("uv")
    if found:
        return found
    raise FileNotFoundError(
        "Could not find 'uv'. Install it with:  pip install uv"
    )


def _du(path: Path) -> int:
    """Return the apparent size in bytes of *path* (recursive)."""
    if not path.exists():
        return 0
    result = subprocess.run(
        ["du", "--apparent-size", "--summarize", "--block-size=1", str(path)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        # Fallback: sum file sizes with Python
        return sum(
            f.stat().st_size
            for f in path.rglob("*")
            if f.is_file() and not f.is_symlink()
        )
    # du output: "<bytes>\t<path>"
    return int(result.stdout.split()[0])


def _fmt_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.2f} {unit}"
        n /= 1024  # type: ignore[assignment]
    return f"{n:.2f} TB"


def _fmt_seconds(s: float) -> str:
    return f"{s:.2f} s"


def _pct_change(baseline: float, new: float) -> str:
    if baseline == 0:
        return "N/A"
    pct = (new - baseline) / baseline * 100
    sign = "+" if pct > 0 else ""
    return f"{sign}{pct:.1f} %"


# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------


class EvalResult(NamedTuple):
    label: str
    elapsed_s: float
    disk_bytes: int


def _run_uv_baseline(
    projects: list[Path],
    packages: list[str],
    uv: str,
) -> EvalResult:
    """Install *packages* into each project using a plain ``uv`` workflow.

    Each project gets its own isolated virtual environment; packages are
    downloaded and stored separately for every project.
    """
    start = time.perf_counter()
    for project in projects:
        venv = project / ".venv"
        subprocess.run([uv, "venv", str(venv)], check=True, capture_output=True)
        python = (
            venv / "Scripts" / "python.exe"
            if sys.platform == "win32"
            else venv / "bin" / "python"
        )
        subprocess.run(
            [uv, "pip", "install", "--python", str(python)] + packages,
            check=True,
            capture_output=True,
        )
    elapsed = time.perf_counter() - start
    total_bytes = sum(_du(p) for p in projects)
    return EvalResult(label="uv (baseline)", elapsed_s=elapsed, disk_bytes=total_bytes)


def _run_pepip(
    projects: list[Path],
    packages: list[str],
    uv: str,
    global_venv: Path,
) -> EvalResult:
    """Install *packages* using pepip's shared global venv + symlink approach."""
    # Import here so this script can also be run standalone without editable install.
    try:
        from pepip.installer import (
            _python_in_venv,
            _site_packages,
            _entries,
            link_packages,
        )
    except ImportError as exc:
        raise SystemExit(
            f"Cannot import pepip: {exc}\n"
            "Run:  pip install -e .  from the repository root."
        ) from exc

    start = time.perf_counter()

    # ── Step 1: create the global venv once ──────────────────────────────────
    subprocess.run([uv, "venv", str(global_venv)], check=True, capture_output=True)

    # ── Step 2: install packages into the global venv once ───────────────────
    global_python = _python_in_venv(global_venv)
    subprocess.run(
        [uv, "pip", "install", "--python", str(global_python)] + packages,
        check=True,
        capture_output=True,
    )
    global_site = _site_packages(global_venv)
    global_entries = _entries(global_site)

    # ── Step 3: for each project, create a local venv and symlink packages ───
    for project in projects:
        local_venv = project / ".venv"
        if not local_venv.exists():
            subprocess.run([uv, "venv", str(local_venv)], check=True, capture_output=True)
        local_site = _site_packages(local_venv)
        link_packages(global_site, local_site, global_entries)

    elapsed = time.perf_counter() - start

    # Disk: global venv + all project venvs (symlinks count as tiny)
    total_bytes = _du(global_venv) + sum(_du(p) for p in projects)
    return EvalResult(label="pepip", elapsed_s=elapsed, disk_bytes=total_bytes)


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


def _print_table(
    n_projects: int,
    packages: list[str],
    baseline: EvalResult,
    pepip_result: EvalResult,
) -> None:
    pkg_list = " ".join(packages)

    rows = [
        ("Metric", "uv (baseline)", "pepip", "Improvement"),
        (
            "Latency",
            _fmt_seconds(baseline.elapsed_s),
            _fmt_seconds(pepip_result.elapsed_s) + (" ★" if pepip_result.elapsed_s < baseline.elapsed_s else ""),
            _pct_change(baseline.elapsed_s, pepip_result.elapsed_s),
        ),
        (
            "Disk usage",
            _fmt_bytes(baseline.disk_bytes),
            _fmt_bytes(pepip_result.disk_bytes) + (" ★" if pepip_result.disk_bytes < baseline.disk_bytes else ""),
            _pct_change(baseline.disk_bytes, pepip_result.disk_bytes),
        ),
    ]

    # Each column is padded with 2 spaces on each side.
    col_widths = [max(len(r[i]) for r in rows) + 4 for i in range(4)]
    inner_width = sum(col_widths) + len(col_widths) - 1  # separators between cols

    title = f"pepip vs uv — evaluation ({n_projects} project(s), packages: {pkg_list})"
    # Widen columns so title fits.
    if len(title) + 4 > inner_width:
        extra = len(title) + 4 - inner_width
        col_widths[-1] += extra
        inner_width = sum(col_widths) + len(col_widths) - 1

    def _cell(text: str, width: int) -> str:
        return f"  {text:<{width - 4}}  "

    def row_str(cells: tuple[str, ...]) -> str:
        return "│" + "│".join(_cell(c, col_widths[i]) for i, c in enumerate(cells)) + "│"

    top_border    = "┌" + "┬".join("─" * w for w in col_widths) + "┐"
    header_border = "├" + "┼".join("─" * w for w in col_widths) + "┤"
    bottom_border = "└" + "┴".join("─" * w for w in col_widths) + "┘"
    title_line    = "│" + f"  {title}  ".center(inner_width) + "│"
    title_sep     = "├" + "┬".join("─" * w for w in col_widths) + "┤"

    print()
    print(top_border)
    print(title_line)
    print(title_sep)
    print(row_str(rows[0]))
    print(header_border)
    for row in rows[1:]:
        print(row_str(row))
    print(bottom_border)
    print()

    # Extra context
    latency_saved = baseline.elapsed_s - pepip_result.elapsed_s
    storage_saved = baseline.disk_bytes - pepip_result.disk_bytes
    if latency_saved > 0:
        print(f"  ⏱  pepip saved {_fmt_seconds(latency_saved)} of install time across {n_projects} project(s).")
    else:
        print(f"  ⏱  pepip was {_fmt_seconds(-latency_saved)} slower than uv for {n_projects} project(s).")
        print("     (Expected for n=1; savings grow with more projects sharing the same packages.)")
    if storage_saved > 0:
        print(f"  💾  pepip saved {_fmt_bytes(storage_saved)} of disk space across {n_projects} project(s).")
    else:
        print(f"  💾  pepip used {_fmt_bytes(-storage_saved)} more disk space than uv.")
        print("     (Expected for n=1; savings grow with more projects sharing the same packages.)")
    print()
    print("  ★ = better result")
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python eval/benchmark.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--projects",
        type=int,
        default=3,
        metavar="N",
        help="Number of simulated projects (default: 3)",
    )
    parser.add_argument(
        "--packages",
        nargs="+",
        default=["tomli", "packaging"],
        metavar="PKG",
        help="Packages to install in each project (default: tomli packaging)",
    )
    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Keep temporary directories after the run for inspection",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    uv = _uv()

    with tempfile.TemporaryDirectory(prefix="pepip-eval-") as tmpdir_str:
        tmpdir = Path(tmpdir_str)
        baseline_root = tmpdir / "baseline"
        pepip_root = tmpdir / "pepip"
        global_venv = pepip_root / "global-venv"

        # Create separate project directories for each strategy.
        baseline_projects = []
        pepip_projects = []
        for i in range(args.projects):
            bp = baseline_root / f"project-{i}"
            bp.mkdir(parents=True)
            baseline_projects.append(bp)

            pp = pepip_root / f"project-{i}"
            pp.mkdir(parents=True)
            pepip_projects.append(pp)

        print(f"\nBenchmarking {args.projects} project(s) with packages: {' '.join(args.packages)}")
        print("Running uv baseline  …", flush=True)
        baseline = _run_uv_baseline(baseline_projects, args.packages, uv)

        print("Running pepip         …", flush=True)
        pepip_result = _run_pepip(pepip_projects, args.packages, uv, global_venv)

        _print_table(args.projects, args.packages, baseline, pepip_result)

        if args.no_cleanup:
            # Move out of the auto-deleted tempdir.
            dest = Path("pepip-eval-results")
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(tmpdir_str, str(dest), symlinks=True)
            print(f"Results kept in: {dest.resolve()}")


if __name__ == "__main__":
    main()
