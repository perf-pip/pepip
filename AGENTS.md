# AGENTS.md

## 1) Project Purpose

The current directory has the source code of `pepip` project.
`pepip` is a Python CLI tool that reuses dependencies across projects. It uses "uv" under the hood.

- It installs resolved package versions once into an immutable shared store.
- It creates per-project virtual environments that symlink package entries from
	the shared store.
- It aims to reduce repeated downloads and disk duplication, similar to pnpm's
	shared-store model for Node.js.

## 2) Core Behavior (High Level)

Given `pepip install ...`:

1. Ensure build venv exists (`~/.pepip/global-venv` or `$PEPIP_HOME/global-venv`).
2. Install requested packages into a temporary target directory using
	 `uv pip install --target`.
3. Copy each resolved distribution version into `$PEPIP_HOME/packages` if it is
	 not already present.
4. Ensure local project venv exists (`.venv` by default).
5. Symlink resolved entries from the immutable store into local `site-packages`.

## 3) Repository Map

- `pepip/installer.py`
	- Core logic: venv creation, package install, site-packages detection,
		package-version storage, symlink linking.
	- Main public API: `install(...)`.
- `pepip/cli.py`
	- CLI parser + command dispatch.
	- Script entry point `pepip = pepip.cli:main`.
- `tests/test_installer.py`
	- Unit tests for installer helpers and integration-style install behavior
		with `subprocess.run` mocked.
- `tests/test_cli.py`
	- CLI behavior tests (success paths, help, error handling, messages).
- `eval/benchmark.py`
	- Performance and disk usage comparison of pepip vs plain uv workflows.
- `test-scripts/`
	- Higher-level validation and experiment scripts beyond the unit suite.
	- Canonical experiment inventory: `docs/Production_readiness.md`.
- `README.md`
	- User-facing overview, setup, usage, benchmark examples.

## 4) Runtime and Build Facts

- Python: `>=3.8` (see `pyproject.toml`).
- Build backend: `hatchling`.
- Runtime dependency: `uv>=0.11.0`.
- Test framework: `pytest`.
- Linting configured with Ruff rules `E`, `F`, `W`.
- Supported OS targets: Linux, macOS, and Windows.

### Cross-platform compatibility notes

- Keep path handling platform-aware (`pathlib`, `sys.platform`) and avoid hardcoding POSIX-only assumptions.
- The package store is interpreter/ABI/platform scoped so incompatible binaries are not mixed across OSes.
- On Windows, symlink creation may require Developer Mode or elevated permissions; preserve clear error propagation for symlink failures.

## 5) Important Paths and Environment Variables

- `PEPIP_HOME`
	- If set, global state root is `$PEPIP_HOME`.
	- Otherwise defaults to `~/.pepip`.
- `GLOBAL_VENV`
	- Computed as `PEPIP_HOME / "global-venv"`.
	- Used as the build interpreter for target installs, not as the package
		store.
- Package store
	- Computed under `PEPIP_HOME / "packages"`.
	- Scoped by the build interpreter ABI/platform so compiled wheels are not
		mixed across incompatible Python runtimes.
- Local venv
	- Defaults to `.venv` unless overridden by `--venv`.

## 6) Critical Invariants (Do Not Break)

1. **Never overwrite real local files/dirs in site-packages.**
	 - In `link_packages(...)`, only replace symlinks when needed.
	 - If a non-symlink local entry already exists, leave it untouched.

2. **Correct symlinks should remain untouched.**
	 - Avoid churn and unnecessary filesystem operations.

3. **Outdated/broken symlinks may be replaced.**
	 - Safe repair behavior is expected.

4. **`install(...)` requires package input.**
	 - Must receive package specifiers and/or requirements file.

5. **Resolved packages are stored before local linking.**
	 - Local symlinks must point at immutable package-version store entries.
	 - A mutable global `site-packages` directory must not be used as the source
		 of project symlinks.

6. **Site-packages path resolution should remain interpreter-aware.**
	 - `_site_packages(...)` prefers querying the venv's own Python via
		 `sysconfig.get_path('purelib')`.

## 7) CLI Contract

Command shape:

- `pepip install PACKAGE...`
- `pepip install -r requirements.txt`
- Optional: `--venv PATH`

Expected behavior:

- `pepip install` with neither packages nor `-r` shows install help and exits
	non-zero (via argparse help flow).
- Installer exceptions are surfaced as user-friendly stderr lines:
	- `FileNotFoundError` -> exit code `1`.
	- Other exceptions -> exit code `1`.
