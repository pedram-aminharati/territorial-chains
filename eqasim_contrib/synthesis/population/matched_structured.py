import numpy as np
import pandas as pd

from synthesis.population.matched import statistical_matching, DEFAULT_MATCHING_ATTRIBUTES

"""
This stage is an alternative to synthesis.population.matched. It attaches a
respondent of the household travel survey to every person of the synthetic
population in two steps instead of one.

1) The structure of the day is drawn from a small Bayesian network which is
   fitted on the survey: whether the person goes out, the primary activity
   (work, education, other), the number of home-based tours and the number of
   secondary activities. The home territory (INSEE urban type) acts on going
   out and on the number of tours.

2) The respondent is drawn among those who have reported a day with that
   structure, by the usual statistical matching on the person attributes.

Compared to matching in one step, this has three consequences:

- The effect of the territory does not need a cell with enough respondents for
  every combination of all attributes, because it enters through two small
  tables.

- The tables are estimated for the study area with partial pooling: respondents
  living in the study area count fully, and the national table for the same
  parent values is added as a prior. The weight of the prior is selected by
  cross-validation on the respondents of the study area. Where the area has
  enough respondents, their behaviour prevails, elsewhere the national pattern
  for the same kind of territory is used. This needs filter_hts to be off.

- The urban type of a person is the one of the municipality where the home has
  been placed (synthesis.population.spatial.home.zones). The census does not
  give the municipality for municipalities below 10,000 inhabitants, so that
  the urban type attached to the census is "none" for all of them.

The stage returns the same table as synthesis.population.matched and can replace
it in a configuration file:

aliases:
  synthesis.population.matched: synthesis.population.matched_structured
"""

AGE_BOUNDARIES = [14, 29, 44, 59, 74, 1000]

# Order in which the structure is drawn, with the parents of each variable
STRUCTURE = [
    ("mobile", ["urban_type", "socioprofessional_class"]),
    ("primary", ["socioprofessional_class", "age_class"]),
    ("tours", ["primary", "urban_type"]),
    ("secondary", ["primary", "tours"]),
]

STRUCTURE_COLUMNS = [item[0] for item in STRUCTURE]
PRIOR_STRENGTHS = [1, 3, 10, 30, 100, 300, 1000, 3000]
MARGINAL_STRENGTH = 5.0

def configure(context):
    context.config("random_seed")
    context.config("matching_minimum_observations", 20)
    context.config("matching_minimum_age", 5)
    context.config("matching_attributes", DEFAULT_MATCHING_ATTRIBUTES)
    context.config("structure_prior_strength", "auto")

    context.stage("synthesis.population.sampled")
    context.stage("synthesis.population.spatial.home.zones")
    context.stage("data.spatial.urban_type")
    context.stage("data.spatial.codes")
    context.stage("data.hts.selected", alias = "hts")

def describe_structure(df_persons, df_trips):
    # One row per respondent with the four variables which describe the structure of the day
    df_trips = df_trips.sort_values(by = ["person_id", "trip_id"])

    first = df_trips.groupby("person_id", sort = False)["preceding_purpose"].first().astype(str).str[0]
    following = df_trips["following_purpose"].astype(str).str[0].groupby(
        df_trips["person_id"].values, sort = False).agg("".join)

    chain = df_persons["person_id"].map(first + following).fillna("h")
    inner = chain.str.strip("h")

    df = pd.DataFrame({ "hts_person_id": df_persons["person_id"].values })
    df["mobile"] = np.where(chain.str.len().values > 1, "yes", "no")

    df["primary"] = "other"
    df.loc[chain.str.contains("e").values, "primary"] = "education"
    df.loc[chain.str.contains("w").values, "primary"] = "work"

    # A tour is a sequence of activities away from home between two stays at home
    tours = np.where(inner == "", 0, inner.str.count("h+") + 1)
    df["tours"] = np.minimum(np.maximum(tours, 1), 3).astype(str)

    # Shop, leisure and other activities (only "s", "l" and "o" start with these letters)
    df["secondary"] = np.minimum(chain.str.count("[slo]").values, 3).astype(str)

    # Persons who stay at home have no further structure
    f_home = df["mobile"] == "no"
    df.loc[f_home, "primary"] = "none"
    df.loc[f_home, "tours"] = "0"
    df.loc[f_home, "secondary"] = "0"

    return df

