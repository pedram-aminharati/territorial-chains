"""Work package 4: chain generators against statistical matching, on held-out respondents.

Usage
-----
    python scripts/benchmark_generators.py /path/to/eqasim-france [results_dir] [splits]

Reads ``results/chains_entd.parquet`` (written by survey_contrasts.py). For each
random split, 80% of the diary respondents train every generator and the other
20% are the target: each generator sees only their attributes and proposes a
chain, which is then compared with what those respondents actually reported, by
urban type. Repeating over splits gives a mean and a range, the way Hörl and
Balac (2021) report variation over realisations.

The methods are eqasim's statistical matching, a Bayesian network, a causal
transformer, a conditional variational autoencoder and a conditional Wasserstein
GAN, each with and without the home territory among its inputs.

``floor`` is not a generator: it is the distance between the training and test
respondents of the same urban type, i.e. what sampling alone produces.
"""

import os
import sys
import time
import warnings

import numpy as np
import pandas as pd

from territorial_chains import add_indicators, weighted_share, weighted_mean, hellinger
from territorial_chains.generators import (MatchingGenerator, BayesNetGenerator, AutoregressiveGenerator, VAEGenerator,
                                           GANGenerator, ATTRIBUTES)

URBAN = ["central_city", "suburb", "isolated_city", "none"]
DEFAULT = ["sex", "any_cars", "age_class", "socioprofessional_class", "departement_id"]
NO_TERRITORY = [a for a in ATTRIBUTES if a != "urban_type"]
TOP_K, REPLICATES = 25, 4


def methods(eqasim_path, seed):
    return {
        "matching_default": lambda: MatchingGenerator(eqasim_path, DEFAULT),
        "matching_urban": lambda: MatchingGenerator(eqasim_path, ["urban_type"] + DEFAULT),
        "bayesnet_learned": lambda: BayesNetGenerator(seed=seed),
        "bayesnet_territory": lambda: BayesNetGenerator(required_edges=[("urban_type", "mobile")], seed=seed),
        "autoregressive_blind": lambda: AutoregressiveGenerator(attributes=NO_TERRITORY, seed=seed),
        "autoregressive_territory": lambda: AutoregressiveGenerator(attributes=ATTRIBUTES, seed=seed),
        "vae_blind": lambda: VAEGenerator(attributes=NO_TERRITORY, seed=seed),
        "vae_territory": lambda: VAEGenerator(attributes=ATTRIBUTES, seed=seed),
        "gan_blind": lambda: GANGenerator(attributes=NO_TERRITORY, seed=seed),
        "gan_territory": lambda: GANGenerator(attributes=ATTRIBUTES, seed=seed),
    }


def score(generated, observed, classes, known):
    """Rows of metrics, one per urban type plus 'all'."""
    def pooled(frame):
        return frame.assign(klass=frame["chain"].where(frame["chain"].isin(classes), "__other__"))
    gen, obs = pooled(add_indicators(generated)), pooled(observed)
    rows = []
    for urban in URBAN + ["all"]:
        g = gen if urban == "all" else gen[gen["urban_type"] == urban]
        o = obs if urban == "all" else obs[obs["urban_type"] == urban]
        gm, om = g[~g["immobile"]], o[~o["immobile"]]
        rows.append({
            "urban_type": urban,
            "hellinger": hellinger(weighted_share(o, "klass", "weight"), weighted_share(g, "klass", "weight")),
            "immobile_generated": weighted_mean(g["immobile"], g["weight"]),
            "immobile_observed": weighted_mean(o["immobile"], o["weight"]),
            "tours_generated": weighted_mean(gm["n_tours"], gm["weight"]),
            "tours_observed": weighted_mean(om["n_tours"], om["weight"]),
            "activities_generated": weighted_mean(gm["n_activities"], gm["weight"]),
            "activities_observed": weighted_mean(om["n_activities"], om["weight"]),
            "novel_share": weighted_mean(~g["chain"].isin(known), g["weight"]),
            "closed_day_generated": weighted_mean(g["closed_day"], g["weight"]),
            "closed_day_observed": weighted_mean(o["closed_day"], o["weight"]),
        })
    return rows


def main(eqasim_path, results_dir="results", splits=5):
    warnings.filterwarnings("ignore")
    results_dir = os.path.abspath(results_dir)
    out = os.path.join(results_dir, "generators")
    os.makedirs(out, exist_ok=True)

    data = pd.read_parquet(os.path.join(results_dir, "chains_entd.parquet"))
    data["sex"] = data["sex"].astype(str)
    records, structures = [], []

    # A run that was interrupted continues after the last split it completed. A split counts
    # as complete only if it holds every method of the current list.
    expected, done = {"floor"} | set(methods(eqasim_path, 0)), set()
    if os.path.exists(os.path.join(out, "benchmark.csv")):
        earlier = pd.read_csv(os.path.join(out, "benchmark.csv"))
        done = {split for split, group in earlier.groupby("split") if set(group["method"]) == expected}
        records = earlier[earlier["split"].isin(done)].to_dict("records")
        kept = pd.read_csv(os.path.join(out, "structures.csv"))
        structures = kept[kept["split"].isin(done)].to_dict("records")

    for split in range(int(splits)):
        if split in done:
            print("split %d  already complete" % split, flush=True)
            continue
        rng = np.random.default_rng(1000 + split)
        is_test = np.zeros(len(data), dtype=bool)
        for urban in URBAN:                                   # stratified by territory
            idx = np.flatnonzero(data["urban_type"] == urban)
            is_test[rng.choice(idx, size=len(idx) // 5, replace=False)] = True
        train, test = data[~is_test].reset_index(drop=True), data[is_test].reset_index(drop=True)

        classes = weighted_share(train, "chain", "weight").sort_values(ascending=False).index[:TOP_K]
        known = set(train["chain"])
        target = pd.concat([test] * REPLICATES, ignore_index=True)

        for row in score(train[["chain", "urban_type", "weight"]], test, classes, known):
            records.append({"split": split, "method": "floor", **row})

        for name, build in methods(eqasim_path, split).items():
            start = time.time()
            generator = build().fit(train)
            chains = generator.sample(target, rng)
            generated = pd.DataFrame({"chain": chains, "urban_type": target["urban_type"], "weight": target["weight"]})
            for row in score(generated, test, classes, known):
                records.append({"split": split, "method": name, "seconds": round(time.time() - start, 1),
                                "latent_kl": getattr(generator, "validation_kl", np.nan), **row})
            if hasattr(generator, "edges"):
                structures.append({"split": split, "method": name,
                                   "edges": "; ".join("%s > %s" % e for e in generator.edges)})
            print("split %d  %-26s %5.1fs" % (split, name, time.time() - start), flush=True)

        pd.DataFrame.from_records(records).to_csv(os.path.join(out, "benchmark.csv"), index=False)
        pd.DataFrame.from_records(structures).to_csv(os.path.join(out, "structures.csv"), index=False)

    frame = pd.DataFrame.from_records(records)
    numeric = [c for c in frame.columns if c not in ("split", "method", "urban_type", "seconds", "latent_kl")]
    summary = frame.groupby(["method", "urban_type"])[numeric].agg(["mean", "min", "max"])
    summary.columns = ["%s_%s" % c for c in summary.columns]
    summary.reset_index().to_csv(os.path.join(out, "summary.csv"), index=False)
    print("written to", out)


if __name__ == "__main__":
    main(*sys.argv[1:4])
