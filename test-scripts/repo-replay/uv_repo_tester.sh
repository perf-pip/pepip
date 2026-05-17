#!/usr/bin/env bash
set -euo pipefail

# Replay a repo list with uv to establish a baseline success set.
#
# For each repo, this script clones the repo, creates a uv venv, installs
# dependencies plus pytest tooling, runs tests, and records successes so that
# later pepip runs can focus only on repos that already passed with uv.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
REPOS_FILE="${UV_REPOS_FILE:-${SCRIPT_DIR}/uv_repos.txt}"
WORK_DIR="${WORK_DIR:-${TMPDIR:-/tmp}/uv-repo-tests}"
REPO_TIMEOUT_SECS="${REPO_TIMEOUT_SECS:-1800}"
INSTALL_TIMEOUT_SECS="${INSTALL_TIMEOUT_SECS:-120}"
PYTEST_TIMEOUT_SECS="${PYTEST_TIMEOUT_SECS:-600}"
START_INDEX=0
LIMIT=0
INPUT_REPOS_FILE=""

usage() {
  cat <<'EOF'
Simple uv repo tester.

Flow per repo:
  1. Clone repo
  2. cd into repo
  3. Create uv venv in .venv at the repo root
  4. Install project/dependencies using uv commands
  5. Install pytest-related packages using uv commands
  6. Run pytest using the .venv Python
  7. Record successes immediately and skip them on later runs

Options:
  --repos PATH      File containing repository URLs, one per line
                    Defaults to test-scripts/repo-replay/uv_repos.txt
  --workdir PATH    Directory for clones and logs
  --start N         Zero-based repo index to start from
  --limit N         Maximum number of repos to process; 0 means no limit
  -h, --help        Show this help

Notes:
  - The virtual environment is always .venv in each cloned repo root.
EOF
}

while [[ "$#" -gt 0 ]]; do
  case "$1" in
    --repos) REPOS_FILE="$2"; shift 2 ;;
    --workdir) WORK_DIR="$2"; shift 2 ;;
    --start) START_INDEX="$2"; shift 2 ;;
    --limit) LIMIT="$2"; shift 2 ;;
    -h|--help)
      usage
      exit 0
      ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

for tool in git timeout uv; do
  if ! command -v "${tool}" >/dev/null 2>&1; then
    echo "${tool} is required on PATH." >&2
    exit 1
  fi
done

if [[ ! -f "${REPOS_FILE}" ]]; then
  echo "Repo file not found: ${REPOS_FILE}" >&2
  exit 1
fi

# Clear any previous work directory before starting
rm -rf "${WORK_DIR}"
mkdir -p "${WORK_DIR}/clones" "${WORK_DIR}/logs"
INPUT_REPOS_FILE="${WORK_DIR}/uv_repos_input.txt"
cp "${REPOS_FILE}" "${INPUT_REPOS_FILE}"

cleanup_workdir() {
  echo
  echo "Cleaning work directory: ${WORK_DIR}"
  rm -rf "${WORK_DIR}"
}

trap cleanup_workdir EXIT

SUCCESS_FILE="${SCRIPT_DIR}/uv_repos_success.txt"
FAILED_FILE="${SCRIPT_DIR}/uv_repos_failed.txt"
RESULTS_FILE="${SCRIPT_DIR}/results.tsv"
touch "${SUCCESS_FILE}" "${FAILED_FILE}"
if [[ ! -s "${RESULTS_FILE}" ]]; then
  printf 'repo\tstatus\tnote\tlog_file\n' > "${RESULTS_FILE}"
fi

UV_CACHE_DIR="/system/conda/miniconda3/uv/cache/"

repo_slug_from_url() {
  local url="$1"
  local no_git="${url%.git}"
  basename "${no_git}"
}

repo_is_successful() {
  grep -Fxq -- "$1" "${SUCCESS_FILE}" 2>/dev/null
}

