"""Work package 3: score an eqasim population against its source survey, by territory.

Usage
-----
    python scripts/evaluate_population.py <run_dir> <entd|emp|edgt_44> <urban_type_zip> [results_dir] [reference]

``reference`` scores the population against another survey than the one it was matched
from, for instance ``edgt_44`` (the regional survey); results then go to
``results/<run name>__vs_<reference>/``.

``run_dir`` is an eqasim output folder (``*_persons.parquet`` etc., plus
``run.log`` and, for distances, ``*_activities.geoparquet``). ``results_dir``
must already hold the survey tables written by ``survey_contrasts.py``.

Territory of a synthetic person is the urban-unit status of the home commune,
the same INSEE typology the surveys carry.

Outputs, in ``results/<run name>/``
-----------------------------------
matching_levels.csv   how many persons were matched on how many attributes (from the log)
donor_territory.csv   where each territory's donors come from
indicators.csv        chain indicators by urban type, generated next to observed
fidelity.csv          distance between generated and observed chain distributions, by urban type
contrast.csv          between-territory contrast, generated against observed
gaps.csv              rural minus central-city gap for each indicator, generated against observed
top_chains.csv        the most frequent observed chains by urban type, generated next to observed
"""

import glob
import io
import os
import re
import sys
import zipfile

import numpy as np
import pandas as pd

from territorial_chains import (
    chains_from_activities, add_indicators, weighted_mean, weighted_share,
    stratified_fidelity, contrast_retention, hellinger,
)

URBAN_ORDER = ["central_city", "suburb", "isolated_city", "none"]
URBAN_CODES = {"B": "suburb", "C": "central_city", "I": "isolated_city", "H": "none"}
TOP_K = 25
ROUTED_TO_EUCLIDEAN = 1.3        # eqasim's own convention (data.hts.*.reweighted)

SCALARS = {
    "immobile_share":         ("immobile", "all"),
    "activities_per_mobile":  ("n_activities", "mobile"),
    "tours_per_mobile":       ("n_tours", "mobile"),
    "simple_commute_share":   ("simple_commute", "mobile"),
    "secondary_share":        ("has_secondary", "mobile"),
    "euclidean_km_per_mobile": ("euclidean_km", "mobile"),
}


# --------------------------------------------------------------------------- loading

def load_urban_types(zip_path):
    """Commune -> urban type, from INSEE's urban-unit file."""
    with zipfile.ZipFile(zip_path) as archive:
        content = archive.read(archive.namelist()[0])
    df = None
    for engine in ("calamine", "openpyxl"):      # whichever Excel reader is installed
        try:
            df = pd.read_excel(io.BytesIO(content), sheet_name="Composition_communale", skiprows=5, engine=engine)
            break
        except ImportError:
            continue
    if df is None:
        raise ImportError("Reading the urban-unit workbook needs python-calamine or openpyxl.")
    return df.assign(commune_id=df["CODGEO"].astype(str).str.zfill(5),
                     urban_type=df["STATUT_COM_UU"].map(URBAN_CODES))[["commune_id", "urban_type"]]


def _one(run_dir, suffix):
    matches = glob.glob(os.path.join(run_dir, "*_%s" % suffix))
    return matches[0] if matches else None


