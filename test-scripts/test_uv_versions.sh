#!/usr/bin/env bash
set -euo pipefail

# Test pepip install flow against a wide uv version matrix.
# Usage:
#   scripts/test_uv_versions.sh
#   scripts/test_uv_versions.sh 0.4.30 0.5.22 0.6.17

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK_DIR="${TMPDIR:-/tmp}/pepip-uv-version-matrix"
PYTHON_BIN="${PYTHON:-python3}"
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
  source "${venv_dir}/bin/activate"

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

    if ! ./.venv/bin/python -c "import idna; assert idna.__version__ == '3.10'"; then
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
