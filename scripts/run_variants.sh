#!/usr/bin/env bash
# Run one or more eqasim variants and keep their logs next to the outputs.
#
#   bash scripts/run_variants.sh                 # smoke test (0.1% sample)
#   bash scripts/run_variants.sh A_entd_local B_entd_national C_entd_urban D_emp_national E_emp_urban
#
# The log of each run is written to output/<variant>/run.log; it contains the
# matching levels eqasim reports, which the analysis reads.
set -uo pipefail

PILOT="$(cd "$(dirname "$0")/.." && pwd)"
CODE="$HOME/eqasim-france"
[ $# -eq 0 ] && set -- smoke

for variant in "$@"; do
  config="$PILOT/configs/$variant.yml"
  if [ ! -f "$config" ]; then
    echo "No such config: $config (run configs/make_configs.py first)"; exit 1
  fi
  mkdir -p "$PILOT/output/$variant"
  echo "=== $variant  $(date '+%H:%M:%S')"
  ( cd "$CODE" && uv run -m synpp "$config" ) 2>&1 | tee "$PILOT/output/$variant/run.log"
  status=${PIPESTATUS[0]}
  echo "=== $variant finished with status $status  $(date '+%H:%M:%S')" | tee -a "$PILOT/output/$variant/run.log"
  if [ "$status" -ne 0 ]; then exit "$status"; fi
done
exit 0
