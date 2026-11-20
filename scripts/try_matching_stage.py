"""Try the structured-matching stage on the residents of an existing population.

Usage
-----
    python scripts/try_matching_stage.py <eqasim_path> <data_path> <run_dir> <urban_type_zip> [results_dir] [draws]

The stage ``synthesis.population.matched_structured`` (eqasim_contrib/) replaces
eqasim's matching. Generating a population with it takes a full pipeline run. This
script answers a narrower question without one: given the residents of a population
that already exists, which survey respondent does the stage attach to each of them,
and how do the resulting activity chains compare with the two surveys?

That is enough for every chain indicator, because in eqasim the chain of a resident
is the chain of the attached respondent. Distances and the simulation are not
covered: they need the rest of the pipeline.

How it works: eqasim's ``data`` and ``synthesis`` packages are copied to a scratch
folder, the stage is added, and four small stand-in stages hand it the residents
and home communes of ``run_dir``, the urban type of every commune and the study
area. The survey is read by eqasim's own stages, and the stage runs under synpp as
it would in the pipeline. The regional-survey patch is applied to the scratch copy
only. Run this in the eqasim-france environment (it needs synpp and numba).

``results/chains_entd.parquet`` and ``results/chains_edgt_44.parquet`` must exist
(written by survey_contrasts.py and regional_reference.py).

Outputs, in ``results/structured/``
-----------------------------------
by_draw.csv   one row per survey used as source, draw, reference survey and urban type:
              Hellinger distance, share staying home, tours per mobile person
summary.csv   mean, minimum and maximum over the draws
draws.csv     per source and draw: weight of the national prior selected by
              cross-validation, share of respondents from the study area, share of
              residents matched on every attribute
"""

import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap

import pandas as pd

from territorial_chains import add_indicators, stratified_fidelity, hellinger

import evaluate_population as scoring

HERE = os.path.dirname(os.path.abspath(__file__))
CONTRIB = os.path.join(HERE, "..", "eqasim_contrib")
STAGE = "synthesis.population.matched_structured"
SEEDS = [1234, 2234, 3234, 4234, 5234]
DEPARTEMENT = "44"

STAND_INS = {
    "synthesis/population/sampled.py": """
        import pandas as pd
        def configure(context): context.config("stand_in_path")
        def execute(context): return pd.read_parquet(context.config("stand_in_path") + "/residents.parquet")
    """,
    "synthesis/population/spatial/home/zones.py": """
        import pandas as pd
        def configure(context): context.config("stand_in_path")
        def execute(context): return pd.read_parquet(context.config("stand_in_path") + "/homes.parquet")
    """,
    "data/spatial/urban_type.py": """
        import pandas as pd
        def configure(context): context.config("stand_in_path")
        def execute(context): return pd.read_parquet(context.config("stand_in_path") + "/urban_types.parquet")
    """,
    "data/spatial/codes.py": """
        import pandas as pd
        def configure(context): context.config("stand_in_path")
        def execute(context): return pd.DataFrame({"departement_id": ["%s"]})
    """ % DEPARTEMENT,
}


def one(run_dir, suffix):
    path = scoring._one(run_dir, suffix)
    if path is None:
        raise FileNotFoundError("No *_%s in %s" % (suffix, run_dir))
    return path


def prepare(eqasim_path, run_dir, urban_types, scratch):
    """Scratch copy of eqasim with the stage, the stand-ins and their tables."""
    tree, tables = os.path.join(scratch, "tree"), os.path.join(scratch, "tables")
    os.makedirs(tables)
    for package in ("data", "synthesis"):
        shutil.copytree(os.path.join(eqasim_path, package), os.path.join(tree, package),
                        ignore=shutil.ignore_patterns("__pycache__"))

    patch = os.path.abspath(os.path.join(CONTRIB, "patches", "edgt_44_urban_type.patch"))
    if subprocess.run(["git", "apply", "--check", patch], cwd=tree, capture_output=True).returncode == 0:
        subprocess.run(["git", "apply", patch], cwd=tree, check=True)

    shutil.copy(os.path.join(CONTRIB, "synthesis", "population", "matched_structured.py"),
                os.path.join(tree, "synthesis", "population"))
    for relative, source in STAND_INS.items():
        with open(os.path.join(tree, relative), "w") as f:
            f.write(textwrap.dedent(source))

    persons = pd.read_parquet(one(run_dir, "persons.parquet"))
    households = pd.read_parquet(one(run_dir, "households.parquet"))
    households = households[households["commune_id"].notna()]
    residents = persons[["person_id", "household_id", "age", "sex", "socioprofessional_class"]].merge(
        households[["household_id", "number_of_vehicles", "departement_id", "commune_id"]], on="household_id")
    residents.to_parquet(os.path.join(tables, "residents.parquet"))
    households[["household_id", "commune_id"]].to_parquet(os.path.join(tables, "homes.parquet"))
    urban_types.dropna().to_parquet(os.path.join(tables, "urban_types.parquet"))

    homes = households[["household_id", "commune_id"]].copy()
    homes["commune_id"] = homes["commune_id"].astype(str).str.zfill(5)
    homes = homes.merge(urban_types, on="commune_id", how="left")
    homes["urban_type"] = homes["urban_type"].fillna("none")
    return tree, tables, residents[["person_id", "household_id"]].merge(homes[["household_id", "urban_type"]], on="household_id")


