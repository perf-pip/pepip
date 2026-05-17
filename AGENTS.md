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
		package-version storage, stale metadata cleanup, symlink linking.
	- Main public API: `install(...)`.
- `pepip/cli.py`
	- CLI parser + command dispatch.
	- `install` is handled by pepip; every other command is forwarded to `uv`.
	- Script entry point `pepip = pepip.cli:main`.
- `pepip/__init__.py`
	- Package metadata module.
- `tests/installer/`
	- Installer-focused test suite split by concern:
		- `test_core_helpers.py`
		- `test_distribution_metadata.py`
		- `test_install_flow.py`
		- `test_link_packages.py`
		- `test_stale_distribution_links.py`
		- `test_store.py`
		- `test_venv_management.py`
	- Shared helpers: `tests/installer/helpers.py`.
- `tests/cli/`
	- CLI behavior tests, including `install` handling and uv passthrough:
		- `test_install_command.py`
		- `test_uv_passthrough_commands.py`
- `eval/benchmark.py`
	- Performance and disk usage comparison of pepip vs plain uv workflows.
- `test-scripts/`
	- Higher-level validation and experiment scripts beyond the unit suite.
	- Canonical experiment inventory: `docs/Production_Tests.md`.
- `README.md`
	- User-facing overview, setup, usage, benchmark examples.
- `docs/USAGE.md`
	- Development notes and CLI behavior summary, including Docker-oriented usage.

## 4) Runtime and Build Facts

- Python: `>=3.8` (see `pyproject.toml`).
- Build backend: `hatchling`.
- Runtime dependency: `uv>=0.4.0`.
- Test framework: `pytest`.
- Optional test extras: `pytest-cov`, `pytest-mock`.
- Dev tooling declared in `pyproject.toml`: `black`, `isort`, `mypy`, `ruff`, `rich`.
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
	- Scoped by interpreter cache tag / platform / machine so compiled wheels are
		not mixed across incompatible Python runtimes.
	- Resolution prefers the local venv interpreter when that venv already
		exists; otherwise pepip falls back to the global build venv interpreter.
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

7. **Stale distribution metadata symlinks for relinked packages should be cleaned up.**
	 - When a distribution is being relinked, old symlinked `.dist-info` /
		 `.egg-info` entries for that same normalized distribution name may be
		 removed.
	 - Real directories/files must still be preserved.

8. **Installer failures during staging must not create or mutate the local venv unnecessarily.**
	 - `install(...)` stages packages first; if `uv pip install` fails, pepip
		 should not proceed to local venv creation/linking.

## 7) CLI Contract

Command shape:

- `pepip install PACKAGE...`
- `pepip install -r requirements.txt`
- Optional: `--venv PATH`
- Any non-`install` invocation is forwarded to `uv` unchanged, including:
	- `pepip sync ...`
	- `pepip run ...`
	- `pepip venv ...`
	- `pepip pip ...`
	- `pepip --version`

Expected behavior:

- `pepip install` with neither packages nor `-r` shows install help and exits
	non-zero (via argparse help flow).
- `pepip` with no arguments shows top-level help and exits `0`.
- Top-level `--help` shows top-level help and exits `0`.
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
test-scripts/uv-compatibility/test_uv_versions.sh
python3 test-scripts/package-smoke/install_smoke_matrix.py --mode pepip --batch-size 5
cp test-scripts/repo-replay/uv_repos.txt /tmp/pepip-uv-repos.txt
test-scripts/repo-replay/uv_repo_tester.sh --repos /tmp/pepip-uv-repos.txt
test-scripts/repo-replay/pepip_repo_tester.sh
```

If changing CLI behavior, run at least:

```bash
pytest tests/cli
```

If changing installer behavior, run at least:

```bash
pytest tests/installer
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

- `docs/Production_Tests.md`
- `test-scripts/README.md`

## 10) Known Limitations / Design Tradeoffs

- The local venv links resolved site-package entries, but console scripts from
	installed packages are not currently linked into the local venv's `bin` /
	`Scripts` directory.
- Namespace packages can still need special handling if multiple distributions
	own the same top-level package directory.
