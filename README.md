# UN Data Commons Test

This workspace explores and visualizes emissions data. It currently contains a global time-series chart and a country-level comparison of emissions and income.

## Interactive dashboard

The Streamlit dashboard presents the country-year workbook as an interactive emissions explorer. It includes filters for year, World Bank region, and income level; selectable measures; trend and top-country charts; an income-versus-emissions bubble plot; a sortable country table; and a filtered CSV download.

Install the project dependencies and start the dashboard from the project root:

```bash
python -m pip install -r requirements.txt
python -m streamlit run dashboard.py
```

The dashboard reads `data/emissions_powerbi_2000_2023.xlsx`. Generate or refresh that workbook first if it is missing:

```bash
python scripts/export_powerbi_workbook.py
```

### Deploy on Streamlit Community Cloud

Push this project to a GitHub repository, including `dashboard.py`, `requirements.txt`, and `data/emissions_powerbi_2000_2023.xlsx`. In [Streamlit Community Cloud](https://share.streamlit.io/), create an app from that repository, select the branch, and set the app file path to `dashboard.py`. The checked-in workbook lets the app start without downloading source data during deployment. To refresh it, run the export script locally and push the updated workbook.

Use the sidebar to choose a trend period, snapshot year, measure, regions, and income levels. The country highlight selection controls individual trend lines; clear it to see the aggregate for the selected filters. Downloaded CSV rows match the active geography filters and snapshot year.

## Country comparison (2023)

The country scatter plot compares GDP per capita with CO2 emissions per capita. Each point is a country/economy, the color indicates its World Bank region, and bubble size represents population. GDP per capita is shown on a logarithmic scale. The script also reports summary insights, including top emitters and the correlation between log GDP per capita and emissions per capita.

### Generate the chart and data

Requires Python and Matplotlib. Install Matplotlib if needed:

```bash
python -m pip install matplotlib
```

Run from the project root:

```bash
python scripts/create_country_emissions_scatter.py
```

The script retrieves data from the World Bank API and writes:

- `exports/country_co2_income_scatter_2023.png` — chart
- `data/country_co2_income_comparison_2023.csv` — joined country-level data used by the chart

The CSV includes year, ISO3 code, country, region, total emissions, population, GDP per capita, and calculated emissions per capita. Countries without complete, positive values for all three indicators are omitted. The number of records can change as the source data is revised.

## Power BI workbook (2000-2023)

To export a longitudinal, Power BI-ready workbook with emissions, population, and GDP indicators:

```bash
python scripts/export_powerbi_workbook.py
```

The script downloads observations from the World Bank API and creates `data/emissions_powerbi_2000_2023.xlsx`. The workbook contains:

- `FactCountryYear` — one row per country/economy-year with available emissions, population, and GDP-per-capita measures, plus calculated emissions per capita and emissions per GDP.
- `DimCountry` — country/economy names, ISO3 keys, World Bank regions, income levels, and lending types.
- `DimYear` — calendar year and decade attributes.
- `FieldGuide` — field definitions, units, indicator codes, sources, and calculation notes.
- `ModelGuide` — relationship setup and data interpretation notes.

In Power BI, load the workbook tables and create one-to-many, single-direction relationships from `DimCountry[CountryISO3]` to `FactCountryYear[CountryISO3]` and from `DimYear[Year]` to `FactCountryYear[Year]`. Blank cells mean the source observation is unavailable; they should not be replaced with zero. Each indicator has its own coverage, so calculated measures are blank when required inputs are missing. The workbook is refreshed by rerunning the script; it requires an internet connection and Python's `openpyxl` package.

### Data sources and interpretation

- **CO2 emissions:** World Bank World Development Indicators, indicator `EN.GHG.CO2.MT.CE.AR5`. The indicator is sourced from the EDGAR/JRC Community GHG Database and measures CO2 emissions in Mt CO2e, excluding land use, land-use change, and forestry (LULUCF).
- **GDP per capita:** World Bank indicator `NY.GDP.PCAP.CD` (current US$).
- **Population:** World Bank indicator `SP.POP.TOTL`.
- **Country names and regions:** World Bank country metadata.

The association shown is descriptive and does not establish that income causes emissions. GDP is in current US dollars, and country-level emissions per capita is calculated as total emissions divided by population.

## Global time series

`scripts/create_scatter_plot.py` generates `exports/world_co2_emissions_scatter_2000-2023.png`. Its annual values are currently embedded in the script rather than downloaded from a reproducible source. Treat this chart as a draft: its data and source should be verified before analysis or comparison with the country-level chart, which uses a different emissions measure and source.

## Project layout

- `scripts/` — chart-generation scripts
- `data/` — generated data snapshots
- `exports/` — generated chart images
- `notebooks/` — space for exploratory analysis
- `.vscode/` — editor configuration

To refresh the country comparison, rerun its script while connected to the internet. It uses the fixed comparison year defined near the top of the script.
