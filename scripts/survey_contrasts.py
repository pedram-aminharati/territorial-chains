"""Work package 2: activity chains by territory in ENTD 2008 and EMP 2019.

The surveys are read through eqasim's own cleaning stages, so the chains scored
here are exactly the ones the pipeline would hand to statistical matching.

Usage
-----
    python scripts/survey_contrasts.py /path/to/eqasim-france /path/to/data [results_dir]

``data`` must contain ``entd_2008/`` and ``emp_2019/`` as eqasim expects them.
Run it with the eqasim environment (it needs ``synpp``).

Outputs (CSV, in ``results/``)
------------------------------
donors.csv            respondents and Kish effective size by survey, area and urban type
indicators.csv        weighted chain indicators by urban type, with bootstrap intervals
contrast.csv          between-territory divergence of chain distributions, with a permutation noise floor
thin_cells.csv        share of people whose matching cell has fewer than 20 donors
emp_day_weights.csv   weekday immobility in EMP under person weights and under day weights
"""

import os
import sys
import zipfile

import numpy as np
import pandas as pd

from territorial_chains import (
    chains_from_hts, add_indicators, weighted_share, weighted_mean,
    kish_effective_size, bootstrap_ci, jensen_shannon, distribution,
)

URBAN_ORDER = ["central_city", "suburb", "isolated_city", "none"]
PRIMARY = {"home", "work", "education", "leisure", "shop"}          # eqasim default purposes
AGE_BOUNDARIES = [14, 29, 44, 59, 74, 1000]                        # as in synthesis/population/matched.py
MATCHING = ["sex", "any_cars", "age_class", "socioprofessional_class"]
MINIMUM_OBSERVATIONS = 20
EMP_ZIP = "emp_2019/emp_2019_donnees_individuelles_anonymisees_novembre2024.zip"


# --------------------------------------------------------------------------- loading

def load_survey(eqasim_path, data_path, cache_path, hts):
    """Run eqasim's ``data.hts.<hts>.cleaned`` stage and return one row per diary respondent."""
    import synpp

    cwd = os.getcwd()
    os.chdir(eqasim_path)
    sys.path.insert(0, eqasim_path)
    try:
        households, persons, trips = synpp.run(
            [{"descriptor": "data.hts.%s.cleaned" % hts}],
            config={"data_path": data_path, "regions": [], "departments": [44]},
            working_directory=cache_path)[0]
    finally:
        os.chdir(cwd)

    if hts == "edgt_44":
        households = households.merge(edgt_urban_types(households, data_path), on="household_id")

    # Same purpose reduction as eqasim's data.hts.selected stage.
    trips = trips.copy()
    for column in ("preceding_purpose", "following_purpose"):
        trips[column] = trips[column].astype(str).where(trips[column].astype(str).isin(PRIMARY), "other")

    # Only respondents whose day is known (eqasim's reweighted stage does the same).
    persons = persons[persons["number_of_trips"] >= 0].copy()

    df = add_indicators(chains_from_hts(persons, trips))
    df = df.merge(persons[[
        "person_id", "household_id", "trip_weight", "age", "sex",
        "socioprofessional_class", "departement_id",
    ] + [c for c in ("emp_person_id",) if c in persons]], on="person_id")
    df = df.merge(households[["household_id", "urban_type", "number_of_vehicles"]], on="household_id")

    distance = trips.groupby("person_id")["routed_distance"].sum() / 1000.0
    df["distance_km"] = df["person_id"].map(distance).fillna(0.0)

    # With filter_hts, eqasim also drops respondents with a trip that starts or ends outside
    # the study area (data.hts.<hts>.filtered). For a single departement that is every
    # respondent who leaves their home departement during the day.
    home = trips["person_id"].map(persons.set_index("person_id")["departement_id"].astype(str))
    leaves = (trips["origin_departement_id"].astype(str) != home) | (trips["destination_departement_id"].astype(str) != home)
    df["leaves_departement"] = df["person_id"].isin(set(trips.loc[leaves, "person_id"]))
    if hts != "entd":       # only checked on ENTD, where trip ends carry a departement
        df["leaves_departement"] = None

    df["weight"] = df["trip_weight"].astype(float)
    df["urban_type"] = df["urban_type"].astype(str)
    df["departement_id"] = df["departement_id"].astype(str)
    df["age_class"] = np.digitize(df["age"], AGE_BOUNDARIES, right=True)
    df["any_cars"] = df["number_of_vehicles"] > 0
    df["survey"] = hts
    return df[df["weight"] > 0].reset_index(drop=True)


