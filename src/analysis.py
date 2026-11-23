"""Lost talent at the International Mathematical Olympiad.

Reads data/processed/country_panel.csv (built by prepare_data.py), writes three
figures to figures/ and the key numbers to results/results.md.

Run from the repository root:
    python src/prepare_data.py
    python src/analysis.py
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "data" / "processed" / "country_panel.csv"
FIGURES = ROOT / "figures"
RESULTS = ROOT / "results"

# Palette: one blue ramp (light -> dark) plus neutral inks
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#e4e3df"
BLUE_LIGHT, BLUE_MID, BLUE_DARK = "#86b6ef", "#2a78d6", "#0d366b"
QUARTILE_LABELS = ["Poorest 25%", "Lower-middle", "Upper-middle", "Richest 25%"]

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "font.size": 11, "axes.edgecolor": INK_2, "axes.labelcolor": INK_2,
    "xtick.color": INK_2, "ytick.color": INK_2, "text.color": INK,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.titlesize": 13, "axes.titleweight": "bold", "axes.titlelocation": "left",
})


def ols_hc1(y: np.ndarray, regressors: list[np.ndarray]):
    """OLS with heteroskedasticity-robust (HC1) standard errors."""
    X = np.column_stack([np.ones(len(y))] + regressors)
    beta = np.linalg.lstsq(X, y, rcond=None)[0]
    resid = y - X @ beta
    n, k = X.shape
    xtx_inv = np.linalg.inv(X.T @ X)
    cov = xtx_inv @ (X.T * resid**2) @ X @ xtx_inv * n / (n - k)
    r2 = 1 - resid @ resid / ((y - y.mean()) @ (y - y.mean()))
    return beta, np.sqrt(np.diag(cov)), r2, n


def style_axis(ax, ygrid=True):
    if ygrid:
        ax.yaxis.grid(True, color=GRID, linewidth=0.8)
        ax.set_axisbelow(True)
    ax.tick_params(length=0)


def fig_participation(panel: pd.DataFrame) -> pd.DataFrame:
    by_q = panel.groupby("income_quartile").agg(
        countries=("iso3", "size"), took_part=("participated", "sum"))
    by_q["rate"] = by_q["took_part"] / by_q["countries"] * 100

    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    bars = ax.bar(QUARTILE_LABELS, by_q["rate"], color=BLUE_MID, width=0.6,
                  edgecolor=SURFACE, linewidth=2)
    for bar, (_, row) in zip(bars, by_q.iterrows()):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 2,
                f"{row.rate:.0f}%\n({int(row.took_part)} of {int(row.countries)})",
                ha="center", va="bottom", fontsize=10, color=INK)
    ax.set_ylim(0, 115)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_ylabel("Countries that sent a team (%)")
    ax.set_title("Most of the poorest countries never send a team",
                 pad=26)
    ax.text(0, 1.025, "Share of countries with at least one IMO team, 2015-2024, "
            "by GDP per capita quartile", transform=ax.transAxes,
            fontsize=9.5, color=INK_2)
    style_axis(ax)
    fig.tight_layout()
    fig.savefig(FIGURES / "1_participation_by_income.png", dpi=200)
    plt.close(fig)
    return by_q


def fig_funnel(panel: pd.DataFrame) -> pd.DataFrame:
    shares = pd.DataFrame({
        "Population": panel.groupby("income_quartile")["population"].sum(),
        "IMO contestants": panel.groupby("income_quartile")["contestants"].sum(),
        "Gold medals": panel.groupby("income_quartile")["gold"].sum(),
    })
    shares = shares / shares.sum() * 100

    fig, ax = plt.subplots(figsize=(8.5, 4.8))
    x = np.arange(4)
    width = 0.26
    colors = [BLUE_LIGHT, BLUE_MID, BLUE_DARK]
    for i, (col, color) in enumerate(zip(shares.columns, colors)):
        bars = ax.bar(x + (i - 1) * width, shares[col], width, label=col,
                      color=color, edgecolor=SURFACE, linewidth=2)
        for bar, value in zip(bars, shares[col]):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.8,
                    f"{value:.1f}" if value < 1 else f"{value:.0f}",
                    ha="center", va="bottom", fontsize=8.5, color=INK_2)
    ax.set_xticks(x, QUARTILE_LABELS)
    ax.set_ylabel("Share of the total (%)")
    ax.set_ylim(0, 55)
    ax.set_title("From people to gold medals, the poorest countries almost vanish",
                 pad=26)
    ax.text(0, 1.025, "Share of world population, IMO contestants and gold medals, "
            "2015-2024, by GDP per capita quartile", transform=ax.transAxes,
            fontsize=9.5, color=INK_2)
    ax.legend(frameon=False, loc="upper left", ncol=3, fontsize=9.5)
    style_axis(ax)
    fig.tight_layout()
    fig.savefig(FIGURES / "2_population_contestants_gold.png", dpi=200)
    plt.close(fig)
    return shares


def fig_scores(panel: pd.DataFrame):
    teams = panel[panel["participated"]].copy()
    teams["log_gdp"] = np.log10(teams["gdp_pc"])
    teams["log_pop"] = np.log10(teams["population"])
    beta, se, r2, n = ols_hc1(teams["score_per_contestant"].to_numpy(),
                              [teams["log_gdp"].to_numpy(), teams["log_pop"].to_numpy()])

    fig, ax = plt.subplots(figsize=(8.5, 5.2))
    sizes = 12 + 160 * (teams["population"] / teams["population"].max()) ** 0.5
    ax.scatter(teams["gdp_pc"], teams["score_per_contestant"], s=sizes,
               color=BLUE_MID, alpha=0.75, edgecolor=SURFACE, linewidth=1)
    # Simple fit line on log income, for the eye
    slope, intercept = np.polyfit(teams["log_gdp"], teams["score_per_contestant"], 1)
    xs = np.linspace(teams["log_gdp"].min(), teams["log_gdp"].max(), 100)
    ax.plot(10 ** xs, intercept + slope * xs, color=INK_2, linewidth=1.5,
            linestyle="--")
    labels = {"China": "China", "United States": "USA", "Viet Nam": "Vietnam",
              "India": "India", "Pakistan": "Pakistan", "Nigeria": "Nigeria",
              "Italy": "Italy", "Iran, Islamic Rep.": "Iran", "Ukraine": "Ukraine"}
    offsets = {"Ukraine": (-50, 3), "Italy": (-46, 22)}
    for _, row in teams[teams["wb_name"].isin(labels)].iterrows():
        ax.annotate(labels[row.wb_name], (row.gdp_pc, row.score_per_contestant),
                    xytext=offsets.get(row.wb_name, (6, 4)), textcoords="offset points",
                    fontsize=9, color=INK,
                    arrowprops=(dict(arrowstyle="-", color=INK_2, linewidth=0.8)
                                if row.wb_name == "Italy" else None))
    italy = teams[teams["wb_name"] == "Italy"]
    ax.scatter(italy["gdp_pc"], italy["score_per_contestant"], s=60, facecolor="none",
               edgecolor=INK, linewidth=1.2)
    ax.set_xscale("log")
    ax.set_xticks([500, 1000, 5000, 10000, 50000], ["$500", "$1k", "$5k", "$10k", "$50k"])
    ax.set_xlabel("GDP per capita, 2015-2023 average (current US$, log scale)")
    ax.set_ylabel("Points per contestant (max 42)")
    ax.set_ylim(0, 42)
    ax.set_title("Richer countries score higher, but some middle-income countries beat them",
                 pad=26)
    ax.text(0, 1.025, f"{n} countries that took part in the IMO 2015-2024; "
            "dot size = population", transform=ax.transAxes, fontsize=9.5, color=INK_2)
    style_axis(ax)
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    fig.tight_layout()
    fig.savefig(FIGURES / "3_scores_vs_income.png", dpi=200)
    plt.close(fig)
    return beta, se, r2, n


def main() -> None:
    FIGURES.mkdir(exist_ok=True)
    RESULTS.mkdir(exist_ok=True)
    panel = pd.read_csv(PANEL)

    by_q = fig_participation(panel)
    shares = fig_funnel(panel)
    beta, se, r2, n = fig_scores(panel)

    gdp_ranges = panel.groupby("income_quartile")["gdp_pc"].agg(["min", "max"])
    lines = [
        "# Results",
        "",
        f"Countries in the panel (population >= 1 million): {len(panel)}",
        "",
        "## 1. Participation by income quartile (2015-2024)",
        "",
        "| Quartile | GDP per capita (US$) | Countries | Sent a team | Rate |",
        "| --- | --- | --- | --- | --- |",
    ]
    for q, label in zip(range(1, 5), QUARTILE_LABELS):
        lo, hi = gdp_ranges.loc[q]
        row = by_q.loc[q]
        lines.append(f"| {label} | {lo:,.0f}-{hi:,.0f} | {int(row.countries)} | "
                     f"{int(row.took_part)} | {row.rate:.0f}% |")
    lines += ["", "## 2. Shares of population, contestants and gold medals (%)", "",
              "| Quartile | Population | IMO contestants | Gold medals |",
              "| --- | --- | --- | --- |"]
    for q, label in zip(range(1, 5), QUARTILE_LABELS):
        s = shares.loc[q]
        lines.append(f"| {label} | {s['Population']:.1f} | {s['IMO contestants']:.1f} | "
                     f"{s['Gold medals']:.1f} |")
    lines += ["", "## 3. Points per contestant vs income (OLS, robust HC1 standard errors)", "",
              "| Term | Coefficient | Std. error |", "| --- | --- | --- |",
              f"| Intercept | {beta[0]:.2f} | {se[0]:.2f} |",
              f"| log10 GDP per capita | {beta[1]:.2f} | {se[1]:.2f} |",
              f"| log10 population | {beta[2]:.2f} | {se[2]:.2f} |",
              "", f"R-squared = {r2:.2f}, N = {n} countries"]
    (RESULTS / "results.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