- Non-`install` commands are delegated to `uv`; pepip is not implementing the
	full uv command surface itself.

## 11) test-scripts Experiment Map

Use `docs/Production_Tests.md` as the high-level description. The runnable
instructions live in the folder READMEs under `test-scripts/`.

- `test-scripts/uv-compatibility/`
	- `test_uv_versions.sh` and `test_uv_versions_direct.sh`
	- `uv` compatibility matrix and direct CLI/source validation across `uv` versions.
- `test-scripts/package-smoke/`
	- `install_smoke_matrix.py` with `_smoke_matrix_utils.py`
	- Pinned package install smoke matrix for `uv` mode and `pepip` mode.
	- Creates or resets `./.venv` in the current working directory.
- `test-scripts/repo-replay/`
	- `uv_repo_tester.sh`
	- External repository baseline with plain `uv`.
	- Uses `uv_repos.txt` and writes `uv_repos_success.txt` / `uv_repos_failed.txt`.
	- `pepip_repo_tester.sh`
	- External repository replay with `pepip` against the repositories that already passed with `uv`.
	- Uses `uv_repos_success.txt` and writes `pepip_repos_success.txt` / `pepip_repos_failed.txt`.
	- Result files: `results.tsv`, `pepip_results.tsv`.
	- Helpers: `remove_finished.py` and `sort-repos.py`.
- `test-scripts/manual-sanity/`
	- `test_package_versions.sh` and `test_script.sh`
	- Small local manual sanity checks for version isolation and disk-usage behavior.

## 12) Quick Task Routing for Future Agents

- "CLI flags/help/output wrong" -> inspect `pepip/cli.py` +
	`tests/cli/test_install_command.py` and
	`tests/cli/test_uv_passthrough_commands.py`.
- "Symlink behavior broken" -> inspect `pepip/installer.py` +
	`tests/installer/test_link_packages.py`.
- "Install command not invoking uv correctly" -> inspect `install(...)` command
	assembly and `tests/installer/test_install_flow.py`.
- "Store scoping / package version persistence wrong" -> inspect
	`_package_store_root(...)`, `_store_distribution(...)`, and
	`tests/installer/test_store.py`.
- "Distribution metadata or top-level ownership wrong" -> inspect
	`_metadata_from_dist_info(...)`, `_record_roots(...)`, and
	`tests/installer/test_distribution_metadata.py`.
- "Old `.dist-info` links are lingering or wrong version metadata survives" ->
	inspect `_remove_stale_distribution_links(...)` and
	`tests/installer/test_stale_distribution_links.py`.
- "Local/global venv creation behavior wrong" -> inspect
	`ensure_global_venv(...)`, `ensure_local_venv(...)`, and
	`tests/installer/test_venv_management.py`.
- "Performance/disk comparison question" -> inspect and run `eval/benchmark.py`.
- "uv version compatibility question" -> inspect
	`test-scripts/uv-compatibility/test_uv_versions.sh` +
	`test-scripts/uv-compatibility/test_uv_versions_direct.sh`.
- "Real package install smoke failure" -> inspect
	`test-scripts/package-smoke/install_smoke_matrix.py` +
	`test-scripts/package-smoke/_smoke_matrix_utils.py`.
- "Docker / host-mounted shared store usage" -> inspect `docs/USAGE.md`.
- "External repository experiment or pass-rate question" -> inspect
	`docs/Production_Tests.md`, `test-scripts/repo-replay/uv_repo_tester.sh`,
	`test-scripts/repo-replay/pepip_repo_tester.sh`, and the
	`test-scripts/repo-replay/*_repos_*.txt` files.

## 13) Definition of Done for Agent Changes

Before finishing:

1. Relevant tests pass.
2. No invariant in section 6 is violated.
3. CLI behavior remains consistent with section 7, unless intentionally changed
	 with tests.
4. User-facing changes are reflected in `README.md` when appropriate.
5. Validation or experiment changes are reflected in `docs/Production_Tests.md`
	 and `test-scripts/README.md` when appropriate.

Note:
When you change something that is covered in README.md or AGENTS.md, edit the files as well.
