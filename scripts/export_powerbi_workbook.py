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
MCP_URL = "https://unsd-datacommons.gcp.un-icc.cloud/mcp"
SAMPLE_COUNTRIES = ["USA", "China", "Germany", "Nigeria", "Brazil"]
INDICATORS = {
    "EmissionsMtCO2": {
        "query": "carbon dioxide emissions",
        "name": "Carbon dioxide emissions from fuel combustion",
        "unit": "Mt CO2",
        "definition": "Annual carbon dioxide emissions from fuel combustion, converted from tonnes to million tonnes.",
        "source": "United Nations Statistics Division SDG Data Portal.",
    },
    "GDPUSD": {
        "query": "gross domestic product current prices US dollars",
        "name": "Gross domestic product at current prices in US dollars",
        "unit": "current US$",
        "definition": "Gross domestic product at current prices, reported in US dollars.",
        "source": "UNIDO Statistics Data Portal.",
    },
    "Population": {
        "query": "total population",
        "name": "Total population",
        "unit": "persons",
        "definition": "Total population.",
        "source": "UNICEF Data.",
    },
}

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
WORKBOOK_PATH = DATA_DIR / f"emissions_powerbi_{START_YEAR}_{END_YEAR}.xlsx"
YEARS = list(range(START_YEAR, END_YEAR + 1))


def call_mcp_tool(name, arguments):
    body = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        MCP_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
        method="POST",
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                payload = json.load(response)
            if "error" in payload:
                raise RuntimeError(f"Data Commons MCP error: {payload['error']}")
            result = payload.get("result", {})
            if result.get("isError"):
                raise RuntimeError(f"Data Commons tool {name} failed: {result}")
            text = next(
                (item.get("text") for item in result.get("content", []) if item.get("type") == "text"),
                None,
            )
            if text is not None:
                return json.loads(text)
            return result
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as error:
            if attempt == 2:
                raise RuntimeError(f"Could not call Data Commons tool {name}: {error}") from error
            time.sleep(attempt + 1)
    raise RuntimeError(f"Data Commons tool {name} did not return a result")


def fetch_country_metadata():
    url = "https://api.worldbank.org/v2/country?format=json&per_page=400"
    request = urllib.request.Request(url, headers={"User-Agent": "UNDataCommons-Test/1.0"})
    with urllib.request.urlopen(request, timeout=90) as response:
        payload = json.load(response)
    if not isinstance(payload, list) or len(payload) < 2 or not isinstance(payload[1], list):
        raise RuntimeError("Unexpected World Bank country classification response")

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


def discover_indicators():
    variables = {}
    for field, info in INDICATORS.items():
        response = call_mcp_tool(
            "search_child_indicators",
            {
                "query": info["query"],
                "parent_place": "World",
                "sample_child_places": SAMPLE_COUNTRIES,
                "include_topics": False,
            },
        )
        mappings = response.get("dcidNameMappings", {})
        matches = [
            item["dcid"]
            for item in response.get("variables", [])
            if mappings.get(item["dcid"]) == info["name"]
        ]
        if response.get("status") != "SUCCESS" or len(matches) != 1:
            raise RuntimeError(
                f"Expected one Data Commons indicator named {info['name']!r}; "
                f"found {matches or 'no exact match'}"
            )
        variables[field] = matches[0]
    return variables


def assess_indicators(variable_dcids):
    response = call_mcp_tool(
        "get_variable_metadata",
        {
            "variable_dcids": list(variable_dcids.values()),
            "entity_dcids": [
                "country/USA",
                "country/CHN",
                "country/DEU",
                "country/NGA",
                "country/BRA",
            ],
        },
    )
    if response.get("status") != "SUCCESS":
        raise RuntimeError(f"Data Commons metadata assessment failed: {response}")
    sources = {}
    for field, dcid in variable_dcids.items():
        metadata = response.get("variables", {}).get(dcid)
        if not metadata:
            raise RuntimeError(f"Data Commons returned no metadata for {dcid}")
        facets = [
            facet
            for facet in metadata.get("facets", [])
            if int(facet.get("dateRange", {}).get("start", END_YEAR + 1)) <= START_YEAR
            and int(facet.get("dateRange", {}).get("end", 0)) >= END_YEAR
        ]
        if len(facets) != 1:
            ranges = [facet.get("dateRange") for facet in metadata.get("facets", [])]
            raise RuntimeError(
                f"Expected one {START_YEAR}-{END_YEAR} source for {dcid}; found ranges {ranges}"
            )
        facet = facets[0]
        sources[field] = {
            "dcid": dcid,
            "source_id": facet["id"],
            "date_range": facet["dateRange"],
            "observation_period": facet.get("properties", {}).get("observationPeriod", ""),
            "unit": facet.get("properties", {}).get("unit", ""),
            "provenance": response.get("provenances", {}).get(facet.get("provenanceId"), {}),
        }
    return sources


def fetch_indicator(variable_dcid, source_id):
    payload = call_mcp_tool(
        "get_child_observations",
        {
            "variable_dcid": variable_dcid,
            "parent_place_dcid": "Earth",
            "child_place_type": "Country",
            "date": "range",
            "date_range_start": str(START_YEAR),
            "date_range_end": str(END_YEAR),
            "source_override": source_id,
        },
    )
    if not payload.get("data") or not payload.get("entityMetadata"):
        raise RuntimeError(f"Unexpected Data Commons response for {variable_dcid}")
    if payload.get("variable", {}).get("dcid") != variable_dcid:
        raise RuntimeError(f"Data Commons returned an unexpected indicator for {variable_dcid}")
    names = {
        dcid.removeprefix("country/"): name
        for dcid, name in payload["entityMetadata"].get("rows", [])
        if dcid.startswith("country/")
    }
    observations = {}
    for place, date, value in payload["data"].get("rows", []):
        if place.startswith("country/") and value is not None:
            observations[(place.removeprefix("country/"), int(date))] = float(value)
    if not observations:
        raise RuntimeError(f"No observations returned for Data Commons indicator {variable_dcid}")
    years = {year for _, year in observations}
    if min(years) > START_YEAR or max(years) < END_YEAR:
        raise RuntimeError(
            f"Data Commons observations for {variable_dcid} cover {min(years)}-{max(years)}, "
            f"not the requested {START_YEAR}-{END_YEAR}"
        )
    return observations, names, payload.get("sourceMetadata", {})