def edgt_urban_types(households, data_path):
    """Urban type of each EDGT household, which eqasim's cleaning does not keep.

    The survey gives the home as a fine zone (sampling sector + zone). The zone table
    published with the survey names the commune of every zone; communes merged since
    2015 are brought to today's codes (reference/communes_2015_to_2026.csv), and the
    urban type is INSEE's urban-unit status of that commune, as for the populations.
    """
    import glob
    from evaluate_population import load_urban_types

    def one(pattern):
        matches = glob.glob(os.path.join(data_path, pattern), recursive=True)
        if not matches:
            raise FileNotFoundError("Not found under %s: %s" % (data_path, pattern))
        return matches[0]

    workbook = one("edgt_44_2015/**/07_denomination_perimetres_EDGT44*.xls")
    zones = None
    for engine in ("calamine", "xlrd"):
        try:
            zones = pd.read_excel(workbook, sheet_name="ZF", dtype=str, engine=engine)
            break
        except ImportError:
            continue
    if zones is None:
        raise ImportError("Reading the EDGT zone table needs python-calamine or xlrd.")

    here = os.path.dirname(os.path.abspath(__file__))
    merged = pd.read_csv(os.path.join(here, "..", "reference", "communes_2015_to_2026.csv"), dtype=str)
    today = dict(zip(merged["commune_2015"], merged["commune_2026"]))

    out = households[["household_id"]].copy()
    out["zone"] = households["MTIR"].astype(str).str.zfill(3) + households["MP2"].astype(str).str.zfill(3)
    out = out.merge(zones[["ZF", "Id_commune"]].rename(columns={"ZF": "zone"}), on="zone", how="left")
    out["commune_id"] = out["Id_commune"].map(lambda code: today.get(code, code))
    out = out.merge(load_urban_types(one("urban_type/UU2020*.zip")), on="commune_id", how="left")
    if out["urban_type"].isna().any():
        raise RuntimeError("%d EDGT households could not be given an urban type" % out["urban_type"].isna().sum())
    return out[["household_id", "commune_id", "urban_type"]]


def emp_day_weights(data_path):
    """EMP 2019 day weights, which eqasim's cleaning stage does not read.

    The EMP diary describes a day on which the respondent travelled; people with
    no diary are those who stayed in on every weekday (``MIMMOSEM == 1``). The
    file carries a day weight ``POND_JOUR`` for that reason. Returns the per
    respondent weekday day weight and the immobility implied by each weighting.
    """
    with zipfile.ZipFile(os.path.join(data_path, EMP_ZIP)) as archive:
        trips = pd.read_csv(archive.open("5. k_deploc_public_V4.csv"), sep=",", encoding="latin1",
                            usecols=["IDENT_IND", "TYPEJOUR", "POND_JOUR"])
        persons = pd.read_csv(archive.open("k_individu_public_V3.csv"), sep=";", encoding="latin1",
                              usecols=["IDENT_IND", "IDENT_MEN", "pond_indC", "MIMMOSEM"])
        households = pd.read_csv(archive.open("tcm_men_public_V3.csv"), sep=",", encoding="latin1",
                                 usecols=["ident_men", "STATUTCOM_UU_RES"])

    persons = persons.merge(households.rename(columns={"ident_men": "IDENT_MEN"}), on="IDENT_MEN", how="left")
    persons["urban_type"] = persons["STATUTCOM_UU_RES"].map(
        {"B": "suburb", "C": "central_city", "I": "isolated_city", "H": "none"}).fillna("none")

    first = trips.drop_duplicates("IDENT_IND")
    weekday = first[first["TYPEJOUR"] == 1].set_index("IDENT_IND")["POND_JOUR"]
    persons["weekday_day_weight"] = persons["IDENT_IND"].map(weekday)
    persons["has_diary"] = persons["IDENT_IND"].isin(first["IDENT_IND"])

    def summary(group):
        total = group["pond_indC"].sum()
        return pd.Series({
            "respondents": len(group),
            "no_diary_all_week": int((~group["has_diary"]).sum()),
            "immobile_person_weight": group.loc[~group["has_diary"], "pond_indC"].sum() / total,
            "immobile_day_weight": 1.0 - group["weekday_day_weight"].sum() / (5.0 * total),
        })

    table = pd.concat([
        persons.groupby("urban_type").apply(summary, include_groups=False),
        summary(persons).to_frame("all").T,
    ])
    table.index.name = "urban_type"
    return persons[["IDENT_IND", "weekday_day_weight"]], table.reset_index()


