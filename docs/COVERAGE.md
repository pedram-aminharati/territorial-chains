# The project description, task by task

The postdoctoral project "Représentation de la mobilité urbaine et rurale dans
les populations synthétiques" (IRT SystemX, PEPR MOBIDEC) lists six groups of
tasks. This page says, for each, what this pilot study covers, where to find
it, and what it does not cover. It was written on 20 Nov 2026 against the
published description. The pilot is one person's work over a few weeks on one
département, so "covered" means a first measured answer, not a finished one.

## 1. Characterise activity chains by territory

| Asked | In this study | Where | Not covered |
|---|---|---|---|
| Targeted literature review on urban, peri-urban and rural contexts | A reading of the six references of the description and of two papers on how staying home is measured, with what the study takes from each | `docs/LITERATURE.md` | The French literature on peri-urban and rural mobility |
| Indicators: number and sequence of activities, purposes, distances, commuting | Chain as a sequence, activities and tours per mobile person, share staying home, simple commutes, secondary activities, straight-line distance per person, home-to-work distance | `territorial_chains/chains.py`, `docs/RESULTS_SURVEYS.md`, `docs/RESULTS_LINKS.md` | Durations and start times |
| One analysis grid for observed and synthetic data | The same code scores surveys and populations: Hellinger distance over the most frequent chains inside a territory, and the gap between territories | `territorial_chains/compare.py`, `scripts/evaluate_population.py` | |

## 2. Analyse the French mobility surveys

| Asked | In this study | Where | Not covered |
|---|---|---|---|
| Prepare the data and rebuild chains | ENTD 2008, EMP 2019 and EDGT Loire-Atlantique 2015 read through eqasim's own cleaning stages | `scripts/survey_contrasts.py`, `scripts/regional_reference.py` | Other regional surveys |
| Build a territorial typology | INSEE urban units in four classes, and distance to the nearest large city in four bands | `docs/RESULTS_SURVEYS.md`, `docs/RESULTS_LINKS.md` | A peri-urban class (INSEE commuting areas), density grid |
| Quantify contrasts with weights and their limits | Weighted shares with bootstrap intervals, respondents per cell, the effect of the weight chosen in EMP 2019 (2.6% or 14.0% staying home) | `docs/RESULTS_SURVEYS.md`, `docs/UPSTREAM_NOTES.md` | |
| Links with socio-demographics | The rural gap recomputed with age, occupation and car ownership equalised, in both directions | `docs/RESULTS_LINKS.md` | Income, household structure, working time |
| Links with home and work places | Home-to-work distance by urban type of the home, surveys and populations | `docs/RESULTS_LINKS.md` | Flows between types of territory |
| Links with accessibility and public transport supply | Distance to Nantes or Saint-Nazaire as a first stand-in | `docs/RESULTS_LINKS.md` | Public transport supply and accessibility, although the six GTFS timetables used for the simulation would allow it |

## 3. Evaluate the populations eqasim produces

| Asked | In this study | Where | Not covered |
|---|---|---|---|
| Run the generation chain | Nine variants for Loire-Atlantique at 10%, two of them over five seeds, with eqasim-france v1.5.0 | `configs/make_configs.py`, `docs/RESULTS_PIPELINE.md`, `docs/SEEDS.md` | Other départements |
| Compute the same indicators and compare by territory | Every variant scored by urban type against the national survey and against the regional one, and by distance band | `docs/RESULTS_PIPELINE.md`, `docs/RESULTS_LOCAL.md`, `docs/RESULTS_LINKS.md` | |
| Compare by population group | Fidelity for people in work, retired people and others, all residents and rural residents | `docs/RESULTS_LINKS.md` | Finer groups, which the 1,667 local respondents of the national survey do not allow |
| Identify the priority gaps | Default matching ignores the home territory; the urban type option has a blind spot in 59 communes; the reference survey decides which variant is best; default matching loses the gap in tours even with a local survey | `README.md`, project page | |
| A reproducible quality protocol | One command per table, the analysis written as an eqasim stage that gives the same figures inside the pipeline, 53 tests, continuous integration | `eqasim_contrib/`, `tests/`, `.github/workflows/` | |

## 4. Develop methods that are sensitive to context

| Asked | In this study | Where | Not covered |
|---|---|---|---|
| Territorial variables in the generation | Urban type in matching, in four generative models, and taken from the home commune in a new matching stage | `docs/RESULTS_GENERATORS.md`, `docs/RESULTS_STRUCTURED.md` | Continuous descriptors (density, accessibility) |
| Matching approaches based on learning | A matching stage that draws the structure of the day from tables pooled between local and national respondents, with the pooling weight chosen by cross-validation, then matches a respondent inside that structure | `eqasim_contrib/synthesis/population/matched_structured.py` | Learned parents for the tables |
| Probabilistic models and generative sequence models | Bayesian network, autoregressive transformer, variational autoencoder, GAN | `territorial_chains/generators.py` | Times, durations and modes; tuning |
| Compare on fidelity | Hellinger distance on held-out respondents over five splits, with a floor | `docs/RESULTS_GENERATORS.md` | |
| Compare on the coherence of chains | Share of days that start and end at home, share of chains never reported | `docs/RESULTS_GENERATORS.md` | Coherence of timing |
| Compare on transferability between territories | Generators trained on the national survey and judged against the regional one; populations built from one survey judged against the other | `docs/RESULTS_GENERATORS.md`, `docs/RESULTS_LOCAL.md` | A second target territory |
| An article for Transportation Research Part C or CEUS | A four-page technical note with the results so far | `docs/TECHNICAL_NOTE.pdf` | The article |

## 5. Integrate into applied projects

| Asked | In this study | Where | Not covered |
|---|---|---|---|
| Integrate into eqasim simulation chains | The new matching stage replaces eqasim's through a configuration entry and ran in complete runs; two populations were simulated with MATSim over three seeds | `docs/RESULTS_STRUCTURED.md`, `docs/SIMULATION.md` | Simulation of the populations built with the new stage |
| Case studies on SERM design and on telework | None. They need the partners' scenarios and data | | All of it |
| Effects and limits for decision support | Under the urban type option rural residents make 18% fewer trips in every seed, and car kilometres change by less than 1.5% over the département | `docs/SIMULATION.md`, `docs/SEEDS.md` | A mode-choice model calibrated for the area |

## 6. Documentation, open code and dissemination

| Asked | In this study | Where | Not covered |
|---|---|---|---|
| Documented code, tests, reproducible scripts | A library with 53 tests, scripts from download to figures, setup guides | `README.md`, `tests/`, `scripts/`, `docs/SETUP_WSL.md` | |
| Open-source contribution to eqasim | Two stages and two patches written against v1.5.0 in the project's style, and eight observations made while running the pipeline | `eqasim_contrib/`, `docs/UPSTREAM_NOTES.md` | Nothing has been submitted upstream |
| Reports, publications, presentations | Project page, technical note, a ten-minute storyline | project page, `docs/TECHNICAL_NOTE.pdf`, `docs/TALK.md` | Publications |

## What the pilot does not claim

One département, one regional survey, small untuned models and one author who
had not run eqasim before. The findings are measured and reproducible. Whether
they hold elsewhere is the work the project describes.
