#!/usr/bin/env bash
set -euo pipefail

# This version of the script installs "uv" directly
# without installing into a virtual environment.

# Test pepip install flow against a wide uv version matrix.
# Usage:
#   scripts/test_uv_versions.sh
#   scripts/test_uv_versions.sh 0.4.30 0.5.22 0.6.17

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WORK_DIR="${TMPDIR:-/tmp}/pepip-uv-version-matrix"
PYTHON_BIN="${PYTHON:-python3}"

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
  "0.10.22"
  "0.11.0"
)

if [[ "$#" -gt 0 ]]; then
  UV_VERSIONS=("$@")
else
  UV_VERSIONS=("${DEFAULT_UV_VERSIONS[@]}")
fi

echo "Root: ${ROOT_DIR}"
echo "Work dir: ${WORK_DIR}"
echo "Python: ${PYTHON_BIN}"
echo "Testing uv versions: ${UV_VERSIONS[*]}"

rm -rf "${WORK_DIR}"
mkdir -p "${WORK_DIR}"

FAILURES=()

for uv_version in "${UV_VERSIONS[@]}"; do
  echo
  echo "=== Testing uv==${uv_version} ==="
  case_dir="${WORK_DIR}/uv-${uv_version}"
  prefix_dir="${case_dir}/prefix"
  pepip_home="${case_dir}/pepip-home"
  project_dir="${case_dir}/project"
  pip_prefix_scripts_dir="${prefix_dir}/bin"

  rm -rf "${case_dir}"
  mkdir -p "${case_dir}" "${project_dir}" "${prefix_dir}" "${pepip_home}"

  if ! "${PYTHON_BIN}" -m pip install --prefix "${prefix_dir}" "uv==${uv_version}" >/dev/null 2>&1; then
    FAILURES+=("uv==${uv_version} (failed to install uv into prefix)")
    continue
  fi

  site_packages="$("${PYTHON_BIN}" -c "import sysconfig; print(sysconfig.get_path('purelib', vars={'base': '${prefix_dir}', 'platbase': '${prefix_dir}'}))")"

  cli_pythonpath="${ROOT_DIR}:${site_packages}"

  if ! env PATH="${pip_prefix_scripts_dir}:${PATH}" PYTHONPATH="${cli_pythonpath}" "${PYTHON_BIN}" -m pepip.cli --help >/dev/null 2>&1; then
    FAILURES+=("uv==${uv_version} (pepip CLI unavailable from source + uv prefix)")
    continue
  fi

  if ! env PATH="${pip_prefix_scripts_dir}:${PATH}" PYTHONPATH="${site_packages}" uv --version; then
    FAILURES+=("uv==${uv_version} (uv command unavailable after install)")
    continue
  fi

  if (
    cd "${project_dir}"
    if ! env \
      PATH="${pip_prefix_scripts_dir}:${PATH}" \
      PYTHONPATH="${cli_pythonpath}" \
      PEPIP_HOME="${pepip_home}" \
      "${PYTHON_BIN}" -m pepip.cli install "idna==3.10" >/dev/null 2>&1; then
      exit 10
    fi

    if ! ./.venv/bin/python -c "import idna; assert idna.__version__ == '3.10'"; then
      exit 11
    fi
  ); then
    status=0
  else
    status=$?
  fi

  if [[ "${status}" -ne 0 ]]; then
    FAILURES+=("uv==${uv_version} (pepip install/verification failed, code ${status})")
  else
    echo "PASS uv==${uv_version}"
  fi
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
