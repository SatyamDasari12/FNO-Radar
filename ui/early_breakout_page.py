import os
from datetime import datetime
import pytz
from utils.logging import logger

import plotly.graph_objs as go
import streamlit as st

from services.early_breakout_service import scan_early_breakouts
from services.shortterm_scanner_service import fetch_india_vix

IST = pytz.timezone("Asia/Kolkata")


def _now_ist() -> str:
    return datetime.now(IST).strftime("%d %b %Y, %I:%M %p IST")


def _score_color(score: float) -> str:
    if score >= 75:
        return "#1a7f37"  # strong green
    elif score >= 55:
        return "#2ea043"  # moderate green
    elif score >= 40:
        return "#b45309"  # amber
    else:
        return "#b91c1c"  # red


def _render_pattern_chart(symbol: str, chart_df_dict: dict, pattern_data: dict) -> None:
    import pandas as pd
    df = pd.DataFrame.from_dict(chart_df_dict, orient='index')
    df.index = pd.to_datetime(df.index)
    
    fig = go.Figure()
    
    # Candlestick
    fig.add_trace(go.Candlestick(
        x=df.index,
        open=df['Open'],
        high=df['High'],
        low=df['Low'],
        close=df['Close'],
        name='Price'
    ))
    
    valid_dates = df.index.strftime('%Y-%m-%d').tolist()
    
    # Valleys (Green O)
    valleys_in_range = [v for v in pattern_data.get('valleys', []) if v in valid_dates]
    if valleys_in_range:
        valley_prices = df.loc[valleys_in_range, 'Low'] * 0.98
        fig.add_trace(go.Scatter(
            x=valleys_in_range,
            y=valley_prices,
            mode='markers',
            marker=dict(color='#3fb950', size=8, symbol='circle-open', line=dict(width=2)),
            name='Valleys'
        ))
        
    # Peaks (Red X)
    peaks_in_range = [p for p in pattern_data.get('peaks', []) if p in valid_dates]
    if peaks_in_range:
        peak_prices = df.loc[peaks_in_range, 'High'] * 1.02
        fig.add_trace(go.Scatter(
            x=peaks_in_range,
            y=peak_prices,
            mode='markers',
            marker=dict(color='#f85149', size=8, symbol='x', line=dict(width=2)),
            name='Peaks'
        ))
        
    # Draw Patterns
    colors = ['#58a6ff', '#f59e0b', '#a371f7']
    for i, pattern in enumerate(pattern_data.get('patterns', [])):
        pts = pattern['points']
        if all(pt['date'] in valid_dates for pt in pts):
            x_vals = [pt['date'] for pt in pts]
            y_vals = [pt['price'] for pt in pts]
            color = colors[i % len(colors)]
            
            fig.add_trace(go.Scatter(
                x=x_vals,
                y=y_vals,
                mode='lines+markers',
                line=dict(color=color, width=3, dash='dot'),
                marker=dict(size=6, color=color),
                name=f"{pattern['type']}"
            ))
            
    fig.update_layout(
        yaxis_title="Price (₹)",
        xaxis_rangeslider_visible=False,
        height=400,
        margin=dict(l=10, r=10, t=30, b=10),
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#c9d1d9"),
        xaxis=dict(gridcolor="rgba(128,128,128,0.15)"),
        yaxis=dict(gridcolor="rgba(128,128,128,0.15)"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def render_early_breakout_page() -> None:
    st.title("🚀 Early Breakout Scanner")
    st.caption(
        f"Identify pre-breakout consolidations, Bollinger squeezes, and early momentum shifts | {_now_ist()}"
    )

    col1, col2, col3 = st.columns([1.5, 1.5, 1])
    with col1:
        universe_choice = st.selectbox(
            "Stock Universe",
            ["F&O Only", "Nifty Largecap 100", "Nifty Midcap 200", "Nifty Smallcap 200", "Nifty Microcap 250"],
            index=0,
            help="Select which index universe to scan for early breakouts."
        )
    with col2:
        top_n = st.slider(
            "Max Candidates to Display",
            min_value=5,
            max_value=30,
            value=15,
            step=5,
        )
    
    with col3:
        vix_val = fetch_india_vix()
        if vix_val < 15:
            vix_desc = "🟢 Low Volatility (Breakouts Favored)"
            vix_border = "#1a7f37"
        elif vix_val <= 20:
            vix_desc = "🟡 Elevated Volatility (Be Selective)"
            vix_border = "#b45309"
        else:
            vix_desc = "🔴 High Volatility (Trap Risk)"
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

    run_scan = st.button("🚀 Run Early Breakout Scan", type="primary", use_container_width=True)

    if run_scan:
        progress_text = st.empty()
        progress_bar = st.progress(0.0)
        
        def update_progress(current: int, total: int, symbol: str):
            pct = current / total
            progress_bar.progress(pct)
            progress_text.markdown(f"⏳ **Scanning {current}/{total}:** `{symbol}`...")

        with st.spinner("Analyzing volume accumulation, volatility squeeze, and sector phases..."):
            results = scan_early_breakouts(
                universe=universe_choice,
                top_n=top_n,
                progress_callback=update_progress
            )
            
        progress_text.empty()
        progress_bar.empty()

        if results is None or results.empty:
            st.warning("No stocks matched the early breakout criteria currently.")
            return

        st.subheader(f"🏆 Top Ranked {universe_choice} Pre-Breakout Candidates")
        st.caption(
            "Ranking based on Volatility Squeeze (25%), Volume Expansion (25%), Early Momentum (20%), Oscillators (15%), and Sector/RS (15%)."
        )

        for rank, (_, row) in enumerate(results.iterrows(), start=1):
            score = row.get("Score", 0)
            symbol = row.get("Symbol", "")
            sector = row.get("Sector", "Other")
            sector_phase = row.get("Sector Phase", "Unknown")
            close = row.get("Close (₹)", 0.0)
            tags = row.get("Tags", "Neutral")
            
            stop_loss = row.get("Stop Loss (₹)", 0.0)
            target1 = row.get("Target 1 (₹)", 0.0)
            target2 = row.get("Target 2 (₹)", 0.0)
            rr_ratio = row.get("R:R Ratio", 0.0)
            chart_df_dict = row.get("Chart_DF", {})
            pattern_data = row.get("Pattern_Data", {})
            option_rec = row.get("Option_Rec")
            
            score_bg = _score_color(score)
            rr_color = "#3fb950" if rr_ratio >= 2.0 else "#f59e0b" if rr_ratio >= 1.5 else "#f85149"
            
            phase_color = "#3fb950" if sector_phase == "Leading" else "#a371f7" if sector_phase == "Improving" else "#f85149" if sector_phase == "Lagging" else "#8b949e"
            
            border_style = f"border-left: 5px solid {score_bg}; border: 1px solid #30363d;"
            
            html_str = f"""<div style="background:#161b22; {border_style} border-radius:10px; padding:14px 18px; margin-bottom:10px;">
<div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
<div>
<span style="color:#8b949e; font-size:0.75rem; font-weight:700;">#{rank}</span>&nbsp;
<span style="color:#e6edf3; font-size:1.05rem; font-weight:800;">{symbol}</span>
&nbsp;<span style="color:#8b949e; font-size:0.75rem;">({sector})</span>
&nbsp;<span style="background:{phase_color}22; color:{phase_color}; font-size:0.68rem; padding:2px 7px; border-radius:20px; font-weight:700;">Sector: {sector_phase}</span>
</div>
<div style="display:flex; gap:10px; align-items:center;">
<span style="background:{score_bg}22; color:{score_bg}; padding:3px 8px; border-radius:6px; font-weight:800; font-size:0.8rem; border:1px solid {score_bg}55;">Score: {score:.1f}</span>
<span style="color:#e6edf3; font-weight:800; font-size:0.9rem;">₹{close:.2f}</span>
</div>
</div>
<div style="margin-top:10px; border-top:1px solid #21262d; padding-top:8px;">
<div style="display:flex; gap:18px; flex-wrap:wrap; margin-bottom:6px;">
<span style="color:#8b949e; font-size:0.78rem;">SL: <b style="color:#f85149;">₹{stop_loss:.2f}</b></span>
<span style="color:#8b949e; font-size:0.78rem;">Target 1: <b style="color:#3fb950;">₹{target1:.2f}</b></span>
<span style="color:#8b949e; font-size:0.78rem;">Target 2: <b style="color:#58a6ff;">₹{target2:.2f}</b></span>
<span style="color:#8b949e; font-size:0.78rem;">R:R Ratio <b style="color:{rr_color};">{rr_ratio:.1f}</b></span>
</div>
<div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px; font-size:0.76rem;">
<span style="color:#8b949e;">Signals: <b style="color:#c9d1d9;">{tags}</b></span>
</div>
</div>
"""
            if option_rec:
                opt_contract = option_rec.get("Contract")
                opt_premium = option_rec.get("Premium", 0.0)
                opt_moneyness = option_rec.get("Moneyness", "")
                opt_delta = option_rec.get("Delta", 0.0)
                opt_theta = option_rec.get("Theta_Pct", 0.0)
                opt_rr = option_rec.get("RR_Ratio", 0.0)
                opt_warning = option_rec.get("Warning")
                
                warning_html = ""
                if opt_warning:
                    warning_html = f"""<div style="margin-top:8px; padding:6px 10px; background-color:rgba(185, 28, 28, 0.15); border: 1px solid #b91c1c; border-radius:4px; font-size:0.75rem; color:#ff7b72; font-weight:600;">
⚠️ <b>Warning:</b> {opt_warning} (Consider risk before trading)
</div>"""
                
                html_str += f"""
<div style="margin-top:10px; background:#1c2128; border:1px solid #30363d; border-radius:6px; padding:10px; display:flex; justify-content:space-between; flex-wrap:wrap; align-items:center; gap:10px;">
    <div>
        <span style="font-size:0.65rem; color:#8b949e; text-transform:uppercase; font-weight:700;">Suggested Trade ({opt_moneyness})</span><br>
        <span style="font-size:0.95rem; font-weight:800; color:#58a6ff;">{opt_contract}</span>
    </div>
    <div style="display:flex; gap:15px; align-items:center;">
        <div>
            <span style="font-size:0.65rem; color:#8b949e; text-transform:uppercase; font-weight:700;">Premium</span><br>
            <span style="font-size:0.9rem; font-weight:700; color:#e6edf3;">₹{opt_premium:.2f}</span>
        </div>
        <div>
            <span style="font-size:0.65rem; color:#8b949e; text-transform:uppercase; font-weight:700;">Delta</span><br>
            <span style="font-size:0.9rem; font-weight:700; color:#e6edf3;">{opt_delta:.2f}</span>
        </div>
        <div>
            <span style="font-size:0.65rem; color:#8b949e; text-transform:uppercase; font-weight:700;">Theta Decay</span><br>
            <span style="font-size:0.9rem; font-weight:700; color:#f85149;">-{opt_theta:.1f}%/d</span>
        </div>
        <div>
            <span style="font-size:0.65rem; color:#8b949e; text-transform:uppercase; font-weight:700;">Opt R:R</span><br>
            <span style="font-size:0.9rem; font-weight:700; color:#3fb950;">{opt_rr:.1f}</span>
        </div>
    </div>
</div>
{warning_html}
"""
            
            html_str += "</div>"
            st.markdown(html_str, unsafe_allow_html=True)
            
            if chart_df_dict and pattern_data:
                with st.expander(f"📈 View Chart & Patterns for {symbol}"):
                    _render_pattern_chart(symbol, chart_df_dict, pattern_data)

        st.markdown("---")
