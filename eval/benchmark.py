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

* **pepip** — resolved package versions are stored once in a shared immutable
  store; each project's ``.venv`` contains only cheap symlinks to that store.

Usage
-----
Run from the repository root::

    python eval/benchmark.py

Optional flags::

    --projects N      Number of simulated projects (default: 5)
    --packages PKG…   Space-separated package list
                      (default: tomli packaging requests numpy pandas)
    --no-cleanup      Keep temporary directories after the run for inspection

Output example::

┌────────────┬─────────────┬────────┬─────────────┐
│  Metric    │  uv         │ pepip  │ Improvement │
├────────────┼─────────────┼────────┼─────────────┤
│  Latency   │  0.56 s     │ 0.33 s │ -41.3 %     │
│  Disk      │  475.19 MB  │ 95 MB  │ -80.0 %     │
└────────────┴─────────────┴────────┴─────────────┘

  ⏱  pepip saved 0.23 s of install time across 5 project(s).
  💾  pepip saved 379.97 MB of disk space across 5 project(s).

  ★ = better result

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
import os
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
    raise FileNotFoundError("Could not find 'uv'. Install it with:  pip install uv")


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


def _run_id() -> str:
    """Return a collision-resistant run id for benchmark work directories."""
    stamp = time.strftime("%Y%m%d-%H%M%S")
    return f"{stamp}-{os.getpid()}"


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
    total_bytes = sum(_du(p / ".venv") for p in projects)
    return EvalResult(label="uv (baseline)", elapsed_s=elapsed, disk_bytes=total_bytes)


def _run_pepip(
    projects: list[Path],
    packages: list[str],
    uv: str,
    state_root: Path,
) -> EvalResult:
    """Install *packages* using pepip's shared package-version store."""
    # Import here so this script can run both with editable install and from source.
    try:
        import pepip.installer as installer
    except ImportError:
        repo_root = Path(__file__).resolve().parents[1]
        sys.path.insert(0, str(repo_root))
        try:
            import pepip.installer as installer
        except ImportError as final_exc:
            raise SystemExit(
                f"Cannot import pepip: {final_exc}\n"
                f"Run:  {sys.executable} -m pip install -e .  from {repo_root}"
            ) from final_exc

    start = time.perf_counter()

    old_global_venv = installer.GLOBAL_VENV
    old_uv_executable = installer._uv_executable
    installer.GLOBAL_VENV = state_root / "global-venv"
    installer._uv_executable = lambda: uv
    try:
        for project in projects:
            installer.install(
                packages=packages,
                local_venv=project / ".venv",
            )
    finally:
        installer.GLOBAL_VENV = old_global_venv
        installer._uv_executable = old_uv_executable

    elapsed = time.perf_counter() - start

    # Disk: count only virtual environment directories.
    total_bytes = _du(state_root / "global-venv") + sum(
        _du(project / ".venv") for project in projects
    )
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
            _fmt_seconds(pepip_result.elapsed_s)
            + (" ★" if pepip_result.elapsed_s < baseline.elapsed_s else ""),
            _pct_change(baseline.elapsed_s, pepip_result.elapsed_s),
        ),
        (
            "Disk usage",
            _fmt_bytes(baseline.disk_bytes),
            _fmt_bytes(pepip_result.disk_bytes)
            + (" ★" if pepip_result.disk_bytes < baseline.disk_bytes else ""),
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
        return (
            "│" + "│".join(_cell(c, col_widths[i]) for i, c in enumerate(cells)) + "│"
        )

    top_border = "┌" + "┬".join("─" * w for w in col_widths) + "┐"
    header_border = "├" + "┼".join("─" * w for w in col_widths) + "┤"
    bottom_border = "└" + "┴".join("─" * w for w in col_widths) + "┘"
    title_line = "│" + f"  {title}  ".center(inner_width) + "│"
    title_sep = "├" + "┬".join("─" * w for w in col_widths) + "┤"

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
        print(
            f"  ⏱  pepip saved {_fmt_seconds(latency_saved)} of install time "
            f"across {n_projects} project(s)."
        )
    else:
        print(
            f"  ⏱  pepip was {_fmt_seconds(-latency_saved)} slower than uv "
            f"for {n_projects} project(s)."
        )
        print(
            "     (Expected for n=1; savings grow with more projects sharing "
            "the same packages.)"
        )
    if storage_saved > 0:
        print(
            f"  💾  pepip saved {_fmt_bytes(storage_saved)} of disk space "
            f"across {n_projects} project(s)."
        )
    else:
        print(f"  💾  pepip used {_fmt_bytes(-storage_saved)} more disk space than uv.")
        print(
            "     (Expected for n=1; savings grow with more projects sharing "
            "the same packages.)"
        )
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
        default=5,
        metavar="N",
        help="Number of simulated projects (default: 5)",
    )
    parser.add_argument(
        "--packages",
        nargs="+",
        default=["tomli", "packaging", "requests", "numpy", "pandas"],
        metavar="PKG",
        help=(
            "Packages to install in each project "
            "(default: tomli packaging requests numpy pandas)"
        ),
    )
    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Keep temporary directories after the run for inspection",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    if args.projects < 1:
        raise SystemExit("--projects must be >= 1")

    uv = _uv()

    # Keep benchmark work under a stable parent so repeated invocations in the
    # same environment never collide with one another.
    root_parent = Path(tempfile.gettempdir()) / "pepip-eval-runs"
    root_parent.mkdir(parents=True, exist_ok=True)
    run_root = root_parent / f"run-{_run_id()}"
    run_root.mkdir(parents=True)

    baseline_root = run_root / "baseline"
    pepip_root = run_root / "pepip"

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

    try:
        print(
            f"\nBenchmarking {args.projects} project(s) with packages: "
            f"{' '.join(args.packages)}"
        )
        print("Running uv baseline  …", flush=True)
        baseline = _run_uv_baseline(baseline_projects, args.packages, uv)

        print("Running pepip         …", flush=True)
        pepip_result = _run_pepip(pepip_projects, args.packages, uv, pepip_root)

        _print_table(args.projects, args.packages, baseline, pepip_result)

        if args.no_cleanup:
            dest = Path("pepip-eval-results") / run_root.name
            if dest.exists():
                shutil.rmtree(dest)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(run_root, dest, symlinks=True)
            print(f"Results kept in: {dest.resolve()}")
    finally:
        if not args.no_cleanup and run_root.exists():
            shutil.rmtree(run_root)


if __name__ == "__main__":
    main()
