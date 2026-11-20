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

## Limits

- One census sample (variant A, seed 1); the five draws redraw the structure,
  the cross-validation folds and the matching.
- The parents of each table were fixed by hand from the survey analysis
  (territory acts on going out and on the number of tours). They were chosen
  before S was scored, but after both surveys had been analysed.
- 13% of the respondents S attaches live in Loire-Atlantique, against 79% in
  variant B, and 11% of residents are matched on every attribute.
- Distances, modes and simulated travel are not covered. They need a pipeline
  run with the stage (`S_entd_structured`, `T_edgt44_structured`).
