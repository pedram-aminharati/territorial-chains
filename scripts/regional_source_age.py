"""Populations built from the regional survey: how much of the stay-home gap is age?

Usage
-----
    python scripts/regional_source_age.py <output_dir> <urban_type_zip> [results_dir]

A population matched from the regional survey and scored against that survey can
still differ from it, because the census and the survey do not describe the same
people. In Loire-Atlantique the census counts more residents over 64 in rural
communes than the regional survey of 2015 does, and older people stay home more.

For each population found in ``output_dir`` (F, G and T), the share of residents
staying home is computed for central cities and rural communes, as generated and
with the age mix of the survey respondents of the same urban type. The rural minus
central-city gap is given both ways, next to the survey's own.

Output: ``results/links/regional_source_age.csv``, one row per population.
"""

import os
import sys

import numpy as np
import pandas as pd

from evaluate_population import load_population, load_urban_types

RUNS = ["F_edgt44", "G_edgt44_urban", "T_edgt44_structured"]
AGE_BOUNDS = [0, 14, 24, 44, 64, 74, 200]
PAIR = ("central_city", "none")


def main(output_dir, urban_type_zip, results_dir="results"):
    urban_types = load_urban_types(urban_type_zip)
    survey = pd.read_parquet(os.path.join(results_dir, "chains_edgt_44.parquet"))
    survey["age_band"] = pd.cut(survey["age"], AGE_BOUNDS)

    rows = []
    for run in RUNS:
        run_dir = os.path.join(output_dir, run)
        if not os.path.isdir(run_dir):
            continue
        population = load_population(run_dir, urban_types)
        population["age_band"] = pd.cut(population["age"], AGE_BOUNDS)

        row = {"run": run}
        for urban in PAIR:
            observed = survey[survey["urban_type"] == urban]
            mix = observed.groupby("age_band", observed=True)["weight"].sum()
            mix = mix / mix.sum()
            generated = population[population["urban_type"] == urban]
            rate = generated.groupby("age_band", observed=True)["immobile"].mean()
            own = generated.groupby("age_band", observed=True).size() / len(generated)

            row[urban + "_generated"] = generated["immobile"].mean()
            row[urban + "_survey_age_mix"] = (rate * mix).sum()
            row[urban + "_observed"] = np.average(observed["immobile"], weights=observed["weight"])
            row[urban + "_over_64_population"] = own.iloc[-2:].sum()
            row[urban + "_over_64_survey"] = mix.iloc[-2:].sum()
        for kind in ("generated", "survey_age_mix", "observed"):
            row["gap_" + kind] = row["none_" + kind] - row["central_city_" + kind]
        rows.append(row)

    out = os.path.join(results_dir, "links")
    os.makedirs(out, exist_ok=True)
    table = pd.DataFrame(rows)
    table.to_csv(os.path.join(out, "regional_source_age.csv"), index=False)
    print(table.set_index("run").T.round(4).to_string())


if __name__ == "__main__":
    main(*sys.argv[1:4])
