### Test coverage in this repo

The current automated test suite covers `74` tests across `9` files in `tests/`.

- `tests/cli/test_install_command.py` and `tests/cli/test_venv_command.py` cover CLI parsing, help/error behavior, argument forwarding, and user-facing success/error messages.
- `tests/installer/test_core_helpers.py` and `tests/installer/test_venv_management.py` cover `uv` discovery, venv path resolution, interpreter-aware `site-packages` lookup, and cross-platform Python executable handling.
- `tests/installer/test_link_packages.py` enforces the core filesystem invariants: do not overwrite real local files, keep correct symlinks untouched, replace stale symlinks safely, and fail clearly when symlink creation is blocked.
- `tests/installer/test_store.py` and `tests/installer/test_distribution_metadata.py` cover immutable store naming, metadata parsing, owned-entry discovery from `RECORD`/`top_level.txt`, and copy-once store behavior.
- `tests/installer/test_install_flow.py` and `tests/installer/test_stale_distribution_links.py` cover end-to-end install flow with mocked `uv` calls, dependency linking, requirements-file installs, reuse of existing local venv interpreters, per-project version isolation, and stale `.dist-info` cleanup.

Validated locally in this workspace:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest
```

Result: `74 passed`.

### Validation scripts

The `test-scripts/` directory contains higher-level checks that go beyond the unit suite.

### Test-script experiments

Each experiment below lists its main entrypoint and the files it depends on.

#### 1. uv compatibility matrix

Purpose: validate `pepip` behavior against multiple `uv` versions.

Files involved:

- `test-scripts/test_uv_versions.sh`
- `test-scripts/test_uv_versions_direct.sh`

Notes:

- `test_uv_versions.sh` runs the automated test suite and a real `pepip install idna==3.10` check across a `uv` version matrix.
- `test_uv_versions_direct.sh` exercises the CLI directly from source while swapping `uv` versions installed into an isolated prefix, which is useful for PATH and import-resolution issues.

#### 2. Package smoke matrix

Purpose: install representative Python packages in `uv` mode or `pepip` mode and run lightweight import/runtime verification.

Files involved:

- `test-scripts/install_smoke_matrix.py`
- `test-scripts/_smoke_matrix_utils.py`
- `test-scripts/results.tsv`
- `test-scripts/pepip_results.tsv`

Notes:

- Covers packages such as `numpy`, `pandas`, `scipy`, `scikit-learn`, `fastapi`, `sqlalchemy`, `httpx`, `polars`, `pillow`, `aiohttp`, and `lxml`.
- `results.tsv` and `pepip_results.tsv` store captured run results.

#### 3. External repository baseline with uv

Purpose: clone real repositories and confirm they install and test successfully with plain `uv`.

Files involved:

- `test-scripts/uv_repo_tester.sh`
- `test-scripts/uv_repos.txt`
- `test-scripts/uv_repos_success.txt`
- `test-scripts/uv_repos_failed.txt`
- `test-scripts/remove_finished.py`
- `test-scripts/sort-repos.py`

Notes:

- `uv_repos.txt` is the source repository list.
- `uv_repos_success.txt` and `uv_repos_failed.txt` capture the baseline outcome set.
- Helper scripts support curation and reruns of the repository list.

#### 4. External repository replay with pepip

Purpose: rerun the repositories that already passed under `uv` and compare whether `pepip` can replace the install flow successfully.

Files involved:

- `test-scripts/pepip_repo_tester.sh`
- `test-scripts/uv_repos_success.txt`
- `test-scripts/pepip_repos_success.txt`
- `test-scripts/pepip_repos_failed.txt`

Notes:

- The input is `uv_repos_success.txt` so the comparison is against repositories already proven to pass with `uv`.
- `pepip_repos_success.txt` and `pepip_repos_failed.txt` capture the replay results.

#### 5. Local manual sanity checks

Purpose: quickly check version isolation and disk-usage behavior across small local test projects.

Files involved:

- `test-scripts/test_package_versions.sh`
- `test-scripts/test_script.sh`

Typical validation commands:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 pytest
test-scripts/test_uv_versions.sh
python3 test-scripts/install_smoke_matrix.py --mode pepip --batch-size 5

# Run tests across multile repositories
test-scripts/uv_repo_tester.sh
test-scripts/pepip_repo_tester.sh
```

### Production readiness

`pepip` is in a reasonable state for real project use when your main concern is repeated dependency materialization across many local environments:

- Core installer invariants are explicitly tested.
- The store is interpreter/platform scoped, which reduces the risk of mixing incompatible artifacts.
- CLI behavior is covered with direct tests instead of relying only on manual usage.
- There is compatibility machinery for multiple `uv` release families, not just a single pinned toolchain.
- There are smoke and external-repo validation scripts for catching regressions that unit tests alone would miss.

