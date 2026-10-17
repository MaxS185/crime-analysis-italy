"""Crime Analysis Dashboard - redesigned layout (dark glass cards, pastel palette).

Cities = the 108 provincial capitals (municipality level of the ISTAT data).
The map uses the macro-area rows already aggregated in the data (no re-summing of cities).
"""

import base64
import json
import os
from pathlib import Path

import altair as alt
import pandas as pd
import snowflake.connector
import streamlit as st

from queries import QUERIES

st.set_page_config(page_title="Crime Analysis Italy", layout="wide")

ASSETS_DIR = Path(__file__).parent / "assets"
SNAPSHOT_DIR = Path(__file__).parent / "snapshot"
MIME_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}

# English labels for the ISTAT macro areas (the database stores them in Italian).
MACRO_AREA_EN = {
    "ITC": "North-West",
    "ITD": "North-East",
    "ITE": "Centre",
    "ITF": "South",
    "ITG": "Islands",
}

# Pastel palette: lavender, soft yellow, mint, sky blue, coral.
FLAG_GREEN, FLAG_WHITE, FLAG_RED = "#2FBF71", "#F4F5F7", "#E5484D"
LAVENDER, YELLOW, MINT, SKY, CORAL = "#B8A9FF", "#FFE08A", "#8FE3C0", "#8EC9FF", "#FF9E9E"
CITY_COLORS = [LAVENDER, YELLOW, MINT, SKY, CORAL]
MACRO_COLORS = {"ITC": LAVENDER, "ITD": SKY, "ITE": YELLOW, "ITF": CORAL, "ITG": MINT}
TEXT_COLOR = "#E8EAF2"
MUTED_COLOR = "#9AA0B8"
GRID_COLOR = "rgba(255,255,255,0.08)"
FONT = "Plus Jakarta Sans"

# Map layout: where each macro area is anchored on the land (lon, lat) and where its
# circle sits (lon, lat), placed in the sea or beside Italy so circles never overlap.
MAP_ANCHOR = {
    "ITC": (8.4, 45.1),
    "ITD": (11.6, 45.6),
    "ITE": (12.3, 42.9),
    "ITF": (15.6, 40.7),
    "ITG": (14.2, 37.6),  # Sicily; Sardinia is added in MAP_EXTRA_ANCHOR
}
# Macro areas made of separate pieces get one leader line per piece.
MAP_EXTRA_ANCHOR = {"ITG": [(9.0, 40.0)]}  # Sardinia
MAP_CIRCLE = {
    "ITC": (3.2, 44.6),
    "ITD": (17.0, 46.9),
    "ITE": (18.4, 43.0),
    "ITF": (19.8, 39.2),
    "ITG": (7.8, 36.6),
}
CIRCLE_MAX_PX2 = 21000  # circle area (px^2) of the macro area with the most crimes
CIRCLE_MIN_PX2 = 10500  # floor so the text always fits inside the smallest circle

TOP_CRIME_TYPES = 10


