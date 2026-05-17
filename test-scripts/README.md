# Test Scripts

This directory contains higher-level validation scripts for `pepip`. These are
slower and more environment-dependent than the unit tests, so run them when you
need confidence, `uv` compatibility coverage, or real-world install
signals.

Run commands from the repository's root unless a folder README says otherwise.

## Prerequisites

- Python 3.8 or newer.
- [uv](https://docs.astral.sh/uv/getting-started/installation/) tool installed and added to `PATH`.
- `pepip` runnable from this checkout, or install it with `pip install -e .`.
- For repository replay: `git`, `timeout`, `rg`, and network access.
- For package smoke tests: Python 3.10 is expected by default.
- On Windows, install [Git for Windows](https://git-scm.com/download/win) and
  run the `.sh` scripts from Git Bash.

## Folders

- [`uv-compatibility/`](uv-compatibility/) checks `pepip` against multiple `uv`
  versions.
  - This proved that `pepip` is compatible with a wide range of `uv` versions mentioned in pyproject.toml, including older versions.
- [`package-smoke/`](package-smoke/) installs pinned packages and runs import and basic usage checks.
  - This proved that `pepip` can install a wide range of packages similar to `uv`, making them usable.
  - This ensures that the packages and code which works using `uv` also works using `pepip`.
- [`repo-replay/`](repo-replay/) compares plain `uv` installs with `pepip`
  installs across external repositories.
  - This proved that `pepip` has the same compatibility as `uv` across a wide range of real-world repositories, despite lower installation times.
  - While package-smoke/ tests a wide range of popular packages, repo-replay/ tests a wide range of real-world repositories that use uv, which may have different package combinations and edge cases.
- [`manual-sanity/`](manual-sanity/) contains small ad hoc local checks.
  - These proved that `pepip` can install multiple packages in multiple folders and save space.

## Common Commands

```bash
# Fast project-level baseline.
pip install -e ".[dev]"
pytest

# Check the supported uv version matrix.
test-scripts/uv-compatibility/test_uv_versions.sh

# Run the package smoke matrix in pepip mode.
python3 test-scripts/package-smoke/install_smoke_matrix.py --mode pepip --batch-size 3

# Run a external-repository baseline and replay.
test-scripts/repo-replay/pepip_repo_tester.sh
#     -> Uses the above list to test pepip and compare results with uv
```

For the high-level validation strategy and current experiment interpretation,
see [`docs/Production_Tests.md`](../docs/Production_Tests.md).

## Windows

The Bash scripts support Windows through Git Bash. Install Git for Windows,
open Git Bash from the repository root, and run the same commands shown above.

PowerShell and `cmd.exe` versions are not included. If you love native
PowerShell or CMD scripts, please create an
[Issue](https://github.com/perf-pip/pepip/issues).
