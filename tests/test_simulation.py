import pandas as pd
import pytest

from territorial_chains import read_table, attach_home, mode_shares, travel_per_resident, convergence


@pytest.fixture
def residents():
    return pd.DataFrame({"person_id": [1, 2, 3, 4],
                         "urban_type": ["central_city", "central_city", "none", "none"]})


@pytest.fixture
def trips():
    # person 2 stays home; person 9 is not a resident and must be ignored
    return pd.DataFrame({
        "person_id":       [1, 1, 3, 3, 4, 9],
        "mode":            ["walk", "walk", "car", "car", "pt", "car"],
        "routed_distance": [1000.0, 1000.0, 10000.0, 10000.0, 5000.0, 99000.0],
        "travel_time":     [600.0, 600.0, 900.0, 900.0, 1200.0, 60.0],
    })


def test_attach_home_drops_non_residents(trips, residents):
    df = attach_home(trips, residents)
    assert len(df) == 5 and set(df["person_id"]) == {1, 3, 4}


def test_mode_shares_sum_to_one_per_territory(trips, residents):
    table = mode_shares(attach_home(trips, residents))
    sums = table.groupby("urban_type")[["trip_share", "km_share"]].sum()
    assert sums.to_numpy() == pytest.approx(1.0)
    rural = table[table["urban_type"] == "none"].set_index("mode")
    assert rural.loc["car", "trip_share"] == pytest.approx(2 / 3)
    assert rural.loc["car", "km_share"] == pytest.approx(20 / 25)
    overall = table[table["urban_type"] == "all"].set_index("mode")
    assert overall.loc["walk", "trip_share"] == pytest.approx(2 / 5)
    assert list(overall.index) == ["car", "pt", "walk"]          # fixed mode order


def test_travel_per_resident_counts_people_who_stay_home(trips, residents):
    table = travel_per_resident(attach_home(trips, residents), residents).set_index("urban_type")
    central, rural, overall = table.loc["central_city"], table.loc["none"], table.loc["all"]
    assert central["residents"] == 2 and central["travelling_share"] == pytest.approx(0.5)
    assert central["km_per_resident"] == pytest.approx(1.0)       # 2 km over 2 residents
    assert central["car_km_per_resident"] == 0.0
    assert rural["car_km_per_resident"] == pytest.approx(10.0)    # 20 km by car over 2 residents
    assert rural["minutes_per_resident"] == pytest.approx(25.0)
    assert overall["trips_per_resident"] == pytest.approx(5 / 4)
    assert overall["km_per_trip"] == pytest.approx(27 / 5)


def test_territory_without_trips_gets_zeros(residents):
    empty = pd.DataFrame({"person_id": [1], "mode": ["walk"], "routed_distance": [500.0], "travel_time": [300.0]})
    table = travel_per_resident(attach_home(empty, residents), residents).set_index("urban_type")
    assert table.loc["none", "trips_per_resident"] == 0.0
    assert pd.isna(table.loc["none", "km_per_trip"])


def test_read_table_handles_delimiters_and_compression(tmp_path, trips):
    trips.to_csv(tmp_path / "semi.csv", sep=";", index=False)
    trips.to_csv(tmp_path / "comma.csv.gz", sep=",", index=False)
    assert list(read_table(tmp_path / "semi.csv").columns) == list(trips.columns)
    assert len(read_table(tmp_path / "comma.csv.gz")) == len(trips)
    pytest.importorskip("zstandard")
    trips.to_csv(tmp_path / "semi.csv.zst", sep=";", index=False, compression="zstd")
    assert read_table(tmp_path / "semi.csv.zst")["routed_distance"].sum() == trips["routed_distance"].sum()


def test_convergence_long_form():
    stats = pd.DataFrame({"Iteration": [0, 1], "walk": [0.3, 0.25], "car": [0.6, 0.65], "pt": [0.1, 0.1]})
    long = convergence(stats)
    assert list(long.columns) == ["iteration", "mode", "share"]
    assert list(long[long["iteration"] == 1]["mode"]) == ["car", "pt", "walk"]
    assert long.groupby("iteration")["share"].sum().to_numpy() == pytest.approx(1.0)
