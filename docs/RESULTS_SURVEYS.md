# Survey analysis by territory: first results

Run on 12 Nov 2026 with `scripts/survey_contrasts.py`, eqasim-france v1.5.0
cleaning stages, ENTD 2008 and EMP 2019 public files. Weekday diaries only.
Territory is INSEE's urban-unit status, the typology eqasim already supports:
central city, suburb, isolated city, none (rural). Intervals are 95% bootstrap
intervals over respondents. Tables are in `results/`.

## 1. Donors

| | ENTD 2008 | EMP 2019 |
|---|---|---|
| Diary respondents, France | 17,997 | 10,811 |
| Diary respondents, Loire-Atlantique | 1,798 | 195 |
| of which isolated city / rural | 186 / 254 | 6 / 37 |
| Kish effective size, Loire-Atlantique | 758 | 144 |

ENTD over-sampled the region; EMP did not. Moving to the newer survey divides
the local donor pool by nine.

## 2. EMP weekday immobility depends on which weight is used

In the EMP files, the 455 respondents without a diary are exactly those with
`MIMMOSEM == 1` (stayed in on every weekday), and the trip file carries a day
weight `POND_JOUR`. Read with the person weight `pond_indC`, as eqasim's
`data.hts.emp` stages do, 2.6% of people stay at home on a weekday. Read with
the day weight, 14.0% do (13.2% in central cities, 15.4% in rural communes),
in line with ENTD (10% to 17%) and with the EMP's own seven-day recall
variables (13% to 17% for each of the seven days). `POND_JOUR` is not read anywhere in eqasim
v1.5.0 or on `main` as of today.

Checked on 13 Nov 2026 against the SDES note that accompanies the public files
("Mise à disposition des tables de l'EMP 2019", December 2021): local-mobility
trips are to be weighted by `pond_jour`, a typical weekday is obtained by
keeping weekdays and dividing by 5, a per-person figure by dividing by the sum
of `pond_indC`, and `pond_jour` already contains the person weight. The 14.0%
above applies exactly that rule to people instead of trips. The note itself
gives no rule for the share of people who stay home, so that last step is this
study's, not the note's.

## 3. Where the territorial contrast is

ENTD 2008, weekday, by urban type (central city / suburb / isolated city / rural):

| Indicator | Central | Suburb | Isolated | Rural |
|---|---|---|---|---|
| Stayed home | 12.2% | 10.1% | 13.1% | 16.8% |
| Distance per mobile person (km, mean) | 31.8 | 35.5 | 44.8 | 50.5 |
| Home-based tours per mobile person | 1.64 | 1.57 | 1.59 | 1.53 |
| Out-of-home activities per mobile person | 2.32 | 2.21 | 2.25 | 2.27 |
| Simple commute (home-work-home or home-school-home) | 16.7% | 19.6% | 17.5% | 17.9% |

Immobility, distance and the number of tours separate rural from urban with
non-overlapping intervals. The number of activities and the share of simple
commutes do not. EMP 2019 shows the same pattern (distance 35 to 57 km).
Distances are means and include the long trips made that day.

## 4. The sequence of purposes differs little between urban types

Jensen-Shannon divergence between chain distributions (25 most frequent chains
plus a pooled remainder), against the 95th percentile obtained by shuffling
territory labels:

| Pair | ENTD: observed / noise | EMP: observed / noise |
|---|---|---|
| suburb / rural | 0.0160 / 0.0054 | 0.0102 / 0.0074 |
| central city / rural | 0.0097 / 0.0074 | 0.0137 / 0.0080 |
| central city / suburb | 0.0057 / 0.0063 | 0.0059 / 0.0068 |
| pairs with isolated city | below noise | below noise |

Only rural against urban exceeds what chance produces. With this four-class
typology, the contrast sits in how far people go and whether they go out, much
more than in the order of purposes. A finer typology (density grid,
accessibility) may show more; that is the next test.

## 5. Thin matching cells

Share of people whose cell (sex, car, age class, socio-professional class) has
fewer than 20 donors, the threshold below which eqasim drops attributes:

| Donor pool | ENTD | EMP |
|---|---|---|
| National | 1.0% | 3.4% |
| National, with urban type | 7.2% (isolated city 19%) | 18.0% (isolated city 50%) |
| Loire-Atlantique only | 17.3% | 87.5% |
| Loire-Atlantique only, with urban type | 69.6% | 100% |

Computed on the survey's own weighted population as a stand-in for the census.
The pipeline runs (work package 3) will replace this with the matched levels
eqasim reports.
