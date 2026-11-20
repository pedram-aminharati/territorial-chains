import os

import numpy as np
import pandas as pd
import pytest

from territorial_chains.generators import chain_structure, ATTRIBUTES


def toy_survey(n=3000, seed=0):
    """Rural people stay home far more often; nothing else depends on territory."""
    rng = np.random.default_rng(seed)
    urban = rng.choice(["central_city", "none"], size=n)
    stays = rng.random(n) < np.where(urban == "none", 0.45, 0.05)
    mobile_chain = rng.choice(["hwh", "hsh", "hwshlh", "hlh"], size=n, p=[0.5, 0.2, 0.1, 0.2])
    return pd.DataFrame({
        "person_id": np.arange(n), "weight": rng.uniform(0.5, 1.5, n),
        "sex": rng.choice(["female", "male"], size=n), "any_cars": rng.random(n) < 0.8,
        "age_class": rng.integers(0, 6, n), "socioprofessional_class": rng.integers(1, 9, n),
        "urban_type": urban, "departement_id": "44",
        "chain": np.where(stays, "h", mobile_chain),
    })


def stay_home_gap(target, chains):
    home = pd.Series(chains == "h")
    rural = (target["urban_type"] == "none").to_numpy()
    return home[rural].mean() - home[~rural].mean()


def test_chain_structure():
    s = chain_structure(["h", "hwh", "hwshlh", "heh", "hlhlhsh"])
    assert s["mobile"].tolist() == ["no", "yes", "yes", "yes", "yes"]
    assert s["primary"].tolist() == ["none", "work", "work", "education", "other"]
    assert s["tours"].tolist() == ["0", "1", "2", "1", "3"]
    assert s["secondary"].tolist() == ["0", "0", "2", "0", "3"]


def test_bayesnet_with_territory_edge_keeps_the_gap():
    pytest.importorskip("pgmpy")
    from territorial_chains.generators import BayesNetGenerator
    train, target = toy_survey(seed=1), toy_survey(seed=2)
    rng = np.random.default_rng(0)
    model = BayesNetGenerator(required_edges=[("urban_type", "mobile")]).fit(train)
    assert ("urban_type", "mobile") in model.edges
    chains = model.sample(target, rng)
    assert stay_home_gap(target, chains) == pytest.approx(0.40, abs=0.07)
    assert set(chains) <= set(train["chain"])          # it only reuses reported chains


def test_autoregressive_learns_territory_only_when_it_sees_it():
    pytest.importorskip("torch")
    from territorial_chains.generators import AutoregressiveGenerator
    train, target = toy_survey(seed=1), toy_survey(seed=2)
    rng = np.random.default_rng(0)
    seeing = AutoregressiveGenerator(attributes=ATTRIBUTES, epochs=6, d_model=32, layers=1).fit(train)
    blind = AutoregressiveGenerator(attributes=[a for a in ATTRIBUTES if a != "urban_type"],
                                    epochs=6, d_model=32, layers=1).fit(train)
    assert stay_home_gap(target, seeing.sample(target, rng)) > 0.25
    assert abs(stay_home_gap(target, blind.sample(target, rng))) < 0.08


def test_vae_learns_territory_only_when_it_sees_it():
    pytest.importorskip("torch")
    from territorial_chains.generators import VAEGenerator
    train, target = toy_survey(seed=1), toy_survey(seed=2)
    rng = np.random.default_rng(0)
    seeing = VAEGenerator(attributes=ATTRIBUTES, epochs=12, d_model=32, latent=8).fit(train)
    blind = VAEGenerator(attributes=[a for a in ATTRIBUTES if a != "urban_type"],
                         epochs=12, d_model=32, latent=8).fit(train)
    chains = seeing.sample(target, rng)
    assert len(chains) == len(target) and all(set(c) <= set("hweslo") for c in chains)
    assert stay_home_gap(target, chains) > 0.25
    assert abs(stay_home_gap(target, blind.sample(target, rng))) < 0.08
    assert seeing.validation_kl >= 0.0


def test_gan_learns_territory_only_when_it_sees_it():
    pytest.importorskip("torch")
    from territorial_chains.generators import GANGenerator
    train, target = toy_survey(seed=1), toy_survey(seed=2)
    rng = np.random.default_rng(0)
    seeing = GANGenerator(attributes=ATTRIBUTES, steps=300, hidden=128, d_model=32).fit(train)
    blind = GANGenerator(attributes=[a for a in ATTRIBUTES if a != "urban_type"], steps=300, hidden=128, d_model=32).fit(train)
    chains = seeing.sample(target, rng)
    assert len(chains) == len(target) and all(c and set(c) <= set("hweslo") for c in chains)
    assert stay_home_gap(target, chains) > 0.2
    assert abs(stay_home_gap(target, blind.sample(target, rng))) < 0.1


@pytest.mark.skipif("EQASIM_PATH" not in os.environ, reason="needs an eqasim-france checkout")
def test_matching_wraps_eqasim():
    from territorial_chains.generators import MatchingGenerator
    train, target = toy_survey(seed=1), toy_survey(seed=2)
    model = MatchingGenerator(os.environ["EQASIM_PATH"], ["urban_type", "sex", "age_class"]).fit(train)
    chains = model.sample(target, np.random.default_rng(0))
    assert len(chains) == len(target)
    assert stay_home_gap(target, chains) == pytest.approx(0.40, abs=0.07)
