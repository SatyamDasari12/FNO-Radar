"""
Options Analysis Service — NSE F&O Call Buying Strategy (Advanced)
===================================================================
Implements the full 6-layer strategy from NSE_FO_Call_Buying_Strategy_Advanced.md

Layer 1 — Hard Filters (pre-qualification):
  • Volume ≥ 1.2× 20-day average
  • Close > 20 DMA
  • ATR(14)/Price ≥ 1.5%
  • 3-day price gain ≤ 8%
  • IV rank in [25, 65]

Layer 2 — Indicator Normalization (0–100):
  A. Momentum Score     (5-day % gain, normalised)          → 25%
  B. Breakout Strength  (close vs. 10-day highest high)     → 15%
  C. Volume Expansion   (today vs 20-day avg)               → 15%
  D. OI Long Buildup    (OI change, price↑ required)        → 15%
  E. RSI Zone Score     (ideal 45–65)                       → 10%
  F. IV Sweet Spot      (ideal rank 30–60)                  → 10%
  G. Nifty Alignment    (NIFTY50 > its 20 DMA)              → 10%

Layer 3 — Final Composite Score (0–100), select Top-N.

Layer 4 — Contract Selection:
  • Strike where 0.40 ≤ BS-Delta ≤ 0.55
  • Daily Theta ≤ 0.5% of option premium
  • Reward/Risk ≥ 1.8 (reward = target×delta, risk = premium×0.30)

Layer 5 — Exit signals included in output.

Layer 6 — Enhancements:
  • Relative Strength vs Nifty (10-day): +5 pts if RS > 0
  • Nifty alignment bonus already in Layer 2.
"""
from __future__ import annotations

import calendar
import json
import math
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests
import yfinance as yf

from utils.logging import logger

# ── Paths ─────────────────────────────────────────────────────────────────────
_DATA_DIR = "data"
_FNO_MASTER_FILE = os.path.join(_DATA_DIR, "fno_master.json")

# ── NSE API headers ───────────────────────────────────────────────────────────
_NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
}

# ── Nifty 50 historical cache ─────────────────────────────────────────────────
_nifty_hist_cache: Optional[pd.DataFrame] = None

# ── OI data cache (symbol → {oi, oi_change_pct, fetched}) ─────────────────────
_oi_cache: Dict[str, Dict] = {}


def _get_nifty_hist() -> pd.DataFrame:
    global _nifty_hist_cache
    if _nifty_hist_cache is not None:
        return _nifty_hist_cache
    try:
        t = yf.Ticker("^NSEI")
        h = t.history(period="90d", auto_adjust=False)
        if isinstance(h.columns, pd.MultiIndex):
            h.columns = [c[0] for c in h.columns]
        _nifty_hist_cache = h
        return h
    except Exception:
        return pd.DataFrame()


# ── Hardcoded fallback F&O list ───────────────────────────────────────────────
_HARDCODED_FNO_STOCKS: List[str] = [
    "360ONE", "ABB", "ABCAPITAL", "ADANIENT", "ADANIGREEN", "ADANIPORTS",
    "ALKEM", "AMBER", "AMBUJACEM", "ANGELONE", "APLAPOLLO", "APOLLOHOSP",
    "ASHOKLEY", "ASIANPAINT", "ASTRAL", "AUBANK", "AUROPHARMA", "AXISBANK",
    "BAJAJ-AUTO", "BAJAJFINSV", "BAJAJHLDNG", "BAJFINANCE", "BANDHANBNK",
    "BANKBARODA", "BANKINDIA", "BDL", "BEL", "BHARATFORG", "BHARTIARTL",
    "BHEL", "BIOCON", "BLUESTARCO", "BOSCHLTD", "BPCL", "BRITANNIA", "BSE",
    "CAMS", "CANBK", "CDSL", "CGPOWER", "CHOLAFIN", "CIPLA", "COALINDIA",
    "COFORGE", "COLPAL", "CONCOR", "CROMPTON", "CUMMINSIND", "DABUR",
    "DALBHARAT", "DELHIVERY", "DIVISLAB", "DIXON", "DLF", "DMART", "DRREDDY",
    "EICHERMOT", "EXIDEIND", "FEDERALBNK", "FORTIS", "GAIL", "GLENMARK",
    "GMRAIRPORT", "GODREJCP", "GODREJPROP", "GRASIM", "HAL", "HAVELLS",
    "HCLTECH", "HDFCAMC", "HDFCBANK", "HDFCLIFE", "HEROMOTOCO", "HINDALCO",
    "HINDPETRO", "HINDUNILVR", "ICICIBANK", "ICICIGI", "ICICIPRULI",
    "IDBI", "IDFCFIRSTB", "IEX", "IGL", "INDHOTEL", "INDIGO", "INDUSINDBK",
    "INDUSTOWER", "INFY", "IOC", "IPCALAB", "IRCTC", "IRFC",
    "ITC", "JKCEMENT", "JSWSTEEL", "JUBLFOOD", "KALYANKJIL",
    "KOTAKBANK", "L&TFH", "LALPATHLAB", "LT", "LTTS", "LUPIN",
    "M&M", "M&MFIN", "MARICO", "MARUTI", "MAXHEALTH",
    "MCDOWELL-N", "MCX", "METROPOLIS", "MFSL", "MOTHERSON",
    "MPHASIS", "MRF", "MUTHOOTFIN", "NATIONALUM", "NAUKRI",
    "NBCC", "NCC", "NESTLEIND", "NMDC", "NTPC", "OBEROIRLTY",
    "OFSS", "ONGC", "PAGEIND", "PEL", "PERSISTENT",
    "PFC", "PIDILITIND", "PNB", "POLYCAB", "POWERGRID",
    "PVRINOX", "RECLTD", "RELIANCE", "RVNL", "SAIL", "SBICARD",
    "SBILIFE", "SBIN", "SHRIRAMFIN", "SIEMENS", "SONACOMS",
    "SUNPHARMA", "SUNTV", "TATACHEM", "TATACOMM", "TATACONSUM",
    "TATAELXSI", "TATAMOTORS", "TATAPOWER", "TATASTEEL", "TCS",
    "TECHM", "TIINDIA", "TITAN", "TORNTPHARM", "TRENT",
    "TVSMOTOR", "UBL", "ULTRACEMCO", "UNIONBANK", "UPL",
    "VEDL", "VOLTAS", "WIPRO", "YESBANK", "ZOMATO", "ZYDUSLIFE",
    "ADANIENSOL", "APOLLOTYRE", "MAZDOCK", "IREDA", "HUDCO", "ETERNAL",
]

# ── In-memory cache ───────────────────────────────────────────────────────────
_fno_master_cache: Optional[List[Dict]] = None


