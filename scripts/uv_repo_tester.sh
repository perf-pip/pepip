#!/usr/bin/env bash
set -euo pipefail

# Test Python repositories with uv by default, and optionally compare pepip.
#
# Default mode:
#   1. Clone repo
#   2. Create a uv-managed venv
#   3. Install using uv-friendly project flows
#   4. Install pytest tooling with uv
#   5. Run pytest through uv
#   6. Record passing repos in uv_repos_success.txt and failing repos in uv_repos_failed.txt
#
# Pepip mode (--pepip):
#   1. Run the same uv baseline first
#   2. Only if uv baseline passes, freeze the uv environment
#   3. Install dependencies/project with pepip into a fresh venv
#   4. Run pytest through uv
#   5. Record pepip passing repos in pepip_repos_success.txt and failing repos in pepip_repos_failed.txt
#
# This script prints process output live and writes per-repo logs so failures
# are diagnosable. It avoids shell activation (`source .venv/bin/activate`) and
# uses uv commands / `uv run` wherever possible.
#
# Usage:
#   scripts/uv_repo_tester.sh
#   scripts/uv_repo_tester.sh --pepip
#   scripts/uv_repo_tester.sh --repos scripts/uv_repos.txt --workdir /tmp/pepip-uv-repos
#
# Env overrides:
#   PYTHON_BIN=python3.12
#   UV_REPOS_FILE=scripts/uv_repos.txt
#   WORK_DIR=/tmp/pepip-uv-repos
#   REPO_TIMEOUT_SECS=1800
#   PYTEST_ARGS='-vv -ra'

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
REPOS_FILE="${UV_REPOS_FILE:-${ROOT_DIR}/scripts/uv_repos.txt}"
WORK_DIR="${WORK_DIR:-${TMPDIR:-/tmp}/pepip-uv-repo-tests}"
REPO_TIMEOUT_SECS="${REPO_TIMEOUT_SECS:-60}"
PYTEST_ARGS="${PYTEST_ARGS:--vv -ra}"
UV_BASE_VENV=".venv-uv"
PEPIP_VENV=".venv-pepip"
RUN_PEPIP=0

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --pepip)
      RUN_PEPIP=1
      shift
      ;;
    --repos)
      REPOS_FILE="$2"
      shift 2
      ;;
    --workdir)
      WORK_DIR="$2"
      shift 2
      ;;
    --python)
      PYTHON_BIN="$2"
      shift 2
      ;;
    --pytest-args)
      PYTEST_ARGS="$2"
      shift 2
      ;;
    -h|--help)
      sed -n '1,45p' "$0" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "Unknown arg: $1" >&2
      exit 2
      ;;
  esac
done

for tool in uv timeout git; do
  if ! command -v "${tool}" >/dev/null 2>&1; then
    echo "${tool} is required on PATH." >&2
    exit 1
  fi
done

if [[ "${RUN_PEPIP}" -eq 1 ]]; then
  if ! "${PYTHON_BIN}" -c 'import pepip.cli' >/dev/null 2>&1; then
    echo "--pepip was passed, but pepip.cli is not importable by ${PYTHON_BIN}." >&2
    echo "Run this from the pepip repo or set PYTHONPATH so ${PYTHON_BIN} can import pepip.cli." >&2
    exit 1
  fi
fi

if [[ ! -f "${REPOS_FILE}" ]]; then
  echo "Repo file not found: ${REPOS_FILE}" >&2
  exit 1
fi

MODE="uv"
if [[ "${RUN_PEPIP}" -eq 1 ]]; then
  MODE="pepip"
fi

mkdir -p "${WORK_DIR}/clones" "${WORK_DIR}/logs"
rm -f \
  "${WORK_DIR}/uv_repos_success.txt" \
  "${WORK_DIR}/uv_repos_failed.txt" \
  "${WORK_DIR}/pepip_repos_success.txt" \
  "${WORK_DIR}/pepip_repos_failed.txt"

RESULTS_FILE="${WORK_DIR}/results.tsv"
printf 'repo\tmode\tuv_status\tpepip_status\tnote\tlog_file\n' > "${RESULTS_FILE}"