Current limits still matter before wider production rollout:

- Console scripts are not linked into the local venv `bin` / `Scripts` directory yet.
- Namespace-package edge cases may still need more dedicated handling.
- The stronger compatibility scripts are present in-repo, but they are heavier than the default `pytest` path and should be part of release validation, not just ad hoc local testing.

### External repository experiment

The external repository comparison is defined by:

- [`test-scripts/uv_repo_tester.sh`](../test-scripts/uv_repo_tester.sh)
- [`test-scripts/pepip_repo_tester.sh`](../test-scripts/pepip_repo_tester.sh)
- [`test-scripts/uv_repos_success.txt`](../test-scripts/uv_repos_success.txt)
	- To add more repositories, please create an Issue.
- [`test-scripts/pepip_repos_success.txt`](../test-scripts/pepip_repos_success.txt)

Both scripts use the same high-level flow: clone each repository, create a virtual environment, install the project, and run tests. The uv script creates a repo list in which uv is successful, and the pepip script experiments on the repos in the same list.

Current result: The pass rate is 100%. All repositories that passed under `uv` also passed under `pepip` in this experiment. This proves that `pepip` is a viable replacement for `uv` in real-world projects.

## Readiness summary

For day-to-day local use, the repo now has three layers of confidence:

- focused unit and install-flow tests in `tests/`
- compatibility and smoke scripts in `test-scripts/`
- optional external-repository replay through `test-scripts/pepip_repo_tester.sh`

# Repositories tested on External repository experiment

