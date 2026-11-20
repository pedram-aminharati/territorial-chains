"""Links between activity chains and who people are, where they work and how far from the city they live.

Usage
-----
    python scripts/territory_links.py <eqasim_path> <data_path> <output_dir> <urban_type_zip> <iris_contours> [results_dir]

Four analyses that go with work packages 1 to 3 of the project description. They read the
two surveys through eqasim's own cleaning stages (run this in the eqasim-france
environment), the populations of ``output_dir`` (variants A, B and C) and the tables
written by ``survey_contrasts.py`` and ``regional_reference.py``.

Outputs, in ``results/links/``
------------------------------
composition.csv     Is the rural minus central-city gap a matter of who lives there? The gap
                    in each survey, raw and with the mix of age and occupation (then also car
                    ownership) equalised between the two, in both directions.
commuting.csv       Home-to-work trips by urban type of the home, in the surveys and in the
                    populations: share of people who make one, median and mean straight-line
                    distance.
groups.csv          Distance between generated and observed chain distributions by population
                    group (in work, retired, other), for all residents and for rural ones.
distance_bands.csv  A second description of territory: distance from the home commune to the
                    nearest of Nantes and Saint-Nazaire, in four bands. Chain indicators in the
                    regional survey and in the populations, and the distance between the two.

Straight-line distances in the national survey are routed distances divided by 1.3, eqasim's
own convention. The regional survey records both.
"""

import os
import sys

import numpy as np
import pandas as pd

from territorial_chains import weighted_mean, weighted_share, hellinger, standardised_gap, bootstrap_ci

import evaluate_population as scoring
from export_page_data import load_communes
from survey_contrasts import edgt_urban_types

URBAN = scoring.URBAN_ORDER
VARIANTS = {"A": "A_entd_local", "B": "B_entd_national", "C": "C_entd_urban"}
SURVEYS = {"entd": "National survey (ENTD 2008)", "edgt_44": "Regional survey (EDGT 2015)"}
CELLS = ["age_class", "socioprofessional_class", "any_cars"]
CENTRES = {"44109": "Nantes", "44184": "Saint-Nazaire"}
BANDS = [(0, 5, "under 5 km"), (5, 15, "5 to 15 km"), (15, 30, "15 to 30 km"), (30, 1000, "30 km and more")]
GROUPS = {"in work": [1, 2, 3, 4, 5, 6], "retired": [7], "other": [8]}
TOP_K = 25


# --------------------------------------------------------------------------- loading

def survey_tables(eqasim_path, data_path, cache, hts):
    """Households, persons and trips as eqasim's cleaning stage returns them."""
    import synpp

    cwd = os.getcwd()
    os.chdir(eqasim_path)
    if eqasim_path not in sys.path:
        sys.path.insert(0, eqasim_path)
    try:
        return synpp.run([{"descriptor": "data.hts.%s.cleaned" % hts}],
                         config={"data_path": data_path, "regions": [], "departments": [44]}, working_directory=cache)[0]
    finally:
        os.chdir(cwd)


def population(run_dir, urban_types):
    """Matched residents of one variant with chain, home commune, urban type and occupation."""
    persons = pd.read_parquet(scoring._one(run_dir, "persons.parquet"))
    df = scoring.load_population(run_dir, urban_types)
    return df.merge(persons[["person_id", "socioprofessional_class"]], on="person_id")


def group_of(frame):
    lookup = {code: name for name, codes in GROUPS.items() for code in codes}
    return frame["socioprofessional_class"].astype(int).map(lookup)


# --------------------------------------------------------------------------- composition

