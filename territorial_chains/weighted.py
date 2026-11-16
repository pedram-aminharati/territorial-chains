"""Weighted statistics for survey data.

Household travel surveys are not simple random samples: every respondent
carries an expansion weight. All statistics here take the weight explicitly,
and the bootstrap resamples respondents (not weight units), which is what
keeps the intervals honest in thin strata.
"""

import numpy as np
import pandas as pd


def weighted_mean(values, weights):
    values = np.asarray(values, dtype=float)
    weights = np.asarray(weights, dtype=float)
    return float(np.sum(values * weights) / np.sum(weights))


def weighted_share(df, column, weight=None):
    """Weighted distribution of a categorical column, as a Series summing to 1."""
    w = df[weight] if weight is not None else pd.Series(1.0, index=df.index)
    totals = w.groupby(df[column], observed=True).sum()
    return totals / totals.sum()


def kish_effective_size(weights):
    """Kish effective sample size: (sum w)^2 / sum w^2.

    Equal to n for equal weights and smaller otherwise. This, not the raw
    respondent count, is the number of donors a stratum really offers.
    """
    w = np.asarray(weights, dtype=float)
    if len(w) == 0:
        return 0.0
    return float(w.sum() ** 2 / np.sum(w ** 2))


def bootstrap_ci(df, statistic, n_boot=500, level=0.95, seed=0):
    """Percentile bootstrap interval for ``statistic(df) -> float``.

    Rows (respondents) are resampled with replacement; weights travel with
    their respondent.
    """
    rng = np.random.default_rng(seed)
    n = len(df)
    if n == 0:
        return (np.nan, np.nan, np.nan)

    draws = np.empty(n_boot)
    for b in range(n_boot):
        draws[b] = statistic(df.iloc[rng.integers(0, n, n)])

    alpha = (1.0 - level) / 2.0
    lower, upper = np.nanquantile(draws, [alpha, 1.0 - alpha])
    return (float(statistic(df)), float(lower), float(upper))
