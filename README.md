# pepip

Alternative to "conda" to share each dependency version in a shared global environment to save storage space

## Overview

`pepip` (performance pip) solves a common pain point in Python development: each project typically has its own virtual environment, so large packages like `torch` or `transformers` are downloaded and stored multiple times — once per project.

`pepip` takes inspiration from [pnpm](https://pnpm.io/) for Node.js:

* Packages are installed **once** into a single shared global virtual environment (`~/.pepip/global-venv`), using [`uv`](https://github.com/astral-sh/uv) for fast downloads.
* Inside each project's `.venv`, **symlinks** point back to the global copies, so Python can import the packages as normal.
* Re-installing a package that is already in the global environment is near-instant — no download required.

## Requirements

* Python 3.8+
* [`uv`](https://github.com/astral-sh/uv) — installed automatically as a dependency

## Installation

```bash
pip install pepip
```

## Usage

### Install packages

```bash
# Install one or more packages
pepip install numpy pandas

# Install from a requirements file
pepip install -r requirements.txt

# Use a custom local venv path (default: .venv)
pepip install numpy --venv /path/to/my-env
```

After running `pepip install`, a `.venv` directory is created (or updated) in the current directory. Activate it as usual:

```bash
source .venv/bin/activate
python -c "import numpy; print(numpy.__version__)"
```

### How it works

```
~/.pepip/
└── global-venv/
    └── lib/
        └── python3.12/
            └── site-packages/
                ├── numpy/          ← real package files (downloaded once)
                ├── numpy-2.0.dist-info/
                ├── torch/
                └── ...

my-project/
└── .venv/
    └── lib/
        └── python3.12/
            └── site-packages/
                ├── numpy -> ~/.pepip/global-venv/lib/.../numpy   (symlink)
                ├── numpy-2.0.dist-info -> ...                   (symlink)
                └── ...
```

The global environment path can be overridden via the `PEPIP_HOME` environment variable:

```bash
PEPIP_HOME=/shared/team-env pepip install torch
```

## Development

```bash
# Clone and install in editable mode
git clone https://github.com/perf-pip/pepip
cd pepip
pip install -e .

# Run tests
pip install pytest
pytest
```

## Evaluation — pepip vs uv

The `eval/benchmark.py` script measures installation latency and disk usage
when setting up N projects with the same packages, comparing pepip against a
plain `uv` workflow.

```bash
# 3 projects, default packages (tomli, packaging)
python eval/benchmark.py

# 5 projects, larger dependency set
python eval/benchmark.py --projects 5 --packages requests certifi charset-normalizer idna urllib3

# Keep the temp directories for manual inspection
python eval/benchmark.py --no-cleanup
```

### Sample results (3 projects, packages: `tomli packaging`)

```
┌──────────────┬─────────────────┬─────────────┬──────────────────────┐
│  pepip vs uv — evaluation (3 project(s), packages: tomli packaging)  │
├──────────────┬─────────────────┬─────────────┬──────────────────────┤
│  Metric      │  uv (baseline)  │  pepip       │  Improvement         │
├──────────────┼─────────────────┼─────────────┼──────────────────────┤
│  Latency     │  0.34 s         │  0.35 s     │  +3.5 %              │
│  Disk usage  │  2.98 MB        │  1.10 MB ★  │  -63.2 %             │
└──────────────┴─────────────────┴─────────────┴──────────────────────┘

  ★ = better result
```

### Sample results (5 projects, packages: `requests certifi charset-normalizer idna urllib3`)

```
┌──────────────┬─────────────────┬─────────────┬───────────────────────────────────────────────────────┐
│  pepip vs uv — evaluation (5 project(s), packages: requests certifi charset-normalizer idna urllib3)  │
├──────────────┬─────────────────┬─────────────┬───────────────────────────────────────────────────────┤
│  Metric      │  uv (baseline)  │  pepip       │  Improvement                                          │
├──────────────┼─────────────────┼─────────────┼───────────────────────────────────────────────────────┤
│  Latency     │  0.76 s         │  0.50 s ★   │  -33.8 %                                              │
│  Disk usage  │  9.46 MB        │  2.06 MB ★  │  -78.2 %                                              │
└──────────────┴─────────────────┴─────────────┴───────────────────────────────────────────────────────┘

  ★ = better result
```

**Key observations:**

* **Storage savings** are consistent regardless of project count: because each
  package version is stored exactly once in the global venv, the local `.venv`
  directories contain only tiny symlinks (~dozens of bytes each) instead of
  full copies.  With 5 projects and the `requests` dependency tree (~2 MB each),
  pepip saves **7.4 MB** compared to separate venvs.

* **Latency savings** grow with project count: the first project pays the same
  download + install cost as plain `uv`.  Every subsequent project only needs
  venv creation + symlink creation, which is nearly instant.  For tiny packages
  (cached by uv), the difference is negligible at n=3, but reaches **−34 %**
  at n=5 with a larger dependency set.  For real-world packages like `torch` or
  `transformers` (GB-scale), the savings per extra project would be
  proportionally larger.