remove_repo_url() {
  local repo_url="$1"
  local repos_file="$2"
  local temp_file
  temp_file="$(mktemp)"

  awk -v target="${repo_url}" '
    {
      raw = $0
      normalized = raw
      sub(/#.*/, "", normalized)
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", normalized)

      if (normalized == target) {
        next
      }

      print raw
    }
  ' "${repos_file}" > "${temp_file}"

  mv "${temp_file}" "${repos_file}"
}

repo_has_forbidden_packages() {
  local files=()

  [[ -f pyproject.toml ]] && files+=(pyproject.toml)
  [[ -f uv.lock ]] && files+=(uv.lock)

  if [[ "${#files[@]}" -gt 0 ]]; then
    rg -n -i -m 1 -F -e 'torch' -e 'transformers' -e 'sentence-transformers' "${files[@]}" >/dev/null 2>&1
  else
    return 1
  fi
}

record_success() {
  local repo_url="$1"
  if ! repo_is_successful "${repo_url}"; then
    printf '%s\n' "${repo_url}" >> "${SUCCESS_FILE}"
  fi
}

record_failure() {
  local repo_url="$1"
  local note="$2"
  printf '%s\t%s\n' "${repo_url}" "${note}" >> "${FAILED_FILE}"
}

write_result() {
  local repo_url="$1"
  local status="$2"
  local note="$3"
  local log_file="$4"
  printf '%s\t%s\t%s\t%s\n' "${repo_url}" "${status}" "${note}" "${log_file}" >> "${RESULTS_FILE}"
}

clear_uv_cache() {
  if [[ -d "${UV_CACHE_DIR}" ]]; then
    echo "Clearing uv cache: ${UV_CACHE_DIR}"
    rm -rf "${UV_CACHE_DIR}"
  fi
}

venv_python() {
  local venv_dir="${1:-.venv}"
  if [[ -x "${venv_dir}/Scripts/python.exe" ]]; then
    printf '%s\n' "${venv_dir}/Scripts/python.exe"
  else
    printf '%s\n' "${venv_dir}/bin/python"
  fi
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
  shift

  set +e
  timeout --preserve-status "${REPO_TIMEOUT_SECS}" "$@" 2>&1 | tee -a "${log_file}"
  local status="${PIPESTATUS[0]}"
  set -e

  if [[ "${status}" -ne 0 ]]; then
    echo "Command failed. Exit status: ${status}" | tee -a "${log_file}"
  fi

  return "${status}"
}

run_pytest_logged() {
  local log_file="$1"
  shift

  set +e
  timeout --preserve-status "${PYTEST_TIMEOUT_SECS}" "$@" 2>&1 | tee -a "${log_file}"
  local status="${PIPESTATUS[0]}"
  set -e

  # pytest exit code 5 means no tests were collected. For install-compatibility
  # sweeps, treat that as failure because no runnable test signal was produced.
  if [[ "${status}" -eq 5 ]]; then
    echo "Pytest collected no tests. Treating as fail." | tee -a "${log_file}"
    status=1
  fi

  if [[ "${status}" -ne 0 ]]; then
    echo "Command failed. Exit status: ${status}" | tee -a "${log_file}"
  fi

  return "${status}"
}

run_install_logged() {
  local log_file="$1"
  shift

  set +e
  timeout --preserve-status "${INSTALL_TIMEOUT_SECS}" "$@" 2>&1 | tee -a "${log_file}"
  local status="${PIPESTATUS[0]}"
  set -e

  if [[ "${status}" -ne 0 ]]; then
    echo "Command failed. Exit status: ${status}" | tee -a "${log_file}"
  fi

  return "${status}"
}

create_venv() {
  local log_file="$1"
  rm -rf .venv .pytest_cache

  log_section "${log_file}" "uv: create venv"
  run_logged "${log_file}" uv venv
}

install_repo_with_uv() {
  local log_file="$1"

  log_section "${log_file}" "uv: install repo/dependencies"

  if [[ -f pyproject.toml ]]; then
    # Simple order: try uv sync first, then editable install fallbacks.
    local python_bin
    python_bin="$(venv_python)"
    run_install_logged "${log_file}" uv sync --all-extras --dev && return 0
    run_install_logged "${log_file}" uv sync --dev && return 0
    run_install_logged "${log_file}" uv sync && return 0
    run_install_logged "${log_file}" uv pip install --python "${python_bin}" -e '.[all]' && return 0
    run_install_logged "${log_file}" uv pip install --python "${python_bin}" -e '.[test]' && return 0
    run_install_logged "${log_file}" uv pip install --python "${python_bin}" -e '.[tests]' && return 0
    run_install_logged "${log_file}" uv pip install --python "${python_bin}" -e '.[dev]' && return 0
    run_install_logged "${log_file}" uv pip install --python "${python_bin}" -e . && return 0
    return 1
  fi

  local installed_any=0
  local python_bin
  python_bin="$(venv_python)"
  local req
  for req in requirements-dev.txt dev-requirements.txt requirements-test.txt requirements-tests.txt test-requirements.txt requirements.txt; do
    if [[ -f "${req}" ]]; then
      installed_any=1
      run_install_logged "${log_file}" uv pip install --python "${python_bin}" -r "${req}" || return 1
    fi
  done

  if [[ -f setup.py || -f setup.cfg ]]; then
    run_install_logged "${log_file}" uv pip install --python "${python_bin}" -e . || return 1
    installed_any=1
  fi

  [[ "${installed_any}" -eq 1 ]]
}

install_test_packages() {
  local log_file="$1"
  local python_bin
  python_bin="$(venv_python)"
  log_section "${log_file}" "uv: install pytest tooling"
  run_install_logged "${log_file}" uv pip install --python "${python_bin}" \
    pytest pytest-cov pytest-mock pytest-xdist
}

run_tests() {
  local log_file="$1"
  local python_bin
  python_bin="$(venv_python)"
  log_section "${log_file}" "uv: pytest"
  run_pytest_logged "${log_file}" "${python_bin}" -m pytest -vv -ra --maxfail=1
}

echo "Repos file: ${REPOS_FILE}"
echo "Work dir: ${WORK_DIR}"
echo "Repo timeout seconds: ${REPO_TIMEOUT_SECS}"
echo "Install timeout seconds: ${INSTALL_TIMEOUT_SECS}"
echo "Pytest timeout seconds: ${PYTEST_TIMEOUT_SECS}"
echo "Pytest args: -vv -ra"
echo "Success file: ${SUCCESS_FILE}"

repo_index=0
processed_count=0

while IFS= read -r repo_url; do
  repo_url="${repo_url%%#*}"
  repo_url="$(echo "${repo_url}" | xargs)"
  [[ -z "${repo_url}" ]] && continue

  if [[ "${repo_index}" -lt "${START_INDEX}" ]]; then
    repo_index=$((repo_index + 1))
    continue
  fi

  if [[ "${LIMIT}" -gt 0 && "${processed_count}" -ge "${LIMIT}" ]]; then
    break
  fi

  repo_index=$((repo_index + 1))
  processed_count=$((processed_count + 1))

  if repo_is_successful "${repo_url}"; then
    echo "Skipping previously successful repo: ${repo_url}"
    write_result "${repo_url}" "skipped" "previous success" ""
    clear_uv_cache
    remove_repo_url "${repo_url}" "${REPOS_FILE}"
    continue
  fi

  repo_name="$(repo_slug_from_url "${repo_url}")"
  repo_dir="${WORK_DIR}/clones/${repo_name}"
  repo_log="${WORK_DIR}/logs/${repo_name}.log"
  : > "${repo_log}"

  echo
  echo "=============== ${repo_url} ==============="
  echo "Log: ${repo_log}"

  rm -rf "${repo_dir}"

  log_section "${repo_log}" "git clone"
  if ! run_logged "${repo_log}" git clone --depth 1 "${repo_url}" "${repo_dir}"; then
    record_failure "${repo_url}" "git clone failed"
    write_result "${repo_url}" "failed" "git clone failed" "${repo_log}"
    remove_repo_url "${repo_url}" "${REPOS_FILE}"
    continue
  fi

  if [[ ! -d "${repo_dir}" ]]; then
    record_failure "${repo_url}" "git clone failed (no directory)"
    write_result "${repo_url}" "failed" "git clone failed (no directory)" "${repo_log}"
    remove_repo_url "${repo_url}" "${REPOS_FILE}"
    continue
  fi

  pushd "${repo_dir}" >/dev/null

  note="ok"
  status="passed"
  if repo_has_forbidden_packages; then
    note="contains torch/transformers/sentence-transformers"
    status="skipped"
  fi

  if [[ "${status}" == "skipped" ]]; then
    :
  elif ! create_venv "${repo_log}"; then
    note="uv venv failed"
    status="failed"
  elif ! install_repo_with_uv "${repo_log}"; then
    note="uv install failed"
    status="failed"
  elif ! install_test_packages "${repo_log}"; then
    note="pytest tooling install failed"
    status="failed"
  elif ! run_tests "${repo_log}"; then
    note="pytest failed"
    status="failed"
  fi

  popd >/dev/null

  if [[ "${status}" == "passed" ]]; then
    record_success "${repo_url}"
    echo "Passed: ${repo_url}" | tee -a "${repo_log}"
  elif [[ "${status}" == "skipped" ]]; then
    echo "Skipped: ${repo_url} (${note})" | tee -a "${repo_log}"
  else
    record_failure "${repo_url}" "${note}"
    echo "Failed: ${repo_url} (${note})" | tee -a "${repo_log}"
  fi

  write_result "${repo_url}" "${status}" "${note}" "${repo_log}"
  remove_repo_url "${repo_url}" "${REPOS_FILE}"

  echo "Deleting repo folder: ${repo_dir}"
  rm -rf "${repo_dir}"
  clear_uv_cache
done < "${INPUT_REPOS_FILE}"

echo
echo "Results written to: ${RESULTS_FILE}"
echo "Logs written to: ${WORK_DIR}/logs"
echo "Successes: ${SUCCESS_FILE}"
echo "Failures:  ${FAILED_FILE}"
column -t -s $'\t' "${RESULTS_FILE}" || cat "${RESULTS_FILE}"
