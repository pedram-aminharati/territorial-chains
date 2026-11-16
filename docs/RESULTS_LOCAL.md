# The regional survey as a second reference

EDGT Loire-Atlantique 2015 (open data of the Département, Licence Ouverte): 12,722 households,
20,799 diary respondents aged 5 and over, weekdays. Read through eqasim's own
`data.hts.edgt_44.cleaned` stage by `scripts/regional_reference.py`. eqasim does not keep the
home zone; it is recovered here from the zone table published with the survey, brought to
today's communes (`reference/communes_2015_to_2026.csv`) and given INSEE's urban-unit status.

## Staying home on a weekday

Estimate with 95% bootstrap interval.

| Sample | Central | Suburb | Isolated | Rural | All |
|---|---|---|---|---|---|
| National survey, ENTD 2008 | 12.2% (10.8 to 13.9) | 10.1% (9.1 to 11.3) | 13.1% (10.4 to 16.2) | 16.8% (15.4 to 18.2) | 12.5% (11.9 to 13.2) |
| ENTD respondents living in Loire-Atlantique | 10.2% (7.4 to 12.9) | 7.5% (5.4 to 10.0) | 6.7% (2.8 to 11.5) | 5.8% (3.0 to 9.2) | 8.1% (6.5 to 9.8) |
| same, respondents | 694 | 664 | 186 | 254 | 1,798 |
| Regional survey, EDGT 2015 | 8.8% (8.1 to 9.5) | 8.9% (8.2 to 9.6) | 9.3% (8.4 to 10.3) | 9.4% (8.4 to 10.4) | 9.0% (8.6 to 9.4) |
| same, respondents | 6,278 | 7,266 | 3,765 | 3,490 | 20,799 |

The national survey has a rural excess; neither sample from the département does. The
département also stays home less than France as a whole.

## The populations against each survey

Hellinger distance between generated and observed chain distributions, seed 1.

| Variant | Reference | Central | Suburb | Isolated | Rural |
|---|---|---|---|---|---|
| A, default, local donors | national | 0.087 | 0.077 | 0.116 | 0.129 |
| A, default, local donors | regional | 0.100 | 0.089 | 0.101 | 0.121 |
| B, default, national donors | national | 0.076 | 0.066 | 0.108 | 0.115 |
| B, default, national donors | regional | 0.113 | 0.098 | 0.105 | 0.124 |
| C, urban type | national | 0.055 | 0.064 | 0.053 | 0.042 |
| C, urban type | regional | 0.127 | 0.124 | 0.143 | 0.166 |

Over five seeds, against the regional survey, rural residents: A 0.121 (0.118 to 0.125), C 0.167 (0.166 to 0.170);
C is further than A in every territory in every seed.

## Reading

The urban-type option gives rural residents rural donors, but three quarters of those donors
live elsewhere in France. They bring the national rural pattern, which the département's own
data do not show. Judged locally, the default configuration is the closer one.

## Limits

- The surveys are seven years apart and differ in protocol: the regional survey was run face to
  face in the three agglomerations and by telephone elsewhere, so mode and territory are partly
  confounded in it.
- The regional survey records more activities per mobile person (about 2.7 to 2.8 against 2.2 to 2.3),
  which moves every ENTD-based population away from it.
- Urban type of regional respondents: 2020 urban units applied to the 2015 home commune.
- 349 of the 12,722 households lived in communes that have since merged; they follow the new commune.
