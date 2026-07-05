from __future__ import annotations

import calendar
from datetime import datetime, timedelta
from typing import Dict, List

import pandas as pd
import yfinance as yf

from features.indicators import add_indicators_to_ohlc
from utils.logging import logger

# Comprehensive NIFTY universe — symbols kept as .NS for yfinance data pull,
# but stripped in display output
UNIVERSE_MAP: Dict[str, List[str]] = {
    "NIFTY 50": [
        "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS", "TCS.NS",
        "LT.NS", "SBIN.NS", "ITC.NS", "KOTAKBANK.NS", "AXISBANK.NS",
        "BEL.NS", "MARUTI.NS", "SUNPHARMA.NS", "TATAMOTORS.NS", "POWERGRID.NS",
        "HINDUNILVR.NS", "BAJFINANCE.NS", "NTPC.NS", "TITAN.NS", "WIPRO.NS",
        "HCLTECH.NS", "ONGC.NS", "BAJAJ-AUTO.NS", "M&M.NS", "COALINDIA.NS",
        "TECHM.NS", "JSWSTEEL.NS", "ADANIPORTS.NS", "GRASIM.NS", "HINDALCO.NS",
        "TATASTEEL.NS", "INDUSINDBK.NS", "ASIANPAINT.NS", "NESTLEIND.NS",
        "ULTRACEMCO.NS", "DRREDDY.NS", "CIPLA.NS", "BAJAJFINSV.NS", "DIVISLAB.NS",
        "TATACONSUM.NS", "HEROMOTOCO.NS", "UPL.NS", "BPCL.NS", "EICHERMOT.NS",
        "APOLLOHOSP.NS", "SBILIFE.NS", "HDFCLIFE.NS", "BRITANNIA.NS", "ADANIENT.NS",
        "SHRIRAMFIN.NS",
    ],
    "NIFTY 100": [
        "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS", "TCS.NS",
        "LT.NS", "SBIN.NS", "ITC.NS", "KOTAKBANK.NS", "AXISBANK.NS",
        "BEL.NS", "SUNPHARMA.NS", "TATAMOTORS.NS", "POWERGRID.NS", "ONGC.NS",
        "NTPC.NS", "COALINDIA.NS", "HCLTECH.NS", "WIPRO.NS", "HAL.NS",
        "HINDUNILVR.NS", "BAJFINANCE.NS", "TITAN.NS", "M&M.NS", "TECHM.NS",
        "JSWSTEEL.NS", "ADANIPORTS.NS", "GRASIM.NS", "HINDALCO.NS", "TATASTEEL.NS",
        "INDUSINDBK.NS", "ASIANPAINT.NS", "NESTLEIND.NS", "ULTRACEMCO.NS",
        "DRREDDY.NS", "CIPLA.NS", "BAJAJFINSV.NS", "DIVISLAB.NS", "TATACONSUM.NS",
        "HEROMOTOCO.NS", "UPL.NS", "BPCL.NS", "EICHERMOT.NS", "APOLLOHOSP.NS",
        "SBILIFE.NS", "HDFCLIFE.NS", "BRITANNIA.NS", "ADANIENT.NS", "SHRIRAMFIN.NS",
        "RECLTD.NS", "PFC.NS", "IRCTC.NS", "IRFC.NS", "BANKBARODA.NS", "PNB.NS",
        "BHARTIARTL.NS", "TATAPOWER.NS", "SIEMENS.NS", "HAVELLS.NS", "GODREJCP.NS",
        "DABUR.NS", "MARICO.NS", "PIDILITIND.NS", "BERGEPAINT.NS",
        "BAJAJHLDNG.NS", "MUTHOOTFIN.NS", "CHOLAFIN.NS",
    ],
    "NIFTY 200 (slower)": [
        "RELIANCE.NS", "HDFCBANK.NS", "ICICIBANK.NS", "INFY.NS", "TCS.NS",
        "LT.NS", "SBIN.NS", "ITC.NS", "KOTAKBANK.NS", "AXISBANK.NS",
        "BEL.NS", "SUNPHARMA.NS", "TATAMOTORS.NS", "POWERGRID.NS", "ONGC.NS",
        "NTPC.NS", "COALINDIA.NS", "HCLTECH.NS", "WIPRO.NS", "HAL.NS",
        "IRCTC.NS", "IRFC.NS", "BANKBARODA.NS", "PNB.NS", "BHARTIARTL.NS",
        "RECLTD.NS", "PFC.NS", "TATAPOWER.NS", "SIEMENS.NS", "HAVELLS.NS",
        "GODREJCP.NS", "DABUR.NS", "MARICO.NS", "PIDILITIND.NS",
        "MUTHOOTFIN.NS", "CHOLAFIN.NS", "TITAN.NS", "M&M.NS",
        "INDUSINDBK.NS", "ASIANPAINT.NS", "NESTLEIND.NS", "ULTRACEMCO.NS",
        "TATACONSUM.NS", "SHRIRAMFIN.NS", "ADANIENT.NS", "ADANIPORTS.NS",
        "LUPIN.NS", "AUROPHARMA.NS", "IPCALAB.NS", "ALKEM.NS", "GLENMARK.NS",
        "TVSMOTOR.NS", "ESCORTS.NS", "BALKRISIND.NS", "MRF.NS", "CEATLTD.NS",
        "GAIL.NS", "PETRONET.NS", "IGL.NS", "HINDPETRO.NS",
        "VEDL.NS", "SAIL.NS", "NMDC.NS", "HINDALCO.NS", "JSPL.NS",
        "DMART.NS", "TRENT.NS", "PAGEIND.NS",
        "COFORGE.NS", "MPHASIS.NS", "PERSISTENT.NS", "LTTS.NS", "TATAELXSI.NS",
        "CANBK.NS", "UNIONBANK.NS", "FEDERALBNK.NS", "IDFCFIRSTB.NS", "AUBANK.NS",
        "POLYCAB.NS", "CROMPTON.NS", "VOLTAS.NS",
        "DEEPAKNITR.NS", "TATACHEM.NS", "AARTIIND.NS", "NAVINFLUOR.NS",
        "MCX.NS", "BSE.NS", "CDSL.NS",
        "NCC.NS", "KEC.NS",
        "INDIGO.NS", "CONCOR.NS", "DELHIVERY.NS",
        "FORTIS.NS", "MAXHEALTH.NS",
        "LALPATHLAB.NS", "METROPOLIS.NS",
        "NYKAA.NS", "ZOMATO.NS", "PAYTM.NS", "INFOEDGE.NS",
    ],
}

