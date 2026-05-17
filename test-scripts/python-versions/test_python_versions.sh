#!/usr/bin/env bash
set -euo pipefail

# Run pepip tests across supported Python minor versions.
#
# The script asks uv to install each requested Python version into a
# script-owned install directory, creates one isolated runner virtual
# environment per version, installs pepip[test] from the current checkout, runs
# pytest, then verifies a small pepip install in a throwaway project.
#
# Usage:
#   test-scripts/python-versions/test_python_versions.sh
#   test-scripts/python-versions/test_python_versions.sh 3.10 3.11 3.12

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
WORK_DIR="${TMPDIR:-/tmp}/pepip-python-version-matrix"
PYTHON_INSTALL_DIR="${PYTHON_INSTALL_DIR:-${WORK_DIR}/python-installations}"
PYTEST_TARGET="${PYTEST_TARGET:-tests}"
export UV_PYTHON_INSTALL_DIR="${PYTHON_INSTALL_DIR}"

DEFAULT_PYTHON_VERSIONS=(
  "3.8"
  "3.9"
  "3.10"
  "3.11"
  "3.12"
  "3.13"
  "3.14"
)

if [[ "$#" -gt 0 ]]; then
  PYTHON_VERSIONS=("$@")
else
  PYTHON_VERSIONS=("${DEFAULT_PYTHON_VERSIONS[@]}")
fi

usage() {
  cat <<'EOF'
Run pepip tests across Python minor versions.

Usage:
  test-scripts/python-versions/test_python_versions.sh [PYTHON_VERSION...]

Examples:
  test-scripts/python-versions/test_python_versions.sh
  test-scripts/python-versions/test_python_versions.sh 3.11 3.12

Environment variables:
  PYTEST_TARGET=tests/installer           Limit the pytest target.
  TMPDIR=/path/to/tmp                     Change where matrix directories are created.
  PYTHON_INSTALL_DIR=/path/to/pythons     Change where uv installs Python versions.

Default matrix:
  3.8 3.9 3.10 3.11 3.12 3.13 3.14
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

venv_activate() {
  local venv_dir="$1"
  if [[ -f "${venv_dir}/Scripts/activate" ]]; then
    # Support Windows' Git Bash.
    printf '%s\n' "${venv_dir}/Scripts/activate"
  else
    printf '%s\n' "${venv_dir}/bin/activate"
  fi
}

venv_python() {
  local venv_dir="$1"
  if [[ -x "${venv_dir}/Scripts/python.exe" ]]; then
    # Support Windows' Git Bash.
    printf '%s\n' "${venv_dir}/Scripts/python.exe"
  else
    printf '%s\n' "${venv_dir}/bin/python"
  fi
}

echo "Root: ${ROOT_DIR}"
echo "Work dir: ${WORK_DIR}"
echo "uv Python install dir: ${PYTHON_INSTALL_DIR}"
echo "Pytest target: ${PYTEST_TARGET}"
echo "Testing Python versions: ${PYTHON_VERSIONS[*]}"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required but was not found on PATH." >&2
  exit 1
fi

rm -rf "${WORK_DIR}"
mkdir -p "${WORK_DIR}" "${PYTHON_INSTALL_DIR}"

FAILURES=()

for python_version in "${PYTHON_VERSIONS[@]}"; do
  echo
  echo "=== Testing Python ${python_version} ==="

  if ! uv python install --install-dir "${PYTHON_INSTALL_DIR}" "${python_version}"; then
    FAILURES+=("Python ${python_version} (uv failed to install interpreter)")
    continue
  fi

  if ! python_bin="$(uv python find --managed-python --no-project "${python_version}")"; then
    FAILURES+=("Python ${python_version} (uv failed to resolve managed interpreter)")
    continue
  fi
  echo "uv-managed interpreter: ${python_bin}"
  "${python_bin}" --version

  case_dir="${WORK_DIR}/python-${python_version}"
  venv_dir="${case_dir}/runner-venv"
  project_dir="${case_dir}/project"

  rm -rf "${case_dir}"
  mkdir -p "${case_dir}" "${project_dir}"

  if ! "${python_bin}" -m venv "${venv_dir}"; then
    FAILURES+=("Python ${python_version} (failed to create runner venv)")
    continue
  fi

  # shellcheck disable=SC1091
  source "$(venv_activate "${venv_dir}")"

  if ! python -m pip install --upgrade pip >/dev/null 2>&1; then
    FAILURES+=("Python ${python_version} (failed to upgrade pip)")
    deactivate || true
    continue
  fi

  if ! (
    cd "${ROOT_DIR}"
    python -m pip install ".[test]" >/dev/null 2>&1
  ); then
    FAILURES+=("Python ${python_version} (failed to install pepip[test])")
    deactivate || true
    continue
  fi

  if ! (
    cd "${ROOT_DIR}"
    python -m pytest -q ${PYTEST_TARGET}
  ); then
    FAILURES+=("Python ${python_version} (pytest failed for target: ${PYTEST_TARGET})")
    deactivate || true
    continue
  fi

  if ! (
    cd "${project_dir}"
    export PEPIP_HOME="${case_dir}/pepip-home"
    pepip install "idna==3.10" >/dev/null 2>&1
    project_python="$(venv_python "./.venv")"
    "${project_python}" -c "import idna; assert idna.__version__ == '3.10'"
  ); then
    FAILURES+=("Python ${python_version} (pepip install/verification failed)")
  else
    echo "PASS Python ${python_version}"
  fi

  deactivate || true
done

echo
if [[ "${#FAILURES[@]}" -gt 0 ]]; then
  echo "Python version matrix failures:"
  for failure in "${FAILURES[@]}"; do
    echo "  - ${failure}"
  done
  exit 1
fi

echo "All Python version checks passed."
