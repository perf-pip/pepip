#!/usr/bin/env bash
set -euo pipefail

# Install the same packages across multiple folders to compare disk usage.
#
# Creates a set of temp project directories, installs numpy and pandas using
# pepip, then shows per-directory storage consumption to highlight symlink
# savings versus fully duplicated environments.

WORK_DIR="${TMPDIR:-/tmp}/pepip-test"

mkdir -p "${WORK_DIR}"
cd "${WORK_DIR}"
rm -rf temp*

for i in {1..10}; do
  mkdir "temp${i}"
  (
    cd "temp${i}"
    pepip install numpy pandas
  )
done

# Now, check the storage used by each folder
if command -v ncdu >/dev/null 2>&1; then
  ncdu
else
  du -sh temp*
fi
