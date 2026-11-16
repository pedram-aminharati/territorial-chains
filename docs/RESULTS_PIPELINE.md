# eqasim populations by territory: first results

Five variants of eqasim-france v1.5.0 for Loire-Atlantique, 10% sample
(138,915 matched persons each), one random seed, run on 12 Nov 2026 and scored
with `scripts/evaluate_population.py`. Territory of a synthetic person is the
urban-unit status of the home commune. "Observed" is the source survey,
national, by urban type (ENTD 2008, or EMP 2019 with day weights). Tables are
in `results/<variant>/`.

Re-scored on 13 Nov 2026 after two findings. In the variants with national
donors, 23 to 105 matched persons belong to a household that leaves the
pipeline without a home commune; they were first counted as rural and are now
left out (rural values move in the last digit). And variant A's donor pool is
smaller than "Loire-Atlantique respondents": eqasim's `filter_hts` also drops
respondents with a trip that starts or ends outside the département, leaving
1,667 of the 1,798.

| Variant | Survey | Donors | Matching attributes |
|---|---|---|---|
| A | ENTD | Loire-Atlantique only (`filter_hts: true`, eqasim default) | default |
| B | ENTD | national | default |
| C | ENTD | national | urban type first, then default |
| D | EMP | national | default |
| E | EMP | national | urban type first, then default |

## 1. Whose day does a resident receive?

Share of residents whose donor lives in the same urban type:

| Home | A | B | C | D | E |
|---|---|---|---|---|---|
| Central city | 42% | 37% | 92% | 36% | 92% |
| Suburb | 39% | 39% | 85% | 41% | 85% |
| Isolated city | 13% | 12% | 43% | 8% | 43% |
| Rural | 16% | 18% | 100% | 22% | 100% |

With the default attributes every territory draws from the same donor mix
(about 36% central, 38% suburb, 12% isolated, 14% rural in variant A).

With the urban-type option, 57% of isolated-city residents still receive a
rural donor, as do 15% of suburban and 8% of central-city residents. The
census does not give the commune of people living in small municipalities;
`data/census/cleaned.py` sets their urban type to `none`, and they are placed
in an actual commune only later. They are matched as rural whatever their
commune turns out to be.

The option also trades local donors for territorial ones: the share of donors
living in Loire-Atlantique falls from 79% (B) to 26% (C).

## 2. Staying at home

| | Central | Suburb | Isolated | Rural |
|---|---|---|---|---|
| Observed, ENTD | 12.2% | 10.1% | 13.1% | 16.8% |
| A, default, local donors | 9.6% | 9.1% | 8.8% | 8.5% |
| B, default, national donors | 8.9% | 9.3% | 9.2% | 8.7% |
| C, urban type | 10.7% | 10.8% | 14.4% | 16.5% |
| Observed, EMP day-weighted | 13.2% | 13.7% | 15.5% | 15.4% |
| D, EMP default | 3.4% | 3.2% | 3.1% | 3.2% |
| E, EMP urban type | 3.3% | 2.9% | 3.6% | 4.6% |

Against the national survey, the default configuration has no territorial
gradient and the urban-type option has the national one. The regional survey
of Loire-Atlantique itself shows no gradient (docs/RESULTS_LOCAL.md), so this
table does not say which population is right for the département. Populations built from EMP have about 3% of
people at home against 13% to 15% in the day-weighted survey, the consequence
of the weight issue described in `RESULTS_SURVEYS.md`.

## 3. Tours and chain distributions

Home-based tours per mobile person, rural minus central city: observed -0.11;
A +0.03; B +0.04; C -0.09.

Hellinger distance between generated and observed chain distributions (25 most
frequent chains plus remainder):

| | Central | Suburb | Isolated | Rural |
|---|---|---|---|---|
| A | 0.087 | 0.077 | 0.116 | 0.129 |
| B | 0.076 | 0.066 | 0.108 | 0.115 |
| C | 0.055 | 0.064 | 0.053 | 0.042 |
| D | 0.147 | 0.153 | 0.180 | 0.179 |
| E | 0.140 | 0.152 | 0.163 | 0.137 |

With default attributes the error is largest where the posting expects it,
in isolated cities and rural communes. The urban-type option divides the rural
error by three.

Share of the observed between-territory contrast (Jensen-Shannon) retained:
3% to 51% in A, 6% to 27% in B. In C it ranges from 31% to 239%; values above
100% for pairs involving central cities mean the generated contrast exceeds
the national one.

## 4. Matching levels reported by eqasim

| Variant | Matched on all attributes | Without the last one (departement) |
|---|---|---|
| A | 77.1% | 77.1% |
| B | 79.0% | 98.5% |
| C | 24.4% | 90.3% |
| D | 6.7% | 96.8% |
| E | 0.0% | 81.0% |

## 5. Distances

Straight-line kilometres per mobile person and weekday (survey distances divided
by eqasim's factor of 1.3):

| | Central | Suburb | Isolated | Rural | Rural minus central |
|---|---|---|---|---|---|
| Observed, ENTD | 24.5 | 27.3 | 34.5 | 38.9 | 14.4 |
| A | 16.6 | 19.3 | 27.2 | 30.0 | 13.4 |
| B | 17.5 | 20.2 | 28.0 | 30.6 | 13.2 |
| C | 16.1 | 20.4 | 28.7 | 31.6 | 15.6 |
| Observed, EMP | 27.2 | 32.5 | 31.4 | 43.6 | 16.4 |
| D | 17.1 | 19.8 | 26.8 | 29.0 | 11.9 |
| E | 15.7 | 20.2 | 27.2 | 30.7 | 15.1 |

The territorial gradient in distance is reproduced by every variant (91% to
108% of the observed gap with ENTD), because distances come from the location
step (census commuting flows, then secondary locations), not from the matched
chain. Levels are 7 to 9 km below the survey everywhere; a likely reason is that
survey means include long trips leaving the area while the population is
generated for one departement, and the reference is national.

## 6. Is the difference between territories kept?

Rural residents minus central-city residents, from `results/<variant>/gaps.csv`.
A and C are means over five seeds, with the range in brackets.

| | Staying home (points) | Tours per mobile person | Distance per mobile person (km) |
|---|---|---|---|
| National survey (ENTD) | +4.6 | −0.11 | +14.4 |
| Regional survey (EDGT 2015) | +0.6 | −0.13 | +13.1 |
| A | −0.7 [−1.1, −0.4] | +0.03 [+0.03, +0.04] | +13.3 [13.1, 13.6] |
| B | −0.1 | +0.04 | +13.2 |
| C | +6.2 [+5.8, +6.7] | −0.10 [−0.10, −0.09] | +15.6 [15.3, 15.9] |

Both surveys find fewer home-based tours and longer distances for rural
residents. Every variant keeps the distance gap. Only C reproduces the gap in
tours. On staying home the surveys disagree, and A and B sit with the regional
survey while C goes beyond the national one. So C is not simply worse locally:
it is right on tours and wrong on staying home.

## Limits

- The reference is national while the population is Loire-Atlantique with
  2022 demographics, so part of each gap is composition, not matching error.
  The regional survey (EDGT 44) is the missing local reference.
- These tables are seed 1. Variants A and C were repeated over five seeds (docs/SEEDS.md); the ranges are narrow.