def load_fno_master() -> List[Dict]:
    """
    Load NSE F&O master from data/fno_master.json.
    All returned entries are guaranteed to have exchange == "NSE".
    Falls back to NSE live API, then hardcoded list.
    BSE stocks are never included.
    """
    global _fno_master_cache
    if _fno_master_cache is not None:
        return _fno_master_cache

    if os.path.exists(_FNO_MASTER_FILE):
        try:
            with open(_FNO_MASTER_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list) and len(data) > 50:
                # ── NSE-only guard: drop any non-NSE entries ──────────────
                nse_only = [e for e in data if str(e.get("exchange", "NSE")).upper() == "NSE"]
                dropped = len(data) - len(nse_only)
                if dropped:
                    logger.warning(
                        f"Dropped {dropped} non-NSE entries from fno_master.json. "
                        "Re-run scripts/refresh_fno_master.py to fix the master."
                    )
                _fno_master_cache = nse_only
                logger.info(
                    f"F&O master loaded: {len(nse_only)} NSE stocks "
                    f"(from {_FNO_MASTER_FILE})"
                )
                return _fno_master_cache
        except Exception as exc:
            logger.warning(f"Failed to load fno_master.json: {exc}")

    # ── Live fallback: NSE Securities-in-F&O index ────────────────────────
    _nse_fo_url = (
        "https://www.nseindia.com/api/equity-stockIndices"
        "?index=SECURITIES%20IN%20F%26O"
    )
    for url in [_nse_fo_url, "https://www.nseindia.com/api/master-quote"]:
        try:
            r = requests.get(url, headers=_NSE_HEADERS, timeout=8)
            if r.status_code != 200:
                continue
            payload = r.json()
            # Securities-in-F&O returns {data: [{symbol:...}, ...]}
            # master-quote returns ["SYM1", "SYM2", ...]
            if isinstance(payload, dict) and "data" in payload:
                symbols = sorted({
                    str(d["symbol"]).strip().upper()
                    for d in payload["data"]
                    if d.get("symbol") and d["symbol"] != "SECURITIES IN F&O"
                })
            elif isinstance(payload, list):
                symbols = sorted({str(s).strip().upper() for s in payload if s})
            else:
                continue
            if len(symbols) > 50:
                _fno_master_cache = [
                    {"symbol": s, "name": s, "lot_size": 0, "exchange": "NSE"}
                    for s in symbols
                ]
                logger.info(f"F&O master from live NSE API: {len(symbols)} stocks")
                return _fno_master_cache
        except Exception:
            continue

    # ── Ultimate hardcoded fallback ───────────────────────────────────────
    _fno_master_cache = [
        {"symbol": s, "name": s, "lot_size": 0, "exchange": "NSE"}
        for s in _HARDCODED_FNO_STOCKS
    ]
    logger.warning("F&O master using hardcoded fallback list")
    return _fno_master_cache


def get_fno_stock_list() -> List[str]:
    return [e["symbol"] for e in load_fno_master()]


def get_fno_master_map() -> Dict[str, Dict]:
    return {e["symbol"]: e for e in load_fno_master()}


# ── Month helpers ─────────────────────────────────────────────────────────────

def _last_thursday_of_month(year: int, month: int) -> datetime:
    last_day = calendar.monthrange(year, month)[1]
    d = datetime(year, month, last_day)
    while d.weekday() != 3:
        d -= timedelta(days=1)
    return d


def get_month_options() -> List[Tuple[str, int, int]]:
    now = datetime.now()
    result = []
    for offset in range(5):
        m = now.month + offset
        y = now.year + (m - 1) // 12
        m = (m - 1) % 12 + 1
        approx = _last_thursday_of_month(y, m)
        if approx.date() >= now.date():
            label = datetime(y, m, 1).strftime("%B %Y")
            result.append((label, y, m))
    return result


def _find_month_expiry(ticker: Optional[Any], year: int, month: int) -> Optional[str]:
    """
    Return the NSE F&O expiry date for the given month.

    NSE stock options expire on the LAST THURSDAY of the expiry month.
    We use this as the definitive formula — yfinance option dates are NOT
    used because they reflect Yahoo Finance's cache which can be BSE-aligned
    or stale for Indian F&O contracts.

    If the computed Thursday is in the past (month already expired), return None.
    """
    expiry_dt = _last_thursday_of_month(year, month)
    today = datetime.now().date()
    # Allow the expiry day itself (last day to trade)
    if expiry_dt.date() < today:
        return None
    return expiry_dt.strftime("%Y-%m-%d")


# ── Strike / contract ─────────────────────────────────────────────────────────

def _strike_step(spot: float) -> float:
    if spot < 100:      return 5.0
    elif spot < 250:    return 10.0
    elif spot < 500:    return 25.0
    elif spot < 1000:   return 50.0
    elif spot < 2500:   return 100.0
    elif spot < 5000:   return 200.0
    elif spot < 10000:  return 500.0
    else:               return 1000.0


def _contract_name(symbol: str, expiry_str: str, strike: float, opt_type: str = "CE") -> str:
    dt = datetime.strptime(expiry_str, "%Y-%m-%d")
    month_abbr = dt.strftime("%b").upper()
    strike_str = f"{int(strike)}" if strike == int(strike) else f"{strike:.1f}"
    return f"{symbol} {month_abbr} {strike_str} {opt_type}"


# ── Black-Scholes (call price, delta, theta) ──────────────────────────────────

def _norm_cdf(x: float) -> float:
    return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0


def _norm_pdf(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)


def black_scholes_call(S: float, K: float, T: float, r: float, sigma: float) -> float:
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return max(S - K, 0.0)
    try:
        d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)
        return max(S * _norm_cdf(d1) - K * math.exp(-r * T) * _norm_cdf(d2), 0.0)
    except Exception:
        return max(S - K, 0.0)

def black_scholes_put(S: float, K: float, T: float, r: float, sigma: float) -> float:
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return max(K - S, 0.0)
    try:
        d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)
        return max(K * math.exp(-r * T) * _norm_cdf(-d2) - S * _norm_cdf(-d1), 0.0)
    except Exception:
        return max(K - S, 0.0)


def _bs_greeks(S: float, K: float, T: float, r: float, sigma: float) -> Tuple[float, float, float]:
    """Returns (price, delta, daily_theta)."""
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return max(S - K, 0.0), 1.0 if S > K else 0.0, 0.0
    try:
        d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)
        price = S * _norm_cdf(d1) - K * math.exp(-r * T) * _norm_cdf(d2)
        delta = _norm_cdf(d1)
        # Theta (per year) → daily
        theta_annual = (
            -(S * _norm_pdf(d1) * sigma) / (2 * math.sqrt(T))
            - r * K * math.exp(-r * T) * _norm_cdf(d2)
        )
        daily_theta = theta_annual / 365.0
        return max(price, 0.0), delta, daily_theta
    except Exception:
        return max(S - K, 0.0), 0.5, 0.0


def _estimate_volatility(hist: pd.DataFrame) -> float:
    try:
        closes = hist["Close"].dropna()
        if len(closes) < 5:
            return 0.30
        log_rets = (closes / closes.shift(1)).apply(math.log).dropna()
        return float(min(max(log_rets.std() * math.sqrt(252), 0.05), 2.5))
    except Exception:
        return 0.30


