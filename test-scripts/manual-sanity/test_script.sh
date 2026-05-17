#!/usr/bin/env bash
set -euo pipefail

# Test by installing the same packages in multiple folders,
# allowing to check the storage used by each folder.

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
