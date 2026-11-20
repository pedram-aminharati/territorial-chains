"""The pieces meant for eqasim-france (eqasim_contrib/).

The two stages are run by synpp itself, with small stand-ins for the eqasim
stages they read. The patches are checked against a real checkout when the
environment variable EQASIM_PATH points to one.
"""

import importlib.util
import os
import shutil
import stat
import subprocess
import sys
import textwrap

import numpy as np
import pandas as pd
import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
CONTRIB = os.path.join(HERE, "..", "eqasim_contrib")
PATCHES = ["java_version_check.patch", "edgt_44_urban_type.patch"]

# Stand-ins for the eqasim stages the analysis stage depends on. Eight residents of four
# communes; residents 1 to 6 are matched, 7 is a child without a respondent.
STUBS = {
    "synthesis/population/enriched.py": """
        import pandas as pd
        def configure(context): pass
        def execute(context):
            return pd.DataFrame({
                "person_id": [1, 2, 3, 4, 5, 6, 7], "household_id": [1, 1, 2, 3, 4, 4, 4],
                "hts_person_id": [10, 11, 12, 13, 12, 13, -1],
                "commune_id": pd.Categorical(["44109", "44109", "44162", "undefined", "undefined", "undefined", "undefined"]),
            })
    """,
    "synthesis/population/activities.py": """
        import pandas as pd
        def configure(context): pass
        def execute(context):
            chains = {1: "home work home", 2: "home", 3: "home shop home leisure home", 4: "home", 5: "home shop home leisure home",
                      6: "home", 7: "home"}
            rows = [(p, i, purpose) for p, chain in chains.items() for i, purpose in enumerate(chain.split())]
            return pd.DataFrame(rows, columns=["person_id", "activity_index", "purpose"]).sample(frac=1.0, random_state=0)
    """,
    "synthesis/population/spatial/home/zones.py": """
        import pandas as pd
        def configure(context): pass
        def execute(context):
            return pd.DataFrame({"household_id": [1, 2, 3, 4],
                                 "commune_id": pd.Categorical(["44109", "44162", "44036", "44999"])})
    """,
    "data/spatial/urban_type.py": """
        import pandas as pd
        def configure(context): pass
        def execute(context):
            return pd.DataFrame({"commune_id": ["44109", "44162", "44036", "44999"],
                                 "urban_type": pd.Categorical(["central_city", "suburb", "isolated_city", "none"])})
    """,
    "data/hts/selected.py": """
        import pandas as pd
        def configure(context): context.config("survey_urban_type", True)
        def execute(context):
            households = pd.DataFrame({"household_id": [100, 101, 102, 103],
                                       "urban_type": pd.Categorical(["central_city", "central_city", "none", "none"])})
            if not context.config("survey_urban_type"):
                households = households.drop(columns="urban_type")
            persons = pd.DataFrame({"person_id": [10, 11, 12, 13], "household_id": [100, 101, 102, 103],
                                    "person_weight": [3.0, 1.0, 1.0, 1.0]})
            trips = pd.DataFrame({
                "person_id": [12, 10, 12, 10, 12, 12], "trip_id": [3, 1, 4, 2, 5, 6],
                "preceding_purpose": ["home", "home", "shop", "work", "home", "leisure"],
                "following_purpose": ["shop", "work", "home", "home", "leisure", "home"]})
            return households, persons, trips
    """,
}


