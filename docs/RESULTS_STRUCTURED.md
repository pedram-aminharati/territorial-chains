# A matching stage that draws the structure of the day first

Run on 16 Nov 2026 with `scripts/try_matching_stage.py`. The stage is
`eqasim_contrib/synthesis/population/matched_structured.py`; its design is
described in `eqasim_contrib/README.md`.

## What was run

The stage was run by synpp, with eqasim's own survey stages and matching
function, on the 138,915 matched residents of variant A (seed 1) and their
home communes. No pipeline run was made: in eqasim the chain of a resident is
the chain of the attached respondent, so the respondent is enough to score
every chain indicator. Five draws per survey used as source. Scored against
the national survey (ENTD 2008, by urban type) and the regional survey (EDGT
Loire-Atlantique 2015), with the same code as the other populations.

## Hellinger distance to each survey

Mean over five draws, range in brackets. A and C are the seed-1 populations.

| | Central | Suburb | Isolated | Rural |
|---|---|---|---|---|
| **Against the national survey** | | | | |
| A, default, local donors | 0.087 | 0.077 | 0.116 | 0.129 |
| C, urban type, national donors | 0.055 | 0.064 | 0.053 | 0.042 |
| S, structure first, national survey | 0.046 [0.041, 0.050] | 0.050 [0.045, 0.054] | 0.069 [0.067, 0.071] | 0.053 [0.042, 0.059] |
| **Against the regional survey** | | | | |
| A | 0.100 | 0.089 | 0.101 | 0.121 |
| C | 0.127 | 0.124 | 0.143 | 0.166 |
| S | 0.114 [0.111, 0.119] | 0.112 [0.106, 0.117] | 0.108 [0.107, 0.110] | 0.140 [0.135, 0.145] |

S never sees the regional survey. It is about as close to the national survey
as C (closer in central cities and suburbs, further in isolated cities and
rural communes) and lies between A and C against the regional survey in every
territory.

## Staying home and tours under S

| | Central | Suburb | Isolated | Rural |
|---|---|---|---|---|
| Staying home, S | 10.7% | 9.2% | 12.0% | 14.6% |
| Staying home, regional survey | 8.8% | 8.9% | 9.3% | 9.4% |
| Staying home, national survey | 12.2% | 10.1% | 13.1% | 16.8% |
| Tours per mobile person, S | 1.67 | 1.62 | 1.58 | 1.60 |
| Tours per mobile person, regional survey | 1.71 | 1.70 | 1.60 | 1.57 |
| Tours per mobile person, national survey | 1.64 | 1.57 | 1.59 | 1.53 |

The pooled tables stay close to the national pattern for staying home. The
national survey has 254 rural respondents in Loire-Atlantique, split in the
"goes out" table over eight occupation classes, and the cross-validation chose
a prior weight of 30 pseudo-respondents in three draws and 100 in two. With
that little local information the stage cannot recover what the regional survey
shows, and it should not be expected to.

## With the regional survey as source (T)

The same stage fed with the regional survey (20,799 respondents, urban type
from the patch in `eqasim_contrib/`) gives 0.037, 0.028, 0.047 and 0.051 against
that survey and 8.6%, 8.6%, 9.4% and 10.3% of residents staying home. This is a
comparison of a population with its own source: it shows that the stage runs
with a local survey and follows it by territory, not that the result is right.

## Complete runs of the pipeline

Run on 20 Nov 2026 with `scripts/run_remaining.sh`, which installs the two
stages and the regional-survey patch into eqasim-france v1.5.0 and generates
four populations end to end (10% sample, one seed, 14 to 17 minutes each).
S and T use the new stage. F and G use eqasim's own matching fed with the
regional survey, without and with the urban type, which the patch makes
possible. Scored with `scripts/evaluate_population.py`.

Hellinger distance to each survey.

