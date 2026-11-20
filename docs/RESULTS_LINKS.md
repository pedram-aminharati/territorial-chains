# Who people are, where they work, how far from the city they live

Run on 20 Nov 2026 with `scripts/territory_links.py`. Four analyses that the
project description asks for and that the first results did not cover: the link
between territory and socio-demographics, commuting, fidelity by population
group, and a description of territory other than the four urban types. Tables
are in `results/links/`.

## 1. Is the rural gap a matter of who lives there?

Rural minus central-city gap in the share of people staying home, raw and with
the composition of the two groups equalised. Each standardised figure is given
both ways, rural respondents reweighted to the central-city mix and the
reverse, with 95% bootstrap intervals for the first.

| | Raw | Same age and occupation | Same age, occupation and car ownership |
|---|---|---|---|
| National survey (ENTD 2008) | +4.6 points (2.6 to 6.4) | +5.5 (3.5 to 7.6), reverse +5.1 | +5.3 (3.4 to 9.1), reverse +5.3 |
| Regional survey (EDGT 2015) | +0.6 points (−0.7 to 1.8) | +0.9 (−0.3 to 2.3), reverse +0.9 | +3.1 (1.3 to 4.8), reverse +2.2 |

Nationally the gap is not a matter of composition. It stays between 5.1 and 5.5
points whatever is equalised and in whichever direction.

In Loire-Atlantique the raw gap is nil and stays under one point when age and
occupation are equalised. It becomes 2 to 3 points once car ownership is
equalised as well. Only 1.6% of rural respondents of the regional survey live
without a car, against 17% in central cities, and people without a car stay
home twice as often. So territory may act locally in the same direction as
nationally, offset by the fact that almost every rural household has a car. This
last figure rests on a few dozen rural respondents without a car and should be
read as an indication.

The gap in home-based tours per mobile person does not depend on composition in
either survey (−0.12 to −0.16 nationally, −0.14 to −0.19 regionally).

## 2. Commuting

People with a home-to-work trip, and the straight-line distance of that trip, by
urban type of the home.

| Median distance (km) | Central | Suburb | Isolated | Rural |
|---|---|---|---|---|
| National survey | 4.3 | 7.7 | 10.0 | 10.0 |
| Regional survey | 4.4 | 6.9 | 12.9 | 14.9 |
| A | 4.7 | 6.2 | 12.2 | 12.6 |
| B | 4.6 | 6.2 | 11.7 | 12.2 |
| C | 4.2 | 6.9 | 13.0 | 14.3 |

Between 26% and 31% of people make such a trip in every source and territory.
The populations reproduce the regional gradient in commuting distance, with
medians within 3 km of the regional survey everywhere. This is the work of
the location step, which uses census commuting flows, and it holds whatever the
matching. Means are lower in the populations than in the surveys in cities (7 to
9 km against 10 to 13 km), because workplaces are placed inside the département while
the surveys include commutes that leave it. Distances in the national survey are
routed distances divided by 1.3 and were recorded in whole kilometres, which is
why two medians are equal.

## 3. Fidelity by population group

Hellinger distance between generated and observed chain distributions, all
residents, by occupation group.

| Reference | Group | A | B | C |
|---|---|---|---|---|
| National survey | in work | 0.104 | 0.067 | 0.036 |
| National survey | retired | 0.116 | 0.104 | 0.074 |
| National survey | other | 0.173 | 0.083 | 0.147 |
| Regional survey | in work | 0.156 | 0.114 | 0.138 |
| Regional survey | retired | 0.118 | 0.102 | 0.113 |
| Regional survey | other | 0.179 | 0.195 | 0.226 |

"Other" gathers children, students and adults without occupation. It is the
worst reproduced group against the regional survey in every variant.

By group the ranking of variants is less clear-cut than by territory. Against
the regional survey, C is the furthest for the "other" group but not for people
in work or retired people, where A is the furthest. A has 1,667 donors in all, which is few once
they are split by group. B, with national donors and default attributes, is the
closest to the regional survey for people in work and for retired people. The
statement that C is the furthest from the regional survey holds territory by
territory, not group by group.

## 4. Distance to the city, a second description of territory

Communes are grouped by the straight-line distance from their centre to the
centre of Nantes or Saint-Nazaire, whichever is nearer.

| Staying home | Under 5 km | 5 to 15 km | 15 to 30 km | 30 km and more |
|---|---|---|---|---|
| Regional survey | 8.5% (7.7 to 9.2) | 8.7% (8.0 to 9.4) | 8.8% (8.0 to 9.7) | 11.0% (9.9 to 12.2) |
| A | 9.5% | 9.0% | 8.9% | 8.9% |
| B | 8.7% | 9.2% | 9.0% | 9.6% |
| C | 9.9% | 10.8% | 15.2% | 15.9% |

| Distance to the regional survey | Under 5 km | 5 to 15 km | 15 to 30 km | 30 km and more |
|---|---|---|---|---|
| A | 0.104 | 0.093 | 0.120 | 0.096 |
| B | 0.115 | 0.103 | 0.122 | 0.100 |
| C | 0.126 | 0.128 | 0.159 | 0.140 |

The regional survey does show more people staying home far from the two cities,
11.0% beyond 30 km against 8.5% to 8.8% nearer. The four urban types hide this,
because rural communes lie at every distance. No variant reproduces it. A and B
are flat, and C jumps to 15% from 15 km outwards, which is too much and too
early. A description of territory by distance or accessibility would give a
generator something that the urban type does not.

247 respondents of the regional survey live outside the département and are left
out of these bands.

## Limits

- Occupation is the eight-class code that eqasim uses for matching. Income,
  household structure and working time were not looked at.
- Distance to two city centres is a crude stand-in for accessibility. Public
  transport supply was not measured, although the timetables used for the
  simulation would allow it.
- Peri-urban communes are not a class of their own here. INSEE's zoning by
  commuting area would give one.
- One seed for the populations in this note.
