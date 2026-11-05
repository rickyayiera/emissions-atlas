import json
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.table import Table, TableStyleInfo


START_YEAR = 2000
END_YEAR = 2023
API_ROOT = "https://api.worldbank.org/v2"
INDICATORS = {
    "EmissionsMtCO2e": {
        "code": "EN.GHG.CO2.MT.CE.AR5",
        "name": "Carbon dioxide (CO2) emissions (total) excluding LULUCF",
        "unit": "Mt CO2e",
        "definition": (
            "Annual CO2 emissions from agriculture, energy, waste, and industrial "
            "sectors; excludes land use, land-use change, and forestry (LULUCF)."
        ),
        "source": (
            "EDGAR Community GHG Database, Joint Research Centre (European Commission), "
            "and International Energy Agency, distributed through World Bank WDI."
        ),
    },
    "GDPPerCapitaUSD": {
        "code": "NY.GDP.PCAP.CD",
        "name": "GDP per capita (current US$)",
        "unit": "current US$ per person",
        "definition": "Gross domestic product divided by midyear population, in current US dollars.",
        "source": "World Bank World Development Indicators.",
    },
    "Population": {
        "code": "SP.POP.TOTL",
        "name": "Population, total",
        "unit": "persons",
        "definition": "Total population based on the de facto definition of population.",
        "source": "World Bank World Development Indicators.",
    },
}

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
WORKBOOK_PATH = DATA_DIR / f"emissions_powerbi_{START_YEAR}_{END_YEAR}.xlsx"
YEARS = list(range(START_YEAR, END_YEAR + 1))


def fetch_json(url):
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "UNDataCommons-Test/1.0 (public data visualization)"},
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                return json.load(response)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as error:
            if attempt == 2:
                raise RuntimeError(f"Could not retrieve World Bank data from {url}: {error}") from error
            time.sleep(attempt + 1)


def fetch_country_metadata():
    url = f"{API_ROOT}/country?format=json&per_page=400"
    payload = fetch_json(url)
    if not isinstance(payload, list) or len(payload) < 2 or not isinstance(payload[1], list):
        raise RuntimeError("Unexpected World Bank country metadata response")

    countries = {}
    for row in payload[1]:
        region = row.get("region", {})
        iso3 = row.get("id", "")
        if not iso3 or region.get("id") in ("", "NA"):
            continue
        countries[iso3] = {
            "Country": row["name"],
            "Region": region["value"].strip(),
            "IncomeLevel": row.get("incomeLevel", {}).get("value", ""),
            "LendingType": row.get("lendingType", {}).get("value", ""),
        }
    if not countries:
        raise RuntimeError("World Bank country metadata contained no country records")
    return countries


def fetch_indicator(indicator):
    url = (
        f"{API_ROOT}/country/all/indicator/{indicator['code']}"
        f"?date={START_YEAR}:{END_YEAR}&format=json&per_page=20000"
    )
    payload = fetch_json(url)
    if not isinstance(payload, list) or len(payload) < 2 or not isinstance(payload[1], list):
        raise RuntimeError(f"Unexpected World Bank response for {indicator['code']}")

    observations = {}
    for row in payload[1]:
        iso3 = row.get("countryiso3code")
        date = row.get("date")
        value = row.get("value")
        if iso3 and date and value is not None:
            observations[(iso3, int(date))] = float(value)
    if not observations:
        raise RuntimeError(f"No observations returned for World Bank indicator {indicator['code']}")
    return observations


