"""Runtime theme switching for Budget Tracker.

config.toml: base = "dark"
  → Streamlit propagates the theme to every sub-component via its JS bridge:
    Glide Data Grid canvas cells, tooltips, dropdowns, tab panels, etc.
  → We must NOT set background-color/color on canvas-rendered elements
    (.dvn-scroller, [data-testid="stDataFrameResizable"], [role="gridcell"]).
    Those overrides fight the JS renderer and make cell content invisible.

Dark mode  — palette reinforcement on top of the dark base (minimal CSS).
Light mode — full surface flip since the base is dark.
System     — dark rules unconditionally + @media (prefers-color-scheme: light).
"""

import streamlit as st

THEME_KEY     = "app_theme"
THEMES        = ["System", "Light", "Dark"]
DEFAULT_THEME = "System"

# ── Palette ────────────────────────────────────────────────────────────────────
_PRIMARY      = "#4CAF50"
_PRIMARY_DARK = "#388E3C"
_BG           = "#0e1117"
_SURFACE      = "#161b22"
_SURFACE2     = "#1c2128"
_BORDER       = "#30363d"
_TEXT         = "#e6edf3"
_TEXT_MUTED   = "#8b949e"

_L_BG         = "#ffffff"
_L_SURFACE    = "#f0f2f6"
_L_BORDER     = "#d0d4db"
_L_TEXT       = "#1f2328"
_L_MUTED      = "#57606a"

_ICONS = {"System": "🖥️ System", "Light": "☀️ Light", "Dark": "🌙 Dark"}


# ── Dark palette reinforcement ─────────────────────────────────────────────────
def _dark_rules() -> str:
    return f"""
    /* surfaces */
    html, body, .stApp,
    [data-testid="stAppViewContainer"],
    [data-testid="stMainBlockContainer"] {{
        background-color: {_BG} !important;
        color: {_TEXT} !important;
    }}
    [data-testid="stHeader"] {{
        background-color: rgba(14,17,23,.97) !important;
        border-bottom: 1px solid {_BORDER} !important;
    }}
    /* sidebar */
    [data-testid="stSidebar"] {{
        background-color: {_SURFACE} !important;
        border-right: 1px solid {_BORDER} !important;
    }}
    [data-testid="stSidebar"] *,
    [data-testid="stSidebarContent"] * {{
        color: {_TEXT} !important;
    }}
    /* metric cards */
    [data-testid="metric-container"] {{
        background-color: {_SURFACE} !important;
        border: 1px solid {_BORDER} !important;
        border-radius: 8px !important;
        padding: 16px !important;
    }}
    [data-testid="stMetricValue"],
    [data-testid="stMetricLabel"],
    [data-testid="stMetricDelta"] {{
        color: {_TEXT} !important;
    }}
    /* text */
    p, h1, h2, h3, h4, h5, h6, span, label, small,
    .stMarkdown, .stText,
    [data-testid="stMarkdownContainer"] {{
        color: {_TEXT} !important;
    }}
    [data-testid="stCaptionContainer"], .stCaption {{
        color: {_TEXT_MUTED} !important;
    }}
    /* tooltip popup */
    [data-baseweb="tooltip"] > div, [role="tooltip"] {{
        background-color: {_SURFACE2} !important;
        color: {_TEXT} !important;
        border: 1px solid {_BORDER} !important;
        border-radius: 6px !important;
    }}
    /* tabs */
    .stTabs [data-baseweb="tab-list"] {{
        background-color: {_SURFACE} !important;
        border-bottom: 1px solid {_BORDER} !important;
    }}
    .stTabs [data-baseweb="tab"] {{
        background-color: transparent !important;
        color: {_TEXT_MUTED} !important;
    }}
    .stTabs [aria-selected="true"] {{
        background-color: {_BG} !important;
        color: {_PRIMARY} !important;
        border-bottom: 2px solid {_PRIMARY} !important;
    }}
    .stTabs [data-baseweb="tab-panel"],
    [data-baseweb="tab-panel"] {{
        background-color: {_BG} !important;
        color: {_TEXT} !important;
    }}
    /* form inputs */
    .stTextInput input,
    .stNumberInput input,
    .stTextArea textarea,
    .stDateInput input {{
        background-color: {_SURFACE} !important;
        color: {_TEXT} !important;
        border-color: {_BORDER} !important;
    }}
    .stTextInput input::placeholder,
    .stNumberInput input::placeholder,
    .stTextArea textarea::placeholder {{
        color: {_TEXT_MUTED} !important;
    }}
    .stTextInput input:focus,
    .stNumberInput input:focus,
    .stTextArea textarea:focus {{
        border-color: {_PRIMARY} !important;
        box-shadow: 0 0 0 2px rgba(76,175,80,.25) !important;
    }}
    /* selectbox / dropdown */
    [data-testid="stSelectbox"] > div > div,
    [data-baseweb="select"] > div {{
        background-color: {_SURFACE} !important;
        color: {_TEXT} !important;
        border-color: {_BORDER} !important;
    }}
    [data-baseweb="popover"],
    [data-baseweb="popover"] ul,
    [data-baseweb="menu"] {{
        background-color: {_SURFACE2} !important;
        border: 1px solid {_BORDER} !important;
    }}
    [data-baseweb="option"] {{
        background-color: {_SURFACE2} !important;
        color: {_TEXT} !important;
    }}
    [data-baseweb="option"]:hover,
    [data-baseweb="option"][aria-selected="true"] {{
        background-color: {_SURFACE} !important;
    }}
    /* radio & checkbox */
    .stRadio label, .stCheckbox label,
    [data-testid="stWidgetLabel"] {{
        color: {_TEXT} !important;
    }}
    /* buttons */
    .stButton > button {{
        background-color: {_SURFACE2} !important;
        color: {_TEXT} !important;
        border-color: {_BORDER} !important;
    }}
    .stButton > button:hover {{
        border-color: {_PRIMARY} !important;
        background-color: {_SURFACE} !important;
    }}
    [data-testid="baseButton-primary"],
    .stButton > button[kind="primary"] {{
        background-color: {_PRIMARY} !important;
        border-color: {_PRIMARY} !important;
        color: #fff !important;
    }}
    [data-testid="baseButton-primary"]:hover,
    .stButton > button[kind="primary"]:hover {{
        background-color: {_PRIMARY_DARK} !important;
    }}
    [data-testid="stDownloadButton"] button {{
        background-color: {_SURFACE2} !important;
        color: {_TEXT} !important;
        border-color: {_BORDER} !important;
    }}
    /* dataframe — outer frame only; canvas cells are controlled by Streamlit JS */
    [data-testid="stDataFrame"] {{
        border: 1px solid {_BORDER} !important;
        border-radius: 4px !important;
    }}
    /* st.table (HTML table — fully CSS-controllable) */
    [data-testid="stTable"] table {{
        background-color: {_SURFACE} !important;
        color: {_TEXT} !important;
        border-collapse: collapse !important;
    }}
    [data-testid="stTable"] th {{
        background-color: {_SURFACE2} !important;
        color: {_TEXT} !important;
        border: 1px solid {_BORDER} !important;
        padding: 8px 12px !important;
    }}
    [data-testid="stTable"] td {{
        color: {_TEXT} !important;
        border: 1px solid {_BORDER} !important;
        padding: 8px 12px !important;
    }}
    [data-testid="stTable"] tr:nth-child(even) td {{
        background-color: {_SURFACE2} !important;
    }}
    /* expander — no border-radius to avoid canvas clipping */
    [data-testid="stExpander"] {{
        background-color: {_SURFACE} !important;
        border: 1px solid {_BORDER} !important;
    }}
    [data-testid="stExpander"] summary,
    [data-testid="stExpander"] summary p {{
        color: {_TEXT} !important;
    }}
    /* file uploader */
    [data-testid="stFileUploader"],
    [data-testid="stFileUploadDropzone"] {{
        background-color: {_SURFACE} !important;
        border: 2px dashed {_BORDER} !important;
    }}
    [data-testid="stFileUploader"] *,
    [data-testid="stFileUploadDropzone"] * {{
        color: {_TEXT} !important;
    }}
    /* alerts */
    [data-testid="stAlert"] {{
        background-color: {_SURFACE2} !important;
        border-color: {_BORDER} !important;
    }}
    [data-testid="stAlert"] p,
    [data-testid="stAlert"] span {{
        color: {_TEXT} !important;
    }}
    /* json viewer */
    [data-testid="stJson"] {{
        background-color: {_SURFACE} !important;
        color: {_TEXT} !important;
    }}
    hr {{ border-color: {_BORDER} !important; }}
    """


