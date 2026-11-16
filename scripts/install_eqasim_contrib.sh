#!/usr/bin/env bash
# Add this project's contributions to an eqasim-france checkout (v1.5.0).
#
#   bash scripts/install_eqasim_contrib.sh                      # the analysis stage only
#   bash scripts/install_eqasim_contrib.sh edgt_44_urban_type   # and a patch, by name
#   EQASIM=/other/checkout bash scripts/install_eqasim_contrib.sh java_version_check
#
# The stage is a new file and changes nothing else. A patch changes existing stages:
# synpp notices and runs those stages and everything after them again. Read
# eqasim_contrib/README.md before applying java_version_check to a checkout whose
# simulation cache you want to keep.
set -euo pipefail

PILOT="$(cd "$(dirname "$0")/.." && pwd)"
CODE="${EQASIM:-$HOME/eqasim-france}"
CONTRIB="$PILOT/eqasim_contrib"

if [ ! -d "$CODE/analysis/synthesis" ]; then
  echo "No eqasim-france checkout at $CODE (set EQASIM=/path/to/it)"; exit 1
fi

cp "$CONTRIB/analysis/synthesis/chains_by_territory.py" "$CODE/analysis/synthesis/"
echo "stage copied: analysis.synthesis.chains_by_territory"

for name in "$@"; do
  patch="$CONTRIB/patches/$name.patch"
  if [ ! -f "$patch" ]; then
    echo "No such patch: $name (available: java_version_check, edgt_44_urban_type)"; exit 1
  fi
  if git -C "$CODE" apply --check "$patch" 2>/dev/null; then
    git -C "$CODE" apply "$patch"
    echo "patch applied: $name"
  elif git -C "$CODE" apply --reverse --check "$patch" 2>/dev/null; then
    echo "patch already applied: $name"
  else
    echo "patch does not apply to $CODE: $name (it was written for eqasim-france v1.5.0)"; exit 1
  fi
done
