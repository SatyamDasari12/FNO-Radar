"""
Options Scanner Page — Advanced F&O Options Scanner
===================================================
Displays the 7-factor composite score with per-factor breakdown,
hard filter status, Greeks (Delta/Theta), Reward/Risk ratio,
current premium (Live LTP or BS), target price, expected premium,
and estimated profit. Supporting both Call and Put strategies.
"""
from __future__ import annotations

from datetime import datetime

import plotly.graph_objs as go
import pytz
import streamlit as st

from services.options_service import (
    get_fno_stock_list,
    get_month_options,
    scan_fno_options_for_month as scan_fno_calls_for_month,
)
import services.put_options_service as put_service
from services.llm_service import explain_option_contract

IST = pytz.timezone("Asia/Kolkata")


def _now_ist() -> str:
    return datetime.now(IST).strftime("%d %b %Y, %I:%M %p IST")


def _trend_color(score: float) -> str:
    """Color based on final score 0-100."""
    if score >= 65: return "#1a7f37"
    if score >= 45: return "#b45309"
    return "#b91c1c"


def _score_label(score: float) -> str:
    if score >= 65: return "🟢 Strong"
    if score >= 45: return "🟡 Moderate"
    return "🔴 Weak"


def _src_badge(src: str) -> str:
    if src == "NSE Live": return "🟢 NSE Live (Market)"
    if src == "NSE Close": return "🔵 NSE Close (YF)"
    return "⚪ Computed EOD"


def _src_color(src: str) -> str:
    if src == "NSE Live": return "#3fb950"
    if src == "NSE Close": return "#58a6ff"
    return "#8b949e"


def _pct_bar(val: float, max_val: float = 100.0, color: str = "#58a6ff") -> str:
    """Inline mini progress bar as HTML."""
    pct = min(max(val / max_val * 100, 0), 100)
    return (
        f'<div style="background:#21262d;border-radius:4px;height:6px;margin-top:3px;">'
        f'<div style="background:{color};width:{pct:.0f}%;height:100%;border-radius:4px;"></div>'
        f'</div>'
    )