# ── Full light override ────────────────────────────────────────────────────────
def _light_rules() -> str:
    return f"""
    html, body, .stApp,
    [data-testid="stAppViewContainer"],
    [data-testid="stMainBlockContainer"] {{
        background-color: {_L_BG} !important;
        color: {_L_TEXT} !important;
    }}
    [data-testid="stHeader"] {{
        background-color: rgba(255,255,255,.97) !important;
        border-bottom: 1px solid {_L_BORDER} !important;
    }}
    [data-testid="stSidebar"] {{
        background-color: {_L_SURFACE} !important;
        border-right: 1px solid {_L_BORDER} !important;
    }}
    [data-testid="stSidebar"] *,
    [data-testid="stSidebarContent"] * {{
        color: {_L_TEXT} !important;
    }}
    [data-testid="metric-container"] {{
        background-color: {_L_BG} !important;
        border: 1px solid {_L_BORDER} !important;
        border-radius: 8px !important;
        padding: 16px !important;
    }}
    [data-testid="stMetricValue"],
    [data-testid="stMetricLabel"],
    [data-testid="stMetricDelta"] {{
        color: {_L_TEXT} !important;
    }}
    p, h1, h2, h3, h4, h5, h6, span, label, small,
    .stMarkdown, .stText,
    [data-testid="stMarkdownContainer"],
    .stRadio label, .stCheckbox label,
    [data-testid="stWidgetLabel"] {{
        color: {_L_TEXT} !important;
    }}
    [data-testid="stCaptionContainer"], .stCaption {{
        color: {_L_MUTED} !important;
    }}
    [data-baseweb="tooltip"] > div, [role="tooltip"] {{
        background-color: {_L_SURFACE} !important;
        color: {_L_TEXT} !important;
        border: 1px solid {_L_BORDER} !important;
    }}
    .stTabs [data-baseweb="tab-list"] {{
        background-color: {_L_SURFACE} !important;
        border-bottom: 1px solid {_L_BORDER} !important;
    }}
    .stTabs [data-baseweb="tab"] {{
        background-color: transparent !important;
        color: {_L_MUTED} !important;
    }}
    .stTabs [aria-selected="true"] {{
        background-color: {_L_BG} !important;
        color: {_PRIMARY} !important;
    }}
    .stTabs [data-baseweb="tab-panel"],
    [data-baseweb="tab-panel"] {{
        background-color: {_L_BG} !important;
        color: {_L_TEXT} !important;
    }}
    .stTextInput input, .stNumberInput input,
    .stTextArea textarea, .stDateInput input {{
        background-color: {_L_BG} !important;
        color: {_L_TEXT} !important;
        border-color: {_L_BORDER} !important;
    }}
    [data-testid="stSelectbox"] > div > div,
    [data-baseweb="select"] > div {{
        background-color: {_L_BG} !important;
        color: {_L_TEXT} !important;
        border-color: {_L_BORDER} !important;
    }}
    [data-baseweb="popover"], [data-baseweb="menu"] {{
        background-color: {_L_BG} !important;
        border: 1px solid {_L_BORDER} !important;
    }}
    [data-baseweb="option"] {{
        background-color: {_L_BG} !important;
        color: {_L_TEXT} !important;
    }}
    [data-baseweb="option"]:hover {{
        background-color: {_L_SURFACE} !important;
    }}
    .stButton > button {{
        background-color: {_L_BG} !important;
        color: {_L_TEXT} !important;
        border-color: {_L_BORDER} !important;
    }}
    [data-testid="baseButton-primary"],
    .stButton > button[kind="primary"] {{
        background-color: {_PRIMARY} !important;
        border-color: {_PRIMARY} !important;
        color: #fff !important;
    }}
    [data-testid="stDataFrame"] {{
        border: 1px solid {_L_BORDER} !important;
        border-radius: 4px !important;
    }}
    [data-testid="stTable"] table {{
        background-color: {_L_BG} !important;
        color: {_L_TEXT} !important;
        border-collapse: collapse !important;
    }}
    [data-testid="stTable"] th {{
        background-color: {_L_SURFACE} !important;
        color: {_L_TEXT} !important;
        border: 1px solid {_L_BORDER} !important;
        padding: 8px 12px !important;
    }}
    [data-testid="stTable"] td {{
        color: {_L_TEXT} !important;
        border: 1px solid {_L_BORDER} !important;
        padding: 8px 12px !important;
    }}
    [data-testid="stExpander"] {{
        background-color: {_L_SURFACE} !important;
        border: 1px solid {_L_BORDER} !important;
    }}
    [data-testid="stExpander"] summary,
    [data-testid="stExpander"] summary p {{
        color: {_L_TEXT} !important;
    }}
    [data-testid="stFileUploader"],
    [data-testid="stFileUploadDropzone"] {{
        background-color: {_L_SURFACE} !important;
        border: 2px dashed {_L_BORDER} !important;
    }}
    [data-testid="stFileUploader"] *,
    [data-testid="stFileUploadDropzone"] * {{
        color: {_L_TEXT} !important;
    }}
    [data-testid="stAlert"] {{
        background-color: {_L_SURFACE} !important;
        color: {_L_TEXT} !important;
    }}
    [data-testid="stJson"] {{
        background-color: {_L_SURFACE} !important;
        color: {_L_TEXT} !important;
    }}
    hr {{ border-color: {_L_BORDER} !important; }}
    """


