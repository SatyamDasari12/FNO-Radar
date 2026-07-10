import streamlit as st

from ui.stock_analysis_page import render_stock_analysis_page
from ui.intraday_scanner_page import render_intraday_scanner_page
from ui.options_scanner_page import render_options_scanner_page
from ui.portfolio_advisor_page import render_portfolio_advisor_page
from ui.shortterm_scanner_page import render_shortterm_scanner_page
from ui.early_breakout_page import render_early_breakout_page
from ui.paper_trader_page import render_paper_trader_page


PAGES = {
    "📈 Stock Analysis": render_stock_analysis_page,
    "⚡ Intraday Scanner": render_intraday_scanner_page,
    "📊 Options Scanner": render_options_scanner_page,
    "🔍 ShortTerm Scanner": render_shortterm_scanner_page,
    "🚀 Early Breakout": render_early_breakout_page,
    "🧺 Portfolio Advisor": render_portfolio_advisor_page,
    "🎮 Dummy Trading": render_paper_trader_page,
}

CUSTOM_CSS = """
<style>
/* ── Font ── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

/* ── App background ── */
.stApp {
    background: #0d1117;
}

header[data-testid="stHeader"] {
    background: transparent !important;
}

.block-container {
    max-width: 98% !important;
    padding-top: 1rem !important;
    padding-bottom: 1rem !important;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: #161b22;
    border-right: 1px solid #30363d;
}
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] div {
    color: #c9d1d9 !important;
}
[data-testid="stSidebar"] h2 {
    color: #58a6ff !important;
    font-size: 1.1rem !important;
    font-weight: 700 !important;
    text-align: center;
    background: none !important;
    -webkit-text-fill-color: unset !important;
}

/* ── Headings (explicit colors, no gradient text on small elements) ── */
h1 {
    color: #e6edf3 !important;
    font-weight: 800 !important;
    font-size: 1.9rem !important;
    border-bottom: 2px solid #21262d;
    padding-bottom: 0.35em;
    background: none !important;
    -webkit-text-fill-color: #e6edf3 !important;
}
h2 {
    color: #58a6ff !important;
    font-weight: 700 !important;
    font-size: 1.15rem !important;
    background: none !important;
    -webkit-text-fill-color: #58a6ff !important;
    border-left: 3px solid #1f6feb;
    padding-left: 10px;
    margin-top: 1.4em;
}
h3 {
    color: #c9d1d9 !important;
    font-weight: 600 !important;
    font-size: 1rem !important;
    background: none !important;
    -webkit-text-fill-color: #c9d1d9 !important;
}

/* ── Body text ── */
p, li, span, label {
    color: #c9d1d9 !important;
}
strong, b {
    color: #e6edf3 !important;
}

/* ── Metric cards ── */
[data-testid="stMetric"] {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 10px;
    padding: 10px 14px;
}
[data-testid="stMetricLabel"] p {
    color: #8b949e !important;
    font-size: 0.75rem !important;
    font-weight: 600 !important;
    text-transform: uppercase;
    letter-spacing: 0.06em;
}
[data-testid="stMetricValue"] {
    color: #e6edf3 !important;
    font-size: 1.3rem !important;
    font-weight: 700 !important;
}
[data-testid="stMetricValue"] * {
    color: #e6edf3 !important;
}
[data-testid="stMetricDelta"] {
    font-size: 0.8rem !important;
}
[data-testid="stMetricDelta"] svg { display: none; }

/* ── Buttons ── */
.stButton > button {
    border-radius: 8px;
    font-weight: 600;
    font-size: 0.9rem;
    letter-spacing: 0.04em;
    transition: all 0.18s ease;
    color: #e6edf3 !important;
    background: #21262d;
    border: 1px solid #30363d;
}
.stButton > button:hover {
    transform: translateY(-2px);
    border-color: #58a6ff;
    box-shadow: 0 4px 16px rgba(88, 166, 255, 0.2);
}
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #1a7f37 0%, #238636 100%);
    border: 1px solid #2ea043;
    color: #ffffff !important;
}
.stButton > button[kind="primary"]:hover {
    box-shadow: 0 4px 18px rgba(46, 160, 67, 0.35);
}

/* ── Inputs ── */
.stTextInput > div > div > input,
.stNumberInput > div > div > input {
    background: #161b22 !important;
    border: 1px solid #30363d !important;
    color: #e6edf3 !important;
    border-radius: 8px !important;
}
.stTextInput > label, .stNumberInput > label,
.stSelectbox > label, .stSlider > label,
.stCheckbox > label, .stDateInput > label {
    color: #8b949e !important;
    font-size: 0.82rem !important;
    font-weight: 600 !important;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
.stCheckbox span { color: #c9d1d9 !important; }

/* ── Selectbox ── */
[data-testid="stSelectbox"] > div > div {
    background: #161b22 !important;
    border: 1px solid #30363d !important;
    border-radius: 8px !important;
    color: #e6edf3 !important;
}

/* ── Progress bar ── */
.stProgress > div > div {
    border-radius: 6px;
    background: linear-gradient(90deg, #238636, #2ea043) !important;
}
.stProgress > div {
    background: #21262d;
    border-radius: 6px;
}

/* ── Expander ── */
details[data-testid="stExpander"] summary {
    background: #161b22 !important;
    border: 1px solid #30363d !important;
    border-radius: 8px;
    color: #c9d1d9 !important;
    padding: 8px 12px;
    font-weight: 500;
}
details[data-testid="stExpander"] summary:hover {
    border-color: #58a6ff !important;
}
details[data-testid="stExpander"] > div {
    background: #0d1117;
    border: 1px solid #21262d;
    border-top: none;
    border-radius: 0 0 8px 8px;
    padding: 12px;
}

/* ── Info / warning / error alerts ── */
[data-testid="stAlert"] {
    border-radius: 8px;
    border: 1px solid #30363d;
    background: #161b22 !important;
}
[data-testid="stAlert"] p { color: #c9d1d9 !important; }

/* ── DataFrame / table ── */
[data-testid="stDataFrame"] {
    border-radius: 10px;
    overflow: hidden;
    border: 1px solid #30363d;
}

/* ── Caption ── */
[data-testid="stCaptionContainer"] p {
    color: #8b949e !important;
    font-size: 0.82rem !important;
}

/* ── Divider ── */
hr { border-color: #21262d !important; }

/* ── Selectbox dropdown list — BaseWebUI portal-level selectors ── */
/* The dropdown renders in a portal OUTSIDE .stSelectbox, so must target globally */
[data-baseweb="popover"] { background-color: #2d333b !important; }
[data-baseweb="popover"] ul { background-color: #2d333b !important; }
ul[role="listbox"] { background-color: #2d333b !important; color: #e6edf3 !important; border: 1px solid #444c56 !important; border-radius: 8px !important; }
li[role="option"] { background-color: #2d333b !important; color: #e6edf3 !important; }
li[role="option"]:hover, [data-highlighted] { background-color: #373e47 !important; color: #ffffff !important; }
li[role="option"][aria-selected="true"] { background-color: #1f6feb44 !important; color: #58a6ff !important; font-weight: 600; }
</style>
"""


def main() -> None:
    st.set_page_config(
        page_title="FNO-Radar (NSE/BSE)",
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

    with st.sidebar:
        st.markdown(
            "<h2 style='text-align:center; color:#58a6ff !important;'>📈 FNO-Radar</h2>",
            unsafe_allow_html=True,
        )
        st.caption("Stock assistant")
        st.markdown("---")

        selected_page = st.radio(
            "Navigate",
            list(PAGES.keys()),
            label_visibility="collapsed",
        )

        st.markdown("---")
        st.markdown("**🤖 AI Models**")
        st.caption("• Llama 3.3 70B (Groq) — Reasoning")
        st.caption("• Random Forest + Gradient Boosting — Prediction")
        st.caption("• Prophet — Price Range Forecast")
        st.caption("• all-MiniLM-L6-v2 — News RAG")

        st.markdown("---")
        st.markdown("**📡 Data Sources**")
        st.caption("• yfinance — Price & Options")
        st.caption("• Economic Times RSS — News")
        st.caption("• MoneyControl RSS — News")

        st.markdown("---")
        st.caption("⚠️ Educational only. Not SEBI-registered advice.")

    PAGES[selected_page]()


if __name__ == "__main__":
    main()
