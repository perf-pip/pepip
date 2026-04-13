# AGENTS.md

This file is a fast, structured guide for AI agents working in this repository.
It describes the project intent, code map, invariants, workflows, and safe edit
patterns.

## 1) Project Purpose

`pepip` is a Python CLI tool that reuses dependencies across projects.

- It installs packages once into a shared global virtual environment.
- It creates per-project virtual environments that symlink package entries from
	the shared global environment.
- It aims to reduce repeated downloads and disk duplication, similar to pnpm's
	shared-store model for Node.js.

## 2) Core Behavior (High Level)

Given `pepip install ...`:

1. Ensure global venv exists (`~/.pepip/global-venv` or `$PEPIP_HOME/global-venv`).
2. Install requested packages into that global venv using `uv pip install`.
3. Diff global `site-packages` before/after install to detect new entries.
4. Ensure local project venv exists (`.venv` by default).
5. Symlink only newly added entries from global `site-packages` into local
	 `site-packages`.

## 3) Repository Map

- `pepip/installer.py`
	- Core logic: venv creation, package install, site-packages detection,
		symlink linking.
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
- `README.md`
	- User-facing overview, setup, usage, benchmark examples.

## 4) Runtime and Build Facts

- Python: `>=3.8` (see `pyproject.toml`).
- Build backend: `hatchling`.
- Runtime dependency: `uv>=0.11.0`.
- Test framework: `pytest`.
- Linting configured with Ruff rules `E`, `F`, `W`.

## 5) Important Paths and Environment Variables

- `PEPIP_HOME`
	- If set, global state root is `$PEPIP_HOME`.
	- Otherwise defaults to `~/.pepip`.
- `GLOBAL_VENV`
	- Computed as `PEPIP_HOME / "global-venv"`.
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

5. **Global install happens before local linking.**
	 - New entries are computed by diffing global site-packages pre/post install.

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
- README usage examples

## 10) Known Limitations / Design Tradeoffs

- Current linking step only links entries detected as newly added during the
	current install operation.
- Existing global packages that predate the current install call are not
	retro-linked unless they appear in the new-entry diff.
- Behavior is intentional in current design, but any change here must be backed
	by explicit tests and documentation updates.

## 11) Quick Task Routing for Future Agents

- "CLI flags/help/output wrong" -> inspect `pepip/cli.py` + `tests/test_cli.py`.
- "Symlink behavior broken" -> inspect `pepip/installer.py` +
	`tests/test_installer.py` (`TestLinkPackages`).
- "Install command not invoking uv correctly" -> inspect `install(...)` command
	assembly and tests around requirements handling.
- "Performance/disk comparison question" -> inspect and run `eval/benchmark.py`.

## 12) Definition of Done for Agent Changes

Before finishing:

1. Relevant tests pass.
2. No invariant in section 6 is violated.
3. CLI behavior remains consistent with section 7, unless intentionally changed
	 with tests.
4. User-facing changes are reflected in `README.md` when appropriate.
