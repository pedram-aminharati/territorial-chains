"""Build the project page (docs/index.html) from the result tables.

Usage:  python site/build_site.py [results_dir] [repo_url]

The page is a single self-contained HTML file: data is inlined as JSON and the
charts are drawn in the browser with plain SVG, so it works offline and on
GitHub Pages without any build step or external library.
"""

import json
import os
import sys
from datetime import date

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

URBAN = ["central_city", "suburb", "isolated_city", "none"]
URBAN_LABEL = {"central_city": "Central city", "suburb": "Suburb",
               "isolated_city": "Isolated city", "none": "Rural"}

VARIANTS = [
    # key, letter, survey, short description
    ("A_entd_local",    "A", "entd", "Default attributes, local donors"),
    ("B_entd_national", "B", "entd", "Default attributes, national donors"),
    ("C_entd_urban",    "C", "entd", "Urban type added, national donors"),
    ("D_emp_national",  "D", "emp",  "Default attributes, national donors"),
    ("E_emp_urban",     "E", "emp",  "Urban type added, national donors"),
]


GENERATORS = [
    # key, display name, family, sees territory
    ("matching_default",         "Matching, default attributes",    "Statistical matching", False),
    ("matching_urban",           "Matching, urban type first",      "Statistical matching", True),
    ("bayesnet_learned",         "Bayesian network, learned graph", "Bayesian network",     False),
    ("bayesnet_territory",       "Bayesian network, territory edge", "Bayesian network",    True),
    ("autoregressive_blind",     "Transformer, without territory",  "Autoregressive",       False),
    ("autoregressive_territory", "Transformer, with territory",     "Autoregressive",       True),
    ("vae_blind",                "Autoencoder, without territory",  "Variational autoencoder", False),
    ("vae_territory",            "Autoencoder, with territory",     "Variational autoencoder", True),
    ("gan_blind",                "GAN, without territory",          "Adversarial",          False),
    ("gan_territory",            "GAN, with territory",             "Adversarial",          True),
]


GAPS = ["immobile_share", "tours_per_mobile", "euclidean_km_per_mobile"]


def by_urban(frame, value, key="urban_type"):
    indexed = frame.set_index(key)[value]
    return [float(indexed[u]) for u in URBAN]