def run_stage(tmp_path, **config):
    """Run the analysis stage with synpp in a fresh interpreter and return its three tables."""
    pytest.importorskip("synpp")
    tree, out = tmp_path / "tree", tmp_path / "out"
    out.mkdir()
    for relative, source in STUBS.items():
        target = tree / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(textwrap.dedent(source))
    stage = tree / "analysis" / "synthesis" / "chains_by_territory.py"
    stage.parent.mkdir(parents=True)
    shutil.copy(os.path.join(CONTRIB, "analysis", "synthesis", "chains_by_territory.py"), stage)

    settings = {"output_path": str(out), "output_prefix": "test_", **config}
    script = ("import sys, synpp; sys.path.insert(0, '.'); "
              "synpp.run([{'descriptor': 'analysis.synthesis.chains_by_territory'}], config=%r, "
              "working_directory=%r)" % (settings, str(tmp_path / "cache")))
    (tmp_path / "cache").mkdir()
    done = subprocess.run([sys.executable, "-c", script], cwd=tree, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr[-2000:]

    def table(name):
        path = out / ("test_chains_by_territory_%s.csv" % name)
        return pd.read_csv(path, sep=";") if path.exists() else None
    return table("indicators"), table("chains"), table("donors")


def test_stage_scores_the_population_by_territory(tmp_path):
    indicators, chains, donors = run_stage(tmp_path)
    by = indicators.set_index("urban_type")

    # Six matched residents: two in the central city, one suburb, one isolated city, two rural.
    assert by["persons"].to_dict() == {"central_city": 2, "suburb": 1, "isolated_city": 1, "none": 2, "all": 6}
    assert by.loc["central_city", "population_stays_home"] == pytest.approx(0.5)
    assert by.loc["none", "population_tours_per_mobile_person"] == pytest.approx(2.0)

    # The survey side is weighted: respondent 10 (weight 3) goes to work, respondent 11 stays home.
    assert by.loc["central_city", "survey_stays_home"] == pytest.approx(0.25)
    assert by.loc["central_city", "respondents"] == 2
    # The rural population repeats the two rural respondents exactly.
    assert by.loc["none", "hellinger_distance"] == pytest.approx(0.0, abs=1e-9)
    assert by.loc["central_city", "hellinger_distance"] > 0.1
    # Residents whose commune the census withholds.
    assert by.loc["none", "census_commune_undefined"] == pytest.approx(1.0)
    assert by.loc["central_city", "census_commune_undefined"] == pytest.approx(0.0)

    shares = chains[chains["urban_type"] == "central_city"].set_index("chain")
    assert shares.loc["hwh", "survey"] == pytest.approx(0.75)
    assert shares.loc["hwh", "population"] == pytest.approx(0.5)

    same = donors.set_index("urban_type")["donor_same_urban_type"]
    assert same["central_city"] == pytest.approx(1.0)
    assert same["suburb"] == pytest.approx(0.0)       # its respondent lives in a rural commune
    assert same["all"] == pytest.approx(4 / 6)


def test_stage_without_urban_type_in_the_survey(tmp_path):
    indicators, chains, donors = run_stage(tmp_path, survey_urban_type=False)
    by = indicators.set_index("urban_type")
    assert donors is None
    assert pd.isna(by.loc["central_city", "survey_stays_home"])        # no reference by territory
    assert by.loc["all", "respondents"] == 4                           # the overall comparison remains
    assert by.loc["none", "population_stays_home"] == pytest.approx(0.5)
    assert set(chains["urban_type"]) == {"all"}


# --------------------------------------------------------------------------- structured matching

# A plain stand-in for eqasim's statistical_matching with the same contract: residents come
# back sorted by attribute values, with the number of attributes each one was matched on.
MATCHING_STAND_IN = """
    import numpy as np

    DEFAULT_MATCHING_ATTRIBUTES = ["sex", "any_cars", "age_class", "socioprofessional_class", "departement_id"]

    def statistical_matching(progress, df_source, source_identifier, weight, df_target, target_identifier, columns,
                             random_seed=0, minimum_observations=0):
        random = np.random.default_rng(random_seed)
        df_target = df_target[[target_identifier] + columns].sort_values(by=columns + [target_identifier]).copy()
        assigned, levels = np.full(len(df_target), -1), np.zeros(len(df_target), dtype=int)
        for level in range(len(columns), 0, -1):
            target_keys = df_target[columns[:level]].astype(str).agg("|".join, axis=1).values
            source_keys = df_source[columns[:level]].astype(str).agg("|".join, axis=1).values
            for key in np.unique(target_keys[assigned < 0]):
                f_source = source_keys == key
                if f_source.sum() < max(minimum_observations, 1):
                    continue
                f_target = (target_keys == key) & (assigned < 0)
                w = df_source[weight].values[f_source].astype(float)
                assigned[f_target] = random.choice(df_source[source_identifier].values[f_source], size=f_target.sum(), p=w / w.sum())
                levels[f_target] = level
        if (assigned < 0).any():
            raise RuntimeError("Some target observations could not be matched.")
        df_target[source_identifier] = assigned
        return df_target[[target_identifier, source_identifier]], levels
"""

STRUCTURED_STUBS = {
    name: """
        import pandas as pd
        def configure(context): context.config("fixtures")
        def execute(context): return pd.read_pickle(context.config("fixtures") + "/%s.p")
    """ % key
    for name, key in [("synthesis/population/sampled.py", "sampled"), ("synthesis/population/spatial/home/zones.py", "zones"),
                      ("data/spatial/urban_type.py", "urban_type"), ("data/spatial/codes.py", "codes"),
                      ("data/hts/selected.py", "hts")]
}


def survey_and_residents(local_respondents, seed=0):
    """A survey in which rural people stay home half of the time, except in the study area."""
    rng = np.random.default_rng(seed)
    n = 6000
    local = np.arange(n) < local_respondents
    urban = rng.choice(["central_city", "none"], size=n)
    stays = rng.random(n) < np.where((urban == "none") & ~local, 0.5, 0.1)
    chain = np.where(stays, "h", rng.choice(["hwh", "hsh", "hwhsh", "heh"], size=n, p=[0.5, 0.2, 0.2, 0.1]))
    purposes = {"h": "home", "w": "work", "s": "shop", "e": "education"}
    trips = [(person, index, purposes[a], purposes[b])
             for person, c in enumerate(chain) for index, (a, b) in enumerate(zip(c[:-1], c[1:]))]
    households = pd.DataFrame({
        "household_id": np.arange(n), "departement_id": pd.Categorical(np.where(local, "44", "75")),
        "urban_type": pd.Categorical(urban), "number_of_vehicles": rng.integers(0, 3, n)})
    persons = pd.DataFrame({
        "person_id": np.arange(n), "household_id": np.arange(n), "departement_id": households["departement_id"],
        "person_weight": rng.uniform(0.5, 1.5, n), "age": rng.integers(5, 90, n),
        "sex": pd.Categorical(rng.choice(["female", "male"], size=n)), "socioprofessional_class": rng.integers(1, 9, n)})
    trips = pd.DataFrame(trips, columns=["person_id", "trip_id", "preceding_purpose", "following_purpose"])

    m = 4000
    residents = pd.DataFrame({
        "person_id": np.arange(m) + 100000, "household_id": np.arange(m), "age": rng.integers(0, 90, m),
        "sex": pd.Categorical(rng.choice(["female", "male"], size=m)), "socioprofessional_class": rng.integers(1, 9, m),
        "number_of_vehicles": rng.integers(0, 3, m), "departement_id": pd.Categorical(["44"] * m),
        "commune_id": pd.Categorical(["undefined"] * m)})          # the census withholds the commune
    zones = pd.DataFrame({"household_id": np.arange(m), "commune_id": pd.Categorical(np.where(np.arange(m) % 2, "44001", "44002"))})
    fixtures = {"sampled": residents, "zones": zones, "hts": (households, persons, trips),
                "urban_type": pd.DataFrame({"commune_id": ["44001", "44002"], "urban_type": ["none", "central_city"]}),
                "codes": pd.DataFrame({"departement_id": ["44"]})}
    rural = residents["person_id"][(np.arange(m) % 2).astype(bool)]
    return fixtures, pd.Series(chain == "h", index=np.arange(n)), set(rural)


def run_structured(tmp_path, fixtures, eqasim=None, **config):
    pytest.importorskip("synpp")
    tree, store = tmp_path / "tree", tmp_path / "fixtures"
    store.mkdir()
    if eqasim:                                   # eqasim's own matching function and its imports
        for package in ("data", "synthesis"):
            shutil.copytree(os.path.join(eqasim, package), tree / package, ignore=shutil.ignore_patterns("__pycache__"))
    else:
        (tree / "synthesis" / "population").mkdir(parents=True)
        (tree / "synthesis" / "population" / "matched.py").write_text(textwrap.dedent(MATCHING_STAND_IN))
    for relative, source in STRUCTURED_STUBS.items():
        (tree / relative).parent.mkdir(parents=True, exist_ok=True)
        (tree / relative).write_text(textwrap.dedent(source))
    shutil.copy(os.path.join(CONTRIB, "synthesis", "population", "matched_structured.py"), tree / "synthesis" / "population")
    for key, value in fixtures.items():
        pd.to_pickle(value, store / ("%s.p" % key))

    # A later stage asks for eqasim's matching by name and must receive this stage instead,
    # as it will in a configuration file with an "aliases" entry.
    (tree / "later_stage.py").write_text(textwrap.dedent("""
        def configure(context): context.stage("synthesis.population.matched")
        def execute(context): return context.stage("synthesis.population.matched")
    """))
    settings = {"fixtures": str(store), "random_seed": 7, "processes": 1, **config}
    script = ("import sys, synpp; sys.path.insert(0, '.'); "
              "synpp.run([{'descriptor': 'later_stage'}], config=%r, working_directory=%r, "
              "aliases={'synthesis.population.matched': 'synthesis.population.matched_structured'})[0].to_pickle(%r)"
              % (settings, str(tmp_path / "cache"), str(tmp_path / "out.p")))
    (tmp_path / "cache").mkdir()
    done = subprocess.run([sys.executable, "-c", script], cwd=tree, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr[-2000:]
    return pd.read_pickle(tmp_path / "out.p"), done.stdout


def stay_home_shares(assignment, stays_home, rural):
    home = assignment["hts_person_id"].map(stays_home)
    is_rural = assignment["person_id"].isin(rural)
    return float(home[is_rural].mean()), float(home[~is_rural].mean())


def check_structured(tmp_path, eqasim=None):
    # Many respondents in the study area: their behaviour prevails over the national pattern.
    fixtures, stays_home, rural = survey_and_residents(local_respondents=2000)
    assignment, printed = run_structured(tmp_path / "local", fixtures, eqasim)
    assert list(assignment.columns) == ["person_id", "hts_person_id"]
    adults = fixtures["sampled"][fixtures["sampled"]["age"] >= 5]
    assert sorted(assignment["person_id"]) == sorted(adults["person_id"])          # children are not matched
    assert assignment["hts_person_id"].isin(fixtures["hts"][1]["person_id"]).all()
    assert "weight of the national prior" in printed and "matched levels" in printed
    rural_home, central_home = stay_home_shares(assignment, stays_home, rural)
    assert rural_home < 0.2 and central_home < 0.2

    # The same survey read as one national pool: rural residents get the national rural pattern,
    # although the census gives no commune for any of them.
    assignment, _ = run_structured(tmp_path / "pooled", fixtures, eqasim, structure_prior_strength=1e6)
    rural_home, central_home = stay_home_shares(assignment, stays_home, rural)
    assert rural_home > 0.3 and central_home < 0.2

    # No respondent in the study area: the national tables are used as they are.
    fixtures, stays_home, rural = survey_and_residents(local_respondents=0)
    assignment, printed = run_structured(tmp_path / "none", fixtures, eqasim)
    assert "weight of the national prior" not in printed
    rural_home, central_home = stay_home_shares(assignment, stays_home, rural)
    assert rural_home > 0.4 and central_home < 0.2


def test_structured_matching_pools_local_and_national_respondents(tmp_path):
    for name in ("local", "pooled", "none"):
        (tmp_path / name).mkdir()
    check_structured(tmp_path)


# --------------------------------------------------------------------------- patches

EQASIM = os.environ.get("EQASIM_PATH", "")
needs_eqasim = pytest.mark.skipif(
    not EQASIM or not os.path.isdir(os.path.join(EQASIM, ".git")),
    reason="needs EQASIM_PATH pointing to a git checkout of eqasim-france")


def git(path, *arguments, **options):
    return subprocess.run(["git", "-C", path, *arguments], capture_output=True, text=True, **options)


@needs_eqasim
@pytest.mark.parametrize("patch", PATCHES)
def test_patch_applies_to_the_checkout(patch):
    path = os.path.abspath(os.path.join(CONTRIB, "patches", patch))
    forward = git(EQASIM, "apply", "--check", path)
    already = git(EQASIM, "apply", "--reverse", "--check", path)
    assert forward.returncode == 0 or already.returncode == 0, forward.stderr


@needs_eqasim
@pytest.mark.skipif(os.name == "nt", reason="uses shell scripts as stand-ins for java")
@pytest.mark.parametrize("version,accepted", [
    ("25", True), ("17.0.9", True), ("25.0.1.1", True), ("21-ea", True), ("11.0.2", False), ("1.8.0_292", False)])
def test_java_version_check_after_the_patch(tmp_path, version, accepted):
    # The released file, patched in a scratch folder.
    released = git(EQASIM, "show", "v1.5.0:matsim/runtime/java.py")
    if released.returncode != 0:
        released = git(EQASIM, "show", "HEAD:matsim/runtime/java.py")
    target = tmp_path / "matsim" / "runtime" / "java.py"
    target.parent.mkdir(parents=True)
    target.write_text(released.stdout)
    patch = os.path.abspath(os.path.join(CONTRIB, "patches", "java_version_check.patch"))
    applied = subprocess.run(["git", "apply", patch], cwd=tmp_path, capture_output=True, text=True)
    assert applied.returncode == 0, applied.stderr

    java = tmp_path / "java"
    java.write_text('#!/bin/sh\necho \'openjdk version "%s" 2026-01-20\' >&2\n' % version)
    java.chmod(java.stat().st_mode | stat.S_IEXEC)

    spec = importlib.util.spec_from_file_location("patched_java", target)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class Context:
        def config(self, name):
            return {"java_binary": str(java)}[name]

    if accepted:
        module.validate(Context())
    else:
        with pytest.raises(RuntimeError, match="at least version 17"):
            module.validate(Context())


@needs_eqasim
def test_structured_matching_with_the_matching_function_of_eqasim(tmp_path):
    pytest.importorskip("numba")
    for name in ("local", "pooled", "none"):
        (tmp_path / name).mkdir()
    check_structured(tmp_path, eqasim=EQASIM)
