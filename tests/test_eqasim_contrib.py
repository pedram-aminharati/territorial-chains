"""The pieces meant for eqasim-france (eqasim_contrib/).

The analysis stage is run by synpp itself, with small stand-ins for the eqasim
stages it reads. The patches are checked against a real checkout when the
environment variable EQASIM_PATH points to one.
"""

import importlib.util
import os
import shutil
import stat
import subprocess
import sys
import textwrap

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


# --------------------------------------------------------------------------- patches

needs_eqasim = pytest.mark.skipif(
    not os.path.isdir(os.path.join(os.environ.get("EQASIM_PATH", ""), ".git")),
    reason="needs EQASIM_PATH pointing to a git checkout of eqasim-france")


def git(path, *arguments, **options):
    return subprocess.run(["git", "-C", path, *arguments], capture_output=True, text=True, **options)


@needs_eqasim
@pytest.mark.parametrize("patch", PATCHES)
def test_patch_applies_to_the_checkout(patch):
    path = os.path.abspath(os.path.join(CONTRIB, "patches", patch))
    forward = git(os.environ["EQASIM_PATH"], "apply", "--check", path)
    already = git(os.environ["EQASIM_PATH"], "apply", "--reverse", "--check", path)
    assert forward.returncode == 0 or already.returncode == 0, forward.stderr


@needs_eqasim
@pytest.mark.skipif(os.name == "nt", reason="uses shell scripts as stand-ins for java")
@pytest.mark.parametrize("version,accepted", [
    ("25", True), ("17.0.9", True), ("25.0.1.1", True), ("21-ea", True), ("11.0.2", False), ("1.8.0_292", False)])
def test_java_version_check_after_the_patch(tmp_path, version, accepted):
    # The released file, patched in a scratch folder.
    released = git(os.environ["EQASIM_PATH"], "show", "v1.5.0:matsim/runtime/java.py")
    if released.returncode != 0:
        released = git(os.environ["EQASIM_PATH"], "show", "HEAD:matsim/runtime/java.py")
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