def collect(results):
    read = lambda *parts: pd.read_csv(os.path.join(results, *parts))
    data = {
        "territories": [{"key": u, "label": URBAN_LABEL[u]} for u in URBAN],
        "variants": [], "donors": {}, "fidelity": {}, "matching": {},
        "indicators": {}, "observed": {}, "top_chains": {},
    }

    persons = None
    for key, letter, survey, description in VARIANTS:
        folder = os.path.join(results, key)
        if not os.path.isdir(folder):
            continue
        donors = read(key, "donor_territory.csv")
        rows = donors[donors["urban_type"].isin(URBAN)].set_index("urban_type")
        overall = donors[donors["urban_type"] == "all"].iloc[0]
        persons = max(persons or 0, int(overall["persons"]))
        data["donors"][letter] = {
            "matrix": [[float(rows.loc[home, "donor_%s" % donor]) for donor in URBAN] for home in URBAN],
            "same": [float(rows.loc[home, "donor_same_urban_type"]) for home in URBAN],
            "local": float(overall["donor_from_loire_atlantique"]),
            "same_all": float(overall["donor_same_urban_type"]),
        }
        data["fidelity"][letter] = by_urban(read(key, "fidelity.csv"), "distance")

        levels = read(key, "matching_levels.csv").sort_values("attributes_matched")
        data["matching"][letter] = {
            "attributes": int(levels["attributes_matched"].max()),
            "all": float(levels["share"].iloc[-1]),
            "all_but_last": float(levels["share"].iloc[-2]),
        }

        indicators = read(key, "indicators.csv")
        data["indicators"][letter] = {
            name: by_urban(group, "generated") for name, group in indicators.groupby("indicator")}
        data["observed"].setdefault(survey, {
            name: by_urban(group, "observed") for name, group in indicators.groupby("indicator")})

        chains = read(key, "top_chains.csv")
        data["top_chains"][letter] = {
            u: chains[chains["urban_type"] == u][["chain", "observed", "generated"]].to_dict("records")
            for u in URBAN}

        data["variants"].append({"key": key, "id": letter, "survey": survey.upper(), "label": description})

    # --- surveys
    survey_ind = read("indicators.csv")
    data["survey"] = {}
    for survey, group in survey_ind.groupby("survey"):
        data["survey"][survey] = {
            name: [[float(r.estimate), float(r.ci_lower), float(r.ci_upper)]
                   for r in sub.set_index("urban_type").loc[URBAN].itertuples()]
            for name, sub in group.groupby("indicator")}

    donors = read("donors.csv")
    data["survey_donors"] = donors.to_dict("records")

    thin = read("thin_cells.csv")
    data["thin"] = thin[thin["urban_type"] == "all"][["survey", "donor_pool", "share_in_thin_cells"]].to_dict("records")
    data["thin_isolated"] = thin[thin["urban_type"] == "isolated_city"][["survey", "donor_pool", "share_in_thin_cells"]].to_dict("records")

    emp = read("emp_day_weights.csv").set_index("urban_type")
    data["emp_weights"] = {
        "person": float(emp.loc["all", "immobile_person_weight"]),
        "day": float(emp.loc["all", "immobile_day_weight"]),
        "day_by_urban": [float(emp.loc[u, "immobile_day_weight"]) for u in URBAN],
        "no_diary": int(emp.loc["all", "no_diary_all_week"]),
        "respondents": int(emp.loc["all", "respondents"]),
    }

    contrast = read("contrast.csv")
    data["survey_contrast"] = contrast.to_dict("records")

    # --- generator benchmark (optional: present once benchmark_generators.py has run)
    bench_path = os.path.join(results, "generators", "benchmark.csv")
    if os.path.exists(bench_path):
        bench = pd.read_csv(bench_path)

        def stat(method, urban, column):
            v = bench[(bench["method"] == method) & (bench["urban_type"] == urban)][column]
            return [float(v.mean()), float(v.min()), float(v.max())]

        data["generators"] = {
            "splits": int(bench["split"].nunique()),
            "methods": [{
                "key": key, "name": name, "family": family, "aware": aware,
                "rural_home": stat(key, "none", "immobile_generated"),
                "rural_error": stat(key, "none", "hellinger"),
                "all_error": stat(key, "all", "hellinger"),
                "novel": stat(key, "all", "novel_share")[0],
            } for key, name, family, aware in GENERATORS if (bench["method"] == key).any()],
            "observed_rural_home": stat("floor", "none", "immobile_observed")[0],
            "floor_rural": stat("floor", "none", "hellinger")[0],
            "floor_all": stat("floor", "all", "hellinger")[0],
        }
        structures = pd.read_csv(os.path.join(results, "generators", "structures.csv"))
        learned = structures[structures["method"] == "bayesnet_learned"]["edges"]
        data["generators"]["territory_edges_found"] = int(learned.str.contains("urban_type").sum())

    # --- MATSim runs (optional: present once evaluate_simulation.py has run on both variants)
    sims = {}
    for letter, key in (("A", "A_entd_local_sim"), ("C", "C_entd_urban_sim")):
        folder = os.path.join(results, key)
        if not os.path.exists(os.path.join(folder, "sim_travel.csv")):
            continue
        travel = read(key, "sim_travel.csv").set_index("urban_type").loc[URBAN + ["all"]]
        modes = read(key, "sim_modes.csv").pivot(index="urban_type", columns="mode", values="trip_share").loc[URBAN + ["all"]]
        entry = {"travel": {column: [float(v) for v in travel[column]] for column in travel.columns},
                 "modes": {mode: [float(v) for v in modes[mode]] for mode in modes.columns}}
        convergence_path = os.path.join(folder, "sim_convergence.csv")
        if os.path.exists(convergence_path):
            entry["iterations"] = int(pd.read_csv(convergence_path)["iteration"].max()) + 1
        sims[letter] = entry
    if len(sims) == 2:
        data["simulation"] = sims

    # --- map and matching explorer (optional: present once export_page_data.py has run)
    units_path = os.path.join(results, "map", "units.csv")
    if os.path.exists(units_path):
        data["map"] = collect_map(results, units_path)
    cells_path = os.path.join(results, "explorer_cells.csv")
    if os.path.exists(cells_path):
        cells = pd.read_csv(cells_path)
        data["explorer"] = {
            # sex, car, age class, occupation, in departement, in A's pool, urban type, respondents, weight, weighted stay-home, weighted trips
            "cells": [[int(r.sex == "male"), int(r.any_cars), int(r.age_class), int(r.socioprofessional_class),
                       int(r.departement), int(r.local), URBAN.index(r.urban_type), int(r.respondents),
                       float(r.weight), float(r.weighted_immobile), float(r.weighted_trips)] for r in cells.itertuples()],
            "pool": {"all": int(cells["respondents"].sum()),
                     "departement": int(cells.loc[cells["departement"], "respondents"].sum()),
                     "local": int(cells.loc[cells["local"], "respondents"].sum())},
            "minimum": 20,
        }

    # --- repeats over random seeds (optional: present once summarise_seeds.py has run)
    seeds_path = os.path.join(results, "seeds", "summary.csv")
    if os.path.exists(seeds_path):
        summary = pd.read_csv(seeds_path)
        diff = pd.read_csv(os.path.join(results, "seeds", "differences.csv"))
        keep = ["immobile_share", "hellinger", "trips_per_resident", "car_km_per_resident"]
        if (summary["quantity"] == "hellinger_edgt").any():
            keep.append("hellinger_edgt")
        stats = {}
        for quantity in keep:
            sub = summary[summary["quantity"] == quantity]
            stats[quantity] = {
                variant: [[float(r.mean), float(r.minimum), float(r.maximum)]
                          for r in group.set_index("urban_type").loc[URBAN].itertuples()]
                for variant, group in sub.groupby("variant")}
        rows = {}
        for quantity in keep + ["travelling_share", "km_per_trip", "minutes_per_resident", "trip_share_pt"]:
            sub = diff[diff["quantity"] == quantity].set_index("urban_type")
            order = URBAN + (["all"] if "all" in sub.index else [])
            rows[quantity] = [[float(sub.loc[u, c]) for c in ("difference", "difference_min", "difference_max",
                                                              "relative", "relative_min", "relative_max")]
                              + [bool(sub.loc[u, "same_sign_in_every_seed"])] for u in order]
        count = lambda source: int(summary[summary["source"] == source]["seeds"].max())
        data["seeds"] = {"stats": stats, "diff": rows, "population": count("population"), "simulation": count("simulation")}

    # --- regional survey as a second reference (optional: present once regional_reference.py has run)
    local_path = os.path.join(results, "edgt", "stay_home.csv")
    if os.path.exists(local_path):
        stay = pd.read_csv(local_path)
        home = {sample: [[float(r.estimate), float(r.ci_lower), float(r.ci_upper), int(r.respondents)]
                         for r in group.set_index("urban_type").loc[URBAN + ["all"]].itertuples()]
                for sample, group in stay.groupby("sample")}
        edgt_ind = pd.read_csv(os.path.join(results, "edgt", "indicators.csv"))
        local = {"home": home, "fidelity": {}, "indicators": {
            name: by_urban(group, "estimate") for name, group in edgt_ind.groupby("indicator")}}
        local["indicators"]["euclidean_km_per_mobile"] = [v / 1.3 for v in local["indicators"]["distance_km_per_mobile"]]
        for key, letter, _, _ in VARIANTS:
            scored = os.path.join(results, key + "__vs_edgt_44", "fidelity.csv")
            if os.path.exists(scored):
                local["fidelity"][letter] = by_urban(pd.read_csv(scored), "distance")
        data["local"] = local

    # --- contrast between territories: the rural minus central-city gap, generated against observed
    generated, observed, regional = {}, {}, {}
    for key, letter, survey, _ in VARIANTS:
        folders = [key]
        for n in range(2, 6):                                 # seed repeats, simulated or not
            found = [f for f in ("%s_seed%d_sim" % (key, n), "%s_seed%d" % (key, n))
                     if os.path.exists(os.path.join(results, f, "gaps.csv"))]
            folders += found[:1]
        tables = [read(f, "gaps.csv").set_index("indicator") for f in folders
                  if os.path.exists(os.path.join(results, f, "gaps.csv"))]
        if not tables:
            continue
        observed[survey] = {name: float(tables[0].loc[name, "observed_gap"]) for name in GAPS}
        values = {name: [float(t.loc[name, "generated_gap"]) for t in tables] for name in GAPS}
        generated[letter] = {name: [sum(v) / len(v), min(v), max(v), len(v)] for name, v in values.items()}
        scored = os.path.join(results, key + "__vs_edgt_44", "gaps.csv")
        if os.path.exists(scored) and not regional:
            table = pd.read_csv(scored).set_index("indicator")
            regional = {name: float(table.loc[name, "observed_gap"]) for name in GAPS}
    if generated:
        data["gaps"] = {"indicators": GAPS, "generated": generated, "observed": observed, "regional": regional}

    # --- structured matching tried on existing residents (optional: scripts/try_matching_stage.py)
    structured_path = os.path.join(results, "structured", "summary.csv")
    if os.path.exists(structured_path):
        summary = pd.read_csv(structured_path)
        draws = pd.read_csv(os.path.join(results, "structured", "draws.csv"))
        scores = {}
        for (source, reference), group in summary.groupby(["source", "reference"]):
            rows = group.set_index("urban_type").loc[URBAN]
            scores.setdefault(source, {})[reference] = {
                quantity: [[float(r["%s_%s" % (quantity, s)]) for s in ("mean", "min", "max")] for _, r in rows.iterrows()]
                for quantity in ("hellinger", "immobile_share", "tours_per_mobile")}
        national = draws[draws["source"] == "entd"]
        data["structured"] = {
            "scores": scores, "draws": int(len(national)),
            "prior": sorted({float(v) for v in national["prior_strength"]}),
            "local": float(national["respondents_from_study_area"].mean()),
            "matched_all": float(national["matched_all_attributes"].mean()),
        }

    data["meta"] = {"persons": persons, "built": date.today().strftime("%d %B %Y"), "eqasim": "1.5.0"}
    return data