touch "${WORK_DIR}/uv_repos_success.txt" "${WORK_DIR}/uv_repos_failed.txt"
if [[ "${RUN_PEPIP}" -eq 1 ]]; then
  touch "${WORK_DIR}/pepip_repos_success.txt" "${WORK_DIR}/pepip_repos_failed.txt"
fi

echo "Root: ${ROOT_DIR}"
echo "Repos file: ${REPOS_FILE}"
echo "Work dir: ${WORK_DIR}"
echo "Mode: ${MODE}"
echo "Python: ${PYTHON_BIN}"
echo "Repo timeout seconds: ${REPO_TIMEOUT_SECS}"
echo "Pytest args: ${PYTEST_ARGS}"

run_with_timeout() {
  local seconds="$1"
  shift
  timeout --preserve-status "${seconds}" "$@"
}

log_section() {
  local log_file="$1"
  local title="$2"
  {
    echo
    echo "----- ${title} -----"
    date '+%Y-%m-%d %H:%M:%S %Z'
  } | tee -a "${log_file}"
}

run_logged() {
  local log_file="$1"
  local seconds="$2"
  shift 2

  set +e
  run_with_timeout "${seconds}" "$@" 2>&1 | tee -a "${log_file}"
  local status="${PIPESTATUS[0]}"
  set -e

  if [[ "${status}" -eq 124 || "${status}" -eq 137 || "${status}" -eq 143 ]]; then
    echo "Command timed out or was terminated. Exit status: ${status}" | tee -a "${log_file}"
  elif [[ "${status}" -ne 0 ]]; then
    echo "Command failed. Exit status: ${status}" | tee -a "${log_file}"
  fi

  return "${status}"
}

run_logged_allow_pytest_no_tests() {
  local log_file="$1"
  local seconds="$2"
  shift 2

  set +e
  run_with_timeout "${seconds}" "$@" 2>&1 | tee -a "${log_file}"
  local status="${PIPESTATUS[0]}"
  set -e

  if [[ "${status}" -eq 5 ]]; then
    echo "Pytest collected no tests. Treating this as passing for install compatibility." | tee -a "${log_file}"
    return 0
  fi

  if [[ "${status}" -eq 124 || "${status}" -eq 137 || "${status}" -eq 143 ]]; then
    echo "Command timed out or was terminated. Exit status: ${status}" | tee -a "${log_file}"
  elif [[ "${status}" -ne 0 ]]; then
    echo "Command failed. Exit status: ${status}" | tee -a "${log_file}"
  fi

  return "${status}"
}

repo_slug_from_url() {
  local url="$1"
  local no_git="${url%.git}"
  basename "${no_git}"
}

record_uv_success() {
  local repo_url="$1"
  printf '%s\n' "${repo_url}" >> "${WORK_DIR}/uv_repos_success.txt"
}

record_uv_failure() {
  local repo_url="$1"
  local note="$2"
  printf '%s\t%s\n' "${repo_url}" "${note}" >> "${WORK_DIR}/uv_repos_failed.txt"
}

record_pepip_success() {
  local repo_url="$1"
  printf '%s\n' "${repo_url}" >> "${WORK_DIR}/pepip_repos_success.txt"
}

record_pepip_failure() {
  local repo_url="$1"
  local note="$2"
  printf '%s\t%s\n' "${repo_url}" "${note}" >> "${WORK_DIR}/pepip_repos_failed.txt"
}

write_result() {
  local repo_url="$1"
  local uv_status="$2"
  local pepip_status="$3"
  local note="$4"
  local log_file="$5"
  printf '%s\t%s\t%s\t%s\t%s\t%s\n' "${repo_url}" "${MODE}" "${uv_status}" "${pepip_status}" "${note}" "${log_file}" >> "${RESULTS_FILE}"
}

install_common_test_tools() {
  local venv_dir="$1"
  local log_file="$2"
  local label="$3"

  # pytest-cov is common because many repos place --cov in pytest config.
  # pytest-mock and pytest-xdist are low-risk and frequently required by tests.
  log_section "${log_file}" "${label}: install pytest tooling"
  run_logged "${log_file}" "${REPO_TIMEOUT_SECS}" \
    uv pip --python "${venv_dir}/bin/python" install pytest pytest-cov pytest-mock pytest-xdist
}