def render_options_scanner_page() -> None:
    st.title("📊 Advanced F&O Options Scanner")
    st.caption(
        f"NSE F&O Options Strategy · 7-Factor Composite Score · "
        f"Delta-Optimal Strike Selection | {_now_ist()}"
    )

    # ── Controls ──────────────────────────────────────────────────────────
    c_strat, c1, c2, c3 = st.columns([1.5, 1.5, 1, 1])

    with c_strat:
        strategy_mode = st.selectbox(
            "Strategy Mode",
            options=["Call Buying Strategy", "Put Buying Strategy"],
            index=0,
            help="Select whether to scan for bullish Call options or bearish Put options.",
        )

    # ── Strategy Overview ─────────────────────────────────────────────────
    if strategy_mode == "Call Buying Strategy":
        with st.expander("📖 Strategy Overview — NSE F&O Advanced Call Buying", expanded=False):
            st.markdown("""
### 🎯 Objective
Select high-probability CALL option trades across 200+ NSE F&O stocks.
Focus on **short-term bullish acceleration** with controlled Theta and IV risk.
**Holding Period: 3–7 trading days.**

---

### Layer 1 — Hard Filters (Pre-Qualification)
All conditions must be satisfied:
| Condition | Rule |
|-----------|------|
| Trend | Close **>** 20 DMA |
| Volume | Today ≥ **1.2×** 20-day average |
| ATR | ATR(14)/Price ≥ **1.5%** |
| 3-day cap | Price gain ≤ **8%** (avoid chasing) |
| IV Range | IV Rank ∈ [25, 65] |

---

### Layer 2 — 7-Factor Normalized Scoring (0–100 each)

| Factor | Formula | Weight |
|--------|---------|--------|
| **A. Momentum** | `((Close/Close_5d) - 1) × 100`, then `×5` capped at 100 | **25%** |
| **B. Breakout** | 100 if Close > Highest High(10 days), else 0 | **15%** |
| **C. Volume Expansion** | `min(100, (Today Vol / 20d Avg) × 50)` | **15%** |
| **D. OI Long Buildup** | Price ↑ + Volume↑ proxy (live OI unavailable from API) | **15%** |
| **E. RSI Zone** | 45–65 → 100, 65–72 → 60, >72 → 20, else → 40 | **10%** |
| **F. IV Sweet Spot** | Rank 30–60 → 100, 20–30/60–70 → 60, else → 20 | **10%** |
| **G. Nifty Alignment** | NIFTY50 > its 20 DMA → 100, else 40 | **10%** |

**Bonus:** +5 pts if Stock 10d return > NIFTY50 10d return (Relative Strength)

---

### Layer 4 — Contract Selection Rules
- **Delta**: 0.40 ≤ Δ ≤ 0.55 (sweet spot between time value and intrinsic)
- **Theta**: Daily theta ≤ 0.5% of premium
- **Reward/Risk**: `(Target Move × Delta) / (Premium × 0.30)` ≥ **1.8**

---

### Layer 5 — Exit Signals (shown per contract)
1. Stock closes below 5 EMA
2. Momentum Score < 50
3. Option premium drops 30%
4. 5 trading days completed

> ⚠️ *Live NSE option LTP used when market is open; Black-Scholes fair value otherwise.*
            """)
    else:
        with st.expander("📖 Strategy Overview — NSE F&O Advanced Put Buying", expanded=False):
            st.markdown("""
### 🎯 Objective
Select high-probability PUT option trades across 200+ NSE F&O stocks.
Focus on **short-term bearish acceleration** with controlled Theta and IV risk.
**Holding Period: 3–7 trading days.**

---

### Layer 1 — Hard Filters (Pre-Qualification)
All conditions must be satisfied:
| Condition | Rule |
|-----------|------|
| Trend | Close **<** 20 DMA |
| Volume | Today ≥ **1.2×** 20-day average |
| ATR | ATR(14)/Price ≥ **1.5%** |
| 3-day cap | Price loss ≤ **8%** (3d return ≥ -8%) |
| IV Range | IV Rank ≤ **40** (cheap volatility filter) |

---

### Layer 2 — 7-Factor Normalized Scoring (0–100 each)

| Factor | Formula | Weight |
|--------|---------|--------|
| **A. Momentum** | `(1 - Close/Close_5d) × 100`, then `×5` capped at 100 | **25%** |
| **B. Breakout** | 100 if Close < Lowest Low(10 days), else 0 | **15%** |
| **C. Volume Expansion** | `min(100, (Today Vol / 20d Avg) × 50)` | **15%** |
| **D. OI Short Buildup** | Price ↓ + Volume↑ proxy (live OI unavailable from API) | **15%** |
| **E. RSI Zone** | 35–55 or rollover from >70 → 100, 28–35 → 60, <28 → 20, else → 40 | **10%** |
| **F. IV Sweet Spot** | Rank ≤ 40 → 100, 40-55 → 60, else → 20 | **10%** |
| **G. Nifty Alignment** | NIFTY50 < its 20 DMA → 100, else 40 | **10%** |

**Bonus:** +5 pts if Stock 10d return < NIFTY50 10d return (Relative Weakness)

---

### Layer 4 — Contract Selection Rules
- **Delta**: -0.55 ≤ Δ ≤ -0.40 (sweet spot between time value and intrinsic)
- **Theta**: Daily theta ≤ 0.5% of premium
- **Reward/Risk**: `(Target Move × |Delta|) / (Premium × 0.30)` ≥ **1.8**

---

### Layer 5 — Exit Signals (shown per contract)
1. Stock closes above 5 EMA (bearish trend broken)
2. Momentum Score < 50
3. Option premium drops 30%
4. 5 trading days completed

> ⚠️ *Live NSE option LTP used when market is open; Black-Scholes fair value otherwise.*
            """)

    month_opts = get_month_options()
    month_labels = [m[0] for m in month_opts]

    with c1:
        selected_month_label = st.selectbox(
            "Expiry Month",
            options=month_labels,
            index=0,
            help="Each stock's actual expiry within this month is resolved automatically per its NSE option calendar.",
        )

    sel = next((m for m in month_opts if m[0] == selected_month_label), None)
    sel_year = sel[1] if sel else datetime.now().year
    sel_month = sel[2] if sel else datetime.now().month

    with c2:
        top_n = st.slider("Top results (strategy: 5)", 3, 20, 5, 1)

    with c3:
        min_score = st.slider("Min Score (0-100)", 20, 80, 45, 5,
                              help="Minimum composite score. Strategy recommends ≥45.")

    try:
        fno_count = len(get_fno_stock_list())
        st.caption(
            f"📋 Scanning **{fno_count}** F&O stocks through Hard Filters → 7-Factor Score → "
            f"Delta/Theta/R-R Contract Selection | Expiry: **{selected_month_label}**"
        )
    except Exception:
        pass

    if st.button("🔍 Run Advanced Strategy Scan", type="primary"):
        with st.spinner(
            f"Running 6-Layer Strategy Scan for {selected_month_label}…  "
            "(60–120 seconds)"
        ):
            if strategy_mode == "Call Buying Strategy":
                df = scan_fno_calls_for_month(
                    year=sel_year,
                    month=sel_month,
                    top_n=top_n,
                    min_score=float(min_score),
                )
            else:
                df = put_service.scan_fno_options_for_month(
                    year=sel_year,
                    month=sel_month,
                    top_n=top_n,
                    min_score=float(min_score),
                )
            st.session_state["options_scan_results"] = df
            st.session_state["options_scan_mode"] = strategy_mode

    df = st.session_state.get("options_scan_results")
    scan_mode = st.session_state.get("options_scan_mode", "Call Buying Strategy")

    if df is not None:
        if df.empty:
            st.warning(
                f"No stocks passed the strategy filters for **{selected_month_label}**. "
                "Try lowering Min Score or selecting a future month."
            )
            return

        st.success(
            f"✅ **{len(df)}** top candidates selected from {len(get_fno_stock_list())} F&O stocks | "
            f"{_now_ist()}"
        )
        st.markdown("---")

        # ── Ranked Cards ──────────────────────────────────────────────────
        st.subheader("🏆 Top Option Contracts (Strategy-Selected)")

        for rank, (_, row) in enumerate(df.iterrows(), start=1):
            contract   = row.get("Contract", "")
            sym        = row.get("Symbol", "")
            company    = row.get("Company", sym)
            expiry     = row.get("Expiry", "—")
            days_left  = int(row.get("Days to Expiry", 0))
            src        = row.get("Price Source", "BS Model")
            strike_type = row.get("Strike Type", "ATM")
            strike_rule = row.get("Strike Rule", "ATM (default)")
            spot       = float(row.get("Underlying Spot (₹)", 0))
            strike     = float(row.get("Strike (₹)", 0))
            moneyness  = float(row.get("Moneyness%", 0))
            cur_prem   = float(row.get("Current Premium (₹)", 0))
            bs_val     = float(row.get("BS Fair Value (₹)", 0))
            lot        = row.get("Lot Size", "—")
            invest     = float(row.get("Investment / Lot (₹)", 0))
            target     = float(row.get("Target Spot Price (₹)", 0))
            exp_prem   = float(row.get("Expected Premium @ Target (₹)", 0))
            profit     = float(row.get("Est Profit / Lot (₹)", 0))
            ret_pct    = float(row.get("Return%", 0))
            delta_v    = float(row.get("Delta", 0))
            theta_v    = float(row.get("Daily Theta (₹)", 0))
            theta_pct  = float(row.get("Theta % of Premium", 0))
            rr         = float(row.get("Reward/Risk Ratio", 0))
            theta_ok   = row.get("Theta OK", "—")
            rr_ok      = row.get("R/R OK", "—")
            final_sc   = float(row.get("Final Score (0-100)", 0))
            sc_a       = float(row.get("A Momentum (25%)", 0))
            sc_b       = float(row.get("B Breakout (15%)", 0))
            sc_c       = float(row.get("C Volume (15%)", 0))
            sc_d       = float(row.get("D OI (15%)", 0))
            sc_e       = float(row.get("E RSI (10%)", 0))
            sc_f       = float(row.get("F IV (10%)", 0))
            sc_g       = float(row.get("G Nifty (10%)", 0))
            rs_bonus   = float(row.get("RS Bonus", 0))
            rs_10d     = float(row.get("RS vs Nifty 10d%", 0))
            rsi_v      = float(row.get("RSI", 50))
            iv_rank    = float(row.get("IV Rank", 50))
            atr_v      = float(row.get("ATR (₹)", 0))
            vol_str    = row.get("Volatility (σ)", "—")
            mom_pct    = float(row.get("Momentum%", 0))
            breakout   = row.get("Breakout", "—")
            vol_ratio  = float(row.get("Vol Ratio", 1))
            above_sma  = row.get("Above 20DMA", "—")
            below_sma  = row.get("Below 20DMA", "—")
            above_5ema = row.get("Above 5 EMA", "—")
            atr_flag   = row.get("ATR% ≥ 1.5", "—")
            iv_range   = row.get("IV Range OK", "—")
            gain3_call = row.get("3d Gain ≤ 8%", "—")
            gain3_put  = row.get("3d Gain ≥ -8", "—")
            exit_sigs  = row.get("Exit Signals", "None")
            news_score = float(row.get("News Score", 0))
            news_head  = row.get("Latest News", "—")
            corp_action = row.get("Corporate Action", "None")

            bcolor = _trend_color(final_sc)
            pc = "#3fb950" if profit >= 0 else "#f85149"
            sc_src = _src_color(src)
            rs_color = "#3fb950" if (rs_10d > 0 if scan_mode == "Call Buying Strategy" else rs_10d < 0) else "#f85149"
            
            is_straddle = row.get("Straddle Opportunity", False)
            hedge_contract = row.get("Hedge Contract", "—")
            hedge_premium = float(row.get("Hedge Premium (₹)", 0.0))
            hedge_invest = hedge_premium * (int(lot) if str(lot).isdigit() else 0)

            
            if scan_mode == "Call Buying Strategy":
                moneyness_label = f"+{moneyness:.1f}% OTM" if moneyness > 0 else f"{abs(moneyness):.1f}% ITM"
            else:
                moneyness_label = f"+{moneyness:.1f}% ITM" if moneyness > 0 else f"{abs(moneyness):.1f}% OTM"
                
            news_color = "#3fb950" if news_score > 0.3 else ("#f85149" if news_score < -0.3 else "#8b949e")

            # Strike type badge style
            if strike_type.startswith("OTM"):
                st_color  = "#f59e0b"   # amber — aggressive
                st_icon   = "🚀"
            elif strike_type.startswith("ITM"):
                st_color  = "#14b8a6"   # teal — conservative
                st_icon   = "🛡️"
            else:
                st_color  = "#58a6ff"   # blue — default
                st_icon   = "🎯"

            # ── Clickable expander: the contract name IS the expand toggle ──────
            with st.container():
                _profit_sign = "+" if profit >= 0 else ""
                straddle_badge = "🔥 STRADDLE SETUP" if is_straddle else ""
                _expander_label = (
                    f"#{rank}  ·  **{contract}**  ·  {company}  {straddle_badge}  "
                    f"|  {_score_label(final_sc)} {final_sc:.1f}/100  "
                    f"|  {st_icon} {strike_type}  "
                    f"|  📅 {expiry} ({days_left}d)  "
                    f"|  📍 {moneyness_label}  "
                    f"|  Est ₹{_profit_sign}{abs(profit):,.0f} ({ret_pct:+.1f}%)"
                )
                with st.expander(_expander_label, expanded=False):

                    sma_check_label = "Close&gt;20DMA" if scan_mode == "Call Buying Strategy" else "Close&lt;20DMA"
                    sma_check_val = above_sma if scan_mode == "Call Buying Strategy" else below_sma

                    gain3_label = "3d Gain≤8%" if scan_mode == "Call Buying Strategy" else "3d Gain≥-8%"
                    gain3_val = gain3_call if scan_mode == "Call Buying Strategy" else gain3_put

                    # Full detail HTML card
                    st.markdown(f"""
<div style="
    background:linear-gradient(135deg,#0d1117 0%,#161b22 100%);
    border:1px solid #21262d;
    border-radius:12px;
    padding:16px 20px;
">
  <!-- Strike Rule -->
  <div style="margin-bottom:6px;color:{st_color};font-size:0.66rem;font-style:italic;opacity:0.85;">
    Strike Rule: {strike_rule}
  </div>

  <!-- Hard Filter Row -->
  <div style="display:flex;gap:10px;flex-wrap:wrap;background:#010409;
              padding:6px 12px;border-radius:8px;border:1px solid #21262d;">
    <span style="font-size:0.68rem;color:#8b949e;">Hard Filters:</span>
    <span style="font-size:0.68rem;">{sma_check_label} {sma_check_val}</span>
    <span style="font-size:0.68rem;">ATR≥1.5% {atr_flag}</span>
    <span style="font-size:0.68rem;">{gain3_label} {gain3_val}</span>
    <span style="font-size:0.68rem;">IV Range {iv_range}</span>
    <span style="font-size:0.68rem;">Above 5EMA {above_5ema}</span>
  </div>


  <!-- 7-Factor Score Bars -->
  <div style="margin-top:10px;display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:6px;">
    <div>
      <div style="color:#8b949e;font-size:0.62rem;">A. Momentum <b style="color:#e6edf3;">{sc_a:.0f}</b><span style="color:#d29922;font-size:0.58rem;"> ×25%</span></div>
      {_pct_bar(sc_a, 100, "#58a6ff")}
    </div>
    <div>
      <div style="color:#8b949e;font-size:0.62rem;">B. Breakout <b style="color:#e6edf3;">{sc_b:.0f}</b><span style="color:#d29922;font-size:0.58rem;"> ×15%</span></div>
      {_pct_bar(sc_b, 100, "#26a69a")}
    </div>
    <div>
      <div style="color:#8b949e;font-size:0.62rem;">C. Volume <b style="color:#e6edf3;">{sc_c:.0f}</b><span style="color:#d29922;font-size:0.58rem;"> ×15%</span></div>
      {_pct_bar(sc_c, 100, "#7c3aed")}
    </div>
    <div>
      <div style="color:#8b949e;font-size:0.62rem;">D. OI Proxy <b style="color:#e6edf3;">{sc_d:.0f}</b><span style="color:#d29922;font-size:0.58rem;"> ×15%</span></div>
      {_pct_bar(sc_d, 100, "#f59e0b")}
    </div>
    <div>
      <div style="color:#8b949e;font-size:0.62rem;">E. RSI Zone <b style="color:#e6edf3;">{sc_e:.0f}</b><span style="color:#d29922;font-size:0.58rem;"> ×10%</span></div>
      {_pct_bar(sc_e, 100, "#ec4899")}
    </div>
    <div>
      <div style="color:#8b949e;font-size:0.62rem;">F. IV Spot <b style="color:#e6edf3;">{sc_f:.0f}</b><span style="color:#d29922;font-size:0.58rem;"> ×10%</span></div>
      {_pct_bar(sc_f, 100, "#14b8a6")}
    </div>
    <div>
      <div style="color:#8b949e;font-size:0.62rem;">G. Nifty <b style="color:#e6edf3;">{sc_g:.0f}</b><span style="color:#d29922;font-size:0.58rem;"> ×10%</span></div>
      {_pct_bar(sc_g, 100, "#84cc16")}
    </div>
    <div>
      <div style="color:#8b949e;font-size:0.62rem;">RS Bonus <b style="color:{rs_color};">{'+' if rs_10d>0 else ''}{rs_10d:.1f}% → {'+' if rs_bonus>0 else ''}{rs_bonus:.0f}pts</b></div>
      {_pct_bar(rs_bonus, 5, rs_color)}
    </div>
  </div>

  <!-- Greeks Row -->
  <div style="margin-top:8px;display:flex;gap:16px;flex-wrap:wrap;align-items:center;">
    <span style="color:#8b949e;font-size:0.74rem;">Δ Delta <b style="color:#58a6ff;">{delta_v:.3f}</b></span>
    <span style="color:#8b949e;font-size:0.74rem;">Θ Theta <b style="color:#f85149;">₹{theta_v:.3f}/day</b> ({theta_pct:.3f}%) {theta_ok}</span>
    <span style="color:#8b949e;font-size:0.74rem;">⚖️ R/R <b style="color:{'#3fb950' if rr>=1.8 else '#f85149'};">{rr:.2f}</b> {rr_ok}</span>
    <span style="color:#8b949e;font-size:0.74rem;">RSI <b style="color:{'#3fb950' if 45<=rsi_v<=65 else '#d29922'};">{rsi_v:.1f}</b></span>
    <span style="color:#8b949e;font-size:0.74rem;">IV Rank <b style="color:#c9d1d9;">{iv_rank:.1f}</b></span>
    <span style="color:#8b949e;font-size:0.74rem;">σ <b style="color:#c9d1d9;">{vol_str}</b></span>
    <span style="color:#8b949e;font-size:0.74rem;">5m% <b style="color:#c9d1d9;">{'+' if mom_pct>=0 else ''}{mom_pct:.2f}%</b></span>
    <span style="color:#8b949e;font-size:0.74rem;">Breakout {breakout}</span>
  </div>

  <!-- Corporate Actions -->
  {f'<div style="margin-top:10px; background-color:#3d1a11; border-left:4px solid #f85149; padding:8px 12px; border-radius:4px; color:#ff7b72; font-size:0.8rem; font-weight:600;">{corp_action}</div>' if corp_action and corp_action != 'None' else ''}

  <!-- News -->
  {f'<div style="margin-top:7px;color:#8b949e;font-size:0.76rem;border-left:2px solid {news_color};padding-left:8px;font-style:italic;">&#34;{news_head}&#34;</div>' if news_head and news_head != '—' else ''}

  <!-- Investment / Profit Box -->
  <div style="margin-top:12px;background:#010409;border:1px solid #21262d;border-radius:10px;
              padding:12px 18px;display:flex;gap:24px;flex-wrap:wrap;align-items:center;">
    <div style="text-align:center;min-width:120px;">
      <div style="color:#8b949e;font-size:0.68rem;text-transform:uppercase;letter-spacing:0.6px;">Current Premium</div>
      <div style="color:#e6edf3;font-size:1.05rem;font-weight:900;font-family:monospace;">₹{cur_prem:,.2f}</div>
      <div style="color:{sc_src};font-size:0.65rem;">{_src_badge(src)}</div>
      <div style="color:#484f58;font-size:0.64rem;">BS: ₹{bs_val:,.2f}</div>
    </div>
    <div style="text-align:center;min-width:65px;">
      <div style="color:#8b949e;font-size:0.68rem;text-transform:uppercase;letter-spacing:0.6px;">Lot Size</div>
      <div style="color:#e6edf3;font-size:1.05rem;font-weight:700;">{lot}</div>
    </div>
    <div style="text-align:center;min-width:120px;">
      <div style="color:#8b949e;font-size:0.68rem;text-transform:uppercase;letter-spacing:0.6px;">💰 Investment/Lot</div>
      <div style="color:#ffa726;font-size:1.15rem;font-weight:900;font-family:monospace;">₹{invest:,.0f}</div>
      <div style="color:#484f58;font-size:0.64rem;">₹{cur_prem:,.2f} × {lot}</div>
    </div>
    <div style="text-align:center;min-width:110px;">
      <div style="color:#8b949e;font-size:0.68rem;text-transform:uppercase;letter-spacing:0.6px;">📍 Current Price</div>
      <div style="color:#e6edf3;font-size:1.1rem;font-weight:800;font-family:monospace;">₹{spot:,.2f}</div>
    </div>
    <div style="text-align:center;min-width:110px;">
      <div style="color:#8b949e;font-size:0.68rem;text-transform:uppercase;letter-spacing:0.6px;">🎯 Target Price</div>
      <div style="color:#58a6ff;font-size:1.1rem;font-weight:800;font-family:monospace;">₹{target:,.2f}</div>
      <div style="color:#d29922;font-size:0.66rem;">needs {'+' if target>=spot else ''}{target-spot:+,.0f} ({(target-spot)/spot*100:+.1f}%)</div>
    </div>
    <div style="text-align:center;min-width:120px;">
      <div style="color:#8b949e;font-size:0.68rem;text-transform:uppercase;letter-spacing:0.6px;">Exp Premium @ Target</div>
      <div style="color:#c9d1d9;font-size:1.05rem;font-weight:700;font-family:monospace;">₹{exp_prem:,.2f}</div>
    </div>
    <div style="text-align:center;min-width:120px;">
      <div style="color:#8b949e;font-size:0.68rem;text-transform:uppercase;letter-spacing:0.6px;">📈 Est Profit/Lot</div>
      <div style="color:{pc};font-size:1.18rem;font-weight:900;font-family:monospace;">{'+' if profit>=0 else ''}₹{abs(profit):,.0f}</div>
      <div style="color:#484f58;font-size:0.64rem;">(₹{exp_prem:,.2f}−₹{cur_prem:,.2f})×{lot}</div>
    </div>
    <div style="text-align:center;min-width:80px;">
      <div style="color:#8b949e;font-size:0.68rem;text-transform:uppercase;letter-spacing:0.6px;">Return%</div>
      <div style="color:{pc};font-size:1.15rem;font-weight:900;">{'+' if ret_pct>=0 else ''}{ret_pct:.1f}%</div>
    </div>
  </div>

  <!-- Hedge & Risk Management Box -->
  <div style="margin-top:12px;background:#1a0f00;border:1px solid #663c00;border-radius:10px;
              padding:12px 18px;display:flex;gap:24px;flex-wrap:wrap;align-items:center;">
    <div style="text-align:left;flex-grow:1;">
      <div style="color:#d29922;font-size:0.75rem;text-transform:uppercase;letter-spacing:0.6px;font-weight:700;">🛡️ Recommended Risk Reduction (Hedge)</div>
      <div style="color:#e6edf3;font-size:0.85rem;margin-top:4px;">Buy <b>{hedge_contract}</b> at ~₹{hedge_premium:,.2f}</div>
      <div style="color:#8b949e;font-size:0.75rem;">Hedge Investment: ₹{hedge_invest:,.0f} per lot</div>
    </div>
    {f'''<div style="text-align:right;border-left:1px solid #663c00;padding-left:16px;">
<div style="color:#f85149;font-size:0.85rem;font-weight:800;text-transform:uppercase;">🔥 Straddle Alert</div>
<div style="color:#ff7b72;font-size:0.75rem;margin-top:2px;">Volatility Squeeze + Upcoming Catalyst</div>
<div style="color:#e6edf3;font-size:0.75rem;">Buying BOTH {contract} and {hedge_contract} can yield massive profits</div>
</div>''' if is_straddle else ''}
  </div>

  <!-- Exit Signals -->
  <div style="margin-top:6px;display:flex;gap:6px;align-items:center;flex-wrap:wrap;">
    <span style="color:#8b949e;font-size:0.64rem;">Exit Signals:</span>
    <span style="color:{'#f85149' if exit_sigs!='None' else '#3fb950'};font-size:0.64rem;">{exit_sigs}</span>
  </div>
</div>
""", unsafe_allow_html=True)

                    # ── AI Analysis section ───────────────────────────────────
                    st.markdown("---")
                    st.markdown("#### 🤖 AI Analysis & Trend Summary")

                    _ai_key = f"_opt_ai_{contract}"
                    if _ai_key not in st.session_state:
                        st.session_state[_ai_key] = None

                    if st.session_state[_ai_key] is None:
                        if st.button(
                            "✨ Summarize",
                            key=f"_btn_ai_{contract}",
                            type="primary",
                            use_container_width=False,
                        ):
                            with st.spinner("Asking AI analyst…"):
                                st.session_state[_ai_key] = explain_option_contract(dict(row))
                            st.rerun()
                    else:
                        st.markdown(
                            "<div style='background:#0d1117;border:1px solid #21262d;"
                            "border-left:4px solid #58a6ff;border-radius:10px;"
                            "padding:14px 18px;font-size:0.88rem;color:#c9d1d9;"
                            "white-space:pre-wrap;line-height:1.65;'>"
                            + st.session_state[_ai_key].replace("<", "&lt;").replace(">", "&gt;")
                            + "</div>",
                            unsafe_allow_html=True,
                        )
                        if st.button(
                            "🔄 Refresh AI",
                            key=f"_btn_refresh_{contract}",
                            use_container_width=False,
                        ):
                            st.session_state[_ai_key] = None
                            st.rerun()

            st.markdown("<div style='margin-bottom:6px;'></div>", unsafe_allow_html=True)






        # ── Score Radar / Bar Chart ───────────────────────────────────────
        st.subheader("📊 Composite Score Breakdown")

        # Stacked bar chart of the 7 factors for all top stocks
        factor_cols = [
            ("A Momentum (25%)", 0.25, "#58a6ff"),
            ("B Breakout (15%)", 0.15, "#26a69a"),
            ("C Volume (15%)", 0.15, "#7c3aed"),
            ("D OI (15%)", 0.15, "#f59e0b"),
            ("E RSI (10%)", 0.10, "#ec4899"),
            ("F IV (10%)", 0.10, "#14b8a6"),
            ("G Nifty (10%)", 0.10, "#84cc16"),
        ]

        fig = go.Figure()
        for col, weight, color in factor_cols:
            if col in df.columns:
                contrib = df[col] * weight  # weighted contribution
                fig.add_trace(go.Bar(
                    name=col.split("(")[0].strip(),
                    x=df["Contract"],
                    y=contrib,
                    marker_color=color,
                    text=df[col].round(0).astype(int).astype(str),
                    textposition="inside",
                    textfont=dict(size=8),
                ))

        fig.update_layout(
            barmode="stack",
            height=380,
            margin=dict(l=10, r=10, t=30, b=100),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            dragmode=False,
            legend=dict(
                orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                font=dict(size=9, color="#8b949e"),
            ),
            xaxis=dict(tickangle=-35, tickfont=dict(size=8), color="#8b949e"),
            yaxis=dict(title="Weighted Score", gridcolor="rgba(128,128,128,0.15)",
                       color="#8b949e", range=[0, 105]),
            title=dict(text="Weighted Factor Contributions (stacked)", font=dict(size=11, color="#8b949e")),
        )
        st.plotly_chart(fig, use_container_width=True, config={"scrollZoom": False, "displayModeBar": False})

        # ── R/R vs Score Scatter ──────────────────────────────────────────
        st.subheader("⚖️ Reward/Risk vs Composite Score")
        fig2 = go.Figure(go.Scatter(
            x=df["Final Score (0-100)"],
            y=df["Reward/Risk Ratio"],
            mode="markers+text",
            text=df["Contract"],
            textposition="top center",
            textfont=dict(size=8, color="#8b949e"),
            marker=dict(
                size=14,
                color=df["Return%"],
                colorscale="RdYlGn",
                colorbar=dict(title="Return%", thickness=12),
                cmin=-20, cmax=60,
                line=dict(color="#30363d", width=1),
            ),
        ))
        fig2.add_hline(y=1.8, line=dict(color="#f85149", dash="dash", width=1),
                       annotation_text="Min R/R = 1.8", annotation_font_size=9)
        fig2.update_layout(
            height=380, margin=dict(l=10, r=10, t=10, b=40),
            plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
            dragmode=False,
            xaxis=dict(title="Composite Score (0-100)", gridcolor="rgba(128,128,128,0.12)", color="#8b949e"),
            yaxis=dict(title="Reward/Risk Ratio", gridcolor="rgba(128,128,128,0.12)", color="#8b949e"),
        )
        st.plotly_chart(fig2, use_container_width=True, config={"scrollZoom": False, "displayModeBar": False})

        # ── Full Table ────────────────────────────────────────────────────
        st.subheader("📋 Full Strategy Output")
        display_cols = [
            "Contract", "Company", "Price Source", "Expiry", "Days to Expiry",
            "Final Score (0-100)",
            "A Momentum (25%)", "B Breakout (15%)", "C Volume (15%)",
            "D OI (15%)", "E RSI (10%)", "F IV (10%)", "G Nifty (10%)",
            "RS Bonus",
            "Underlying Spot (₹)", "Strike (₹)", "Moneyness%",
            "Current Premium (₹)", "BS Fair Value (₹)", "Lot Size",
            "Investment / Lot (₹)", "Delta", "Daily Theta (₹)",
            "Theta % of Premium", "Theta OK", "Reward/Risk Ratio", "R/R OK",
            "Target Spot Price (₹)", "Expected Premium @ Target (₹)",
            "Est Profit / Lot (₹)", "Return%",
            "RSI", "IV Rank", "ATR (₹)", "Volatility (σ)",
            "Breakout", "Vol Ratio", "Momentum%",
            "Above 20DMA", "ATR% ≥ 1.5", "3d Gain ≤ 8%", "IV Range OK",
            "Above 5 EMA", "Exit Signals",
            "News Score", "Latest News",
        ]
        disp = df[[c for c in display_cols if c in df.columns]].copy()
        st.dataframe(disp.reset_index(drop=True), use_container_width=True)

        # ── News Headlines ─────────────────────────────────────────────────
        if "Latest News" in df.columns:
            news_df = df[["Symbol", "Latest News", "News Score"]].drop_duplicates("Symbol")
            news_df = news_df[news_df["Latest News"] != "—"]
            if not news_df.empty:
                st.subheader("📰 Latest News")
                for _, nrow in news_df.iterrows():
                    nc_ = "#3fb950" if float(nrow["News Score"]) > 0.3 else (
                        "#f85149" if float(nrow["News Score"]) < -0.3 else "#8b949e")
                    st.markdown(
                        f"<div style='border-left:3px solid {nc_};padding:4px 12px;margin:4px 0;"
                        f"color:#c9d1d9;font-size:0.82rem;'>"
                        f"<b style='color:{nc_};'>{nrow['Symbol']}</b> — {nrow['Latest News']}</div>",
                        unsafe_allow_html=True,
                    )

        st.caption(
            "📌 **Score formula**: (0.25×A)+(0.15×B)+(0.15×C)+(0.15×D)+(0.10×E)+(0.10×F)+(0.10×G) + RS bonus. "
            "**Contract selected** by finding strike with Delta 0.40–0.55, theta ≤ 0.5%/day, R/R ≥ 1.8. "
            "**Premium** = Live NSE LTP when market open, else Black-Scholes (90d HV). "
            "**Target** = Spot + 1.5×ATR. **D (OI)** uses price+volume proxy (live OI unavailable). "
            "⚠️ *Not investment advice.*"
        )