MAP_METRICS = {
    # key: (column, rounding step of the colour scale)
    "immobile": ("immobile_share", 0.01),
    "donor": ("donor_same_share", None),
    "trips": ("trips_per_resident", 0.1),
    "carkm": ("car_km_per_resident", 1.0),
}
SMALL_SAMPLE = 100


def collect_map(results, units_path):
    import math

    units = pd.read_csv(units_path, dtype={"unit_id": str, "epci_id": str})
    with open(os.path.join(results, "map", "shapes.json"), encoding="utf-8") as f:
        shapes = json.load(f)

    out = {"w": shapes["width"], "h": shapes["height"], "communes": shapes["communes"], "epci": shapes["epci"],
           "towns": shapes["towns"], "small": SMALL_SAMPLE, "units": {}, "domains": {}}
    wide = {}
    for level in ("commune", "epci"):
        frame = units[units["level"] == level]
        a, c = (frame[frame["variant"] == v].set_index("unit_id") for v in ("A", "C"))
        wide[level] = (a, c)
        out["units"][level] = {
            unit: {"name": a.loc[unit, "name"], "epci": a.loc[unit, "epci_id"],
                   "u": URBAN.index(a.loc[unit, "urban_type"]) if level == "commune" else -1,
                   "n": [int(a.loc[unit, "residents"]), int(c.loc[unit, "residents"])],
                   "v": {key: [round(float(a.loc[unit, column]), 4), round(float(c.loc[unit, column]), 4)]
                         for key, (column, _) in MAP_METRICS.items()}}
            for unit in a.index}

    # One colour scale per measure, shared by both variants and both geographies, set on the
    # communes with enough sampled residents so that a hamlet cannot stretch it.
    a, c = wide["commune"]
    enough = a["residents"] >= SMALL_SAMPLE
    for key, (column, step) in MAP_METRICS.items():
        if step is None:
            out["domains"][key] = [0.0, 1.0, 1.0]
            continue
        values = pd.concat([a.loc[enough, column], c.loc[enough, column]])
        change = (c.loc[enough, column] - a.loc[enough, column]).abs()
        out["domains"][key] = [round(math.floor(values.quantile(0.05) / step) * step, 4),
                               round(math.ceil(values.quantile(0.95) / step) * step, 4),
                               round(math.ceil(change.quantile(0.95) / step) * step, 4)]
    return out