install_pyproject_baseline() {
  local log_file="$1"

  # Most uv-native projects are happiest with uv sync. Try richer/common
  # variants first, then progressively relax. Keep every sync bound to the
  # repo-local ${UV_BASE_VENV} through UV_PROJECT_ENVIRONMENT.
  log_section "${log_file}" "uv baseline: pyproject install"

  if run_logged "${log_file}" "${REPO_TIMEOUT_SECS}" env UV_PROJECT_ENVIRONMENT="${UV_BASE_VENV}" uv sync --all-extras --dev; then
    return 0
  fi

  if run_logged "${log_file}" "${REPO_TIMEOUT_SECS}" env UV_PROJECT_ENVIRONMENT="${UV_BASE_VENV}" uv sync --all-extras; then
    return 0
  fi

  if run_logged "${log_file}" "${REPO_TIMEOUT_SECS}" env UV_PROJECT_ENVIRONMENT="${UV_BASE_VENV}" uv sync --dev; then
    return 0
  fi

  if run_logged "${log_file}" "${REPO_TIMEOUT_SECS}" env UV_PROJECT_ENVIRONMENT="${UV_BASE_VENV}" uv sync; then
    return 0
  fi

  # Fallbacks for repos with pyproject.toml but no uv project metadata, invalid
  # lock constraints for the current platform, or extras that are missing.
  # Important: if .[all] fails, automatically retry plain editable install.
  if run_logged "${log_file}" "${REPO_TIMEOUT_SECS}" uv pip --python "${UV_BASE_VENV}/bin/python" install -e '.[all]'; then
    return 0
  fi

  if run_logged "${log_file}" "${REPO_TIMEOUT_SECS}" uv pip --python "${UV_BASE_VENV}/bin/python" install -e '.[test]'; then
    return 0
  fi

  if run_logged "${log_file}" "${REPO_TIMEOUT_SECS}" uv pip --python "${UV_BASE_VENV}/bin/python" install -e '.[tests]'; then
    return 0
  fi

  if run_logged "${log_file}" "${REPO_TIMEOUT_SECS}" uv pip --python "${UV_BASE_VENV}/bin/python" install -e '.[dev]'; then
    return 0
  fi

  run_logged "${log_file}" "${REPO_TIMEOUT_SECS}" uv pip --python "${UV_BASE_VENV}/bin/python" install -e .
}

install_requirements_baseline() {
  local log_file="$1"

  log_section "${log_file}" "uv baseline: requirements install"

  local installed_any=0
  local req
  for req in requirements-dev.txt dev-requirements.txt requirements-test.txt requirements-tests.txt test-requirements.txt requirements.txt; do
    if [[ -f "${req}" ]]; then
      installed_any=1
      if ! run_logged "${log_file}" "${REPO_TIMEOUT_SECS}" uv pip --python "${UV_BASE_VENV}/bin/python" install -r "${req}"; then
        return 1
      fi
    fi
  done

  if [[ "${installed_any}" -eq 0 ]]; then
    return 1
  fi

  if [[ -f setup.py || -f setup.cfg ]]; then
    # Ensure the repo itself is importable for src-layout and package tests.
    run_logged "${log_file}" "${REPO_TIMEOUT_SECS}" uv pip --python "${UV_BASE_VENV}/bin/python" install -e . || true
  fi
}

install_baseline() {
  local log_file="$1"

  if [[ -f pyproject.toml ]]; then
    install_pyproject_baseline "${log_file}"
    return "$?"
  fi

  install_requirements_baseline "${log_file}"
}

run_pytest_with_env() {
  local venv_dir="$1"
  local log_file="$2"

  # Prefer python -m pytest so the interpreter and installed packages come from
  # the selected venv. Use uv run instead of venv activation.
  run_logged_allow_pytest_no_tests "${log_file}" "${REPO_TIMEOUT_SECS}" \
    uv run --python "${venv_dir}/bin/python" python -m pytest ${PYTEST_ARGS}
}

