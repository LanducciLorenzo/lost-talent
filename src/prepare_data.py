"""Build a country-level panel linking International Mathematical Olympiad (IMO)
results to national income and population.

Inputs (data/raw):
  imo_country_results.csv  - IMO results by country and year, 1959-2024
                             (TidyTuesday 2024-09-24, from imo-official.org)
  gdp_current_usd.csv      - GDP in current US$ by country and year (World Bank,
                             via github.com/datasets/gdp)
  population.csv           - population by country and year (World Bank,
                             via github.com/datasets/population)

Output (data/processed):
  country_panel.csv        - one row per country with population >= 1 million
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"

IMO_YEARS = range(2015, 2025)      # the last ten IMOs in the data
GDP_YEARS = range(2015, 2024)      # matching period for income
MIN_POPULATION = 1_000_000         # leave out micro-states

# IMO country names that differ from World Bank names
IMO_TO_WB = {
    "Czech Republic": "Czechia",
    "Egypt": "Egypt, Arab Rep.",
    "Hong Kong": "Hong Kong SAR, China",
    "Islamic Republic of Iran": "Iran, Islamic Rep.",
    "Ivory Coast": "Cote d'Ivoire",
    "Kyrgyzstan": "Kyrgyz Republic",
    "Laos": "Lao PDR",
    "Macau": "Macao SAR, China",
    "Palestine": "West Bank and Gaza",
    "People's Republic of China": "China",
    "Republic of Korea": "Korea, Rep.",
    "Republic of Moldova": "Moldova",
    "Slovakia": "Slovak Republic",
    "Syria": "Syrian Arab Republic",
    "Türkiye": "Turkiye",
    "United States of America": "United States",
    "Venezuela": "Venezuela, RB",
    "Vietnam": "Viet Nam",
    # Not in World Bank data, so they drop out of the merge:
    # "Taiwan", "Democratic People's Republic of Korea"
}

# World Bank regional and income aggregates (not countries)
WB_AGGREGATES = {
    "AFE", "AFW", "ARB", "CEB", "CSS", "EAP", "EAR", "EAS", "ECA", "ECS", "EMU",
    "EUU", "FCS", "HIC", "HPC", "IBD", "IBT", "IDA", "IDB", "IDX", "INX", "LAC",
    "LCN", "LDC", "LIC", "LMC", "LMY", "LTE", "MEA", "MIC", "MNA", "NAC", "OED",
    "OSS", "PRE", "PSS", "PST", "SAS", "SSA", "SSF", "SST", "TEA", "TEC", "TLA",
    "TMN", "TSA", "TSS", "UMC", "WLD",
}

PROBLEMS = ["p1", "p2", "p3", "p4", "p5", "p6"]


def load_income() -> pd.DataFrame:
    gdp = pd.read_csv(RAW / "gdp_current_usd.csv")
    pop = pd.read_csv(RAW / "population.csv")
    gdp = gdp.rename(columns={"Country Name": "wb_name", "Country Code": "iso3",
                              "Year": "year", "Value": "gdp"})
    pop = pop.rename(columns={"Country Name": "wb_name", "Country Code": "iso3",
                              "Year": "year", "Value": "population"})
    df = gdp.merge(pop[["iso3", "year", "population"]], on=["iso3", "year"])
    df = df[df["year"].isin(GDP_YEARS) & ~df["iso3"].isin(WB_AGGREGATES)]
    df["gdp_pc"] = df["gdp"] / df["population"]
    return (df.groupby(["iso3", "wb_name"], as_index=False)
              .agg(gdp_pc=("gdp_pc", "mean"), population=("population", "mean")))


def load_imo() -> pd.DataFrame:
    imo = pd.read_csv(RAW / "imo_country_results.csv")
    imo = imo[imo["year"].isin(IMO_YEARS)].copy()
    imo["team_points"] = imo[PROBLEMS].sum(axis=1)
    imo["wb_name"] = imo["country"].replace(IMO_TO_WB)
    out = imo.groupby("wb_name", as_index=False).agg(
        imo_name=("country", "first"),
        imo_years=("year", "nunique"),
        contestants=("team_size_all", "sum"),
        points=("team_points", "sum"),
        gold=("awards_gold", "sum"),
        silver=("awards_silver", "sum"),
        bronze=("awards_bronze", "sum"),
    )
    out["score_per_contestant"] = out["points"] / out["contestants"]  # max 42
    out["medals"] = out[["gold", "silver", "bronze"]].sum(axis=1)
    return out


def main() -> None:
    income = load_income()
    imo = load_imo()

    unmatched = sorted(set(imo["wb_name"]) - set(income["wb_name"]))
    print("IMO teams without World Bank income data (dropped):", unmatched)

    panel = income.merge(imo, on="wb_name", how="left")
    panel = panel[panel["population"] >= MIN_POPULATION].dropna(subset=["gdp_pc"])
    panel["participated"] = panel["imo_years"].fillna(0) > 0
    for col in ["imo_years", "contestants", "points", "gold", "silver", "bronze", "medals"]:
        panel[col] = panel[col].fillna(0).astype(int)

    # Income quartiles among all countries in the panel (1 = poorest)
    panel["income_quartile"] = pd.qcut(panel["gdp_pc"], 4, labels=[1, 2, 3, 4]).astype(int)

    PROCESSED.mkdir(parents=True, exist_ok=True)
    panel = panel.sort_values("gdp_pc").reset_index(drop=True)
    panel.to_csv(PROCESSED / "country_panel.csv", index=False)
    print(f"Saved {len(panel)} countries, {panel['participated'].sum()} took part "
          f"in at least one IMO between {IMO_YEARS.start} and {IMO_YEARS.stop - 1}.")


if __name__ == "__main__":
    main()
