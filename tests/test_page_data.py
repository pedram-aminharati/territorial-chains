import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
pytest.importorskip("geopandas")        # evaluate_population reads activity locations with it
import export_page_data as page  # noqa: E402


def test_short_names():
    assert page.short_name("CC du Pays de Blain") == "Pays de Blain"
    assert page.short_name("CA de la Région Nazairienne et de l'Estuaire (CARENE)") == "CARENE"
    assert page.short_name("CC d'Erdre et Gesvres") == "Erdre et Gesvres"
    assert page.short_name("Nantes Métropole") == "Nantes Métropole"


def test_reference_table_is_complete():
    table = page.load_epci()
    assert len(table) == 207 and table["commune_id"].is_unique
    assert table["epci_id"].nunique() == 17
    assert table["commune_id"].str.startswith("44").all()
    assert (table.groupby("epci_id")["epci_name"].nunique() == 1).all()


def test_aggregate_counts_residents_who_do_not_travel():
    df = pd.DataFrame({"person_id": [1, 2, 3, 4], "commune_id": ["a", "a", "a", "b"],
                       "immobile": [True, False, False, False], "donor_same": [True, True, False, False],
                       "trips": [0.0, 4.0, 2.0, 3.0], "car_km": [0.0, 10.0, 5.0, 0.0]})
    out = page.aggregate(df, "commune_id").set_index("commune_id")
    assert out.loc["a", "residents"] == 3
    assert out.loc["a", "immobile_share"] == pytest.approx(1 / 3)
    assert out.loc["a", "trips_per_resident"] == pytest.approx(2.0)
    assert out.loc["a", "car_km_per_resident"] == pytest.approx(5.0)
    assert out.loc["b", "donor_same_share"] == 0.0


def test_commune_mergers_table():
    here = os.path.dirname(__file__)
    merged = pd.read_csv(os.path.join(here, "..", "reference", "communes_2015_to_2026.csv"), dtype=str)
    assert len(merged) == 20 and merged["commune_2015"].is_unique
    assert not set(merged["commune_2015"]) & set(merged["commune_2026"])      # no chain of mergers
    current = set(page.load_epci()["commune_id"])
    inside = merged[merged["commune_2026"].str.startswith("44")]
    assert set(inside["commune_2026"]) <= current                              # targets exist today
