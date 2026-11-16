# Contributions prepared for eqasim-france

Three pieces written against eqasim-france v1.5.0 (commit `820aa017`), in that
project's own style so that each can be proposed upstream as it is. None has
been submitted yet.

| Piece | What it does | How it was checked |
|---|---|---|
| `analysis/synthesis/chains_by_territory.py` | A new analysis stage. Compares the activity chains of the population with the survey, by urban type of the home commune. | Run by synpp with eqasim's real ENTD stages on two saved populations. Not yet run inside a complete pipeline run. |
| `patches/edgt_44_urban_type.patch` | Lets `use_urban_type` work with `hts: edgt_44`, which v1.5.0 cannot do. | eqasim's patched EDGT stages run on the real survey files. No population has been matched with it yet. |
| `patches/java_version_check.patch` | Fixes the Java version check, which fails when the version does not have exactly three numbers. | Unit test with six version strings. |

Tests are in `tests/test_eqasim_contrib.py`. The patch tests run when
`EQASIM_PATH` points to a git checkout of eqasim-france.

## Install

```bash
bash scripts/install_eqasim_contrib.sh                      # the stage only
bash scripts/install_eqasim_contrib.sh edgt_44_urban_type   # the stage and one patch
```

The stage is a new file and leaves everything else untouched. A patch changes
existing stages, and synpp runs a stage again, with everything that depends on
it, when its code has changed. For `edgt_44_urban_type` that only concerns
populations built from the regional survey. For `java_version_check` it concerns
every stage that calls Java, so the network and timetable conversion would run
again. If you already work around the check with the wrapper from
`scripts/setup_simulation.sh`, there is no need to apply that patch locally.

## The analysis stage

```bash
bash scripts/run_territory_stage.sh C_entd_urban
```

or, in any eqasim configuration, add `analysis.synthesis.chains_by_territory`
to `run` and set `urban_type_path`. The stage reads
`synthesis.population.enriched`, `synthesis.population.activities`,
`synthesis.population.spatial.home.zones`, `data.spatial.urban_type` and
`data.hts.selected`. It returns three tables and writes them to the output
folder as `<prefix>chains_by_territory_<name>.csv`:

- `indicators`, one row per urban type and one for the whole area: matched
  residents, share staying home, activities and home-based tours per mobile
  person, in the population and in the survey, the Hellinger distance between
  the two chain distributions, and the share of residents whose commune the
  census withholds.
- `chains`, the share of each of the most frequent survey chains in both
  (`territory_chains_top_k`, 25 by default).
- `donors`, for each home urban type the urban type of the matched respondents.

The survey side needs the urban type of the respondents. ENTD and EMP carry it,
EGT carries it with `use_urban_type`, and the regional survey of
Loire-Atlantique carries it once the patch below is applied. Without it the
stage reports the population side and the overall comparison only.

What the check showed: on variant C the stage gives the same numbers as this
repository's own scoring script, which was written separately (Hellinger
distances of 0.055, 0.064, 0.053 and 0.042 by urban type, and the same donor
table). On variant A the population side is identical. The survey side differs
there by design, because the stage compares with the survey selected for the
run, which `filter_hts` reduces to 1,667 local respondents, while the project
page compares with the national survey.

In the variants with national donors, between 23 and 105 matched persons have
no home commune in the pipeline output. The stage counts them, reports the
number in the log and leaves them out.

## Urban type for the regional survey

`data.hts.edgt_44.cleaned` does not keep where a respondent lives, so matching
on the urban type is not possible with this survey. The patch reads the home
zone of each household, looks up its commune in the zone table published with
the survey (`07_denomination_perimetres_EDGT44_DTIR_D30_D10_D2.xls`, sheet `ZF`,
expected next to the three survey files or given with `edgt_44_zones_path`), brings the twenty communes merged
since 2015 to their current code, and takes the urban type from
`data.spatial.urban_type`.

Run on the survey files, the patched stages give 6,278 respondents in central
cities, 7,266 in suburbs, 3,765 in isolated cities and 3,490 in rural communes
when the urban-type table covers the whole country. Inside eqasim that table
only covers the study area. With `departments: [44]`, the 168 respondents of
the survey who live in communes that belong to Maine-et-Loire today fall back
to rural, as the EGT stage does for respondents outside its area. That is 0.8%
of the 20,799 respondents, all of them in isolated cities.

`configs/make_configs.py` writes a variant for it, `G_edgt44_urban`. It has not
been generated.

## Java version check

`matsim/runtime/java.py` unpacks the version into exactly three numbers. Ubuntu's
OpenJDK 25 reports four and the pipeline stops before any stage runs. The patch
reads the major number only and accepts `25`, `17.0.9`, `25.0.1.1` and `21-ea`.
Versions below 17 are still refused. The issue text is in
`docs/UPSTREAM_NOTES.md`.