def _estimate_iv_rank(sigma: float, hist: pd.DataFrame) -> float:
    """
    Proxy IV Rank: compare current HV (30-day) against its 52-week range.
    Returns a 0-100 rank.
    """
    try:
        closes = hist["Close"].dropna()
        if len(closes) < 30:
            return 50.0
        # Rolling 10-day HV as proxy for option IV series
        log_rets = (closes / closes.shift(1)).apply(math.log)
        rolling_hv = log_rets.rolling(10).std() * math.sqrt(252)
        rolling_hv = rolling_hv.dropna()
        if len(rolling_hv) < 10:
            return 50.0
        hv_min = float(rolling_hv.min())
        hv_max = float(rolling_hv.max())
        current_hv = float(rolling_hv.iloc[-1])
        if hv_max == hv_min:
            return 50.0
        return round(((current_hv - hv_min) / (hv_max - hv_min)) * 100, 1)
    except Exception:
        return 50.0


# ── News sentiment ─────────────────────────────────────────────────────────────

_POSITIVE_WORDS = {
    "surge", "rally", "beats", "gain", "upgrade", "outperform", "record",
    "profit", "growth", "buy", "bullish", "strong", "positive", "win", "order",
    "contract", "expansion", "raised", "delivered", "milestone", "boost",
    "jump", "soar", "breakout", "target", "momentum",
}
_NEGATIVE_WORDS = {
    "fall", "drop", "crash", "miss", "downgrade", "underperform", "loss",
    "weak", "bearish", "sell", "concern", "risk", "fraud", "delay", "penalty",
    "fine", "lawsuit", "warning", "caution", "cut", "selloff", "probe",
    "decline", "slump", "below", "disappoint",
}


def _get_news_sentiment(symbol: str) -> Tuple[float, str]:
    """
    Fetch news for the NSE symbol and score sentiment.
    BSE-specific articles (containing 'bom:', '.bo', 'bse:', 'sensex') are
    filtered out so only NSE-relevant news influences the score.
    """
    try:
        ticker = yf.Ticker(f"{symbol}.NS")
        news = ticker.news
        if not news:
            return 0.0, ""
        scores = []
        headlines = []

        # Keywords that identify BSE-specific content (not relevant for NSE analysis)
        _BSE_MARKERS = ("bom:", "bse:", ".bo ", "(bse", "sensex", "bombay stock")

        for article in news[:8]:   # scan more articles to find NSE-relevant ones
            content = article.get("content", article)
            title = (
                content.get("title", "") if isinstance(content, dict)
                else article.get("title", "")
            ).lower()
            if not title:
                continue

            # Skip articles that are BSE-specific
            if any(marker in title for marker in _BSE_MARKERS):
                continue

            headlines.append(title[:80])
            pos = sum(1 for w in _POSITIVE_WORDS if w in title)
            neg = sum(1 for w in _NEGATIVE_WORDS if w in title)
            scores.append(1.0 if pos > neg else (-1.0 if neg > pos else 0.0))

            if len(scores) >= 5:   # enough articles scored
                break

        avg = (sum(scores) / len(scores)) if scores else 0.0
        return round(avg, 2), headlines[0] if headlines else ""
    except Exception:
        return 0.0, ""


# ── NSE live option LTP ───────────────────────────────────────────────────────

_nse_session = requests.Session()
_nse_session_warmed: bool = False
_nse_session_last_warm: float = 0.0   # epoch seconds of last successful warm
_NSE_SESSION_TTL: float = 300.0       # re-warm every 5 minutes



def _warm_nse_session(force: bool = False) -> None:
    """
    3-step NSE cookie chain:
      1. Homepage       — sets _ga, nsit, nseappid cookies
      2. Derivatives page — sets additional cookies for API access
      3. master-quote API — confirms session is live

    Re-warms if TTL expired (5 min) or if force=True.
    Works both during market hours AND after hours.
    """
    global _nse_session_warmed, _nse_session_last_warm
    import time
    now = time.time()
    if not force and _nse_session_warmed and (now - _nse_session_last_warm) < _NSE_SESSION_TTL:
        return
    _nse_session_warmed = False
    try:
        html_headers = {**_NSE_HEADERS, "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9"}
        # Step 1: Homepage
        _nse_session.get("https://www.nseindia.com", headers=html_headers, timeout=8)
        # Step 2: Derivatives page (sets more F&O-specific cookies)
        _nse_session.get(
            "https://www.nseindia.com/market-data/equity-derivatives-watch",
            headers=html_headers, timeout=8,
        )
        # Step 3: API warm-up
        r = _nse_session.get(
            "https://www.nseindia.com/api/master-quote",
            headers={**_NSE_HEADERS, "Accept": "application/json"},
            timeout=8,
        )
        if r.status_code == 200:
            _nse_session_warmed = True
            _nse_session_last_warm = now
    except Exception as ex:
        logger.debug(f"NSE session warm failed: {ex}")


def _fetch_nse_ltp_via_api(
    symbol: str, expiry_str: str, strike: float, opt_type: str = "CE",
) -> Optional[float]:
    """Fetch option LTP from NSE live API (works during AND after market hours)."""
    try:
        h = {
            **_NSE_HEADERS,
            "Accept": "application/json",
            "Referer": f"https://www.nseindia.com/get-quotes/derivatives?symbol={symbol}",
        }
        r = _nse_session.get(
            f"https://www.nseindia.com/api/quote-derivative?symbol={symbol}",
            headers=h, timeout=8,
        )
        # If blocked, re-warm and retry once
        if r.status_code in (401, 403) or len(r.text) < 50:
            _warm_nse_session(force=True)
            r = _nse_session.get(
                f"https://www.nseindia.com/api/quote-derivative?symbol={symbol}",
                headers=h, timeout=8,
            )
        if r.status_code != 200 or len(r.text) < 50:
            return None
        data = r.json()
        stocks = data.get("stocks", [])
        if not stocks:
            return None
        expiry_dt = datetime.strptime(expiry_str, "%Y-%m-%d")
        alt_expiry = expiry_dt.strftime("%d-%b-%Y")   # e.g. "27-Mar-2026"
        nse_expiry = alt_expiry.lstrip("0")           # "27-Mar-2026" (no leading zero)
        for entry in stocks:
            md = entry.get("metadata", {})
            e_expiry = str(md.get("expiryDate", "")).strip()
            e_strike = float(md.get("strikePrice", 0))
            e_type   = str(md.get("optionType", "")).upper().strip()
            e_instr  = str(md.get("instrumentType", "")).upper()
            if (
                "OPT" in e_instr
                and e_type == opt_type.upper()
                and abs(e_strike - strike) < 0.5
                and (e_expiry == nse_expiry or e_expiry == alt_expiry)
            ):
                ltp = md.get("lastPrice") or md.get("ltp")
                if ltp and str(ltp) not in ("-", "", "0"):
                    return float(str(ltp).replace(",", ""))
    except Exception as ex:
        logger.debug(f"NSE API LTP {symbol} {expiry_str} {strike}{opt_type}: {ex}")
    return None


