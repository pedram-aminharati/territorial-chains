# Targeted reading

A short reading of the references given in the project description, with two
more on how staying at home is measured. It says what each paper measures and
what this study takes from it. It is not a review of the French literature on
peri-urban and rural mobility, which remains to be done.

## Activity chains as the object of study

**Jiang, Ferreira and González (2012)** cluster the daily activity structure of
more than 30,000 people from the Chicago travel survey and find eight groups on
weekdays and seven at weekends, a richer picture than the usual split between
workers, students and non-workers. **He et al. (2024)** apply sequence analysis
and hierarchical clustering to commuters in Kunming, find four patterns, and
explain membership with a multinomial logit in which sex, commuting and working
time, household structure, car ownership and the activity opportunities around
the home all play a part.

What this study takes from them. The day is treated as a whole, as a chain, and
compared as a distribution over the most frequent chains. Following both papers,
the link with who people are is checked directly: the rural gap is recomputed
with the mix of age, occupation and car ownership equalised, and fidelity is
reported by population group (`docs/RESULTS_LINKS.md`). Car ownership turns out
to matter here too.

## Territory and commuting

**Susilo and Maat (2007)** relate commuting journeys to urban form over time
with the Dutch National Travel Survey. This study has no time dimension. It
reports home-to-work distance by urban type of the home in two surveys and in
the generated populations, and a second description of territory, distance from
the home to the nearest large city, which shows a contrast that the four urban
types hide.

## How staying at home is measured

**Madre, Axhausen and Brög (2007)** collate the share of people who do not leave
home on the survey day across many travel surveys. They conclude that it should
lie between 8% and 12% for a one-day weekday diary, and that part of what
surveys report comes from respondents who decline the diary by saying that they
stayed in. **Hubert, Armoogum, Axhausen and Madre (2008)** compare travel surveys
with time-use surveys in Belgium, France and Great Britain and find that
time-use surveys report markedly lower shares.

What this study takes from them. Staying home is the indicator on which the two
surveys used here disagree most (12.5% of people in the national survey of 2008,
9.0% in the regional survey of 2015), and survey protocol is a plausible part of
that difference, next to place and date. The range given by Madre and colleagues
is also a useful check on generated populations. Variants A and B, built from
the national survey of 2008, fall inside it. Variant C goes above it in isolated
cities and rural communes (14% to 17%). The variants built from the 2019 survey
read with person weights have 3% to 5% of residents at home, far below it (note
4 in `docs/UPSTREAM_NOTES.md`).

## Generating populations and chains

**Hörl and Balac (2021)** describe the eqasim pipeline and its statistical
matching, and validate activity chains by ranking the most frequent ones against
the survey. This study does the same by territory. **Joubert and de Waal
(2020)** learn a Bayesian network over person attributes and the features of
their activity chains and sample plans from it. **Shone and Hillel (2024)**
train variational autoencoders on about 37,000 daily sequences of the 2021 UK
National Travel Survey, in two representations, and judge the output on
correctness (structure, frequency, participation, transitions and timing) and on
creativity (diversity and novelty).

What this study takes from them. The generator benchmark has a Bayesian network
and a variational autoencoder next to matching, and scores each on the distance
between chain distributions, on a structural check (days that start and end at
home) and on novelty. Timing is absent because the benchmark generates the order
of activities only, and diversity is not reported. A transformer and a GAN were
added for comparison; neither comes from these references.

## References

He, M., Chen, N., He, Y., Li, J. and Liu, Y. (2024). Exploring the
activity-travel patterns of multi-purpose commuters on workdays based on
activity chains and time allocation: evidence from Kunming, China. ISPRS
International Journal of Geo-Information, 13(12), 446.

Hörl, S. and Balac, M. (2021). Synthetic population and travel demand for Paris
and Île-de-France based on open and publicly available data. Transportation
Research Part C, 130, 103291.

Hubert, J.-P., Armoogum, J., Axhausen, K. W. and Madre, J.-L. (2008). Immobility
and mobility seen through trip-based versus time-use surveys. Transport Reviews,
28(5), 641-658.

Jiang, S., Ferreira, J. and González, M. C. (2012). Clustering daily patterns of
human activities in the city. Data Mining and Knowledge Discovery, 25(3),
478-510.

Joubert, J. W. and de Waal, A. (2020). Activity-based travel demand generation
using Bayesian networks. Transportation Research Part C, 120, 102804.

Madre, J.-L., Axhausen, K. W. and Brög, W. (2007). Immobility in travel diary
surveys. Transportation, 34(1), 107-128.

Shone, F. and Hillel, T. (2024). Activity sequence modelling with deep
generative models. hEART 2024, Espoo.

Susilo, Y. O. and Maat, K. (2007). The influence of built environment to the
trends in commuting journeys in the Netherlands. Transportation, 34(5), 589-609.