def make_country_year_rows(countries, observations):
    rows = []

    iso3_codes = sorted(set(countries) | {
        iso3 for values in observations.values() for iso3, _ in values
    })
    population = observations["Population"]
    for iso3 in iso3_codes:
        for year in YEARS:
            emissions_tonnes = observations["EmissionsMtCO2"].get((iso3, year))
            gdp_value = observations["GDPUSD"].get((iso3, year))
            population_value = population.get((iso3, year))
            if emissions_tonnes is None and gdp_value is None and population_value is None:
                continue

            emissions_value = emissions_tonnes / 1_000_000 if emissions_tonnes is not None else None
            valid_population = population_value is not None and population_value > 0
            valid_gdp = gdp_value is not None and gdp_value >= 0
            valid_emissions = emissions_value is not None and emissions_value >= 0
            gdp_per_capita = (
                gdp_value / population_value if valid_gdp and valid_population else None
            )
            emissions_per_capita = (
                emissions_value * 1_000_000 / population_value
                if valid_emissions and valid_population
                else None
            )
            emissions_per_gdp = (
                emissions_value * 1_000_000_000 / gdp_value
                if valid_emissions and valid_gdp and gdp_value > 0
                else None
            )
            rows.append(
                [
                    year,
                    iso3,
                    emissions_value,
                    population_value,
                    gdp_value,
                    gdp_per_capita,
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


def build_workbook(countries, fact_rows, downloaded_at, sources):
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
            "EmissionsMtCO2",
            "Population",
            "GDPUSD",
            "GDPPerCapitaUSD",
            "EmissionsPerCapitaTonnesCO2",
            "EmissionsKgCO2PerGDPUSD",
        ],
        fact_rows,
        {
            "EmissionsMtCO2": "#,##0.0",
            "Population": "#,##0",
            "GDPUSD": "$#,##0",
            "GDPPerCapitaUSD": "$#,##0.00",
            "EmissionsPerCapitaTonnesCO2": "0.00",
            "EmissionsKgCO2PerGDPUSD": "0.000",
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
            "World Bank country metadata, supplemented with Data Commons names",
            "Unknown classifications indicate country entities absent from World Bank metadata.",
        ],
    ]
    for field, info in INDICATORS.items():
        dictionary_rows.append(
            [
                field,
                info["definition"],
                info["unit"],
                f"{info['source']} Data Commons indicator: {sources[field]['dcid']}",
                f"Source facet: {sources[field]['source_id']}; coverage assessed for {START_YEAR}-{END_YEAR}.",
            ]
        )
    dictionary_rows.extend(
        [
            [
                "GDPPerCapitaUSD",
                "GDPUSD divided by Population.",
                "current US$ per person",
                "Calculated from this workbook's GDP and population fields.",
                "Blank when GDP or positive population is unavailable.",
            ],
            [
                "EmissionsPerCapitaTonnesCO2",
                "EmissionsMtCO2 multiplied by 1,000,000 and divided by Population.",
                "tonnes CO2 per person",
                "Calculated from this workbook's emissions and population fields.",
                "Blank when emissions or positive population is unavailable.",
            ],
            [
                "EmissionsKgCO2PerGDPUSD",
                "Emissions in kg CO2 divided by GDPUSD.",
                "kg CO2 per current US$",
                "Calculated from this workbook's emissions and GDP fields.",
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
        ["Emissions scope", "CO2 from fuel combustion only; this is not total greenhouse gas emissions and is not CO2-equivalent (CO2e)."],
        ["GDP comparability", "GDP is in current US dollars and is not adjusted for inflation or purchasing power. GDP per capita is derived as GDPUSD / Population."],
        ["Classification provenance", "Country names and region/income/lending classifications are World Bank metadata where available; Data Commons names fill missing countries, with classifications marked Unknown."],
        ["Interpretation", "Country-level associations are descriptive and do not establish causality."],
        ["Observation service", MCP_URL],
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
    variable_dcids = discover_indicators()
    sources = assess_indicators(variable_dcids)
    observations = {}
    source_names = {}
    for field in INDICATORS:
        values, names, _source_metadata = fetch_indicator(
            sources[field]["dcid"], sources[field]["source_id"]
        )
        observations[field] = values
        source_names.update(names)
    for iso3, name in source_names.items():
        if iso3 not in countries:
            countries[iso3] = {
                "Country": name,
                "Region": "Unknown",
                "IncomeLevel": "Unknown",
                "LendingType": "Unknown",
            }
    fact_rows = make_country_year_rows(countries, observations)
    downloaded_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    build_workbook(countries, fact_rows, downloaded_at, sources)

    print(f"Saved Power BI workbook: {WORKBOOK_PATH}")
    print(f"Country/economy dimension rows: {len(countries)}")
    print(f"Country-year fact rows: {len(fact_rows)}")
    for field, values in observations.items():
        print(f"{field} observations: {len(values)} ({sources[field]['dcid']})")


if __name__ == "__main__":
    main()