def _fetch_nse_futures_oi(symbol: str) -> Dict:
    """
    Fetch real Open Interest data for the nearest-month futures contract
    from the NSE derivative quote API. Returns {oi, oi_change_pct, volume}.
    Results are cached per symbol for the duration of the scan.
    """
    if symbol in _oi_cache:
        return _oi_cache[symbol]

    default = {"oi": 0, "oi_change_pct": 0.0, "volume": 0, "source": "unavailable"}
    try:
        _warm_nse_session()
        h = {
            **_NSE_HEADERS,
            "Accept": "application/json",
            "Referer": f"https://www.nseindia.com/get-quotes/derivatives?symbol={symbol}",
        }
        r = _nse_session.get(
            f"https://www.nseindia.com/api/quote-derivative?symbol={symbol}",
            headers=h, timeout=8,
        )
        if r.status_code != 200 or len(r.text) < 50:
            _oi_cache[symbol] = default
            return default

        data = r.json()
        stocks = data.get("stocks", [])
        if not stocks:
            _oi_cache[symbol] = default
            return default

        # Find the nearest-month FUTURES contract (FUTSTK)
        for entry in stocks:
            md = entry.get("metadata", {})
            instr = str(md.get("instrumentType", "")).upper()
            if "FUT" in instr:
                oi_val = int(md.get("openInterest", 0) or 0)
                oi_change = float(md.get("pchangeinOpenInterest", 0) or 0)
                vol = int(md.get("numberOfContractsTraded", 0) or 0)
                result = {
                    "oi": oi_val,
                    "oi_change_pct": oi_change,
                    "volume": vol,
                    "source": "NSE Live",
                }
                _oi_cache[symbol] = result
                return result

        _oi_cache[symbol] = default
        return default
    except Exception as ex:
        logger.debug(f"NSE OI fetch failed for {symbol}: {ex}")
        _oi_cache[symbol] = default
        return default


def _fetch_ltp_via_yfinance(
    symbol: str, expiry_str: str, strike: float, opt_type: str = "CE",
) -> Optional[float]:
    """
    Fallback: fetch option LTP from yfinance option chain.
    Yahoo Finance caches the last close price so this works 24/7,
    including after market hours and weekends.
    """
    try:
        ticker = yf.Ticker(f"{symbol}.NS")
        chain = ticker.option_chain(expiry_str)
        if chain is None:
            return None
        df = chain.calls if opt_type.upper() == "CE" else chain.puts
        if df is None or df.empty:
            return None
        # Find the row closest to our target strike
        df = df.copy()
        df["diff"] = (df["strike"] - strike).abs()
        row = df.nsmallest(1, "diff").iloc[0]
        ltp = float(row.get("lastPrice", 0) or 0)
        if ltp > 0.01:
            return round(ltp, 2)
    except Exception as ex:
        logger.debug(f"yfinance LTP fallback {symbol} {expiry_str} {strike}{opt_type}: {ex}")
    return None


def _fetch_live_option_ltp(
    symbol: str, expiry_str: str, strike: float, opt_type: str = "CE",
) -> Tuple[Optional[float], str]:
    """
    Fetch the option LTP with a 2-source cascade:
      1. NSE live API  (works during + after market hours — returns last close when closed)
      2. yfinance      (fallback — 24/7, reads last closing option price from Yahoo cache)

    Returns (ltp, source_label).
    """
    _warm_nse_session()   # no-op if session is fresh

    # ── Source 1: NSE API ───────────────────────────────────────────────────
    ltp = _fetch_nse_ltp_via_api(symbol, expiry_str, strike, opt_type)
    if ltp and ltp > 0.01:
        return ltp, "NSE Live"

    # ── Source 2: yfinance option chain ────────────────────────────────────
    ltp = _fetch_ltp_via_yfinance(symbol, expiry_str, strike, opt_type)
    if ltp and ltp > 0.01:
        return ltp, "NSE Close"

    return None, ""


# ─────────────────────────────────────────────────────────────────────────────
# LAYER 1: HARD FILTERS
# ─────────────────────────────────────────────────────────────────────────────

def _compute_hard_filters(hist: pd.DataFrame, spot: float) -> Tuple[bool, Dict]:
    """
    Returns (passes, filter_details).
    Checks:
      • Close > 20 DMA
      • Volume ≥ 1.2× 20-day avg volume
      • ATR(14)/Price ≥ 1.5%
      • 3-day price gain ≤ 8%
      • IV rank ∈ [25, 65]  (computed as HV rank proxy)
    """
    details: Dict = {}
    try:
        closes = hist["Close"].dropna()
        n = len(closes)
        last = float(closes.iloc[-1])

        # Close > 20 DMA
        sma20 = float(closes.tail(20).mean()) if n >= 20 else None
        above_sma20 = (sma20 is not None and last > sma20)
        details["Above 20DMA"] = above_sma20
        details["20DMA"] = round(sma20, 2) if sma20 else None

        # Volume ≥ 1.2× 20-day avg
        vol_ok = False
        if "Volume" in hist.columns:
            vols = hist["Volume"].dropna()
            if len(vols) >= 20:
                avg_vol = float(vols.tail(20).mean())
                today_vol = float(vols.iloc[-1])
                vol_ratio = today_vol / avg_vol if avg_vol > 0 else 0
                vol_ok = vol_ratio >= 1.2
                details["Vol Ratio"] = round(vol_ratio, 2)
            else:
                vol_ok = True  # insufficient data — pass through
                details["Vol Ratio"] = None
        else:
            vol_ok = True
            details["Vol Ratio"] = None

        # ATR(14)/Price ≥ 1.5%
        try:
            hi = hist["High"].values[-15:]
            lo = hist["Low"].values[-15:]
            cl = closes.values[-15:]
            trs = [max(hi[i]-lo[i], abs(hi[i]-cl[i-1]), abs(lo[i]-cl[i-1]))
                   for i in range(1, len(hi))]
            atr = sum(trs[-14:]) / min(len(trs), 14) if trs else spot * 0.02
        except Exception:
            atr = spot * 0.02
        atr_pct = atr / last * 100
        atr_ok = atr_pct >= 1.5
        details["ATR%"] = round(atr_pct, 2)
        details["atr"] = round(atr, 2)

        # 3-day gain ≤ 8%
        gain3 = 0.0
        if n >= 4:
            gain3 = (last - float(closes.iloc[-4])) / float(closes.iloc[-4]) * 100
        gain3_ok = gain3 <= 8.0
        details["3d Gain%"] = round(gain3, 2)

        # IV Rank [25, 65]
        iv_rank = _estimate_iv_rank(_estimate_volatility(hist), hist)
        iv_ok = 25 <= iv_rank <= 65
        details["IV Rank"] = round(iv_rank, 1)

        passes = above_sma20 and vol_ok and atr_ok and gain3_ok
        # IV rank is a soft pre-filter — log but don't hard-exclude
        # (because HV-proxy may not exactly match option IV rank)
        details["PassedHardFilter"] = passes
        return passes, details

    except Exception as exc:
        logger.debug(f"Hard filter error: {exc}")
        return True, {}  # pass on error: don't exclude on bad data


# ─────────────────────────────────────────────────────────────────────────────
# LAYER 2: INDICATOR NORMALIZATION (0–100)
# ─────────────────────────────────────────────────────────────────────────────

