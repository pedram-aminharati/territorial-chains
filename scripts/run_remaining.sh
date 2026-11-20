#!/usr/bin/env bash
# The runs that were still open on 20 November 2026, in one go. Run from the project folder:
#
#   bash scripts/run_remaining.sh
#
# 1. copies the two stages of eqasim_contrib/ into ~/eqasim-france and applies the patch
#    that gives the regional survey an urban type
# 2. writes the configs again (the existing ones come out unchanged)
# 3. generates four populations:
#      S_entd_structured     the new matching stage, national survey
#      T_edgt44_structured   the new matching stage, regional survey
#      F_edgt44              eqasim's matching, regional survey
#      G_edgt44_urban        eqasim's matching, regional survey, urban type first
# 4. runs the territory analysis stage inside eqasim on variant C
#
# A step that fails does not stop the others. The summary printed at the end says which
# ones finished and is kept in output/remaining_runs.log; each log is in
# output/<variant>/run.log (territory.log for step 4).
# To run only some variants:  VARIANTS="S_entd_structured" bash scripts/run_remaining.sh
set -uo pipefail

PILOT="$(cd "$(dirname "$0")/.." && pwd)"
CODE="${EQASIM:-$HOME/eqasim-france}"
SUMMARY="$PILOT/output/remaining_runs.log"
VARIANTS="${VARIANTS:-S_entd_structured T_edgt44_structured F_edgt44 G_edgt44_urban}"
cd "$PILOT" || exit 1
mkdir -p "$PILOT/output"
: > "$SUMMARY"

note() { echo "$1" | tee -a "$SUMMARY"; }

note "=== started $(date '+%Y-%m-%d %H:%M:%S')"

if ! bash "$PILOT/scripts/install_eqasim_contrib.sh" edgt_44_urban_type 2>&1 | tee -a "$SUMMARY"; then
  note "FAILED: the stages or the patch could not be installed in $CODE; nothing was run"; exit 1
fi

if ! ( cd "$CODE" && uv run python "$PILOT/configs/make_configs.py" "$PILOT" 0.1 ) > "$PILOT/output/make_configs.log" 2>&1; then
  note "FAILED: configs/make_configs.py (see output/make_configs.log); nothing was run"; exit 1
fi
note "configs written"

for variant in $VARIANTS; do
  start=$(date +%s)
  if bash "$PILOT/scripts/run_variants.sh" "$variant"; then
    result="ok"
  else
    result="FAILED"
  fi
  tables=$(find "$PILOT/output/$variant" -maxdepth 1 -name '*_persons.parquet' 2>/dev/null | wc -l)
  note "$result  $variant  $(( ($(date +%s) - start) / 60 )) min, population tables: $tables"
  if [ "$result" = "FAILED" ]; then
    tail -n 25 "$PILOT/output/$variant/run.log" 2>/dev/null | sed 's/^/      /' | tee -a "$SUMMARY"
  fi
done

start=$(date +%s)
if bash "$PILOT/scripts/run_territory_stage.sh" C_entd_urban; then
  note "ok  territory analysis stage on C_entd_urban  $(( ($(date +%s) - start) / 60 )) min"
else
  note "FAILED  territory analysis stage on C_entd_urban"
  tail -n 25 "$PILOT/output/C_entd_urban/territory.log" 2>/dev/null | sed 's/^/      /' | tee -a "$SUMMARY"
fi

note "=== finished $(date '+%Y-%m-%d %H:%M:%S')"

echo
echo "Summary (also in output/remaining_runs.log):"
cat "$SUMMARY"
