import os

import numpy as np
import pandas as pd

"""
This stage describes the activity chains of the synthetic population by type
of home territory and compares them with the household travel survey that the
chains were matched from.

The territory is the INSEE urban unit status of the home municipality (central
city, suburb, isolated city, rural), the same classification that the option
use_urban_type uses for matching. Other analysis stages compare chains by age
and sex; this one adds the spatial breakdown.

For each type of territory the stage gives:
- the share of residents who stay at home and the size of the chains, in the
  population and in the survey
- the Hellinger distance between the chain distribution of the population and
  the one of the survey
- the most frequent chains with their share in both
- the type of territory in which the matched survey respondents live

The comparison with the survey needs the urban type of the respondents, which
ENTD and EMP always carry and EGT carries when use_urban_type is set. Without
it, only the population side is reported.

The tables are returned as a dictionary of data frames and written as CSV files
to the output path.
"""

URBAN_TYPES = ["central_city", "suburb", "isolated_city", "none"]

PURPOSE_MAPPING = {
    "home": "h", "work": "w", "education": "e",
    "shop": "s", "leisure": "l", "other": "o"
}

def configure(context):
    context.stage("synthesis.population.enriched")
    context.stage("synthesis.population.activities")
    context.stage("synthesis.population.spatial.home.zones")
    context.stage("data.spatial.urban_type")
    context.stage("data.hts.selected", alias = "hts")

    context.config("output_path")
    context.config("output_prefix", "ile_de_france_")
    context.config("territory_chains_top_k", 25)

def describe_chains(df):
    # Adds the indicators which are derived from the chain alone
    df["stays_home"] = df["chain"].str.len() == 1
    df["activities"] = df["chain"].str.replace("h", "", regex = False).str.len()

    # A tour is a sequence of activities away from home between two stays at home
    inner = df["chain"].str.strip("h")
    df["tours"] = np.where(inner == "", 0, inner.str.count("h+") + 1)

    return df

def population_chains(context):
    df_persons = context.stage("synthesis.population.enriched")
    census_columns = ["commune_id"] if "commune_id" in df_persons else []

    df_persons = df_persons[["person_id", "household_id", "hts_person_id"] + census_columns].rename(
        columns = { "commune_id": "census_commune_id" })

    # Persons below the matching age have no survey respondent and no chain of their own
    df_persons = df_persons[df_persons["hts_person_id"] >= 0]

    df_activities = context.stage("synthesis.population.activities")[[
        "person_id", "activity_index", "purpose"
    ]].sort_values(by = ["person_id", "activity_index"])

    df_chains = df_activities["purpose"].astype(str).map(PURPOSE_MAPPING).groupby(
        df_activities["person_id"].values, sort = False).agg("".join)
    df_chains = df_chains.rename("chain").rename_axis("person_id").reset_index()

    df_homes = context.stage("synthesis.population.spatial.home.zones")[["household_id", "commune_id"]].copy()
    df_homes["commune_id"] = df_homes["commune_id"].astype(str)

    df_urban_type = context.stage("data.spatial.urban_type")[["commune_id", "urban_type"]].copy()
    df_urban_type["commune_id"] = df_urban_type["commune_id"].astype(str)
    df_urban_type["urban_type"] = df_urban_type["urban_type"].astype(str)

    df = pd.merge(df_persons, df_chains, on = "person_id")
    df = pd.merge(df, df_homes, on = "household_id", how = "left")
    df = pd.merge(df, df_urban_type, on = "commune_id", how = "left")
    assert len(df) == len(df_persons)

    # Persons without a home municipality or outside of the urban type table cannot be
    # attributed to a territory. They are reported and left out.
    f_missing = df["urban_type"].isna()
    context.set_info("persons_without_urban_type", int(np.count_nonzero(f_missing)))

    if np.any(f_missing):
        print("Persons without urban type (left out):", np.count_nonzero(f_missing))

    df = df[~f_missing].copy()
    df["weight"] = 1.0
    return describe_chains(df)

