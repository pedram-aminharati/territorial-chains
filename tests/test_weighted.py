import numpy as np
import pandas as pd
import pytest

from territorial_chains import weighted_share, weighted_mean, kish_effective_size, bootstrap_ci


def test_weights_change_the_answer():
    df = pd.DataFrame({"chain": ["hwh", "h", "h"], "w": [8.0, 1.0, 1.0]})
    assert weighted_share(df, "chain")["hwh"] == pytest.approx(1 / 3)        # naive
    assert weighted_share(df, "chain", "w")["hwh"] == pytest.approx(0.8)     # weighted


def test_weighted_mean():
    assert weighted_mean([0, 10], [3, 1]) == pytest.approx(2.5)


def test_kish_effective_size():
    assert kish_effective_size(np.ones(50)) == pytest.approx(50)
    # one respondent carrying almost all the weight is worth about one donor
    assert kish_effective_size([1000] + [1] * 49) < 2
    assert kish_effective_size([]) == 0


def test_bootstrap_interval_covers_and_narrows():
    rng = np.random.default_rng(1)
    small = pd.DataFrame({"x": rng.normal(5, 2, 40), "w": 1.0})
    large = pd.DataFrame({"x": rng.normal(5, 2, 4000), "w": 1.0})
    stat = lambda d: weighted_mean(d["x"], d["w"])
    _, lo_s, hi_s = bootstrap_ci(small, stat, n_boot=300)
    est, lo_l, hi_l = bootstrap_ci(large, stat, n_boot=300)
    assert lo_l <= est <= hi_l
    assert (hi_l - lo_l) < (hi_s - lo_s)
