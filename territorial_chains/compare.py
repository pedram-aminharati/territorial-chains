"""Fidelity of generated chains against observed ones, by territory.

Two questions are kept apart:

1. *Fidelity inside a territory*: is the generated distribution close to the
   observed one for people living in the same kind of place?
   -> ``stratified_fidelity``

2. *Contrast between territories*: the survey says rural and urban days
   differ by some amount. Does the generated population reproduce that
   difference, or does it flatten it?
   -> ``contrast_matrix`` and ``contrast_retention``

A generator can do well on (1) on average and still fail (2), which is the
failure this project is about.
"""

import itertools

import numpy as np
import pandas as pd

from .weighted import weighted_share


def distribution(df, column, weight=None, top_k=None):
    """Weighted distribution; optionally keep the ``top_k`` categories and pool the rest."""
    share = weighted_share(df, column, weight).sort_values(ascending=False)
    if top_k is not None and len(share) > top_k:
        share = pd.concat([share.iloc[:top_k], pd.Series({"__other__": share.iloc[top_k:].sum()})])
    return share


def _align(p, q):
    index = p.index.union(q.index)
    p = p.reindex(index, fill_value=0.0).to_numpy(dtype=float)
    q = q.reindex(index, fill_value=0.0).to_numpy(dtype=float)
    return p / p.sum(), q / q.sum()


def hellinger(p, q):
    """Hellinger distance in [0, 1]; 0 means identical distributions."""
    p, q = _align(p, q)
    return float(np.sqrt(0.5 * np.sum((np.sqrt(p) - np.sqrt(q)) ** 2)))


def jensen_shannon(p, q):
    """Jensen-Shannon divergence in bits, in [0, 1]."""
    p, q = _align(p, q)
    m = 0.5 * (p + q)

    def kl(a, b):
        mask = a > 0
        return np.sum(a[mask] * np.log2(a[mask] / b[mask]))

    return float(0.5 * kl(p, m) + 0.5 * kl(q, m))


def stratified_fidelity(df_observed, df_generated, column, stratum,
                        observed_weight=None, generated_weight=None, metric=hellinger):
    """Distance between observed and generated distributions inside each stratum."""
    records = []
    for value in sorted(set(df_observed[stratum].unique()) | set(df_generated[stratum].unique())):
        obs = df_observed[df_observed[stratum] == value]
        gen = df_generated[df_generated[stratum] == value]
        if len(obs) == 0 or len(gen) == 0:
            continue
        records.append({
            stratum: value,
            "n_observed": len(obs),
            "n_generated": len(gen),
            "distance": metric(
                weighted_share(obs, column, observed_weight),
                weighted_share(gen, column, generated_weight)),
        })
    return pd.DataFrame.from_records(records)


def contrast_matrix(df, column, stratum, weight=None, metric=jensen_shannon):
    """Pairwise distance between the strata of one population."""
    shares = {
        value: weighted_share(group, column, weight)
        for value, group in df.groupby(stratum, observed=True)
    }
    values = sorted(shares)
    matrix = pd.DataFrame(0.0, index=values, columns=values)
    for a, b in itertools.combinations(values, 2):
        matrix.loc[a, b] = matrix.loc[b, a] = metric(shares[a], shares[b])
    return matrix


def contrast_retention(df_observed, df_generated, column, stratum,
                       observed_weight=None, generated_weight=None, metric=jensen_shannon):
    """Share of the observed between-territory contrast that survives generation.

    For every pair of territories the ratio generated / observed distance is
    reported. 1 means the contrast is fully reproduced, values below 1 mean the
    generator flattens territorial differences, values above 1 exaggerate them.
    """
    observed = contrast_matrix(df_observed, column, stratum, observed_weight, metric)
    generated = contrast_matrix(df_generated, column, stratum, generated_weight, metric)

    records = []
    for a, b in itertools.combinations(observed.index, 2):
        if a not in generated.index or b not in generated.index:
            continue
        obs, gen = observed.loc[a, b], generated.loc[a, b]
        records.append({
            "pair": "%s / %s" % (a, b),
            "observed": obs, "generated": gen,
            "retention": gen / obs if obs > 0 else np.nan,
        })
    return pd.DataFrame.from_records(records)