def keys_of(df, columns):
    return df[columns].astype(str).agg("|".join, axis = 1).values

def count_table(df, weights, column, parents, states):
    df_counts = pd.crosstab(keys_of(df, parents), df[column].values, values = weights, aggfunc = "sum")
    return df_counts.reindex(columns = states).fillna(0.0)

def fit_tables(df_source, f_local, prior_strength):
    """
        Fits one conditional table per structure variable. Returns for each variable
        the states, their overall distribution (used for parent values which do not
        occur in the survey) and the table for the study area, which gives the
        probabilities of the states for every combination of parent values.
    """
    weights = df_source["person_weight"].values.astype(float)
    weights = weights * len(weights) / weights.sum()

    # Persons who stay at home only inform the first table
    f_mobile = (df_source["mobile"] == "yes").values
    two_levels = np.any(f_local) and not np.all(f_local)
    tables = {}

    for column, parents in STRUCTURE:
        f = np.ones(len(df_source), dtype = bool) if column == "mobile" else f_mobile
        states = sorted(df_source.loc[f, column].unique())

        marginal = pd.Series(weights[f]).groupby(df_source.loc[f, column].values).sum().reindex(states).values
        marginal = marginal / marginal.sum()

        df_national = count_table(df_source[f], weights[f], column, parents, states)
        national = (df_national.values + MARGINAL_STRENGTH * marginal) / (
            df_national.values.sum(axis = 1, keepdims = True) + MARGINAL_STRENGTH)
        df_national = pd.DataFrame(national, index = df_national.index, columns = states)

        if two_levels:
            df_local = count_table(df_source[f & f_local], weights[f & f_local], column, parents, states)
            df_local = df_local.reindex(df_national.index).fillna(0.0)

            local = (df_local.values + prior_strength * national) / (
                df_local.values.sum(axis = 1, keepdims = True) + prior_strength)
            df_local = pd.DataFrame(local, index = df_national.index, columns = states)
        else:
            df_local = df_national

        tables[column] = (states, marginal, df_local)

    return tables

def log_likelihood(df, weights, tables):
    total = 0.0

    for column, parents in STRUCTURE:
        states, marginal, df_table = tables[column]
        f = np.ones(len(df), dtype = bool) if column == "mobile" else (df["mobile"] == "yes").values

        df_probabilities = df_table.reindex(keys_of(df[f], parents))
        df_probabilities = df_probabilities.fillna(pd.Series(marginal, index = states))

        columns = df_probabilities.columns.get_indexer(df.loc[f, column].values)
        probabilities = df_probabilities.values[np.arange(len(columns)), columns]
        probabilities = np.where(columns >= 0, probabilities, 1e-6)

        total += np.sum(weights[f] * np.log(np.maximum(probabilities, 1e-6)))

    return total / np.sum(weights)

def select_prior_strength(df_source, f_local, random, folds = 5):
    """
        Selects the weight of the national prior by cross-validation: the
        respondents of the study area are held out in turns, and the selected
        value is the one which predicts the structure of their days best.
    """
    local_indices = np.flatnonzero(f_local)
    assignment = random.permutation(len(local_indices)) % folds
    weights = df_source["person_weight"].values.astype(float)
    scores = {}

    for prior_strength in PRIOR_STRENGTHS:
        score = 0.0

        for fold in range(folds):
            held_out = local_indices[assignment == fold]
            f_train = np.ones(len(df_source), dtype = bool)
            f_train[held_out] = False

            tables = fit_tables(df_source[f_train], f_local[f_train], prior_strength)
            score += log_likelihood(df_source.iloc[held_out], weights[held_out], tables) / folds

        scores[prior_strength] = score

    return max(scores, key = scores.get), scores

