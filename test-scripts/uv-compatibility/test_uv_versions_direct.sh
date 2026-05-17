#!/usr/bin/env bash
set -euo pipefail

# Run pepip tests across a matrix of uv versions installed directly on PATH.
#
# This variant installs uv into the active Python environment instead of
# creating per-version venvs. It is useful for quick checks in CI or local
# environments where creating many venvs is undesirable.
#
# Usage:
#   test-scripts/uv-compatibility/test_uv_versions_direct.sh
#   test-scripts/uv-compatibility/test_uv_versions_direct.sh 0.4.30 0.5.22 0.6.17

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
echo "Testing uv versions: ${UV_VERSIONS[*]}"

rm -rf "${WORK_DIR}"
mkdir -p "${WORK_DIR}"

FAILURES=()

prefix_scripts_dir() {
  local prefix_dir="$1"
  if [[ -d "${prefix_dir}/Scripts" ]]; then
    printf '%s\n' "${prefix_dir}/Scripts"
  else
    printf '%s\n' "${prefix_dir}/bin"
  fi
}

venv_python() {
  local venv_dir="$1"
  if [[ -x "${venv_dir}/Scripts/python.exe" ]]; then
    printf '%s\n' "${venv_dir}/Scripts/python.exe"
  else
    printf '%s\n' "${venv_dir}/bin/python"
  fi
}

for uv_version in "${UV_VERSIONS[@]}"; do
  echo
  echo "=== Testing uv==${uv_version} ==="
  case_dir="${WORK_DIR}/uv-${uv_version}"
  prefix_dir="${case_dir}/prefix"
  pepip_home="${case_dir}/pepip-home"
  project_dir="${case_dir}/project"

  rm -rf "${case_dir}"
  mkdir -p "${case_dir}" "${project_dir}" "${prefix_dir}" "${pepip_home}"

  if ! "${PYTHON_BIN}" -m pip install --prefix "${prefix_dir}" "uv==${uv_version}" >/dev/null 2>&1; then
    FAILURES+=("uv==${uv_version} (failed to install uv into prefix)")
    continue
  fi

  pip_prefix_scripts_dir="$(prefix_scripts_dir "${prefix_dir}")"
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

    project_python="$(venv_python "./.venv")"
    if ! "${project_python}" -c "import idna; assert idna.__version__ == '3.10'"; then
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
