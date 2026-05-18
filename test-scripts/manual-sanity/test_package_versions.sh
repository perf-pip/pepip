#!/usr/bin/env bash
set -euo pipefail

# Validate that separate project folders can use different package versions.
#
# This script creates two project directories, installs different pure-Python
# package versions with pepip, and then prints versions from each venv to
# confirm isolation and correct linking behavior. Pure-Python packages keep the
# check portable on Windows without depending on a native build toolchain.

venv_python() {
  local venv_dir="$1"
  if [[ -x "${venv_dir}/Scripts/python.exe" ]]; then
    printf '%s\n' "${venv_dir}/Scripts/python.exe"
  else
    printf '%s\n' "${venv_dir}/bin/python"
  fi
}

WORK_DIR="${TMPDIR:-/tmp}/pepip-test"

mkdir -p "${WORK_DIR}"
cd "${WORK_DIR}"
rm -rf temp*
mkdir temp1 temp2

(
  cd temp1
  pepip install "click==8.1.7" "requests==2.32.3"
)
(
  cd temp2
  pepip install "click==8.1.3" "requests==2.31.0"
)

"$(venv_python "./temp1/.venv")" -c "import importlib.metadata as md; import click, requests; print(md.version('click')); print(md.version('requests'))"
"$(venv_python "./temp2/.venv")" -c "import importlib.metadata as md; import click, requests; print(md.version('click')); print(md.version('requests'))"