def sample_structure(df_target, tables, random):
    df_target = df_target.copy()

    for column, parents in STRUCTURE:
        states, marginal, df_table = tables[column]
        f = np.ones(len(df_target), dtype = bool) if column == "mobile" else (df_target["mobile"] == "yes").values

        keys = keys_of(df_target[f], parents)
        sampled = np.empty(len(keys), dtype = object)

        for key in np.unique(keys):
            f_key = keys == key
            probabilities = df_table.loc[key].values if key in df_table.index else marginal
            sampled[f_key] = random.choice(states, size = np.count_nonzero(f_key), p = probabilities / probabilities.sum())

        df_target[column] = { "mobile": "no", "primary": "none", "tours": "0", "secondary": "0" }[column]
        df_target.loc[f, column] = sampled

    return df_target

class Progress:
    def update(self, count): pass

def match_within_structure(df_source, df_target, columns, minimum_observations, random):
    """
        Draws a respondent for every person among the respondents with the same
        structure of the day, by statistical matching on the given attributes.
    """
    source_keys, target_keys = keys_of(df_source, STRUCTURE_COLUMNS), keys_of(df_target, STRUCTURE_COLUMNS)

    weights = df_source["person_weight"].values.astype(float)
    all_keys = np.unique(source_keys)

    # Structures which nobody has reported are replaced by a reported one with the
    # same mobility and primary activity
    for key in np.unique(target_keys):
        if not key in all_keys:
            candidates = [k for k in all_keys if k.split("|")[:2] == key.split("|")[:2]]
            f_candidates = np.isin(source_keys, candidates)
            replacement = random.choice(source_keys[f_candidates], size = np.count_nonzero(target_keys == key),
                p = weights[f_candidates] / weights[f_candidates].sum())
            target_keys[target_keys == key] = replacement

    assigned = np.zeros(len(df_target), dtype = df_source["hts_person_id"].dtype)
    levels = np.zeros(len(df_target), dtype = int)

    for key in np.unique(target_keys):
        f_source, f_target = source_keys == key, target_keys == key
        df_class = df_source[f_source]

        if len(df_class) >= minimum_observations:
            # A constant first attribute makes sure that every person finds a respondent,
            # the other attributes are used as far as this structure has respondents
            df_assignment, class_levels = statistical_matching(
                Progress(), df_class.assign(same_structure = 0), "hts_person_id", "person_weight",
                df_target[f_target].assign(same_structure = 0), "person_id", ["same_structure"] + columns,
                random_seed = int(random.integers(1 << 30)), minimum_observations = minimum_observations)

            # The assignment and the levels come back in the same (sorted) order
            df_assignment["level"] = class_levels - 1
            df_assignment = df_assignment.set_index("person_id").loc[df_target.loc[f_target, "person_id"].values]

            assigned[f_target] = df_assignment["hts_person_id"].values
            levels[f_target] = df_assignment["level"].values
        else:
            assigned[f_target] = random.choice(df_class["hts_person_id"].values, size = np.count_nonzero(f_target),
                p = weights[f_source] / weights[f_source].sum())

    return assigned, levels

def prepare_attributes(df):
    # The age class is always needed, as it is a parent in the structure
    df["age_class"] = np.digitize(df["age"], AGE_BOUNDARIES, right = True)
    df["any_cars"] = df["number_of_vehicles"] > 0
    return df