def load_population(run_dir, urban_types):
    """One row per matched synthetic person, with chain indicators and home territory."""
    persons = pd.read_parquet(_one(run_dir, "persons.parquet"))
    households = pd.read_parquet(_one(run_dir, "households.parquet"))
    activities = pd.read_parquet(_one(run_dir, "activities.parquet"))

    df = add_indicators(chains_from_activities(activities))
    df = df.merge(persons[["person_id", "household_id", "age", "sex", "hts_person_id"]], on="person_id")
    df = df.merge(households[["household_id", "commune_id"]], on="household_id")
    # A few households come out of the pipeline without a home commune (0.02 to 0.08% of
    # matched persons in the variants with national donors; cause not investigated). They
    # have no territory and are left out rather than counted as rural.
    homeless = df["commune_id"].isna()
    df = df[~homeless].copy()
    df["commune_id"] = df["commune_id"].astype(str).str.zfill(5)
    df = df.merge(urban_types, on="commune_id", how="left")
    df["urban_type"] = df["urban_type"].fillna("none")
    df["weight"] = 1.0
    df.attrs["without_home_commune"] = int(homeless.sum())

    # Persons below the matching age have no donor and no chain of their own.
    df = df[df["hts_person_id"].notna() & (df["hts_person_id"] >= 0)].copy()

    df["euclidean_km"] = np.nan
    geo = _one(run_dir, "activities.geoparquet")
    if geo is not None:
        import geopandas as gpd
        points = gpd.read_parquet(geo)[["person_id", "activity_index", "geometry"]]
        points = points.sort_values(["person_id", "activity_index"])
        x, y = points.geometry.x.to_numpy(), points.geometry.y.to_numpy()
        same = points["person_id"].to_numpy()[1:] == points["person_id"].to_numpy()[:-1]
        step = np.where(same, np.hypot(np.diff(x), np.diff(y)), 0.0)
        total = pd.Series(np.concatenate([[0.0], step]), index=points["person_id"].to_numpy()).groupby(level=0).sum()
        df["euclidean_km"] = df["person_id"].map(total).fillna(0.0) / 1000.0
    attrs = dict(df.attrs)
    df = df.reset_index(drop=True)
    df.attrs.update(attrs)
    return df


def load_reference(results_dir, survey):
    """Observed chains for the survey the population was matched from.

    For EMP the reference is day-weighted (see docs/RESULTS_SURVEYS.md): mobile
    diaries carry ``POND_JOUR`` and the stay-at-home mass is added per urban type.
    """
    if survey in ("entd", "edgt_44"):
        ref = pd.read_parquet(os.path.join(results_dir, "chains_%s.parquet" % survey))
    elif survey == "emp":
        ref = pd.read_parquet(os.path.join(results_dir, "chains_emp_day_weighted.parquet"))
        immobility = pd.read_csv(os.path.join(results_dir, "emp_day_weights.csv")).set_index("urban_type")["immobile_day_weight"]
        home = []
        for urban, group in ref.groupby("urban_type"):
            share = immobility[urban]
            home.append({"urban_type": urban, "chain": "h",
                         "weight": group["weight"].sum() * share / (1.0 - share), "distance_km": 0.0})
        ref = pd.concat([ref, add_indicators(pd.DataFrame(home))], ignore_index=True)
    else:
        raise ValueError("survey must be entd, emp or edgt_44")
    ref["euclidean_km"] = ref["distance_km"] / ROUTED_TO_EUCLIDEAN
    return ref


def donors(results_dir, survey):
    """Every diary respondent of the survey, as eqasim identifies them."""
    table = pd.read_parquet(os.path.join(results_dir, "chains_%s.parquet" % survey))
    return table[["person_id", "urban_type", "departement_id", "sex"]].rename(columns={
        "person_id": "hts_person_id", "urban_type": "donor_urban_type",
        "departement_id": "donor_departement", "sex": "donor_sex"})


# --------------------------------------------------------------------------- tables

def matching_levels(run_dir):
    path = os.path.join(run_dir, "run.log")
    if not os.path.exists(path):
        return pd.DataFrame()
    records = [
        {"attributes_matched": int(m.group(1)), "persons": int(m.group(2)), "share": float(m.group(3)) / 100.0}
        for m in re.finditer(r"^(\d+) matched levels: (\d+) ([\d.]+)%", open(path).read(), flags=re.M)
    ]
    return pd.DataFrame.from_records(records)


def donor_territory(population, donor_table):
    df = population.merge(donor_table, on="hts_person_id", how="left")
    found = df["donor_urban_type"].notna()
    if found.mean() < 0.99 or (df.loc[found, "sex"].astype(str) != df.loc[found, "donor_sex"].astype(str)).mean() > 0.01:
        raise RuntimeError("Donor identifiers do not line up with the survey table; "
                           "re-run survey_contrasts.py on the same survey files as the pipeline.")
    records = []
    for urban in URBAN_ORDER + ["all"]:
        g = df if urban == "all" else df[df["urban_type"] == urban]
        if len(g) == 0:
            continue
        row = {"urban_type": urban, "persons": len(g),
               "donor_same_urban_type": float((g["donor_urban_type"] == g["urban_type"]).mean()),
               "donor_from_loire_atlantique": float((g["donor_departement"] == "44").mean()),
               "distinct_donors": int(g["hts_person_id"].nunique())}
        for donor in URBAN_ORDER:
            row["donor_%s" % donor] = float((g["donor_urban_type"] == donor).mean())
        records.append(row)
    return pd.DataFrame.from_records(records)


