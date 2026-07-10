from __future__ import annotations

import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import pandas as pd
import yfinance as yf
from ta.momentum import RSIIndicator
from ta.trend import MACD
from ta.volatility import AverageTrueRange, BollingerBands

from services.scanner_service import SYMBOL_SECTOR_MAP
from services.shortterm_scanner_service import load_universe_symbols, fetch_india_vix
from services.pattern_recognition_service import analyze_patterns
from services.options_service import (
    _estimate_volatility, 
    _strike_step, 
    _bs_greeks, 
    get_month_options, 
    _find_month_expiry,
    _contract_name,
    _fetch_live_option_ltp
)
from utils.logging import logger

SECTOR_INDEX_MAP = {
    "IT": "^CNXIT",
    "Pharma": "^CNXPHARMA",
    "Diagnostics": "^CNXPHARMA",
    "FMCG": "^CNXFMCG",
    "Auto": "^CNXAUTO",
    "Metals": "^CNXMETAL",
    "Energy": "^CNXENERGY",
    "Financials": "^CNXFIN",
    "PSU Banks": "^CNXPSUBANK",
    "Private Banks": "^NSEBANK",
    "Real Estate": "^CNXREALTY",
    "Media": "^CNXMEDIA",
    "Capital Goods": "^CNXINFRA",
    "Defence": "^CNXPSE",
    "Railways": "^CNXPSE",
}

# Cache for sector index data
_sector_cache: Dict[str, pd.DataFrame] = {}


def fetch_sector_history(sector_name: str) -> Optional[pd.DataFrame]:
    """Fetch and cache sector index history for cycle phase analysis."""
    index_ticker = SECTOR_INDEX_MAP.get(sector_name)
    if not index_ticker:
        # Fallback to NIFTY 50 if sector index unknown
        index_ticker = "^NSEI"

    if index_ticker in _sector_cache:
        return _sector_cache[index_ticker]

    try:
        end_date = datetime.now().date() + timedelta(days=1)
        start_date = end_date - timedelta(days=90)
        df = yf.download(index_ticker, start=start_date, end=end_date, interval="1d", progress=False, auto_adjust=False)
        if df is not None and not df.empty:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [col[0] for col in df.columns]
            # Calculate basic indicators for sector
            close = df["Close"]
            df["EMA_20"] = close.ewm(span=20, adjust=False).mean()
            macd_obj = MACD(close=close, window_slow=26, window_fast=12, window_sign=9)
            df["MACD"] = macd_obj.macd()
            df["MACD_HIST"] = macd_obj.macd_diff()
            _sector_cache[index_ticker] = df
            return df
    except Exception as e:
        logger.warning(f"Failed to fetch sector index {index_ticker} for {sector_name}: {e}")
    return None


def get_sector_phase(sector_name: str) -> str:
    """
    Determine Sector Cycle Phase:
    - Leading: > 20 EMA & MACD positive
    - Weakening: > 20 EMA & MACD negative
    - Improving: < 20 EMA & MACD positive (bottoming)
    - Lagging: < 20 EMA & MACD negative
    """
    df = fetch_sector_history(sector_name)
    if df is None or df.empty or len(df) < 20:
        return "Unknown"
    
    last = df.iloc[-1]
    close = float(last["Close"])
    ema20 = float(last["EMA_20"]) if pd.notna(last["EMA_20"]) else close
    macd = float(last["MACD_HIST"]) if pd.notna(last["MACD_HIST"]) else 0.0
    
    if close > ema20 and macd > 0:
        return "Leading"
    elif close > ema20 and macd <= 0:
        return "Weakening"
    elif close <= ema20 and macd > 0:
        return "Improving"
    else:
        return "Lagging"


