# Production Tests

This document explains the validation layers used for `pepip`. The runnable
instructions live next to the scripts in [`test-scripts/`](../test-scripts/);
this page focuses on what each validation layer proves and when to use it.

## Validation Layers

| Layer | Purpose | When to run |
| --- | --- | --- |
| Unit tests | Fast checks for CLI behavior, installer flow, store layout, metadata handling, and symlink invariants. | Every code change. |
| uv compatibility | Confirms `pepip` works across supported `uv` release families. | Before releases or when changing installer command assembly. |
| Package smoke matrix | Installs pinned real packages and runs lightweight import/runtime checks. | Before releases or after changing package storage/linking behavior. |
| External repository replay | Compares plain `uv` installs with `pepip` installs on real projects. | Release validation and broad compatibility investigations. |
| Manual sanity checks | Quick local experiments for version isolation and disk usage. | Ad hoc debugging only. |

## Recommended Release Check

Start with the fast tests, then add heavier checks as needed:

```bash
pytest
test-scripts/uv-compatibility/test_uv_versions.sh
python3 test-scripts/package-smoke/install_smoke_matrix.py --mode pepip --batch-size 5
cp test-scripts/repo-replay/uv_repos.txt /tmp/pepip-uv-repos.txt
test-scripts/repo-replay/uv_repo_tester.sh --repos /tmp/pepip-uv-repos.txt --limit 10
test-scripts/repo-replay/pepip_repo_tester.sh --limit 10
```

For full instructions, prerequisites, and options, see:

- [`test-scripts/README.md`](../test-scripts/README.md)
- [`test-scripts/uv-compatibility/README.md`](../test-scripts/uv-compatibility/README.md)
- [`test-scripts/package-smoke/README.md`](../test-scripts/package-smoke/README.md)
- [`test-scripts/repo-replay/README.md`](../test-scripts/repo-replay/README.md)
- [`test-scripts/manual-sanity/README.md`](../test-scripts/manual-sanity/README.md)

## Unit Tests

The unit suite is the default validation path:

```bash
pytest
```

The tests cover:

- CLI parsing, help text, error behavior, `install` handling, and `uv`
  passthrough behavior.
- Global and local virtual environment creation.
- Interpreter-aware `site-packages` detection.
- Store scoping by interpreter, ABI, platform, and machine.
- Distribution metadata parsing from `.dist-info`, `RECORD`, and
  `top_level.txt`.
- Symlink invariants: preserve real local files, keep correct links untouched,
  replace stale links, and surface symlink failures clearly.
- End-to-end install flow with mocked `uv` calls, requirements-file installs,
  existing venv reuse, version isolation, and stale metadata cleanup.

Use focused subsets while developing:

```bash
pytest tests/cli
pytest tests/installer
```

## uv Compatibility

Folder: [`test-scripts/uv-compatibility/`](../test-scripts/uv-compatibility/)

This layer checks that `pepip` remains compatible with a range of `uv` versions.
It matters because `pepip install` shells out to `uv pip install --target`, so
changes in `uv` behavior can affect staging and resolution.

Entrypoints:

- [`test_uv_versions.sh`](../test-scripts/uv-compatibility/test_uv_versions.sh)
  installs each `uv` version in an isolated runner venv, installs
  `pepip[test]`, runs pytest, and verifies a real `pepip install idna==3.10`.
- [`test_uv_versions_direct.sh`](../test-scripts/uv-compatibility/test_uv_versions_direct.sh)
  installs `uv` into an isolated prefix and runs `pepip` from the source tree.
  Use this when debugging source import or `PATH` issues.

## Package Smoke Matrix

Folder: [`test-scripts/package-smoke/`](../test-scripts/package-smoke/)

This layer installs pinned packages such as `numpy`, `pandas`, `scipy`,
`scikit-learn`, `fastapi`, `sqlalchemy`, `httpx`, `polars`, `pillow`,
`aiohttp`, `lxml`, and `orjson`. Each package has a small smoke check so the
script catches more than successful installation.

Entrypoint:

- [`install_smoke_matrix.py`](../test-scripts/package-smoke/install_smoke_matrix.py)

Use `--mode uv` for a plain `uv` baseline, `--mode pepip` for the shared-store
path, or `--mode all` to run both in the same environment.

## External Repository Replay

Folder: [`test-scripts/repo-replay/`](../test-scripts/repo-replay/)

This is the broadest compatibility check. It runs real repositories through a
plain `uv` baseline first, then reruns the repositories that passed using
`pepip` for dependency installation.

Flow:

1. [`uv_repo_tester.sh`](../test-scripts/repo-replay/uv_repo_tester.sh) reads
   [`uv_repos.txt`](../test-scripts/repo-replay/uv_repos.txt), clones each
   repository, creates `.venv`, installs dependencies with plain `uv`, installs
   pytest tooling, and runs pytest.
2. Passing repositories are written to
   [`uv_repos_success.txt`](../test-scripts/repo-replay/uv_repos_success.txt).
3. [`pepip_repo_tester.sh`](../test-scripts/repo-replay/pepip_repo_tester.sh)
   reads that success list and repeats the install/test flow using `pepip`.
4. Results are written to
   [`pepip_repos_success.txt`](../test-scripts/repo-replay/pepip_repos_success.txt)
   and
   [`pepip_repos_failed.txt`](../test-scripts/repo-replay/pepip_repos_failed.txt).

Result files:

- [`results.tsv`](../test-scripts/repo-replay/results.tsv) records plain `uv`
  baseline rows.
- [`pepip_results.tsv`](../test-scripts/repo-replay/pepip_results.tsv) records
  `pepip` replay rows.
- [`uv_repos_failed.txt`](../test-scripts/repo-replay/uv_repos_failed.txt)
  records repositories that did not pass the baseline.

Interpretation:

- A repository that fails under plain `uv` is not useful for judging `pepip`
  compatibility, because the baseline itself failed.
- The meaningful comparison set is the repositories in
  [`uv_repos_success.txt`](../test-scripts/repo-replay/uv_repos_success.txt).
- A `pepip` pass means the repository installed and tested successfully when
  dependency installation was routed through `pepip`.
- A `pepip` failure needs log inspection; it may be a `pepip` bug, a missing
  console-script behavior, an unsupported namespace-package case, timeout, or
  an external project/environment issue.

The checked-in success files are the current reference result set. Refresh them
by rerunning the repo replay scripts and reviewing the changed `.txt` and
`.tsv` files.

## Manual Sanity Checks

Folder: [`test-scripts/manual-sanity/`](../test-scripts/manual-sanity/)

These scripts are intentionally small and local:

- [`test_package_versions.sh`](../test-scripts/manual-sanity/test_package_versions.sh)
  checks that different temp projects can import different pinned package
  versions.
- [`test_script.sh`](../test-scripts/manual-sanity/test_script.sh) creates
  several temp projects and opens `ncdu` for disk-usage inspection.

They are useful for debugging, but they are not a substitute for the automated
unit suite or release validation scripts.

## Known Validation Limits

- Console scripts from installed packages are not linked into local venv
  `bin` / `Scripts` directories yet, so repository failures involving installed
  command-line tools need careful interpretation.
- Namespace packages can require special handling when multiple distributions
  own the same top-level package.
- External repository tests depend on current network access, upstream project
  state, package indexes, and host resources.
- The heavier scripts intentionally mutate result files. Use a copied repo list
  or review generated diffs before committing refreshed results.