# ── CSS composition ────────────────────────────────────────────────────────────
def _themed_css(mode: str) -> str:
    dark  = _dark_rules()
    light = _light_rules()
    if mode == "Dark":
        return f"<style>{dark}</style>"
    if mode == "Light":
        return f"<style>{light}</style>"
    # System: dark rules always active (dark base = default);
    # light rules activate only when OS prefers light
    return f"<style>{dark}@media (prefers-color-scheme: light) {{{light}}}</style>"


# ── Public API ─────────────────────────────────────────────────────────────────
def apply_theme() -> None:
    """Inject theme CSS. Call once per render at the top of app.py."""
    mode = st.session_state.get(THEME_KEY, DEFAULT_THEME)
    st.markdown(_themed_css(mode), unsafe_allow_html=True)


def render_selector(compact: bool = False) -> None:
    current = st.session_state.get(THEME_KEY, DEFAULT_THEME)
    idx     = THEMES.index(current) if current in THEMES else 0
    selected = st.radio(
        "🎨 Theme",
        THEMES,
        index=idx,
        horizontal=compact,
        format_func=lambda t: _ICONS[t],
        key="theme_radio_compact" if compact else "theme_radio_settings",
    )
    if selected != current:
        st.session_state[THEME_KEY] = selected
        st.rerun()