def _evaluate_option(symbol_bare: str, spot: float, hist: pd.DataFrame, target: float, stop_loss: float) -> Optional[Dict]:
    """
    Evaluates and recommends the optimal Call Option for the given early breakout stock.
    Returns a dictionary with option details or None if no valid option is found.
    """
    try:
        sigma = _estimate_volatility(hist)
        months = get_month_options()
        if not months:
            return None
            
        # Get Current/Nearest Month
        label, y, m = months[0]
        expiry_str = _find_month_expiry(None, y, m)
        if not expiry_str:
            # Try next month if current month already expired
            if len(months) > 1:
                label, y, m = months[1]
                expiry_str = _find_month_expiry(None, y, m)
            if not expiry_str:
                return None
                
        expiry_dt = datetime.strptime(expiry_str, "%Y-%m-%d").date()
        today = datetime.now().date()
        days_left = (expiry_dt - today).days
        if days_left <= 0:
            days_left = 1
        T = days_left / 365.0
        
        step = _strike_step(spot)
        atm = round(spot / step) * step
        
        # We want slightly OTM or ATM for breakouts since they are expected to move fast
        strike_candidates = [atm, atm + step]
        best_option = None
        best_rr = 0.0
        
        for K in strike_candidates:
            price, delta, daily_theta = _bs_greeks(spot, K, T, 0.067, sigma)
            if price < 0.5:
                continue
            
            # Risk: We assume the option will lose roughly 40% if stop loss is hit
            risk = price * 0.40
            
            # Reward: Expected gain in option price if target is hit. 
            reward = delta * max((target - spot), 0)
            
            rr_ratio = reward / risk if risk > 0 else 0
            
            # Theta decay condition
            theta_pct = abs(daily_theta) / price if price > 0 else 1.0
            
            # Pick the option with the highest R:R ratio, regardless of strict thresholds
            if rr_ratio > best_rr:
                moneyness = "ATM" if K == atm else ("ITM" if K < atm else "OTM")
                
                # Fetch live option premium via NSE API if available
                live_ltp, _ = _fetch_live_option_ltp(symbol_bare, expiry_str, K, "CE")
                premium_to_show = live_ltp if live_ltp else price
                
                warnings = []
                if theta_pct > 0.025:
                    warnings.append("High Theta Decay")
                if rr_ratio < 1.2:
                    warnings.append("Poor R:R")
                warning_str = " | ".join(warnings) if warnings else None
                
                best_option = {
                    "Contract": _contract_name(symbol_bare, expiry_str, K, "CE"),
                    "Strike": K,
                    "Moneyness": moneyness,
                    "Type": "Call (CE)",
                    "Expiry": expiry_str,
                    "Premium": premium_to_show,
                    "Delta": delta,
                    "Daily_Theta": abs(daily_theta),
                    "Theta_Pct": theta_pct * 100,
                    "RR_Ratio": rr_ratio,
                    "Warning": warning_str
                }
                best_rr = rr_ratio
                    
        return best_option
    except Exception as e:
        logger.debug(f"Option evaluation error for {symbol_bare}: {e}")
        return None

def calculate_early_breakout_indicators(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df

    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] for col in df.columns]

    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df.get("Volume")
    n = len(df)

    # MA
    df["EMA_20"] = close.ewm(span=20, adjust=False).mean()
    df["SMA_50"] = close.rolling(window=50, min_periods=25).mean()

    # RSI
    if n >= 14:
        df["RSI_14"] = RSIIndicator(close=close, window=14).rsi()
    else:
        df["RSI_14"] = 50.0

    # MACD
    if n >= 26:
        macd_obj = MACD(close=close, window_slow=26, window_fast=12, window_sign=9)
        df["MACD"] = macd_obj.macd()
        df["MACD_HIST"] = macd_obj.macd_diff()
    else:
        df["MACD"] = 0.0
        df["MACD_HIST"] = 0.0

    # ATR
    if n >= 14:
        atr_obj = AverageTrueRange(high=high, low=low, close=close, window=14)
        df["ATR_14"] = atr_obj.average_true_range()
    else:
        df["ATR_14"] = close * 0.04

    # Bollinger Bands
    if n >= 20:
        bb = BollingerBands(close=close, window=20, window_dev=2)
        df["BB_HIGH"] = bb.bollinger_hband()
        df["BB_LOW"] = bb.bollinger_lband()
        df["BB_WIDTH"] = (df["BB_HIGH"] - df["BB_LOW"]) / close
        df["AVG_BB_WIDTH"] = df["BB_WIDTH"].rolling(window=20).mean()
    else:
        df["BB_HIGH"] = close * 1.05
        df["BB_LOW"] = close * 0.95
        df["BB_WIDTH"] = 0.1
        df["AVG_BB_WIDTH"] = 0.1

    # Volume Ratio
    if volume is not None and n >= 20:
        vol_mean = volume.rolling(window=20, min_periods=10).mean()
        df["VOLUME_RATIO"] = (volume / vol_mean.replace(0, 1.0)).fillna(1.0)
    else:
        df["VOLUME_RATIO"] = 1.0

    # 15-day range (Consolidation)
    if n >= 15:
        high_15 = high.rolling(window=15).max()
        low_15 = low.rolling(window=15).min()
        df["RANGE_15D_PCT"] = (high_15 - low_15) / low_15 * 100.0
        df["CONSOLIDATION_LOW"] = low_15
    else:
        df["RANGE_15D_PCT"] = 99.0
        df["CONSOLIDATION_LOW"] = low

    return df


