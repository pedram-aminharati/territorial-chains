# Territorial evaluation of activity chains in eqasim synthetic populations

**A pilot study on Loire-Atlantique.** Technical note, Pedram Aminharati, 20 November 2026.
Code and tables at github.com/pedram-aminharati/territorial-chains, figures at
pedram-aminharati.github.io/territorial-chains.

## 1. Question

eqasim gives each person of a synthetic population the recorded day of a survey
respondent who resembles them. The match is made on sex, car ownership, age class,
socio-professional class and, when at least 20 respondents remain, the
département. Where respondents are scarce, attributes are dropped from the end of
that list, so the place a person lives is the first thing the matching gives up.

This note measures what that does to the activity chains of urban and rural
residents, whether the `use_urban_type` option repairs it, and what it changes
once the population is simulated. A second question appeared on the way and
proved as important as the first. A population for one département can be judged
against the national survey split by type of territory, or against the
département's own survey, and the two do not give the same answer.

## 2. Data and method

Populations were generated with eqasim-france v1.5.0 for Loire-Atlantique at a
10% sampling rate, about 139,000 matched residents each. Five variants differ
only in the matching step.

| Variant | Survey | Donors | Matching attributes |
|---|---|---|---|
| A | ENTD 2008 | Loire-Atlantique only | default |
| B | ENTD 2008 | national | default |
| C | ENTD 2008 | national | urban type first, then default |
| D | EMP 2019 | national | default |
| E | EMP 2019 | national | urban type first, then default |

Territory is the INSEE urban-unit status of the home commune, in four classes
(central city, suburb, isolated city, rural). A chain is the ordered list of a
person's activities. Three surveys were read through eqasim's own cleaning code.
ENTD 2008 has 17,997 diary respondents, of whom 1,798 live in the département.
EMP 2019 has 195 there. The regional survey, EDGT Loire-Atlantique 2015, has
20,799 respondents. Its home zones were mapped to today's communes to give each
respondent an urban type.

Two measures are used throughout. Fidelity inside a territory is the Hellinger
distance between generated and observed chain distributions, over the 25 most
frequent chains and a pooled remainder. The contrast between territories is the
rural minus central-city gap of an indicator, in the population and in the
survey. Variants A and C were repeated over five random seeds, and three seeds of
each were simulated with MATSim on an OpenStreetMap network with six GTFS
timetables. Observed and generated chains go through the same code, which is
covered by 51 tests.

## 3. Results

### 3.1 Default matching ignores the home territory, and the option has a blind spot

Share of residents whose respondent lives in the same type of territory.

| Variant | Central | Suburb | Isolated | Rural | Respondents from the département |
|---|---|---|---|---|---|
| A, default, local | 42% | 39% | 13% | 16% | 100% |
| C, urban type | 92% | 85% | 43% | 100% | 26% |

By default a rural resident receives a rural respondent's day 16% of the time.
The option brings this to 100% for rural residents but only to 43% in isolated
cities. The census does not name the commune of people living in municipalities
under 10,000 inhabitants, and the pipeline labels all of them rural before homes
are placed. In 59 communes that INSEE classes as urban, home to 18% of residents,
nobody receives a respondent from their own kind of place.

### 3.2 Which survey is the reference decides which variant is best

Share of people staying home on a weekday, and Hellinger distance of each
variant to each survey (seed 1).

| | Central | Suburb | Isolated | Rural |
|---|---|---|---|---|
| Staying home, national survey | 12.2% | 10.1% | 13.1% | 16.8% |
| Staying home, regional survey | 8.8% | 8.9% | 9.3% | 9.4% |
| Staying home, A | 9.6% | 9.1% | 8.8% | 8.5% |
| Staying home, C | 10.7% | 10.8% | 14.4% | 16.5% |
| Distance to the national survey, A | 0.087 | 0.077 | 0.116 | 0.129 |
| Distance to the national survey, C | 0.055 | 0.064 | 0.053 | 0.042 |
| Distance to the regional survey, A | 0.100 | 0.089 | 0.101 | 0.121 |
| Distance to the regional survey, C | 0.127 | 0.124 | 0.143 | 0.166 |

Against the national survey the option gives the closest population in every
territory. Against the regional survey it gives the furthest, in every territory
and in all five seeds. Nationally, rural residents stay home more often. In
Loire-Atlantique they do not, and the 254 rural respondents of the national
survey who live in the département agree with the regional survey on this (5.8%).
Three quarters of the respondents the option brings in live elsewhere in France,
and they carry the national rural pattern with them. Type of territory is not a
sufficient description of a territory.

### 3.3 The option is right on tours and wrong on staying home

Rural minus central-city gap. A and C are means over five seeds.

| | Staying home | Tours per mobile person | Distance per mobile person |
|---|---|---|---|
| National survey | +4.6 points | −0.11 | +14.4 km |
| Regional survey | +0.6 points | −0.13 | +13.1 km |
| A | −0.7 points | +0.03 | +13.3 km |
| C | +6.2 points | −0.10 | +15.6 km |

Both surveys find fewer home-based tours and longer distances for rural
residents. Every variant keeps the distance gap, because distances come from the
location step and not from the matched chain. Only C reproduces the gap in tours.
So the option is not simply worse locally. It brings in one difference that both
surveys support and one that the regional survey contradicts.