# --------------------------------------------------------------------------- tables

def donors_table(df):
    records = []
    for area, frame in (("France", df), ("Loire-Atlantique (44)", df[df["departement_id"] == "44"])):
        for urban in URBAN_ORDER + ["all"]:
            g = frame if urban == "all" else frame[frame["urban_type"] == urban]
            records.append({
                "survey": df["survey"].iloc[0], "area": area, "urban_type": urban,
                "respondents": len(g),
                "effective_size": round(kish_effective_size(g["weight"]), 0),
            })
    return pd.DataFrame.from_records(records)


INDICATORS = {
    "immobile_share":        (lambda d: weighted_mean(d["immobile"], d["weight"]), "all"),
    "activities_per_mobile": (lambda d: weighted_mean(d["n_activities"], d["weight"]), "mobile"),
    "tours_per_mobile":      (lambda d: weighted_mean(d["n_tours"], d["weight"]), "mobile"),
    "simple_commute_share":  (lambda d: weighted_mean(d["simple_commute"], d["weight"]), "mobile"),
    "secondary_share":       (lambda d: weighted_mean(d["has_secondary"], d["weight"]), "mobile"),
    "distance_km_per_mobile": (lambda d: weighted_mean(d["distance_km"], d["weight"]), "mobile"),
}


def indicators_table(df, n_boot=400):
    records = []
    for urban in URBAN_ORDER:
        g = df[df["urban_type"] == urban]
        for name, (statistic, scope) in INDICATORS.items():
            sample = g if scope == "all" else g[~g["immobile"]]
            estimate, lower, upper = bootstrap_ci(sample, statistic, n_boot=n_boot, seed=1)
            records.append({
                "survey": df["survey"].iloc[0], "urban_type": urban, "indicator": name,
                "estimate": estimate, "ci_lower": lower, "ci_upper": upper, "n": len(sample),
            })
    return pd.DataFrame.from_records(records)


def contrast_table(df, column="chain", top_k=25, n_perm=300, seed=0):
    """Divergence between urban types, against what shuffled labels produce.

    Divergences on sparse distributions are inflated by sampling noise, so each
    pair is reported next to the 95th percentile obtained after permuting the
    territory labels of the two groups (the value expected with no real contrast).
    """
    rng = np.random.default_rng(seed)
    keep = distribution(df, column, "weight").index[:top_k]
    df = df.assign(_c=df[column].where(df[column].isin(keep), "__other__"))

    records = []
    for i, a in enumerate(URBAN_ORDER):
        for b in URBAN_ORDER[i + 1:]:
            pair = df[df["urban_type"].isin([a, b])]
            is_a = (pair["urban_type"] == a).to_numpy()

            def divergence(mask):
                return jensen_shannon(weighted_share(pair[mask], "_c", "weight"),
                                      weighted_share(pair[~mask], "_c", "weight"))

            observed = divergence(is_a)
            null = [divergence(rng.permutation(is_a)) for _ in range(n_perm)]
            records.append({
                "survey": df["survey"].iloc[0], "pair": "%s / %s" % (a, b),
                "js_divergence": observed, "noise_floor_p95": float(np.quantile(null, 0.95)),
                "ratio_to_noise": observed / float(np.quantile(null, 0.95)),
            })
    return pd.DataFrame.from_records(records)


