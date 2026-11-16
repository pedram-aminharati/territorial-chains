"""Toy experiment: does eqasim's statistical matching flatten territorial contrast?

THIS USES SIMULATED DATA. It says nothing about real French mobility. Its only
purpose is to show the mechanism and to check that the contrast-retention
indicator detects it, before any real survey is involved.

Set-up
------
A toy "survey" in which chain behaviour depends on territory (urban / rural)
and on age class. Rural respondents are scarce, as in a national survey cut
down to one departement. The toy "census" is large and half rural.

The script then calls eqasim's own ``statistical_matching`` function, unchanged,
with the territory attribute either absent, last in the attribute list
(where eqasim puts ``departement_id``), or first, and reports how much of the
urban/rural contrast survives in the matched population.

Usage:  python scripts/demo_matching_flattening.py /path/to/eqasim-france
"""

import sys

import numpy as np
import pandas as pd

from territorial_chains import contrast_retention, stratified_fidelity

CHAINS = ["h", "hwh", "hwshlh", "hlh", "hsh"]
# P(chain | territory, age_class): rural days are simpler, more car-commute-only.
P = {
    ("urban", 0): [0.08, 0.30, 0.32, 0.18, 0.12],
    ("urban", 1): [0.22, 0.10, 0.10, 0.28, 0.30],
    ("rural", 0): [0.12, 0.58, 0.06, 0.10, 0.14],
    ("rural", 1): [0.40, 0.08, 0.02, 0.20, 0.30],
}


def simulate(n_urban, n_rural, seed, id_offset=0):
    rng = np.random.default_rng(seed)
    rows = []
    for territory, n in (("urban", n_urban), ("rural", n_rural)):
        age = rng.integers(0, 2, n)
        sex = rng.integers(0, 2, n)
        chain = np.array([rng.choice(CHAINS, p=P[(territory, a)]) for a in age])
        rows.append(pd.DataFrame({"territory": territory, "age_class": age, "sex": sex, "chain": chain}))
    df = pd.concat(rows, ignore_index=True)
    df["person_id"] = np.arange(len(df)) + id_offset
    df["person_weight"] = rng.uniform(0.5, 1.5, len(df))
    return df


class _Progress:
    def update(self, n):
        pass


def main(eqasim_path, n_rural_donors=(400, 60, 25), minimum_observations=20):
    sys.path.insert(0, eqasim_path)
    from synthesis.population.matched import statistical_matching   # eqasim's code, unchanged

    census = simulate(20000, 20000, seed=1)
    reference = simulate(20000, 20000, seed=2, id_offset=10**6)     # large "truth" sample

    variants = {
        "no territory":            ["sex", "age_class"],
        "territory last (eqasim)": ["sex", "age_class", "territory"],
        "territory first":         ["territory", "sex", "age_class"],
    }

    records = []
    for n_rural in n_rural_donors:
        survey = simulate(3000, n_rural, seed=3, id_offset=2 * 10**6)
        source = survey.rename(columns={"person_id": "hts_person_id"})

        for label, columns in variants.items():
            assignment, levels = statistical_matching(
                _Progress(), source, "hts_person_id", "person_weight",
                census.copy(), "person_id", list(columns),
                random_seed=0, minimum_observations=minimum_observations)

            matched = assignment.merge(census[["person_id", "territory"]], on="person_id").merge(
                source[["hts_person_id", "chain"]], on="hts_person_id")

            retention = contrast_retention(reference, matched, "chain", "territory")["retention"].iloc[0]
            fidelity = stratified_fidelity(reference, matched, "chain", "territory").set_index("territory")["distance"]
            full_match = float(np.mean(levels == len(columns)))

            records.append({
                "rural donors": n_rural, "matching": label,
                "contrast retained": round(retention, 2),
                "Hellinger urban": round(fidelity["urban"], 3),
                "Hellinger rural": round(fidelity["rural"], 3),
                "matched on all attributes": "%.0f%%" % (100 * full_match),
            })

    table = pd.DataFrame.from_records(records)
    print(table.to_string(index=False))
    return table


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "../code")
