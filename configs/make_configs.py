"""Write the eqasim config variants for the Loire-Atlantique pilot.

Usage:  python configs/make_configs.py /abs/project/path [sampling_rate]

The project path must contain data/ and output/ (see docs/SETUP_WSL.md).
One YAML per experimental variant is written next to this script.
"""

import sys
from pathlib import Path

import yaml

VARIANTS = {
    # name:            (hts,       filter_hts, urban_type)
    "A_entd_local":    ("entd",    True,  False),   # eqasim defaults for a single departement
    "B_entd_national": ("entd",    False, False),   # all national donors, territory = departement only
    "C_entd_urban":    ("entd",    False, True),    # + INSEE urban type, placed first
    "D_emp_national":  ("emp",     False, False),   # newer survey (2019)
    "E_emp_urban":     ("emp",     False, True),
    "F_edgt44":        ("edgt_44", True,  False),   # regional survey as donors: local reference
    # Regional donors matched on the urban type. eqasim v1.5.0 does not keep the home zone of
    # this survey: apply eqasim_contrib/patches/edgt_44_urban_type.patch first (see its README).
    "G_edgt44_urban":  ("edgt_44", True,  True),
}

# The analysis stage of eqasim_contrib/, run inside eqasim on a variant's population.
TERRITORY_STAGE = "analysis.synthesis.chains_by_territory"

URBAN_TYPE_FILE = "urban_type/UU2020_au_01-01-2026.zip"    # as fetched by scripts/download_data.sh

# Variants that are also simulated with MATSim. Each gets its own output folder
# holding the population *and* the MATSim scenario built from it, so the
# simulation results can always be joined back to the right persons.
SIMULATED = ["A_entd_local", "C_entd_urban"]
SIMULATION = {
    "gtfs_path": "gtfs_nantes",        # all *.zip in data/gtfs_nantes are cut and merged
    "osm_path": "osm_nantes",          # any *.osm.pbf in data/osm_nantes
    "java_memory": "20G",              # eqasim's default of 50G is more than WSL usually has
    "maven_skip_tests": True,
    # Wrapper written by scripts/setup_simulation.sh: eqasim's version check only
    # accepts a three-number Java version, Ubuntu's OpenJDK 25 can report four.
    "java_binary": str(Path.home() / "eqasim-tools" / "java"),
}


# Repeats over random seeds (work package: sampling noise). Seed 1 is the run above.
# Each repeat redraws the 10% census sample, the matching and the locations.
SEEDS = {2: 2234, 3: 3234, 4: 4234, 5: 5234}
REPEATED = ["A_entd_local", "C_entd_urban"]


def build(project, name, hts, filter_hts, urban_type, sampling_rate, simulate=False, random_seed=1234):
    config = {
        "processes": 4,
        "hts": hts,
        "filter_hts": filter_hts,
        "sampling_rate": sampling_rate,
        "random_seed": random_seed,
        "data_path": str(project / "data"),
        "output_path": str(project / "output" / name),
        "output_prefix": "nantes_",
        "output_formats": ["parquet", "geoparquet"],     # geoparquet carries the activity locations
        "regions": [],
        "departments": [44],
        "ban_path": "ban_nantes",
        "bdtopo_path": "bdtopo_nantes",
    }
    if urban_type:
        config["use_urban_type"] = True
        config["urban_type_path"] = URBAN_TYPE_FILE
        config["matching_attributes"] = ["urban_type", "*default*"]
    if urban_type and hts == "edgt_44":
        # The zone table of the regional survey, wherever the download left it under data/.
        found = sorted((project / "data" / "edgt_44_2015").rglob("07_denomination_perimetres_EDGT44*.xls"))
        if found:
            config["edgt_44_zones_path"] = found[0].relative_to(project / "data").as_posix()

    if simulate:
        config.update(SIMULATION)

    return {
        # One shared cache: synpp reuses every stage whose configuration is unchanged,
        # so the census, SIRENE and building stages run once for all variants, and
        # the road network and timetables once for all simulated variants.
        "working_directory": str(Path.home() / "eqasim-cache"),
        # matsim.output writes the MATSim scenario and tests it for two iterations.
        "run": ["synthesis.output", "matsim.output"] if simulate else ["synthesis.output"],
        "config": config,
    }


def write(out, project, name, config, quiet=False):
    if not quiet:      # synpp needs the folder to exist; the run scripts create it for the repeats
        (project / "output" / name).mkdir(parents=True, exist_ok=True)
    path = out / ("%s.yml" % name)
    with open(path, "w") as f:
        yaml.safe_dump(config, f, sort_keys=False)
    if not quiet:
        print("wrote", path)


def main(project, sampling_rate=0.1):
    project = Path(project).resolve()
    out = Path(__file__).parent
    (Path.home() / "eqasim-cache").mkdir(parents=True, exist_ok=True)

    for name, (hts, filter_hts, urban_type) in VARIANTS.items():
        write(out, project, name, build(project, name, hts, filter_hts, urban_type, sampling_rate))

    # The same variants with the territory analysis as the requested stage. It writes its
    # tables next to the population, so the output folder is the variant's own.
    for name, (hts, filter_hts, urban_type) in VARIANTS.items():
        config = build(project, name, hts, filter_hts, urban_type, sampling_rate)
        config["run"] = [TERRITORY_STAGE]
        config["config"].setdefault("urban_type_path", URBAN_TYPE_FILE)
        write(out, project, name + "_territory", config, quiet=True)
    print("wrote %d configs for the territory analysis stage (<variant>_territory.yml)" % len(VARIANTS))

    for name in SIMULATED:
        hts, filter_hts, urban_type = VARIANTS[name]
        write(out, project, name + "_sim",
              build(project, name + "_sim", hts, filter_hts, urban_type, sampling_rate, simulate=True))

    # Seed repeats, each as a population-only config and as a simulated one.
    for index, seed in SEEDS.items():
        for name in REPEATED:
            hts, filter_hts, urban_type = VARIANTS[name]
            for suffix, simulate in (("", False), ("_sim", True)):
                run = "%s_seed%d%s" % (name, index, suffix)
                write(out, project, run, build(project, run, hts, filter_hts, urban_type, sampling_rate,
                                               simulate=simulate, random_seed=seed), quiet=True)
    print("wrote %d seed-repeat configs (%s, seeds %s)" % (
        4 * len(SEEDS), ", ".join(REPEATED), ", ".join(map(str, SEEDS))))

    # Smoke tests: 0.1% sample, national ENTD donors. They fail fast on any missing
    # input; smoke_sim also builds the Java tools, the network and the timetables.
    write(out, project, "smoke", build(project, "smoke", "entd", False, False, 0.001))
    write(out, project, "smoke_sim", build(project, "smoke_sim", "entd", False, False, 0.001, simulate=True))


if __name__ == "__main__":
    main(sys.argv[1], float(sys.argv[2]) if len(sys.argv) > 2 else 0.1)
