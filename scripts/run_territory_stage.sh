#!/usr/bin/env bash
# Run the territory analysis stage inside eqasim, on the population of one or more variants.
#
#   bash scripts/install_eqasim_contrib.sh        # once: copies the stage into ~/eqasim-france
#   bash scripts/run_territory_stage.sh C_entd_urban
#
# The stage reads the population from the pipeline's cache. Stages that are no longer
# cached are computed again first, which can take as long as generating the variant.
# The tables are written to output/<variant>/ as *_chains_by_territory_*.csv and the
# log to output/<variant>/territory.log.
set -uo pipefail

PILOT="$(cd "$(dirname "$0")/.." && pwd)"
CODE="${EQASIM:-$HOME/eqasim-france}"
[ $# -eq 0 ] && { echo "Usage: bash scripts/run_territory_stage.sh <variant> [<variant> ...]"; exit 1; }

if [ ! -f "$CODE/analysis/synthesis/chains_by_territory.py" ]; then
  echo "The stage is not installed in $CODE: run scripts/install_eqasim_contrib.sh first"; exit 1
fi

for variant in "$@"; do
  config="$PILOT/configs/${variant}_territory.yml"
  if [ ! -f "$config" ]; then
    echo "No such config: $config (run configs/make_configs.py first)"; exit 1
  fi
  mkdir -p "$PILOT/output/$variant"
  echo "=== $variant, territory analysis  $(date '+%H:%M:%S')"
  ( cd "$CODE" && uv run -m synpp "$config" ) 2>&1 | tee "$PILOT/output/$variant/territory.log"
  status=${PIPESTATUS[0]}
  echo "=== $variant finished with status $status  $(date '+%H:%M:%S')" | tee -a "$PILOT/output/$variant/territory.log"
  if [ "$status" -ne 0 ]; then exit "$status"; fi
  ls "$PILOT/output/$variant"/*chains_by_territory_*.csv 2>/dev/null
done
exit 0