### 3.4 Once simulated, trips change and car distance barely does

Over three seeds, rural residents make 18% fewer trips under C than under A
(17.5% to 18.7%). Car kilometres per resident change by −4.8% in central cities,
+1.4% in suburbs, +2.4% in isolated cities and −3.5% in rural communes. These
differences keep their sign in every seed and nearly cancel over the département
(−0.8%). The mode-choice model is the Île-de-France calibration, so only
differences between variants are read, not levels.

About 3% of planned trips are missing from the simulation output. The log shows
why. When the last iteration ends, about 4,800 agents have not finished their day
and none was removed, which accounts for 95% of the persons concerned. What holds
them up was not identified.

### 3.5 A generator reproduces the territorial pattern only if it sees territory

Five families were trained on 80% of the national respondents and asked to
propose a chain for the other 20% from their attributes alone, over five random
splits. Each was run without and with the urban type among its inputs.

| Family | Rural staying home, without / with territory | Distance for rural residents, with territory | Distance for all, with territory |
|---|---|---|---|
| Statistical matching (eqasim) | 12.5% / 17.2% | 0.093 | 0.054 |
| Bayesian network | 12.6% / 16.3% | 0.099 | 0.047 |
| Transformer | 12.4% / 16.8% | 0.105 | 0.069 |
| Variational autoencoder | 12.0% / 15.3% | 0.092 | 0.051 |
| GAN | 15.0% / 19.9% | 0.184 | 0.149 |

Held-out rural respondents stay home 16.8% of the time. The distance between two
samples of the survey itself is 0.085 for rural residents and 0.046 for all.
What decides the result is whether the model sees territory, not which model it
is. No model is clearly better than matching with the urban type. The Bayesian
network and the autoencoder are level with it, the transformer is behind, and a
plain untuned GAN is far behind. Structure search never linked territory to the
chain on its own, so that edge had to be imposed.

### 3.6 A generator that fits inside the pipeline

The models above write the order of activities only, without times or modes, so
they cannot replace matching in eqasim. A matching stage was written that can.
It draws the structure of the day from four small tables (going out, primary
activity, number of tours, number of secondary activities), then matches a real
respondent inside that structure with eqasim's own function. The tables pool
respondents of the study area with national ones, with a weight chosen by
cross-validation, and the urban type is taken from the home commune itself,
which removes the blind spot of section 3.1. The stage replaces eqasim's matching
through a configuration entry.

Tried on the residents of variant A, mean of five draws.

| Population | Reference | Central | Suburb | Isolated | Rural |
|---|---|---|---|---|---|
| New stage, national survey as source | national survey | 0.046 | 0.050 | 0.069 | 0.053 |
| New stage, national survey as source | regional survey | 0.114 | 0.112 | 0.108 | 0.140 |
| New stage, regional survey as source | regional survey | 0.037 | 0.028 | 0.047 | 0.051 |

With the national survey as source the stage is about as close to that survey as
C, and lies between A and C against the regional survey, which it never sees.
Pooling does not recover the local pattern, because the national survey has too
few respondents in the département. Fed with the regional survey, the stage
follows it by territory. That last row compares a population with its own source,
so it shows that the stage works with a local survey, not that the result is
right. No full pipeline run has been made with the stage yet.

## 4. What was prepared for eqasim

Four pieces were written against v1.5.0 in the project's own style and are kept
in `eqasim_contrib/`. The first is the matching stage of section 3.6. The second
is an analysis stage that scores chains by urban type inside the pipeline. Run
with eqasim's survey stages on a saved population, it reproduces this study's own
scoring. The third is a patch that gives respondents of the regional survey an
urban type, which v1.5.0 cannot do. The fourth fixes the Java version check,
which stops the pipeline with recent JDKs. Eight observations made while running
the pipeline are written up in `docs/UPSTREAM_NOTES.md`. One of them concerns EMP
2019, where 2.6% of people stay home on a weekday with the person weights the
pipeline reads, and 14.0% with the survey's day weights.

## 5. Limits

- One département. Whether others follow the national pattern or look like
  Loire-Atlantique is untested.
- The two references differ in more than place. They are seven years apart, and
  the regional survey mixes face-to-face and telephone interviews by territory.
  The direction of the reversal is supported by two samples. Its size is not
  established.
- Variants B, D and E have one seed. A and C have five, three of them simulated.
- Four classes of urban type are coarse. A finer description of territory may
  show contrasts that this one hides.
- The new matching stage and the patches have been tested on saved populations
  and on the survey files, not in a complete pipeline run.

## 6. Next steps

Generate populations with the new stage and with the regional survey as source,
and score them on distances and in simulation. Replace the four urban types with
continuous descriptors of territory such as density and accessibility. Repeat the
comparison in a second département that has its own survey. Propose the analysis
stage and the two patches to eqasim-france.

## References

Hörl, S. and Balac, M. (2021). Synthetic population and travel demand for Paris
and Île-de-France based on open and publicly available data. Transportation
Research Part C, 130, 103291.

Joubert, J. W. and de Waal, A. (2020). Activity-based travel demand generation
using Bayesian networks. Transportation Research Part C, 120, 102804.

Shone, F. and Hillel, T. (2024). Deep generative models for activity sequences,
as cited in the position description.
