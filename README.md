# 🐍 pepip

> **uv and pip, but shared.** Install packages once. Use them everywhere.

`pepip` is the [pnpm](https://pnpm.io/) of Python — a drop-in alternative to `pip` / `uv` that stores each package **once** in a global environment and wires your project `.venv` to it via symlinks. No more downloading `torch` five times.

---

## 🤔 The Problem

Every Python project gets its own virtual environment. That means every project downloads and stores its own copy of every dependency — including the big ones.

```
project-a/.venv/   →  numpy (35 MB)  pandas (15 MB)  torch (2.4 GB)
project-b/.venv/   →  numpy (35 MB)  pandas (15 MB)  torch (2.4 GB)
project-c/.venv/   →  numpy (35 MB)  pandas (15 MB)  torch (2.4 GB)
                                                  ↑ stored 3× for no reason
```

## ✅ The Solution

`pepip` keeps a single global environment and symlinks each project's `.venv` back to it. Same Python import behaviour. A fraction of the disk usage.

```
~/.pepip/global-venv/   →  numpy (35 MB)  pandas (15 MB)  torch (2.4 GB)  ← stored once

project-a/.venv/        →  numpy (symlink)  pandas (symlink)  torch (symlink)
project-b/.venv/        →  numpy (symlink)  pandas (symlink)  torch (symlink)
project-c/.venv/        →  numpy (symlink)  pandas (symlink)  torch (symlink)
```

---

## 🚀 Installation

```bash
pip install pepip
```

**Requirements:** Python 3.8+ · [`uv`](https://github.com/astral-sh/uv) (auto-installed)

---

## 📦 Usage

### Install packages

```bash
# Install one or more packages
pepip install numpy pandas

# Install from a requirements file
pepip install -r requirements.txt

# Use a custom local venv path (default: .venv)
pepip install numpy --venv /path/to/my-env
```

Then activate and use your `.venv` exactly as you normally would:

```bash
source .venv/bin/activate
python -c "import numpy; print(numpy.__version__)"
```

### Override the global store location

```bash
PEPIP_HOME=/shared/team-env pepip install torch
```

This is handy for sharing a global store across a whole team on a shared machine.

---

## 🗂 How it works

```
~/.pepip/
└── global-venv/
    └── lib/
        └── python3.12/
            └── site-packages/
                ├── numpy/                ← real files, downloaded once
                ├── numpy-2.0.dist-info/
                ├── pandas/
                └── ...

my-project/
└── .venv/
    └── lib/
        └── python3.12/
            └── site-packages/
                ├── numpy   ──────────→  ~/.pepip/global-venv/.../numpy   (symlink, ~bytes)
                ├── pandas  ──────────→  ~/.pepip/global-venv/.../pandas  (symlink, ~bytes)
                └── ...
```

- **First install** of a package — downloads once into the global store, then symlinks.
- **Every subsequent project** using the same package — symlinks only. Near-instant, zero extra disk.

---

## 📊 Benchmarks

The `eval/benchmark.py` script measures installation latency and disk usage across N projects compared to a plain `uv` workflow.

```bash
# 5 projects, mixed real-world packages
python eval/benchmark.py --projects 5 --packages tomli packaging requests numpy pandas

# Keep temp directories for manual inspection
python eval/benchmark.py --no-cleanup
```

### Latest results — 5 projects · `tomli packaging requests numpy pandas`

| Metric | uv (baseline) | pepip | Improvement |
|---|---|---|---|
| ⏱ Latency | 0.56 s | **0.33 s** ★ | −41.3 % |
| 💾 Disk usage | 475.19 MB | **95.22 MB** ★ | −80.0 % |

> ⏱ pepip saved **0.23 s** of install time across 5 projects.
> 💾 pepip saved **379.97 MB** of disk space across 5 projects.

### Why the savings get better over time

- **Storage savings** are consistent from project one: each package version lives exactly once in the global store, so local `.venv` directories contain only tiny symlinks (dozens of bytes each) instead of full copies.
- **Latency savings** grow with project count: the first project pays the same download cost as plain `uv`. Every additional project only needs venv creation + symlink creation, which is nearly instant. For large packages like `torch` or `transformers` (GBs in size), these savings per extra project are proportionally enormous.

---

## 🛠 Development

```bash
# Clone and install in editable mode
git clone https://github.com/perf-pip/pepip
cd pepip
pip install -e .

# Run tests
pip install pytest
pytest
```

---

## 💡 Inspired by

[pnpm](https://pnpm.io/) — the Node.js package manager that pioneered content-addressable, symlink-based shared stores. `pepip` brings the same idea to the Python ecosystem.

## Acknowledgements
- [uv](https://docs.astral.sh/uv/) — used for _venv_ management and package installation in the global store.

---

<p align="center">Made with ❤️ for developers tired of downloading <code>torch</code> over and over again.</p>