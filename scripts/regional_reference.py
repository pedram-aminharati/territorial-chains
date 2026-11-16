"""The regional survey (EDGT Loire-Atlantique 2015) as a local reference.

Usage
-----
    python scripts/regional_reference.py <eqasim_path> <data_path> [results_dir]

Reads the survey through eqasim's own ``data.hts.edgt_44.cleaned`` stage, gives each
respondent the urban type of the home commune, and writes:

chains_edgt_44.parquet    one row per diary respondent (not versioned; reference for scoring)
edgt/respondents.csv      respondents and effective sample size by urban type
edgt/indicators.csv       chain indicators by urban type with bootstrap intervals,
                          next to the national survey (ENTD 2008) used so far
edgt/stay_home.csv        share staying home by urban type in three samples: the regional
                          survey, the national survey, and the national survey's
                          respondents who live in Loire-Atlantique

Populations are then scored against it with
``evaluate_population.py <run> entd <urban_type_zip> results edgt_44``.
"""

import os
import sys

import pandas as pd

from territorial_chains import kish_effective_size, weighted_mean, bootstrap_ci

from survey_contrasts import load_survey, indicators_table, URBAN_ORDER


def main(eqasim_path, data_path, results_path="results"):
    eqasim_path, data_path, results_path = map(os.path.abspath, (eqasim_path, data_path, results_path))
    out = os.path.join(results_path, "edgt")
    os.makedirs(out, exist_ok=True)
    cache = os.path.join(results_path, "_cache")
    os.makedirs(cache, exist_ok=True)

    edgt = load_survey(eqasim_path, data_path, cache, "edgt_44")
    edgt.to_parquet(os.path.join(results_path, "chains_edgt_44.parquet"), index=False)

    rows = [{"urban_type": u, "respondents": int((edgt["urban_type"] == u).sum()),
             "effective_size": round(kish_effective_size(edgt.loc[edgt["urban_type"] == u, "weight"]), 0)}
            for u in URBAN_ORDER]
    rows.append({"urban_type": "all", "respondents": len(edgt),
                 "effective_size": round(kish_effective_size(edgt["weight"]), 0)})
    pd.DataFrame(rows).to_csv(os.path.join(out, "respondents.csv"), index=False)

    table = indicators_table(edgt)
    national = os.path.join(results_path, "indicators.csv")
    if os.path.exists(national):
        entd = pd.read_csv(national)
        entd = entd[entd["survey"] == "entd"][["urban_type", "indicator", "estimate", "ci_lower", "ci_upper"]]
        table = table.merge(entd.rename(columns={"estimate": "entd_estimate", "ci_lower": "entd_ci_lower",
                                                 "ci_upper": "entd_ci_upper"}), on=["urban_type", "indicator"], how="left")
    table.to_csv(os.path.join(out, "indicators.csv"), index=False)

    # Staying home in three samples: the regional survey, the national survey, and the
    # national survey's own respondents who live in Loire-Atlantique.
    samples = [("edgt", edgt)]
    national_chains = os.path.join(results_path, "chains_entd.parquet")
    if os.path.exists(national_chains):
        entd_chains = pd.read_parquet(national_chains)
        samples += [("entd", entd_chains), ("entd_44", entd_chains[entd_chains["departement_id"].astype(str) == "44"])]
    stay = []
    share = lambda d: weighted_mean(d["immobile"], d["weight"])
    for name, frame in samples:
        for urban in URBAN_ORDER + ["all"]:
            group = frame if urban == "all" else frame[frame["urban_type"] == urban]
            estimate, lower, upper = bootstrap_ci(group, share, n_boot=400, seed=1)
            stay.append({"sample": name, "urban_type": urban, "respondents": len(group),
                         "estimate": estimate, "ci_lower": lower, "ci_upper": upper})
    pd.DataFrame(stay).to_csv(os.path.join(out, "stay_home.csv"), index=False)

    print(pd.DataFrame(rows).to_string(index=False))
    print("written to", out)


if __name__ == "__main__":
    main(*sys.argv[1:4])
