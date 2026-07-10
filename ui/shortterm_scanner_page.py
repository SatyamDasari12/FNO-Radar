import os
from datetime import datetime
import pytz
from utils.logging import logger

import plotly.graph_objs as go
import streamlit as st

from services.shortterm_scanner_service import scan_shortterm_stocks, fetch_india_vix

IST = pytz.timezone("Asia/Kolkata")


def _now_ist() -> str:
    return datetime.now(IST).strftime("%d %b %Y, %I:%M %p IST")


def _score_color(score: float) -> str:
    """Color based on composite score 0-100 (recalibrated for v2 continuous scoring)."""
    if score >= 55:
        return "#1a7f37"  # strong green
    elif score >= 40:
        return "#2ea043"  # moderate green
    elif score >= 25:
        return "#b45309"  # amber
    else:
        return "#b91c1c"  # red


def _score_label(score: float) -> str:
    """Label recalibrated for v2 continuous scoring model."""
    if score >= 55:
        return "🟢 Strong Buy"
    elif score >= 40:
        return "🟢 Moderate Buy"
    elif score >= 25:
        return "🟡 Watch"
    else:
        return "🔴 Weak"


def render_shortterm_scanner_page() -> None:
    st.title("🔍 ShortTerm Scanner")
    st.caption(
        f"Scan Midcap & Smallcap stocks using Moving Averages, RSI, Volume/OI, Bollinger Bands, VWAP, and India VIX | {_now_ist()}"
    )

    # ── Controls ──────────────────────────────────────────────────────────
    col1, col2, col3 = st.columns([1.5, 1.5, 1])
    with col1:
        universe_choice = st.selectbox(
            "Stock Universe",
            ["F&O Only", "Nifty Largecap 100", "Nifty Midcap 200", "Nifty Smallcap 200", "Nifty Microcap 250"],
            index=0,  # Keep F&O Only as default index
            help="Select which index universe to scan."
        )
    with col2:
        top_n = st.slider(
            "Max Candidates to Display",
            min_value=5,
            max_value=30,
            value=12,
            step=5,
            help="Limit the number of ranked stocks shown."
        )
    
    with col3:
        # Load India VIX dynamically
        vix_val = fetch_india_vix()
        if vix_val < 15:
            vix_desc = "🟢 Low Volatility (Bullish Favored)"
            vix_border = "#1a7f37"
        elif vix_val <= 20:
            vix_desc = "🟡 Elevated Volatility (Be Selective)"
            vix_border = "#b45309"
        else:
            vix_desc = "🔴 High Volatility (Risk-Off Alert)"
            vix_border = "#b91c1c"
            
        st.markdown(
            f"""
            <div style="
                border: 1px solid {vix_border}; 
                border-radius: 8px; 
                padding: 10px; 
                text-align: center;
                background-color: #161b22;
                margin-top: 15px;
            ">
                <span style="font-size: 0.72rem; color: #8b949e; text-transform: uppercase; font-weight: 700; letter-spacing: 0.05em;">India VIX Level</span><br/>
                <span style="font-size: 1.1rem; color: #e6edf3; font-weight: 800;">{vix_val:.2f}</span><br/>
                <span style="font-size: 0.68rem; color: #c9d1d9; font-weight: 600;">{vix_desc}</span>
            </div>
            """,
            unsafe_allow_html=True
        )

    # ── Action Buttons ───────────────────────────────────────────────────
    run_scan = st.button("🚀 Run ShortTerm Scanner", type="primary", use_container_width=True)

    if run_scan:
        progress_text = st.empty()
        progress_bar = st.progress(0.0)
        
        def update_progress(current: int, total: int, symbol: str):
            pct = current / total
            progress_bar.progress(pct)
            progress_text.markdown(f"⏳ **Scanning {current}/{total}:** `{symbol}`...")

        with st.spinner("Processing stock data, calculating indicators, and assessing risk..."):
            results = scan_shortterm_stocks(
                universe=universe_choice,
                top_n=top_n,
                progress_callback=update_progress
            )
            
        progress_text.empty()
        progress_bar.empty()

        if results is None or results.empty:
            st.warning("No stocks matched the short-term scanning criteria (or data is unavailable).")
            return

        try:
            os.makedirs("data", exist_ok=True)
            results.to_json("data/shortterm_scan_cache.json", orient="records", indent=2)
        except Exception as e:
            logger.error(f"Failed to cache shortterm scan results: {e}")

        st.subheader(f"🏆 Top Ranked {universe_choice} Candidates")
        st.caption(
            "Ranking based on Composite Score (0-100) combining 20EMA/50SMA Trend, RSI zone, Vol/OI expansion, Bollinger breakouts, and VWAP position."
        )

        # ── Candidates Cards ──────────────────────────────────────────────
        for rank, (_, row) in enumerate(results.iterrows(), start=1):
            score = row.get("Score", 0)
            symbol = row.get("Symbol", "")
            change = row.get("Change%", 0.0)
            rsi = row.get("RSI", 50.0)
            close = row.get("Close (₹)", 0.0)
            tags = row.get("Technical Tags", "Neutral")
            sector = row.get("Sector", "Other")
            is_early = row.get("Early Entry", False)
            
            stop_loss = row.get("Stop Loss (₹)", 0.0)
            target1 = row.get("Target 1 (₹)", 0.0)
            target2 = row.get("Target 2 (₹)", 0.0)
            expected_px = row.get("Expected Price (₹)", 0.0)
            momentum_5d = row.get("Momentum 5D%", 0.0)
            rr_ratio = row.get("R:R Ratio", 0.0)
            profit_1lakh = row.get("Exp. Profit (₹1L)", 0.0)
            holding_period = row.get("Holding Period", "8 - 12 days")
            
            return_1y = row.get("Return 1Y%", 0.0)
            high_52w = row.get("High 52W (₹)", 0.0)
            low_52w = row.get("Low 52W (₹)", 0.0)
            dist_from_high = row.get("Dist from 52W High%", 0.0)
            micro_low = row.get("Est 2W Micro Low", 0.0)
            micro_high = row.get("Est 2W Micro High", 0.0)
            macro_low = row.get("Est 2W Macro Low", 0.0)
            macro_high = row.get("Est 2W Macro High", 0.0)
            
            score_bg = _score_color(score)
            score_lbl = _score_label(score)
            
            change_color = "#3fb950" if change >= 0 else "#f85149"
            change_sign = "+" if change >= 0 else ""
            mom_color = "#3fb950" if momentum_5d >= 0 else "#f85149"
            mom_sign = "+" if momentum_5d >= 0 else ""
            rr_color = "#3fb950" if rr_ratio >= 1.5 else "#f59e0b" if rr_ratio >= 1.0 else "#f85149"
            
            early_badge = ""
            border_style = f"border-left: 5px solid {score_bg}; border: 1px solid #30363d;"
            if is_early:
                early_badge = '&nbsp;<span style="background:#f59e0b22; color:#f59e0b; font-size:0.68rem; padding:2px 7px; border-radius:20px; border:1px solid #f59e0b66; font-weight:700;">🌟 Early Entry</span>'
                border_style = "border: 1.5px solid #f59e0b;"  # Golden border highlight
            
            st.markdown(
                f"""<div style="background:#161b22; {border_style} border-radius:10px; padding:14px 18px; margin-bottom:10px;">
<div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
<div>
<span style="color:#8b949e; font-size:0.75rem; font-weight:700;">#{rank}</span>&nbsp;
<span style="color:#e6edf3; font-size:1.05rem; font-weight:800;">{symbol}</span>
&nbsp;<span style="color:#8b949e; font-size:0.75rem;">({sector})</span>
{early_badge}
</div>
<div style="display:flex; gap:10px; align-items:center;">
<span style="background:{score_bg}22; color:{score_bg}; padding:3px 8px; border-radius:6px; font-weight:800; font-size:0.8rem; border:1px solid {score_bg}55;">Score: {score:.1f} &nbsp;&bull;&nbsp; {score_lbl}</span>
<span style="color:{change_color}; font-weight:800; font-size:0.9rem;">{change_sign}{change:.2f}%</span>
</div>
</div>
<div style="margin-top:10px; border-top:1px solid #21262d; padding-top:8px;">
<div style="display:flex; gap:18px; flex-wrap:wrap; margin-bottom:6px;">
<span style="color:#8b949e; font-size:0.78rem;">Price: <b style="color:#e6edf3;">₹{close:.2f}</b></span>
<span style="color:#8b949e; font-size:0.78rem;">5D Mom: <b style="color:{mom_color};">{mom_sign}{momentum_5d:.1f}%</b></span>
<span style="color:#8b949e; font-size:0.78rem;">SL: <b style="color:#f85149;">₹{stop_loss:.2f}</b></span>
<span style="color:#8b949e; font-size:0.78rem;">T1: <b style="color:#3fb950;">₹{target1:.2f}</b></span>
<span style="color:#8b949e; font-size:0.78rem;">T2: <b style="color:#58a6ff;">₹{target2:.2f}</b></span>
<span style="color:#8b949e; font-size:0.78rem;">R:R <b style="color:{rr_color};">{rr_ratio:.1f}</b></span>
<span style="color:#8b949e; font-size:0.78rem;">Exp. Profit (₹1L): <b style="color:#2ea043;">₹{profit_1lakh:,.2f}</b></span>
<span style="color:#8b949e; font-size:0.78rem;">Holding: <b style="color:#58a6ff;">{holding_period}</b></span>
</div>
<div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px; font-size:0.76rem;">
<span style="color:#8b949e;">RSI: <b style="color:#c9d1d9;">{rsi:.1f}</b> &nbsp;&bull;&nbsp; {tags}</span>
{f'<span style="font-size:0.72rem; color:#f59e0b; font-style:italic;">🌟 Trend began in the last 48 hrs — High potential for early entry!</span>' if is_early else ''}
</div>
</div>
<div style="margin-top:6px; border-top:1px dashed #21262d; padding-top:6px;">
<span style="color:#8b949e; font-size:0.75rem;">1Y Return: <b style="color:{'#3fb950' if return_1y >= 0 else '#f85149'};">{'+' if return_1y >= 0 else ''}{return_1y:.1f}%</b></span> &nbsp;&bull;&nbsp;
<span style="color:#8b949e; font-size:0.75rem;">52W Range: ₹{low_52w:.1f} - ₹{high_52w:.1f} <b style="color:{'#f85149' if dist_from_high < -15 else '#c9d1d9'};">({dist_from_high:.1f}% from High)</b></span> &nbsp;&bull;&nbsp;
<span style="color:#8b949e; font-size:0.75rem;">Est 2W (Short-Term): <b style="color:#58a6ff;">₹{micro_low:.1f} - ₹{micro_high:.1f}</b></span> &nbsp;&bull;&nbsp;
<span style="color:#8b949e; font-size:0.75rem;">Est 2W (1Y Macro): <b style="color:#a371f7;">₹{macro_low:.1f} - ₹{macro_high:.1f}</b></span>
</div>
</div>""",
                unsafe_allow_html=True,
            )

        st.markdown("---")

        # ── Charts Section ──────────────────────────────────────────────────
        col_chart1, col_chart2 = st.columns(2)
        
        with col_chart1:
            st.subheader("📊 Momentum Score Comparison")
            fig_bar = go.Figure(
                go.Bar(
                    x=results["Symbol"],
                    y=results["Score"],
                    marker_color=[_score_color(s) for s in results["Score"]],
                    text=results["Score"],
                    textposition="outside",
                    textfont=dict(color="#c9d1d9")
                )
            )
            fig_bar.update_layout(
                height=320,
                margin=dict(l=10, r=10, t=20, b=50),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                dragmode=False,
                xaxis=dict(tickangle=-45, tickfont=dict(size=9, color="#8b949e")),
                yaxis=dict(title="Score", gridcolor="rgba(128,128,128,0.15)", color="#8b949e"),
            )
            st.plotly_chart(fig_bar, use_container_width=True, config={"displayModeBar": False})

        with col_chart2:
            st.subheader("🏭 Average Score by Sector")
            if "Sector" in results.columns:
                sector_avg = (
                    results.groupby("Sector")["Score"]
                    .mean()
                    .sort_values(ascending=False)
                    .reset_index()
                )
                fig_sector = go.Figure(
                    go.Bar(
                        x=sector_avg["Sector"],
                        y=sector_avg["Score"].round(1),
                        marker_color="#388bfd",
                        text=sector_avg["Score"].round(1),
                        textposition="outside",
                        textfont=dict(color="#c9d1d9")
                    )
                )
                fig_sector.update_layout(
                    height=320,
                    margin=dict(l=10, r=10, t=20, b=50),
                    plot_bgcolor="rgba(0,0,0,0)",
                    paper_bgcolor="rgba(0,0,0,0)",
                    dragmode=False,
                    xaxis=dict(tickangle=-45, tickfont=dict(size=9, color="#8b949e")),
                    yaxis=dict(title="Average Score", gridcolor="rgba(128,128,128,0.15)", color="#8b949e"),
                )
                st.plotly_chart(fig_sector, use_container_width=True, config={"displayModeBar": False})