run_uv_baseline_for_current_repo() {
  local repo_url="$1"
  local repo_log="$2"

  rm -rf "${UV_BASE_VENV}" .pytest_cache

  log_section "${repo_log}" "uv baseline: create venv"
  if ! run_logged "${repo_log}" "${REPO_TIMEOUT_SECS}" uv venv "${UV_BASE_VENV}" --python "${PYTHON_BIN}"; then
    record_uv_failure "${repo_url}" "uv venv failed"
    write_result "${repo_url}" "failed" "not_run" "uv venv failed" "${repo_log}"
    return 1
  fi

  if ! install_baseline "${repo_log}"; then
    record_uv_failure "${repo_url}" "uv install failed"
    write_result "${repo_url}" "failed" "not_run" "uv install failed" "${repo_log}"
    return 1
  fi

  if ! install_common_test_tools "${UV_BASE_VENV}" "${repo_log}" "uv baseline"; then
    record_uv_failure "${repo_url}" "uv pytest tooling install failed"
    write_result "${repo_url}" "failed" "not_run" "uv pytest tooling install failed" "${repo_log}"
    return 1
  fi

  log_section "${repo_log}" "uv baseline: pytest"
  if ! run_pytest_with_env "${UV_BASE_VENV}" "${repo_log}"; then
    record_uv_failure "${repo_url}" "uv pytest failed"
    write_result "${repo_url}" "failed" "not_run" "uv pytest failed" "${repo_log}"
    return 1
  fi

  echo "uv baseline passed." | tee -a "${repo_log}"
  record_uv_success "${repo_url}"
  return 0
}

run_pepip_for_current_repo() {
  local repo_url="$1"
  local repo_log="$2"

  rm -rf "${PEPIP_VENV}" .pytest_cache

  log_section "${repo_log}" "uv baseline: pip freeze"
  if ! run_logged "${repo_log}" "${REPO_TIMEOUT_SECS}" bash -lc "uv pip --python '${UV_BASE_VENV}/bin/python' freeze > .pepip-baseline-requirements.txt"; then
    record_pepip_failure "${repo_url}" "pip freeze failed"
    write_result "${repo_url}" "passed" "failed" "pip freeze failed" "${repo_log}"
    return 1
  fi

  # Drop editable/local installs from freeze, then install the repo separately.
  grep -vE '^-e | @ file://| @ editable' .pepip-baseline-requirements.txt > .pepip-baseline-requirements-noneditable.txt || true

  log_section "${repo_log}" "pepip: create venv"
  if ! run_logged "${repo_log}" "${REPO_TIMEOUT_SECS}" uv venv "${PEPIP_VENV}" --python "${PYTHON_BIN}"; then
    record_pepip_failure "${repo_url}" "pepip venv failed"
    write_result "${repo_url}" "passed" "failed" "pepip venv failed" "${repo_log}"
    return 1
  fi

  log_section "${repo_log}" "pepip: dependency install"
  if [[ -s .pepip-baseline-requirements-noneditable.txt ]]; then
    if ! run_logged "${repo_log}" "${REPO_TIMEOUT_SECS}" env PYTHONPATH="${ROOT_DIR}:${PYTHONPATH:-}" "${PYTHON_BIN}" -m pepip.cli install -r .pepip-baseline-requirements-noneditable.txt --venv "${PEPIP_VENV}"; then
      record_pepip_failure "${repo_url}" "pepip install -r failed"
      write_result "${repo_url}" "passed" "failed" "pepip install -r failed" "${repo_log}"
      return 1
    fi
  else
    echo "No non-editable dependencies to install with pepip." | tee -a "${repo_log}"
  fi

  log_section "${repo_log}" "pepip: project install"
  if ! run_logged "${repo_log}" "${REPO_TIMEOUT_SECS}" env PYTHONPATH="${ROOT_DIR}:${PYTHONPATH:-}" "${PYTHON_BIN}" -m pepip.cli install . --venv "${PEPIP_VENV}"; then
    record_pepip_failure "${repo_url}" "pepip install . failed"
    write_result "${repo_url}" "passed" "failed" "pepip install . failed" "${repo_log}"
    return 1
  fi

  if ! install_common_test_tools "${PEPIP_VENV}" "${repo_log}" "pepip"; then
    record_pepip_failure "${repo_url}" "pepip pytest tooling install failed"
    write_result "${repo_url}" "passed" "failed" "pepip pytest tooling install failed" "${repo_log}"
    return 1
  fi

  log_section "${repo_log}" "pepip: pytest"
  if ! run_pytest_with_env "${PEPIP_VENV}" "${repo_log}"; then
    record_pepip_failure "${repo_url}" "pepip pytest failed"
    write_result "${repo_url}" "passed" "failed" "pepip pytest failed" "${repo_log}"
    return 1
  fi

  echo "pepip passed." | tee -a "${repo_log}"
  record_pepip_success "${repo_url}"
  write_result "${repo_url}" "passed" "passed" "ok" "${repo_log}"
}