def _compute_composite_score(
    hist: pd.DataFrame,
    spot: float,
    iv_rank: float,
    nifty_hist: pd.DataFrame,
    symbol: str = "",
    days_left: int = 21,
) -> Tuple[float, Dict]:
    """
    Computes the 7-factor composite score (0–100) and sub-scores.
    Includes DTE penalty (Improvement #2) and real OI scoring (Improvement #1).

    Returns (final_score_0_100, sub_scores_dict)
    """
    sub: Dict = {}
    try:
        closes = hist["Close"].dropna()
        n = len(closes)

        # ── A. Momentum Score (25%) ────────────────────────────────────────
        # Momentum = ((Close / Close_5daysAgo) - 1) × 100
        # Score = Min(100, Max(0, Momentum × 5))
        mom = 0.0
        if n >= 6:
            mom = (float(closes.iloc[-1]) / float(closes.iloc[-6]) - 1) * 100
        a_score = min(100.0, max(0.0, mom * 5))
        sub["A_Momentum"] = round(a_score, 1)
        sub["Momentum%"] = round(mom, 2)

        # ── B. Breakout Strength (15%) — Graduated Scoring ─────────────────
        # Improvement #5: Graduated scale instead of binary 0/100
        b_score = 0.0
        if n >= 11:
            highest10 = float(hist["High"].dropna().tail(11).iloc[:-1].max())
            proximity = (spot - highest10) / highest10 * 100 if highest10 > 0 else 0
            if proximity > 0:
                b_score = 100.0   # confirmed breakout
            elif proximity > -1.0:
                b_score = 70.0    # within 1% of breakout — near breakout
            elif proximity > -2.5:
                b_score = 40.0    # approaching breakout zone
            else:
                b_score = 0.0     # far from breakout
            sub["HighestHigh10"] = round(highest10, 2)
            sub["Breakout_Proximity%"] = round(proximity, 2)
        sub["B_Breakout"] = b_score

        # ── C. Volume Expansion (15%) ──────────────────────────────────────
        # Volume_Score = Min(100, Volume_Ratio × 50)
        c_score = 50.0  # neutral default
        if "Volume" in hist.columns:
            vols = hist["Volume"].dropna()
            if len(vols) >= 20:
                avg_vol = float(vols.tail(20).mean())
                today_vol = float(vols.iloc[-1])
                vol_ratio = today_vol / avg_vol if avg_vol > 0 else 1.0
                c_score = min(100.0, vol_ratio * 50)
                sub["VolRatio"] = round(vol_ratio, 2)
        sub["C_Volume"] = round(c_score, 1)

        # ── D. OI Long Buildup (15%) — Real OI from NSE API ───────────────
        # Improvement #1: Uses actual futures OI data from NSE derivative API.
        # Falls back to price+vol proxy only if NSE data is unavailable.
        d_score = 0.0
        mom_positive = mom > 0
        oi_data = _fetch_nse_futures_oi(symbol) if symbol else {}
        oi_source = oi_data.get("source", "unavailable")

        if oi_source == "NSE Live" and oi_data.get("oi", 0) > 0:
            # Real OI-based scoring
            oi_change = oi_data.get("oi_change_pct", 0.0)
            if mom_positive and oi_change > 0:
                # Long buildup: price ↑ + OI ↑
                d_score = min(100.0, max(0.0, oi_change * 5))
            elif mom_positive and oi_change < 0:
                # Short covering: price ↑ + OI ↓ (weaker signal)
                d_score = min(50.0, max(0.0, abs(oi_change) * 2))
            elif not mom_positive and oi_change > 0:
                # Short buildup: price ↓ + OI ↑ (bearish, penalize)
                d_score = 0.0
            else:
                # Long unwinding: price ↓ + OI ↓
                d_score = 10.0
            sub["OI_Change%"] = round(oi_change, 2)
            sub["OI_Source"] = "NSE Live"
        else:
            # Fallback: price + volume proxy
            if mom_positive and c_score > 50:
                d_score = min(100.0, (c_score - 50) * 2)
            sub["OI_Source"] = "Price+Vol Proxy"
        sub["D_OI"] = round(d_score, 1)

        # ── E. RSI Zone Score (10%) ────────────────────────────────────────
        # 45–65 → 100, 65–72 → 60, >72 → 20, else → 40
        try:
            delta = closes.diff().dropna()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = (-delta.clip(upper=0)).rolling(14).mean()
            rs = gain / loss.replace(0, float("inf"))
            rsi = float((100 - (100 / (1 + rs))).iloc[-1])
        except Exception:
            rsi = 50.0
        if 45 <= rsi <= 65:
            e_score = 100.0
        elif 65 < rsi <= 72:
            e_score = 60.0
        elif rsi > 72:
            e_score = 20.0
        else:
            e_score = 40.0
        sub["E_RSI"] = round(e_score, 1)
        sub["RSI"] = round(rsi, 1)

        # ── F. IV Sweet Spot Score (10%) ───────────────────────────────────
        # Ideal rank 30–60 → 100, 20–30 or 60–70 → 60, else → 20
        if 30 <= iv_rank <= 60:
            f_score = 100.0
        elif (20 <= iv_rank < 30) or (60 < iv_rank <= 70):
            f_score = 60.0
        else:
            f_score = 20.0
        sub["F_IV"] = round(f_score, 1)
        sub["IV_Rank"] = round(iv_rank, 1)

        # ── G. Nifty Alignment (10%) ───────────────────────────────────────
        # NIFTY50 Close > its 20 DMA → 100 else 40
        g_score = 40.0
        if not nifty_hist.empty:
            nc = nifty_hist["Close"].dropna()
            if len(nc) >= 20:
                nifty_close = float(nc.iloc[-1])
                nifty_sma20 = float(nc.tail(20).mean())
                g_score = 100.0 if nifty_close > nifty_sma20 else 40.0
                sub["Nifty_Above20DMA"] = nifty_close > nifty_sma20
        sub["G_Nifty"] = g_score

        # ── Composite ──────────────────────────────────────────────────────
        composite = (
            0.25 * a_score
            + 0.15 * b_score
            + 0.15 * c_score
            + 0.15 * d_score
            + 0.10 * e_score
            + 0.10 * f_score
            + 0.10 * g_score
        )

        # ── Layer 6: Enhancements ──────────────────────────────────────────
        bonus = 0.0

        # Relative Strength vs Nifty (10-day)
        rs_10d = 0.0
        if not nifty_hist.empty and n >= 11:
            nc = nifty_hist["Close"].dropna()
            if len(nc) >= 11:
                stock_ret10 = (float(closes.iloc[-1]) / float(closes.iloc[-11]) - 1) * 100
                nifty_ret10 = (float(nc.iloc[-1]) / float(nc.iloc[-11]) - 1) * 100
                rs_10d = stock_ret10 - nifty_ret10
                if rs_10d > 0:
                    bonus += 5.0
        sub["RS_vs_Nifty_10d"] = round(rs_10d, 2)
        sub["RS_Bonus"] = bonus

        # ── Improvement #2: Days-to-Expiry (DTE) Penalty ──────────────────
        dte_penalty = 0.0
        if days_left <= 3:
            dte_penalty = -15.0   # extremely risky theta decay
        elif days_left <= 7:
            dte_penalty = -8.0    # expiry week — elevated risk
        elif days_left > 21:
            dte_penalty = -3.0    # too much time premium paid
        sub["DTE_Penalty"] = dte_penalty
        sub["Days_to_Expiry"] = days_left

        final = round(max(0.0, min(composite + bonus + dte_penalty, 100.0)), 2)
        sub["FinalScore"] = final

        return final, sub

    except Exception as exc:
        logger.debug(f"Composite score error: {exc}")
        return 50.0, {}


