import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import summarise_seeds as seeds  # noqa: E402

URBAN = ["central_city", "suburb", "isolated_city", "none"]


def write_run(folder, home, trips=None):
    os.makedirs(folder)
    pd.DataFrame({"urban_type": URBAN, "indicator": "immobile_share", "observed": 0.1,
                  "generated": home, "n_generated": 100}).to_csv(os.path.join(folder, "indicators.csv"), index=False)
    pd.DataFrame({"urban_type": URBAN, "distance": 0.05}).to_csv(os.path.join(folder, "fidelity.csv"), index=False)
    pd.DataFrame({"urban_type": URBAN + ["all"], "donor_same_urban_type": 0.5,
                  "donor_from_loire_atlantique": 1.0}).to_csv(os.path.join(folder, "donor_territory.csv"), index=False)
    pd.DataFrame({"attributes_matched": [4, 5], "share": [0.9, 0.7]}).to_csv(os.path.join(folder, "matching_levels.csv"), index=False)
    if trips is not None:
        pd.DataFrame({"urban_type": URBAN + ["all"], "residents": 100, "travelling_share": 0.9,
                      "trips_per_resident": trips, "km_per_resident": 20.0, "car_km_per_resident": 10.0,
                      "minutes_per_resident": 60.0, "km_per_trip": 5.0}).to_csv(os.path.join(folder, "sim_travel.csv"), index=False)
        pd.DataFrame({"urban_type": "all", "mode": ["car", "pt", "walk"], "trips": 1, "km": 1.0,
                      "trip_share": [0.5, 0.1, 0.4], "km_share": 0.3}).to_csv(os.path.join(folder, "sim_modes.csv"), index=False)


@pytest.fixture
def results(tmp_path):
    # seed 1 keeps its original folder names; seed 2 is simulated; seed 3 is population only
    write_run(tmp_path / "A_entd_local", 0.08)
    write_run(tmp_path / "A_entd_local_sim", 0.08, trips=4.0)
    write_run(tmp_path / "C_entd_urban", 0.16)
    write_run(tmp_path / "C_entd_urban_sim", 0.16, trips=3.0)
    write_run(tmp_path / "A_entd_local_seed2_sim", 0.10, trips=4.2)
    write_run(tmp_path / "C_entd_urban_seed2_sim", 0.18, trips=3.4)
    write_run(tmp_path / "A_entd_local_seed3", 0.09)
    write_run(tmp_path / "C_entd_urban_seed3", 0.20)
    return str(tmp_path)


def test_seeds_are_found_under_their_folder_names(results):
    table = seeds.records(results)
    counts = table.groupby(["variant", "source"])["seed"].nunique()
    assert counts[("A", "population")] == 3 and counts[("C", "population")] == 3
    assert counts[("A", "simulation")] == 2 and counts[("C", "simulation")] == 2


def test_summary_gives_mean_and_range(results):
    summary = seeds.summarise(seeds.records(results))
    row = summary[(summary["variant"] == "C") & (summary["quantity"] == "immobile_share") & (summary["urban_type"] == "none")].iloc[0]
    assert row["seeds"] == 3
    assert row["mean"] == pytest.approx(0.18) and row["minimum"] == pytest.approx(0.16) and row["maximum"] == pytest.approx(0.20)


def test_differences_are_paired_by_seed(results):
    diff = seeds.differences(seeds.records(results))
    trips = diff[(diff["quantity"] == "trips_per_resident") & (diff["urban_type"] == "all")].iloc[0]
    assert trips["seeds"] == 2
    assert trips["difference"] == pytest.approx((-1.0 - 0.8) / 2)
    assert trips["relative_min"] == pytest.approx(-0.25) and trips["relative_max"] == pytest.approx(-0.8 / 4.2)
    assert bool(trips["same_sign_in_every_seed"])
    flat = diff[(diff["quantity"] == "hellinger") & (diff["urban_type"] == "none")].iloc[0]
    assert not bool(flat["same_sign_in_every_seed"])          # no difference at all is not a consistent sign


def test_scores_against_the_regional_survey_are_picked_up(results):
    for name in ("A_entd_local", "C_entd_urban"):
        folder = os.path.join(results, name + "__vs_edgt_44")
        os.makedirs(folder)
        pd.DataFrame({"urban_type": URBAN, "distance": 0.1 if name.startswith("A") else 0.15}).to_csv(
            os.path.join(folder, "fidelity.csv"), index=False)
    table = seeds.records(results)
    local = table[table["quantity"] == "hellinger_edgt"]
    assert set(local["variant"]) == {"A", "C"} and set(local["seed"]) == {1}
    assert local[local["variant"] == "C"]["value"].iloc[0] == pytest.approx(0.15)
