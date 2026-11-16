import pandas as pd
import pytest

from territorial_chains import chains_from_hts, chains_from_activities, add_indicators


def _hts():
    persons = pd.DataFrame({
        "person_id": [1, 2, 3, 4],
        "number_of_trips": [2, 4, 0, -1],   # 3 stayed home, 4 is unknown
    })
    trips = pd.DataFrame({
        "person_id": [1, 1, 2, 2, 2, 2],
        "trip_id": [1, 2, 1, 2, 3, 4],
        "preceding_purpose": ["home", "work", "home", "work", "shop", "home"],
        "following_purpose": ["work", "home", "work", "shop", "home", "leisure"],
    })
    return persons, trips


def test_hts_chains_and_immobility():
    chains = chains_from_hts(*_hts()).set_index("person_id")["chain"]
    assert chains[1] == "hwh"
    assert chains[2] == "hwshl"
    assert chains[3] == "h"          # zero trips -> stayed home
    assert 4 not in chains.index     # unknown trips are dropped, not counted as immobile


def test_activities_match_hts_encoding():
    activities = pd.DataFrame({
        "person_id": [7, 7, 7, 8],
        "activity_index": [2, 0, 1, 0],          # deliberately unsorted
        "purpose": ["home", "home", "education", "home"],
    })
    chains = chains_from_activities(activities).set_index("person_id")["chain"]
    assert chains[7] == "heh"
    assert chains[8] == "h"


def test_unknown_purpose_is_an_error():
    activities = pd.DataFrame({"person_id": [1], "activity_index": [0], "purpose": ["sleep"]})
    with pytest.raises(ValueError):
        chains_from_activities(activities)


@pytest.mark.parametrize("chain, activities, trips, tours, commute", [
    ("h",       0, 0, 0, False),
    ("hwh",     1, 2, 1, True),
    ("heh",     1, 2, 1, True),
    ("hwshlh",  3, 5, 2, False),   # work+shop tour, then a leisure tour
    ("hwhwh",   2, 4, 2, False),   # lunch at home: two tours
    ("hws",     2, 2, 1, False),   # day does not end at home
])
def test_indicators(chain, activities, trips, tours, commute):
    row = add_indicators(pd.DataFrame({"chain": [chain]})).iloc[0]
    assert row["n_activities"] == activities
    assert row["n_trips"] == trips
    assert row["n_tours"] == tours
    assert bool(row["simple_commute"]) is commute
    assert bool(row["immobile"]) is (chain == "h")