# ─────────────────────────────────────────────────────────────────────────────
# LAYER 4: SMART STRIKE SELECTION
# ─────────────────────────────────────────────────────────────────────────────

def _choose_strike_type(
    momentum_score: float,
    volume_ratio: float,
    iv_rank: float,
    iv_high_threshold: float = 60.0,
) -> Tuple[int, str]:
    """
    Deterministic 3-rule strike selection:

      Rule 1 (★ Aggressive):  Momentum_Score > 75 AND Volume_Ratio > 1.8
                               → OTM +1  (accelerating momentum, confirm with volume)

      Rule 2 (★ Conservative): IV Rank slightly high (> iv_high_threshold)
                               → ITM −1  (options are expensive; ITM lets us buy
                                          intrinsic value cheaply, theta is lower)

      Default:                 ATM       (balanced Delta ~0.50, strategy sweet spot)

    Returns (strike_offset, label)
      strike_offset: number of steps relative to ATM
                     0 = ATM, +1 = OTM +1, -1 = ITM -1
    """
    if momentum_score > 75 and volume_ratio > 1.8:
        return +1, "OTM +1"
    elif iv_rank > iv_high_threshold:
        return -1, "ITM -1"
    else:
        return 0, "ATM"


def _select_optimal_strike(
    spot: float,
    T: float,
    sigma: float,
    atr: float,
    momentum_score: float,
    volume_ratio: float,
    iv_rank: float,
    risk_free_rate: float = 0.067,
    min_rr_ratio: float = 1.8,
    max_theta_pct: float = 0.005,
) -> Optional[Dict]:
    """
    Select the single optimal option strike using the 3-rule logic, then
    compute Black-Scholes Greeks and validate Delta/Theta/R-R constraints.

    Strike Decision Rules
    ---------------------
    Rule 1 (Aggressive):   Momentum_Score > 75 AND Volume_Ratio > 1.8 → OTM +1
    Rule 2 (Conservative): IV Rank > 60                                → ITM -1
    Default:               ATM

    Greeks are computed for the selected strike and shown as advisory flags
    (not hard filters) — so no good stock is ever dropped due to Greeks alone.
    """
    step = _strike_step(spot)
    atm = round(spot / step) * step

    # ── Rule-based strike selection ────────────────────────────────────
    offset, strike_type_label = _choose_strike_type(momentum_score, volume_ratio, iv_rank)
    K = atm + offset * step
    if K <= 0:
        K = atm        # safety: never go below zero
        offset = 0
        strike_type_label = "ATM"

    # ── Compute Greeks for selected strike ────────────────────────────
    price, delta, daily_theta = _bs_greeks(spot, K, T, risk_free_rate, sigma)

    # If the selected strike gives a near-zero premium, fall back to ATM
    min_valid_premium = max(spot * 0.001, 0.50)
    if price < min_valid_premium and offset != 0:
        K = atm
        offset = 0
        strike_type_label = "ATM (fallback)"
        price, delta, daily_theta = _bs_greeks(spot, K, T, risk_free_rate, sigma)

    if price < min_valid_premium:
        return None  # even ATM has no tradeable premium (extremely illiquid / deep bear)

    # ── Advisory constraint checks (shown in UI, never hard-exclude) ────
    theta_pct = abs(daily_theta) / price if price > 0 else 1.0
    theta_ok = theta_pct <= max_theta_pct

    target_move = atr * 1.5
    reward = target_move * delta
    risk = price * 0.30
    rr_ratio = reward / risk if risk > 0 else 0.0
    rr_ok = rr_ratio >= min_rr_ratio

    # Delta advisory check
    in_target_delta = 0.40 <= delta <= 0.55

    return {
        "strike": K,
        "strike_type": strike_type_label,
        "strike_offset": offset,
        "bs_price": round(price, 2),
        "delta": round(delta, 3),
        "daily_theta": round(daily_theta, 4),
        "theta_pct": round(theta_pct * 100, 3),
        "rr_ratio": round(rr_ratio, 2),
        "theta_ok": theta_ok,
        "rr_ok": rr_ok,
        "in_target_delta": in_target_delta,
    }


# ─────────────────────────────────────────────────────────────────────────────
# MAIN PER-SYMBOL SCAN
# ─────────────────────────────────────────────────────────────────────────────