def narrative(data):
    """Numbers quoted in the text, formatted once so text and charts cannot disagree."""
    pct = lambda x, d=0: ("%." + str(d) + "f%%") % (100 * x)
    d, obs = data["donors"], data["observed"]["entd"]
    ind = data["indicators"]
    donors_local = {s: next(r["respondents"] for r in data["survey_donors"]
                            if r["survey"] == s and r["area"].startswith("Loire") and r["urban_type"] == "all")
                    for s in ("entd", "emp")}
    values = {
        "persons": "{:,}".format(data["meta"]["persons"]),
        "built": data["meta"]["built"],
        "rural_same_A": pct(d["A"]["same"][3]),
        "rural_same_B": pct(d["B"]["same"][3]),
        "rural_same_C": pct(d["C"]["same"][3]),
        "isolated_same_C": pct(d["C"]["same"][2]),
        "isolated_rural_C": pct(d["C"]["matrix"][2][3]),
        "local_B": pct(d["B"]["local"]),
        "local_C": pct(d["C"]["local"]),
        "obs_rural_home": pct(obs["immobile_share"][3], 1),
        "obs_suburb_home": pct(obs["immobile_share"][1], 1),
        "A_rural_home": pct(ind["A"]["immobile_share"][3], 1),
        "C_rural_home": pct(ind["C"]["immobile_share"][3], 1),
        "fid_rural_A": "%.3f" % data["fidelity"]["A"][3],
        "fid_rural_C": "%.3f" % data["fidelity"]["C"][3],
        "emp_person": pct(data["emp_weights"]["person"], 1),
        "emp_day": pct(data["emp_weights"]["day"], 1),
        "emp_no_diary": str(data["emp_weights"]["no_diary"]),
        "D_home": pct(sum(ind["D"]["immobile_share"]) / 4, 0),
        "donors_entd": "{:,}".format(donors_local["entd"]),
        "donors_emp": "{:,}".format(donors_local["emp"]),
        "km_obs_central": "%.0f" % obs["euclidean_km_per_mobile"][0],
        "km_obs_rural": "%.0f" % obs["euclidean_km_per_mobile"][3],
        "km_A_central": "%.0f" % ind["A"]["euclidean_km_per_mobile"][0],
        "km_A_rural": "%.0f" % ind["A"]["euclidean_km_per_mobile"][3],
    }
    g = data.get("generators")
    if g:
        m = {x["key"]: x for x in g["methods"]}
        # The GAN is reported apart: it misses the level of staying home whatever it is given.
        blind = [x["rural_home"][0] for x in g["methods"] if not x["aware"] and not x["key"].startswith("gan")]
        aware = [x["rural_home"][0] for x in g["methods"] if x["aware"] and not x["key"].startswith("gan")]
        words = {2: "two", 3: "three", 4: "four", 5: "five"}
        gan = {k: m.get("gan_" + k) for k in ("blind", "territory")}
        values.update({key: "" for key in ("gen_gan_blind", "gen_gan_aware", "gen_gan_rural", "gen_gan_all", "gen_gan_novel")})
        if gan["blind"] and gan["territory"]:
            values.update({
                "gen_gan_blind": pct(gan["blind"]["rural_home"][0], 1), "gen_gan_aware": pct(gan["territory"]["rural_home"][0], 1),
                "gen_gan_rural": "%.3f" % gan["territory"]["rural_error"][0], "gen_gan_all": "%.3f" % gan["territory"]["all_error"][0],
                "gen_gan_novel": pct(gan["territory"]["novel"], 0),
            })
        values.update({
            "gen_splits": str(g["splits"]),
            "gen_obs_rural": pct(g["observed_rural_home"], 1),
            "gen_blind_count": words.get(len(blind), str(len(blind))),
            "gen_blind_rural": pct(sum(blind) / len(blind), 1),
            "gen_aware_low": pct(min(aware), 1), "gen_aware_high": pct(max(aware), 1),
            "gen_novel": pct(m["autoregressive_territory"]["novel"], 0),
            "gen_vae_novel": pct(m["vae_territory"]["novel"], 0),
            "gen_match_rural": "%.3f" % m["matching_urban"]["rural_error"][0],
            "gen_bn_rural": "%.3f" % m["bayesnet_territory"]["rural_error"][0],
            "gen_vae_rural": "%.3f" % m["vae_territory"]["rural_error"][0],
            "gen_ar_rural": "%.3f" % m["autoregressive_territory"]["rural_error"][0],
            "gen_edges": str(g["territory_edges_found"]),
        })
    sim = data.get("simulation")
    if sim:
        change = lambda column, i: sim["C"]["travel"][column][i] / sim["A"]["travel"][column][i] - 1.0
        signed = lambda x, d=0: (("%+." + str(d) + "f%%") % (100 * x)).replace("-", "\u2212")
        fewer = lambda x: "%.0f%% %s" % (100 * abs(x), "fewer" if x < 0 else "more")
        longer = lambda x: "%.0f%% %s" % (100 * abs(x), "shorter" if x < 0 else "longer")
        values.update({
            "sim_iter_A": str(sim["A"].get("iterations", "")),
            "sim_iter_C": str(sim["C"].get("iterations", "")),
            "sim_trips_rural": fewer(change("trips_per_resident", 3)),
            "sim_trips_central": fewer(change("trips_per_resident", 0)),
            "sim_carkm_rural": signed(change("car_km_per_resident", 3), 1),
            "sim_carkm_all": signed(change("car_km_per_resident", 4), 1),
            "sim_triplen_rural": longer(change("km_per_trip", 3)),
            "sim_carkm_max": "%.0f%%" % (100 * max(abs(change("car_km_per_resident", i)) for i in range(5)) + 0.5),
        })
    m = data.get("map")
    if m:
        groups, communes = m["units"]["epci"], m["units"]["commune"]
        span = lambda i: (min(groups.values(), key=lambda u: u["v"]["immobile"][i]),
                          max(groups.values(), key=lambda u: u["v"]["immobile"][i]))
        (a_low, a_high), (c_low, c_high) = span(0), span(1)
        blind = [u for u in communes.values() if u["v"]["donor"][1] < 0.05]
        residents_c = sum(u["n"][1] for u in communes.values())
        values.update({
            "map_groups": str(len(groups)), "map_communes": str(len(communes)),
            "map_A_low": pct(a_low["v"]["immobile"][0], 1), "map_A_high": pct(a_high["v"]["immobile"][0], 1),
            "map_C_low": pct(c_low["v"]["immobile"][1], 1), "map_C_low_name": c_low["name"],
            "map_C_high": pct(c_high["v"]["immobile"][1], 1), "map_C_high_name": c_high["name"],
            "map_blind": str(len(blind)),
            "map_blind_share": pct(sum(u["n"][1] for u in blind) / residents_c),
            "map_blind_urban": str(sum(1 for u in blind if URBAN[u["u"]] != "none")),
            "map_small": str(sum(1 for u in communes.values() if u["n"][0] < m["small"])),
            "map_small_n": str(m["small"]),
        })
    sd = data.get("seeds")
    if sd:
        minus = lambda text: text.replace("-", "\u2212")
        rng = lambda v, d=1: "%s to %s" % (pct(v[1], d), pct(v[2], d))
        rel = lambda row, d=1: minus(("%+." + str(d) + "f%%") % (100 * row[3]))
        rel_rng = lambda row, d=1: minus(("%+." + str(d) + "f%% to %+." + str(d) + "f%%") % tuple(
            sorted((100 * row[4], 100 * row[5]), key=abs)))
        home, car, trips = sd["stats"]["immobile_share"], sd["diff"]["car_km_per_resident"], sd["diff"]["trips_per_resident"]
        values.update({
            "seed_pop": str(sd["population"]), "seed_sim": str(sd["simulation"]),
            "seed_A_rural": pct(home["A"][3][0], 1), "seed_A_rural_range": rng(home["A"][3]),
            "seed_C_rural": pct(home["C"][3][0], 1), "seed_C_rural_range": rng(home["C"][3]),
            "seed_trips_rural": "%.0f%% fewer" % (-100 * trips[3][3]),
            "seed_trips_rural_range": "%.1f%% to %.1f%% fewer" % tuple(sorted((-100 * trips[3][4], -100 * trips[3][5]))),
            "seed_car_central": rel(car[0]), "seed_car_suburb": rel(car[1]), "seed_car_isolated": rel(car[2]),
            "seed_car_rural": rel(car[3]), "seed_car_rural_range": rel_rng(car[3]),
            "seed_car_all": rel(car[4]), "seed_car_all_range": rel_rng(car[4]),
        })
    loc = data.get("local")
    if loc:
        home = loc["home"]
        ci = lambda v, d=1: "%s to %s" % (pct(v[1], d), pct(v[2], d))
        values.update({
            "loc_respondents": "{:,}".format(home["edgt"][4][3]),
            "loc_home_rural": pct(home["edgt"][3][0], 1), "loc_home_rural_ci": ci(home["edgt"][3]),
            "loc_home_low": pct(min(v[0] for v in home["edgt"][:4]), 1),
            "loc_home_high": pct(max(v[0] for v in home["edgt"][:4]), 1),
            "loc_home_all": pct(home["edgt"][4][0], 1),
            "e44_home_rural": pct(home["entd_44"][3][0], 1), "e44_home_rural_ci": ci(home["entd_44"][3]),
            "e44_rural_n": str(home["entd_44"][3][3]), "e44_home_all": pct(home["entd_44"][4][0], 1),
            "nat_home_all": pct(home["entd"][4][0], 1),
            "loc_fid_rural_A": "%.3f" % loc["fidelity"]["A"][3], "loc_fid_rural_C": "%.3f" % loc["fidelity"]["C"][3],
            "nonlocal_C": pct(1 - d["C"]["local"]),
        })
        if sd and "hellinger_edgt" in sd.get("stats", {}):
            he = sd["stats"]["hellinger_edgt"]
            values.update({"seed_loc_A": "%.3f" % he["A"][3][0], "seed_loc_C": "%.3f" % he["C"][3][0]})
    gp = data.get("gaps")
    gap_keys = ["gap_seeds", "gap_home_nat", "gap_home_reg", "gap_home_C", "gap_tours_nat", "gap_tours_reg",
                "gap_tours_A", "gap_tours_C"]
    values.update({key: "" for key in gap_keys})
    if gp and "entd" in gp["observed"] and gp["regional"] and {"A", "C"} <= set(gp["generated"]):
        minus = lambda text: text.replace("-", "\u2212")
        points = lambda v: minus("%+.1f points" % (100 * v))
        tours = lambda v: minus("%+.2f" % v)
        gen, obs, reg = gp["generated"], gp["observed"]["entd"], gp["regional"]
        values.update({
            "gap_seeds": str(gen["C"]["immobile_share"][3]),
            "gap_home_nat": points(obs["immobile_share"]), "gap_home_reg": points(reg["immobile_share"]),
            "gap_home_C": points(gen["C"]["immobile_share"][0]),
            "gap_tours_nat": tours(obs["tours_per_mobile"]), "gap_tours_reg": tours(reg["tours_per_mobile"]),
            "gap_tours_A": tours(gen["A"]["tours_per_mobile"][0]), "gap_tours_C": tours(gen["C"]["tours_per_mobile"][0]),
        })
    st = data.get("structured")
    st_keys = ["st_draws", "st_prior", "st_home_rural", "st_home_rural_C", "st_regional_low", "st_regional_high",
               "st_local", "st_tours_gap"]
    values.update({key: "" for key in st_keys})
    if st and "entd" in st["scores"]:
        s = st["scores"]["entd"]
        prior = ["%g" % v for v in st["prior"]]
        values.update({
            "st_draws": str(st["draws"]),
            "st_prior": prior[0] if len(prior) == 1 else " or ".join([", ".join(prior[:-1]), prior[-1]]),
            "st_home_rural": pct(s["entd"]["immobile_share"][3][0], 1),
            "st_home_rural_C": pct(ind["C"]["immobile_share"][3], 1),
            "st_local": pct(st["local"], 0),
            "st_tours_gap": ("%+.2f" % (s["entd"]["tours_per_mobile"][3][0] - s["entd"]["tours_per_mobile"][0][0])).replace("-", "\u2212"),
        })
        regional = st["scores"].get("edgt_44", {}).get("edgt_44")
        if regional:
            values.update({"st_regional_low": "%.3f" % min(v[0] for v in regional["hellinger"]),
                           "st_regional_high": "%.3f" % max(v[0] for v in regional["hellinger"])})
    e = data.get("explorer")
    if e:
        values.update({
            "exp_all": "{:,}".format(e["pool"]["all"]),
            "exp_dept": "{:,}".format(e["pool"]["departement"]),
            "exp_local": "{:,}".format(e["pool"]["local"]),
            "exp_dropped": str(e["pool"]["departement"] - e["pool"]["local"]),
        })
    return values


