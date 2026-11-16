# Presenting the pilot: storyline and questions to expect

Ten minutes, with the project page open. Each step names the section to show.

## Storyline

1. **The question** (top of page). eqasim gives each census person the day of a
   survey respondent who resembles them. Territory is the last attribute in the
   list and the first one dropped. Does the population still know where its
   people live, and against which survey should that be judged?
2. **Whose day?** (Donors, then Explorer). By default 16% of rural residents get
   a rural donor. Show one resident in the explorer under the three designs.
3. **The option and its blind spot** (Map, measure "Donor from own territory",
   commune view). With `use_urban_type`, rural communes are at 100% and 59 urban
   communes at 0%, because the census hides the commune of small municipalities.
4. **The reversal** (Regional survey). Nationally rural residents stay home
   more; in Loire-Atlantique they do not, in two independent samples. Judged
   against the regional survey, the default population is the closer one. This
   is the main result: type of territory does not describe a territory.
5. **Does it matter downstream?** (Simulation, Stability). 18% fewer rural trips
   in every seed; car kilometres move by a few percent by territory and cancel
   over the département.
6. **Can a model do better?** (Generators). On the national survey, what counts
   is whether the model sees territory, not which model it is.
7. **What I would do next** in the postdoc: richer territorial descriptors than
   four urban types, references that are local where they exist, and a
   generator integrated as an eqasim stage. The territory analysis already
   exists as a stage (`eqasim_contrib/`); the generators do not.

## Questions to expect, with the honest answer

- **Is the reversal real or a survey artefact?** Both samples from the
  département agree, but the regional survey mixes face-to-face and telephone
  by territory, and the surveys are seven years apart. The direction is solid;
  the size is not.
- **Why does the option use national donors?** Matching on urban type first
  leaves too few local respondents per cell; 74% of donors then come from
  elsewhere.
- **Only one département?** Yes. Whether other départements look like the
  national pattern or like Loire-Atlantique is untested.
- **How many seeds?** Five populations and three simulations per variant, for
  the two main variants only.
- **Are the simulated levels credible?** No: the mode-choice model is the
  Île-de-France calibration. Only differences between variants are used.
- **What is new for transport research here?** The measurement by territory,
  the two-reference comparison and the commune-level view. The generators are a
  first benchmark, not a contribution yet: they write the order of activities
  only, without times, so they cannot replace matching in the pipeline as they
  are.
- **What did you not have time to check?** The cause of the 3% of trips missing
  in the simulation, the households without a home commune, and a population
  built from the regional survey itself (variant F).
- **Your background is not transport.** Correct. Before this application I had
  not run eqasim; the page shows how I work in a new field.
