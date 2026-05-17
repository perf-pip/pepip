# Manual Sanity Checks

These scripts are small local experiments. They are useful for quick manual
checks.

## Scripts

- [`test_script.sh`](test_script.sh) creates several projects, installs repeated dependencies with `pepip`, then opens `ncdu` so you can inspect disk usage.
- [`test_package_versions.sh`](test_package_versions.sh) installs different pinned versions of the same packages into separate projects and prints the imported versions.

## Run

Install `pepip` first, or run from an environment where the `pepip` command is available:
```bash
pip install -e .
```

Then, run the scripts:

For disk-usage inspection:
```bash
test-scripts/manual-sanity/test_script.sh
```

For package version checks:
```bash
test-scripts/manual-sanity/test_package_versions.sh
```

Both scripts create and delete directories under `/tmp/pepip-test`.