- Success prints count of newly linked entries (singular/plural aware).

## 8) Local Development Workflow (for Agents)

Use these commands when validating edits:

```bash
pytest
```

Optional benchmark sanity check:

```bash
python eval/benchmark.py
```

Optional higher-level validation:

```bash
test-scripts/test_uv_versions.sh
python3 test-scripts/install_smoke_matrix.py --mode pepip --batch-size 5
test-scripts/uv_repo_tester.sh
test-scripts/pepip_repo_tester.sh
```

If changing CLI behavior, run at least:

```bash
pytest tests/test_cli.py
```

If changing installer behavior, run at least:

```bash
pytest tests/test_installer.py
```

## 9) Safe Change Strategy for Agents

When modifying code:

1. Keep changes minimal and scoped.
2. Preserve existing public API names unless explicitly migrating.
3. Add/adjust tests in the same PR when behavior changes.
4. Prefer deterministic filesystem logic; avoid destructive operations.
5. Preserve cross-platform handling (`win32` vs POSIX paths).

When adding features, consider whether they affect:

- CLI parser and help text (`pepip/cli.py`)
- installer core flow (`pepip/installer.py`)
- tests in both CLI and installer suites
- validation coverage in `test-scripts/` when behavior affects compatibility or real-world install flows
- README usage examples

If the change touches validation workflows or experiment interpretation, also update:

- `docs/Production_readiness.md`
- `test-scripts/README.md`

## 10) Known Limitations / Design Tradeoffs

- The local venv links resolved site-package entries, but console scripts from
	installed packages are not currently linked into the local venv's `bin` /
	`Scripts` directory.
- Namespace packages can still need special handling if multiple distributions
	own the same top-level package directory.

## 11) test-scripts Experiment Map

Use `docs/Production_readiness.md` as the canonical description. The main experiments in `test-scripts/` are:

- `test_uv_versions.sh` and `test_uv_versions_direct.sh`
	- `uv` compatibility matrix and direct CLI/source validation across `uv` versions.
- `install_smoke_matrix.py` with `_smoke_matrix_utils.py`
	- Pinned package install smoke matrix for `uv` mode and `pepip` mode.
	- Result files: `results.tsv`, `pepip_results.tsv`.
- `uv_repo_tester.sh`
	- External repository baseline with plain `uv`.
	- Uses `uv_repos.txt` and writes `uv_repos_success.txt` / `uv_repos_failed.txt`.
- `pepip_repo_tester.sh`
	- External repository replay with `pepip` against the repositories that already passed with `uv`.
	- Uses `uv_repos_success.txt` and writes `pepip_repos_success.txt` / `pepip_repos_failed.txt`.
- `test_package_versions.sh` and `test_script.sh`
	- Small local manual sanity checks for version isolation and disk-usage behavior.
- `remove_finished.py` and `sort-repos.py`
	- Helpers for curating and rerunning the external repository experiment inputs/results.

## 12) Quick Task Routing for Future Agents

- "CLI flags/help/output wrong" -> inspect `pepip/cli.py` + `tests/test_cli.py`.
- "Symlink behavior broken" -> inspect `pepip/installer.py` +
	`tests/test_installer.py` (`TestLinkPackages`).
- "Install command not invoking uv correctly" -> inspect `install(...)` command
	assembly and tests around requirements handling.
- "Performance/disk comparison question" -> inspect and run `eval/benchmark.py`.
- "uv version compatibility question" -> inspect `test-scripts/test_uv_versions.sh`
	+ `test-scripts/test_uv_versions_direct.sh`.
- "Real package install smoke failure" -> inspect `test-scripts/install_smoke_matrix.py`
	+ `test-scripts/_smoke_matrix_utils.py`.
- "External repository experiment or pass-rate question" -> inspect
	`docs/Production_readiness.md`, `test-scripts/uv_repo_tester.sh`,
	`test-scripts/pepip_repo_tester.sh`, and the `*_repos_*.txt` files.

## 13) Definition of Done for Agent Changes

Before finishing:

1. Relevant tests pass.
2. No invariant in section 6 is violated.
3. CLI behavior remains consistent with section 7, unless intentionally changed
	 with tests.
4. User-facing changes are reflected in `README.md` when appropriate.
5. Validation or experiment changes are reflected in `docs/Production_readiness.md`
	 and `test-scripts/README.md` when appropriate.
