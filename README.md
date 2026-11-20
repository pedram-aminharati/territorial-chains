# Territorial chains: a pilot study on eqasim

Does a synthetic population reproduce the difference between an urban day and a
rural day, and against which survey should that be judged? This repository
measures it for the open-source [eqasim](https://github.com/eqasim-org/eqasim-france)
pipeline (v1.5.0) on Loire-Atlantique (Nantes and its hinterland).

**Project page with all figures:** <https://pedram-aminharati.github.io/territorial-chains/>
(`docs/index.html`, rebuilt from the result tables with `python site/build_site.py`).

**Four-page technical note:** `docs/TECHNICAL_NOTE.pdf` (source `docs/TECHNICAL_NOTE.md`).

[![tests](https://github.com/pedram-aminharati/territorial-chains/actions/workflows/tests.yml/badge.svg)](https://github.com/pedram-aminharati/territorial-chains/actions/workflows/tests.yml)

## What was done

| Step | Where |
|---|---|
| Indicator library for activity chains, weighted survey statistics, fidelity and contrast measures | `territorial_chains/`, `tests/` |
| ENTD 2008 and EMP 2019 analysed by urban type, through eqasim's own cleaning stages | `docs/RESULTS_SURVEYS.md` |
| Five eqasim populations for Loire-Atlantique (10% sample) scored by territory | `docs/RESULTS_PIPELINE.md` |
| Bayesian-network, transformer, variational-autoencoder and GAN generators against matching, on held-out respondents | `docs/RESULTS_GENERATORS.md` |
| Two populations simulated with MATSim (OpenStreetMap network, six GTFS timetables) | `docs/SIMULATION.md` |
| Repeats over five random seeds, three of them simulated | `docs/SEEDS.md` |
| The regional survey (EDGT Loire-Atlantique 2015) as a second reference | `docs/RESULTS_LOCAL.md` |
| Map by intercommunalité and commune, matching explorer | project page |
| What was found in eqasim on the way | `docs/UPSTREAM_NOTES.md` |
| A matching stage that can replace eqasim's, tried on existing residents and in complete runs | `docs/RESULTS_STRUCTURED.md` |
| That stage, the territory analysis as an eqasim stage, and two patches for eqasim-france | `eqasim_contrib/` |
| Four more populations generated end to end: the new stage, and eqasim's matching fed with the regional survey | `docs/RESULTS_STRUCTURED.md` |
| Age, occupation and car ownership, commuting, population groups, distance to the city | `docs/RESULTS_LINKS.md` |
| Generators trained on the national survey and judged against the regional one | `docs/RESULTS_GENERATORS.md` |
| Targeted reading of the references of the project description | `docs/LITERATURE.md` |
| The project description, task by task: what is covered and what is not | `docs/COVERAGE.md` |

## What was found

1. **Default matching ignores the home territory.** In eqasim's default
   configuration, 16% of rural residents receive the day of a rural survey
   respondent; with the `use_urban_type` option, all of them do. Activity
   chains are the same in every kind of place by default.
2. **The option has a blind spot.** The census does not name the commune of
   people in municipalities under 10,000 inhabitants, and the pipeline labels
   them rural. In 59 urban communes, home to 18% of residents, nobody gets a
   donor from their own kind of place.
3. **Which survey is the reference decides who wins.** Against the national
   survey split by urban type, the urban-type population is the closest in
   every territory. Against the département's own survey it is the furthest:
   nationally rural residents stay home more often (16.8%), in
   Loire-Atlantique they do not (9.4%), and three quarters of the donors the
   option brings in live elsewhere in France. Type of territory is not a
   sufficient description of a territory. The option is not simply worse
   locally: both surveys find that rural residents make fewer home-based
   tours, and only the urban-type population reproduces that.
4. **Downstream, trips change and distance barely does.** Simulated with
   MATSim, the urban-type population makes 18% fewer rural trips in every seed;
   car kilometres per resident differ by a few percent by territory and by less
   than 1.5% over the département.
5. **A generator sees territory or it does not.** On the national survey,
   matching, a Bayesian network, a transformer and a variational autoencoder
   reproduce the rural pattern only when territory is among their inputs; no
   model is clearly better than matching with the urban type on that test, and
   a plain GAN is far behind all of them.
6. **A generator can sit inside the pipeline, and pooling only goes so far.**
   A matching stage that first draws the structure of the day, with tables
   pooled between local and national respondents, is as close to the national
   survey as the urban-type option and lies between the two eqasim variants
   against the regional survey. With the 1,798 respondents the national survey
   has in the département, pooling does not recover what the regional survey
   shows; fed with the regional survey, the same stage follows it by territory.
   In complete runs of the pipeline, eqasim's default matching fed with the
   regional survey loses the gap in home-based tours between rural and
   central-city residents (−0.002 against −0.134 observed); the urban type
   option (−0.149) and the new stage (−0.124) keep it.
7. **What a generator learns about territory transfers for one indicator and
   not for another.** Trained on the national survey and judged against the
   regional one, the generators that see territory reproduce the regional gap
   in tours and overstate rural staying home (14% to 15% against 9.4%); those
   that do not see it do the reverse. No generator comes near the floor.
8. **Composition explains part of the picture, not all of it.** The national
   gap in staying home between rural and central-city residents does not
   depend on age, occupation or car ownership (+5.1 to +5.5 points whatever is
   equalised). The regional one is nil, and becomes 2 to 3 points once car
   ownership is equalised. Beyond 30 km from Nantes and Saint-Nazaire more
   people stay home (11.0% against 8.5% to 8.8%), which the four urban types
   hide and no variant reproduces.
9. **EMP 2019 is read with the wrong weight for immobility.** Read with person
   weights, as the pipeline does, 2.6% of people stay home on a weekday; with
   the survey's day weights, 14.0%.

Every number is one command away from the result tables in `results/`, and the
limits are listed on the project page.

## Run it

```bash
pip install -e ".[dev]"
pytest                                           # 53 tests

bash scripts/setup_wsl.sh                        # eqasim-france v1.5.0 and its environment
bash scripts/download_data.sh                    # open data: INSEE, IGN, data.gouv.fr, SDES
bash scripts/run_variants.sh A_entd_local B_entd_national C_entd_urban D_emp_national E_emp_urban
python scripts/survey_contrasts.py ~/eqasim-france data results
python scripts/evaluate_population.py output/C_entd_urban entd data/urban_type/UU2020_au_01-01-2026.zip results
python scripts/benchmark_generators.py ~/eqasim-france results 5

bash scripts/setup_simulation.sh && bash scripts/download_simulation_data.sh
bash scripts/run_simulation.sh A_entd_local_sim C_entd_urban_sim
bash scripts/run_seeds.sh && python scripts/summarise_seeds.py results

bash scripts/download_edgt.sh
python scripts/regional_reference.py ~/eqasim-france data results
python scripts/evaluate_population.py output/C_entd_urban entd data/urban_type/UU2020_au_01-01-2026.zip results edgt_44

python scripts/export_page_data.py output data/urban_type/UU2020_au_01-01-2026.zip data/iris_2024/CONTOURS-IRIS_3-0__GPKG_LAMB93_FXX_2024-01-01.7z
python site/build_site.py

bash scripts/install_eqasim_contrib.sh           # copies the two stages into ~/eqasim-france
bash scripts/run_territory_stage.sh C_entd_urban # the same scoring, run inside eqasim
python scripts/try_matching_stage.py ~/eqasim-france data output/A_entd_local data/urban_type/UU2020_au_01-01-2026.zip results
bash scripts/run_remaining.sh                    # populations S, T, F and G and the territory stage, in one go
python scripts/regional_source_age.py output data/urban_type/UU2020_au_01-01-2026.zip results

python scripts/territory_links.py ~/eqasim-france data output data/urban_type/UU2020_au_01-01-2026.zip data/iris_2024/CONTOURS-IRIS_3-0__GPKG_LAMB93_FXX_2024-01-01.7z results
python scripts/benchmark_transfer.py ~/eqasim-france results 3
```

Which environment for what: the library and its tests need only numpy and
pandas. The scoring scripts read parquet tables and Excel workbooks
(`pip install -e ".[analysis]"`), or run as they are inside the eqasim-france
environment. `survey_contrasts.py`, `regional_reference.py`,
`try_matching_stage.py`, `territory_links.py` and the matching generator import
eqasim itself, so they need that environment. The generators
need `".[models]"`. The pipeline and simulation steps need what
`docs/SETUP_WSL.md` and `docs/SIMULATION.md` list (uv, a Java 25 JDK, Maven).

`scripts/demo_matching_flattening.py` is a **simulation on invented data**: it
calls eqasim's own `statistical_matching`, unchanged, and shows the mechanism
behind finding 1 in isolation.

## Layout

```
territorial_chains/   chains.py (chains, indicators)  weighted.py (survey statistics)
                      compare.py (fidelity, contrast retention, gaps with composition equalised)
                      generators.py (matching, Bayesian network, transformer, variational autoencoder, GAN)
                      simulation.py (mode shares and travel per resident from MATSim trips)
tests/                pytest suite
eqasim_contrib/       two stages and two patches written for eqasim-france, with their own README
configs/              make_configs.py: eqasim configs for departement 44 (populations, simulations, seeds)
scripts/              setup, download, run and scoring scripts (see "Run it")
reference/            intercommunalité of each commune; communes merged since 2015
docs/                 index.html (project page), result notes, setup guides
results/              CSV tables behind every figure
site/                 build_site.py and template.html: the project page generator
```

## Licence and credits

Code: GNU General Public License v2.0, the licence of eqasim-france, whose
matching function this project calls (see `LICENSE`). Data: INSEE, IGN, SDES
(ENTD 2008, EMP 2019), Département de Loire-Atlantique (EDGT 2015),
transport.data.gouv.fr and OpenStreetMap contributors, under their open
licences; none of it is redistributed here.

Pedram Aminharati, November 2026.