def execute(context):
    random = np.random.default_rng(context.config("random_seed"))

    # Survey respondents with the structure of their day
    df_source_households, df_source_persons, df_source_trips = context.stage("hts")
    df_source = pd.merge(df_source_persons, df_source_households)
    df_source = df_source.rename(columns = { "person_id": "hts_person_id" })
    df_source = pd.merge(df_source, describe_structure(df_source_persons, df_source_trips), on = "hts_person_id")

    if not "urban_type" in df_source:
        raise RuntimeError("The household travel survey does not provide the urban type")

    # Persons of the population with the urban type of their home municipality
    df_target = context.stage("synthesis.population.sampled")
    df_target = df_target[df_target["age"] >= context.config("matching_minimum_age")].copy()

    df_homes = context.stage("synthesis.population.spatial.home.zones")[["household_id", "commune_id"]].copy()
    df_homes["commune_id"] = df_homes["commune_id"].astype(str)

    df_urban_type = context.stage("data.spatial.urban_type")[["commune_id", "urban_type"]].copy()
    df_urban_type["commune_id"] = df_urban_type["commune_id"].astype(str)
    df_urban_type["urban_type"] = df_urban_type["urban_type"].astype(str)
    df_homes = pd.merge(df_homes, df_urban_type, on = "commune_id", how = "left")

    initial_count = len(df_target)
    df_target = df_target.drop(columns = [c for c in ("commune_id", "urban_type") if c in df_target])
    df_target = pd.merge(df_target, df_homes[["household_id", "urban_type"]], on = "household_id", how = "left")
    assert len(df_target) == initial_count

    # A home without urban type is treated like a municipality outside of the urban units
    f_missing = df_target["urban_type"].isna()

    if np.any(f_missing):
        print("Persons without urban type (set to 'none'):", np.count_nonzero(f_missing))
        df_target.loc[f_missing, "urban_type"] = "none"

    columns = list(context.config("matching_attributes"))

    try:
        default_index = columns.index("*default*")
        columns[default_index:default_index + 1] = DEFAULT_MATCHING_ATTRIBUTES
    except ValueError: pass

    # The urban type acts through the structure of the day
    columns = [column for column in columns if column != "urban_type"]

    df_source, df_target = prepare_attributes(df_source), prepare_attributes(df_target)

    for df in (df_source, df_target):
        df["urban_type"] = df["urban_type"].astype(str)
        df["departement_id"] = df["departement_id"].astype(str)

    for column in columns:
        if not column in df_source:
            raise RuntimeError("Attribute not available in source (HTS) for matching: {}".format(column))

        if not column in df_target:
            raise RuntimeError("Attribute not available in target (census) for matching: {}".format(column))

    # Fit the structure for the study area
    requested_departements = set(context.stage("data.spatial.codes")["departement_id"].astype(str).unique())
    f_local = df_source["departement_id"].isin(requested_departements).values

    prior_strength = context.config("structure_prior_strength")

    if np.any(f_local) and not np.all(f_local):
        if prior_strength == "auto":
            prior_strength, scores = select_prior_strength(df_source, f_local, random)
            context.set_info("prior_strength_scores", { str(k): float(v) for k, v in scores.items() })

        print("Respondents in the study area: %d of %d, weight of the national prior: %s" % (
            np.count_nonzero(f_local), len(f_local), prior_strength))
    else:
        prior_strength = 0.0

    context.set_info("prior_strength", float(prior_strength))
    tables = fit_tables(df_source, f_local, float(prior_strength))

    # Draw the structure and then the respondent
    df_target = sample_structure(df_target, tables, random)

    assigned, levels = match_within_structure(
        df_source, df_target, columns, context.config("matching_minimum_observations"), random)
    df_target["hts_person_id"] = assigned

    context.set_info("matched_counts", {
        count: int(np.count_nonzero(levels >= count)) for count in range(len(columns) + 1)
    })

    for count in range(len(columns) + 1):
        print("%d matched levels:" % count, np.count_nonzero(levels >= count), "%.2f%%" % (100 * np.count_nonzero(levels >= count) / len(df_target),))

    return df_target[["person_id", "hts_person_id"]]
