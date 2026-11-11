from pathlib import Path
import random

import pandas as pd
import plotly.express as px
import streamlit as st


ROOT = Path(__file__).resolve().parent
WORKBOOK_PATH = ROOT / "data" / "emissions_powerbi_2000_2023.xlsx"
FACT_COLUMNS = [
    "Year",
    "CountryISO3",
    "EmissionsMtCO2",
    "Population",
    "GDPPerCapitaUSD",
    "EmissionsPerCapitaTonnesCO2",
    "EmissionsKgCO2PerGDPUSD",
]
FACT_COLUMN_RENAMES = {
    "EmissionsMtCO2": "EmissionsMtCO2e",
    "EmissionsPerCapitaTonnesCO2": "EmissionsPerCapitaTonnesCO2e",
    "EmissionsKgCO2PerGDPUSD": "EmissionsKgPerGDPUSD",
}
METRICS = {
    "Total CO₂ emissions": ("EmissionsMtCO2e", "Mt CO₂e"),
    "Emissions per person": ("EmissionsPerCapitaTonnesCO2e", "tonnes CO₂e/person"),
    "GDP per person": ("GDPPerCapitaUSD", "current US$/person"),
    "Emissions intensity": ("EmissionsKgPerGDPUSD", "kg CO₂e/current US$"),
}
THEMES = {
    "Field guide": {
        "background": "#f3f6f4",
        "panel": "#ffffff",
        "muted": "#657572",
        "text": "#172c2a",
        "accent": "#148b78",
        "grid": "#e3ebe8",
    },
    "Civic blue": {
        "background": "#f2f5fa",
        "panel": "#ffffff",
        "muted": "#637189",
        "text": "#1c2d48",
        "accent": "#356bd1",
        "grid": "#e2e8f1",
    },
    "Carbon contrast": {
        "background": "#101a1a",
        "panel": "#192525",
        "muted": "#a7b6b2",
        "text": "#edf4f1",
        "accent": "#6bd5ad",
        "grid": "#344744",
    },
}


st.set_page_config(
    page_title="Emissions data | UN Data Commons",
    page_icon="🌍",
    layout="wide",
    initial_sidebar_state="expanded",
)

@st.cache_data(show_spinner="Loading country-year data...")
def load_data(workbook_path, modified_time):
    del modified_time
    fact = pd.read_excel(workbook_path, sheet_name="FactCountryYear", usecols=FACT_COLUMNS)
    fact = fact.rename(columns=FACT_COLUMN_RENAMES)
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
    fig.update_xaxes(gridcolor=COLORS["grid"], zerolinecolor=COLORS["muted"])
    fig.update_yaxes(gridcolor=COLORS["grid"], zerolinecolor=COLORS["muted"])
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


def live_calculation_rows(frame):
    rows = []
    emissions = frame.dropna(subset=["EmissionsMtCO2e"])
    rows.append(
        {
            "Measure": "Total CO₂ emissions",
            "Calculation": "Sum of available country emissions",
            "Numerator": f"{emissions['EmissionsMtCO2e'].sum():,.3f} Mt CO₂e",
            "Denominator": "—",
            "Rows used": len(emissions),
            "Result": format_metric(aggregate_value(frame, "EmissionsMtCO2e"), "EmissionsMtCO2e"),
        }
    )

    population = frame.dropna(subset=["Population"])
    rows.append(
        {
            "Measure": "Population covered",
            "Calculation": "Sum of available country populations",
            "Numerator": f"{population['Population'].sum():,.0f} people",
            "Denominator": "—",
            "Rows used": len(population),
            "Result": format_metric(aggregate_value(frame, "Population"), "Population"),
        }
    )

    per_person = frame.dropna(subset=["EmissionsMtCO2e", "Population"])
    per_person = per_person[(per_person["EmissionsMtCO2e"] >= 0) & (per_person["Population"] > 0)]
    emissions_tonnes = per_person["EmissionsMtCO2e"].sum() * 1_000_000
    population_sum = per_person["Population"].sum()
    rows.append(
        {
            "Measure": "Emissions per person",
            "Calculation": "Sum(emissions × 1,000,000) ÷ sum(population)",
            "Numerator": f"{emissions_tonnes:,.3f} tonnes CO₂e",
            "Denominator": f"{population_sum:,.0f} people",
            "Rows used": len(per_person),
            "Result": format_metric(
                aggregate_value(frame, "EmissionsPerCapitaTonnesCO2e"),
                "EmissionsPerCapitaTonnesCO2e",
            ),
        }
    )

    gdp = frame.dropna(subset=["GDPPerCapitaUSD", "Population"])
    gdp = gdp[gdp["Population"] > 0]
    weighted_gdp = (gdp["GDPPerCapitaUSD"] * gdp["Population"]).sum()
    gdp_population = gdp["Population"].sum()
    rows.append(
        {
            "Measure": "GDP per person",
            "Calculation": "Population-weighted mean: sum(GDP/person × population) ÷ sum(population)",
            "Numerator": f"${weighted_gdp:,.0f}",
            "Denominator": f"{gdp_population:,.0f} people",
            "Rows used": len(gdp),
            "Result": format_metric(aggregate_value(frame, "GDPPerCapitaUSD"), "GDPPerCapitaUSD"),
        }
    )

    intensity = frame.dropna(
        subset=["EmissionsMtCO2e", "GDPPerCapitaUSD", "Population"]
    )
    intensity = intensity[
        (intensity["EmissionsMtCO2e"] >= 0)
        & (intensity["GDPPerCapitaUSD"] > 0)
        & (intensity["Population"] > 0)
    ]
    emissions_kg = intensity["EmissionsMtCO2e"].sum() * 1_000_000_000
    total_gdp = (intensity["GDPPerCapitaUSD"] * intensity["Population"]).sum()
    rows.append(
        {
            "Measure": "Emissions intensity",
            "Calculation": "Sum(emissions × 1,000,000,000) ÷ sum(GDP/person × population)",
            "Numerator": f"{emissions_kg:,.3f} kg CO₂e",
            "Denominator": f"${total_gdp:,.0f} total GDP",
            "Rows used": len(intensity),
            "Result": format_metric(
                aggregate_value(frame, "EmissionsKgPerGDPUSD"),
                "EmissionsKgPerGDPUSD",
            ),
        }
    )

    valid_per_person = frame["EmissionsPerCapitaTonnesCO2e"].dropna()
    rows.append(
        {
            "Measure": "Median emissions per person",
            "Calculation": "Unweighted median of valid country-level emissions/person values",
            "Numerator": "—",
            "Denominator": "—",
            "Rows used": len(valid_per_person),
            "Result": (
                f"{valid_per_person.median():,.2f}"
                if not valid_per_person.empty
                else "—"
            ),
        }
    )
    return pd.DataFrame(rows)


