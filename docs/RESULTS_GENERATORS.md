# Generators against statistical matching: first benchmark

Run on 12 Nov 2026 with `scripts/benchmark_generators.py`, and again on 16 Nov 2026
with the variational autoencoder added. The second run gave the same numbers as
the first for the six earlier methods. Data: the 17,997
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

## Rural residents staying home (observed 16.8%)

| Generator | Blind | Aware |
|---|---|---|
| Matching | 12.5% | 17.2% |
| Bayesian network | 12.6% | 16.3% |
| Transformer | 12.4% | 16.8% |
| Autoencoder | 12.0% | 15.3% |

The result depends on whether the generator sees territory, not on its family.
The autoencoder recovers most of the difference but not all of it (14.4% to
16.2% over the five splits).

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

- No generator is clearly better than matching with the urban type on this
  test. The Bayesian network with a territory edge and the autoencoder with
  territory are level with it for rural residents, and their ranges over splits
  overlap.
- The transformer is the least faithful to the observed distribution. The two
  neural models are the only generators that write chains absent from their
  training data (12% of the transformer's output, 13% of the autoencoder's);
  matching and the Bayesian network reuse reported chains by construction.
- The autoencoder's latent vector is in use: the KL term is 1.1 nats per chain
  on the validation respondents (0.9 to 1.2 over splits).
- In central cities, suburbs and isolated cities every method is within the
  floor: the test samples are too small to separate them (isolated-city floor
  0.19).

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

- One survey (ENTD 2008), national hold-out, not a Loire-Atlantique population.
- Small models and no tuning; the transformer and autoencoder results are lower
  bounds on what those families can do. No adversarial model (GAN) was tried.
- Chains only: no start times or durations yet.
