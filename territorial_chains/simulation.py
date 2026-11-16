"""Travel indicators from simulated trips, by home territory.

The input is the trip table eqasim writes at the end of a MATSim run
(``eqasim_trips.csv``): one row per trip, with ``person_id``, ``mode``,
``routed_distance`` in metres and ``travel_time`` in seconds.
"""

import numpy as np
import pandas as pd

MODES = ["car", "car_passenger", "pt", "bike", "walk"]


def read_table(path):
    """Read a MATSim/eqasim CSV whatever its delimiter (; or ,) and compression (.gz, .zst)."""
    path = str(path)
    compression = "zstd" if path.endswith(".zst") else "infer"
    try:
        table = pd.read_csv(path, sep=";", compression=compression)
        if table.shape[1] == 1:
            table = pd.read_csv(path, sep="\t" if "\t" in table.columns[0] else ",", compression=compression)
    except ImportError as error:        # pandas needs the zstandard package for .zst
        raise ImportError("Reading %s needs the 'zstandard' package (pip install zstandard)." % path) from error
    return table


def _with_all(frame, group):
    """Append a copy of every row under the group label 'all'."""
    return pd.concat([frame, frame.assign(**{group: "all"})], ignore_index=True)


def _ordered(modes):
    return [m for m in MODES if m in modes] + sorted(m for m in modes if m not in MODES)


def attach_home(trips, residents, group="urban_type"):
    """Keep the trips of the given residents and attach their home territory."""
    return trips.merge(residents[["person_id", group]], on="person_id", how="inner")


def mode_shares(trips, group="urban_type"):
    """Share of trips and of distance by mode, for each home territory and overall."""
    df = _with_all(trips.assign(km=trips["routed_distance"] / 1000.0), group)
    table = df.groupby([group, "mode"], observed=True).agg(trips=("km", "size"), km=("km", "sum")).reset_index()
    totals = table.groupby(group, observed=True)[["trips", "km"]].transform("sum")
    table["trip_share"] = table["trips"] / totals["trips"]
    table["km_share"] = table["km"] / totals["km"]
    order = {m: i for i, m in enumerate(_ordered(set(table["mode"])))}
    return table.sort_values([group, "mode"], key=lambda s: s.map(order) if s.name == "mode" else s,
                             kind="stable").reset_index(drop=True)


def travel_per_resident(trips, residents, group="urban_type"):
    """Trips, distance and time per resident (travelling or not), by home territory and overall."""
    df = _with_all(trips.assign(km=trips["routed_distance"] / 1000.0,
                                car_km=np.where(trips["mode"] == "car", trips["routed_distance"] / 1000.0, 0.0),
                                minutes=trips["travel_time"] / 60.0), group)
    people = _with_all(residents[["person_id", group]], group).groupby(group, observed=True)["person_id"].nunique()

    sums = df.groupby(group, observed=True).agg(
        trips=("km", "size"), km=("km", "sum"), car_km=("car_km", "sum"),
        minutes=("minutes", "sum"), travelling=("person_id", "nunique"))
    sums = sums.reindex(people.index).fillna(0.0)

    out = pd.DataFrame({
        "residents": people,
        "travelling_share": sums["travelling"] / people,
        "trips_per_resident": sums["trips"] / people,
        "km_per_resident": sums["km"] / people,
        "car_km_per_resident": sums["car_km"] / people,
        "minutes_per_resident": sums["minutes"] / people,
        "km_per_trip": sums["km"] / sums["trips"].where(sums["trips"] > 0),
    })
    return out.reset_index()


def convergence(modestats):
    """MATSim's modestats table in long form: iteration, mode, share."""
    table = modestats.rename(columns={modestats.columns[0]: "iteration"})
    long = table.melt(id_vars="iteration", var_name="mode", value_name="share")
    order = {m: i for i, m in enumerate(_ordered(set(long["mode"])))}
    return long.sort_values(["iteration", "mode"], key=lambda s: s.map(order) if s.name == "mode" else s,
                            kind="stable").reset_index(drop=True)
