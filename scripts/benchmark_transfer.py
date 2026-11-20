"""Transferability: generators trained on the national survey, judged in another territory.

Usage
-----
    python scripts/benchmark_transfer.py /path/to/eqasim-france [results_dir] [repeats]

``benchmark_generators.py`` holds out respondents of the survey the generators were
trained on. This script asks the harder question a pipeline faces in practice. Every
generator is trained on all diary respondents of the national survey (ENTD 2008) and
proposes a chain for each respondent of the regional survey (EDGT Loire-Atlantique
2015) from that person's attributes. The proposals are compared with what the
regional respondents reported, by urban type.

Reads ``results/chains_entd.parquet`` and ``results/chains_edgt_44.parquet``. Each
repeat retrains the models with another seed. Two rows are not generators:

``national_survey``   the national respondents of the same urban type, taken as they
                      are: the distance between the two surveys, which a generator
                      that reproduced the national survey perfectly would inherit
``floor``             one half of the regional respondents against the other half:
                      what sampling alone produces inside the regional survey

Outputs, in ``results/generators/``: ``transfer.csv`` (one row per repeat, method and
urban type) and ``transfer_summary.csv`` (mean, minimum and maximum over repeats).
"""

import os
import sys
import time
import warnings

import numpy as np
import pandas as pd

from territorial_chains import weighted_share

from benchmark_generators import methods, score, TOP_K


def main(eqasim_path, results_dir="results", repeats=3):
    warnings.filterwarnings("ignore")
    results_dir = os.path.abspath(results_dir)
    out = os.path.join(results_dir, "generators")
    os.makedirs(out, exist_ok=True)

    train = pd.read_parquet(os.path.join(results_dir, "chains_entd.parquet")).reset_index(drop=True)
    target = pd.read_parquet(os.path.join(results_dir, "chains_edgt_44.parquet")).reset_index(drop=True)
    for frame in (train, target):
        frame["sex"] = frame["sex"].astype(str)

    # Chains are compared on the most frequent ones of the survey that is the judge.
    classes = weighted_share(target, "chain", "weight").sort_values(ascending=False).index[:TOP_K]
    known = set(train["chain"])
    expected = {"national_survey", "floor"} | set(methods(eqasim_path, 0))

    records, done = [], set()
    path = os.path.join(out, "transfer.csv")
    if os.path.exists(path):                  # continue after the last complete repeat
        earlier = pd.read_csv(path)
        done = {repeat for repeat, group in earlier.groupby("repeat") if set(group["method"]) == expected}
        records = earlier[earlier["repeat"].isin(done)].to_dict("records")

    for repeat in range(int(repeats)):
        if repeat in done:
            print("repeat %d  already complete" % repeat, flush=True)
            continue
        rng = np.random.default_rng(2000 + repeat)

        for row in score(train[["chain", "urban_type", "weight"]], target, classes, known):
            records.append({"repeat": repeat, "method": "national_survey", **row})
        half = rng.random(len(target)) < 0.5
        for row in score(target.loc[half, ["chain", "urban_type", "weight"]], target[~half], classes, known):
            records.append({"repeat": repeat, "method": "floor", **row})

        for name, build in methods(eqasim_path, repeat).items():
            start = time.time()
            generator = build().fit(train)
            chains = generator.sample(target, rng)
            generated = pd.DataFrame({"chain": chains, "urban_type": target["urban_type"], "weight": target["weight"]})
            for row in score(generated, target, classes, known):
                records.append({"repeat": repeat, "method": name, **row})
            print("repeat %d  %-26s %5.1fs" % (repeat, name, time.time() - start), flush=True)

        pd.DataFrame.from_records(records).to_csv(path, index=False)

    frame = pd.DataFrame.from_records(records)
    numeric = [c for c in frame.columns if c not in ("repeat", "method", "urban_type")]
    summary = frame.groupby(["method", "urban_type"])[numeric].agg(["mean", "min", "max"])
    summary.columns = ["%s_%s" % c for c in summary.columns]
    summary.reset_index().to_csv(os.path.join(out, "transfer_summary.csv"), index=False)
    print("written to", out)


if __name__ == "__main__":
    main(*sys.argv[1:4])