def _scalar(frame, column, scope):
    sample = frame if scope == "all" else frame[~frame["immobile"]]
    sample = sample[sample[column].notna()]
    return weighted_mean(sample[column], sample["weight"]) if len(sample) else np.nan


def indicators(population, reference):
    records = []
    for urban in URBAN_ORDER:
        gen, obs = population[population["urban_type"] == urban], reference[reference["urban_type"] == urban]
        for name, (column, scope) in SCALARS.items():
            records.append({"urban_type": urban, "indicator": name,
                            "observed": _scalar(obs, column, scope),
                            "generated": _scalar(gen, column, scope), "n_generated": len(gen)})
    return pd.DataFrame.from_records(records)


def gaps(table, a="none", b="central_city"):
    wide_obs = table.pivot(index="indicator", columns="urban_type", values="observed")
    wide_gen = table.pivot(index="indicator", columns="urban_type", values="generated")
    out = pd.DataFrame({
        "observed_gap": wide_obs[a] - wide_obs[b],
        "generated_gap": wide_gen[a] - wide_gen[b],
    })
    out["retained"] = out["generated_gap"] / out["observed_gap"]
    return out.reset_index().assign(pair="rural minus central city")


def top_chains(population, reference, k=8):
    """Shares of the k most frequent observed chains, per urban type (as in Hörl & Balac 2021, Fig. 6)."""
    records = []
    for urban in URBAN_ORDER:
        obs = weighted_share(reference[reference["urban_type"] == urban], "chain", "weight")
        gen = weighted_share(population[population["urban_type"] == urban], "chain", "weight")
        for rank, chain in enumerate(obs.sort_values(ascending=False).index[:k], start=1):
            records.append({"urban_type": urban, "rank": rank, "chain": chain,
                            "observed": float(obs[chain]), "generated": float(gen.get(chain, 0.0))})
    return pd.DataFrame.from_records(records)


def _pool(population, reference, top_k=TOP_K):
    keep = weighted_share(reference, "chain", "weight").sort_values(ascending=False).index[:top_k]
    def pooled(frame):
        return frame.assign(chain_class=frame["chain"].where(frame["chain"].isin(keep), "__other__"))
    return pooled(population), pooled(reference)


# --------------------------------------------------------------------------- main

def main(run_dir, survey, urban_type_zip, results_dir="results", reference=None):
    """``survey`` is the one the population was matched from (it identifies the donors);
    ``reference`` is the one it is scored against, the same survey unless given."""
    run_dir, results_dir = os.path.abspath(run_dir), os.path.abspath(results_dir)
    reference = reference or survey
    name = os.path.basename(run_dir.rstrip("/")) + ("" if reference == survey else "__vs_" + reference)
    out = os.path.join(results_dir, name)
    os.makedirs(out, exist_ok=True)

    population = load_population(run_dir, load_urban_types(urban_type_zip))
    if population.attrs.get("without_home_commune"):
        print("left out: %d matched persons whose household has no home commune" % population.attrs["without_home_commune"])
    reference = load_reference(results_dir, reference)
    gen, obs = _pool(population, reference)

    tables = {
        "matching_levels": matching_levels(run_dir),
        "donor_territory": donor_territory(population, donors(results_dir, survey)),
        "indicators": indicators(population, reference),
        "fidelity": stratified_fidelity(obs, gen, "chain_class", "urban_type",
                                        observed_weight="weight", generated_weight="weight", metric=hellinger),
        "contrast": contrast_retention(obs, gen, "chain_class", "urban_type",
                                       observed_weight="weight", generated_weight="weight"),
    }
    tables["gaps"] = gaps(tables["indicators"])
    tables["top_chains"] = top_chains(population, reference)

    for name, table in tables.items():
        table.to_csv(os.path.join(out, "%s.csv" % name), index=False)
    print("written to", out)
    return tables


if __name__ == "__main__":
    main(*sys.argv[1:6])