while IFS= read -r repo_url; do
  repo_url="${repo_url%%#*}"
  repo_url="$(echo "${repo_url}" | xargs)"

  [[ -z "${repo_url}" ]] && continue

  repo_name="$(repo_slug_from_url "${repo_url}")"
  repo_dir="${WORK_DIR}/clones/${repo_name}"
  repo_log="${WORK_DIR}/logs/${repo_name}.log"

  : > "${repo_log}"

  echo
  echo "  =============== ${repo_url} ===============  "
  echo "Log: ${repo_log}"

  log_section "${repo_log}" "repo ${repo_url}"

  rm -rf "${repo_dir}"
  log_section "${repo_log}" "git clone"
  if ! run_logged "${repo_log}" "${REPO_TIMEOUT_SECS}" git clone --depth 1 "${repo_url}" "${repo_dir}"; then
    echo "Clone failed: ${repo_url}"
    record_uv_failure "${repo_url}" "git clone failed"
    if [[ "${RUN_PEPIP}" -eq 1 ]]; then
      record_pepip_failure "${repo_url}" "git clone failed"
    fi
    write_result "${repo_url}" "clone_failed" "not_run" "git clone failed" "${repo_log}"
    continue
  fi

  pushd "${repo_dir}" >/dev/null

  if [[ ! -f pyproject.toml && ! -f setup.py && ! -f setup.cfg && ! -f requirements.txt && ! -f requirements-dev.txt && ! -f dev-requirements.txt && ! -f requirements-test.txt && ! -f requirements-tests.txt && ! -f test-requirements.txt ]]; then
    echo "No supported install input. Skipping." | tee -a "${repo_log}"
    record_uv_failure "${repo_url}" "no supported install input"
    if [[ "${RUN_PEPIP}" -eq 1 ]]; then
      record_pepip_failure "${repo_url}" "no supported install input"
    fi
    write_result "${repo_url}" "skipped" "not_run" "no supported install input" "${repo_log}"
    popd >/dev/null
    continue
  fi

  if ! run_uv_baseline_for_current_repo "${repo_url}" "${repo_log}"; then
    if [[ "${RUN_PEPIP}" -eq 1 ]]; then
      # Pepip is only meaningful after a passing uv baseline, but keep the
      # requested pepip failure file complete for every repo considered.
      record_pepip_failure "${repo_url}" "uv baseline failed"
    fi
    popd >/dev/null
    continue
  fi

  if [[ "${RUN_PEPIP}" -eq 1 ]]; then
    run_pepip_for_current_repo "${repo_url}" "${repo_log}" || true
  else
    write_result "${repo_url}" "passed" "not_run" "ok" "${repo_log}"
  fi

  popd >/dev/null
done < "${REPOS_FILE}"

echo
echo "Results written to: ${RESULTS_FILE}"
echo "Logs written to: ${WORK_DIR}/logs"
echo "uv successes: ${WORK_DIR}/uv_repos_success.txt"
echo "uv failures:  ${WORK_DIR}/uv_repos_failed.txt"
if [[ "${RUN_PEPIP}" -eq 1 ]]; then
  echo "pepip successes: ${WORK_DIR}/pepip_repos_success.txt"
  echo "pepip failures:  ${WORK_DIR}/pepip_repos_failed.txt"
fi
column -t -s $'\t' "${RESULTS_FILE}" || cat "${RESULTS_FILE}"