| | Central | Suburb | Isolated | Rural |
|---|---|---|---|---|
| **Against the national survey** | | | | |
| S, new stage, national survey | 0.048 | 0.053 | 0.069 | 0.057 |
| F, eqasim matching, regional survey | 0.133 | 0.119 | 0.154 | 0.150 |
| G, urban type added, regional survey | 0.143 | 0.124 | 0.146 | 0.140 |
| T, new stage, regional survey | 0.142 | 0.132 | 0.153 | 0.145 |
| **Against the regional survey** | | | | |
| S | 0.112 | 0.113 | 0.109 | 0.137 |
| F | 0.037 | 0.029 | 0.049 | 0.059 |
| G | 0.017 | 0.025 | 0.046 | 0.045 |
| T | 0.037 | 0.028 | 0.044 | 0.055 |

S in a complete run gives what the trial on saved residents gave (0.046 to
0.069 and 0.108 to 0.140 there). The prior weight chosen by cross-validation
was 30, and 11% of residents were matched on every attribute.

F, G and T are judged against their own source, so their distances are small
by construction. G is the closest, T and F are level. What separates them is
the contrast between territories.

| | Central | Suburb | Isolated | Rural | Rural minus central |
|---|---|---|---|---|---|
| Tours per mobile person, regional survey | 1.708 | 1.699 | 1.602 | 1.574 | −0.134 |
| Tours, F | 1.666 | 1.668 | 1.682 | 1.664 | −0.002 |
| Tours, G | 1.702 | 1.666 | 1.557 | 1.554 | −0.149 |
| Tours, T | 1.707 | 1.698 | 1.592 | 1.584 | −0.124 |
| Staying home, regional survey | 8.8% | 8.9% | 9.3% | 9.4% | +0.6 points |
| Staying home, F | 9.9% | 9.7% | 9.6% | 10.0% | +0.2 points |
| Staying home, G | 9.2% | 10.1% | 11.1% | 11.9% | +2.6 points |
| Staying home, T | 8.6% | 8.5% | 9.3% | 10.3% | +1.7 points |

With eqasim's default matching the gap in tours disappears even though the
source is the regional survey itself. The home territory is not among the
matching attributes, so only 17% of rural residents of F receive a rural
respondent. The urban type option and the new stage both bring the gap back.
T does it while attaching a respondent of the same urban type no more often
than F does (17% for rural residents), because the structure of the day is
drawn from tables that depend on the urban type and the respondent is then
chosen inside that structure.

On staying home G and T look too high in rural communes. Most of it is not the
generator. The census counts more people over 64 in rural communes than the
survey of 2015 does (20% against 13%), and older people stay home more. With
the age mix of the survey respondents, computed by
`scripts/regional_source_age.py`, the rural minus central-city gap is −1.1
points in F, +1.1 in G and +0.6 in T, against +0.6 in the survey.

G keeps the blind spot of the option. Only 45% of residents of isolated cities
receive a respondent from an isolated city, the others a rural one.

Mean straight-line distances per mobile person are within 3 km of each other
across the four populations in every territory (15 to 18 km in central cities,
29 to 31 km in rural communes), since distances come from the location step.

The territory analysis stage was also run inside the pipeline, on variant C.
It gives 0.055, 0.064, 0.053 and 0.042 against the national survey and 10.7%,
10.8%, 14.4% and 16.5% of residents staying home, the figures this repository
computes outside the pipeline.

## Limits

- One seed for each complete run. F, G and T are compared with the survey they
  were built from; no third survey of the département exists to judge them.
- The complete runs were not simulated.
- One census sample (variant A, seed 1) for the trial; the five draws redraw the structure,
  the cross-validation folds and the matching.
- The parents of each table were fixed by hand from the survey analysis
  (territory acts on going out and on the number of tours). They were chosen
  before S was scored, but after both surveys had been analysed.
- 13% of the respondents S attaches live in Loire-Atlantique, against 79% in
  variant B, and 11% of residents are matched on every attribute.
