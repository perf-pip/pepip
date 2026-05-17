# External Repository Replay

This folder runs real repositories through two install paths:

1. [`uv_repo_tester.sh`](uv_repo_tester.sh) establishes a plain `uv` baseline.
2. [`pepip_repo_tester.sh`](pepip_repo_tester.sh) replays repositories that
   passed the `uv` baseline using `pepip` for dependency installation.

Use this when you need broad compatibility confidence beyond the local unit
suite and package smoke matrix.

Pre-requisites: `git`, `timeout`, `rg`, and network access.

On Windows, install [Git for Windows](https://git-scm.com/download/win), open
Git Bash from the repository root, and run the same `.sh` commands below. If
you need native PowerShell or CMD versions, please create an
[Issue](https://github.com/perf-pip/pepip/issues).

## Data Files

- [`uv_repos.txt`](uv_repos.txt) is the baseline input list.
- [`uv_repos_success.txt`](uv_repos_success.txt) stores repositories that passed
  the plain `uv` baseline.
- [`pepip_repos_success.txt`](pepip_repos_success.txt) stores repositories that
  passed under `pepip`.
- [`pepip_repos_failed.txt`](pepip_repos_failed.txt) stores `pepip` replay
  failures.
    - Currently, this file is blank, proving that every tested repo that passed tests using `uv` also passed using `pepip`.

## Run

Start with a small sample:

```bash
test-scripts/repo-replay/uv_repo_tester.sh --limit 3
test-scripts/repo-replay/pepip_repo_tester.sh --limit 3
```

Run with the full lists:

```bash
test-scripts/repo-replay/uv_repo_tester.sh
test-scripts/repo-replay/pepip_repo_tester.sh
#     -> Uses the list created by the above script
```

Useful options:

- `--repos PATH` selects the input repository list.
- `--workdir PATH` selects clone and log storage.
- `--start N` skips repositories before index `N`.
- `--limit N` caps the number of repositories processed.

Useful environment variables:

- `WORK_DIR=/path/to/workdir` sets clone and log storage.
- `REPO_TIMEOUT_SECS=1800` controls per-repository command timeout.
- `INSTALL_TIMEOUT_SECS=120` controls install command timeout.
- `PYTEST_TIMEOUT_SECS=600` controls pytest timeout.
- `PYTHON_BIN=/path/to/python3` selects Python for the `pepip` replay script.
- `PEPIP_HOME=/path/to/store` selects the shared store used by the `pepip`
  replay script.
