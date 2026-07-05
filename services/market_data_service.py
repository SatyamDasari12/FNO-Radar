from __future__ import annotations

from datetime import date, timedelta
from typing import Optional, Tuple

import pandas as pd
import yfinance as yf

from models.types import Quote
from features.indicators import add_indicators_to_ohlc
from utils.logging import logger


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Flatten multi-level column headers produced by recent yfinance versions."""
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]
    return df


def resolve_symbol(raw_symbol: str) -> Tuple[str, str]:
    """
    Given a bare symbol like 'BEL' or 'RELIANCE', auto-detects the exchange.
    - Tries NSE first (.NS suffix), then BSE (.BO suffix).
    - If suffix already present (.NS or .BO), returns as-is.

    Returns:
        (full_symbol, exchange_label)  e.g. ('BEL.NS', 'NSE')
    """
    raw = raw_symbol.strip().upper()

    # Already has explicit suffix → use as-is
    if raw.endswith(".NS"):
        return raw, "NSE"
    if raw.endswith(".BO"):
        return raw, "BSE"

    # If it's a numeric scrip code (BSE style), try BSE first
    probes = [(".NS", "NSE"), (".BO", "BSE")]
    if raw.isdigit():
        probes = [(".BO", "BSE"), (".NS", "NSE")]

    for suffix, exchange in probes:
        candidate = raw + suffix
        try:
            ticker = yf.Ticker(candidate)
            hist = ticker.history(period="5d", auto_adjust=False)
            if hist is not None and not hist.empty:
                logger.info(f"Resolved '{raw}' → {candidate} ({exchange})")
                return candidate, exchange
        except Exception as exc:
            logger.debug(f"Symbol probe failed for {candidate}: {exc}")

    # Default fallback: NSE for alphabetic, BSE for numeric
    default_suffix = ".BO" if raw.isdigit() else ".NS"
    default_exch = "BSE" if raw.isdigit() else "NSE"
    logger.warning(f"Could not validate '{raw}' on NSE or BSE; defaulting to {default_exch}.")
    return raw + default_suffix, default_exch


# ---------------------------------------------------------------------------
# Dynamic interval selection
# ---------------------------------------------------------------------------

# yfinance intraday data age limits:
#   1m  → last 7 days only
#   2m/5m/15m/30m/60m/90m → last 60 days only
#   1h  → last 730 days
#   1d / 1wk / 1mo → unlimited
_INTERVAL_MAP = [
    # (max_days, max_start_age_days, interval, label)
    (1,    6,   "5m",  "5-minute"),
    (1,    59,  "15m", "15-minute"),
    (1,    730, "1h",  "1-hour"),
    (5,    59,  "15m", "15-minute"),
    (5,    730, "1h",  "1-hour"),
    (60,   59,  "1h",  "1-hour"),
    (60,   730, "1d",  "Daily"),
    (730,  730, "1d",  "Daily"),
]


def get_dynamic_interval(start: date, end: date) -> Tuple[str, str]:
    """
    Choose the finest yfinance interval that fits within API age limits.

    Returns:
        (interval_str, human_label)  e.g. ('1d', 'Daily')
    """
    range_days = max((end - start).days, 1)
    start_age = (date.today() - start).days  # how many days ago is 'start'

    if range_days <= 1:
        if start_age <= 6:
            return "5m", "5-minute"
        elif start_age <= 59:
            return "15m", "15-minute"
        else:
            return "1h", "1-hour"
    elif range_days <= 5:
        if start_age <= 59:
            return "15m", "15-minute"
        else:
            return "1h", "1-hour"
    elif range_days <= 60:
        if start_age <= 59:
            return "1h", "1-hour"
        else:
            return "1d", "Daily"
    elif range_days <= 730:
        return "1d", "Daily"
    else:
        return "1wk", "Weekly"


def get_rangebreaks(interval: str) -> list:
    """
    Return Plotly rangebreaks to hide non-trading periods.
    - Daily / weekly: hide weekends (Sat-Mon).
    - Intraday: also hide non-NSE/BSE trading hours.
      NSE/BSE: 09:15–15:30 IST = 03:45–10:00 UTC
    """
    weekend_break = dict(bounds=["sat", "mon"])
    if interval in ("1d", "1wk", "1mo"):
        return [weekend_break]
    else:
        # Hide outside 03:30–10:30 UTC (≈ 09:00–16:00 IST, covers pre/post market)
        session_break = dict(bounds=[10.5, 3.5], pattern="hour")
        return [weekend_break, session_break]


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------

def get_price_history(
    symbol: str,
    start: date,
    end: date,
    interval: str = "1d",
) -> Optional[pd.DataFrame]:
    try:
        df = yf.download(
            symbol,
            start=start,
            end=end,
            interval=interval,
            progress=False,
            auto_adjust=False,
        )
    except Exception as exc:
        logger.exception(f"Failed to download history for {symbol}: {exc}")
        return None

    if df is None or df.empty:
        return None

    df = _flatten_columns(df)
    df = df.rename(columns={"Adj Close": "AdjClose"})

    # Drop any duplicate index entries (can happen with intraday data near DST)
    df = df[~df.index.duplicated(keep="last")]

    return df


def get_history_with_indicators(
    symbol: str,
    start: date,
    end: date,
    interval: str = "1d",
) -> Optional[pd.DataFrame]:
    df = get_price_history(symbol, start, end, interval=interval)
    if df is None:
        return None
    return add_indicators_to_ohlc(df)


def get_latest_quote(symbol: str) -> Optional[Quote]:
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="6mo", auto_adjust=False)
    except Exception as exc:
        logger.exception(f"Failed to fetch latest quote for {symbol}: {exc}")
        return None

    if hist is None or hist.empty:
        return None

    hist = _flatten_columns(hist)
    hist = hist.rename(columns={"Adj Close": "AdjClose"})
    hist = add_indicators_to_ohlc(hist)
    last_price = float(hist["Close"].iloc[-1])
    return Quote(symbol=symbol, last_price=last_price, history_df=hist)


# ---------------------------------------------------------------------------
# Support / Resistance
# ---------------------------------------------------------------------------

def compute_support_resistance(df: pd.DataFrame, lookback: int = 60) -> dict:
    """Compute basic support and resistance from recent swing highs/lows."""
    if df is None or df.empty or len(df) < 5:
        return {}

    recent = df.tail(lookback)
    support = float(recent["Low"].min())
    resistance = float(recent["High"].max())

    # Pivot-based S/R using last 20 bars
    pivot_df = df.tail(20)
    pivot = (
        pivot_df["High"].iloc[-1]
        + pivot_df["Low"].iloc[-1]
        + pivot_df["Close"].iloc[-1]
    ) / 3.0
    r1 = 2 * pivot - pivot_df["Low"].iloc[-1]
    s1 = 2 * pivot - pivot_df["High"].iloc[-1]

    return {
        "support": round(support, 2),
        "resistance": round(resistance, 2),
        "pivot": round(float(pivot), 2),
        "r1": round(float(r1), 2),
        "s1": round(float(s1), 2),
    }


def fetch_nse_sector_performance() -> pd.DataFrame:
    """
    Fetch historical daily data for key NSE sectoral indices from yfinance.
    Computes 1-day and 5-day percentage returns for each sector.
    Returns:
        pd.DataFrame sorted by 5-day performance.
    """
    sector_map = {
        "Nifty Bank": "^NSEBANK",
        "Nifty IT": "^CNXIT",
        "Nifty FMCG": "^CNXFMCG",
        "Nifty Pharma": "^CNXPHARMA",
        "Nifty Auto": "^CNXAUTO",
        "Nifty Metal": "^CNXMETAL",
        "Nifty Realty": "^CNXREALTY",
        "Nifty Fin Service": "^CNXFIN",
        "Nifty Media": "^CNXMEDIA",
        "Nifty Energy": "^CNXENERGY",
        "Nifty Infra": "^CNXINFRA",
        "Nifty PSU Bank": "^CNXPSUBANK"
    }
    
    tickers = list(sector_map.values())
    try:
        # Download last 10 days of daily data
        df = yf.download(tickers, period="15d", interval="1d", progress=False)
        if df.empty:
            logger.warning("No sector index data returned from yfinance.")
            return pd.DataFrame()
        if isinstance(df.columns, pd.MultiIndex):
            close_df = df["Close"]
        else:
            close_df = df["Close"] if "Close" in df.columns else df
        
        rows = []
        for name, ticker in sector_map.items():
            if ticker not in close_df.columns:
                continue
            
            series = close_df[ticker].dropna()
            if len(series) < 2:
                continue
                
            last_close = float(series.iloc[-1])
            prev_close = float(series.iloc[-2])
            
            # 1-day return
            change_1d = (last_close - prev_close) / prev_close * 100.0
            
            # 5-day return
            idx_5d = -min(6, len(series))
            prev_5d_close = float(series.iloc[idx_5d])
            change_5d = (last_close - prev_5d_close) / prev_5d_close * 100.0
            
            rows.append({
                "Sector": name,
                "Ticker": ticker,
                "Close": round(last_close, 2),
                "Change 1D%": round(change_1d, 2),
                "Change 5D%": round(change_5d, 2)
            })
            
        if not rows:
            return pd.DataFrame()
            
        res_df = pd.DataFrame(rows)
        # Sort by 5D performance descending
        return res_df.sort_values(by="Change 5D%", ascending=False).reset_index(drop=True)
        
    except Exception as e:
        logger.exception(f"Error fetching NIFTY sector performance: {e}")
        return pd.DataFrame()

def fetch_corporate_actions(symbol: str) -> str:
    """
    Fetch upcoming earnings and dividends within the next 30 days for a given stock.
    Returns a formatted warning string if corporate actions are found.
    """
    try:
        import yfinance as yf
        from datetime import datetime, date
        ticker = yf.Ticker(f"{symbol}.NS")
        cal = ticker.calendar
        if not cal:
            return ""
            
        warnings = []
        now_date = datetime.now().date()
        
        # 1. Earnings Date Check
        earnings_dates = cal.get("Earnings Date", [])
        if earnings_dates:
            for edate in earnings_dates:
                if isinstance(edate, date):
                    days_away = (edate - now_date).days
                    if 0 <= days_away <= 30:
                        warnings.append(f"Earnings in {days_away}d ({edate.strftime('%b %d')})")
        
        # 2. Ex-Dividend Date Check
        ex_div_date = cal.get("Ex-Dividend Date")
        if ex_div_date and isinstance(ex_div_date, date):
            days_away = (ex_div_date - now_date).days
            if 0 <= days_away <= 30:
                warnings.append(f"Dividend Ex-Date in {days_away}d ({ex_div_date.strftime('%b %d')})")
                
        if warnings:
            return "⚠️ " + " | ".join(warnings)
        return ""
    except Exception as e:
        logger.debug(f"Failed to fetch corporate actions for {symbol}: {e}")
        return ""