def make_country_year_rows(countries, observations):
    emissions, gdp_per_capita, population = (
        observations["EmissionsMtCO2e"],
        observations["GDPPerCapitaUSD"],
        observations["Population"],
    )
    rows = []

    for iso3 in sorted(countries):
        for year in YEARS:
            emissions_value = emissions.get((iso3, year))
            gdp_value = gdp_per_capita.get((iso3, year))
            population_value = population.get((iso3, year))
            if emissions_value is None and gdp_value is None and population_value is None:
                continue

            valid_population = population_value is not None and population_value > 0
            valid_gdp = gdp_value is not None and gdp_value > 0
            valid_emissions = emissions_value is not None and emissions_value >= 0
            emissions_per_capita = (
                emissions_value * 1_000_000 / population_value
                if valid_emissions and valid_population
                else None
            )
            emissions_per_gdp = (
                emissions_value * 1_000_000_000 / (gdp_value * population_value)
                if valid_emissions and valid_gdp and valid_population
                else None
            )
            rows.append(
                [
                    year,
                    iso3,
                    emissions_value,
                    population_value,
                    gdp_value,
                    emissions_per_capita,
                    emissions_per_gdp,
                ]
            )

    if not rows:
        raise RuntimeError("No country-year observations were available to export")
    return rows