def fetch_nifty_return_15d() -> float:
    try:
        nifty = yf.Ticker("^NSEI")
        df = nifty.history(period="25d")
        if not df.empty:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [c[0] for c in df.columns]
            if len(df) >= 15:
                return (float(df["Close"].iloc[-1]) / float(df["Close"].iloc[-15]) - 1.0) * 100.0
    except Exception as e:
        logger.warning(f"Could not fetch Nifty return: {e}")
    return 0.0


def score_early_breakout(
    symbol_bare: str,
    df: pd.DataFrame,
    sector_phase: str,
    nifty_return_15d: float = 0.0
) -> Tuple[float, Dict[str, float]]:
    
    if df.empty or len(df) < 20:
        return 0.0, {}

    last = df.iloc[-1]
    close = float(last["Close"])
    
    scores: Dict[str, float] = {}

    # 1. Volatility Squeeze (25%)
    # Narrower BB width relative to historical avg = better
    bb_width = float(last.get("BB_WIDTH", 0.1)) if pd.notna(last.get("BB_WIDTH")) else 0.1
    avg_bb_width = float(last.get("AVG_BB_WIDTH", 0.1)) if pd.notna(last.get("AVG_BB_WIDTH")) else 0.1
    
    squeeze_pts = 0.0
    if bb_width < avg_bb_width * 0.8:  # 20% tighter than usual
        squeeze_pts = 25.0
    elif bb_width < avg_bb_width:
        squeeze_pts = 15.0
    
    # Range condition: tighter range = better squeeze
    range_15d = float(last.get("RANGE_15D_PCT", 99.0)) if pd.notna(last.get("RANGE_15D_PCT")) else 99.0
    if range_15d <= 8.0:
        squeeze_pts = min(25.0, squeeze_pts + 10.0)
    elif range_15d <= 12.0:
        squeeze_pts = min(25.0, squeeze_pts + 5.0)
    
    scores["squeeze"] = squeeze_pts

    # 2. Volume Expansion (25%)
    vol_ratio = float(last.get("VOLUME_RATIO", 1.0)) if pd.notna(last.get("VOLUME_RATIO")) else 1.0
    vol_pts = 0.0
    if vol_ratio > 2.0:
        vol_pts = 25.0
    elif vol_ratio > 1.5:
        vol_pts = 20.0
    elif vol_ratio > 1.2:
        vol_pts = 10.0
    scores["volume"] = vol_pts

    # 3. Early Momentum (20%)
    ema20 = float(last.get("EMA_20", close)) if pd.notna(last.get("EMA_20")) else close
    prev_close = float(df["Close"].iloc[-2]) if len(df) >= 2 else close
    prev_ema20 = float(df["EMA_20"].iloc[-2]) if len(df) >= 2 else ema20
    
    mom_pts = 0.0
    if close > ema20 and prev_close <= prev_ema20:  # Fresh cross
        mom_pts = 20.0
    elif close > ema20: # Sustained above
        dist = (close - ema20) / ema20 * 100.0
        if dist < 3.0: # Close to EMA, early breakout
            mom_pts = 15.0
        elif dist < 6.0:
            mom_pts = 10.0
    scores["momentum"] = mom_pts

    # 4. Oscillator Shifts (15%)
    rsi = float(last.get("RSI_14", 50.0)) if pd.notna(last.get("RSI_14")) else 50.0
    prev_rsi = float(df["RSI_14"].iloc[-2]) if len(df) >= 2 and "RSI_14" in df.columns else rsi
    macd_hist = float(last.get("MACD_HIST", 0.0)) if pd.notna(last.get("MACD_HIST")) else 0.0
    
    osc_pts = 0.0
    if 50.0 <= rsi <= 60.0 and prev_rsi < 50.0:  # Fresh shift to bullish zone
        osc_pts += 8.0
    elif 55.0 <= rsi <= 65.0:
        osc_pts += 5.0
        
    if macd_hist > 0:
        osc_pts += 7.0
    scores["oscillators"] = min(15.0, osc_pts)

    # 5. Sector Phase & RS (15%)
    stock_return_15d = (close / float(df["Close"].iloc[-15]) - 1.0) * 100.0 if len(df) >= 15 else 0.0
    rs_diff = stock_return_15d - nifty_return_15d
    
    bonus_pts = 0.0
    if rs_diff > 0:
        bonus_pts += min(7.5, rs_diff * 1.5)
        
    if sector_phase == "Leading":
        bonus_pts += 7.5
    elif sector_phase == "Improving":
        bonus_pts += 5.0
    scores["sector_rs"] = min(15.0, bonus_pts)

    total_score = sum(scores.values())
    return round(min(100.0, total_score), 1), scores