# ---------------------------------------------------------------------------
# Theme (one CSS block: it depends on Streamlit's internal markup)
# ---------------------------------------------------------------------------
@st.cache_data
def theme_css() -> str:
    """Background image under a dark veil, glass cards, pills, fonts."""
    background = ""
    files = sorted(ASSETS_DIR.glob("background.*"))
    if files:
        image = files[0]
        mime = MIME_TYPES.get(image.suffix.lower(), "image/png")
        encoded = base64.b64encode(image.read_bytes()).decode()
        background = f"""
        .stApp {{
            background-image:
                linear-gradient(rgba(8, 10, 20, 0.82), rgba(8, 10, 20, 0.82)),
                url("data:{mime};base64,{encoded}");
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
        }}"""
    return f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
    {background}
    .stApp, .stApp p, .stApp label, .stApp h1, .stApp h2, .stApp h3, .stApp h4,
    .stApp span, .stApp button, .stApp div[data-testid="stCaptionContainer"] {{
        font-family: '{FONT}', sans-serif;
    }}
    header[data-testid="stHeader"] {{ background: transparent; }}
    [data-testid="stMainBlockContainer"], .block-container {{
        max-width: 1800px;
        padding-top: 2.2rem;
        padding-bottom: 3rem;
    }}

    /* Glass cards: every container whose key starts with "card_" or "kpi_" */
    [class*="st-key-card_"], [class*="st-key-kpi_"] {{
        background: rgba(24, 27, 44, 0.62);
        border: 1px solid rgba(255, 255, 255, 0.09);
        border-radius: 22px;
        padding: 1.1rem 1.25rem 1rem 1.25rem;
        backdrop-filter: blur(14px);
        -webkit-backdrop-filter: blur(14px);
        box-shadow: 0 8px 30px rgba(0, 0, 0, 0.28);
    }}
    /* Accent line on top of the three filter cards */
    .st-key-card_macro  {{ border-top: 3px solid {FLAG_GREEN}; }}
    .st-key-card_crime  {{ border-top: 3px solid {FLAG_WHITE}; }}
    .st-key-card_years  {{ border-top: 3px solid {FLAG_RED}; }}

    .card-title {{
        font-size: 1.05rem; font-weight: 700; color: {TEXT_COLOR};
        margin: 0 0 0.6rem 0; letter-spacing: 0.01em;
    }}
    .card-title small {{ font-weight: 500; color: {MUTED_COLOR}; margin-left: 0.4rem; }}
    .page-title {{ font-size: 2rem; font-weight: 800; color: {TEXT_COLOR}; margin: 0; }}
    .page-sub {{ color: {MUTED_COLOR}; margin: 0.15rem 0 1.1rem 0; font-size: 0.95rem; }}

    /* KPI numbers */
    .kpi-label {{ color: {MUTED_COLOR}; font-size: 1.05rem; font-weight: 600; }}
    .kpi-value {{ color: {TEXT_COLOR}; font-size: 2.7rem; font-weight: 800; line-height: 1.15; }}
    .kpi-chip {{
        display: inline-block; margin-top: 0.3rem; padding: 0.15rem 0.75rem;
        border-radius: 999px; font-size: 0.92rem; font-weight: 700;
    }}
    .chip-up   {{ background: rgba(255,158,158,0.18); color: {CORAL}; }}
    .chip-down {{ background: rgba(143,227,192,0.18); color: {MINT}; }}
    .chip-flat {{ background: rgba(255,255,255,0.08); color: {MUTED_COLOR}; }}

    /* Centred content (horizontally and vertically) in filter and KPI cards, same height per row */
    .st-key-card_macro, .st-key-card_crime, .st-key-card_years, [class*="st-key-kpi_"] {{
        display: flex; flex-direction: column;
        justify-content: center; align-items: center;
        text-align: center;
    }}
    .st-key-card_macro, .st-key-card_crime, .st-key-card_years {{ min-height: 0; padding-top: 0.7rem; padding-bottom: 0.7rem; }}
    [class*="st-key-kpi_"] {{ min-height: 150px; }}
    .st-key-card_macro [data-testid="stButtonGroup"], .st-key-card_crime [data-testid="stButtonGroup"],
    .st-key-card_years [data-testid="stButtonGroup"] {{ justify-content: center; width: 100%; }}
    /* Pills grow to fill the card width, slightly larger text */
    .st-key-card_macro [data-testid="stButtonGroup"] button, .st-key-card_crime [data-testid="stButtonGroup"] button,
    .st-key-card_years [data-testid="stButtonGroup"] button {{
        flex: 1 1 auto; justify-content: center; min-width: max-content;
        font-size: 1rem !important; padding: 0.3rem 1rem !important;
    }}
    .st-key-card_macro [data-testid="stButtonGroup"], .st-key-card_crime [data-testid="stButtonGroup"],
    .st-key-card_years [data-testid="stButtonGroup"] {{ flex-wrap: wrap; }}
    [data-testid="stButtonGroup"] button p {{
        white-space: nowrap; overflow: visible !important; text-overflow: clip !important;
    }}
    .st-key-card_macro .card-title, .st-key-card_crime .card-title, .st-key-card_years .card-title {{ margin-bottom: 0.4rem; }}
    .st-key-card_macro [data-testid="stMarkdownContainer"], .st-key-card_crime [data-testid="stMarkdownContainer"],
    .st-key-card_years [data-testid="stMarkdownContainer"], [class*="st-key-kpi_"] [data-testid="stMarkdownContainer"] {{
        text-align: center;
    }}

    /* Pills: neutral when off; when on, outlined and tinted in the card's flag colour,
       with white text. Several selectors because Streamlit's markup changes by version. */
    [data-testid="stButtonGroup"] button {{
        border-radius: 999px !important;
        font-weight: 600;
        background: rgba(255,255,255,0.05) !important;
        border: 1px solid rgba(255,255,255,0.14) !important;
        color: {MUTED_COLOR} !important;
    }}
    .st-key-card_macro :is(button[data-testid="stBaseButton-pillsActive"], button[kind="pillsActive"], button[aria-checked="true"], button[aria-pressed="true"]) {{
        background: rgba(47,191,113,0.30) !important; border: 1.5px solid {FLAG_GREEN} !important; color: #ffffff !important;
    }}
    .st-key-card_crime :is(button[data-testid="stBaseButton-pillsActive"], button[kind="pillsActive"], button[aria-checked="true"], button[aria-pressed="true"]) {{
        background: rgba(244,245,247,0.24) !important; border: 1.5px solid {FLAG_WHITE} !important; color: #ffffff !important;
    }}
    .st-key-card_years :is(button[data-testid="stBaseButton-pillsActive"], button[kind="pillsActive"], button[aria-checked="true"], button[aria-pressed="true"]) {{
        background: rgba(229,72,77,0.30) !important; border: 1.5px solid {FLAG_RED} !important; color: #ffffff !important;
    }}
    [data-testid="stButtonGroup"] button p, [data-testid="stButtonGroup"] button span {{ color: inherit !important; }}
    /* Equal heights: inside every row, cards stretch so the blocks line up at top and bottom */
    [class*="st-key-row_"] > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"] {{ align-items: stretch; }}
    [class*="st-key-row_"] > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"]
        > [data-testid="stColumn"] > [data-testid="stVerticalBlock"] {{ height: 100%; }}
    [class*="st-key-row_"] > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"]
        > [data-testid="stColumn"] > [data-testid="stVerticalBlock"] > [data-testid="stLayoutWrapper"] {{
        flex: 1 1 0; display: flex; flex-direction: column;
    }}
    [class*="st-key-row_"] > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"]
        > [data-testid="stColumn"] > [data-testid="stVerticalBlock"] > [data-testid="stLayoutWrapper"]
        > [class*="st-key-card_"],
    [class*="st-key-row_"] > [data-testid="stLayoutWrapper"] > [data-testid="stHorizontalBlock"]
        > [data-testid="stColumn"] > [data-testid="stVerticalBlock"] > [data-testid="stLayoutWrapper"]
        > [class*="st-key-kpi_"] {{ flex: 1 1 auto; }}

    .st-key-card_map [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:last-child [data-testid="stVerticalBlock"] {{ align-items: flex-end; }}
    .st-key-card_map [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:last-child [data-testid="stButtonGroup"] {{ justify-content: flex-end; }}
    .st-key-card_types, .st-key-card_severity {{ gap: 0.1rem; }}
    /* City popover button: same look as the white Crime type pills, only wider */
    .st-key-city_pop button, .st-key-city_pop_on button {{
        border-radius: 999px !important; width: 100%; font-weight: 600; font-size: 1rem !important;
        padding: 0 1rem !important; min-height: 0 !important; height: 32px !important; line-height: 1.5;
        background: rgba(244,245,247,0.24) !important; border: 1.5px solid {FLAG_WHITE} !important;
        color: #ffffff !important;
    }}
    .st-key-city_pop button p, .st-key-city_pop_on button p {{ color: inherit !important; white-space: nowrap; }}
    .st-key-city_pop [data-testid="stIconMaterial"], .st-key-city_pop_on [data-testid="stIconMaterial"] {{ display: none; }}
    .st-key-city_pop button, .st-key-city_pop_on button {{ position: relative; }}
    .st-key-city_pop button::after, .st-key-city_pop_on button::after {{
        content: "\\25BE"; position: absolute; right: 14px; top: 50%; transform: translateY(-50%); font-size: 0.9em;
    }}
    /* Keep Streamlit's icon font: the page font must not apply to icon glyphs */
    [data-testid="stIconMaterial"] {{ font-family: "Material Symbols Rounded" !important; }}
    [data-testid="stButtonGroup"] button:disabled {{ opacity: 0.75; cursor: not-allowed; }}
    /* No toolbar (view data, download, fullscreen) on charts */
    [data-testid="stElementContainer"]:has([data-testid="stVegaLiteChart"]) [data-testid="stElementToolbar"] {{
        display: none !important;
    }}
    /* Map / table switch */
    .st-key-card_map :is(button[data-testid="stBaseButton-segmented_controlActive"], button[kind="segmented_controlActive"], button[aria-checked="true"], button[aria-pressed="true"]) {{
        background: {FLAG_WHITE} !important; border-color: {FLAG_WHITE} !important; color: #1a1c2c !important;
    }}
    .st-key-card_map :is(button[data-testid="stBaseButton-segmented_controlActive"], button[kind="segmented_controlActive"], button[aria-checked="true"], button[aria-pressed="true"]) p {{
        color: #1a1c2c !important;
    }}
    </style>
    """


@st.cache_data
def load_macro_geojson() -> dict:
    """Macro-area boundaries (ISTAT, CC BY 4.0), merged from the regional limits."""
    return json.loads((ASSETS_DIR / "macro_areas.geojson").read_text(encoding="utf-8"))


st.markdown(theme_css(), unsafe_allow_html=True)


@st.cache_resource
def get_connection():
    """Open one Snowflake connection, with credentials read from Streamlit secrets."""
    return snowflake.connector.connect(**st.secrets["snowflake"])


def use_snapshot() -> bool:
    """True when the app reads the exported result files instead of querying Snowflake.

    That is the case when no Snowflake credentials are configured (the public
    deployment), or when the CRIME_APP_DATA environment variable is set to "snapshot".
    """
    if os.environ.get("CRIME_APP_DATA") == "snapshot":
        return True
    try:
        return "snowflake" not in st.secrets
    except Exception:  # no secrets configured at all
        return True


@st.cache_data(ttl=3600)
def run_query(name: str) -> pd.DataFrame:
    """Return the result of a named query (see queries.py), lowercase column names.

    With Snowflake credentials configured the query runs live against the warehouse.
    Otherwise the result is read from the CSV exported by
    scripts/04_export_app_snapshot.py, which holds the output of the same query.
    """
    if use_snapshot():
        df = pd.read_csv(
            SNAPSHOT_DIR / f"{name}.csv", dtype={"area_code": str, "macro_area_code": str}
        )
    else:
        cursor = get_connection().cursor()
        try:
            cursor.execute(QUERIES[name])
            df = cursor.fetch_pandas_all()
        finally:
            cursor.close()
    df.columns = [c.lower() for c in df.columns]
    return df


# ---------------------------------------------------------------------------
# Chart helpers
# ---------------------------------------------------------------------------
def style_chart(chart: alt.TopLevelMixin) -> alt.TopLevelMixin:
    """Transparent background, light text, soft grid: matches the dark cards."""
    return (
        chart.configure(background="rgba(0,0,0,0)", font=FONT)
        .configure_view(stroke=None)
        .configure_axis(
            labelColor=MUTED_COLOR,
            titleColor=MUTED_COLOR,
            gridColor=GRID_COLOR,
            domainColor=GRID_COLOR,
            tickColor=GRID_COLOR,
            labelFontSize=11,
            titleFontSize=11,
            titleFontWeight=600,
        )
        .configure_legend(labelColor=TEXT_COLOR, labelFontSize=12, symbolType="circle", symbolSize=110)
    )


def show(chart: alt.TopLevelMixin) -> None:
    st.altair_chart(style_chart(chart), width="stretch", theme=None)


def card_title(icon: str, title: str, note: str = "") -> None:
    small = f"<small>{note}</small>" if note else ""
    st.markdown(f'<div class="card-title">{icon} {title}{small}</div>', unsafe_allow_html=True)


def top5_chart(per_area_year, top, value_col, y_title, number_format, height=250, y_pad=None):
    """Smooth line chart over the years for the cities in `top` (already ranked)."""
    order = top["area_name"].tolist()
    trend = per_area_year[per_area_year["area_code"].isin(top["area_code"])]
    if y_pad is None:
        y_scale = alt.Scale(zero=True)
    else:  # start the axis just below the lowest value shown
        y_min = max(0, int((trend[value_col].min() - y_pad) // 1000 * 1000))
        y_scale = alt.Scale(zero=False, domainMin=y_min, nice=True)
    chart = (
        alt.Chart(trend)
        .mark_line(interpolate="monotone", strokeWidth=3, point=alt.OverlayMarkDef(size=60, filled=True))
        .encode(
            x=alt.X("year:O", title=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y(f"{value_col}:Q", title=y_title, scale=y_scale, axis=alt.Axis(format=",.0f")),
            color=alt.Color(
                "area_name:N",
                sort=order,
                scale=alt.Scale(domain=order, range=CITY_COLORS[: len(order)]),
                legend=alt.Legend(orient="top", direction="horizontal", title=None, columns=5),
            ),
            tooltip=[
                alt.Tooltip("area_name:N", title="City"),
                alt.Tooltip("year:O", title="Year"),
                alt.Tooltip(f"{value_col}:Q", title=y_title, format=number_format),
            ],
        )
        .properties(height=height)
    )
    show(chart)


def macro_area_map(macro_totals, geo):
    """Neutral Italy map plus one circle per macro area, joined by a leader line.

    Circle area is proportional to total crimes (with a floor so text fits).
    """
    df = macro_totals.copy()
    df["circle_lon"] = df["macro_area_code"].map(lambda c: MAP_CIRCLE[c][0])
    df["circle_lat"] = df["macro_area_code"].map(lambda c: MAP_CIRCLE[c][1])
    df["anchor_lon"] = df["macro_area_code"].map(lambda c: MAP_ANCHOR[c][0])
    df["anchor_lat"] = df["macro_area_code"].map(lambda c: MAP_ANCHOR[c][1])
    scale = CIRCLE_MAX_PX2 / df["crime_count"].max()
    df["size_px2"] = (df["crime_count"] * scale).clip(lower=CIRCLE_MIN_PX2)
    df["opacity"] = df["selected"].map({"yes": 1.0, "no": 0.3})
    df["crimes_label"] = df["crime_count"].map(lambda v: f"{v:,.0f}")
    df["rate_label"] = df["crime_rate_per_100k"].map(lambda v: f"{v:,.0f} per 100k")

    # One leader line per land piece: circle -> anchor (Islands has Sicily and Sardinia).
    anchor_rows = []
    for code in df["macro_area_code"]:
        opacity = df.loc[df["macro_area_code"] == code, "opacity"].iloc[0]
        for n, (a_lon, a_lat) in enumerate([MAP_ANCHOR[code], *MAP_EXTRA_ANCHOR.get(code, [])]):
            anchor_rows.append((code, f"{code}-{n}", a_lon, a_lat, opacity))
    anchors_df = pd.DataFrame(
        anchor_rows, columns=["macro_area_code", "line_id", "anchor_lon", "anchor_lat", "opacity"]
    )
    circle_pos = df.set_index("macro_area_code")[["circle_lon", "circle_lat"]]
    lines = pd.concat(
        [
            anchors_df.rename(columns={"anchor_lon": "lon", "anchor_lat": "lat"})
            .drop(columns="line_id")
            .assign(line_id=anchors_df["line_id"], point=0),
            anchors_df.assign(
                lon=anchors_df["macro_area_code"].map(circle_pos["circle_lon"]),
                lat=anchors_df["macro_area_code"].map(circle_pos["circle_lat"]),
                point=1,
            )[["macro_area_code", "lon", "lat", "opacity", "line_id", "point"]],
        ]
    )

    land = (
        alt.Chart(alt.Data(values=geo, format=alt.DataFormat(property="features", type="json")))
        .mark_geoshape(fill="rgba(255,255,255,0.10)", stroke="rgba(255,255,255,0.35)", strokeWidth=0.8, tooltip=None)
    )
    leader = (
        alt.Chart(lines)
        .mark_line(strokeWidth=1.4, strokeDash=[4, 3], tooltip=None)
        .encode(
            longitude="lon:Q",
            latitude="lat:Q",
            detail="line_id:N",
            order="point:Q",
            color=alt.Color("macro_area_code:N", scale=alt.Scale(domain=list(MACRO_COLORS), range=list(MACRO_COLORS.values())), legend=None),
            opacity=alt.Opacity("opacity:Q", scale=None),
        )
    )
    anchors = (
        alt.Chart(anchors_df)
        .mark_circle(size=40, tooltip=None)
        .encode(
            longitude="anchor_lon:Q",
            latitude="anchor_lat:Q",
            color=alt.Color("macro_area_code:N", scale=alt.Scale(domain=list(MACRO_COLORS), range=list(MACRO_COLORS.values())), legend=None),
            opacity=alt.Opacity("opacity:Q", scale=None),
        )
    )
    tip = [
        alt.Tooltip("macro_area:N", title="Macro-area"),
        alt.Tooltip("crime_count:Q", title="Total crimes", format=",.0f"),
        alt.Tooltip("crime_rate_per_100k:Q", title="Per 100,000 inhabitants", format=",.1f"),
    ]
    circles = (
        alt.Chart(df)
        .mark_circle(stroke="rgba(255,255,255,0.6)", strokeWidth=1.2)
        .encode(
            longitude="circle_lon:Q",
            latitude="circle_lat:Q",
            size=alt.Size("size_px2:Q", scale=None, legend=None),
            color=alt.Color("macro_area_code:N", scale=alt.Scale(domain=list(MACRO_COLORS), range=list(MACRO_COLORS.values())), legend=None),
            opacity=alt.Opacity("opacity:Q", scale=None),
            tooltip=tip,
        )
    )

    def text(field, dy, size, weight):
        return (
            alt.Chart(df)
            .mark_text(color="#1a1c2c", fontSize=size, fontWeight=weight, dy=dy)
            .encode(
                longitude="circle_lon:Q",
                latitude="circle_lat:Q",
                text=f"{field}:N",
                opacity=alt.Opacity("opacity:Q", scale=None),
                tooltip=tip,
            )
        )

    layers = [
        land,
        leader,
        anchors,
        circles,
        text("macro_area", -22, 12, "bold"),
        text("crimes_label", -2, 18, 800),
        text("rate_label", 20, 11, "normal"),
    ]
    chart = (
        alt.layer(*layers)
        .project(type="mercator")
        .properties(height=560)
    )
    show(chart)


def kpi(label: str, value: str, chip_text: str = "", chip_kind: str = "flat") -> None:
    chip = f'<span class="kpi-chip chip-{chip_kind}">{chip_text}</span>' if chip_text else ""
    st.markdown(
        f'<div class="kpi-label">{label}</div><div class="kpi-value">{value}</div>{chip}',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------
data = run_query("city")
macro_data = run_query("macro")
crime_data = run_query("crime")

# Snowflake NUMBER columns can arrive as Decimal objects: force standard types.
for frame in (data, macro_data, crime_data):
    frame["year"] = frame["year"].astype(int)
    frame["is_severe_crime"] = frame["is_severe_crime"].astype(bool)
    frame["crime_count"] = frame["crime_count"].astype(float)
for frame in (data, macro_data):
    frame["population"] = frame["population"].astype(float)

macro_name_to_code = {name: code for code, name in MACRO_AREA_EN.items()}
macro_options = list(MACRO_AREA_EN.values())
year_options = sorted(data["year"].unique().tolist())

# ---------------------------------------------------------------------------
# Header and filters (three cards on one row)
# ---------------------------------------------------------------------------
st.markdown('<p class="page-title">Crime Analysis Italy</p>', unsafe_allow_html=True)
st.markdown(
    '<p class="page-sub">Reported crimes in Italian provincial capitals, ISTAT data 2019-2024.</p>',
    unsafe_allow_html=True,
)

city_macro_names = (
    data.drop_duplicates("area_name").set_index("area_name")["macro_area_code"].map(MACRO_AREA_EN)
)


def sync_macro_with_cities() -> None:
    """When cities are chosen, the macro-area buttons follow them (and are locked).

    The previous macro-area selection is kept and restored when the city list is emptied.
    """
    cities = st.session_state.get("city_sel", [])
    if cities:
        st.session_state.setdefault("macro_backup", list(st.session_state["macro_sel"]))
        wanted = set(city_macro_names.reindex(cities).dropna())
        st.session_state["macro_sel"] = [m for m in macro_options if m in wanted]
    elif "macro_backup" in st.session_state:
        st.session_state["macro_sel"] = st.session_state.pop("macro_backup")


st.session_state.setdefault("macro_sel", list(macro_options))
cities_locked = bool(st.session_state.get("city_sel"))

with st.container(key="row_filters"):
    col_macro, col_crime, col_years = st.columns([5, 4, 5])
    with col_macro:
        with st.container(key="card_macro"):
            card_title("🧭", "Macro-area", "set by the city selection" if cities_locked else "")
            macro_sel = st.pills(
                "Macro-area", macro_options, selection_mode="multi", key="macro_sel",
                disabled=cities_locked, label_visibility="collapsed",
            )
    with col_crime:
        with st.container(key="card_crime"):
            card_title("🚨", "Crime type & cities")
            sev_col, city_col = st.columns([5, 4], vertical_alignment="center")
            with sev_col:
                severity_sel = st.pills(
                    "Crime type", ["Severe", "Non-severe"], selection_mode="multi",
                    default=["Severe", "Non-severe"], label_visibility="collapsed",
                )
            with city_col:
                # Same look as the pills. The list offers the cities of the macro-areas in scope:
                # the current selection, or the one saved before cities were chosen.
                scope = st.session_state.get("macro_backup", macro_sel) or []
                available = data[
                    data["macro_area_code"].isin([macro_name_to_code[n] for n in scope])
                ]
                city_names = sorted(available["area_name"].unique().tolist())
                st.session_state["city_sel"] = [
                    c for c in st.session_state.get("city_sel", []) if c in city_names
                ]
                n_cities = len(st.session_state["city_sel"])
                with st.container(key="city_pop_on" if n_cities else "city_pop"):
                    with st.popover(
                        f"Cities ({n_cities})" if n_cities else "All cities", width="stretch"
                    ):
                        city_sel = st.multiselect(
                            "Cities", city_names, key="city_sel", placeholder="Search a city",
                            help="Leave empty to include all cities.",
                            on_change=sync_macro_with_cities,
                        )
    with col_years:
        with st.container(key="card_years"):
            card_title("📅", "Years")
            year_sel = st.pills(
                "Years", year_options, selection_mode="multi", default=year_options,
                label_visibility="collapsed",
            )

if not (macro_sel and severity_sel and year_sel):
    st.info("Select at least one option in each filter.")
    st.stop()

macro_codes = [macro_name_to_code[name] for name in macro_sel]
severity_flags = []
if "Severe" in severity_sel:
    severity_flags.append(True)
if "Non-severe" in severity_sel:
    severity_flags.append(False)
year_sel = sorted(year_sel)
city_codes = (
    data.loc[data["area_name"].isin(city_sel), "area_code"].unique().tolist() if city_sel else None
)

subset = data[
    data["macro_area_code"].isin(macro_codes)
    & data["is_severe_crime"].isin(severity_flags)
    & data["year"].isin(year_sel)
]
if city_codes is not None:
    subset = subset[subset["area_code"].isin(city_codes)]
if subset.empty:
    st.info("No data for this selection.")
    st.stop()

# ---------------------------------------------------------------------------
# Aggregation. Rate rule: sum crime_count and population first, then recompute.
# ---------------------------------------------------------------------------
# One row per city and year (severity groups summed; population taken once).
per_area_year = subset.groupby(
    ["area_code", "area_name", "macro_area_code", "year"], as_index=False
).agg(crime_count=("crime_count", "sum"), population=("population", "max"))
per_area_year["crime_rate_per_100k"] = (
    per_area_year["crime_count"] / per_area_year["population"] * 100_000
)

# One row per city over the selected years.
totals = per_area_year.groupby(["area_code", "area_name", "macro_area_code"], as_index=False).agg(
    crime_count=("crime_count", "sum"), population=("population", "sum")
)
totals["crime_rate_per_100k"] = totals["crime_count"] / totals["population"] * 100_000

top_total = totals.nlargest(5, "crime_count")
top_rate = totals.nlargest(5, "crime_rate_per_100k")

# Per year, all selected cities together (KPIs).
per_year = per_area_year.groupby("year", as_index=False).agg(
    crime_count=("crime_count", "sum"), population=("population", "sum")
)
per_year["crime_rate_per_100k"] = per_year["crime_count"] / per_year["population"] * 100_000
total_crimes = totals["crime_count"].sum()
overall_rate = total_crimes / totals["population"].sum() * 100_000

# Macro areas: rows already aggregated in the data. The map follows the year and
# crime-type filters; the macro-area buttons only dim the areas not selected.
macro_subset = macro_data[
    macro_data["is_severe_crime"].isin(severity_flags) & macro_data["year"].isin(year_sel)
]
macro_per_year = macro_subset.groupby(["macro_area_code", "year"], as_index=False).agg(
    crime_count=("crime_count", "sum"), population=("population", "max")
)
macro_totals = macro_per_year.groupby("macro_area_code", as_index=False).agg(
    crime_count=("crime_count", "sum"), population=("population", "sum")
)
macro_totals["crime_rate_per_100k"] = (
    macro_totals["crime_count"] / macro_totals["population"] * 100_000
)
macro_totals["macro_area"] = macro_totals["macro_area_code"].map(MACRO_AREA_EN)
macro_totals["selected"] = macro_totals["macro_area_code"].isin(macro_codes).map(
    {True: "yes", False: "no"}
)

# Crime types under the active filters.
crime_subset = crime_data[
    crime_data["macro_area_code"].isin(macro_codes)
    & crime_data["is_severe_crime"].isin(severity_flags)
    & crime_data["year"].isin(year_sel)
]
if city_codes is not None:
    crime_subset = crime_subset[crime_subset["area_code"].isin(city_codes)]
crime_types = (
    crime_subset
    .groupby(["crime_name", "is_severe_crime"], as_index=False)["crime_count"]
    .sum()
    .nlargest(TOP_CRIME_TYPES, "crime_count")
)
crime_types["group"] = crime_types["is_severe_crime"].map({True: "Severe", False: "Non-severe"})

# Severe vs non-severe over time (follows macro-area and year filters).
severity_trend = (
    subset.groupby(["year", "is_severe_crime"], as_index=False)["crime_count"].sum()
)
severity_trend["group"] = severity_trend["is_severe_crime"].map(
    {True: "Severe", False: "Non-severe"}
)
# Index: first selected year = 100 for each group, so the two shapes are comparable
# (severe crimes are a small fraction of the total, so absolute values would be flat).
severity_trend["index"] = severity_trend.groupby("group")["crime_count"].transform(
    lambda s: s / s.iloc[0] * 100
)

# ---------------------------------------------------------------------------
# KPI strip
# ---------------------------------------------------------------------------
if len(year_sel) >= 2:
    first = per_year.loc[per_year["year"] == year_sel[0], "crime_count"].iloc[0]
    last = per_year.loc[per_year["year"] == year_sel[-1], "crime_count"].iloc[0]
    change = (last - first) / first * 100 if first else 0.0
    change_label = f"{change:+.1f}%"
    change_chip = f"{year_sel[0]} → {year_sel[-1]}"
    change_kind = "up" if change > 0.05 else "down" if change < -0.05 else "flat"
else:
    change_label, change_chip, change_kind = "n/a", "select 2+ years", "flat"

with st.container(key="row_kpi"):
    k1, k2, k3, k4 = st.columns(4)
    with k1:
        with st.container(key="kpi_total"):
            kpi(
                "Total crimes (provincial capitals only)",
                f"{total_crimes:,.0f}",
                f"{len(year_sel)} year(s) selected",
            )
    with k2:
        with st.container(key="kpi_rate"):
            kpi("Crimes per 100,000 inhabitants", f"{overall_rate:,.0f}", "total ÷ population")
    with k3:
        with st.container(key="kpi_change"):
            kpi("Change first → last year", change_label, change_chip, change_kind)
    with k4:
        with st.container(key="kpi_cities"):
            kpi("Cities", f"{totals['area_code'].nunique()}", "provincial capitals")

# ---------------------------------------------------------------------------
# Row: crime types + severe vs non-severe (left), map or city table (right)
# ---------------------------------------------------------------------------
city_table = (
    totals.assign(macro_area=totals["macro_area_code"].map(MACRO_AREA_EN))
    .sort_values("crime_count", ascending=False)[
        ["area_name", "macro_area", "crime_count", "population", "crime_rate_per_100k"]
    ]
    .rename(
        columns={
            "area_name": "city",
            "macro_area": "macro-area",
            "crime_count": "crimes",
            "population": "population (sum of years)",
            "crime_rate_per_100k": "rate per 100k",
        }
    )
    .round(1)
)

def keep_view() -> None:
    """Keep exactly one map view selected: clicking the active option restores it."""
    if st.session_state.get("map_view") is None:
        st.session_state["map_view"] = st.session_state.get("map_view_last", "Map")
    st.session_state["map_view_last"] = st.session_state["map_view"]


with st.container(key="row_main"):
    left_col, right_col = st.columns([5, 7])
    with left_col:
        with st.container(key="card_types"):
            card_title("🔎", f"Top {TOP_CRIME_TYPES} crime types", "cities, active filters")
            bars = (
                alt.Chart(crime_types)
                .mark_bar(cornerRadiusEnd=6, size=16)
                .encode(
                    y=alt.Y(
                        "crime_name:N",
                        sort="-x",
                        title=None,
                        axis=alt.Axis(labelLimit=230, labelColor=TEXT_COLOR),
                    ),
                    x=alt.X("crime_count:Q", title="Reported crimes", axis=alt.Axis(format="~s")),
                    color=alt.Color(
                        "group:N",
                        scale=alt.Scale(domain=["Severe", "Non-severe"], range=[CORAL, SKY]),
                        legend=alt.Legend(orient="top", title=None, offset=2, padding=0),
                    ),
                    tooltip=[
                        alt.Tooltip("crime_name:N", title="Crime type"),
                        alt.Tooltip("group:N", title="Group"),
                        alt.Tooltip("crime_count:Q", title="Reported crimes", format=",.0f"),
                    ],
                )
                .properties(height=alt.Step(28), padding={"left": 5, "top": 0, "right": 5, "bottom": 5})
            )
            show(bars)
        with st.container(key="card_severity"):
            card_title("⚖️", "Severe vs non-severe", "index, first year = 100")
            trend = (
                alt.Chart(severity_trend)
                .mark_line(interpolate="monotone", strokeWidth=3, point=alt.OverlayMarkDef(size=60, filled=True))
                .encode(
                    x=alt.X("year:O", title=None, axis=alt.Axis(labelAngle=0)),
                    y=alt.Y(
                        "index:Q",
                        title="Index (first year = 100)",
                        scale=alt.Scale(zero=False),
                        axis=alt.Axis(format=",.0f"),
                    ),
                    color=alt.Color(
                        "group:N",
                        scale=alt.Scale(domain=["Severe", "Non-severe"], range=[CORAL, SKY]),
                        legend=alt.Legend(orient="top", title=None, offset=2, padding=0),
                    ),
                    tooltip=[
                        alt.Tooltip("group:N", title="Group"),
                        alt.Tooltip("year:O", title="Year"),
                        alt.Tooltip("index:Q", title="Index", format=",.1f"),
                        alt.Tooltip("crime_count:Q", title="Reported crimes", format=",.0f"),
                    ],
                )
                .properties(height=130, padding={"left": 5, "top": 0, "right": 5, "bottom": 5})
            )
            show(trend)
            st.caption("Indexed to the first selected year; hover for absolute counts.")
    with right_col:
        with st.container(key="card_map"):
            title_col, switch_col = st.columns([5, 3])
            with switch_col:
                view = st.segmented_control(
                    "View", ["Map", "All cities"], default="Map", label_visibility="collapsed",
                    key="map_view", on_change=keep_view,
                )
            with title_col:
                if view == "All cities":
                    card_title("📋", "All cities", f"{len(totals)} provincial capitals, selected years")
                else:
                    card_title("🗺️", "Crimes by macro-area", "all municipalities, not only capitals")
            if view == "All cities":
                st.dataframe(
                    city_table,
                    width="stretch",
                    hide_index=True,
                    height=500,
                    column_config={
                        "crimes": st.column_config.NumberColumn(format="localized"),
                        "population (sum of years)": st.column_config.NumberColumn(format="localized"),
                        "rate per 100k": st.column_config.NumberColumn(format="localized"),
                    },
                )
                st.download_button(
                    "Download CSV",
                    city_table.to_csv(index=False).encode("utf-8"),
                    file_name="crimes_by_city.csv",
                    mime="text/csv",
                )
            else:
                macro_area_map(macro_totals, load_macro_geojson())
                st.caption(
                    "Whole macro-areas (not only the provincial capitals). Follows the years and "
                    "crime-type filters; macro-areas not selected are dimmed."
                    + (" Not affected by the city selection." if city_codes is not None else "")
                )

# ---------------------------------------------------------------------------
# Row: top-5 cities over time
# ---------------------------------------------------------------------------
with st.container(key="row_bottom"):
    top_left, top_right = st.columns(2)
    with top_left:
        with st.container(key="card_top_total"):
            card_title("🏙️", "Top 5 cities by total crimes")
            top5_chart(
                per_area_year, top_total, "crime_count", "Reported crimes", ",.0f",
                height=280, y_pad=5000,
            )
    with top_right:
        with st.container(key="card_top_rate"):
            card_title("📈", "Top 5 cities by crimes per 100,000 inhabitants")
            top5_chart(
                per_area_year, top_rate, "crime_rate_per_100k", "Crimes per 100,000 inhabitants", ",.1f",
                height=280, y_pad=1000,
            )

if len(year_sel) == 1:
    st.caption("With a single year selected, each chart shows one point per city.")

st.caption(
    "**Cities and filters.** City views cover the 108 provincial capitals only. The macro-area "
    "filter selects which of these cities are analysed; it does not give the figures of the whole "
    "macro-area. The rate is total crimes divided by total population, per 100,000 inhabitants, "
    "never an average of rates. Totals add up parent and standalone crime types and may differ "
    "slightly from the official ISTAT total (about 0.2% in 2024)."
)
st.caption(
    "**Map.** The map shows whole macro-areas (all municipalities), using the aggregated ISTAT "
    "figures. Its totals are therefore much higher than the sum of the provincial capitals shown "
    "elsewhere: over 2019-2024 the capitals account for about 46% of the macro-area totals, from "
    "34% in the South to 60% in the Centre. The map does not follow the city selection."
)
st.caption(
    "Background: Michelangelo, The Creation of Adam (detail), via Wikimedia Commons. "
    "Boundaries: ISTAT, CC BY 4.0."
)
