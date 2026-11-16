"""Tables behind the map and the matching explorer of the project page.

Usage
-----
    python scripts/export_page_data.py <output_dir> <urban_type_zip> <iris_contours> [results_dir]

``output_dir``     holds the simulated variants ``A_entd_local_sim`` and ``C_entd_urban_sim``
                   (population tables and ``simulation/eqasim_trips.csv*``).
``iris_contours``  IGN's CONTOURS-IRIS archive (.7z, needs the ``py7zr`` package) or the
                   ``contours-iris.gpkg`` extracted from it.

Outputs, in ``results/``
------------------------
map/units.csv        one row per variant and geographic unit (commune or intercommunalité):
                     matched residents in the sample, share staying home, share whose donor
                     lives in the same urban type, simulated trips and car km per resident
map/shapes.json      simplified outlines as SVG paths, a few town labels
explorer_cells.csv   the ENTD respondents counted by matching cell, with weights

The intercommunalité of each commune comes from ``reference/epci_loire_atlantique.csv``.
``results/chains_entd.parquet`` must exist (written by ``survey_contrasts.py``).
"""

import glob
import json
import os
import re
import sys
import tempfile

import numpy as np
import pandas as pd

from territorial_chains import read_table

from evaluate_population import load_urban_types, load_population, donors

VARIANTS = {"A": "A_entd_local_sim", "C": "C_entd_urban_sim"}
ATTRIBUTES = ["sex", "any_cars", "age_class", "socioprofessional_class"]
TOWNS = {"44109": "Nantes", "44184": "Saint-Nazaire", "44036": "Châteaubriant",
         "44003": "Ancenis", "44131": "Pornic", "44043": "Clisson"}
MAP_WIDTH = 560.0
SIMPLIFY_METRES = 250.0
HERE = os.path.dirname(os.path.abspath(__file__))


# --------------------------------------------------------------------------- geography

def short_name(name):
    """A display name for an intercommunalité: its nickname if it has one, else without the legal form."""
    inside = re.search(r"\(([^)]+)\)", name)
    if inside:
        return inside.group(1)
    name = re.sub(r"^(CC|CA|CU)\s+", "", name)
    return re.sub(r"^(du|de la|de|des|d')\s*", "", name)


def load_epci():
    table = pd.read_csv(os.path.join(HERE, "..", "reference", "epci_loire_atlantique.csv"), dtype=str)
    table["epci_short"] = table["epci_name"].map(short_name)
    return table


def load_communes(path):
    """Commune outlines of Loire-Atlantique, dissolved from IGN's IRIS contours (Lambert-93)."""
    import geopandas as gpd

    if path.endswith(".7z"):
        import py7zr
        folder = tempfile.mkdtemp()
        with py7zr.SevenZipFile(path) as archive:
            target = [n for n in archive.getnames() if n.endswith("contours-iris.gpkg")]
            archive.extract(folder, targets=target)
        path = os.path.join(folder, target[0])
    iris = gpd.read_file(path, where="code_insee LIKE '44%'")
    communes = iris.dissolve(by="code_insee", as_index=False)[["code_insee", "nom_commune", "geometry"]]
    return communes.rename(columns={"code_insee": "commune_id", "nom_commune": "name"})


def svg_paths(frame, bounds, scale):
    """SVG path data for each geometry, y pointing down, one decimal."""
    def ring(coords):
        points = ["%.1f %.1f" % ((x - bounds[0]) * scale, (bounds[3] - y) * scale) for x, y in coords]
        return "M" + "L".join(points) + "Z"

    def path(geometry):
        polygons = geometry.geoms if geometry.geom_type == "MultiPolygon" else [geometry]
        return "".join(ring(p.exterior.coords) + "".join(ring(i.coords) for i in p.interiors) for p in polygons)

    return frame.geometry.map(path)


def shapes(communes, epci):
    import shapely

    frame = communes.merge(epci, on="commune_id", validate="one_to_one")
    # Simplify all outlines together so that neighbours keep sharing their border.
    frame["geometry"] = shapely.coverage_simplify(frame.geometry.values, SIMPLIFY_METRES)
    bounds = frame.total_bounds
    scale = MAP_WIDTH / (bounds[2] - bounds[0])

    groups = frame.dissolve(by="epci_id", as_index=False)[["epci_id", "epci_short", "geometry"]]
    towns = frame[frame["commune_id"].isin(TOWNS)]
    points = towns.geometry.representative_point()
    return {
        "width": MAP_WIDTH, "height": round((bounds[3] - bounds[1]) * scale, 1),
        "communes": [{"id": r.commune_id, "name": r.name, "epci": r.epci_id, "d": d}
                     for r, d in zip(frame.itertuples(), svg_paths(frame, bounds, scale))],
        "epci": [{"id": r.epci_id, "name": r.epci_short, "d": d}
                 for r, d in zip(groups.itertuples(), svg_paths(groups, bounds, scale))],
        "towns": [{"name": TOWNS[r.commune_id], "x": round((p.x - bounds[0]) * scale, 1),
                   "y": round((bounds[3] - p.y) * scale, 1)} for r, p in zip(towns.itertuples(), points)],
    }


# --------------------------------------------------------------------------- aggregates

