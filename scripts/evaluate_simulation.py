"""Work package 4: what the matching design changes once the population is simulated.

Usage
-----
    python scripts/evaluate_simulation.py <run_dir> <urban_type_zip> [results_dir]

``run_dir`` is the output folder of a simulated variant, as left by
``scripts/run_simulation.sh``: the population tables (``*_persons.parquet``,
``*_households.parquet``) and ``simulation/eqasim_trips.csv*`` with, if
present, ``simulation/modestats.csv``.

Residents are the matched synthetic persons (those with a survey donor), the
same population ``evaluate_population.py`` scores, grouped by the urban-unit
status of their home commune.

Outputs, in ``results/<run name>/``
-----------------------------------
sim_modes.csv        share of trips and of distance by mode, per home territory
sim_travel.csv       trips, km, car km and minutes per resident, per home territory
sim_convergence.csv  mode shares by iteration (the simulation settling down)

A caution that belongs with every number here: eqasim's mode-choice model is
calibrated for Île-de-France. The levels are not a forecast for
Loire-Atlantique; the differences between two variants simulated with the same
network, timetables and parameters are what can be read.
"""

import glob
import os
import sys

import pandas as pd

from territorial_chains import read_table, attach_home, mode_shares, travel_per_resident, convergence

from evaluate_population import load_urban_types, URBAN_ORDER, _one


def load_residents(run_dir, urban_types):
    persons = pd.read_parquet(_one(run_dir, "persons.parquet"))
    households = pd.read_parquet(_one(run_dir, "households.parquet"))
    df = persons[["person_id", "household_id", "hts_person_id"]].merge(
        households[["household_id", "commune_id"]], on="household_id")
    df = df[df["commune_id"].notna()].copy()       # see evaluate_population.load_population
    df["commune_id"] = df["commune_id"].astype(str).str.zfill(5)
    df = df.merge(urban_types, on="commune_id", how="left")
    df["urban_type"] = df["urban_type"].fillna("none")
    matched = df[df["hts_person_id"].notna() & (df["hts_person_id"] >= 0)]
    return matched[["person_id", "urban_type"]].reset_index(drop=True), len(persons)


def load_trips(run_dir):
    matches = sorted(glob.glob(os.path.join(run_dir, "simulation", "eqasim_trips.csv*")))
    if not matches:
        raise FileNotFoundError("No simulation/eqasim_trips.csv* in %s (run scripts/run_simulation.sh first)" % run_dir)
    trips = read_table(matches[0])
    missing = {"person_id", "mode", "routed_distance", "travel_time"} - set(trips.columns)
    if missing:
        raise RuntimeError("Unexpected trip table, missing columns: %s" % sorted(missing))
    # Agents other than residents (freight, for instance) may carry non-numeric identifiers.
    trips["person_id"] = pd.to_numeric(trips["person_id"], errors="coerce")
    return trips[trips["person_id"].notna()].astype({"person_id": "int64"})


def sorted_by_territory(table):
    order = {u: i for i, u in enumerate(URBAN_ORDER + ["all"])}
    return table.sort_values("urban_type", key=lambda s: s.map(order), kind="stable").reset_index(drop=True)


def main(run_dir, urban_type_zip, results_dir="results"):
    run_dir, results_dir = os.path.abspath(run_dir), os.path.abspath(results_dir)
    out = os.path.join(results_dir, os.path.basename(run_dir.rstrip("/")))
    os.makedirs(out, exist_ok=True)

    residents, n_persons = load_residents(run_dir, load_urban_types(urban_type_zip))
    trips = load_trips(run_dir)
    kept = attach_home(trips, residents)
    if len(kept) < 0.95 * len(trips):
        raise RuntimeError("Only %.1f%% of simulated trips belong to matched residents of this run; "
                           "the trip table and the population do not come from the same run."
                           % (100.0 * len(kept) / max(len(trips), 1)))

    tables = {
        "sim_modes": sorted_by_territory(mode_shares(kept)),
        "sim_travel": sorted_by_territory(travel_per_resident(kept, residents)),
    }
    stats = glob.glob(os.path.join(run_dir, "simulation", "modestats.csv*"))
    if stats:
        tables["sim_convergence"] = convergence(read_table(stats[0]))

    for name, table in tables.items():
        table.to_csv(os.path.join(out, "%s.csv" % name), index=False)

    print("%d persons, %d matched residents, %d trips (%d kept)" % (n_persons, len(residents), len(trips), len(kept)))
    if "sim_convergence" in tables:
        print("iterations run: %d" % tables["sim_convergence"]["iteration"].max())
    print(tables["sim_travel"].round(2).to_string(index=False))
    print("written to", out)
    return tables


if __name__ == "__main__":
    main(*sys.argv[1:4])