def survey_chains(context):
    df_households, df_persons, df_trips = context.stage("hts")

    df_trips = df_trips.sort_values(by = ["person_id", "trip_id"])
    first = df_trips.groupby("person_id", sort = False)["preceding_purpose"].first().astype(str).map(PURPOSE_MAPPING)
    following = df_trips["following_purpose"].astype(str).map(PURPOSE_MAPPING).groupby(
        df_trips["person_id"].values, sort = False).agg("".join)

    df = df_persons[["person_id", "household_id", "person_weight"]].copy()
    df = df.rename(columns = { "person_id": "hts_person_id", "person_weight": "weight" })
    df["chain"] = df["hts_person_id"].map(first + following)

    # Respondents without trips have stayed at home
    df["chain"] = df["chain"].fillna("h")

    # The urban type is a household attribute in ENTD and EMP, a person attribute in EGT
    if "urban_type" in df_persons:
        df["urban_type"] = df_persons["urban_type"].astype(str).values
    elif "urban_type" in df_households:
        urban_type = df_households.set_index("household_id")["urban_type"].astype(str)
        df["urban_type"] = df["household_id"].map(urban_type)
    else:
        df["urban_type"] = np.nan

    return describe_chains(df)

def weighted_shares(df, column):
    shares = df.groupby(column)["weight"].sum()
    return shares / shares.sum()

def weighted_mean(df, column):
    if len(df) == 0: return np.nan
    return float(np.average(df[column].astype(float), weights = df["weight"]))

def indicators(df, prefix):
    df_mobile = df[~df["stays_home"]]

    return {
        prefix + "_stays_home": weighted_mean(df, "stays_home"),
        prefix + "_activities_per_mobile_person": weighted_mean(df_mobile, "activities"),
        prefix + "_tours_per_mobile_person": weighted_mean(df_mobile, "tours"),
    }

def hellinger(p, q):
    index = p.index.union(q.index)
    p, q = p.reindex(index, fill_value = 0.0), q.reindex(index, fill_value = 0.0)
    return float(np.sqrt(0.5 * np.sum((np.sqrt(p) - np.sqrt(q))**2)))

def execute(context):
    top_k = context.config("territory_chains_top_k")

    df_population = population_chains(context)
    df_survey = survey_chains(context)
    has_reference = not df_survey["urban_type"].isna().any()

    # Chains are compared on the most frequent ones in the survey, the others are pooled
    top_chains = weighted_shares(df_survey, "chain").sort_values(ascending = False).index[:top_k]

    for df in (df_population, df_survey):
        df["chain_class"] = df["chain"].where(df["chain"].isin(top_chains), "other")

    df_indicators, df_chains, df_donors = [], [], []

    for urban_type in URBAN_TYPES + ["all"]:
        f_population = np.ones(len(df_population), dtype = bool)
        f_survey = np.ones(len(df_survey), dtype = bool)

        if urban_type != "all":
            f_population = (df_population["urban_type"] == urban_type).values
            f_survey = (df_survey["urban_type"] == urban_type).values

        df_p, df_s = df_population[f_population], df_survey[f_survey]
        if len(df_p) == 0: continue

        row = { "urban_type": urban_type, "persons": len(df_p) }
        row.update(indicators(df_p, "population"))

        if "census_commune_id" in df_p:
            # Residents for whom the census only gives the departement: when matching,
            # they have no urban type of their own
            row["census_commune_undefined"] = float((df_p["census_commune_id"].astype(str) == "undefined").mean())

        if has_reference or urban_type == "all":
            row["respondents"] = len(df_s)
            row.update(indicators(df_s, "survey"))

            shares_p, shares_s = weighted_shares(df_p, "chain_class"), weighted_shares(df_s, "chain_class")
            row["hellinger_distance"] = hellinger(shares_p, shares_s)

            for chain in top_chains:
                df_chains.append({
                    "urban_type": urban_type, "chain": chain,
                    "population": float(shares_p.get(chain, 0.0)), "survey": float(shares_s.get(chain, 0.0))
                })

        df_indicators.append(row)

        if has_reference:
            donor_type = df_p["hts_person_id"].map(df_survey.set_index("hts_person_id")["urban_type"])
            shares = donor_type.value_counts(normalize = True)

            donor_row = { "urban_type": urban_type, "persons": len(df_p) }
            donor_row.update({ "donor_" + donor: float(shares.get(donor, 0.0)) for donor in URBAN_TYPES })

            if urban_type != "all":
                donor_row["donor_same_urban_type"] = float(shares.get(urban_type, 0.0))
            else:
                donor_row["donor_same_urban_type"] = float((donor_type.values == df_p["urban_type"].values).mean())

            df_donors.append(donor_row)

    result = {
        "indicators": pd.DataFrame.from_records(df_indicators),
        "chains": pd.DataFrame.from_records(df_chains),
        "donors": pd.DataFrame.from_records(df_donors),
    }

    output_path = context.config("output_path")

    if os.path.isdir(output_path):
        for name, df in result.items():
            if len(df) > 0:
                df.to_csv("%s/%schains_by_territory_%s.csv" % (
                    output_path, context.config("output_prefix"), name), sep = ";", index = False)

    return result