def factual_highlights(frame):
    candidates = [
        ("Total emissions", "EmissionsMtCO2e", "Mt CO₂e"),
        ("Emissions per person", "EmissionsPerCapitaTonnesCO2e", "tonnes CO₂e/person"),
        ("GDP per person", "GDPPerCapitaUSD", "current US$/person"),
        ("Population", "Population", "people"),
    ]
    highlights = []
    for label, column, unit in candidates:
        valid = frame.dropna(subset=[column])
        if valid.empty:
            continue
        row = valid.loc[valid[column].idxmax()]
        highlights.append(
            {
                "label": label,
                "country": row["Country"],
                "value": format_metric(row[column], column),
                "unit": unit,
            }
        )
    return highlights


def make_deviation_chart(frame, column, label, unit, selected_country=None):
    sample = frame.dropna(subset=[column])
    if column != "EmissionsMtCO2e":
        sample = sample[sample[column] > 0]
    if len(sample) < 2:
        return None, sample, None, None

    values = sample[column]
    mean = values.mean()
    standard_deviation = values.std()
    median = values.median()
    fig = px.histogram(
        sample,
        x=column,
        nbins=28,
        labels={column: f"{label} · {unit}"},
        color_discrete_sequence=[COLORS["accent"]],
        opacity=0.86,
    )
    if standard_deviation > 0:
        fig.add_vrect(
            x0=mean - standard_deviation,
            x1=mean + standard_deviation,
            fillcolor=COLORS["accent"],
            opacity=0.11,
            line_width=0,
            layer="below",
        )
        fig.add_vline(
            x=mean - standard_deviation,
            line_dash="dot",
            line_color=COLORS["muted"],
            annotation_text="−1 SD",
            annotation_position="top left",
        )
        fig.add_vline(
            x=mean + standard_deviation,
            line_dash="dot",
            line_color=COLORS["muted"],
            annotation_text="+1 SD",
            annotation_position="top right",
        )
    fig.add_vline(
        x=mean,
        line_color=COLORS["accent"],
        line_width=2,
        annotation_text="Mean",
        annotation_position="top",
    )
    fig.add_vline(
        x=median,
        line_color="#e69f45",
        line_dash="dash",
        annotation_text="Median",
        annotation_position="bottom",
    )
    if selected_country:
        selected = sample[sample["Country"] == selected_country]
        if not selected.empty:
            fig.add_vline(
                x=selected.iloc[0][column],
                line_color="#9658a5",
                line_dash="dash",
                annotation_text=selected_country,
                annotation_position="bottom right",
            )
    return fig, sample, mean, standard_deviation


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