def add_table_sheet(workbook, name, table_name, headers, rows, number_formats=None):
    sheet = workbook.create_sheet(name)
    sheet.append(headers)
    for row in rows:
        sheet.append(row)

    sheet.freeze_panes = "A2"
    sheet.sheet_view.showGridLines = False
    table = Table(displayName=table_name, ref=sheet.dimensions)
    table.tableStyleInfo = TableStyleInfo(
        name="TableStyleMedium2",
        showFirstColumn=False,
        showLastColumn=False,
        showRowStripes=True,
        showColumnStripes=False,
    )
    sheet.add_table(table)

    for cell in sheet[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill(fill_type="solid", fgColor="145A72")
        cell.alignment = Alignment(vertical="center")
    sheet.row_dimensions[1].height = 24

    for column_cells in sheet.columns:
        column_letter = column_cells[0].column_letter
        max_length = max(len(str(cell.value or "")) for cell in column_cells)
        sheet.column_dimensions[column_letter].width = min(max(max_length + 2, 12), 42)

    for column_name, number_format in (number_formats or {}).items():
        column_index = headers.index(column_name) + 1
        for row_index in range(2, sheet.max_row + 1):
            sheet.cell(row=row_index, column=column_index).number_format = number_format
    return sheet


def build_workbook(countries, fact_rows, downloaded_at):
    workbook = Workbook()
    workbook.remove(workbook.active)
    workbook.properties.title = "Country CO2 emissions and socioeconomic data"
    workbook.properties.subject = f"Power BI dataset, {START_YEAR}-{END_YEAR}"
    workbook.properties.creator = "UN Data Commons Test"

    add_table_sheet(
        workbook,
        "FactCountryYear",
        "FactCountryYear",
        [
            "Year",
            "CountryISO3",
            "EmissionsMtCO2e",
            "Population",
            "GDPPerCapitaUSD",
            "EmissionsPerCapitaTonnesCO2e",
            "EmissionsKgPerGDPUSD",
        ],
        fact_rows,
        {
            "EmissionsMtCO2e": "#,##0.0",
            "Population": "#,##0",
            "GDPPerCapitaUSD": "$#,##0.00",
            "EmissionsPerCapitaTonnesCO2e": "0.00",
            "EmissionsKgPerGDPUSD": "0.000",
        },
    )

    country_rows = [
        [
            iso3,
            country["Country"],
            country["Region"],
            country["IncomeLevel"],
            country["LendingType"],
        ]
        for iso3, country in sorted(countries.items())
    ]
    add_table_sheet(
        workbook,
        "DimCountry",
        "DimCountry",
        ["CountryISO3", "Country", "Region", "IncomeLevel", "LendingType"],
        country_rows,
    )

    add_table_sheet(
        workbook,
        "DimYear",
        "DimYear",
        ["Year", "Decade", "YearStart"],
        [[year, f"{year // 10 * 10}s", datetime(year, 1, 1)] for year in YEARS],
        {"YearStart": "yyyy-mm-dd"},
    )

    dictionary_rows = [
        [
            "Year",
            "Calendar year of observation.",
            "year",
            "World Bank observation date",
            f"{START_YEAR}-{END_YEAR}",
        ],
        [
            "CountryISO3",
            "Three-letter country/economy code; join key to DimCountry.",
            "ISO 3166-1 alpha-3",
            "World Bank country metadata",
            "Country/economy records only; regional aggregates excluded.",
        ],
    ]
    for field, info in INDICATORS.items():
        dictionary_rows.append(
            [
                field,
                info["definition"],
                info["unit"],
                f"{info['source']} Indicator: {info['code']}",
                f"{API_ROOT}/country/all/indicator/{info['code']}?date={START_YEAR}:{END_YEAR}&format=json",
            ]
        )
    dictionary_rows.extend(
        [
            [
                "EmissionsPerCapitaTonnesCO2e",
                "EmissionsMtCO2e multiplied by 1,000,000 and divided by Population.",
                "tonnes CO2e per person",
                "Calculated from this workbook's emissions and population fields.",
                "Blank when emissions or positive population is unavailable.",
            ],
            [
                "EmissionsKgPerGDPUSD",
                "Emissions in kg CO2e divided by total GDP (GDP per capita multiplied by population).",
                "kg CO2e per current US$",
                "Calculated from this workbook's emissions, GDP per capita, and population fields.",
                "Uses GDP in current US dollars; blank when a required value is unavailable.",
            ],
        ]
    )
    add_table_sheet(
        workbook,
        "FieldGuide",
        "FieldGuide",
        ["Field", "Definition", "Unit", "Source", "NotesOrAPI"],
        dictionary_rows,
    )
    workbook["FieldGuide"].column_dimensions["B"].width = 68
    workbook["FieldGuide"].column_dimensions["D"].width = 58
    workbook["FieldGuide"].column_dimensions["E"].width = 72
    for row in workbook["FieldGuide"].iter_rows(min_row=2):
        for cell in row[1:]:
            cell.alignment = Alignment(wrap_text=True, vertical="top")
        workbook["FieldGuide"].row_dimensions[row[0].row].height = 42

    guide_rows = [
        ["Dataset", f"Country-year observations, {START_YEAR}-{END_YEAR}"],
        ["DownloadedAtUTC", downloaded_at],
        ["Fact grain", "One row per country/economy and year where at least one source indicator is available."],
        ["Power BI relationship 1", "DimCountry[CountryISO3] (one) -> FactCountryYear[CountryISO3] (many)."],
        ["Power BI relationship 2", "DimYear[Year] (one) -> FactCountryYear[Year] (many)."],
        ["Relationship settings", "Use single-direction filtering from each dimension to FactCountryYear."],
        ["Missing data", "Blank cells represent unavailable source values; they are not zero."],
        ["Coverage", "Indicators can have different country/year coverage. Derived measures are blank if required source data is missing."],
        ["Emissions scope", "CO2 emissions from agriculture, energy, waste, and industry; excludes LULUCF. This is not identical to the separate fuel-combustion time series in this workspace."],
        ["GDP comparability", "GDP per capita is in current US dollars and is not adjusted for inflation or purchasing power."],
        ["Interpretation", "Country-level associations are descriptive and do not establish causality."],
        ["World Bank API", API_ROOT],
    ]
    add_table_sheet(workbook, "ModelGuide", "ModelGuide", ["Topic", "Details"], guide_rows)
    workbook["ModelGuide"].column_dimensions["A"].width = 30
    workbook["ModelGuide"].column_dimensions["B"].width = 115
    for row in workbook["ModelGuide"].iter_rows(min_row=2):
        row[1].alignment = Alignment(wrap_text=True, vertical="top")
        workbook["ModelGuide"].row_dimensions[row[0].row].height = 32

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    workbook.save(WORKBOOK_PATH)


def main():
    countries = fetch_country_metadata()
    observations = {
        field: fetch_indicator(indicator)
        for field, indicator in INDICATORS.items()
    }
    fact_rows = make_country_year_rows(countries, observations)
    downloaded_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    build_workbook(countries, fact_rows, downloaded_at)

    print(f"Saved Power BI workbook: {WORKBOOK_PATH}")
    print(f"Country/economy dimension rows: {len(countries)}")
    print(f"Country-year fact rows: {len(fact_rows)}")
    for field, values in observations.items():
        print(f"{field} observations: {len(values)}")


if __name__ == "__main__":
    main()
