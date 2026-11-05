import csv
import json
import math
import statistics
import time
import urllib.error
import urllib.request
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.lines import Line2D


YEAR = "2023"
API_ROOT = "https://api.worldbank.org/v2"
INDICATORS = {
    "emissions_mt_co2e": "EN.GHG.CO2.MT.CE.AR5",
    "gdp_per_capita_usd": "NY.GDP.PCAP.CD",
    "population": "SP.POP.TOTL",
}

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
EXPORT_DIR = ROOT / "exports"
CSV_PATH = DATA_DIR / f"country_co2_income_comparison_{YEAR}.csv"
CHART_PATH = EXPORT_DIR / f"country_co2_income_scatter_{YEAR}.png"


def fetch_json(url):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "UNDataCommons-Test/1.0 (public data visualization)"},
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.load(response)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as error:
            if attempt == 2:
                raise RuntimeError(f"Could not retrieve World Bank data from {url}: {error}") from error
            time.sleep(attempt + 1)


def fetch_indicator(indicator_code):
    url = (
        f"{API_ROOT}/country/all/indicator/{indicator_code}"
        f"?date={YEAR}&format=json&per_page=3000"
    )
    payload = fetch_json(url)
    if not isinstance(payload, list) or len(payload) < 2 or not isinstance(payload[1], list):
        raise RuntimeError(f"Unexpected World Bank response for indicator {indicator_code}")
    return {
        row["countryiso3code"]: row["value"]
        for row in payload[1]
        if row.get("countryiso3code") and row.get("value") is not None
    }


def fetch_countries():
    payload = fetch_json(f"{API_ROOT}/country?format=json&per_page=400")
    if not isinstance(payload, list) or len(payload) < 2 or not isinstance(payload[1], list):
        raise RuntimeError("Unexpected World Bank country metadata response")
    return {
        row["id"]: {
            "country": row["name"],
            "region": row["region"]["value"].strip(),
        }
        for row in payload[1]
        if row.get("region", {}).get("id") not in ("", "NA")
    }


def load_rows():
    countries = fetch_countries()
    indicators = {
        name: fetch_indicator(code)
        for name, code in INDICATORS.items()
    }
    rows = []

    for iso3, country in countries.items():
        try:
            emissions = float(indicators["emissions_mt_co2e"][iso3])
            gdp_per_capita = float(indicators["gdp_per_capita_usd"][iso3])
            population = float(indicators["population"][iso3])
        except KeyError:
            continue

        if emissions <= 0 or gdp_per_capita <= 0 or population <= 0:
            continue

        rows.append(
            {
                "year": YEAR,
                "iso3": iso3,
                "country": country["country"],
                "region": country["region"],
                "emissions_mt_co2e": emissions,
                "population": int(population),
                "gdp_per_capita_usd": gdp_per_capita,
                "emissions_per_capita_tonnes_co2e": emissions * 1_000_000 / population,
            }
        )

    if len(rows) < 100:
        raise RuntimeError(f"Only {len(rows)} countries had complete data for {YEAR}; expected broader coverage")
    return rows