def run_stage(tree, tables, data_path, cache, source, seed):
    """One draw of the stage: the respondent attached to each resident."""
    import synpp

    config = {"data_path": data_path, "regions": [], "departments": [int(DEPARTEMENT)], "hts": source,
              "filter_hts": source != "entd", "use_urban_type": source != "entd", "random_seed": seed,
              "stand_in_path": tables, "processes": 1}
    if source == "edgt_44":                      # the zone table, wherever the download left it
        found = sorted(glob.glob(os.path.join(data_path, "edgt_44_2015", "**", "07_denomination_perimetres_EDGT44*.xls"),
                                 recursive=True))
        if not found:
            raise FileNotFoundError("The zone table of the regional survey is not under %s/edgt_44_2015" % data_path)
        config["edgt_44_zones_path"] = os.path.relpath(found[0], data_path)
    cwd = os.getcwd()
    os.chdir(tree)
    if tree not in sys.path:
        sys.path.insert(0, tree)
    try:
        return synpp.run([{"descriptor": STAGE}], config=config, working_directory=cache)[0]
    finally:
        os.chdir(cwd)


def score(assignment, residents, chains, references, source, draw):
    df = residents.merge(assignment, on="person_id")
    df = df[df["hts_person_id"] >= 0].merge(chains, on="hts_person_id", how="left")
    if df["chain"].isna().any():
        raise RuntimeError("Respondent identifiers do not line up with results/chains_%s.parquet" % source)
    df = add_indicators(df)
    df["weight"], df["euclidean_km"] = 1.0, float("nan")

    rows = []
    for reference, observed in references.items():
        gen, obs = scoring._pool(df, observed)
        fidelity = stratified_fidelity(obs, gen, "chain_class", "urban_type", observed_weight="weight",
                                       generated_weight="weight", metric=hellinger).set_index("urban_type")["distance"]
        table = scoring.indicators(df, observed).pivot(index="urban_type", columns="indicator", values="generated")
        for urban in scoring.URBAN_ORDER:
            rows.append({"source": source, "draw": draw, "reference": reference, "urban_type": urban,
                         "hellinger": float(fidelity[urban]), "immobile_share": float(table.loc[urban, "immobile_share"]),
                         "tours_per_mobile": float(table.loc[urban, "tours_per_mobile"])})
    summary = {"source": source, "draw": draw, "residents": len(df),
               "respondents_from_study_area": float((df["donor_departement"] == DEPARTEMENT).mean()),
               "distinct_respondents": int(df["hts_person_id"].nunique())}
    return rows, summary


def main(eqasim_path, data_path, run_dir, urban_type_zip, results_dir="results", draws=5):
    eqasim_path, data_path, run_dir = (os.path.abspath(p) for p in (eqasim_path, data_path, run_dir))
    results_dir = os.path.abspath(results_dir)
    out = os.path.join(results_dir, "structured")
    os.makedirs(out, exist_ok=True)

    urban_types = scoring.load_urban_types(urban_type_zip)
    references = {key: scoring.load_reference(results_dir, key) for key in ("entd", "edgt_44")}
    chains = {key: pd.read_parquet(os.path.join(results_dir, "chains_%s.parquet" % key))[
        ["person_id", "chain", "departement_id"]].rename(columns={"person_id": "hts_person_id", "departement_id": "donor_departement"})
        for key in ("entd", "edgt_44")}

    rows, summaries = [], []
    with tempfile.TemporaryDirectory() as scratch:
        tree, tables, residents = prepare(eqasim_path, run_dir, urban_types, scratch)
        cache = os.path.join(scratch, "cache")
        os.makedirs(cache)
        for source in ("entd", "edgt_44"):
            for draw, seed in enumerate(SEEDS[:int(draws)], start=1):
                log = os.path.join(scratch, "stage.log")
                sys.stdout.flush()
                with open(log, "w") as f:                        # the stage prints what it selected
                    stdout = os.dup(1)
                    os.dup2(f.fileno(), 1)
                    try:
                        assignment = run_stage(tree, tables, data_path, cache, source, seed)
                    finally:
                        sys.stdout.flush()
                        os.dup2(stdout, 1)
                        os.close(stdout)
                printed = open(log).read()
                new_rows, summary = score(assignment, residents, chains[source], references, source, draw)
                summary.update(read_log(printed))
                rows += new_rows
                summaries.append(summary)
                print("%s, draw %d: prior weight %s, matched on every attribute %.1f%%" % (
                    source, draw, summary.get("prior_strength", "none"), 100 * summary.get("matched_all_attributes", float("nan"))),
                    flush=True)

    by_draw = pd.DataFrame(rows)
    by_draw.to_csv(os.path.join(out, "by_draw.csv"), index=False, float_format="%.6f")
    keys = ["source", "reference", "urban_type"]
    summary = by_draw.groupby(keys, sort=False)[["hellinger", "immobile_share", "tours_per_mobile"]].agg(["mean", "min", "max"])
    summary.columns = ["%s_%s" % c for c in summary.columns]
    summary.reset_index().to_csv(os.path.join(out, "summary.csv"), index=False, float_format="%.6f")
    pd.DataFrame(summaries).to_csv(os.path.join(out, "draws.csv"), index=False, float_format="%.6f")
    print("written to", out)


def read_log(text):
    """Prior weight and matching levels, as the stage prints them (like eqasim's own matching)."""
    found = {}
    prior = re.search(r"weight of the national prior: ([\d.]+)", text)
    if prior:
        found["prior_strength"] = float(prior.group(1))
    levels = re.findall(r"^(\d+) matched levels: \d+ ([\d.]+)%", text, flags=re.M)
    if levels:
        found["matched_all_attributes"] = float(levels[-1][1]) / 100.0
        found["matched_all_but_last"] = float(levels[-2][1]) / 100.0
    return found


if __name__ == "__main__":
    main(*sys.argv[1:7])
