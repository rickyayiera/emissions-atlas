from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


ROOT = Path(__file__).resolve().parent
WORKBOOK_PATH = ROOT / "data" / "emissions_powerbi_2000_2023.xlsx"
FACT_COLUMNS = [
    "Year",
    "CountryISO3",
    "EmissionsMtCO2e",
    "Population",
    "GDPPerCapitaUSD",
    "EmissionsPerCapitaTonnesCO2e",
    "EmissionsKgPerGDPUSD",
]
METRICS = {
    "Total CO₂ emissions": ("EmissionsMtCO2e", "Mt CO₂e"),
    "Emissions per person": ("EmissionsPerCapitaTonnesCO2e", "tonnes CO₂e/person"),
    "GDP per person": ("GDPPerCapitaUSD", "current US$/person"),
    "Emissions intensity": ("EmissionsKgPerGDPUSD", "kg CO₂e/current US$"),
}
COLORS = {
    "background": "#f3f6f4",
    "panel": "#ffffff",
    "muted": "#657572",
    "text": "#172c2a",
    "accent": "#148b78",
}


st.set_page_config(
    page_title="Emissions Atlas | UN Data Commons",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap');
    .stApp { background: #f3f6f4; color: #172c2a; font-family: 'DM Sans', sans-serif; }
    [data-testid="stSidebar"] { background: #ffffff; border-right: 1px solid #dfe8e4; }
    h1, h2, h3 { font-family: 'Space Grotesk', sans-serif !important; color: #172c2a !important; }
    [data-testid="stMetric"] {
      background: linear-gradient(145deg, #ffffff, #f8fbf9);
      border: 1px solid #dfe8e4; padding: 18px 20px; border-radius: 18px;
      box-shadow: 0 8px 24px rgba(27, 61, 52, .05);
    }
    [data-testid="stMetricLabel"] { color: #657572 !important; }
    [data-testid="stMetricValue"] { color: #172c2a !important; font-family: 'Space Grotesk', sans-serif; }
    div[data-testid="stVerticalBlockBorderWrapper"] {
      background: #ffffff; border: 1px solid #dfe8e4; border-radius: 18px;
      box-shadow: 0 8px 24px rgba(27, 61, 52, .045);
    }
    div[data-testid="stVerticalBlock"] div[data-testid="stHorizontalBlock"] { gap: 1rem; }
    button[data-baseweb="tab"] { font-weight: 600; }
    button[data-baseweb="tab"][aria-selected="true"] { color: #148b78; }
    .hero {
      padding: 2rem 2.2rem; margin: .4rem 0 1.2rem;
      border-radius: 24px; color: #f4fbf8;
      background: radial-gradient(circle at 85% 15%, rgba(73, 201, 168, .35), transparent 28%),
        linear-gradient(120deg, #123b39, #145d53 62%, #177c69);
      box-shadow: 0 16px 36px rgba(18, 59, 57, .15);
    }
    .hero h1 { color: #f4fbf8 !important; font-size: 2.65rem; margin: .25rem 0 .45rem; }
    .eyebrow { color: #a9eedb; text-transform: uppercase; letter-spacing: .16em;
      font-size: .73rem; font-weight: 700; }
    .hero-copy { color: #d7eee7; max-width: 760px; font-size: 1rem; }
    .section-note { color: #657572; font-size: .9rem; margin-top: -.35rem; }
    .stCaption { color: #657572; }
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner="Loading country-year data...")
def load_data(workbook_path, modified_time):
    del modified_time
    fact = pd.read_excel(workbook_path, sheet_name="FactCountryYear", usecols=FACT_COLUMNS)
    countries = pd.read_excel(
        workbook_path,
        sheet_name="DimCountry",
        usecols=["CountryISO3", "Country", "Region", "IncomeLevel"],
    )
    data = fact.merge(countries, on="CountryISO3", how="left", validate="many_to_one")
    data["Year"] = data["Year"].astype(int)
    data["Country"] = data["Country"].fillna(data["CountryISO3"])
    data["Region"] = data["Region"].fillna("Unknown")
    data["IncomeLevel"] = data["IncomeLevel"].fillna("Unknown")
    return data


def chart_layout(fig, height=390):
    fig.update_layout(
        height=height,
        paper_bgcolor=COLORS["panel"],
        plot_bgcolor=COLORS["panel"],
        font={"family": "DM Sans, sans-serif", "color": COLORS["text"]},
        margin={"l": 18, "r": 18, "t": 44, "b": 18},
        legend={"title": None, "orientation": "h", "y": 1.12, "x": 0},
        hoverlabel={"bgcolor": "#1d2b42", "font_color": "#ffffff"},
    )
    fig.update_xaxes(gridcolor="#e3ebe8", zerolinecolor="#c7d4cf")
    fig.update_yaxes(gridcolor="#e3ebe8", zerolinecolor="#c7d4cf")
    return fig


def aggregate_value(frame, column, year=None):
    values = frame if year is None else frame[frame["Year"] == year]
    valid = values.dropna(subset=[column])
    if valid.empty:
        return None

    if column == "EmissionsMtCO2e":
        return valid[column].sum()
    if column == "Population":
        return valid[column].sum()
    if column == "EmissionsPerCapitaTonnesCO2e":
        paired = valid.dropna(subset=["Population"])
        population = paired["Population"].sum()
        emissions = paired["EmissionsMtCO2e"].sum(min_count=1)
        return emissions * 1_000_000 / population if population > 0 else None
    if column == "GDPPerCapitaUSD":
        paired = valid.dropna(subset=["Population"])
        population = paired["Population"].sum()
        return (
            (paired["GDPPerCapitaUSD"] * paired["Population"]).sum() / population
            if population > 0
            else None
        )
    if column == "EmissionsKgPerGDPUSD":
        paired = valid.dropna(subset=["EmissionsMtCO2e", "GDPPerCapitaUSD", "Population"])
        total_gdp = (paired["GDPPerCapitaUSD"] * paired["Population"]).sum()
        total_emissions_kg = paired["EmissionsMtCO2e"].sum() * 1_000_000_000
        return total_emissions_kg / total_gdp if total_gdp > 0 else None
    return None


def format_metric(value, column):
    if value is None or pd.isna(value):
        return "—"
    if column == "EmissionsMtCO2e":
        return f"{value:,.1f}"
    if column == "Population":
        return f"{value:,.0f}"
    if column == "GDPPerCapitaUSD":
        return f"${value:,.0f}"
    if column == "EmissionsPerCapitaTonnesCO2e":
        return f"{value:,.2f}"
    return f"{value:,.3f}"


def aggregate_trend(frame, column):
    records = []
    for year, year_frame in frame.groupby("Year"):
        value = aggregate_value(year_frame, column)
        if value is not None and not pd.isna(value):
            records.append({"Year": year, "Value": value})
    return pd.DataFrame(records)


if not WORKBOOK_PATH.exists():
    st.error(
        "The Power BI workbook was not found. Generate it first with "
        "`python scripts/export_powerbi_workbook.py`."
    )
    st.stop()

try:
    data = load_data(str(WORKBOOK_PATH), WORKBOOK_PATH.stat().st_mtime)
except (OSError, ValueError, KeyError) as error:
    st.error(f"Could not load the dashboard workbook: {error}")
    st.stop()


st.sidebar.markdown("## Explore the data")
st.sidebar.caption("Filters update the charts, indicators, table, and export.")

min_year, max_year = int(data["Year"].min()), int(data["Year"].max())
year_range = st.sidebar.slider(
    "Trend period",
    min_value=min_year,
    max_value=max_year,
    value=(min_year, max_year),
)
snapshot_year = st.sidebar.select_slider(
    "Snapshot year",
    options=list(range(min_year, max_year + 1)),
    value=max_year,
)
measure_label = st.sidebar.selectbox("Measure", list(METRICS))
measure_column, measure_unit = METRICS[measure_label]

regions = sorted(data["Region"].dropna().unique())
selected_regions = st.sidebar.multiselect("World Bank regions", regions, default=regions)
income_levels = sorted(data["IncomeLevel"].dropna().unique())
selected_income = st.sidebar.multiselect(
    "Income levels",
    income_levels,
    default=income_levels,
)

st.sidebar.markdown("### Interaction controls")
trend_mode = st.sidebar.radio(
    "Trend mode",
    ["Aggregate", "Country spotlight", "Regional comparison"],
    index=0,
    horizontal=True,
)
show_region_average = st.sidebar.toggle("Overlay regional average", value=True)

base = data[
    data["Year"].between(year_range[0], year_range[1])
    & data["Region"].isin(selected_regions)
    & data["IncomeLevel"].isin(selected_income)
].copy()

countries = (
    base[["CountryISO3", "Country"]]
    .drop_duplicates()
    .sort_values("Country")
)
country_options = dict(zip(countries["Country"], countries["CountryISO3"]))
highlight_defaults = [
    country
    for country in ("China", "United States", "India")
    if country in country_options
]
highlight_names = st.sidebar.multiselect(
    "Highlight in trend",
    options=list(country_options),
    default=highlight_defaults,
    help="Optional country trend lines. Leave blank to show the aggregate for the selected filters.",
)
highlight_codes = [country_options[name] for name in highlight_names]
region_highlight = None
if trend_mode == "Regional comparison" and selected_regions:
    region_highlight = st.sidebar.selectbox(
        "Compare region",
        options=selected_regions,
        index=0,
    )


def regional_trend(frame, column):
    rows = []
    for (year, region), year_region in frame.groupby(["Year", "Region"]):
        value = aggregate_value(year_region, column)
        if value is not None and not pd.isna(value):
            rows.append({"Year": year, "Region": region, "Value": value})
    return pd.DataFrame(rows)


def make_trend_chart(frame):
    if trend_mode == "Regional comparison":
        trend_data = regional_trend(frame, measure_column)
        if trend_data.empty:
            return px.line(title="No regional trend available for the chosen filters")
        fig = px.line(
            trend_data,
            x="Year",
            y="Value",
            color="Region",
            markers=True,
            line_group="Region",
            labels={"Value": measure_unit, "Year": "Year"},
        )
        if region_highlight is not None:
            fig.update_traces(
                selector={"legendgroup": region_highlight},
                line={"width": 4},
                marker={"size": 9},
            )
        fig.update_traces(
            hovertemplate="%{fullData.name}<br>Year %{x}<br>%{y:,.3f}<extra></extra>"
        )
    elif trend_mode == "Country spotlight" and highlight_codes:
        trend_data = frame[frame["CountryISO3"].isin(highlight_codes)].dropna(
            subset=[measure_column]
        )
        fig = px.line(
            trend_data,
            x="Year",
            y=measure_column,
            color="Country",
            markers=True,
            custom_data=["CountryISO3"],
            labels={measure_column: measure_unit, "Year": "Year"},
        )
        fig.update_traces(
            hovertemplate="%{fullData.name}<br>Year %{x}<br>%{y:,.3f}<extra></extra>"
        )
    else:
        trend_data = aggregate_trend(frame, measure_column)
        fig = px.line(
            trend_data,
            x="Year",
            y="Value",
            markers=True,
            labels={"Value": measure_unit, "Year": "Year"},
        )
        fig.update_traces(
            line={"color": COLORS["accent"], "width": 3},
            hovertemplate="Year %{x}<br>%{y:,.3f}<extra></extra>",
        )
        if trend_mode == "Aggregate" and show_region_average:
            region_avg = regional_trend(frame, measure_column)
            if not region_avg.empty:
                region_avg = (
                    region_avg.groupby("Year", as_index=False)["Value"].mean()
                    .rename(columns={"Value": "Average"})
                )
                avg_fig = px.line(
                    region_avg,
                    x="Year",
                    y="Average",
                    markers=True,
                    labels={"Average": f"{measure_unit} · region avg", "Year": "Year"},
                )
                fig.add_trace(avg_fig.data[0])
                fig.update_traces(
                    selector={"name": "Average"},
                    line={"color": "#148b78", "width": 2, "dash": "dash"},
                    hovertemplate="Regional average<br>Year %{x}<br>%{y:,.3f}<extra></extra>",
                )
    fig.update_layout(title=f"{year_range[0]}–{year_range[1]}")
    return fig


st.markdown(
    """
    <div class="hero">
      <div class="eyebrow">UN Data Commons · emissions explorer</div>
      <h1>Emissions Atlas</h1>
      <div class="hero-copy">A visual field guide to emissions, population, and prosperity.
      Find the pattern, compare places, and test a few “what ifs” against the data.</div>
    </div>
    """,
    unsafe_allow_html=True,
)
st.caption(
    "World Bank / EDGAR CO₂ emissions excluding land use, land-use change, and forestry (LULUCF). "
    "GDP per capita is in current US dollars. Country-level associations are descriptive, not causal."
)

if base.empty:
    st.warning("No rows match the selected filters and trend period.")
    st.stop()

snapshot = data[
    data["Year"].eq(snapshot_year)
    & data["Region"].isin(selected_regions)
    & data["IncomeLevel"].isin(selected_income)
]
metric_value = aggregate_value(snapshot, measure_column)
population_value = aggregate_value(snapshot, "Population")
country_coverage = snapshot[measure_column].notna().sum()
per_capita_median = snapshot["EmissionsPerCapitaTonnesCO2e"].median()

overview_tab, compare_tab, data_tab, experiment_tab = st.tabs(
    ["✦ Overview", "◎ Compare", "▤ Country data", "⌁ Experiment lab"]
)

with overview_tab:
    metric_columns = st.columns(4)
    with metric_columns[0]:
        st.metric(
            f"{measure_label} · {snapshot_year} ({measure_unit})",
            format_metric(metric_value, measure_column),
        )
    with metric_columns[1]:
        st.metric("Population covered · people", format_metric(population_value, "Population"))
    with metric_columns[2]:
        st.metric("Countries with measure", f"{country_coverage:,}")
    with metric_columns[3]:
        st.metric(
            "Median emissions/person",
            f"{per_capita_median:,.2f}" if not pd.isna(per_capita_median) else "—",
            "tonnes CO₂e",
        )

    trend_column, bar_column = st.columns([1.55, 1])
    with trend_column:
        with st.container(border=True):
            st.subheader(f"{measure_label} over time")
            st.plotly_chart(chart_layout(make_trend_chart(base)), width="stretch")
            if trend_mode == "Country spotlight":
                note = (
                    "Country lines follow “Highlight in trend”; with no highlights, "
                    "the chart shows the aggregate."
                )
            elif trend_mode == "Regional comparison":
                note = "Each line is a region in the current filter set."
            else:
                note = "The aggregate line reflects selected filters; the dashed line is the average across active regions."
            st.markdown(f'<div class="section-note">{note}</div>', unsafe_allow_html=True)
    with bar_column:
        with st.container(border=True):
            st.subheader(f"Top countries · {snapshot_year}")
            top = snapshot.dropna(subset=[measure_column]).nlargest(10, measure_column).sort_values(
                measure_column
            )
            if top.empty:
                st.info("No ranked values for this snapshot.")
            else:
                bar_fig = px.bar(
                    top,
                    x=measure_column,
                    y="Country",
                    orientation="h",
                    color="Region",
                    hover_data={"CountryISO3": True, measure_column: ":,.3f"},
                    labels={measure_column: measure_unit, "Country": ""},
                )
                bar_fig.update_layout(showlegend=False)
                bar_fig.update_traces(hovertemplate="%{y}<br>%{x:,.3f}<extra></extra>")
                st.plotly_chart(chart_layout(bar_fig), width="stretch")

with compare_tab:
    with st.container(border=True):
        st.subheader(f"Income and emissions · {snapshot_year}")
        st.markdown(
            '<div class="section-note">Each bubble is a country; size represents population. '
            'Income uses a logarithmic scale.</div>',
            unsafe_allow_html=True,
        )
        scatter_data = snapshot.dropna(
            subset=["GDPPerCapitaUSD", "EmissionsPerCapitaTonnesCO2e", "Population"]
        )
        scatter_data = scatter_data[
            (scatter_data["GDPPerCapitaUSD"] > 0) & (scatter_data["Population"] > 0)
        ]
        if scatter_data.empty:
            st.info("No complete GDP, population, and emissions records match this snapshot and filter.")
        else:
            scatter_fig = px.scatter(
                scatter_data,
                x="GDPPerCapitaUSD",
                y="EmissionsPerCapitaTonnesCO2e",
                size="Population",
                color="Region",
                hover_name="Country",
                hover_data={
                    "CountryISO3": True,
                    "GDPPerCapitaUSD": ":$,.0f",
                    "EmissionsPerCapitaTonnesCO2e": ":,.2f",
                    "EmissionsMtCO2e": ":,.1f",
                    "Population": ":,.0f",
                },
                size_max=42,
                labels={
                    "GDPPerCapitaUSD": "GDP per capita · current US$ (log scale)",
                    "EmissionsPerCapitaTonnesCO2e": "Emissions per person · tonnes CO₂e",
                    "Region": "World Bank region",
                },
                log_x=True,
                opacity=0.76,
            )
            scatter_fig.update_traces(
                marker={"line": {"width": 0.6, "color": "#ffffff"}},
                hovertemplate=(
                    "%{hovertext}<br>GDP/person: $%{x:,.0f}<br>"
                    "Emissions/person: %{y:,.2f} t CO₂e<extra></extra>"
                ),
            )
            st.plotly_chart(chart_layout(scatter_fig, height=560), width="stretch")

with data_tab:
    with st.container(border=True):
        st.subheader(f"Country-year snapshot · {snapshot_year}")
        st.caption("Rows follow the selected regions and income levels; blanks mean unavailable source data.")
        display_columns = [
            "Country",
            "CountryISO3",
            "Region",
            "IncomeLevel",
            "Year",
            "EmissionsMtCO2e",
            "Population",
            "GDPPerCapitaUSD",
            "EmissionsPerCapitaTonnesCO2e",
            "EmissionsKgPerGDPUSD",
        ]
        table = snapshot.sort_values(measure_column, ascending=False, na_position="last")
        st.dataframe(
            table[display_columns],
            hide_index=True,
            width="stretch",
            height=440,
            column_config={
                "EmissionsMtCO2e": st.column_config.NumberColumn("Emissions · Mt CO₂e", format="%.1f"),
                "Population": st.column_config.NumberColumn("Population", format="%d"),
                "GDPPerCapitaUSD": st.column_config.NumberColumn("GDP/person · US$", format="$%.0f"),
                "EmissionsPerCapitaTonnesCO2e": st.column_config.NumberColumn(
                    "Emissions/person · t CO₂e", format="%.2f"
                ),
                "EmissionsKgPerGDPUSD": st.column_config.NumberColumn(
                    "Intensity · kg CO₂e/US$", format="%.3f"
                ),
            },
        )
        st.download_button(
            "Download filtered country data (CSV)",
            data=snapshot[display_columns].to_csv(index=False).encode("utf-8"),
            file_name=f"emissions_country_data_{snapshot_year}.csv",
            mime="text/csv",
        )

with experiment_tab:
    with st.container(border=True):
        st.subheader("Build a simple what-if")
        st.markdown(
            '<div class="section-note">Move the sliders to see how proportional changes flow through '
            'the selected measure for the filtered countries.</div>',
            unsafe_allow_html=True,
        )
        slider_columns = st.columns(3)
        with slider_columns[0]:
            emissions_change = st.slider("Emissions change", -50, 100, 0, format="%d%%")
        with slider_columns[1]:
            population_change = st.slider("Population change", -50, 100, 0, format="%d%%")
        with slider_columns[2]:
            gdp_change = st.slider("GDP per person change", -50, 100, 0, format="%d%%")
        experiment_label = st.selectbox("Explore scenario measure", list(METRICS), key="experiment_metric")
        experiment_column, experiment_unit = METRICS[experiment_label]

        scenario = base.copy()
        scenario["EmissionsMtCO2e"] *= 1 + emissions_change / 100
        scenario["Population"] *= 1 + population_change / 100
        scenario["GDPPerCapitaUSD"] *= 1 + gdp_change / 100
        scenario["EmissionsPerCapitaTonnesCO2e"] = (
            scenario["EmissionsMtCO2e"] * 1_000_000 / scenario["Population"]
        ).where(scenario["Population"] > 0)
        scenario["EmissionsKgPerGDPUSD"] = (
            scenario["EmissionsMtCO2e"] * 1_000_000_000
            / (scenario["GDPPerCapitaUSD"] * scenario["Population"])
        ).where((scenario["GDPPerCapitaUSD"] > 0) & (scenario["Population"] > 0))

        scenario_snapshot = scenario[scenario["Year"] == snapshot_year]
        observed_value = aggregate_value(snapshot, experiment_column)
        scenario_value = aggregate_value(scenario_snapshot, experiment_column)
        scenario_metrics = st.columns(3)
        with scenario_metrics[0]:
            st.metric(
                f"Observed · {experiment_unit}",
                format_metric(observed_value, experiment_column),
            )
        with scenario_metrics[1]:
            st.metric(
                f"What-if · {experiment_unit}",
                format_metric(scenario_value, experiment_column),
            )
        with scenario_metrics[2]:
            if observed_value and scenario_value is not None:
                change_percent = (scenario_value / observed_value - 1) * 100
                st.metric("Scenario shift", f"{change_percent:+.1f}%")
            else:
                st.metric("Scenario shift", "—")

        observed_trend = aggregate_trend(base, experiment_column).rename(
            columns={"Value": "Observed"}
        )
        scenario_trend = aggregate_trend(scenario, experiment_column).rename(
            columns={"Value": "What-if"}
        )
        comparison = observed_trend.merge(scenario_trend, on="Year", how="outer")
        if comparison.empty:
            st.info("No trend values are available for this scenario.")
        else:
            scenario_fig = px.line(
                comparison,
                x="Year",
                y=["Observed", "What-if"],
                markers=True,
                labels={"value": experiment_unit, "variable": "Series", "Year": "Year"},
                color_discrete_map={"Observed": "#8a9995", "What-if": COLORS["accent"]},
            )
            scenario_fig.update_traces(hovertemplate="%{fullData.name}<br>Year %{x}<br>%{y:,.3f}<extra></extra>")
            st.plotly_chart(chart_layout(scenario_fig), width="stretch")
        st.caption(
            "Illustrative sensitivity test only—not a forecast or policy estimate. "
            "The sliders apply uniform percentage changes to the selected countries and years."
        )

st.markdown("---")
st.caption(
    "Source: World Bank World Development Indicators; CO₂ indicator EN.GHG.CO2.MT.CE.AR5 "
    "(EDGAR/JRC, excluding LULUCF). GDP/person: NY.GDP.PCAP.CD. Population: SP.POP.TOTL. "
    "Blank observations indicate unavailable data, not zero. Refresh the source workbook by "
    "running `python scripts/export_powerbi_workbook.py`."
)