# Lightweight sector tagging
SYMBOL_SECTOR_MAP: Dict[str, str] = {
    "BEL.NS": "Defence", "HAL.NS": "Defence", "BDL.NS": "Defence", "BEML.NS": "Defence",
    "BHEL.NS": "Capital Goods", "SIEMENS.NS": "Capital Goods", "ABB.NS": "Capital Goods",
    "CUMMINSIND.NS": "Capital Goods", "THERMAX.NS": "Capital Goods",
    "IRCTC.NS": "Railways", "IRFC.NS": "Railways", "RVNL.NS": "Railways", "RAILTEL.NS": "Railways",
    "SBIN.NS": "PSU Banks", "BANKBARODA.NS": "PSU Banks", "PNB.NS": "PSU Banks",
    "CANBK.NS": "PSU Banks", "UNIONBANK.NS": "PSU Banks",
    "POWERGRID.NS": "Energy", "ONGC.NS": "Energy", "NTPC.NS": "Energy",
    "RELIANCE.NS": "Energy", "COALINDIA.NS": "Energy", "TATAPOWER.NS": "Energy",
    "ADANIGREEN.NS": "Energy", "ADANIPOWER.NS": "Energy",
    "GAIL.NS": "Energy", "IGL.NS": "Energy", "MGL.NS": "Energy", "PETRONET.NS": "Energy",
    "INFY.NS": "IT", "TCS.NS": "IT", "HCLTECH.NS": "IT", "WIPRO.NS": "IT",
    "TECHM.NS": "IT", "COFORGE.NS": "IT", "MPHASIS.NS": "IT",
    "PERSISTENT.NS": "IT", "LTTS.NS": "IT", "TATAELXSI.NS": "IT",
    "OFSS.NS": "IT", "KPITTECH.NS": "IT",
    "SUNPHARMA.NS": "Pharma", "DRREDDY.NS": "Pharma", "CIPLA.NS": "Pharma",
    "DIVISLAB.NS": "Pharma", "LUPIN.NS": "Pharma", "AUROPHARMA.NS": "Pharma",
    "BIOCON.NS": "Pharma", "ALKEM.NS": "Pharma", "GLENMARK.NS": "Pharma",
    "LALPATHLAB.NS": "Diagnostics", "METROPOLIS.NS": "Diagnostics",
    "HDFCBANK.NS": "Private Banks", "ICICIBANK.NS": "Private Banks",
    "KOTAKBANK.NS": "Private Banks", "AXISBANK.NS": "Private Banks",
    "INDUSINDBK.NS": "Private Banks", "FEDERALBNK.NS": "Private Banks",
    "IDFCFIRSTB.NS": "Private Banks", "AUBANK.NS": "Private Banks",
    "HINDUNILVR.NS": "FMCG", "ITC.NS": "FMCG", "NESTLEIND.NS": "FMCG",
    "BRITANNIA.NS": "FMCG", "DABUR.NS": "FMCG", "MARICO.NS": "FMCG",
    "GODREJCP.NS": "FMCG", "COLPAL.NS": "FMCG", "EMAMILTD.NS": "FMCG",
    "LT.NS": "Infra", "NCC.NS": "Infra", "KEC.NS": "Infra",
    "TATAMOTORS.NS": "Auto", "MARUTI.NS": "Auto", "M&M.NS": "Auto",
    "BAJAJ-AUTO.NS": "Auto", "HEROMOTOCO.NS": "Auto",
    "TVSMOTOR.NS": "Auto", "EICHERMOT.NS": "Auto", "ESCORTS.NS": "Auto",
    "BALKRISIND.NS": "Auto Ancillary", "MRF.NS": "Auto Ancillary",
    "CEATLTD.NS": "Auto Ancillary", "APOLLOTYRE.NS": "Auto Ancillary",
    "ADANIPORTS.NS": "Logistics", "CONCOR.NS": "Logistics", "DELHIVERY.NS": "Logistics",
    "JSWSTEEL.NS": "Metals", "TATASTEEL.NS": "Metals", "HINDALCO.NS": "Metals",
    "VEDL.NS": "Metals", "SAIL.NS": "Metals", "NMDC.NS": "Metals", "JSPL.NS": "Metals",
    "ASIANPAINT.NS": "Paints", "BERGEPAINT.NS": "Paints", "PIDILITIND.NS": "Chemicals",
    "DEEPAKNITR.NS": "Chemicals", "TATACHEM.NS": "Chemicals", "AARTIIND.NS": "Chemicals",
    "ULTRACEMCO.NS": "Cement", "GRASIM.NS": "Cement",
    "TITAN.NS": "Consumer", "TRENT.NS": "Retail", "DMART.NS": "Retail",
    "ZOMATO.NS": "Food Tech", "INDIGO.NS": "Aviation",
    "BHARTIARTL.NS": "Telecom", "TATACOMM.NS": "Telecom",
    "MCX.NS": "Capital Markets", "BSE.NS": "Capital Markets", "CDSL.NS": "Capital Markets",
    "BAJFINANCE.NS": "NBFC", "BAJAJFINSV.NS": "NBFC", "MUTHOOTFIN.NS": "NBFC",
    "CHOLAFIN.NS": "NBFC", "SHRIRAMFIN.NS": "NBFC",
    "SBILIFE.NS": "Insurance", "HDFCLIFE.NS": "Insurance",
    "RECLTD.NS": "PSU Finance", "PFC.NS": "PSU Finance",
    "HAVELLS.NS": "Electricals", "POLYCAB.NS": "Electricals", "CROMPTON.NS": "Electricals",
    "VOLTAS.NS": "Consumer Durables",
    "FORTIS.NS": "Healthcare", "MAXHEALTH.NS": "Healthcare",
    "APOLLOHOSP.NS": "Healthcare",
}

