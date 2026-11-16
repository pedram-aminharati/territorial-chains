#!/usr/bin/env bash
# Build the MATSim scenario of a variant with eqasim, then simulate it.
#
#   ITERATIONS=2 bash scripts/run_simulation.sh smoke_sim          # toolchain test, 0.1% sample
#   bash scripts/run_simulation.sh A_entd_local_sim C_entd_urban_sim
#
# Step 1 runs the eqasim pipeline (stages synthesis.output and matsim.output):
# it builds pt2matsim and eqasim-java with Maven, cuts the road network and
# the timetables to the département, writes the scenario into
# output/<variant>/ and tests it for two iterations.
#
# Step 2 runs the simulation itself with the jar eqasim wrote, the way the
# eqasim documentation describes, with a cap on the number of iterations.
# eqasim stops earlier on its own once the mode shares are stable.
# The simulation writes to ~/eqasim-sim/<variant> (Linux side, fast); the few
# tables the analysis needs are then copied to output/<variant>/simulation/.
#
# Settings (environment variables):
#   ITERATIONS   cap on iterations             default 60
#   JAVA_MEMORY  heap for the simulation       default 20G
#   THREADS      threads                       default all cores, at most 12
set -uo pipefail

PILOT="$(cd "$(dirname "$0")/.." && pwd)"
ITERATIONS="${ITERATIONS:-60}"
JAVA_MEMORY="${JAVA_MEMORY:-20G}"
CORES="$(nproc)"
THREADS="${THREADS:-$(( CORES > 12 ? 12 : CORES ))}"
PREFIX="nantes_"

[ $# -eq 0 ] && { echo "Usage: bash scripts/run_simulation.sh <variant>_sim [...]"; exit 1; }

for variant in "$@"; do
  OUT="$PILOT/output/$variant"
  SIM="$HOME/eqasim-sim/$variant"

  # --- 1. population + scenario (eqasim pipeline)
  bash "$PILOT/scripts/run_variants.sh" "$variant" || exit $?
  for needed in "${PREFIX}run.jar" "${PREFIX}config.xml" "${PREFIX}population.xml.gz" "${PREFIX}network.xml.gz"; do
    if [ ! -f "$OUT/$needed" ]; then
      echo "Scenario file missing: $OUT/$needed"; exit 1
    fi
  done

  # --- 2. simulation
  mkdir -p "$HOME/eqasim-sim" "$OUT/simulation"
  echo "=== $variant simulation, at most $ITERATIONS iterations, $THREADS threads  $(date '+%H:%M:%S')"
  ( cd "$OUT" && exec java "-Xmx$JAVA_MEMORY" -cp "${PREFIX}run.jar" org.eqasim.ile_de_france.RunSimulation \
      --config-path "${PREFIX}config.xml" \
      --config:controler.lastIteration "$ITERATIONS" \
      --config:controler.outputDirectory "$SIM" \
      --config:global.numberOfThreads "$THREADS" \
      --config:qsim.numberOfThreads "$THREADS" ) > "$OUT/simulation/simulation.log" 2>&1 &
  pid=$!
  trap 'kill "$pid" 2>/dev/null; exit 130' INT TERM

  # MATSim's log is long; show one line per finished iteration instead.
  seen=""
  while kill -0 "$pid" 2>/dev/null; do
    sleep 20
    last="$(grep -ao 'ITERATION [0-9]* ENDS' "$OUT/simulation/simulation.log" 2>/dev/null | tail -1)"
    if [ -n "$last" ] && [ "$last" != "$seen" ]; then
      echo "  $(date '+%H:%M:%S')  $last"; seen="$last"
    fi
  done
  wait "$pid"; status=$?
  trap - INT TERM

  if [ "$status" -ne 0 ]; then
    echo "=== $variant simulation FAILED with status $status. Last lines of the log:"
    tail -30 "$OUT/simulation/simulation.log"
    exit "$status"
  fi

  # --- 3. keep what the analysis reads
  copied=0
  for pattern in "eqasim_trips.csv*" "eqasim_pt.csv*" "modestats.csv*" "scorestats.csv*" "stopwatch.csv*" "traveldistancestats.csv*"; do
    for file in "$SIM"/$pattern; do
      [ -f "$file" ] && cp -f "$file" "$OUT/simulation/" && copied=$((copied + 1))
    done
  done
  if ! ls "$OUT/simulation"/eqasim_trips.csv* >/dev/null 2>&1; then
    echo "=== $variant: the simulation ended but wrote no eqasim_trips table in $SIM"; ls "$SIM" | head -40; exit 1
  fi
  echo "=== $variant simulation finished with status 0, $copied tables copied to output/$variant/simulation  $(date '+%H:%M:%S')"
done
