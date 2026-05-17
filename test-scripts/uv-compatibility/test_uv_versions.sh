#!/usr/bin/env bash
set -euo pipefail

# Run pepip tests across a matrix of uv versions using per-version venvs.
#
# This script installs uv into isolated virtual environments for each version,
# runs the pepip test suite (or a configurable pytest target), and reports any
# failures so compatibility regressions are caught early.
#
# Usage:
#   test-scripts/uv-compatibility/test_uv_versions.sh
#   test-scripts/uv-compatibility/test_uv_versions.sh 0.4.30 0.5.22 0.6.17

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
WORK_DIR="${TMPDIR:-/tmp}/pepip-uv-version-matrix"
if [[ -n "${PYTHON:-}" ]]; then
  PYTHON_BIN="${PYTHON}"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
else
  PYTHON_BIN="python"
fi
PYTEST_TARGET="${PYTEST_TARGET:-tests}"

# Versions chosen to span multiple uv release families.
DEFAULT_UV_VERSIONS=(
  "0.4.0"
  "0.4.30"
  "0.5.0"
  "0.5.22"
  "0.6.0"
  "0.6.17"
  "0.7.0"
  "0.7.22"
  "0.8.0"
  "0.8.22"
  "0.9.0"
  "0.9.11"
  "0.10.0"
  "0.10.12"
  "0.11.0"
  "0.11.10"
  "0.11.14"
)

if [[ "$#" -gt 0 ]]; then
  UV_VERSIONS=("$@")
else
  UV_VERSIONS=("${DEFAULT_UV_VERSIONS[@]}")
fi

echo "Root: ${ROOT_DIR}"
echo "Work dir: ${WORK_DIR}"
echo "Python: ${PYTHON_BIN}"
echo "Pytest target: ${PYTEST_TARGET}"
echo "Testing uv versions: ${UV_VERSIONS[*]}"

rm -rf "${WORK_DIR}"
mkdir -p "${WORK_DIR}"

FAILURES=()

venv_activate() {
  local venv_dir="$1"
  if [[ -f "${venv_dir}/Scripts/activate" ]]; then
    # Support Windows' Git Bash
    printf '%s\n' "${venv_dir}/Scripts/activate"
  else
    printf '%s\n' "${venv_dir}/bin/activate"
  fi
}

venv_python() {
  local venv_dir="$1"
  if [[ -x "${venv_dir}/Scripts/python.exe" ]]; then
    # Support Windows' Git Bash
    printf '%s\n' "${venv_dir}/Scripts/python.exe"
  else
    printf '%s\n' "${venv_dir}/bin/python"
  fi
}

for uv_version in "${UV_VERSIONS[@]}"; do
  echo
  echo "=== Testing uv==${uv_version} ==="
  case_dir="${WORK_DIR}/uv-${uv_version}"
  venv_dir="${case_dir}/runner-venv"
  project_dir="${case_dir}/project"

  rm -rf "${case_dir}"
  mkdir -p "${case_dir}" "${project_dir}"

  "${PYTHON_BIN}" -m venv "${venv_dir}"
  # shellcheck disable=SC1091
  source "$(venv_activate "${venv_dir}")"

  if ! python -m pip install --upgrade pip >/dev/null 2>&1; then
    FAILURES+=("uv==${uv_version} (failed to upgrade pip)")
    deactivate || true
    continue
  fi

  if ! python -m pip install "uv==${uv_version}" "${ROOT_DIR}[test]" >/dev/null 2>&1; then
    FAILURES+=("uv==${uv_version} (failed to install uv/pepip[test])")
    deactivate || true
    continue
  fi

  if ! uv --version; then
    FAILURES+=("uv==${uv_version} (uv command unavailable after install)")
    deactivate || true
    continue
  fi

  echo "Installed uv version:"
  uv --version

  if ! (
    cd "${ROOT_DIR}"
    python -m pytest -q ${PYTEST_TARGET}
  ); then
    FAILURES+=("uv==${uv_version} (pytest failed for target: ${PYTEST_TARGET})")
    deactivate || true
    continue
  fi

  (
    cd "${project_dir}"
    if ! pepip install "idna==3.10" >/dev/null 2>&1; then
      exit 10
    fi

    project_python="$(venv_python "./.venv")"
    if ! "${project_python}" -c "import idna; assert idna.__version__ == '3.10'"; then
      exit 11
    fi
  )
  status=$?

  if [[ "${status}" -ne 0 ]]; then
    FAILURES+=("uv==${uv_version} (pepip install/verification failed, code ${status})")
  else
    echo "PASS uv==${uv_version}"
  fi

  deactivate || true
done

echo
if [[ "${#FAILURES[@]}" -gt 0 ]]; then
  echo "uv compatibility failures:"
  for failure in "${FAILURES[@]}"; do
    echo "  - ${failure}"
  done
  exit 1
fi

echo "All uv version checks passed."