def rounded(value, digits=6):
    """Round every float so that the page does not depend on how a CSV parser reads the last digit."""
    if isinstance(value, float):
        return round(value, digits)
    if isinstance(value, dict):
        return {key: rounded(item, digits) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [rounded(item, digits) for item in value]
    return value


def main(results=None, repo_url="https://github.com/pedram-aminharati/territorial-chains"):
    results = os.path.abspath(results or os.path.join(ROOT, "results"))
    data = collect(results)
    values = narrative(data)
    values["repo"] = repo_url

    html = open(os.path.join(HERE, "template.html"), encoding="utf-8").read()
    for key, value in values.items():
        html = html.replace("{{%s}}" % key, value)
    html = html.replace("/*__DATA__*/null", json.dumps(rounded(data), separators=(",", ":"), ensure_ascii=False))

    missing = [part.split("}}")[0] for part in html.split("{{")[1:]]
    if missing:
        raise RuntimeError("Unfilled placeholders: %s" % sorted(set(missing)))

    out = os.path.join(ROOT, "docs")
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    open(os.path.join(out, ".nojekyll"), "w").close()
    print("wrote", os.path.join(out, "index.html"), "(%d kB)" % (len(html) // 1024))


if __name__ == "__main__":
    main(*sys.argv[1:3])