def scan_early_breakouts(
    universe: str,
    top_n: int = 20,
    progress_callback = None
) -> pd.DataFrame:
    symbols = load_universe_symbols(universe)
    if not symbols:
        return pd.DataFrame()

    nifty_ret = fetch_nifty_return_15d()
    
    end_date = datetime.now().date() + timedelta(days=1)
    start_date = end_date - timedelta(days=150)
    
    rows = []
    total_symbols = len(symbols)
    
    for i, symbol in enumerate(symbols):
        symbol_bare = symbol.replace(".NS", "")
        if progress_callback:
            progress_callback(i + 1, total_symbols, symbol_bare)
            
        try:
            time.sleep(0.05)
            df = yf.download(
                symbol,
                start=start_date,
                end=end_date,
                interval="1d",
                progress=False,
                auto_adjust=False
            )
            if df is None or df.empty or len(df) < 20:
                continue

            # False Breakout Trap Filter: 
            # Check closing position within the daily candle (needs to be in top 50%)
            last = df.iloc[-1]
            close = float(last["Close"])
            high = float(last["High"])
            low = float(last["Low"])
            candle_range = high - low
            if candle_range > 0:
                close_pos = (close - low) / candle_range
                if close_pos < 0.4:
                    # Weak close, rejection wick -> Skip
                    continue

            df = calculate_early_breakout_indicators(df)
            
            sector = SYMBOL_SECTOR_MAP.get(symbol_bare, "Other")
            if sector == "Other":
                sector = SYMBOL_SECTOR_MAP.get(symbol, "Other")
                
            sector_phase = get_sector_phase(sector)
            
            score, sub_scores = score_early_breakout(symbol_bare, df, sector_phase, nifty_ret)
            
            if score < 40.0:  # Skip weak setups
                continue

            last = df.iloc[-1]
            ema20 = float(last["EMA_20"]) if pd.notna(last["EMA_20"]) else close
            consolidation_low = float(last["CONSOLIDATION_LOW"]) if pd.notna(last["CONSOLIDATION_LOW"]) else close * 0.95
            atr = float(last["ATR_14"]) if pd.notna(last["ATR_14"]) else close * 0.04
            
            # Risk Management
            # Stop loss just below EMA 20 or consolidation low (whichever is closer to price but allows some breathing room)
            sl_candidate = min(ema20, consolidation_low)
            stop_loss = round(sl_candidate - (atr * 0.5), 2)
            
            risk = close - stop_loss
            if risk <= 0:
                risk = atr  # Fallback

            target1 = round(close + (1.5 * risk), 2)
            target2 = round(close + (3.0 * risk), 2)
            
            rr_ratio = round((target1 - close) / risk, 2)
            
            if rr_ratio < 1.0:
                continue  # Skip poor R:R

            tags = []
            if sub_scores["squeeze"] >= 15:
                tags.append("Squeeze 🗜️")
            if sub_scores["volume"] >= 10:
                tags.append("Volume Spike ⚡")
            if sub_scores["momentum"] >= 15:
                tags.append("20-EMA Cross 🚀")
            if sub_scores["oscillators"] >= 7:
                tags.append("MACD+ 📶")

            # Chart Pattern Recognition
            pattern_data = analyze_patterns(df)
            for p in pattern_data.get("patterns", []):
                tags.append(f"[{p['type']}]")
                
            # Option Recommendation (If F&O Universe)
            option_rec = None
            if "f&o" in universe.lower() or "fno" in universe.lower():
                option_rec = _evaluate_option(symbol_bare, close, df, target1, stop_loss)

            # Keep a lightweight copy of the dataframe for UI charting (last 150 bars)
            chart_df = df[["Open", "High", "Low", "Close", "Volume"]].tail(150).copy()
            chart_df.index = chart_df.index.strftime("%Y-%m-%d")

            rows.append({
                "Symbol": symbol_bare,
                "Sector": sector,
                "Sector Phase": sector_phase,
                "Close (₹)": round(close, 2),
                "Score": score,
                "Stop Loss (₹)": stop_loss,
                "Target 1 (₹)": target1,
                "Target 2 (₹)": target2,
                "R:R Ratio": rr_ratio,
                "Tags": ", ".join(tags) if tags else "Neutral",
                "Chart_DF": chart_df.to_dict(orient="index"),
                "Pattern_Data": pattern_data,
                "Option_Rec": option_rec
            })
        except Exception as e:
            logger.debug(f"Error scanning early breakout for {symbol_bare}: {e}")
            continue

    if not rows:
        return pd.DataFrame()

    df_results = pd.DataFrame(rows)
    df_results = df_results.sort_values(by="Score", ascending=False).head(top_n)
    return df_results.reset_index(drop=True)