| Repository                                                  | Stars | Forks |
| ----------------------------------------------------------- | ----: | ----: |
By popular companies:                                         |       | 	  |
| [github/spec-kit](https://github.com/github/spec-kit)       | 94.9k |  8.2k |
| [elastic/elasticsearch-py](https://github.com/elastic/elasticsearch-py) |  4.4k |  1.2k |
| [astral-sh/python-build-standalone](https://github.com/astral-sh/python-build-standalone) |  4.1k |   290 |
| [langchain-ai/langgraph-codeact](https://github.com/langchain-ai/langgraph-codeact) |   731 |    76 |
Over 10k stars:                                               |       |       |
| [vinta/awesome-python](https://github.com/vinta/awesome-python) | 296.9k | 27.9k |
| [rasbt/LLMs-from-scratch](https://github.com/rasbt/LLMs-from-scratch) | 92.3k | 14.3k |
| [pallets/flask](https://github.com/pallets/flask)           | 71.5k | 16.8k |
| [mitmproxy/mitmproxy](https://github.com/mitmproxy/mitmproxy) | 43.5k |  4.6k |
| [modelcontextprotocol/python-sdk](https://github.com/modelcontextprotocol/python-sdk) | 22.9k |  3.4k |
| [tiangolo/typer](https://github.com/tiangolo/typer)         | 19.4k |   892 |
| [pallets/click](https://github.com/pallets/click)           | 17.5k |  1.7k |
| [encode/starlette](https://github.com/encode/starlette)     | 12.3k |  1.2k |
| [tadata-org/fastapi_mcp](https://github.com/tadata-org/fastapi_mcp) | 11.9k |   945 |
| [simonw/llm](https://github.com/simonw/llm)                 | 11.8k |   833 |
| [pallets/jinja](https://github.com/pallets/jinja)           | 11.6k |  1.7k |
| [simonw/datasette](https://github.com/simonw/datasette)     |   11k |   828 |
| [encode/uvicorn](https://github.com/encode/uvicorn)         | 10.6k |   943 |
Over 1k stars:                                               |       |       |
| [ijl/orjson](https://github.com/ijl/orjson)                 |  8.1k |   304 |
| [pallets/werkzeug](https://github.com/pallets/werkzeug)     |  6.9k |  1.8k |
| [hynek/structlog](https://github.com/hynek/structlog)       |  4.8k |   279 |
| [samuelcolvin/watchfiles](https://github.com/samuelcolvin/watchfiles) |  2.5k |   133 |
| [simonw/sqlite-utils](https://github.com/simonw/sqlite-utils) |    2k |   137 |
| [litestar-org/polyfactory](https://github.com/litestar-org/polyfactory) |  1.5k |   111 |
| [fpgmaas/cookiecutter-uv](https://github.com/fpgmaas/cookiecutter-uv) |  1.3k |   188 |
| [osprey-oss/cookiecutter-uv](https://github.com/osprey-oss/cookiecutter-uv) |  1.3k |   188 |
Over 100 stars:                                               |       |       |
| [johnthagen/python-blueprint](https://github.com/johnthagen/python-blueprint) |   732 |   100 |
| [simonw/llm-gemini](https://github.com/simonw/llm-gemini)   |   438 |    51 |
| [hynek/svcs](https://github.com/hynek/svcs)                 |   414 |    24 |
| [a5chin/python-uv](https://github.com/a5chin/python-uv)     |   371 |    69 |
| [python-poetry/poetry-plugin-export](https://github.com/python-poetry/poetry-plugin-export) |   333 |    55 |
| [jlevy/simple-modern-uv](https://github.com/jlevy/simple-modern-uv) |   276 |    27 |
| [machow/quartodoc](https://github.com/machow/quartodoc)     |   262 |    30 |
| [GiovanniGiacometti/python-repo-template](https://github.com/GiovanniGiacometti/python-repo-template) |   160 |    10 |
| [hexlet-boilerplates/python-package](https://github.com/hexlet-boilerplates/python-package) |   142 |   232 |
Over 10 stars:                                               |       |       |
| [browniebroke/pypackage-template](https://github.com/browniebroke/pypackage-template) |    89 |    18 |
| [yezz123/pyngo](https://github.com/yezz123/pyngo)           |    88 |     8 |
| [simonw/llm-openai-plugin](https://github.com/simonw/llm-openai-plugin) |    52 |    12 |
| [IbraheemTuffaha/python-fastapi-template](https://github.com/IbraheemTuffaha/python-fastapi-template) |    51 |    14 |
| [mjun0812/python-project-template](https://github.com/mjun0812/python-project-template) |    32 |     6 |
| [PrefectHQ/examples](https://github.com/PrefectHQ/examples) |    30 |     3 |
| [lincc-frameworks/tdastro](https://github.com/lincc-frameworks/tdastro) |    26 |     3 |
| [gdamjan/uv-getting-started](https://github.com/gdamjan/uv-getting-started) |    16 |     6 |
| [bartdorlandt/convert_poetry2uv](https://github.com/bartdorlandt/convert_poetry2uv) |    13 |     2 |
| [ThomasBury/mlops-uv](https://github.com/ThomasBury/mlops-uv) |    13 |     3 |
Under 10 stars:                                               |       |       |
| [VectorInstitute/aieng-template-uv](https://github.com/VectorInstitute/aieng-template-uv) |     9 |     1 |
| [idatsy/python-base-uv](https://github.com/idatsy/python-base-uv) |     8 |     1 |
| [mgaitan/python-package-copier-template](https://github.com/mgaitan/python-package-copier-template) |     8 |     0 |
| [michplunkett/python-project-template](https://github.com/michplunkett/python-project-template) |     7 |     0 |
| [ryankanno/cookiecutter-py](https://github.com/ryankanno/cookiecutter-py) |     6 |     2 |
| [Diapolo10/python-uv-template](https://github.com/Diapolo10/python-uv-template) |     5 |     0 |
| [jarlor/uv-python-repo-template](https://github.com/jarlor/uv-python-repo-template) |     5 |     0 |
| [lalvarezt/uv-script-manager](https://github.com/lalvarezt/uv-script-manager) |     5 |     0 |
| [Miyamura80/Python-Template](https://github.com/Miyamura80/Python-Template) |     5 |     1 |
| [python-boilerplate/uv-template](https://github.com/python-boilerplate/uv-template) |     5 |     1 |
| [stateful-y/python-package-copier](https://github.com/stateful-y/python-package-copier) |     5 |     0 |
| [amir-kashi/python-uv-template](https://github.com/amir-kashi/python-uv-template) |     3 |     0 |
| [araa47/cookiecutter-python-uv-boilerplate](https://github.com/araa47/cookiecutter-python-uv-boilerplate) |     3 |     0 |
| [JeremieGince/PythonProject-Template](https://github.com/JeremieGince/PythonProject-Template) |     3 |     1 |
| [lucidfrontier45/python-uv-template](https://github.com/lucidfrontier45/python-uv-template) |     3 |     0 |
| [myrheimb/devenv-python-uv](https://github.com/myrheimb/devenv-python-uv) |     3 |     0 |
| [pivoshenko/uv-upsync](https://github.com/pivoshenko/uv-upsync) |     3 |     0 |
| [denisecase/applied-ml-template](https://github.com/denisecase/applied-ml-template) |     2 |    27 |
| [Geson-anko/python-uv-template](https://github.com/Geson-anko/python-uv-template) |     2 |     0 |
| [slangenbach/cookiecutter-python-uv](https://github.com/slangenbach/cookiecutter-python-uv) |     2 |     1 |
| [ulken94/uv_template](https://github.com/ulken94/uv_template) |     2 |     1 |
| [emasuriano/fastapi-uv-demo](https://github.com/emasuriano/fastapi-uv-demo) |     0 |     0 |
