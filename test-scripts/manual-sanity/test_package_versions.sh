#!/usr/bin/env bash
set -euo pipefail

# Validate that separate project folders can use different package versions.
#
# This script creates two project directories, installs different numpy/pandas
# versions with pepip, and then prints versions from each venv to confirm
# isolation and correct linking behavior.

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
  pepip install "numpy==2.4.4" "pandas==3.0.2"
)
(
  cd temp2
  pepip install "numpy==2.3.5" "pandas==2.3.0"
)

"$(venv_python "./temp1/.venv")" -c "import numpy; print(numpy.__version__); import pandas; print(pandas.__version__)"
"$(venv_python "./temp2/.venv")" -c "import numpy; print(numpy.__version__); import pandas; print(pandas.__version__)"
