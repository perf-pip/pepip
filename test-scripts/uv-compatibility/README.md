# uv Compatibility Scripts

These scripts test `pepip` against multiple `uv` versions. Use them before a
release, after changing installer command assembly, or when investigating a
`uv` version-specific failure.

## Scripts

- [`test_uv_versions.sh`](test_uv_versions.sh) installs each `uv` version into
  an isolated runner virtual environment, installs `pepip[test]`, runs pytest,
  then verifies `pepip install idna==3.10`.
- [`test_uv_versions_direct.sh`](test_uv_versions_direct.sh) installs `uv`
  directly into an isolated prefix and runs `pepip` from the source checkout.
  This is useful for catching `PATH` and source-import issues.

## Run

From the repository root:

```bash
test-scripts/uv-compatibility/test_uv_versions.sh
```

Run a smaller matrix by passing versions explicitly:

```bash
test-scripts/uv-compatibility/test_uv_versions.sh 0.4.30 0.8.22 0.11.10
```

Use the direct-source variant when you want to avoid installing `pepip` into the
runner environment:

```bash
test-scripts/uv-compatibility/test_uv_versions_direct.sh 0.8.22 0.11.0
```

Useful environment variables:

- `PYTHON=/path/to/python` selects the Python used to create runner
  environments.
- `PYTEST_TARGET=tests/installer` narrows the pytest target for
  `test_uv_versions.sh`.
- `TMPDIR=/path/to/tmp` changes where temporary matrix directories are created.