# Friendly names for display (strip .NS/.BO internally)
_DISPLAY_NAMES: Dict[str, str] = {
    "RELIANCE": "Reliance Industries", "TCS": "Tata Consultancy Services",
    "HDFCBANK": "HDFC Bank", "ICICIBANK": "ICICI Bank", "INFY": "Infosys",
    "ITC": "ITC Limited", "SBIN": "State Bank of India",
    "KOTAKBANK": "Kotak Mahindra Bank", "AXISBANK": "Axis Bank",
    "LT": "Larsen & Toubro", "HINDUNILVR": "Hindustan Unilever",
    "BAJFINANCE": "Bajaj Finance", "MARUTI": "Maruti Suzuki",
    "ONGC": "Oil & Natural Gas Corp", "HCLTECH": "HCL Technologies",
    "SUNPHARMA": "Sun Pharma", "ASIANPAINT": "Asian Paints",
    "NTPC": "NTPC", "TITAN": "Titan Company",
    "ULTRACEMCO": "UltraTech Cement", "TATAMOTORS": "Tata Motors",
    "M&M": "Mahindra & Mahindra", "POWERGRID": "Power Grid Corp",
    "WIPRO": "Wipro", "BAJAJFINSV": "Bajaj Finserv",
    "NESTLEIND": "Nestle India", "COALINDIA": "Coal India",
    "TECHM": "Tech Mahindra", "JSWSTEEL": "JSW Steel",
    "ADANIPORTS": "Adani Ports", "HINDALCO": "Hindalco",
    "GRASIM": "Grasim Industries", "TATASTEEL": "Tata Steel",
    "INDUSINDBK": "IndusInd Bank", "SBILIFE": "SBI Life Insurance",
    "HDFCLIFE": "HDFC Life", "BRITANNIA": "Britannia Industries",
    "BAJAJ-AUTO": "Bajaj Auto", "APOLLOHOSP": "Apollo Hospitals",
    "DRREDDY": "Dr. Reddy's", "CIPLA": "Cipla",
    "EICHERMOT": "Eicher Motors", "DIVISLAB": "Divi's Labs",
    "TATACONSUM": "Tata Consumer", "HEROMOTOCO": "Hero MotoCorp",
    "UPL": "UPL", "BPCL": "Bharat Petroleum",
    "SHRIRAMFIN": "Shriram Finance", "ADANIENT": "Adani Enterprises",
    "BEL": "Bharat Electronics", "HAL": "Hindustan Aeronautics",
    "IRCTC": "Indian Railway Catering", "IRFC": "Indian Railway Finance",
    "RVNL": "Rail Vikas Nigam", "RAILTEL": "RailTel Corp",
    "BANKBARODA": "Bank of Baroda", "PNB": "Punjab National Bank",
    "CANBK": "Canara Bank", "UNIONBANK": "Union Bank",
    "FEDERALBNK": "Federal Bank", "IDFCFIRSTB": "IDFC First Bank",
    "AUBANK": "AU Small Finance Bank",
    "BHARTIARTL": "Bharti Airtel", "GAIL": "GAIL India",
    "IGL": "Indraprastha Gas", "PETRONET": "Petronet LNG",
    "HINDPETRO": "Hindustan Petroleum",
    "RECLTD": "REC Limited", "PFC": "Power Finance Corp",
    "VEDL": "Vedanta", "SAIL": "SAIL", "NMDC": "NMDC", "JSPL": "Jindal Steel & Power",
    "HAVELLS": "Havells India", "POLYCAB": "Polycab India",
    "CROMPTON": "Crompton Greaves Consumer", "VOLTAS": "Voltas",
    "MCX": "Multi Commodity Exchange", "BSE": "BSE", "CDSL": "CDSL",
    "MUTHOOTFIN": "Muthoot Finance", "CHOLAFIN": "Cholamandalam Investment",
    "TATAPOWER": "Tata Power", "ADANIGREEN": "Adani Green Energy",
    "LUPIN": "Lupin", "AUROPHARMA": "Aurobindo Pharma",
    "ALKEM": "Alkem Laboratories", "GLENMARK": "Glenmark Pharma",
    "LALPATHLAB": "Dr Lal PathLabs", "METROPOLIS": "Metropolis Healthcare",
    "TVSMOTOR": "TVS Motor", "ESCORTS": "Escorts Kubota",
    "BALKRISIND": "Balkrishna Industries", "MRF": "MRF",
    "CEATLTD": "CEAT", "APOLLOTYRE": "Apollo Tyres",
    "COFORGE": "Coforge", "MPHASIS": "Mphasis", "PERSISTENT": "Persistent Systems",
    "LTTS": "L&T Technology Services", "TATAELXSI": "Tata Elxsi",
    "DEEPAKNITR": "Deepak Nitrite", "TATACHEM": "Tata Chemicals",
    "AARTIIND": "Aarti Industries", "NAVINFLUOR": "Navin Fluorine",
    "DMART": "D-Mart (Avenue Supermarts)", "TRENT": "Trent",
    "ZOMATO": "Zomato", "PAYTM": "Paytm", "INFOEDGE": "Info Edge (Naukri)",
    "NYKAA": "Nykaa", "DABUR": "Dabur India", "MARICO": "Marico",
    "GODREJCP": "Godrej Consumer Products", "PIDILITIND": "Pidilite Industries",
    "BERGEPAINT": "Berger Paints", "SIEMENS": "Siemens India",
    "CONCOR": "Container Corp", "DELHIVERY": "Delhivery",
    "FORTIS": "Fortis Healthcare", "MAXHEALTH": "Max Healthcare",
    "INDIGO": "IndiGo (InterGlobe Aviation)",
    "NCC": "NCC Limited", "KEC": "KEC International",
}