def thin_cells_table(df):
    """Share of the (weighted) population whose matching cell has under 20 donors.

    Three donor pools, mirroring the pipeline variants: national donors matched
    on the default attributes, the same with urban type added, and donors
    restricted to Loire-Atlantique as ``filter_hts: true`` does.
    """
    pools = {
        "national, default attributes": (df, MATCHING),
        "national, + urban type": (df, MATCHING + ["urban_type"]),
        "Loire-Atlantique only, default": (df[df["departement_id"] == "44"], MATCHING),
        "Loire-Atlantique only, + urban type": (df[df["departement_id"] == "44"], MATCHING + ["urban_type"]),
    }
    records = []
    for label, (pool, columns) in pools.items():
        if len(pool) == 0:
            continue
        cell_size = pool.groupby(columns, observed=True)["person_id"].transform("size")
        thin = cell_size < MINIMUM_OBSERVATIONS
        for urban in URBAN_ORDER + ["all"]:
            mask = np.ones(len(pool), dtype=bool) if urban == "all" else (pool["urban_type"] == urban).to_numpy()
            if mask.sum() == 0:
                continue
            records.append({
                "survey": df["survey"].iloc[0], "donor_pool": label, "urban_type": urban,
                "donors": int(mask.sum()),
                "share_in_thin_cells": float(pool.loc[mask & thin.to_numpy(), "weight"].sum() / pool.loc[mask, "weight"].sum()),
            })
    return pd.DataFrame.from_records(records)


# --------------------------------------------------------------------------- main

def main(eqasim_path, data_path, results_path="results"):
    eqasim_path, data_path, results_path = map(os.path.abspath, (eqasim_path, data_path, results_path))
    os.makedirs(results_path, exist_ok=True)
    cache = os.path.join(results_path, "_cache")
    os.makedirs(cache, exist_ok=True)

    entd = load_survey(eqasim_path, data_path, cache, "entd")
    emp = load_survey(eqasim_path, data_path, cache, "emp")

    # EMP read with its day weights: mobile diaries only, weighted by POND_JOUR.
    day_weights, emp_immobility = emp_day_weights(data_path)
    emp_day = emp.merge(day_weights, left_on="emp_person_id", right_on="IDENT_IND", how="left")
    emp_day = emp_day[~emp_day["immobile"] & emp_day["weekday_day_weight"].notna()].copy()
    emp_day["weight"] = emp_day["weekday_day_weight"]
    emp_day["survey"] = "emp_day_weighted"

    surveys = [entd, emp, emp_day]

    pd.concat([donors_table(s) for s in (entd, emp)]).to_csv(os.path.join(results_path, "donors.csv"), index=False)
    indicators = pd.concat([indicators_table(s) for s in surveys])
    # The day-weighted EMP frame holds mobile diaries only; its immobility is in emp_day_weights.csv.
    indicators = indicators[~((indicators["survey"] == "emp_day_weighted") & (indicators["indicator"] == "immobile_share"))]
    indicators.to_csv(os.path.join(results_path, "indicators.csv"), index=False)
    pd.concat([contrast_table(s) for s in (entd, emp_day)]).to_csv(os.path.join(results_path, "contrast.csv"), index=False)
    pd.concat([thin_cells_table(s) for s in (entd, emp)]).to_csv(os.path.join(results_path, "thin_cells.csv"), index=False)
    emp_immobility.to_csv(os.path.join(results_path, "emp_day_weights.csv"), index=False)

    for s in surveys:
        s.drop(columns=[c for c in ("IDENT_IND",) if c in s]).to_parquet(
            os.path.join(results_path, "chains_%s.parquet" % s["survey"].iloc[0]), index=False)

    print("written to", results_path)


if __name__ == "__main__":
    main(*sys.argv[1:4])
