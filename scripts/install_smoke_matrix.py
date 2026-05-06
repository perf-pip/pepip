#!/usr/bin/env python3
"""Install pinned packages in batches and run smoke checks in uv and pepip modes."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

from rich.console import Console
from rich.panel import Panel
from rich.prompt import IntPrompt
from rich.table import Table

os.environ["UV_VENV_CLEAR"] = "1"
CONSOLE = Console()
PYTHON_VERSION = "3.10"

DEFAULT_PINNED_VERSIONS = {
    "numpy": "2.1.3",
    "pandas": "2.2.3",
    "requests": "2.32.3",
    "scipy": "1.14.1",
    "matplotlib": "3.9.2",
    "scikit-learn": "1.5.2",
    "sqlalchemy": "2.0.36",
    "fastapi": "0.115.4",
    "click": "8.1.7",
    "pytest": "8.3.3",
}

SMOKE_CODE = r"""
# --- numpy ---
import numpy as np

assert np.__version__ == "2.1.3", f"unexpected numpy version: {np.__version__}"

arr = np.array([1, 2, 3, 4], dtype=np.float64)
assert np.isclose(arr.mean(), 2.5), "numpy mean check failed"


# --- pandas ---
import pandas as pd

assert pd.__version__ == "2.2.3", f"unexpected pandas version: {pd.__version__}"

frame = pd.DataFrame({"x": [1, 2, 3], "y": [10, 20, 30]})
result = frame.groupby("x", as_index=False)["y"].sum()
assert result["y"].tolist() == [10, 20, 30], "pandas groupby check failed"


# --- requests ---
import requests

assert requests.__version__ == "2.32.3", (
    f"unexpected requests version: {requests.__version__}"
)

req = requests.Request("GET", "https://example.com", params={"q": "ok"})
prepared = req.prepare()
assert "q=ok" in prepared.url, "requests prepare/url check failed"


# --- scipy ---
import scipy
from scipy import linalg

assert scipy.__version__ == "1.14.1", f"unexpected scipy version: {scipy.__version__}"

mat = np.array([[2.0, 0.0], [0.0, 5.0]])
inv = linalg.inv(mat)
assert np.allclose(inv, np.array([[0.5, 0.0], [0.0, 0.2]])), "scipy linalg check failed"


# --- matplotlib ---
import matplotlib

assert matplotlib.__version__ == "3.9.2", (
    f"unexpected matplotlib version: {matplotlib.__version__}"
)


# --- scikit-learn ---
import sklearn
from sklearn.linear_model import LinearRegression

assert sklearn.__version__ == "1.5.2", (
    f"unexpected sklearn version: {sklearn.__version__}"
)

X = np.array([[1], [2], [3], [4]], dtype=np.float64)
y = np.array([2, 4, 6, 8], dtype=np.float64)
model = LinearRegression().fit(X, y)
assert np.isclose(model.coef_[0], 2.0), "sklearn fit check failed"


# --- sqlalchemy ---
import sqlalchemy
from sqlalchemy import create_engine, text

assert sqlalchemy.__version__ == "2.0.36", (
    f"unexpected sqlalchemy version: {sqlalchemy.__version__}"
)

engine = create_engine("sqlite:///:memory:")
with engine.connect() as conn:
    value = conn.execute(text("SELECT 42")).scalar_one()
assert value == 42, "sqlalchemy sqlite check failed"


# --- fastapi ---
import fastapi

assert fastapi.__version__ == "0.115.4", (
    f"unexpected fastapi version: {fastapi.__version__}"
)

app = fastapi.FastAPI()

@app.get("/ping")
def ping():
    return {"ok": True}

assert any(route.path == "/ping" for route in app.routes), "fastapi route check failed"


# --- click ---
import click

assert click.__version__ == "8.1.7", f"unexpected click version: {click.__version__}"

@click.command()
def cmd():
    pass

assert cmd.name == "cmd", "click command check failed"


# --- pytest ---
import pytest

