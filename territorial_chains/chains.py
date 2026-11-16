"""Build activity chains and per-person indicators from eqasim tables.

Two entry points produce the same schema, so observed survey data and a
generated population are scored by exactly the same code:

* ``chains_from_hts``        -- cleaned household travel survey (eqasim ``data.hts.*`` format)
* ``chains_from_activities`` -- synthetic population output (``*_activities.csv``)

A chain is a string with one letter per activity, in order, e.g. ``hwh`` or
``hwshlh``. The alphabet is the one eqasim itself uses in ``analysis/chains.py``.
"""

import numpy as np

PURPOSE_CODES = {
    "home": "h", "work": "w", "education": "e",
    "shop": "s", "leisure": "l", "other": "o",
}

SECONDARY = set("slo")


def _encode(purposes):
    unknown = set(purposes.unique()) - set(PURPOSE_CODES)
    if unknown:
        raise ValueError("Unknown activity purposes: %s" % sorted(unknown))
    return purposes.map(PURPOSE_CODES)


def chains_from_hts(df_persons, df_trips, immobile_chain="h"):
    """One row per surveyed person: ``person_id``, ``chain``.

    The chain is the purpose preceding the first trip followed by the purpose
    following every trip. Persons who report zero trips get ``immobile_chain``
    (they stayed home); persons whose trips are unknown (``number_of_trips``
    negative or missing) are dropped, because treating them as immobile would
    bias every share.
    """
    df_trips = df_trips.sort_values(["person_id", "trip_id"])

    first = df_trips.groupby("person_id", sort=False)["preceding_purpose"].first()
    following = _encode(df_trips["following_purpose"]).groupby(
        df_trips["person_id"], sort=False).agg("".join)
    mobile = (_encode(first) + following).rename("chain")

    df = df_persons[["person_id", "number_of_trips"]].merge(
        mobile, left_on="person_id", right_index=True, how="left")

    immobile = df["chain"].isna() & (df["number_of_trips"] == 0)
    df.loc[immobile, "chain"] = immobile_chain

    return df.dropna(subset=["chain"])[["person_id", "chain"]].reset_index(drop=True)


def chains_from_activities(df_activities):
    """One row per synthetic person: ``person_id``, ``chain``."""
    df = df_activities.sort_values(["person_id", "activity_index"])
    chain = _encode(df["purpose"]).groupby(df["person_id"], sort=False).agg("".join)
    return chain.rename("chain").reset_index()


def add_indicators(df_chains):
    """Append the indicator grid to a table that has a ``chain`` column.

    Indicators (all per person-day):

    ``n_activities``   out-of-home activities
    ``n_trips``        trips, i.e. transitions between activities
    ``n_tours``        home-based tours (departures from home that return)
    ``immobile``       stayed at home all day
    ``has_work`` / ``has_education`` / ``has_secondary``
    ``simple_commute`` exactly home - work/education - home
    ``stops_per_tour`` out-of-home activities per tour, a complexity measure
    ``length_class``   chain length capped at ``5+`` for tabulation
    """
    df = df_chains.copy()
    chain = df["chain"]

    df["n_activities"] = chain.str.replace("h", "", regex=False).str.len()
    df["n_trips"] = chain.str.len() - 1
    df["immobile"] = df["n_trips"] == 0

    # A tour is a maximal run of out-of-home activities enclosed by home.
    inner = chain.str.strip("h")
    df["n_tours"] = np.where(inner == "", 0, inner.str.count("h+") + 1)
    closed = chain.str.startswith("h") & chain.str.endswith("h")
    df["closed_day"] = closed

    df["has_work"] = chain.str.contains("w", regex=False)
    df["has_education"] = chain.str.contains("e", regex=False)
    df["has_secondary"] = chain.apply(lambda c: bool(SECONDARY & set(c)))
    df["simple_commute"] = chain.isin(["hwh", "heh"])

    df["stops_per_tour"] = np.where(
        df["n_tours"] > 0, df["n_activities"] / df["n_tours"].clip(lower=1), 0.0)

    df["length_class"] = df["n_activities"].clip(upper=5).astype(str).replace({"5": "5+"})
    return df
