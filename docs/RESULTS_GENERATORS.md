# Generators against statistical matching: first benchmark

Run on 12 Nov 2026 with `scripts/benchmark_generators.py`, and again on 16 Nov 2026
with the variational autoencoder and then the GAN added. Each new run gave the
same numbers as the one before for the methods already there. Data: the 17,997
ENTD 2008 diary respondents, read through eqasim's cleaning stage. Protocol:
five random splits stratified by urban type; 80% of respondents train every
generator, the other 20% are the target. A generator sees only the target
person's attributes (sex, car, age class, socio-professional class, and for the
territory-aware versions the urban type) and proposes a chain, which is compared
with what the respondent reported. Means over the five splits, range in
brackets. `floor` is the distance between training and test respondents of the
same urban type: what sampling alone produces.

## Generators

| Family | Territory-blind | Territory-aware |
|---|---|---|
| Statistical matching (eqasim's function, unchanged) | default attribute list | urban type first |
| Bayesian network (pgmpy structure search, weighted tables) | graph learned from data | edge urban type to "goes out" imposed |
| Autoregressive transformer (PyTorch, 2 layers) | attributes without urban type | all attributes |
| Conditional variational autoencoder (PyTorch, recurrent encoder and decoder, 16 latent dimensions) | attributes without urban type | all attributes |
| Conditional Wasserstein GAN with gradient penalty (PyTorch, all positions written at once) | attributes without urban type | all attributes |

## Rural residents staying home (observed 16.8%)

| Generator | Blind | Aware |
|---|---|---|
| Matching | 12.5% | 17.2% |
| Bayesian network | 12.6% | 16.3% |
| Transformer | 12.4% | 16.8% |
| Autoencoder | 12.0% | 15.3% |
| GAN | 15.0% | 19.9% |

The result depends on whether the generator sees territory, not on its family.
The autoencoder recovers most of the difference but not all of it (14.4% to
16.2% over the five splits). The GAN responds to territory too, but overstates
staying home with and without it (14.7% and 15.4% over all residents, against
12.8% observed).

## Error on the chain distribution (Hellinger, lower is better)

| Generator | Rural | All residents |
|---|---|---|
| Floor | 0.085 | 0.046 |
| Matching, default | 0.109 [0.102, 0.122] | 0.050 |
| Matching, urban type first | 0.093 [0.081, 0.102] | 0.054 |
| Bayesian network, learned graph | 0.110 [0.098, 0.121] | 0.055 |
| Bayesian network, territory edge | 0.099 [0.080, 0.113] | 0.047 |
| Transformer, without territory | 0.130 [0.103, 0.153] | 0.066 |
| Transformer, with territory | 0.105 [0.088, 0.118] | 0.069 |
| Autoencoder, without territory | 0.115 [0.103, 0.123] | 0.053 |
| Autoencoder, with territory | 0.092 [0.078, 0.100] | 0.051 |
| GAN, without territory | 0.179 [0.171, 0.189] | 0.158 |
| GAN, with territory | 0.184 [0.164, 0.211] | 0.149 |

- No generator is clearly better than matching with the urban type on this
  test. The Bayesian network with a territory edge and the autoencoder with
  territory are level with it for rural residents, and their ranges over splits
  overlap.
- The GAN is far behind every other generator, about twice the distance of the
  transformer for all residents. It writes every position of the chain at once
  from a noise vector and was trained for a fixed number of steps, since it has
  no likelihood to select on.
- Among the others the transformer is the least faithful to the observed
  distribution. The three neural models are the only generators that write
  chains absent from their training data (12% of the transformer's output, 13%
  of the autoencoder's, 12% of the GAN's); matching and the Bayesian network
  reuse reported chains by construction.
- The autoencoder's latent vector is in use: the KL term is 1.1 nats per chain
  on the validation respondents (0.9 to 1.2 over splits).
- In central cities, suburbs and isolated cities every method is within the
  floor: the test samples are too small to separate them (isolated-city floor
  0.19).

## Coherence of the generated chains

Share of days that start and end at home, all residents, mean over the five
splits. Held-out respondents report 94.7%.

| Generator | Blind | Aware |
|---|---|---|
| Matching | 94.1% | 94.4% |
| Bayesian network | 94.1% | 93.9% |
| Transformer | 94.2% | 93.8% |
| Autoencoder | 93.2% | 93.2% |
| GAN | 91.1% | 89.5% |

Matching and the Bayesian network reuse reported chains, so they are coherent
by construction. The transformer and the autoencoder stay within 1.5 points of
the survey although 12% to 13% of their chains were never reported. The GAN
loses 4 to 5 points. This is the only structural check made here; times and
durations are not generated, so their consistency cannot be tested.

## Moved to another territory

Run on 20 Nov 2026 with `scripts/benchmark_transfer.py`. Every generator is
trained on all 17,997 respondents of the national survey and proposes a chain
for each of the 20,799 respondents of the regional survey (EDGT
Loire-Atlantique 2015) from that person's attributes. The proposals are
compared with what the regional respondents reported. Three trainings, mean
and range. `National survey as it is` takes the national respondents of the
same urban type without any model. `Floor` compares one half of the regional
survey with the other.

| Generator | Rural | All residents | Rural staying home |
|---|---|---|---|
| Floor | 0.067 | 0.029 | 9.4% (observed) |
| National survey as it is | 0.162 | 0.127 | 16.8% |
| Matching, default | 0.128 [0.123, 0.133] | 0.093 | 8.5% |
| Matching, urban type first | 0.147 [0.145, 0.148] | 0.110 | 15.3% |
| Bayesian network, learned graph | 0.134 [0.124, 0.147] | 0.125 | 11.0% |
| Bayesian network, territory edge | 0.142 [0.135, 0.148] | 0.123 | 14.8% |
| Transformer, without territory | 0.125 [0.120, 0.128] | 0.110 | 10.7% |
| Transformer, with territory | 0.137 [0.127, 0.148] | 0.121 | 14.2% |
| Autoencoder, without territory | 0.126 [0.119, 0.132] | 0.116 | 11.3% |
| Autoencoder, with territory | 0.145 [0.139, 0.149] | 0.123 | 14.5% |
| GAN, without territory | 0.209 [0.189, 0.225] | 0.211 | 14.9% |
| GAN, with territory | 0.220 [0.211, 0.226] | 0.202 | 16.3% |

- No generator trained on the national survey comes near the floor. The two
  surveys are 0.127 apart for all residents, and the best generator is at
  0.093.
- Every model except the GAN is closer to the regional survey than the national
  respondents taken as they are, because it gives regional respondents days
  that fit their attributes. eqasim's default matching gains the most.
- For rural residents the order of the national test turns over. The versions
  that do not see territory are at 0.125 to 0.134 and the versions that see it
  at 0.137 to 0.147. Ranges overlap for the Bayesian network and the
  transformer, so the difference is small, but it has the same sign in the four
  families.
- The reason is staying home. Regional rural respondents stay home 9.4% of the
  time. The versions that see territory give them 14% to 15%, which is what
  they learned from rural respondents elsewhere in France.
- On home-based tours it is the other way round. The regional gap between rural
  and central-city respondents is −0.13 tours per mobile person. The versions
  that do not see territory give +0.02 to +0.07 and the versions that see it
  −0.09 to −0.11. The Bayesian network is the exception (+0.03), since its
  territory edge points to going out only.

So what a generator learns about territory in the national survey transfers to
Loire-Atlantique for tours and not for staying home. This is the result of
`RESULTS_LOCAL.md`, found again without any population or census in between.

## Structure search does not find territory

Hill climbing on BIC, with chain variables barred from being parents of person
attributes, linked the urban type to a chain variable in 0 of 5 splits, even
with a binary "goes out" variable placed first. Socio-professional class and
age took that role. The effect of territory is real (previous tables) but, in a
tabular network, adding it as a second parent of "goes out" multiplies the
table and the BIC penalty outweighs the gain. The edge was therefore imposed,
which is the kind of expert adjustment Joubert and de Waal describe. The
transformer adds territory as one more embedding and needs no such decision.

## What this suggests for the project

The gain available from territory on chain structure is captured by any
generator that is given the territory. The open problems measured in
`RESULTS_PIPELINE.md` are upstream of the model family: which territorial
variable (four urban-unit classes are coarse), how residents of small
municipalities are labelled, and how to keep local donors. A model-based
generator matters for these because it can take several territorial variables
and a regional effect at once, where matching runs out of donors.

## Limits

- The hold-out test uses one survey (ENTD 2008). The transfer test has one
  target territory and three trainings.
- Small models and no tuning; the transformer, autoencoder and GAN results are
  lower bounds on what those families can do. The GAN in particular is a plain
  fully connected one and decodes the most likely activity at each position.
- Chains only: no start times or durations yet.
