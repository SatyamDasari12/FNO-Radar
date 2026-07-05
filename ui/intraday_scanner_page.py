from datetime import datetime
import pytz

import plotly.graph_objs as go
import streamlit as st

from services.scanner_service import scan_intraday_momentum_stocks, compute_sector_rotation

IST = pytz.timezone("Asia/Kolkata")


def _now_ist() -> str:
    return datetime.now(IST).strftime("%d %b %Y, %I:%M %p IST")


def render_intraday_scanner_page() -> None:
    st.title("⚡ Intraday Scanner")
    st.caption(f"Volume spikes, RSI/VWAP breakouts, MACD momentum, sector rotation | Data as of {_now_ist()}")

    col1, col2 = st.columns([2, 1])
    with col1:
        universe_choice = st.selectbox(
            "Universe",
            ["NIFTY 50", "NIFTY 100", "NIFTY 200 (slower)"],
            index=0,
        )
    with col2:
        top_n = st.slider("Number of ideas", min_value=5, max_value=50, value=15, step=5)

    col_scan, col_sector = st.columns(2)
    with col_scan:
        run_scan = st.button("🔍 Scan Market", type="primary")
    with col_sector:
        run_sector = st.button("🏭 Sector Rotation", type="secondary")

    if run_scan:
        with st.spinner("Scanning intraday opportunities and fetching latest news…"):
            results = scan_intraday_momentum_stocks(
                universe=universe_choice,
                top_n=top_n,
            )

        if results is None or results.empty:
            st.warning("No intraday opportunities detected (or data not available).")
            return

        st.subheader("🏆 Top Momentum Candidates")
        st.caption(
            "Score = RSI (55-75) + Volume Spike + Price>VWAP + MACD + SMA trend + News sentiment. "
            "Profit Est% is ATR-based probability range — not a guarantee."
        )

        # ── Numbered styled cards ────────────────────────────────────────
        for rank, (_, row) in enumerate(results.iterrows(), start=1):
            score = row.get("Score", 0)
            trend = row.get("Trend", "Sideways")
            symbol = row.get("Symbol", "")
            change = row.get("Change%", 0)
            rsi = row.get("RSI", 0)
            close = row.get("Close (₹)", 0)
            news = row.get("Latest News", "—")
            profit_est = row.get("Profit Est%", "—")
            vol_spike = row.get("Vol Spike", "No")

            # Score badge color
            if score >= 6:
                score_color = "#1a7f37"  # strong green
                score_label = "🟢 Strong"
            elif score >= 4:
                score_color = "#b45309"  # amber
                score_label = "🟡 Moderate"
            else:
                score_color = "#b91c1c"  # red
                score_label = "🔴 Weak"

            # Trend badge
            trend_badge = {
                "Bullish": "🚀 Bullish",
                "Bearish": "📉 Bearish",
                "Sideways": "↔️ Sideways",
            }.get(trend, trend)

            trend_color = {
                "Bullish": "#3fb950",
                "Bearish": "#f85149",
                "Sideways": "#d29922",
            }.get(trend, "#8b949e")

            change_color = "#3fb950" if float(change) >= 0 else "#f85149"
            change_sign = "+" if float(change) >= 0 else ""

            with st.container():
                st.markdown(
                    f"""
                    <div style="
                        background: #161b22;
                        border: 1px solid #30363d;
                        border-left: 4px solid {score_color};
                        border-radius: 10px;
                        padding: 12px 16px;
                        margin-bottom: 8px;
                    ">
                        <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:6px;">
                            <div>
                                <span style="color:#8b949e; font-size:0.72rem; font-weight:700;">#{rank}</span>&nbsp;
                                <span style="color:#e6edf3; font-size:0.95rem; font-weight:700;">{symbol}</span>
                                &nbsp;<span style="background:{trend_color}22; color:{trend_color}; font-size:0.68rem; padding:2px 7px; border-radius:20px; border:1px solid {trend_color}66;">{trend_badge}</span>
                            </div>
                            <div style="display:flex; gap:10px; flex-wrap:wrap;">
                                <span style="background:{score_color}22; color:{score_color}; padding:2px 8px; border-radius:6px; font-weight:700; font-size:0.78rem; border:1px solid {score_color}55;">Score {score:.1f} &nbsp;{score_label}</span>
                                <span style="color:{change_color}; font-weight:700; font-size:0.84rem;">{change_sign}{change:.2f}%</span>
                            </div>
                        </div>
                        <div style="margin-top:8px; display:flex; gap:20px; flex-wrap:wrap;">
                            <span style="color:#8b949e; font-size:0.76rem;">&#x1F4B0; <b style="color:#c9d1d9;">&#x20B9;{close:.2f}</b></span>
                            <span style="color:#8b949e; font-size:0.76rem;">&#x1F4CA; RSI <b style="color:#c9d1d9;">{rsi:.1f}</b></span>
                            <span style="color:#8b949e; font-size:0.76rem;">&#x1F4C8; Profit Est <b style="color:#58a6ff;">{profit_est}</b></span>
                            <span style="color:#8b949e; font-size:0.76rem;">&#x26A1; Vol Spike <b style="color:#c9d1d9;">{vol_spike}</b></span>
                        </div>
                        {"" if news == "—" else f'<div style="margin-top:6px; color:#8b949e; font-size:0.71rem;">&#x1F4F0; <i>{news}</i></div>'}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        st.markdown("---")

        # ── Score bar chart ─────────────────────────────────────────────
        st.subheader("📊 Momentum Score Comparison")
        fig_bar = go.Figure(
            go.Bar(
                x=[r["Symbol"] for _, r in results.iterrows()],
                y=results["Score"],
                marker_color=[
                    "#26a69a" if s >= 6 else ("#ffa726" if s >= 4 else "#ef5350")
                    for s in results["Score"]
                ],
                text=results["Score"],
                textposition="outside",
            )
        )
        fig_bar.update_layout(
            height=340,
            margin=dict(l=10, r=10, t=10, b=80),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            dragmode=False,
            xaxis=dict(tickangle=-45, tickfont=dict(size=9), color="#8b949e"),
            yaxis=dict(title="Score", gridcolor="rgba(128,128,128,0.15)", color="#8b949e"),
        )
        st.plotly_chart(fig_bar, use_container_width=True, config={"scrollZoom": False, "displayModeBar": False})

        # Sector breakdown
        if "Sector" in results.columns:
            sector_view = (
                results.groupby("Sector")["Score"]
                .mean()
                .sort_values(ascending=False)
                .reset_index()
            )
            st.subheader("🏭 Sector Strength (avg momentum score)")
            fig_sector = go.Figure(
                go.Bar(
                    x=sector_view["Sector"],
                    y=sector_view["Score"],
                    marker_color="#42a5f5",
                    text=sector_view["Score"].round(2),
                    textposition="outside",
                )
            )
            fig_sector.update_layout(
                height=280,
                margin=dict(l=10, r=10, t=10, b=40),
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                dragmode=False,
                xaxis=dict(color="#8b949e"),
                yaxis=dict(color="#8b949e"),
            )
            st.plotly_chart(fig_sector, use_container_width=True, config={"scrollZoom": False, "displayModeBar": False})

        st.caption(
            "Signals combine: RSI momentum, volume spikes, Price vs VWAP, MACD histogram, "
            "SMA20/50 crossover, news sentiment, and 5-day weekly trend. "
            "Always validate on your broker charts before trading."
        )

    if run_sector:
        with st.spinner("Computing sector rotation (5-day performance)…"):
            sector_data = compute_sector_rotation(universe=universe_choice)

        if sector_data is None or sector_data.empty:
            st.warning("Could not compute sector rotation data.")
            return

        st.subheader("🔄 Sector Rotation — 5-Day Average Return")
        colors = [
            "#26a69a" if v >= 0 else "#ef5350"
            for v in sector_data["Avg 5-day Return %"]
        ]
        fig_rot = go.Figure(
            go.Bar(
                x=sector_data["Sector"],
                y=sector_data["Avg 5-day Return %"],
                marker_color=colors,
                text=[f"{v:.1f}%" for v in sector_data["Avg 5-day Return %"]],
                textposition="outside",
            )
        )
        fig_rot.update_layout(
            height=380,
            margin=dict(l=10, r=10, t=20, b=60),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            dragmode=False,
            xaxis=dict(tickangle=-30, color="#8b949e"),
            yaxis=dict(
                title="Avg 5-day Return %",
                gridcolor="rgba(128,128,128,0.15)",
                zeroline=True,
                zerolinecolor="rgba(255,255,255,0.3)",
                color="#8b949e",
            ),
        )
        st.plotly_chart(fig_rot, use_container_width=True, config={"scrollZoom": False, "displayModeBar": False})
        st.dataframe(sector_data.reset_index(drop=True), use_container_width=True)
        st.caption("Sector rotation is based on average 5-day price change of stocks in the selected universe.")
