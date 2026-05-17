# Python Version Matrix

This folder runs the `pepip` test suite across Python minor versions from 3.8
through 3.14. Use it before a release, after changing interpreter-aware
installer behavior, or when checking support for a new Python version.

Pre-requisites: `uv` must be installed and available on `PATH`. The requested
Python interpreters do not need to be installed locally. The runner uses
`uv python install` to install each requested Python version into a script-owned
directory under the temporary work directory, then requires uv-managed Python
when creating the runner environments.

On Windows, install [Git for Windows](https://git-scm.com/download/win), open
Git Bash from the repository root, and run the same `.sh` commands below. If
you need native PowerShell or CMD versions, please create an
[Issue](https://github.com/perf-pip/pepip/issues).

## Scripts

- [`test_python_versions.sh`](test_python_versions.sh) creates an isolated
  uv-managed Python installation and runner virtual environment for each Python
  version, installs `pepip[test]`, runs pytest, then verifies
  `pepip install idna==3.10` in a throwaway project.

## Run

From the repository root:

```bash
test-scripts/python-versions/test_python_versions.sh
```

Run a smaller matrix by passing versions explicitly:

```bash
test-scripts/python-versions/test_python_versions.sh 3.11 3.12 3.13
```

Useful environment variables:

- `PYTEST_TARGET=tests/installer` narrows the pytest target.
- `PYTHON_INSTALL_DIR=/path/to/pythons` changes where `uv python install`
  stores managed Python installations.
- `TMPDIR=/path/to/tmp` changes where temporary matrix directories are created.
