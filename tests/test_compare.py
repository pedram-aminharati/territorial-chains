import numpy as np
import pandas as pd
import pytest

from territorial_chains import (
    hellinger, jensen_shannon, stratified_fidelity, contrast_matrix, contrast_retention,
)


def _population(urban, rural, n=4000, seed=0):
    """urban / rural: dict chain -> probability."""
    rng = np.random.default_rng(seed)
    frames = []
    for name, probs in (("urban", urban), ("rural", rural)):
        frames.append(pd.DataFrame({
            "territory": name,
            "chain": rng.choice(list(probs), size=n, p=list(probs.values())),
        }))
    return pd.concat(frames, ignore_index=True)


URBAN = {"hwh": 0.35, "hwshlh": 0.35, "hlh": 0.20, "h": 0.10}
RURAL = {"hwh": 0.60, "hwshlh": 0.05, "hlh": 0.10, "h": 0.25}
POOLED = {k: 0.5 * (URBAN[k] + RURAL[k]) for k in URBAN}


def test_distances_are_zero_for_identical_and_bounded():
    p = pd.Series({"a": 0.5, "b": 0.5})
    q = pd.Series({"c": 1.0})                       # disjoint support
    assert hellinger(p, p) == pytest.approx(0)
    assert jensen_shannon(p, p) == pytest.approx(0)
    assert hellinger(p, q) == pytest.approx(1)
    assert jensen_shannon(p, q) == pytest.approx(1)


def test_contrast_matrix_is_symmetric():
    m = contrast_matrix(_population(URBAN, RURAL), "chain", "territory")
    assert m.loc["urban", "rural"] == pytest.approx(m.loc["rural", "urban"])
    assert m.loc["urban", "urban"] == 0


def test_faithful_generator_retains_contrast():
    observed = _population(URBAN, RURAL, seed=1)
    generated = _population(URBAN, RURAL, seed=2)
    retention = contrast_retention(observed, generated, "chain", "territory")["retention"].iloc[0]
    assert retention == pytest.approx(1.0, abs=0.15)


def test_territory_blind_generator_flattens_contrast():
    """A generator that ignores territory looks fine on average and fails here."""
    observed = _population(URBAN, RURAL, seed=1)
    blind = _population(POOLED, POOLED, seed=2)

    retention = contrast_retention(observed, blind, "chain", "territory")["retention"].iloc[0]
    assert retention < 0.1

    fidelity = stratified_fidelity(observed, blind, "chain", "territory")
    assert (fidelity["distance"] > 0.1).all()       # and it is wrong in both territories


def test_standardised_gap_removes_what_composition_explains():
    from territorial_chains import standardised_gap
    # Old people stay home more, wherever they live; the rural stratum is simply older.
    rows = []
    for stratum, old_share in (("rural", 0.8), ("city", 0.2)):
        for old in (True, False):
            n = int(1000 * (old_share if old else 1 - old_share))
            home = 0.4 if old else 0.1
            rows += [{"stratum": stratum, "old": old, "home": i < home * n, "weight": 1.0} for i in range(n)]
    result = standardised_gap(pd.DataFrame(rows), "home", "stratum", "rural", "city", ["old"])
    assert result["raw"] == pytest.approx(0.18, abs=0.005)
    assert result["standardised"] == pytest.approx(0.0, abs=0.005)
    assert result["coverage"] == pytest.approx(1.0)


def test_standardised_gap_keeps_a_real_territory_effect():
    from territorial_chains import standardised_gap
    rows = []
    for stratum, home in (("rural", 0.3), ("city", 0.1)):
        for old in (True, False):
            rows += [{"stratum": stratum, "old": old, "home": i < home * 500, "weight": 2.0} for i in range(500)]
    result = standardised_gap(pd.DataFrame(rows), "home", "stratum", "rural", "city", ["old"])
    assert result["raw"] == pytest.approx(0.2) and result["standardised"] == pytest.approx(0.2)