def _bare(sym: str) -> str:
    """Strip .NS / .BO suffix."""
    return sym.replace(".NS", "").replace(".BO", "")


def _display(sym: str) -> str:
    """Return 'SYMBOL (Full Name)' or just 'SYMBOL'."""
    bare = _bare(sym)
    name = _DISPLAY_NAMES.get(bare)
    return f"{bare} ({name})" if name else bare


def _flatten_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Flatten multi-level column headers produced by recent yfinance versions."""
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] if isinstance(col, tuple) else col for col in df.columns]
    return df


def _get_news_sentiment_score(symbol_bare: str) -> tuple[float, str]:
    """
    Fetch latest news for the stock and return (sentiment_boost, headline).
    Returns (+1.0, headline) for positive sentiment, (-1.0, headline) for negative, (0, '') if unavailable.
    """
    POSITIVE_WORDS = {
        "surges", "rally", "beats", "gains", "upgrade", "outperform", "record",
        "profit", "growth", "buy", "bullish", "strong", "positive", "win", "order",
        "contract", "expansion", "target raised", "delivered", "milestone",
    }
    NEGATIVE_WORDS = {
        "falls", "drops", "crash", "miss", "downgrade", "underperform", "losses",
        "weak", "bearish", "sell", "concern", "risk", "fraud", "delay", "penalty",
        "fine", "lawsuit", "warning", "caution", "cut", "sell-off",
    }
    try:
        ticker = yf.Ticker(f"{symbol_bare}.NS")
        news_data = ticker.news
        if not news_data:
            ticker = yf.Ticker(symbol_bare)
            news_data = ticker.news
        if not news_data:
            return 0.0, ""

        n = news_data[0]
        content = n.get("content", n)
        if isinstance(content, dict):
            title = content.get("title", n.get("title", "")).lower()
        else:
            title = n.get("title", "").lower()

        if not title:
            return 0.0, ""

        pos = sum(1 for w in POSITIVE_WORDS if w in title)
        neg = sum(1 for w in NEGATIVE_WORDS if w in title)
        boost = 0.0
        if pos > neg:
            boost = 1.0
        elif neg > pos:
            boost = -1.0
        return boost, title[:100]
    except Exception:
        return 0.0, ""


def _compute_intraday_score(df: pd.DataFrame) -> float:
    if df is None or df.empty:
        return 0.0

    score = 0.0

    rsi = df["RSI_14"].iloc[-1] if "RSI_14" in df.columns else None
    if rsi is not None and pd.notna(rsi) and 55 <= float(rsi) <= 75:
        score += 2.0

    if "VOLUME_SPIKE" in df.columns:
        vol_spike = df["VOLUME_SPIKE"].iloc[-1]
        if pd.notna(vol_spike) and int(vol_spike):
            score += 2.0

    close = df["Close"].iloc[-1] if "Close" in df.columns else None
    vwap = df["VWAP"].iloc[-1] if "VWAP" in df.columns else None
    if close is not None and vwap is not None and pd.notna(close) and pd.notna(vwap):
        if float(close) > float(vwap):
            score += 1.5

    macd_hist = df["MACD_HIST"].iloc[-1] if "MACD_HIST" in df.columns else None
    if macd_hist is not None and pd.notna(macd_hist) and float(macd_hist) > 0:
        score += 1.0

    close_val = float(close) if close is not None else 0.0
    sma20 = df["SMA_20"].iloc[-1] if "SMA_20" in df.columns else None
    sma50 = df["SMA_50"].iloc[-1] if "SMA_50" in df.columns else None
    if sma20 is not None and pd.notna(sma20) and close_val > float(sma20):
        score += 0.5
    if sma20 is not None and sma50 is not None and pd.notna(sma20) and pd.notna(sma50):
        if float(sma20) > float(sma50):
            score += 0.5  # Golden cross bonus

    return float(score)


def _estimate_probable_profit(df: pd.DataFrame, score: float, week_trend: str) -> tuple[float, float]:
    """
    Estimate intraday/short-term probable profit range (%) using ATR and trend.
    Returns (min_profit%, max_profit%) — not a guarantee.
    """
    if df is None or df.empty:
        return 0.0, 0.0
    try:
        close = float(df["Close"].iloc[-1])
        atr = float(df["ATR_14"].iloc[-1]) if "ATR_14" in df.columns else 0.0
        if atr == 0 or close == 0:
            return 0.0, 0.0

        atr_pct = (atr / close) * 100.0
        # Scale by score (max 7) and trend
        trend_multiplier = {"Bullish": 1.2, "Sideways": 0.7, "Bearish": 0.3}.get(week_trend, 0.7)
        score_factor = min(score / 7.0, 1.0)

        base_profit = atr_pct * score_factor * trend_multiplier
        return round(base_profit * 0.5, 1), round(base_profit * 1.3, 1)
    except Exception:
        return 0.0, 0.0


def _get_week_trend(df: pd.DataFrame) -> str:
    """Determine weekly trend from SMA20 vs SMA50 and 5-day momentum."""
    if df is None or df.empty or len(df) < 5:
        return "Sideways"
    try:
        close = float(df["Close"].iloc[-1])
        close_5d_ago = float(df["Close"].iloc[-min(5, len(df) - 1)])
        momentum_5d = (close - close_5d_ago) / close_5d_ago * 100

        sma20 = df["SMA_20"].iloc[-1] if "SMA_20" in df.columns else None
        sma50 = df["SMA_50"].iloc[-1] if "SMA_50" in df.columns else None

        if sma20 is not None and sma50 is not None and pd.notna(sma20) and pd.notna(sma50):
            if float(sma20) > float(sma50) and momentum_5d > 0:
                return "Bullish"
            elif float(sma20) < float(sma50) and momentum_5d < 0:
                return "Bearish"
        return "Sideways"
    except Exception:
        return "Sideways"


def scan_intraday_momentum_stocks(
    universe: str,
    top_n: int = 15,
) -> pd.DataFrame:
    symbols = UNIVERSE_MAP.get(universe, [])
    if not symbols:
        return pd.DataFrame()

    end = datetime.now().date()
    start = end - timedelta(days=60)

    import time

    rows = []
    for symbol in symbols:
        try:
            time.sleep(0.3)  # Rate limit Yahoo Finance calls
            df = yf.download(
                symbol,
                start=start,
                end=end,
                interval="1d",
                progress=False,
                auto_adjust=False,
            )
            if df is None or df.empty:
                continue
            df = _flatten_columns(df)
            df = df.rename(columns={"Adj Close": "AdjClose"})
            df = add_indicators_to_ohlc(df)
            score = _compute_intraday_score(df)
            week_trend = _get_week_trend(df)

            # News sentiment
            bare = _bare(symbol)
            news_boost, news_headline = _get_news_sentiment_score(bare)
            score += news_boost
            score = max(0.0, round(score, 2))

            # Probable profit estimate
            min_profit, max_profit = _estimate_probable_profit(df, score, week_trend)

            last_close = float(df["Close"].iloc[-1])
            prev_close = float(df["Close"].iloc[-2]) if len(df) >= 2 else last_close
            change_pct = (last_close - prev_close) / prev_close * 100.0 if prev_close > 0 else 0.0

            rows.append(
                {
                    "Symbol": _display(symbol),
                    "Sector": SYMBOL_SECTOR_MAP.get(symbol, "Other"),
                    "Trend": week_trend,
                    "Score": score,
                    "Close (₹)": round(last_close, 2),
                    "Change%": round(change_pct, 2),
                    "RSI": round(float(df["RSI_14"].iloc[-1]) if "RSI_14" in df.columns else 0.0, 1),
                    "VWAP": round(float(df["VWAP"].iloc[-1]) if "VWAP" in df.columns else 0.0, 2),
                    "Vol Spike": "⚡ Yes" if (df["VOLUME_SPIKE"].iloc[-1] if "VOLUME_SPIKE" in df.columns else False) else "No",
                    "Profit Est%": f"{min_profit}–{max_profit}%",
                    "Latest News": news_headline if news_headline else "—",
                }
            )
        except Exception as exc:
            logger.exception(f"Intraday scan failed for {symbol}: {exc}")
            continue

    if not rows:
        return pd.DataFrame()

    df_all = pd.DataFrame(rows)
    df_all = df_all.sort_values("Score", ascending=False).head(top_n)
    return df_all.reset_index(drop=True)


def compute_sector_rotation(universe: str = "NIFTY 100") -> pd.DataFrame:
    """
    Compute sector strength based on 5-day % change grouped by sector.
    """
    symbols = UNIVERSE_MAP.get(universe, [])
    if not symbols:
        return pd.DataFrame()

    end = datetime.now().date()
    start = end - timedelta(days=15)

    import time

    rows = []
    for symbol in symbols:
        try:
            time.sleep(0.3)  # Rate limit Yahoo Finance calls
            df = yf.download(
                symbol,
                start=start,
                end=end,
                interval="1d",
                progress=False,
                auto_adjust=False,
            )
            if df is None or df.empty or len(df) < 2:
                continue
            df = _flatten_columns(df)
            close = df["Close"]
            change_5d = (
                float(close.iloc[-1]) - float(close.iloc[-min(5, len(close) - 1)])
            ) / float(close.iloc[-min(5, len(close) - 1)]) * 100
            rows.append(
                {
                    "Symbol": _display(symbol),
                    "Sector": SYMBOL_SECTOR_MAP.get(symbol, "Other"),
                    "5d_Change%": round(change_5d, 2),
                }
            )
        except Exception as exc:
            logger.exception(f"Sector scan failed for {symbol}: {exc}")
            continue

    if not rows:
        return pd.DataFrame()

    df_all = pd.DataFrame(rows)
    sector_strength = (
        df_all.groupby("Sector")["5d_Change%"]
        .mean()
        .reset_index()
        .sort_values("5d_Change%", ascending=False)
        .rename(columns={"5d_Change%": "Avg 5-day Return %"})
    )
    return sector_strength
