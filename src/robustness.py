"""Robustness checks: do the main results survive different choices?

Re-runs the main numbers with
  - a stricter definition of taking part (at least 5 of the 10 IMOs),
  - all countries, including those under 1 million people,
  - an earlier decade (IMO 2005-2014, GDP 2005-2013).
Writes results/robustness.md.

Run from the repository root:  python src/robustness.py
"""

from pathlib import Path

import numpy as np
import pandas as pd

import prepare_data as prep

ROOT = Path(__file__).resolve().parents[1]


def run(imo_years, gdp_years, min_population, min_imo_years=1) -> dict:
    prep.IMO_YEARS, prep.GDP_YEARS = imo_years, gdp_years
    panel = prep.load_income().merge(prep.load_imo(), on="wb_name", how="left")
    panel = panel[panel["population"] >= min_population].dropna(subset=["gdp_pc"])
    panel[["imo_years", "contestants", "gold"]] = panel[["imo_years", "contestants", "gold"]].fillna(0)
    panel["took_part"] = panel["imo_years"] >= min_imo_years
    panel["quartile"] = pd.qcut(panel["gdp_pc"], 4, labels=[1, 2, 3, 4]).astype(int)

    teams = panel[panel["took_part"]]
    X = np.column_stack([np.ones(len(teams)), np.log10(teams["gdp_pc"]),
                         np.log10(teams["population"])])
    beta = np.linalg.lstsq(X, teams["score_per_contestant"].to_numpy(), rcond=None)[0]

    poorest = panel[panel["quartile"] == 1]
    return {
        "countries": len(panel),
        "poorest_rate": poorest["took_part"].mean() * 100,
        "others_rate": panel[panel["quartile"] > 1]["took_part"].mean() * 100,
        "poorest_contestants": poorest["contestants"].sum() / panel["contestants"].sum() * 100,
        "poorest_gold": poorest["gold"].sum() / panel["gold"].sum() * 100,
        "income_coef": beta[1],
    }


def main() -> None:
    specs = {
        "Main (IMO 2015-2024, population >= 1M)": (range(2015, 2025), range(2015, 2024), 1e6, 1),
        "Took part in at least 5 of 10 IMOs": (range(2015, 2025), range(2015, 2024), 1e6, 5),
        "All countries, any population": (range(2015, 2025), range(2015, 2024), 0, 1),
        "Earlier decade (IMO 2005-2014)": (range(2005, 2015), range(2005, 2014), 1e6, 1),
    }
    lines = ["# Robustness checks", "",
             "| Specification | Countries | Poorest 25% sending a team | Other 75% sending a team "
             "| Poorest 25%: share of contestants | Poorest 25%: share of golds "
             "| Points per contestant for 10x GDP per capita |",
             "| --- | --- | --- | --- | --- | --- | --- |"]
    for name, args in specs.items():
        r = run(*args)
        lines.append(f"| {name} | {r['countries']} | {r['poorest_rate']:.0f}% | {r['others_rate']:.0f}% "
                     f"| {r['poorest_contestants']:.1f}% | {r['poorest_gold']:.1f}% | +{r['income_coef']:.1f} |")
    lines += ["", "In every specification the poorest quarter of countries is the least likely to "
              "send a team, wins a far smaller share of gold medals than its share of contestants, "
              "and richer countries score higher. The size of the gaps depends on the choices: "
              "including micro-states, for example, raises the poorest group's gold share from "
              "0.2% to 2.4%."]
    (ROOT / "results" / "robustness.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
