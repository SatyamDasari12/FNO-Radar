import json
import os
import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime

from services.paper_trade_service import (
    add_active_trade,
    close_active_trade,
    delete_trade,
    get_active_trades,
    get_closed_trades,
    compute_stats
)
from features.stock_master import load_combined_stock_master, build_all_labels


def _load_lot_sizes() -> dict[str, int]:
    """Load symbol-to-lotsize mapping from fno_master.json."""
    fno_path = "data/fno_master.json"
    mapping = {}
    if os.path.exists(fno_path):
        try:
            with open(fno_path, "r", encoding="utf-8") as f:
                entries = json.load(f)
            for entry in entries:
                sym = entry.get("symbol", "").strip().upper()
                lot = entry.get("lot_size", 0)
                if sym and lot > 0:
                    mapping[sym] = lot
        except Exception:
            pass
    return mapping


def render_paper_trader_page() -> None:
    st.title("🎮 Paper Trading System")
    st.caption("Log buy and sell events for stocks/options and track your training performance in real-time.")

    lot_sizes = _load_lot_sizes()
    active_trades = get_active_trades()
    closed_trades = get_closed_trades()
    stats = compute_stats()

    tab1, tab2, tab3 = st.tabs(["📈 Open Positions", "📊 Performance & History", "📥 Log New Position"])

    # ── TAB 1: Open Positions ─────────────────────────────────────────────
    with tab1:
        st.subheader("Open Positions")
        if not active_trades:
            st.info("No active open positions. Go to the 'Log New Position' tab to add a paper trade.")
        else:
            for trade in active_trades:
                tid = trade["id"]
                sym = trade["symbol"]
                otype = trade["option_type"]
                strike = trade["strike_price"]
                expiry = trade["expiry_date"]
                buy_p = trade["buy_price"]
                qty = trade["quantity"]
                buy_val = buy_p * qty
                buy_time = trade["buy_time"]
                notes = trade["notes"]

                desc = f"{otype} Strike {strike} Expiry {expiry}" if otype != "STOCK" else "Equity (Cash)"

                # Fetch current stock close price to estimate market context
                curr_stock_price = "—"
                try:
                    ticker = yf.Ticker(f"{sym}.NS")
                    history = ticker.history(period="1d")
                    if not history.empty:
                        # Handle multi-level columns if present
                        if isinstance(history.columns, pd.MultiIndex):
                            history.columns = [c[0] for c in history.columns]
                        curr_stock_price = f"₹{history['Close'].iloc[-1]:.2f}"
                except Exception:
                    pass

                st.markdown(
                    f"""<div style="background:#161b22; border:1px solid #30363d; border-left:5px solid #58a6ff; border-radius:10px; padding:15px; margin-bottom:12px;">
<div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:8px;">
<div>
<span style="color:#e6edf3; font-size:1.1rem; font-weight:800;">{sym}</span>
&nbsp;<span style="background:#1f6feb22; color:#58a6ff; font-size:0.72rem; padding:2px 8px; border-radius:20px; border:1px solid #1f6feb66; font-weight:600;">{desc}</span>
</div>
<div style="font-size:0.78rem; color:#8b949e;">Logged: {buy_time}</div>
</div>
<div style="margin-top:10px; display:flex; gap:25px; flex-wrap:wrap; font-size:0.84rem;">
<span style="color:#8b949e;">Buy Price: <b style="color:#c9d1d9;">₹{buy_p:.2f}</b></span>
<span style="color:#8b949e;">Quantity: <b style="color:#c9d1d9;">{qty}</b></span>
<span style="color:#8b949e;">Total Cost: <b style="color:#c9d1d9;">₹{buy_val:.2f}</b></span>
<span style="color:#8b949e;">Current Stock Spot: <b style="color:#58a6ff;">{curr_stock_price}</b></span>
</div>
{f'<div style="margin-top:8px; color:#8b949e; font-size:0.76rem; font-style:italic;">📝 Notes: {notes}</div>' if notes else ''}
</div>""",
                    unsafe_allow_html=True
                )

                c_action, c_delete = st.columns([3, 1])
                with c_action:
                    with st.expander(f"🔴 Close Position for {sym}", expanded=False):
                        sell_premium = st.number_input(
                            "Sell Premium / Premium per share (₹)",
                            min_value=0.01,
                            value=float(buy_p),
                            step=0.05,
                            key=f"sell_p_{tid}"
                        )
                        close_btn = st.button("Close Trade (Realize PnL)", type="primary", key=f"close_{tid}")
                        if close_btn:
                            res = close_active_trade(tid, sell_premium)
                            if res:
                                st.success(f"Closed trade for {sym}! Realized profit: ₹{res['pnl']:.2f}")
                                st.rerun()
                with c_delete:
                    if st.button("🗑️ Delete Record", key=f"del_{tid}", use_container_width=True):
                        if delete_trade(tid):
                            st.warning(f"Deleted paper position for {sym}.")
                            st.rerun()

    # ── TAB 2: Performance & History ──────────────────────────────────────
    with tab2:
        st.subheader("Performance Summary")
        
        # KPI metrics display
        k1, k2, k3, k4 = st.columns(4)
        
        # Color coding PnL
        net_val = stats["net_pnl"]
        pnl_color = "#3fb950" if net_val >= 0 else "#f85149"
        pnl_sign = "+" if net_val >= 0 else ""
        
        with k1:
            st.metric("Total Trades", stats["total_trades"])
        with k2:
            st.metric("Win Rate (%)", f"{stats['win_rate']}%")
        with k3:
            # Styled Net P&L display
            st.markdown(
                f"""
                <div style="background:#161b22; border:1px solid #30363d; border-radius:8px; padding:10px 14px; text-align:center;">
                    <span style="font-size:0.75rem; color:#8b949e; text-transform:uppercase; font-weight:600;">Net P&L (₹)</span><br/>
                    <span style="font-size:1.25rem; color:{pnl_color}; font-weight:700;">{pnl_sign}₹{net_val:,.2f}</span>
                </div>
                """,
                unsafe_allow_html=True
            )
        with k4:
            st.metric("Profit Factor", stats["profit_factor"])

        st.markdown("---")
        st.subheader("Trade History")
        
        if not closed_trades:
            st.info("No completed trades yet. Close active positions to build history.")
        else:
            # Turn into DataFrame for display
            history_rows = []
            for t in closed_trades:
                pnl = t["pnl"]
                pnl_pct = t["pnl_pct"]
                pnl_styled = f"₹{pnl:+.2f} ({pnl_pct:+.1f}%)"
                
                history_rows.append({
                    "Symbol": t["symbol"],
                    "Type": t["option_type"],
                    "Strike": t["strike_price"] if t["option_type"] != "STOCK" else "—",
                    "Expiry": t["expiry_date"],
                    "Buy Px": f"₹{t['buy_price']:.2f}",
                    "Sell Px": f"₹{t['sell_price']:.2f}",
                    "Qty": t["quantity"],
                    "P&L": pnl_styled,
                    "Buy Date": t["buy_time"][:10],
                    "Sell Date": t["sell_time"][:10],
                    "Notes": t["notes"]
                })
                
            df_history = pd.DataFrame(history_rows)
            st.dataframe(df_history, use_container_width=True, hide_index=True)

    # ── TAB 3: Log New Position ───────────────────────────────────────────
    with tab3:
        st.subheader("Log New Trade")
        
        # Load stocks typeahead list
        stock_master = load_combined_stock_master()
        labels = build_all_labels(stock_master)
        
        with st.form("log_trade_form"):
            selected_label = st.selectbox(
                "Select Stock/Ticker",
                options=labels,
                help="Type to search for the stock ticker."
            )
            
            # Extract symbol from selectbox label e.g. "AMBUJACEM — Ambuja Cements [NSE]" -> "AMBUJACEM"
            selected_symbol = selected_label.split(" — ")[0].strip() if " — " in selected_label else selected_label
            
            trade_type = st.selectbox(
                "Position Type",
                options=["Option Call (CE)", "Option Put (PE)", "Stock (Cash)"],
                index=0
            )
            
            c_strike, c_expiry = st.columns(2)
            with c_strike:
                strike_px = st.number_input(
                    "Strike Price (₹)",
                    min_value=0.0,
                    value=0.0,
                    step=5.0,
                    help="Only applicable for options contracts."
                )
            with c_expiry:
                # Pre-populate with current month's typical F&O format date
                default_expiry = datetime.now().strftime("%Y-%m-30")
                expiry_dt = st.text_input(
                    "Expiry Date (YYYY-MM-DD)",
                    value=default_expiry,
                    help="Only applicable for options contracts."
                )
                
            c_price, c_qty = st.columns(2)
            with c_price:
                buy_premium = st.number_input(
                    "Buy Premium / Buy Price (₹)",
                    min_value=0.01,
                    value=10.0,
                    step=0.05,
                    help="Enter premium for options, or share price for stocks."
                )
            with c_qty:
                # Look up F&O lot size for selected symbol
                default_lot = lot_sizes.get(selected_symbol, 100)
                qty_val = st.number_input(
                    "Trade Quantity / Shares",
                    min_value=1,
                    value=default_lot,
                    step=1,
                    help=f"Lot size defaults to F&O size if available. (AMBUJACEM is 1000, 360ONE is 150, stocks default to 100)."
                )
                
            trade_notes = st.text_area(
                "Training Remarks / Entry Rationale",
                placeholder="Write why you are taking this trade, e.g., 'EMA 20 crossover breakout on the daily scanner, RSI is at 55.'"
            )
            
            submit_btn = st.form_submit_button("🟢 Log Purchase Position", type="primary")
            
            if submit_btn:
                # Map selectbox label type to backend string format
                otype_map = {
                    "Option Call (CE)": "CE",
                    "Option Put (PE)": "PE",
                    "Stock (Cash)": "STOCK"
                }
                backend_type = otype_map[trade_type]
                
                # Validation checks
                if backend_type != "STOCK" and strike_px <= 0:
                    st.error("Please enter a valid strike price for options.")
                else:
                    new_t = add_active_trade(
                        symbol=selected_symbol,
                        option_type=backend_type,
                        strike_price=strike_px,
                        expiry_date=expiry_dt,
                        buy_price=buy_premium,
                        quantity=qty_val,
                        notes=trade_notes
                    )
                    st.success(f"Success! Logged ACTIVE {selected_symbol} {trade_type} position.")
                    st.rerun()