def _scan_symbol_for_month(
    symbol: str,
    year: int,
    month: int,
    master_entry: Optional[Dict] = None,
    nifty_hist: Optional[pd.DataFrame] = None,
    risk_free_rate: float = 0.067,
) -> Optional[Dict]:
    """
    Full 6-layer analysis for one F&O stock.
    Returns a single result dict for the optimal contract, or None if filtered out.
    """
    import time
    import random
    
    # All data is fetched exclusively from NSE via the .NS yfinance suffix.
    # Expiry date is computed from NSE's last-Thursday-of-month rule (not yfinance).
    ns_sym = f"{symbol}.NS"
    try:
        # Stagger API requests to prevent NSE rate-limiting blocks
        time.sleep(random.uniform(0.1, 0.4))

        # NSE expiry = last Thursday of the month (formula-based, not from yfinance)
        expiry_str = _find_month_expiry(None, year, month)
        if not expiry_str:
            return None

        expiry_dt = datetime.strptime(expiry_str, "%Y-%m-%d")
        T = max((expiry_dt - datetime.now()).days / 365.0, 1 / 365.0)
        days_left = max((expiry_dt - datetime.now()).days, 1)

        # Fetch NSE price history via .NS suffix (Yahoo Finance → NSE exchange)
        ticker = yf.Ticker(ns_sym)
        hist = ticker.history(period="90d", auto_adjust=False)
        if hist is None or hist.empty or len(hist) < 10:
            return None
        if isinstance(hist.columns, pd.MultiIndex):
            hist.columns = [c[0] for c in hist.columns]

        spot = float(hist["Close"].iloc[-1])
        if spot <= 0:
            return None

        # ── Improvement: Straddle Setup Detection (Volatility Squeeze) ────
        is_straddle_setup = False
        try:
            closes = hist["Close"].dropna()
            sma20_full = closes.rolling(window=20).mean()
            std20_full = closes.rolling(window=20).std()
            upper_band = sma20_full + (std20_full * 2)
            lower_band = sma20_full - (std20_full * 2)
            
            bb_width = ((upper_band.iloc[-1] - lower_band.iloc[-1]) / sma20_full.iloc[-1]) * 100
            
            # Squeeze condition: Bandwidth < 6% (extremely tight)
            if bb_width < 6.0:
                # Check for Catalyst
                from services.market_data_service import fetch_corporate_actions
                corp_action = fetch_corporate_actions(symbol)
                if corp_action and ("Earnings" in corp_action or "Dividend" in corp_action):
                    is_straddle_setup = True
        except:
            pass

        # ── Layer 1: Hard Filters ─────────────────────────────────────────
        passes, f_details = _compute_hard_filters(hist, spot)
        
        # Bypass directional trend/volume filters if it's a massive straddle setup
        if not passes and not is_straddle_setup:
            return None

        atr = f_details.get("atr", spot * 0.02)
        iv_rank = f_details.get("IV Rank", 50.0)

        # ── Improvement #3: IV Rank Hard Filter for Calls ─────────────────
        # Exclude stocks with extremely expensive options (IV > 75)
        if iv_rank > 75:
            return None

        # ── Layer 2 & 3: Composite Score ──────────────────────────────────
        nifty = nifty_hist if nifty_hist is not None else pd.DataFrame()
        final_score, sub_scores = _compute_composite_score(
            hist, spot, iv_rank, nifty,
            symbol=symbol, days_left=days_left,
        )
        rsi = sub_scores.get("RSI", 50.0)

        # ── Layer 4: Smart Strike Selection (3-Rule Logic) ───────────────
        sigma = _estimate_volatility(hist)
        # Pull the inputs that drive the strike rule
        momentum_score = sub_scores.get("A_Momentum", 0.0)
        volume_ratio   = sub_scores.get("VolRatio", 1.0)

        contract_info = _select_optimal_strike(
            spot=spot, T=T, sigma=sigma, atr=atr,
            momentum_score=momentum_score,
            volume_ratio=volume_ratio,
            iv_rank=iv_rank,
            risk_free_rate=risk_free_rate,
        )
        if contract_info is None:
            return None

        strike          = contract_info["strike"]
        strike_type     = contract_info["strike_type"]
        bs_price        = contract_info["bs_price"]
        delta_val       = contract_info["delta"]
        daily_theta     = contract_info["daily_theta"]
        theta_pct       = contract_info["theta_pct"]
        rr_ratio        = contract_info["rr_ratio"]

        # ── Live LTP / Last Close premium ─────────────────────────────────
        # _fetch_live_option_ltp returns (price, source_label)
        # source_label = "NSE Live"  → market hours price from NSE API
        #               "NSE Close" → last close from yfinance (after hours)
        #               ""          → both failed, fall back to computed model
        live_ltp, ltp_source = _fetch_live_option_ltp(symbol, expiry_str, strike, "CE")
        if live_ltp and live_ltp > 0.01:
            current_premium = live_ltp
            price_source = ltp_source   # "NSE Live" or "NSE Close"
        else:
            current_premium = bs_price
            price_source = "Computed EOD"


        # Skip near-zero premiums
        min_premium = max(spot * 0.001, 0.50)
        if current_premium < min_premium:
            return None

        # ── Lot size ──────────────────────────────────────────────────────
        lot_size = (master_entry or {}).get("lot_size", 0)
        if not lot_size or lot_size <= 0:
            lot_size = max(int(round(500000 / spot / 25)) * 25, 25)

        comp_name = (master_entry or {}).get("name", symbol)

        # ── Investment ────────────────────────────────────────────────────
        investment = current_premium * lot_size

        # ── Target price and expected premium ─────────────────────────────
        scale = math.sqrt(days_left / 21.0)
        bull_target = round(spot + atr * 1.5 * scale, 2)

        # Expected premium at target: BS at ~50% remaining time
        half_T = T * 0.5
        intrinsic = max(bull_target - strike, 0.0)
        bs_at_target = black_scholes_call(bull_target, strike, half_T, risk_free_rate, sigma * 0.85)
        exp_premium = round(max(intrinsic, bs_at_target), 2)

        gross_profit = round((exp_premium - current_premium) * lot_size, 0)
        ret_pct = round((gross_profit / investment * 100) if investment > 0 else 0.0, 1)

        # ── Improvement #10: Position Sizing Calculator ───────────────────
        risk_capital = 100000.0  # default ₹1 Lakh risk capital
        max_risk_per_trade = risk_capital * 0.02  # 2% risk rule
        stop_loss_amount = current_premium * 0.30 * lot_size  # 30% SL
        recommended_lots = max(1, int(max_risk_per_trade / stop_loss_amount)) if stop_loss_amount > 0 else 1

        # ── Improvement: Hedge Contract Calculation (Protective Put) ──────
        # Hedge is ~2% OTM. For a Call, we buy a Put below spot.
        hedge_strike = round((spot * 0.98) / 50) * 50
        if hedge_strike >= spot:
            hedge_strike -= 50
        
        hedge_bs_price = black_scholes_put(spot, hedge_strike, T, risk_free_rate, sigma)
        hedge_premium = round(max(hedge_bs_price, spot * 0.005), 2)  # Minimum premium bounds
        hedge_contract = f"PE @ ₹{hedge_strike}"

        # ── News sentiment ────────────────────────────────────────────────
        news_score, news_headline = _get_news_sentiment(symbol)

        # ── Layer 5: Exit signals (Improvement #9 — Complete Framework) ───
        closes = hist["Close"].dropna()
        ema5 = float(closes.ewm(span=5, adjust=False).mean().iloc[-1]) if len(closes) >= 5 else spot
        exit_signals = []
        if spot < ema5:
            exit_signals.append("⚠️ Below 5 EMA")
        if sub_scores.get("A_Momentum", 100) < 50:
            exit_signals.append("⚠️ Momentum < 50")
        # Improvement #9: Additional exit checks
        if days_left <= 3:
            exit_signals.append("🔴 Expiry in ≤3 days — exit urgently")
        elif days_left <= 7:
            exit_signals.append("⚠️ Expiry week — trail stop-loss tightly")
        # Stop-loss guidance
        sl_premium = round(current_premium * 0.70, 2)
        exit_signals.append(f"🛑 SL: Exit if premium drops to ₹{sl_premium:.2f} (−30%)")
        # Profit target guidance
        exit_signals.append(f"🎯 Target: Book at ₹{exp_premium:.2f} (+{ret_pct:.0f}%)")

        # ── Final score normalization to 0-1 for display ──────────────────
        normalized_score = round(final_score / 100.0, 3)

        contract = _contract_name(symbol, expiry_str, strike, "CE")

        return {
            "Contract": contract,
            "Symbol": symbol,
            "Company": comp_name,
            "Expiry": expiry_str,
            "Days to Expiry": days_left,
            "Price Source": price_source,
            # ── Strike selection rule ───────────────────────────────────
            "Strike Type": strike_type,
            "Strike Rule": (
                f"OTM +1 (Mom {momentum_score:.0f}>75 & Vol {volume_ratio:.1f}x>1.8x)"
                if strike_type.startswith("OTM") else
                f"ITM -1 (IV Rank {iv_rank:.0f}>60, high IV)"
                if strike_type.startswith("ITM") else
                "ATM (default)"
            ),
            # ── Price / Strike ─────────────────────────────────────────────
            "Underlying Spot (₹)": round(spot, 2),
            "Strike (₹)": strike,
            "Moneyness%": round((strike - spot) / spot * 100, 1),
            # ── Premium / Investment ───────────────────────────────────────
            "Current Premium (₹)": round(current_premium, 2),
            "BS Fair Value (₹)": round(bs_price, 2),
            "Lot Size": lot_size,
            "Investment / Lot (₹)": round(investment, 0),
            # ── Greeks ────────────────────────────────────────────────────
            "Delta": delta_val,
            "Daily Theta (₹)": daily_theta,
            "Theta % of Premium": theta_pct,
            "Reward/Risk Ratio": rr_ratio,
            "Theta OK": "✅" if contract_info["theta_ok"] else "⚠️",
            "R/R OK": "✅" if contract_info["rr_ok"] else "⚠️",
            # ── Target & Profit ────────────────────────────────────────────
            "Target Spot Price (₹)": bull_target,
            "Expected Premium @ Target (₹)": exp_premium,
            "Est Profit / Lot (₹)": gross_profit,
            "Return%": ret_pct,
            "Recommended Lots": recommended_lots,
            "Straddle Opportunity": is_straddle_setup,
            "Hedge Contract": hedge_contract,
            "Hedge Premium (₹)": hedge_premium,

            # ── Greeks & Validation ─────────────────────────────────────────
            "Final Score (0-100)": final_score,
            "BullishScore": normalized_score,  # kept for UI compat
            "A Momentum (25%)": sub_scores.get("A_Momentum", 0.0),
            "B Breakout (15%)": sub_scores.get("B_Breakout", 0.0),
            "C Volume (15%)": sub_scores.get("C_Volume", 0.0),
            "D OI (15%)": sub_scores.get("D_OI", 0.0),
            "OI Source": sub_scores.get("OI_Source", "Proxy"),
            "E RSI (10%)": sub_scores.get("E_RSI", 0.0),
            "F IV (10%)": sub_scores.get("F_IV", 0.0),
            "G Nifty (10%)": sub_scores.get("G_Nifty", 0.0),
            "RS vs Nifty 10d%": sub_scores.get("RS_vs_Nifty_10d", 0.0),
            "RS Bonus": sub_scores.get("RS_Bonus", 0.0),
            "DTE Penalty": sub_scores.get("DTE_Penalty", 0.0),
            # ── Technical ─────────────────────────────────────────────────
            "RSI": rsi,
            "IV Rank": iv_rank,
            "Momentum%": sub_scores.get("Momentum%", 0.0),
            "Breakout": "✅" if sub_scores.get("B_Breakout", 0) >= 70 else "❌",
            "Breakout Proximity%": sub_scores.get("Breakout_Proximity%", 0.0),
            "Vol Ratio": sub_scores.get("VolRatio", 1.0),
            "ATR (₹)": atr,
            "Volatility (σ)": f"{sigma * 100:.1f}%",
            "5 EMA": round(ema5, 2),
            "Above 5 EMA": "✅" if spot >= ema5 else "❌",
            # ── Hard Filter Details ───────────────────────────────────────
            "Above 20DMA": "✅" if f_details.get("Above 20DMA") else "❌",
            "ATR% ≥ 1.5": "✅" if f_details.get("ATR%", 0) >= 1.5 else "❌",
            "3d Gain ≤ 8%": "✅" if f_details.get("3d Gain%", 0) <= 8 else "❌",
            "IV Range OK": "✅" if 25 <= iv_rank <= 65 else "⚠️",
            # ── Position Sizing (Improvement #10) ─────────────────────────
            "Recommended Lots": recommended_lots,
            "SL Premium (₹)": sl_premium,
            "Max Risk/Trade (₹)": round(max_risk_per_trade, 0),
            # ── News ──────────────────────────────────────────────────────
            "News Score": news_score,
            "Latest News": news_headline[:80] if news_headline else "—",
            # ── Exit Signals ──────────────────────────────────────────────
            "Exit Signals": " | ".join(exit_signals) if exit_signals else "None",
        }

    except Exception as exc:
        logger.debug(f"Scan failed for {symbol}: {exc}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC SCAN FUNCTION
# ─────────────────────────────────────────────────────────────────────────────

def scan_fno_options_for_month(
    year: int,
    month: int,
    top_n: int = 10,
    max_workers: int = 3,
    min_score: float = 40.0,   # 0-100 scale
    strike_types: Optional[List[str]] = None,  # unused — kept for API compat
) -> pd.DataFrame:
    """
    Scan all NSE F&O stocks using the Advanced Call Buying Strategy.
    Returns a ranked DataFrame of top-N opportunities.

    Parameters
    ----------
    year, month   : Target expiry month.
    top_n         : Number of top stocks to return (strategy recommends 5).
    max_workers   : Thread pool size.
    min_score     : Minimum composite score (0-100) to include.
    """
    global _oi_cache
    _oi_cache = {}  # Clear OI cache for fresh scan

    master_map = get_fno_master_map()
    fno_stocks = list(master_map.keys())
    nifty_hist = _get_nifty_hist()

    logger.info(
        f"Strategy scan: {len(fno_stocks)} F&O stocks | "
        f"{year}-{month:02d} | top_n={top_n}"
    )

    results: List[Dict] = []

    def _worker(sym: str) -> Optional[Dict]:
        return _scan_symbol_for_month(
            sym, year, month,
            master_entry=master_map.get(sym),
            nifty_hist=nifty_hist,
        )

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_worker, s): s for s in fno_stocks}
        for fut in as_completed(futures):
            try:
                row = fut.result()
                if row is not None and row["Final Score (0-100)"] >= min_score:
                    results.append(row)
            except Exception as exc:
                logger.debug(f"Worker error: {exc}")

    if not results:
        return pd.DataFrame()

    # Sort by score descending
    results.sort(key=lambda r: r["Final Score (0-100)"], reverse=True)

    # ── Improvement #4: Sector Concentration Limit ────────────────────
    # Allow max 2 stocks from the same sector/industry to force diversification.
    # Sector is derived from the first word of the company name as a basic proxy,
    # or from the NIFTY sector classification if available.
    from features.stock_master import load_combined_stock_master
    try:
        master_entries = load_combined_stock_master()
        sector_map = {e.get("symbol", ""): e.get("sector", "Other") for e in master_entries}
    except Exception:
        sector_map = {}

    max_per_sector = 2
    sector_counts: Dict[str, int] = {}
    diversified_results: List[Dict] = []

    for row in results:
        sym = row.get("Symbol", "")
        sector = sector_map.get(sym, "Other")
        if sector_counts.get(sector, 0) < max_per_sector:
            diversified_results.append(row)
            sector_counts[sector] = sector_counts.get(sector, 0) + 1
        if len(diversified_results) >= top_n:
            break

    # If diversification was too aggressive, fill remaining slots unrestricted
    if len(diversified_results) < top_n:
        selected_syms = {r["Symbol"] for r in diversified_results}
        for row in results:
            if row["Symbol"] not in selected_syms:
                diversified_results.append(row)
                if len(diversified_results) >= top_n:
                    break

    # ── Improvement: Fetch Corporate Actions (Earnings/Dividends) ──
    from services.market_data_service import fetch_corporate_actions
    def _add_corp_actions(row):
        corp_act = fetch_corporate_actions(row["Symbol"])
        row["Corporate Action"] = corp_act if corp_act else "None"
        return row
        
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        diversified_results = list(pool.map(_add_corp_actions, diversified_results))

    df = pd.DataFrame(diversified_results).reset_index(drop=True)
    return df