assert pytest.__version__ == "8.3.3", f"unexpected pytest version: {pytest.__version__}"
"""


def run(
    cmd: List[str], cwd: Path, env: Optional[Dict[str, str]] = None
) -> subprocess.CompletedProcess:
    ui_command(cmd)
    completed = subprocess.run(
        cmd,
        cwd=str(cwd),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"Command failed ({completed.returncode}): {' '.join(cmd)}\n"
            f"stdout:\n{completed.stdout}\n"
            f"stderr:\n{completed.stderr}"
        )
    return completed


def ensure_binary(name: str) -> None:
    if shutil.which(name) is None:
        raise FileNotFoundError(f"Required executable not found in PATH: {name}")


def package_batches(packages: Sequence[str], batch_size: int) -> Iterable[List[str]]:
    if batch_size < 1:
        raise ValueError("--batch-size must be greater than or equal to 1.")

    for start in range(0, len(packages), batch_size):
        yield list(packages[start : start + batch_size])


def install_batches_uv(
    work_dir: Path, packages: Sequence[str], batch_size: int
) -> None:
    for idx, batch in enumerate(package_batches(packages, batch_size), start=1):
        ui_header(f"Installing uv batch {idx}", ", ".join(batch))
        run(["uv", "pip", "install", "--python", PYTHON_VERSION, *batch], cwd=work_dir)


def install_batches_pepip(
    work_dir: Path, packages: Sequence[str], batch_size: int
) -> None:
    for idx, batch in enumerate(package_batches(packages, batch_size), start=1):
        ui_header(f"Installing pepip batch {idx}", ", ".join(batch))
        run([sys.executable, "-m", "pepip.cli", "install", *batch], cwd=work_dir)


def run_smoke_code(work_dir: Path) -> None:
    run(
        ["uv", "run", "--python", PYTHON_VERSION, "python", "-c", SMOKE_CODE],
        cwd=work_dir,
    )


def run_uv_mode(work_dir: Path, packages: Sequence[str], batch_size: int) -> None:
    ensure_binary("uv")
    run(["uv", "venv", "--python", PYTHON_VERSION], cwd=work_dir)
    install_batches_uv(work_dir, packages, batch_size)
    run_smoke_code(work_dir)


def run_pepip_mode(work_dir: Path, packages: Sequence[str], batch_size: int) -> None:
    ensure_binary("uv")
    install_batches_pepip(work_dir, packages, batch_size)
    run_smoke_code(work_dir)


AVAILABLE_MODES = ("uv", "pepip")


def modes_to_run(requested: str) -> Iterable[str]:
    if requested == "all":
        return AVAILABLE_MODES
    return (requested,)


def ui_print(message: str, *, style: Optional[str] = None) -> None:
    CONSOLE.print(message, style=style)


def ui_command(cmd: Sequence[str]) -> None:
    ui_print(f"$ {' '.join(cmd)}", style="dim")


def ui_header(title: str, subtitle: str = "") -> None:
    text = title if not subtitle else f"{title}\n[dim]{subtitle}[/dim]"
    CONSOLE.print(Panel.fit(text, border_style="cyan"))


def ui_packages(packages: Sequence[str]) -> None:
    table = Table(title="Pinned packages", show_lines=False)
    table.add_column("#", justify="right")
    table.add_column("Package")
    table.add_column("Version")
    for idx, spec in enumerate(packages, start=1):
        name, _, version = spec.partition("==")
        table.add_row(str(idx), name, version or "custom")
    CONSOLE.print(table)


def select_mode_interactively() -> str:
    options = ["all", *AVAILABLE_MODES]
    table = Table(title="Select install mode")
    table.add_column("Option", justify="right")
    table.add_column("Mode")
    table.add_column("Description")
    descriptions = {
        "all": "Run uv and pepip",
        "uv": "Use uv-managed .venv + uv pip",
        "pepip": "Use pepip CLI against ./.venv",
    }
    for idx, mode in enumerate(options, start=1):
        table.add_row(str(idx), mode, descriptions[mode])

    CONSOLE.print(table)
    choice = IntPrompt.ask(
        "Choose an option",
        choices=[str(i) for i in range(1, len(options) + 1)],
        default=1,
    )
    return options[choice - 1]


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Install pinned popular packages in batches and run smoke operations "
            "using uv or pepip. Uses ./.venv in the current working directory."
        )
    )
    parser.add_argument(
        "--mode",
        choices=["uv", "pepip", "all"],
        default=None,
        help="Which install mode to run. If omitted, an interactive menu is shown.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=3,
        help="Number of packages to install per batch.",
    )
    parser.add_argument(
        "--package",
        action="append",
        default=[],
        help=(
            "Override package list with explicit pinned specifiers. "
            "Provide multiple times, e.g. --package numpy==2.1.3."
        ),
    )
    args = parser.parse_args()

    packages = (
        args.package
        if args.package
        else [f"{name}=={version}" for name, version in DEFAULT_PINNED_VERSIONS.items()]
    )
    if not packages:
        raise ValueError("No packages specified.")

    selected_mode = args.mode or select_mode_interactively()
    selected_modes = tuple(modes_to_run(selected_mode))
    work_dir = Path.cwd()

    ui_header(
        "Package smoke runner",
        (
            f"Selected mode: {selected_mode}; batch size: {args.batch_size}; "
            f"python: {PYTHON_VERSION}; workdir={work_dir}"
        ),
    )
    ui_packages(packages)

    for mode in selected_modes:
        ui_header(f"Running mode: {mode}", f"workdir={work_dir}")
        if mode == "uv":
            run_uv_mode(work_dir, packages, args.batch_size)
        elif mode == "pepip":
            run_pepip_mode(work_dir, packages, args.batch_size)
        else:
            raise ValueError(f"Unsupported mode: {mode}")

    ui_print("\nAll selected modes passed.", style="bold green")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