def composition(references, n_boot=200):
    """The rural minus central-city gap, raw and with the composition of the two strata equalised.

    Two sets of attributes and two directions are reported, because the answer can depend on
    both: rural respondents given the central-city mix, and central-city respondents given the
    rural mix. Whichever stratum is reweighted, the gap is always rural minus central city.
    """
    indicators = {"immobile_share": ("immobile", "all"), "tours_per_mobile": ("n_tours", "mobile")}
    cell_sets = {"age and occupation": ["age_class", "socioprofessional_class"],
                 "age, occupation and car": ["age_class", "socioprofessional_class", "any_cars"]}

    def gaps(sample, column, cells, standard):
        if standard == "central city":
            return standardised_gap(sample, column, "urban_type", "none", "central_city", cells)
        mirrored = standardised_gap(sample, column, "urban_type", "central_city", "none", cells)
        return {"raw": -mirrored["raw"], "standardised": -mirrored["standardised"], "coverage": mirrored["coverage"]}

    rows = []
    for survey, table in references.items():
        for name, (column, scope) in indicators.items():
            sample = table if scope == "all" else table[~table["immobile"]]
            sample = sample[sample["urban_type"].isin(["none", "central_city"])].reset_index(drop=True)
            for label, cells in cell_sets.items():
                for standard in ("central city", "rural"):
                    estimate = gaps(sample, column, cells, standard)
                    rng, draws = np.random.default_rng(1), {"raw": [], "standardised": []}
                    for _ in range(n_boot):          # respondents are resampled, weights travel with them
                        again = gaps(sample.iloc[rng.integers(0, len(sample), len(sample))], column, cells, standard)
                        for key in draws:
                            draws[key].append(again[key])
                    row = {"survey": survey, "indicator": name, "attributes": label, "mix_of": standard,
                           "respondents_rural": int((sample["urban_type"] == "none").sum()),
                           "respondents_central": int((sample["urban_type"] == "central_city").sum()),
                           "coverage": estimate["coverage"]}
                    for key in ("raw", "standardised"):
                        low, high = np.quantile(draws[key], [0.025, 0.975])
                        row.update({key: estimate[key], key + "_low": float(low), key + "_high": float(high)})
                    rows.append(row)
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- commuting

def commute_table(frame, source):
    """Share of people with a home-to-work trip, and its straight-line distance, by urban type."""
    rows = []
    for urban in URBAN + ["all"]:
        g = frame if urban == "all" else frame[frame["urban_type"] == urban]
        c = g[g["commute_km"].notna()]
        if len(c) == 0:
            continue
        order = np.argsort(c["commute_km"].to_numpy())
        cumulative = np.cumsum(c["weight"].to_numpy()[order]) / c["weight"].sum()
        rows.append({"source": source, "urban_type": urban, "persons": len(g), "commuters": len(c),
                     "commuter_share": float(c["weight"].sum() / g["weight"].sum()),
                     "median_km": float(c["commute_km"].to_numpy()[order][np.searchsorted(cumulative, 0.5)]),
                     "mean_km": weighted_mean(c["commute_km"], c["weight"])})
    return rows


def survey_commutes(reference, trips):
    """First home-to-work trip of each respondent, straight-line kilometres."""
    t = trips[(trips["preceding_purpose"].astype(str) == "home") & (trips["following_purpose"].astype(str) == "work")]
    t = t.sort_values(["person_id", "trip_id"]).drop_duplicates("person_id")
    if "euclidean_distance" in t:
        km = t["euclidean_distance"] / 1000.0
    else:
        km = t["routed_distance"] / 1000.0 / scoring.ROUTED_TO_EUCLIDEAN
    return reference.assign(commute_km=reference["person_id"].map(pd.Series(km.to_numpy(), index=t["person_id"].to_numpy())))


def population_commutes(df, run_dir):
    import geopandas as gpd

    points = gpd.read_parquet(scoring._one(run_dir, "activities.geoparquet"))[["person_id", "activity_index", "purpose", "geometry"]]
    points = points.sort_values(["person_id", "activity_index"])
    x, y = points.geometry.x.to_numpy(), points.geometry.y.to_numpy()
    person, purpose = points["person_id"].to_numpy(), points["purpose"].astype(str).to_numpy()
    leg = (person[1:] == person[:-1]) & (purpose[:-1] == "home") & (purpose[1:] == "work")
    km = pd.Series(np.hypot(np.diff(x), np.diff(y))[leg] / 1000.0, index=person[:-1][leg])
    return df.assign(commute_km=df["person_id"].map(km[~km.index.duplicated()]))


# --------------------------------------------------------------------------- population groups

def groups(populations, references):
    rows = []
    for letter, df in populations.items():
        for survey, reference in references.items():
            keep = weighted_share(reference, "chain", "weight").sort_values(ascending=False).index[:TOP_K]
            pooled = lambda frame: frame.assign(klass=frame["chain"].where(frame["chain"].isin(keep), "__other__"))
            gen, obs = pooled(df), pooled(reference)
            for scope in ("all", "none"):
                g = gen if scope == "all" else gen[gen["urban_type"] == scope]
                o = obs if scope == "all" else obs[obs["urban_type"] == scope]
                for name in GROUPS:
                    gg, oo = g[g["group"] == name], o[o["group"] == name]
                    rows.append({"variant": letter, "reference": survey, "residents": "rural" if scope == "none" else "all",
                                 "group": name, "generated": len(gg), "respondents": len(oo),
                                 "hellinger": hellinger(weighted_share(oo, "klass", "weight"), weighted_share(gg, "klass", "weight")),
                                 "immobile_generated": weighted_mean(gg["immobile"], gg["weight"]),
                                 "immobile_observed": weighted_mean(oo["immobile"], oo["weight"])})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- distance to the city

