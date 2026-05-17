# Package Smoke Matrix

This folder installs pinned packages in batches and runs lightweight smoke code
for each package. It is intended to catch integration issues that unit tests do
not cover, especially binary wheels and dependency-heavy packages.

Pre-requisites: Python 3.10 is expected by default.

## Files

- [`install_smoke_matrix.py`](install_smoke_matrix.py) is the runner.
- [`_smoke_matrix_utils.py`](_smoke_matrix_utils.py) contains deletion helpers
  used when resetting the local test environment.

## Run

Run the packages with `uv`:
```bash
python3 test-scripts/package-smoke/install_smoke_matrix.py --mode uv --batch-size 5
```

Run the same packages with `pepip`:
```bash
python3 test-scripts/package-smoke/install_smoke_matrix.py --mode pepip --batch-size 5
```

Run both modes:
```bash
python3 test-scripts/package-smoke/install_smoke_matrix.py --mode all --batch-size 5
```

Use a smaller slice while debugging:
```bash
python3 test-scripts/package-smoke/install_smoke_matrix.py \
  --mode pepip \
  --start 0 \
  --limit 5 \
  --batch-size 2
```

Notes:

- The runner creates or resets `./.venv` in the current working directory.
- The default venv creation path expects Python 3.10 when using `uv` mode.
- `--package NAME==VERSION` can be repeated to override the default package
  list.
