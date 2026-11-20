# Contributions prepared for eqasim-france

Four pieces written against eqasim-france v1.5.0 (commit `820aa017`), in that
project's own style so that each can be proposed upstream as it is. None has
been submitted yet.

| Piece | What it does | How it was checked |
|---|---|---|
| `analysis/synthesis/chains_by_territory.py` | A new analysis stage. Compares the activity chains of the population with the survey, by urban type of the home commune. | Run by synpp with eqasim's real ENTD stages on two saved populations. Not yet run inside a complete pipeline run. |
| `synthesis/population/matched_structured.py` | A matching stage that can replace eqasim's: it draws the structure of the day from a small network, then matches a respondent inside that structure. | Run by synpp with eqasim's real survey stages and matching function on the residents of a saved population, five draws per survey. Not yet run inside a complete pipeline run. |
| `patches/edgt_44_urban_type.patch` | Lets `use_urban_type` work with `hts: edgt_44`, which v1.5.0 cannot do. | eqasim's patched EDGT stages run on the real survey files, and feed the matching stage above in its trial. No population has been generated with it yet. |
| `patches/java_version_check.patch` | Fixes the Java version check, which fails when the version does not have exactly three numbers. | Unit test with six version strings. |

Tests are in `tests/test_eqasim_contrib.py`. The patch tests run when
`EQASIM_PATH` points to a git checkout of eqasim-france.

## Install

```bash
bash scripts/install_eqasim_contrib.sh                      # the two stages only
bash scripts/install_eqasim_contrib.sh edgt_44_urban_type   # the stages and one patch
```

The stages are new files and leave everything else untouched. A patch changes
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

## The matching stage

eqasim attaches a survey respondent to each resident in one step, by statistical
matching on the person's attributes. `synthesis.population.matched_structured`
does it in two.

1. The structure of the day is drawn from four small tables fitted on the
   survey: whether the person goes out, the primary activity, the number of
   home-based tours and the number of secondary activities. The urban type of
   the home acts on going out and on the number of tours, the two things the
   survey analysis found to differ by territory.
2. A respondent is drawn among those who reported a day with that structure,
   with eqasim's own `statistical_matching` on the usual attributes.

The stage returns the same table as `synthesis.population.matched`, so the rest
of the pipeline is unchanged. It replaces the original through synpp's aliases:

```yaml
aliases:
  synthesis.population.matched: synthesis.population.matched_structured
```

Three things differ from matching in one step.

- **Territory without thin cells.** The urban type enters through two small
  tables, not through a cell for every combination of all attributes.
- **Local and national respondents are pooled.** With `filter_hts` off, each
  table is estimated for the study area with the national table as a prior. The
  weight of the prior, in pseudo-respondents, is chosen by cross-validation on
  the respondents of the study area (`structure_prior_strength: auto`, or a
  number).
- **The urban type is the one of the home commune.** The stage reads it after
  homes are placed, so residents of municipalities under 10,000 inhabitants are
  no longer all labelled rural (note 2 in `docs/UPSTREAM_NOTES.md`).

`scripts/try_matching_stage.py` runs the stage on the residents of a population
that already exists and scores the chains it gives them, without a pipeline
run. On the residents of variant A, mean over five draws (Hellinger distance,
central city, suburb, isolated city, rural):

| Population | Against the national survey | Against the regional survey |
|---|---|---|
| A, default, local donors | 0.087, 0.077, 0.116, 0.129 | 0.100, 0.089, 0.101, 0.121 |
| C, urban type, national donors | 0.055, 0.064, 0.053, 0.042 | 0.127, 0.124, 0.143, 0.166 |
| S, this stage, national survey as source | 0.046, 0.050, 0.069, 0.053 | 0.114, 0.112, 0.108, 0.140 |
| T, this stage, regional survey as source | 0.142, 0.129, 0.154, 0.146 | 0.037, 0.028, 0.047, 0.051 |

S is about as close to the national survey as C and lies between A and C
against the regional survey, which it never sees. The cross-validation chose a
prior weight of 30 in three draws and 100 in two. Row T needs the patch below
and is scored against its own source in the last column, so that column shows
that the stage runs with a local survey, not that it is right.

Known limits. Only 13% of the respondents S attaches live in Loire-Atlantique
(79% in variant B), because inside one structure the cells that include the
département rarely hold 20 respondents; putting `departement_id` earlier in
`matching_attributes` would trade attribute matches for local respondents. The
parents of each table are fixed in the code, not learned. The stage runs in one
process. Distances, modes and the simulation have not been looked at, since no
population has been generated with it: `configs/make_configs.py` writes
`S_entd_structured` and `T_edgt44_structured` for that.

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