def band_of_commune(communes):
    """Band of each commune by straight-line distance from its centre to the nearest large city centre."""
    centroids = communes.set_index("commune_id").geometry.centroid
    distance = pd.concat([centroids.distance(centroids[code]) for code in CENTRES], axis=1).min(axis=1) / 1000.0
    labels = pd.Series(index=distance.index, dtype=object)
    for low, high, name in BANDS:
        labels[(distance >= low) & (distance < high)] = name
    return labels


def distance_bands(samples, reference_key="Regional survey (EDGT 2015)"):
    order = [name for _, _, name in BANDS]
    reference = samples[reference_key]
    keep = weighted_share(reference, "chain", "weight").sort_values(ascending=False).index[:TOP_K]
    pooled = lambda frame: frame.assign(klass=frame["chain"].where(frame["chain"].isin(keep), "__other__"))
    rows = []
    for source, frame in samples.items():
        for band in order:
            g, o = frame[frame["band"] == band], reference[reference["band"] == band]
            mobile = g[~g["immobile"]]
            low, high = np.nan, np.nan
            if source == reference_key:                # an interval for the survey; the populations are large
                _, low, high = bootstrap_ci(g, lambda f: weighted_mean(f["immobile"], f["weight"]), n_boot=300, seed=1)
            rows.append({"source": source, "band": band, "persons": len(g),
                         "immobile_share": weighted_mean(g["immobile"], g["weight"]),
                         "immobile_low": low, "immobile_high": high,
                         "tours_per_mobile": weighted_mean(mobile["n_tours"], mobile["weight"]),
                         "activities_per_mobile": weighted_mean(mobile["n_activities"], mobile["weight"]),
                         "hellinger_to_regional": np.nan if source == reference_key else hellinger(
                             weighted_share(pooled(o), "klass", "weight"), weighted_share(pooled(g), "klass", "weight"))})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- main

def main(eqasim_path, data_path, output_dir, urban_type_zip, iris_contours, results_dir="results"):
    eqasim_path, data_path, output_dir = (os.path.abspath(p) for p in (eqasim_path, data_path, output_dir))
    results_dir = os.path.abspath(results_dir)
    out = os.path.join(results_dir, "links")
    os.makedirs(out, exist_ok=True)
    cache = os.path.join(results_dir, "_cache")
    os.makedirs(cache, exist_ok=True)

    urban_types = scoring.load_urban_types(urban_type_zip)
    references = {key: pd.read_parquet(os.path.join(results_dir, "chains_%s.parquet" % key)) for key in SURVEYS}
    for table in references.values():
        table["group"] = group_of(table)
    populations = {letter: population(os.path.join(output_dir, name), urban_types) for letter, name in VARIANTS.items()
                   if os.path.isdir(os.path.join(output_dir, name))}
    for df in populations.values():
        df["group"] = group_of(df)

    composition(references).to_csv(os.path.join(out, "composition.csv"), index=False, float_format="%.6f")

    tables = {key: survey_tables(eqasim_path, data_path, cache, key) for key in SURVEYS}
    rows = []
    for key, label in SURVEYS.items():
        rows += commute_table(survey_commutes(references[key], tables[key][2]), label)
    for letter, df in populations.items():
        rows += commute_table(population_commutes(df, os.path.join(output_dir, VARIANTS[letter])), letter)
    pd.DataFrame(rows).to_csv(os.path.join(out, "commuting.csv"), index=False, float_format="%.6f")

    groups(populations, references).to_csv(os.path.join(out, "groups.csv"), index=False, float_format="%.6f")

    bands = band_of_commune(load_communes(iris_contours))
    households = tables["edgt_44"][0]
    home = edgt_urban_types(households, data_path).set_index("household_id")["commune_id"]
    regional = references["edgt_44"].assign(band=references["edgt_44"]["household_id"].map(home).map(bands))
    outside = int(regional["band"].isna().sum())
    samples = {"Regional survey (EDGT 2015)": regional[regional["band"].notna()]}
    for letter, df in populations.items():
        samples[letter] = df.assign(band=df["commune_id"].map(bands))
    distance_bands(samples).to_csv(os.path.join(out, "distance_bands.csv"), index=False, float_format="%.6f")

    print("regional respondents living outside the département, left out of the bands: %d" % outside)
    print("written to", out)


if __name__ == "__main__":
    main(*sys.argv[1:7])
