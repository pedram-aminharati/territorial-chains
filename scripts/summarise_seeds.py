"""Repeats over random seeds: mean and range of every result, and paired A-against-C differences.

Usage
-----
    python scripts/summarise_seeds.py [results_dir]

Reads the tables that ``evaluate_population.py`` and ``evaluate_simulation.py`` wrote
for the seed repeats of variants A and C (see docs/SEEDS.md) and writes, in
``results/seeds/``:

summary.csv       variant, quantity, urban type: number of seeds, mean, minimum, maximum, sd
differences.csv   C minus A computed seed by seed (both variants of a seed share the same
                  census sample), with the range of that difference and whether its sign
                  is the same in every seed

A repeat redraws the 10% census sample, the matching and the locations, and for the
simulated quantities MATSim's own random draws.
"""

import os
import sys

import pandas as pd

URBAN = ["central_city", "suburb", "isolated_city", "none"]
VARIANTS = {"A": "A_entd_local", "C": "C_entd_urban"}
SEEDS = [1, 2, 3, 4, 5]


def folders(results, name, seed):
    """Result folders of one seed: (population tables, simulation tables or None)."""
    def first(*candidates):
        for candidate in candidates:
            if os.path.isdir(os.path.join(results, candidate)):
                return os.path.join(results, candidate)
        return None

    if seed == 1:
        return first(name), first(name + "_sim")
    simulated = first("%s_seed%d_sim" % (name, seed))
    return simulated or first("%s_seed%d" % (name, seed)), simulated


def records(results):
    rows = []

    def add(variant, seed, source, quantity, urban, value):
        rows.append({"variant": variant, "seed": seed, "source": source, "quantity": quantity,
                     "urban_type": urban, "value": float(value)})

    for variant, name in VARIANTS.items():
        for seed in SEEDS:
            population, simulation = folders(results, name, seed)
            if population and os.path.exists(os.path.join(population, "indicators.csv")):
                read = lambda table: pd.read_csv(os.path.join(population, table + ".csv"))
                for r in read("indicators").itertuples():
                    add(variant, seed, "population", r.indicator, r.urban_type, r.generated)
                for r in read("fidelity").itertuples():
                    add(variant, seed, "population", "hellinger", r.urban_type, r.distance)
                for r in read("donor_territory").itertuples():
                    add(variant, seed, "population", "donor_same_urban_type", r.urban_type, r.donor_same_urban_type)
                    add(variant, seed, "population", "donor_from_loire_atlantique", r.urban_type, r.donor_from_loire_atlantique)
                local = population + "__vs_edgt_44"       # the same population scored against the regional survey
                if os.path.exists(os.path.join(local, "fidelity.csv")):
                    for r in pd.read_csv(os.path.join(local, "fidelity.csv")).itertuples():
                        add(variant, seed, "population", "hellinger_edgt", r.urban_type, r.distance)
                levels = read("matching_levels")
                if len(levels):
                    add(variant, seed, "population", "matched_on_all_attributes", "all",
                        levels.sort_values("attributes_matched")["share"].iloc[-1])
            if simulation and os.path.exists(os.path.join(simulation, "sim_travel.csv")):
                travel = pd.read_csv(os.path.join(simulation, "sim_travel.csv"))
                for r in travel.itertuples():
                    for column in ("travelling_share", "trips_per_resident", "km_per_resident",
                                   "car_km_per_resident", "minutes_per_resident", "km_per_trip"):
                        add(variant, seed, "simulation", column, r.urban_type, getattr(r, column))
                modes = pd.read_csv(os.path.join(simulation, "sim_modes.csv"))
                for r in modes[modes["mode"].isin(["car", "pt", "walk"])].itertuples():
                    add(variant, seed, "simulation", "trip_share_" + r.mode, r.urban_type, r.trip_share)
    return pd.DataFrame.from_records(rows)


def summarise(table):
    keys = ["variant", "source", "quantity", "urban_type"]
    out = table.groupby(keys)["value"].agg(seeds="size", mean="mean", minimum="min", maximum="max", sd="std")
    return out.reset_index()


def differences(table):
    keys = ["source", "quantity", "urban_type", "seed"]
    wide = table.pivot_table(index=keys, columns="variant", values="value").dropna().reset_index()
    wide["difference"] = wide["C"] - wide["A"]
    wide["relative"] = wide["difference"] / wide["A"].where(wide["A"] != 0)
    out = wide.groupby(keys[:-1]).agg(
        seeds=("difference", "size"), mean_A=("A", "mean"), mean_C=("C", "mean"),
        difference=("difference", "mean"), difference_min=("difference", "min"),
        difference_max=("difference", "max"), relative=("relative", "mean"),
        relative_min=("relative", "min"), relative_max=("relative", "max")).reset_index()
    out["same_sign_in_every_seed"] = (out["difference_min"] > 0) | (out["difference_max"] < 0)
    return out


def main(results="results"):
    results = os.path.abspath(results)
    out = os.path.join(results, "seeds")
    os.makedirs(out, exist_ok=True)

    table = records(results)
    table.to_csv(os.path.join(out, "by_seed.csv"), index=False, float_format="%.6f")
    summarise(table).to_csv(os.path.join(out, "summary.csv"), index=False, float_format="%.6f")
    diff = differences(table)
    diff.to_csv(os.path.join(out, "differences.csv"), index=False, float_format="%.6f")

    counts = table.groupby(["variant", "source"])["seed"].nunique()
    print("seeds found:", counts.to_dict())
    print("written to", out)
    return table, diff


if __name__ == "__main__":
    main(*sys.argv[1:2])
