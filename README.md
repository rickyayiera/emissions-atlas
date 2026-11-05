# UN Data Commons Test

This workspace explores and visualizes emissions data. It currently contains a global time-series chart and a country-level comparison of emissions and income.

## Interactive dashboard

The Streamlit dashboard presents the country-year workbook as a presentation-ready emissions atlas. It includes switchable Field guide, Civic blue, and Carbon contrast themes; a vertically scrolling factual highlight carousel with per-card shuffle controls; region and income emissions-share doughnuts; year, region, and income filters; selectable measures; selectable trend charts with a data lens; top-country charts; an interactive country choropleth with hover details and click-linked country/region charts and tables; country and region glance/deep-dive popovers; a country distribution with mean and standard-deviation markers; a sortable country table; a filtered CSV download; an illustrative what-if lab; and a **Calculations** tab with live numerators, denominators, observation counts, formulas, and chart-method explanations.

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

The script discovers and assesses indicators through the UN Data Commons MCP service, downloads bounded 2000–2023 observations, and creates `data/emissions_powerbi_2000_2023.xlsx`. The workbook contains:

- `FactCountryYear` — one row per country/economy-year with available CO₂ emissions, population, total GDP, GDP per capita, emissions per capita, and emissions intensity.
- `DimCountry` — country/economy names, ISO3 keys, and World Bank regions, income levels, and lending types where available; missing classifications are marked `Unknown`.
- `DimYear` — calendar year and decade attributes.
- `FieldGuide` — field definitions, units, Data Commons indicators and source facets, and calculation notes.
- `ModelGuide` — relationship setup and data interpretation notes.

In Power BI, load the workbook tables and create one-to-many, single-direction relationships from `DimCountry[CountryISO3]` to `FactCountryYear[CountryISO3]` and from `DimYear[Year]` to `FactCountryYear[Year]`. Blank cells mean the source observation is unavailable; they should not be replaced with zero. Each indicator has its own coverage, so calculated measures are blank when required inputs are missing. The workbook is refreshed by rerunning the script; it requires an internet connection and Python's `openpyxl` package.

### Data sources and interpretation

- **CO₂ emissions:** UN Statistics Division SDG Data Portal, Data Commons indicator `undata/sdg/EN_ATM_CO2`. This is CO₂ from fuel combustion, not total greenhouse gas emissions and not CO₂-equivalent (CO₂e).
- **GDP:** UNIDO Statistics Data Portal, Data Commons indicator `undata/unido/NA_GDPCUD`, in current US dollars. GDP per capita is derived as total GDP divided by population.
- **Population:** UNICEF Data, Data Commons indicator `undata/unicef/DM_POP`.
- **Country classifications:** World Bank metadata; Data Commons country names supplement entities without a World Bank match.

The exporter requires an internet connection and calls `https://unsd-datacommons.gcp.un-icc.cloud/mcp`. It discovers each indicator, verifies a source facet covers 2000–2023, and fails if the requested coverage is not available. Emissions are converted from tonnes to Mt; country-level emissions per capita is total emissions divided by population, and intensity is kilograms of CO₂ divided by total GDP. The association shown is descriptive and does not establish that income causes emissions. GDP is in current US dollars and is not adjusted for inflation or purchasing power.

## Global time series

`scripts/create_scatter_plot.py` generates `exports/world_co2_emissions_scatter_2000-2023.png`. Its annual values are currently embedded in the script rather than downloaded from a reproducible source. Treat this chart as a draft: its data and source should be verified before analysis or comparison with the country-level chart, which uses a different emissions measure and source.

## Project layout

- `scripts/` — chart-generation scripts
- `data/` — generated data snapshots
- `exports/` — generated chart images
- `notebooks/` — space for exploratory analysis
- `.vscode/` — editor configuration

To refresh the country comparison, rerun its script while connected to the internet. It uses the fixed comparison year defined near the top of the script.