theme_name = st.sidebar.selectbox("Presentation theme", list(THEMES), key="presentation_theme")
COLORS = THEMES[theme_name]
st.markdown(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&display=swap');
    .stApp {{ background: {COLORS['background']}; color: {COLORS['text']}; font-family: 'DM Sans', sans-serif; }}
    [data-testid="stSidebar"] {{ background: {COLORS['panel']}; border-right: 1px solid {COLORS['grid']}; }}
    .main .block-container {{ max-width: 1440px; padding-top: 1.5rem; padding-bottom: 3rem; }}
    h1, h2, h3 {{ color: {COLORS['text']} !important; }}
    [data-testid="stMetric"] {{
      background: {COLORS['panel']}; border: 1px solid {COLORS['grid']};
      padding: 14px 16px; border-radius: 8px; box-shadow: none;
    }}
    [data-testid="stMetricLabel"] {{ color: {COLORS['muted']} !important; }}
    [data-testid="stMetricValue"] {{ color: {COLORS['text']} !important; }}
    div[data-testid="stVerticalBlockBorderWrapper"] {{
      background: {COLORS['panel']}; border: 1px solid {COLORS['grid']};
      border-radius: 8px; box-shadow: none;
    }}
    div[data-testid="stVerticalBlock"] div[data-testid="stHorizontalBlock"] {{ gap: 1rem; }}
    button[data-baseweb="tab"] {{ font-weight: 600; }}
    button[data-baseweb="tab"][aria-selected="true"] {{ color: {COLORS['accent']}; }}
    .section-note {{ color: {COLORS['muted']}; font-size: .9rem; margin-top: -.35rem; }}
    .stCaption {{ color: {COLORS['muted']}; }}
    </style>
    """,
    unsafe_allow_html=True,
)

st.sidebar.markdown("## Explore the data")
st.sidebar.caption("Filters update the charts, indicators, table, and export.")

min_year, max_year = int(data["Year"].min()), int(data["Year"].max())
if "snapshot_year" not in st.session_state:
    st.session_state["snapshot_year"] = max_year
if "measure_label" not in st.session_state:
    st.session_state["measure_label"] = next(iter(METRICS))
year_range = st.sidebar.slider(
    "Trend period",
    min_value=min_year,
    max_value=max_year,
    value=(min_year, max_year),
)
snapshot_year = st.sidebar.select_slider(
    "Snapshot year",
    options=list(range(min_year, max_year + 1)),
    key="snapshot_year",
)
measure_label = st.sidebar.selectbox("Measure", list(METRICS), key="measure_label")
measure_column, measure_unit = METRICS[measure_label]


def shuffle_view():
    current_year = st.session_state.get("snapshot_year", max_year)
    year_options = [year for year in range(min_year, max_year + 1) if year != current_year]
    if year_options:
        st.session_state["snapshot_year"] = random.choice(year_options)

    measure_options = [measure for measure in METRICS if measure != st.session_state.get("measure_label")]
    if measure_options:
        st.session_state["measure_label"] = random.choice(measure_options)


def toggle_insights():
    st.session_state["insights_open"] = not st.session_state.get("insights_open", False)


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


def emissions_share_chart(frame, group_column):
    share = (
        frame.dropna(subset=["EmissionsMtCO2e"])
        .groupby(group_column, as_index=False)["EmissionsMtCO2e"]
        .sum()
    )
    share = share[share["EmissionsMtCO2e"] > 0]
    if share.empty:
        return None
    fig = px.pie(
        share,
        names=group_column,
        values="EmissionsMtCO2e",
        hole=0.58,
        color_discrete_sequence=px.colors.qualitative.Safe,
    )
    fig.update_traces(
        textposition="inside",
        textinfo="percent+label",
        hovertemplate="%{label}<br>%{percent}<extra></extra>",
        marker={"line": {"color": COLORS["panel"], "width": 2}},
    )
    return fig


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
    fig.update_layout(title=f"{year_range[0]}–{year_range[1]}", clickmode="event+select")
    return fig


title_column, shuffle_column, insights_column = st.columns([4, 1, 1])
with title_column:
    st.title("Emissions data")
    st.caption(
        "Country-level trends and comparisons · World Bank / EDGAR CO₂ emissions excluding land use, "
        "land-use change, and forestry (LULUCF) · GDP per capita in current US dollars."
    )
with shuffle_column:
    st.button(
        "Shuffle",
        key="shuffle_view",
        help="Choose a different snapshot year and measure.",
        on_click=shuffle_view,
        use_container_width=True,
    )
with insights_column:
    st.button(
        "Hide insights" if st.session_state.get("insights_open", False) else "Insights",
        key="toggle_insights",
        on_click=toggle_insights,
        use_container_width=True,
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

if st.session_state.get("insights_open", False):
    with st.container(border=True):
        st.subheader(f"Insights · {snapshot_year}")
        trend = aggregate_trend(base, measure_column)
        if len(trend) > 1:
            first = trend.iloc[0]
            last = trend.iloc[-1]
            difference = last["Value"] - first["Value"]
            if first["Value"] != 0:
                change = abs(difference / first["Value"] * 100)
                direction = "increased" if difference > 0 else "decreased" if difference < 0 else "was unchanged"
                trend_insight = (
                    f"{measure_label} {direction} by {change:,.1f}% from "
                    f"{int(first['Year'])} to {int(last['Year'])}."
                )
            else:
                trend_insight = (
                    f"{measure_label} changed by {difference:,.3f} {measure_unit} from "
                    f"{int(first['Year'])} to {int(last['Year'])}."
                )
            st.write(trend_insight)
        else:
            st.caption("Select a trend period with at least two years to see a change over time.")
        insights = factual_highlights(snapshot)
        if insights:
            st.dataframe(
                pd.DataFrame(insights)
                .rename(
                    columns={
                        "label": "Measure",
                        "country": "Country",
                        "value": "Value",
                        "unit": "Unit",
                    }
                )[["Measure", "Country", "Value", "Unit"]],
                hide_index=True,
                width="stretch",
            )
        else:
            st.info("No complete records are available for this snapshot.")

overview_tab, compare_tab, data_tab, experiment_tab, calculations_tab = st.tabs(
    ["Overview", "Compare", "Country data", "Experiment", "Calculations"]
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
    with st.expander("How are these headline statistics calculated?"):
        st.caption(
            f"These are calculated from the selected snapshot year ({snapshot_year}) and current region/income filters. "
            "Each measure uses only rows with the required source values; missing values are excluded, not treated as zero."
        )
        st.dataframe(
            live_calculation_rows(snapshot),
            hide_index=True,
            width="stretch",
        )

    trend_column, bar_column = st.columns([1.55, 1])
    with trend_column:
        with st.container(border=True):
            st.subheader(f"{measure_label} over time")
            trend_event = st.plotly_chart(
                chart_layout(make_trend_chart(base)),
                width="stretch",
                key="trend_chart",
                on_select="rerun",
                selection_mode="points",
            )
            trend_points = trend_event.get("selection", {}).get("points", [])
            selected_years = sorted(
                {
                    point.get("x")
                    for point in trend_points
                    if point.get("x") is not None
                }
            )
            with st.expander("Open the graph data lens", expanded=bool(selected_years)):
                if selected_years:
                    selected_trend = aggregate_trend(base, measure_column)
                    st.dataframe(
                        selected_trend[selected_trend["Year"].isin(selected_years)],
                        hide_index=True,
                        width="stretch",
                    )
                else:
                    st.caption("Select one or more points on the trend to inspect their values.")
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
            with st.expander("How the trend values are calculated"):
                st.markdown(
                    f"Each point is calculated for its year from the active region and income filters. "
                    f"For **{measure_label}**, the aggregate uses the same formula as the headline statistics. "
                    "Country spotlight plots individual recorded values; regional comparison recalculates the measure "
                    "within each region and year. The optional dashed series is an unweighted mean of the available "
                    "regional values for each year."
                )
    with bar_column:
        with st.container(border=True):
            st.subheader(f"Top countries · {snapshot_year}")
            st.caption(
                f"Ranked by each country's recorded {measure_label.lower()}; "
                "countries without a reported value are omitted."
            )
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
            with st.expander("How the ranking is calculated"):
                st.markdown(
                    f"Filter to **{snapshot_year}** and the selected regions/income levels, remove missing "
                    f"**{measure_column}** values, sort by that measure from largest to smallest, and display "
                    "the first 10 countries. Bar lengths are the recorded country-level values, not regional totals."
                )

    pie_columns = st.columns(2)
    for column, grouping, title in (
        (pie_columns[0], "Region", "Emissions share · region"),
        (pie_columns[1], "IncomeLevel", "Emissions share · income level"),
    ):
        with column:
            with st.container(border=True):
                st.subheader(title)
                st.caption("Share of reported emissions in this filtered snapshot.")
                pie_fig = emissions_share_chart(snapshot, grouping)
                if pie_fig is None:
                    st.info("No positive emissions values are available for this breakdown.")
                else:
                    st.plotly_chart(chart_layout(pie_fig, height=350), width="stretch")
                    with st.expander("Show slice calculations"):
                        pie_rows = (
                            snapshot.dropna(subset=["EmissionsMtCO2e"])
                            .groupby(grouping, as_index=False)["EmissionsMtCO2e"]
                            .sum()
                        )
                        pie_rows = pie_rows[pie_rows["EmissionsMtCO2e"] > 0].copy()
                        denominator = pie_rows["EmissionsMtCO2e"].sum()
                        pie_rows["Share of displayed total (%)"] = (
                            pie_rows["EmissionsMtCO2e"] / denominator * 100
                        )
                        st.caption(
                            "For each category: sum its non-missing country emissions. "
                            "Slice % = category sum ÷ sum of displayed positive category totals × 100. "
                            "Categories with a zero or negative total are excluded."
                        )
                        st.dataframe(
                            pie_rows.rename(
                                columns={
                                    grouping: "Category",
                                    "EmissionsMtCO2e": "Emissions · Mt CO₂e",
                                }
                            ),
                            hide_index=True,
                            width="stretch",
                        )

with compare_tab:
    with st.container(border=True):
        st.subheader(f"Explore the map · {snapshot_year}")
        st.caption(
            "Hover over a country for its name, region, and available measures. "
            "Click a country to link its country and regional deep dives below."
        )
        map_measure_label = st.selectbox(
            "Shade countries by",
            list(METRICS),
            key="map_measure",
        )
        map_column, map_unit = METRICS[map_measure_label]
        map_snapshot = snapshot.dropna(subset=[map_column, "CountryISO3"]).copy()
        map_snapshot = map_snapshot[map_snapshot["CountryISO3"].str.len() == 3]
        if map_column in (
            "GDPPerCapitaUSD",
            "Population",
            "EmissionsPerCapitaTonnesCO2e",
            "EmissionsKgPerGDPUSD",
        ):
            map_snapshot = map_snapshot[map_snapshot[map_column] > 0]
        if map_snapshot.empty:
            st.info("No country-level values are available to shade for this measure and snapshot.")
        else:
            map_fig = px.choropleth(
                map_snapshot,
                locations="CountryISO3",
                locationmode="ISO-3",
                color=map_column,
                hover_name="Country",
                custom_data=["CountryISO3", "Region", "IncomeLevel"],
                hover_data={
                    "EmissionsMtCO2e": ":,.1f",
                    "Population": ":,.0f",
                    "GDPPerCapitaUSD": "$,.0f",
                    "EmissionsPerCapitaTonnesCO2e": ":,.2f",
                    "EmissionsKgPerGDPUSD": ":,.3f",
                    "CountryISO3": True,
                    "Region": True,
                    "IncomeLevel": True,
                },
                color_continuous_scale=[
                    [0, COLORS["background"]],
                    [0.55, COLORS["accent"]],
                    [1, COLORS["accent"]],
                ],
                labels={map_column: map_unit},
            )
            map_fig.update_geos(
                projection_type="natural earth",
                showframe=False,
                showcountries=True,
                countrycolor=COLORS["panel"],
                showcoastlines=False,
                showland=True,
                landcolor=COLORS["background"],
                bgcolor=COLORS["panel"],
                fitbounds="locations",
            )
            map_fig.update_layout(clickmode="event+select")
            map_event = st.plotly_chart(
                chart_layout(map_fig, height=550),
                width="stretch",
                key="atlas_country_map",
                on_select="rerun",
                selection_mode="points",
            )
            with st.expander("How the map shades each country"):
                map_value_count = map_snapshot[map_column].notna().sum()
                st.markdown(
                    f"Each shaded country/economy is matched by its ISO3 code and colored using its "
                    f"**{map_measure_label}** observation for **{snapshot_year}** "
                    f"({map_value_count:,} mapped records after the current filters). "
                    "The color scale maps lower and higher observed values to the palette; it does not "
                    "calculate a regional average or fill missing observations. Positive-only measures "
                    "exclude zero and negative values."
                )
                st.dataframe(
                    map_snapshot[
                        ["Country", "CountryISO3", "Region", "IncomeLevel", map_column]
                    ].sort_values(map_column, ascending=False),
                    hide_index=True,
                    width="stretch",
                    height=240,
                )
            selected_map_points = map_event.get("selection", {}).get("points", [])
            if selected_map_points:
                selected_location = selected_map_points[-1].get("location")
                if selected_location is not None:
                    selected_map_rows = map_snapshot[
                        map_snapshot["CountryISO3"] == selected_location
                    ]
                    if not selected_map_rows.empty:
                        selected_map_row = selected_map_rows.iloc[0]
                        if st.session_state.get("map_selected_iso3") != selected_location:
                            st.session_state["country_lens"] = selected_map_row["Country"]
                            st.session_state["region_lens"] = selected_map_row["Region"]
                        st.session_state["map_selected_iso3"] = selected_location
                        st.session_state["map_selected_region"] = selected_map_row["Region"]

    country_names = sorted(snapshot["Country"].dropna().unique())
    region_names = sorted(snapshot["Region"].dropna().unique())
    map_selected_country = None
    map_selected_region = None
    if st.session_state.get("map_selected_iso3"):
        map_country_rows = snapshot[
            snapshot["CountryISO3"] == st.session_state["map_selected_iso3"]
        ]
        if not map_country_rows.empty:
            map_selected_country = map_country_rows.iloc[0]["Country"]
            map_selected_region = map_country_rows.iloc[0]["Region"]
    selected_country = st.selectbox(
        "Country lens",
        country_names,
        key="country_lens",
        index=(
            country_names.index(map_selected_country)
            if map_selected_country in country_names and "country_lens" not in st.session_state
            else None
        ),
        placeholder="Choose a country",
    ) if country_names else None
    if map_selected_country:
        st.info(
            f"Map selection: **{map_selected_country}** · "
            f"{map_selected_region}. Hover for quick values; open the map selection "
            "deep dive for linked country and region charts and tables."
        )
    lens_columns = st.columns(2)
    if selected_country:
        country_snapshot = snapshot[snapshot["Country"] == selected_country]
        country_history = base[base["Country"] == selected_country].sort_values("Year")
        with lens_columns[0]:
            with st.popover(f"📍 {selected_country} · at a glance", use_container_width=True):
                if not country_snapshot.empty:
                    country_row = country_snapshot.iloc[0]
                    glance_metrics = st.columns(2)
                    for column, label, metric_column in (
                        (glance_metrics[0], "Total emissions", "EmissionsMtCO2e"),
                        (glance_metrics[1], "Per person", "EmissionsPerCapitaTonnesCO2e"),
                        (glance_metrics[0], "GDP per person", "GDPPerCapitaUSD"),
                        (glance_metrics[1], "Population", "Population"),
                    ):
                        with column:
                            st.metric(
                                label,
                                format_metric(country_row[metric_column], metric_column),
                            )
                    st.caption(f"{country_row['Region']} · {country_row['IncomeLevel']} · {snapshot_year}")
                    with st.expander("Country indicator calculations"):
                        st.markdown(
                            "- Emissions, population, and GDP/person are the source-country values for this year.\n"
                            "- Emissions/person = emissions in Mt CO₂e × 1,000,000 ÷ population.\n"
                            "- Emissions intensity = emissions in Mt CO₂e × 1,000,000,000 ÷ "
                            "(GDP/person × population).\n"
                            "Derived indicators are blank when an input is missing or a required denominator is not positive."
                        )
        with lens_columns[1]:
            with st.popover(f"🔎 {selected_country} · deep dive", use_container_width=True):
                if country_history.empty:
                    st.info("No country trend is available for the selected period.")
                else:
                    deep_dive_fig = px.line(
                        country_history.dropna(subset=["EmissionsMtCO2e"]),
                        x="Year",
                        y="EmissionsMtCO2e",
                        markers=True,
                        labels={"EmissionsMtCO2e": "Emissions · Mt CO₂e"},
                        color_discrete_sequence=[COLORS["accent"]],
                    )
                    st.plotly_chart(chart_layout(deep_dive_fig, height=300), width="stretch")
                    st.dataframe(
                        country_history[
                            [
                                "Year",
                                "EmissionsMtCO2e",
                                "EmissionsPerCapitaTonnesCO2e",
                                "GDPPerCapitaUSD",
                                "Population",
                            ]
                        ],
                        hide_index=True,
                        width="stretch",
                    )

    selected_region = st.selectbox(
        "Regional lens",
        region_names,
        key="region_lens",
        index=(
            region_names.index(map_selected_region)
            if map_selected_region in region_names and "region_lens" not in st.session_state
            else None
        ),
        placeholder="Choose a region",
    ) if region_names else None
    with st.expander(
        "Map selection · linked country and region graph + table views",
        expanded=bool(map_selected_country),
    ):
        if selected_country or selected_region:
            detail_columns = st.columns(2)
            with detail_columns[0]:
                st.markdown(f"#### 📍 Country · {selected_country or '—'}")
                if selected_country:
                    country_history = base[base["Country"] == selected_country].sort_values("Year")
                    country_table = country_history
                    country_trend = country_history.dropna(subset=[map_column])
                    if country_trend.empty:
                        st.info(f"No {map_unit} trend is available for this country.")
                    else:
                        country_fig = px.line(
                            country_trend,
                            x="Year",
                            y=map_column,
                            markers=True,
                            labels={map_column: map_unit},
                            color_discrete_sequence=[COLORS["accent"]],
                        )
                        country_fig.update_layout(clickmode="event+select")
                        country_event = st.plotly_chart(
                            chart_layout(country_fig, height=300),
                            width="stretch",
                            key="map_country_trend",
                            on_select="rerun",
                            selection_mode="points",
                        )
                        selected_country_years = {
                            point.get("x")
                            for point in country_event.get("selection", {}).get("points", [])
                            if point.get("x") is not None
                        }
                        country_table = (
                            country_history[country_history["Year"].isin(selected_country_years)]
                            if selected_country_years
                            else country_history
                        )
                    st.dataframe(
                        country_table[
                            [
                                "Year",
                                "EmissionsMtCO2e",
                                "EmissionsPerCapitaTonnesCO2e",
                                "GDPPerCapitaUSD",
                                "Population",
                            ]
                        ],
                        hide_index=True,
                        width="stretch",
                    )
            with detail_columns[1]:
                st.markdown(f"#### 🗺️ Region · {selected_region or '—'}")
                if selected_region:
                    region_history = base[base["Region"] == selected_region]
                    region_trend_data = regional_trend(region_history, map_column)
                    if region_trend_data.empty:
                        st.info(f"No {map_unit} regional trend is available.")
                    else:
                        region_fig = px.line(
                            region_trend_data,
                            x="Year",
                            y="Value",
                            markers=True,
                            labels={"Value": map_unit},
                            color_discrete_sequence=[COLORS["accent"]],
                        )
                        region_fig.update_layout(clickmode="event+select")
                        region_event = st.plotly_chart(
                            chart_layout(region_fig, height=300),
                            width="stretch",
                            key="map_region_trend",
                            on_select="rerun",
                            selection_mode="points",
                        )
                        selected_region_years = {
                            point.get("x")
                            for point in region_event.get("selection", {}).get("points", [])
                            if point.get("x") is not None
                        }
                    region_rows = snapshot[snapshot["Region"] == selected_region]
                    if map_column in region_rows and not region_trend_data.empty:
                        if selected_region_years:
                            region_rows = region_history[
                                region_history["Year"].isin(selected_region_years)
                            ]
                        region_rows = region_rows.dropna(subset=[map_column]).nlargest(
                            12, map_column
                        )
                    st.dataframe(
                        region_rows[
                            [
                                "Year",
                                "Country",
                                "EmissionsMtCO2e",
                                "EmissionsPerCapitaTonnesCO2e",
                                "GDPPerCapitaUSD",
                                "Population",
                            ]
                        ],
                        hide_index=True,
                        width="stretch",
                    )
        else:
            st.caption("Select a country on the map to open its linked charts and tables.")

    if selected_region:
        region_snapshot = snapshot[snapshot["Region"] == selected_region]
        region_history = base[base["Region"] == selected_region]
        region_columns = st.columns(2)
        with region_columns[0]:
            with st.popover(f"🗺️ {selected_region} · at a glance", use_container_width=True):
                st.metric("Countries / economies", f"{region_snapshot['CountryISO3'].nunique():,}")
                st.metric(
                    "Total emissions · Mt CO₂e",
                    format_metric(aggregate_value(region_snapshot, "EmissionsMtCO2e"), "EmissionsMtCO2e"),
                )
                median = region_snapshot["EmissionsPerCapitaTonnesCO2e"].median()
                st.metric(
                    "Median per-capita emissions",
                    f"{median:,.2f}" if not pd.isna(median) else "—",
                    "tonnes CO₂e",
                )
                with st.expander("Regional statistic calculations"):
                    st.dataframe(
                        live_calculation_rows(region_snapshot),
                        hide_index=True,
                        width="stretch",
                    )
        with region_columns[1]:
            with st.popover(f"🧭 {selected_region} · deep dive", use_container_width=True):
                region_trend_data = regional_trend(region_history, measure_column)
                if region_trend_data.empty:
                    st.info("No regional trend is available for the selected period.")
                else:
                    region_fig = px.line(
                        region_trend_data,
                        x="Year",
                        y="Value",
                        markers=True,
                        labels={"Value": measure_unit, "Year": "Year"},
                        color_discrete_sequence=[COLORS["accent"]],
                    )
                    st.plotly_chart(chart_layout(region_fig, height=300), width="stretch")
                    st.dataframe(
                        region_snapshot.nlargest(5, "EmissionsMtCO2e")[
                            ["Country", "EmissionsMtCO2e", "EmissionsPerCapitaTonnesCO2e"]
                        ],
                        hide_index=True,
                        width="stretch",
                    )

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
        with st.expander("How to read and calculate the bubble plot"):
            st.markdown(
                "- One mark represents a country/economy in the selected year and filters.\n"
                "- **Horizontal position:** GDP per person in current US dollars, plotted on a logarithmic x-axis.\n"
                "- **Vertical position:** source emissions per person (Mt CO₂e × 1,000,000 ÷ population).\n"
                "- **Bubble-size input:** total population; Plotly scales marker sizes for readability.\n"
                "- Marks missing GDP/person, emissions/person, or population, and non-positive GDP/person/population, are omitted."
            )

    with st.container(border=True):
        st.subheader("Country distribution · standard-deviation scale")
        deviation_measure = st.selectbox(
            "Distribution measure",
            list(METRICS),
            index=list(METRICS).index("Emissions per person"),
            key="deviation_measure",
        )
        deviation_column, deviation_unit = METRICS[deviation_measure]
        deviation_fig, deviation_sample, mean, standard_deviation = make_deviation_chart(
            snapshot,
            deviation_column,
            deviation_measure,
            deviation_unit,
            selected_country,
        )
        if deviation_fig is None:
            st.info("At least two valid country values are needed to calculate standard deviation.")
        else:
            deviation_metrics = st.columns(3)
            deviation_metrics[0].metric(
                f"Mean · {deviation_unit}",
                format_metric(mean, deviation_column),
            )
            deviation_metrics[1].metric(
                f"Standard deviation · {deviation_unit}",
                format_metric(standard_deviation, deviation_column),
            )
            deviation_metrics[2].metric("Countries in distribution", f"{len(deviation_sample):,}")
            st.plotly_chart(chart_layout(deviation_fig, height=420), width="stretch")
            st.caption(
                "Shaded band spans mean ±1 sample standard deviation; dashed lines mark the mean, "
                "median, and selected country. Standard deviation is sensitive to outliers."
            )
            with st.expander("Show the distribution formulas and current values"):
                st.markdown(
                    "The chart first removes missing values and, except for total emissions, non-positive values. "
                    "The mean is `sum(x) ÷ n`. It uses the **sample** standard deviation: "
                    "`sqrt(sum((x − mean)²) ÷ (n − 1))`. The shaded band is `mean ± 1 SD`; "
                    "the median is the 50th percentile. The histogram places valid countries into 28 bins."
                )
                st.dataframe(
                    pd.DataFrame(
                        [
                            {"Calculation": "Valid country observations", "Value": f"{len(deviation_sample):,}"},
                            {"Calculation": "Sum of observations", "Value": f"{deviation_sample[deviation_column].sum():,.6f} {deviation_unit}"},
                            {"Calculation": "Mean", "Value": f"{mean:,.6f} {deviation_unit}"},
                            {"Calculation": "Sample standard deviation (ddof=1)", "Value": f"{standard_deviation:,.6f} {deviation_unit}"},
                            {"Calculation": "Mean − 1 SD", "Value": f"{mean - standard_deviation:,.6f} {deviation_unit}"},
                            {"Calculation": "Mean + 1 SD", "Value": f"{mean + standard_deviation:,.6f} {deviation_unit}"},
                            {"Calculation": "Median", "Value": f"{deviation_sample[deviation_column].median():,.6f} {deviation_unit}"},
                        ]
                    ),
                    hide_index=True,
                    width="stretch",
                )

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
        with st.expander("How each what-if value is calculated"):
            st.markdown(
                f"- Adjusted emissions = source emissions × `(1 + {emissions_change}/100)`.\n"
                f"- Adjusted population = source population × `(1 + {population_change}/100)`.\n"
                f"- Adjusted GDP/person = source GDP/person × `(1 + {gdp_change}/100)`.\n"
                "- Emissions/person and emissions intensity are then recalculated from those adjusted inputs using "
                "the same formulas as the source workbook.\n"
                "- The aggregate result applies the selected metric's sum or population-weighted calculation to "
                "the scenario snapshot. Scenario shift = `(what-if ÷ observed − 1) × 100%`."
            )

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

with calculations_tab:
    st.subheader("Calculation guide")
    st.markdown(
        f"All live examples below use **{snapshot_year}** and the active region and income filters. "
        "Formulas follow the dashboard's implementation and source workbook; unavailable observations remain blank."
    )
    st.markdown("#### Headline measures · live inputs and outputs")
    st.dataframe(
        live_calculation_rows(snapshot),
        hide_index=True,
        width="stretch",
    )
    st.markdown("#### Derived country indicators · workbook formulas")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Indicator": "Emissions per person",
                    "Calculation": "EmissionsMtCO₂e × 1,000,000 ÷ Population",
                    "Units": "tonnes CO₂e/person",
                    "Required inputs": "Emissions ≥ 0; population > 0",
                },
                {
                    "Indicator": "Emissions intensity",
                    "Calculation": "EmissionsMtCO₂e × 1,000,000,000 ÷ (GDP/person × Population)",
                    "Units": "kg CO₂e/current US$",
                    "Required inputs": "Emissions ≥ 0; GDP/person > 0; population > 0",
                },
                {
                    "Indicator": "Population-weighted GDP/person",
                    "Calculation": "sum(GDP/person × population) ÷ sum(population)",
                    "Units": "current US$/person",
                    "Required inputs": "GDP/person and population available; positive population",
                },
            ]
        ),
        hide_index=True,
        width="stretch",
    )
    st.markdown("#### How the visual summaries are constructed")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "Visual / statistic": "Country trend",
                    "Calculation": "Reapply the selected metric separately to each year; regional mode also groups by region.",
                },
                {
                    "Visual / statistic": "Regional average overlay",
                    "Calculation": "Unweighted arithmetic mean of available regional metric values for each year.",
                },
                {
                    "Visual / statistic": "Top-country bars",
                    "Calculation": "Sort non-missing country values for the snapshot from largest to smallest; show up to 10.",
                },
                {
                    "Visual / statistic": "Emissions-share doughnut",
                    "Calculation": "Sum country emissions within each region/income category; slice share = category sum ÷ displayed positive-category total × 100%.",
                },
                {
                    "Visual / statistic": "Country choropleth",
                    "Calculation": "Color each ISO3-matched country by its selected snapshot value; missing observations are not imputed.",
                },
                {
                    "Visual / statistic": "Country distribution",
                    "Calculation": "Histogram of country values; mean and sample SD (ddof=1); shaded band = mean ±1 SD; dashed line = median.",
                },
                {
                    "Visual / statistic": "Moving highlight cards",
                    "Calculation": "Show the filtered snapshot total or high-ranked country observations; shuffle changes the displayed fact only.",
                },
                {
                    "Visual / statistic": "Income/emissions bubbles",
                    "Calculation": "One country per mark; x = GDP/person (log scale), y = emissions/person, size input = population.",
                },
                {
                    "Visual / statistic": "What-if scenario",
                    "Calculation": "Uniform percentage changes scale selected source inputs, then derived measures and aggregates are recomputed.",
                },
            ]
        ),
        hide_index=True,
        width="stretch",
    )
    st.info(
        "Missing-data rule: blank source values are excluded from the relevant formula, not replaced with zero. "
        "The dashboard's emissions source excludes land use, land-use change, and forestry (LULUCF). "
        "Country-level comparisons are descriptive and do not establish causality."
    )

st.markdown("---")
st.caption(
    "Source: World Bank World Development Indicators; CO₂ indicator EN.GHG.CO2.MT.CE.AR5 "
    "(EDGAR/JRC, excluding LULUCF). GDP/person: NY.GDP.PCAP.CD. Population: SP.POP.TOTL. "
    "Blank observations indicate unavailable data, not zero. Refresh the source workbook by "
    "running `python scripts/export_powerbi_workbook.py`."
)
