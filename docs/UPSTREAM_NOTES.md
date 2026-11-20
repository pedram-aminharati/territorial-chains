# Notes for eqasim-france, from running v1.5.0 on Loire-Atlantique

Things noticed while running the pipeline (commit `820aa017`, eqasim-java commit
`fc85693`). Each has what was observed, how sure it is, and what would settle it.
Nothing here has been reported upstream yet.

## Reproduced on this project's machine

**1. The Java version check fails on version strings that do not have exactly three numbers.**
`matsim/runtime/java.py`, `validate()`: `major, minor, _ = version_number.split('.')`.
With Ubuntu's OpenJDK 25 the pipeline stopped before running anything with
`ValueError: too many values to unpack (expected 3)`. Only the major number is
used afterwards. Worked around here with a wrapper passed as `java_binary`
(`scripts/setup_simulation.sh`). Draft issue:

> **Java version check fails when `java -version` reports more or fewer than three components**
> `matsim/runtime/java.py` unpacks the version into exactly three parts. A build reporting
> four (for example `25.0.1.1`) or one (`25`) raises `ValueError` during validation, before any
> stage runs. Only the major version is needed for the check, so
> `major = int(version_number.split(".")[0])` would be enough. Seen with eqasim-france v1.5.0
> on Ubuntu (WSL 2), OpenJDK 25.

**2. `use_urban_type` cannot give small-town residents donors from small towns.**
`data/census/cleaned.py` sets `urban_type = "none"` when the census commune is
undefined, which is the case for every municipality under 10,000 inhabitants.
In the variant with the option on, all residents of 59 communes that INSEE
classes as urban (18% of matched residents) received rural donors
(`results/map/units.csv`). The home commune is known later in the pipeline, after
matching.

**3. With `filter_hts` and one département, the donor pool loses everyone who left it that day.**
`data/hts/entd/filtered.py` drops respondents with a trip starting or ending
outside the study area: 131 of the 1,798 ENTD respondents living in
Loire-Atlantique, all of them mobile. This is the documented behaviour; the
consequence for a single-département study is a pool with fewer mobile people.

**4. EMP 2019 read with person weights gives 2.6% of people at home on a weekday.**
The EMP stages weight persons by `pond_indC`; `POND_JOUR` is not read. With the
day weight the share is 14.0%, and populations built from EMP inherit about 3%.
The SDES note on the public files prescribes `pond_jour` for local mobility
(details in `docs/RESULTS_SURVEYS.md`); the note gives no rule for immobility
itself, so the 14.0% is this study's application of its rule.

**5. Households whose members never pass by home are written without a home commune.**
0 in the variant with local donors of the national survey; 23 to 105 matched
persons in the four variants with national donors, in every seed, and 37 to 101
in the four populations generated later (S, T, F and G). `iris_id`,
`commune_id` and `departement_id` are all missing in `households`. Inside the
pipeline every household has a commune: the analysis stage, which reads
`synthesis.population.spatial.home.zones`, counts all 138,915 persons. The
codes are lost in `synthesis/output.py`, which takes them from the activities
with purpose `home` (the merge after "Prepare households"). A one-person
household whose matched day starts and ends away from home has no such
activity. Checked on two populations: the 105 households concerned in C and the
39 in F have no home activity at all, and they are exactly the households
without one. Taking the codes from `synthesis.population.spatial.home.zones`
would avoid it. Not patched here.

**6. About 3% of the population's trips are missing from `eqasim_trips`, because some agents never finish their day.**
In both simulated variants, 3% of persons have fewer simulated trips than
planned (5,089 in A, 4,819 in C). Their recorded trips are always the first ones
of the day, three quarters are by car, and about 1,650 persons have none. The
simulation log explains most of it: when the last iteration ends, at 30:00, QSim
reports 4,830 agents in A and 4,592 in C that have not finished their plan, and
it removed none during the run (`lost=0`). That is 95% of the persons with
missing trips in both variants. Their last recorded trip starts around noon
(median 12.1 h, against 17.8 h for everyone else), so these agents are held up
for the rest of the day, not cut off at the end. Whether they sit in a blocked
queue or wait for a service that never comes was not identified; it needs the
events file, which is not kept. The count per iteration falls from 9,687 to
about 4,700 in A and stays there, so more iterations would not remove it.
Tables: `results/<variant>_sim/sim_unfinished.csv`.

## Read in the code, not tested

**7. The Java requirement is 25, not 17.** The documentation and the check ask
for Java 17; the pinned eqasim-java commit sets `maven.compiler.source` and
`target` to 25 in `pom.xml`. The build was done here with JDK 25; whether it
fails with 17 or 21 was not tried.

**8. `matsim.simulation.full_run` may fail its last assertion.** It asserts
`simulation_output/output_events.xml.gz`, while `matsim.simulation.run` asserts
`output_events.xml.zst` and this MATSim version writes `.zst`. The full-run stage
was not used here (the simulation was started from the jar instead), so this is
unverified.

## Prepared contributions

Written against v1.5.0 and kept in `eqasim_contrib/`, with what was tested and
what was not in its README. None has been submitted.

- `analysis.synthesis.chains_by_territory`, a chain analysis by urban type next
  to the existing one by age and sex. Run inside the pipeline on variant C, it
  reproduces this repository's own scoring.
- `synthesis.population.matched_structured`, a matching stage that draws the
  structure of the day first and takes the urban type from the home commune,
  which removes the blind spot of note 2. It replaces
  `synthesis.population.matched` through synpp's aliases. Tried on the residents
  of a saved population and then in two complete runs
  (`docs/RESULTS_STRUCTURED.md`).
- A patch that keeps the home zone of EDGT Loire-Atlantique respondents and
  derives their urban type, so that `use_urban_type` can be combined with
  `hts: edgt_44` (note 2 still applies to the census side). Three populations
  were generated with it.
- A patch for the Java version check of note 1.