def persons_of(run_dir, urban_types, donor_table):
    """Matched residents of one simulated variant with what the map shows about each."""
    df = load_population(run_dir, urban_types)
    df = df.merge(donor_table[["hts_person_id", "donor_urban_type"]], on="hts_person_id", how="left")
    df["donor_same"] = df["donor_urban_type"] == df["urban_type"]

    df["trips"], df["car_km"] = 0.0, 0.0
    trip_files = sorted(glob.glob(os.path.join(run_dir, "simulation", "eqasim_trips.csv*")))
    if trip_files:
        trips = read_table(trip_files[0])
        trips["person_id"] = pd.to_numeric(trips["person_id"], errors="coerce")
        trips = trips[trips["person_id"].notna()]
        trips["car_km"] = np.where(trips["mode"] == "car", trips["routed_distance"] / 1000.0, 0.0)
        per_person = trips.groupby("person_id").agg(trips=("car_km", "size"), car_km=("car_km", "sum"))
        df["trips"] = df["person_id"].map(per_person["trips"]).fillna(0.0)
        df["car_km"] = df["person_id"].map(per_person["car_km"]).fillna(0.0)
    else:
        df[["trips", "car_km"]] = np.nan
    return df


def aggregate(df, key):
    return df.groupby(key).agg(
        residents=("person_id", "size"), immobile_share=("immobile", "mean"),
        donor_same_share=("donor_same", "mean"),
        trips_per_resident=("trips", "mean"), car_km_per_resident=("car_km", "mean")).reset_index()


def units(output_dir, urban_types, donor_table, epci, names):
    rows = []
    for letter, folder in VARIANTS.items():
        df = persons_of(os.path.join(output_dir, folder), urban_types, donor_table)
        df = df.merge(epci, on="commune_id", how="left", validate="many_to_one")
        if df["epci_id"].isna().any():
            raise RuntimeError("Residents in communes missing from reference/epci_loire_atlantique.csv")

        communes = aggregate(df, "commune_id").rename(columns={"commune_id": "unit_id"})
        communes = communes.merge(names.rename(columns={"commune_id": "unit_id"}), on="unit_id")
        communes = communes.merge(epci.rename(columns={"commune_id": "unit_id"})[["unit_id", "epci_id"]], on="unit_id")
        communes = communes.merge(urban_types.rename(columns={"commune_id": "unit_id"}), on="unit_id", how="left")
        communes["urban_type"] = communes["urban_type"].fillna("none")

        groups = aggregate(df, "epci_id").rename(columns={"epci_id": "unit_id"})
        groups = groups.merge(epci.drop_duplicates("epci_id").rename(
            columns={"epci_id": "unit_id", "epci_short": "name"})[["unit_id", "name"]], on="unit_id")
        groups["epci_id"], groups["urban_type"] = groups["unit_id"], ""

        for level, table in (("commune", communes), ("epci", groups)):
            rows.append(table.assign(level=level, variant=letter))
    columns = ["variant", "level", "unit_id", "name", "epci_id", "urban_type", "residents", "immobile_share",
               "donor_same_share", "trips_per_resident", "car_km_per_resident"]
    return pd.concat(rows, ignore_index=True)[columns].sort_values(["variant", "level", "unit_id"])


def explorer_cells(results_dir):
    """ENTD respondents by matching cell: how many, their weight, and what their days look like."""
    chains = pd.read_parquet(os.path.join(results_dir, "chains_entd.parquet"))
    if "leaves_departement" not in chains:
        raise RuntimeError("results/chains_entd.parquet is from an older run: run scripts/survey_contrasts.py again")
    # "local" is variant A's donor pool: residents of the departement who do not leave it
    # during the day (eqasim's filter_hts drops the others). "departement" is the
    # matching attribute of the same name, which the national variants use last.
    chains["departement"] = chains["departement_id"].astype(str) == "44"
    chains["local"] = chains["departement"] & ~chains["leaves_departement"].astype(bool)
    chains["weighted_immobile"] = chains["weight"] * chains["immobile"]
    chains["weighted_trips"] = chains["weight"] * chains["n_trips"]
    cells = chains.groupby(ATTRIBUTES + ["departement", "local", "urban_type"], observed=True).agg(
        respondents=("weight", "size"), weight=("weight", "sum"),
        weighted_immobile=("weighted_immobile", "sum"), weighted_trips=("weighted_trips", "sum")).reset_index()
    return cells.round({"weight": 1, "weighted_immobile": 1, "weighted_trips": 1})


# --------------------------------------------------------------------------- main

def main(output_dir, urban_type_zip, iris_contours, results_dir="results"):
    results_dir = os.path.abspath(results_dir)
    os.makedirs(os.path.join(results_dir, "map"), exist_ok=True)

    epci = load_epci()
    communes = load_communes(iris_contours)
    urban_types = load_urban_types(urban_type_zip)

    table = units(os.path.abspath(output_dir), urban_types, donors(results_dir, "entd"), epci,
                  communes[["commune_id", "name"]])
    table.to_csv(os.path.join(results_dir, "map", "units.csv"), index=False, float_format="%.4f")

    with open(os.path.join(results_dir, "map", "shapes.json"), "w", encoding="utf-8") as f:
        json.dump(shapes(communes, epci), f, ensure_ascii=False, separators=(",", ":"))

    explorer_cells(results_dir).to_csv(os.path.join(results_dir, "explorer_cells.csv"), index=False)

    small = table[(table["level"] == "commune") & (table["variant"] == "A") & (table["residents"] < 100)]
    print("%d units written; %d of %d communes have fewer than 100 sampled residents" % (
        len(table), len(small), table[(table["level"] == "commune") & (table["variant"] == "A")].shape[0]))


if __name__ == "__main__":
    main(*sys.argv[1:5])
