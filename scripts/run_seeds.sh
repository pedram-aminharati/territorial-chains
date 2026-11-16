#!/usr/bin/env bash
# Repeat variants A and C over random seeds, to put a range on every result.
#
#   bash scripts/run_seeds.sh                    # seeds 2 to 5; seeds 2 and 3 are also simulated
#   SIM_SEEDS="" bash scripts/run_seeds.sh       # populations only (much shorter)
#   SEEDS="2 3" SIM_SEEDS="2" bash scripts/run_seeds.sh
#
# Seed 1 is the existing run (random_seed 1234). A repeat redraws the 10% census
# sample, the matching and the locations; a simulated repeat also runs MATSim
# with that seed. A failed run does not stop the others; the summary at the end
# lists what finished. Everything printed is also kept in output/seeds.log.
#
# Rough durations on the machine used so far: 15 to 20 minutes per population,
# about 75 minutes more per simulation. The default is an overnight job.
set -uo pipefail

PILOT="$(cd "$(dirname "$0")/.." && pwd)"
SEEDS="${SEEDS-2 3 4 5}"
SIM_SEEDS="${SIM_SEEDS-2 3}"
VARIANTS="A_entd_local C_entd_urban"
LOG="$PILOT/output/seeds.log"
mkdir -p "$PILOT/output"

{
  echo "=== seed repeats started $(date '+%Y-%m-%d %H:%M:%S')   seeds: $SEEDS   simulated: ${SIM_SEEDS:-none}"
  echo "free space, Linux side: $(df -h --output=avail "$HOME" | tail -1 | tr -d ' ')   project drive: $(df -h --output=avail "$PILOT" | tail -1 | tr -d ' ')"

  missing=0
  for seed in $SEEDS; do for variant in $VARIANTS; do
    [ -f "$PILOT/configs/${variant}_seed${seed}.yml" ] || missing=1
  done; done
  if [ "$missing" -eq 1 ]; then
    echo "Seed configs are missing: run configs/make_configs.py first (see docs/SEEDS.md)."; exit 1
  fi

  summary=()
  for seed in $SEEDS; do
    for variant in $VARIANTS; do
      started=$(date +%s)
      if [[ " $SIM_SEEDS " == *" $seed "* ]]; then
        run="${variant}_seed${seed}_sim"
        bash "$PILOT/scripts/run_simulation.sh" "$run"; status=$?
      else
        run="${variant}_seed${seed}"
        bash "$PILOT/scripts/run_variants.sh" "$run"; status=$?
      fi
      minutes=$(( ($(date +%s) - started) / 60 ))
      if [ "$status" -eq 0 ]; then result="ok"; else result="FAILED (status $status)"; fi
      summary+=("$(printf '%-34s %-22s %4d min' "$run" "$result" "$minutes")")
      echo "### $run: $result after $minutes min"
    done
  done

  echo
  echo "=== seed repeats finished $(date '+%Y-%m-%d %H:%M:%S')"
  printf '  %s\n' "${summary[@]}"
} 2>&1 | tee "$LOG"