def write_csv(rows):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    columns = [
        "year",
        "iso3",
        "country",
        "region",
        "emissions_mt_co2e",
        "population",
        "gdp_per_capita_usd",
        "emissions_per_capita_tonnes_co2e",
    ]
    with CSV_PATH.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def write_chart(rows):
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    regions = sorted({row["region"] for row in rows})
    palette = plt.get_cmap("tab10")
    max_population = max(row["population"] for row in rows)

    plt.style.use("seaborn-v0_8-whitegrid")
    fig, ax = plt.subplots(figsize=(15, 8), dpi=160)

    for index, region in enumerate(regions):
        group = [row for row in rows if row["region"] == region]
        sizes = [
            16 + 90 * math.sqrt(row["population"] / max_population)
            for row in group
        ]
        ax.scatter(
            [row["gdp_per_capita_usd"] for row in group],
            [row["emissions_per_capita_tonnes_co2e"] for row in group],
            s=sizes,
            color=palette(index % 10),
            alpha=0.72,
            edgecolors="white",
            linewidths=0.5,
            label=region,
        )

    top_populated = sorted(rows, key=lambda row: row["population"], reverse=True)[:3]
    for row in top_populated:
        ax.annotate(
            row["country"],
            (row["gdp_per_capita_usd"], row["emissions_per_capita_tonnes_co2e"]),
            xytext=(6, 6),
            textcoords="offset points",
            fontsize=8,
            color="#333333",
        )

    top_per_capita = sorted(
        rows,
        key=lambda row: row["emissions_per_capita_tonnes_co2e"],
        reverse=True,
    )[:2]
    for row in top_per_capita:
        ax.annotate(
            row["country"],
            (row["gdp_per_capita_usd"], row["emissions_per_capita_tonnes_co2e"]),
            xytext=(7, -10),
            textcoords="offset points",
            fontsize=8,
            color="#333333",
        )

    log_gdp = [math.log10(row["gdp_per_capita_usd"]) for row in rows]
    emissions_per_capita = [row["emissions_per_capita_tonnes_co2e"] for row in rows]
    correlation = statistics.correlation(log_gdp, emissions_per_capita)

    ax.set_xscale("log")
    ax.set_xlabel("GDP per capita (current US$, logarithmic scale)", fontsize=11)
    ax.set_ylabel("CO2 emissions per capita (tonnes CO2e)", fontsize=11)
    ax.set_title(
        f"Income and CO2 emissions per person, {YEAR}",
        fontsize=18,
        weight="bold",
        pad=16,
    )
    ax.text(
        0.02,
        0.97,
        f"{len(rows)} countries/economies  |  correlation with log GDP per capita: {correlation:.2f}",
        transform=ax.transAxes,
        va="top",
        fontsize=10,
        color="#34495e",
    )
    ax.text(
        0.02,
        0.02,
        "Bubble size represents population (scaled for readability). Correlation is descriptive, not causal.",
        transform=ax.transAxes,
        fontsize=8,
        color="#555555",
    )
    ax.grid(True, which="major", linewidth=0.7, alpha=0.25)
    region_legend = ax.legend(
        title="World Bank region",
        frameon=False,
        loc="upper left",
        bbox_to_anchor=(1.02, 1),
        fontsize=8,
    )
    ax.add_artist(region_legend)
    population_values = (10_000_000, 100_000_000, 1_000_000_000)
    population_handles = [
        Line2D(
            [],
            [],
            linestyle="",
            marker="o",
            markersize=math.sqrt(16 + 90 * math.sqrt(value / max_population)),
            markerfacecolor="#718096",
            markeredgecolor="white",
            label=f"{value // 1_000_000}M",
        )
        for value in population_values
    ]
    ax.legend(
        handles=population_handles,
        title="Population",
        frameon=False,
        loc="lower left",
        bbox_to_anchor=(1.02, 0.05),
        fontsize=8,
    )
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)

    fig.text(
        0.01,
        0.005,
        "Sources: World Bank WDI (GDP, population, and CO2 emissions); emissions indicator sourced from EDGAR/JRC, excluding LULUCF.",
        fontsize=7,
        color="#555555",
    )
    fig.subplots_adjust(left=0.09, right=0.68, bottom=0.14, top=0.90)
    fig.savefig(CHART_PATH)
    plt.close(fig)
    return correlation


def print_insights(rows, correlation):
    by_total = sorted(rows, key=lambda row: row["emissions_mt_co2e"], reverse=True)
    by_capita = sorted(
        rows,
        key=lambda row: row["emissions_per_capita_tonnes_co2e"],
        reverse=True,
    )
    median_per_capita = statistics.median(
        row["emissions_per_capita_tonnes_co2e"] for row in rows
    )

    print(f"Saved {len(rows)} country/economy records for {YEAR} to {CSV_PATH}")
    print(f"Saved chart to {CHART_PATH}")
    print(
        f"Median emissions per capita: {median_per_capita:.2f} tonnes CO2e; "
        f"correlation with log GDP per capita: {correlation:.2f}"
    )
    print("Largest total emitters (Mt CO2e):")
    for row in by_total[:5]:
        print(f"  {row['country']}: {row['emissions_mt_co2e']:,.0f}")
    print("Highest emissions per capita (tonnes CO2e):")
    for row in by_capita[:5]:
        print(
            f"  {row['country']}: "
            f"{row['emissions_per_capita_tonnes_co2e']:.1f}"
        )


def main():
    rows = load_rows()
    write_csv(rows)
    correlation = write_chart(rows)
    print_insights(rows, correlation)


if __name__ == "__main__":
    main()
