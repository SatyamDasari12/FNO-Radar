"""
Refresh F&O Master Data
========================
Pulls the authoritative NSE F&O stock universe from:

  • PRIMARY: NSE /api/equity-stockIndices?index=SECURITIES%20IN%20F%26O
             (NSE's official "Securities in F&O" index — 200+ stocks)
  • FALLBACK: NSE /api/master-quote
             (secondary list, same stocks from a different NSE endpoint)
  • HARDCODED: 175+ symbol fallback if both APIs fail

Only NSE F&O stocks are included. BSE stocks are excluded by design —
all option chains are fetched from NSE using the .NS yfinance suffix.

Enriches each entry with:
  - Company full name  (from stock_master.json lookup)
  - Lot size          (from NSE archives CSV or known table)
  - Exchange          = "NSE" always

Output: data/fno_master.json
Format: List[{symbol, name, lot_size, exchange}]

Run manually to refresh:
    python scripts/refresh_fno_master.py
"""
import json
import os
import sys
import requests
import pandas as pd
from io import StringIO

# ── Paths ─────────────────────────────────────────────────────────────────────
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT_DIR = os.path.dirname(_THIS_DIR)
DATA_DIR = os.path.join(_ROOT_DIR, "data")
FNO_MASTER_FILE = os.path.join(DATA_DIR, "fno_master.json")
STOCK_MASTER_FILE = os.path.join(DATA_DIR, "stock_master.json")

# ── Standard NSE HTTP headers ─────────────────────────────────────────────────
NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/market-data/equity-derivatives-watch",
    "Connection": "keep-alive",
}

# ── Known NSE F&O lot sizes (quarterly revision by NSE) ──────────────────────
# Source: NSE fo_mktlots.csv → last updated Mar 2026
FALLBACK_LOT_SIZES: dict = {
    "360ONE": 150, "ABB": 50, "ABCAPITAL": 2200, "ADANIENT": 125,
    "ADANIENSOL": 500, "ADANIGREEN": 250, "ADANIPORTS": 400,
    "ALKEM": 50, "AMBER": 50, "AMBUJACEM": 1000,
    "ANGELONE": 250, "APLAPOLLO": 175, "APOLLOHOSP": 125, "APOLLOTYRE": 1500,
    "ASHOKLEY": 2500, "ASIANPAINT": 200, "ASTRAL": 200, "AUBANK": 1500,
    "AUROPHARMA": 650, "AXISBANK": 625,
    "BAJAJ-AUTO": 75, "BAJAJFINSV": 500, "BAJAJHLDNG": 50, "BAJFINANCE": 125,
    "BANDHANBNK": 3600, "BANKBARODA": 5850, "BANKINDIA": 3000,
    "BDL": 125, "BEL": 2250, "BHARATFORG": 575, "BHARTIARTL": 475,
    "BHEL": 2700, "BIOCON": 2200, "BLUESTARCO": 200, "BOSCHLTD": 25,
    "BPCL": 1800, "BRITANNIA": 100, "BSE": 400,
    "CAMS": 125, "CANBK": 3600, "CDSL": 1250, "CGPOWER": 750,
    "CHOLAFIN": 500, "CIPLA": 650, "COALINDIA": 2100, "COFORGE": 100,
    "COLPAL": 700, "CONCOR": 800, "CROMPTON": 1500, "CUMMINSIND": 150,
    "DABUR": 1250, "DALBHARAT": 150, "DELHIVERY": 2150, "DIVISLAB": 200,
    "DIXON": 70, "DLF": 1650, "DMART": 75, "DRREDDY": 125,
    "EICHERMOT": 175, "ETERNAL": 1125,
    "EXIDEIND": 2900, "FEDERALBNK": 5000, "FORTIS": 2000,
    "GAIL": 3825, "GLENMARK": 575, "GMRAIRPORT": 5250, "GODREJCP": 500,
    "GODREJPROP": 375, "GRASIM": 350,
    "HAL": 150, "HAVELLS": 500, "HCLTECH": 350, "HDFCAMC": 200,
    "HDFCBANK": 550, "HDFCLIFE": 1100, "HEROMOTOCO": 150, "HINDALCO": 1075,
    "HINDPETRO": 1450, "HINDUNILVR": 300, "HUDCO": 3250,
    "ICICIBANK": 700, "ICICIGI": 125, "ICICIPRULI": 1000,
    "IDBI": 6400, "IDFCFIRSTB": 11250, "IEX": 3750, "IGL": 1375,
    "INDHOTEL": 1400, "INDIGO": 150, "INDUSINDBK": 600, "INDUSTOWER": 1400,
    "INFY": 400, "IOC": 5000, "IPCALAB": 425, "IRCTC": 1375,
    "IREDA": 2500, "IRFC": 4800, "ITC": 1600,
    "JKCEMENT": 125, "JSWSTEEL": 600, "JUBLFOOD": 250,
    "KALYANKJIL": 833, "KOTAKBANK": 400,
    "L&TFH": 3000, "LALPATHLAB": 200, "LT": 175, "LTTS": 125, "LUPIN": 300,
    "M&M": 350, "M&MFIN": 3000, "MARICO": 1200, "MARUTI": 75,
    "MAXHEALTH": 700, "MAZDOCK": 50, "MCDOWELL-N": 250,
    "MCX": 200, "METROPOLIS": 250, "MFSL": 700,
    "MOTHERSON": 4350, "MPHASIS": 175, "MRF": 15, "MUTHOOTFIN": 375,
    "NATIONALUM": 3750, "NAUKRI": 100, "NBCC": 5000, "NCC": 2500,
    "NESTLEIND": 100, "NMDC": 3750, "NTPC": 2250,
    "OBEROIRLTY": 500, "OFSS": 100, "ONGC": 1925,
    "PAGEIND": 15, "PEL": 250, "PERSISTENT": 125, "PFC": 2250,
    "PIDILITIND": 250, "PNB": 8000, "POLYCAB": 125, "POWERGRID": 2900,
    "PVRINOX": 375,
    "RECLTD": 1500, "RELIANCE": 250, "RVNL": 1900,
    "SAIL": 7100, "SBICARD": 750, "SBILIFE": 375, "SBIN": 750,
    "SHRIRAMFIN": 300, "SIEMENS": 175, "SONACOMS": 750, "SUNPHARMA": 350,
    "SUNTV": 700,
    "TATACHEM": 550, "TATACOMM": 400, "TATACONSUM": 900, "TATAELXSI": 100,
    "TATAMOTORS": 1925, "TATAPOWER": 2700, "TATASTEEL": 2850,
    "TCS": 175, "TECHM": 400, "TIINDIA": 125, "TITAN": 375,
    "TORNTPHARM": 150, "TRENT": 350, "TVSMOTOR": 350,
    "UBL": 350, "ULTRACEMCO": 100, "UNIONBANK": 5700, "UPL": 1300,
    "VEDL": 1750, "VOLTAS": 375, "WIPRO": 1500,
    "YESBANK": 40000, "ZOMATO": 3000, "ZYDUSLIFE": 700,
}


def _make_session() -> requests.Session:
    """Return a warmed NSE session with cookies."""
    s = requests.Session()
    # warm up — get NSE homepage so cookies are set
    try:
        s.get("https://www.nseindia.com", headers=NSE_HEADERS, timeout=8)
    except Exception:
        pass
    return s


def _load_stock_name_map() -> dict:
    """Load {symbol: company_name} from existing stock_master.json."""
    if not os.path.exists(STOCK_MASTER_FILE):
        return {}
    try:
        with open(STOCK_MASTER_FILE, "r", encoding="utf-8") as f:
            entries = json.load(f)
        name_map = {}
        for e in entries:
            sym = str(e[0]).strip().upper()
            name = str(e[1]).strip() if len(e) > 1 else sym
            if sym not in name_map:
                name_map[sym] = name
        print(f"  Loaded {len(name_map)} names from stock_master.json")
        return name_map
    except Exception as ex:
        print(f"  Warning: could not load stock_master.json: {ex}")
        return {}


def _fetch_fno_symbols_primary(session: requests.Session) -> list:
    """
    PRIMARY: NSE 'Securities in F&O' index endpoint.
    Returns the official NSE F&O eligible stock list.
    This is guaranteed to be NSE-only — no BSE stocks.
    """
    url = "https://www.nseindia.com/api/equity-stockIndices?index=SECURITIES%20IN%20F%26O"
    try:
        r = session.get(url, headers=NSE_HEADERS, timeout=12)
        if r.status_code == 200:
            data = r.json()
            if "data" in data and isinstance(data["data"], list):
                # Each entry is a full market data dict; extract 'symbol'
                symbols = sorted({
                    str(d["symbol"]).strip().upper()
                    for d in data["data"]
                    if d.get("symbol") and d["symbol"] not in ("SECURITIES IN F&O",)
                })
                if len(symbols) > 50:
                    print(f"  ✅ PRIMARY: NSE Securities-in-F&O → {len(symbols)} stocks")
                    return symbols
    except Exception as ex:
        print(f"  Primary API failed: {ex}")
    return []


def _fetch_fno_symbols_secondary(session: requests.Session) -> list:
    """
    FALLBACK: NSE /api/master-quote — secondary NSE F&O list.
    Returns NSE F&O symbols.
    """
    try:
        r = session.get(
            "https://www.nseindia.com/api/master-quote",
            headers=NSE_HEADERS, timeout=10,
        )
        if r.status_code == 200 and r.text.strip().startswith("["):
            stocks = r.json()
            if isinstance(stocks, list) and len(stocks) > 50:
                symbols = sorted({str(s).strip().upper() for s in stocks if s})
                print(f"  ✅ SECONDARY: master-quote API → {len(symbols)} stocks")
                return symbols
    except Exception as ex:
        print(f"  Secondary API failed: {ex}")
    return []


def _fetch_fno_symbols() -> list:
    """Fetch NSE F&O symbols — tries primary, secondary, then hardcoded fallback."""
    session = _make_session()

    symbols = _fetch_fno_symbols_primary(session)
    if symbols:
        return symbols

    print("  Trying secondary NSE API...")
    symbols = _fetch_fno_symbols_secondary(session)
    if symbols:
        return symbols

    print("  ⚠️  Both NSE APIs failed — using hardcoded fallback list")
    return sorted(FALLBACK_LOT_SIZES.keys())


def _try_fetch_lot_sizes_csv(session: requests.Session) -> dict:
    """
    Fetch NSE F&O lot sizes from the archives CSV.
    Returns {SYMBOL: lot_size} or empty dict on failure.
    """
    url = "https://archives.nseindia.com/content/fo/fo_mktlots.csv"
    try:
        r = session.get(url, headers=NSE_HEADERS, timeout=12)
        if r.status_code == 200 and "," in r.text and not r.text.startswith("%PDF"):
            df = pd.read_csv(StringIO(r.text))
            df.columns = [str(c).strip() for c in df.columns]
            sym_col = next(
                (c for c in df.columns if "symbol" in c.lower()), None
            )
            num_cols = [c for c in df.columns if c != sym_col]
            if sym_col and num_cols:
                result = {}
                for _, row in df.iterrows():
                    sym = str(row[sym_col]).strip().upper()
                    # Skip index rows / header artifacts
                    if not sym or sym in ("SYMBOL", ""):
                        continue
                    for nc in num_cols:
                        try:
                            val = int(str(row[nc]).replace(",", "").strip())
                            if val > 0:
                                result[sym] = val
                                break
                        except Exception:
                            continue
                print(f"  ✅ NSE lot-size CSV → {len(result)} lot sizes")
                return result
    except Exception as ex:
        print(f"  NSE lot-size CSV fetch failed: {ex}")
    return {}


def refresh():
    print("=" * 60)
    print("  NSE F&O Master Refresh  (NSE ONLY — no BSE)")
    print("=" * 60)

    os.makedirs(DATA_DIR, exist_ok=True)

    print("\n[1] Loading stock name map from stock_master.json...")
    name_map = _load_stock_name_map()

    print("\n[2] Fetching NSE F&O symbol list (Securities-in-F&O index)...")
    symbols = _fetch_fno_symbols()
    print(f"    → {len(symbols)} NSE F&O stocks fetched")

    print("\n[3] Fetching lot sizes from NSE archives CSV...")
    session = _make_session()
    live_lots = _try_fetch_lot_sizes_csv(session)
    # Merge: live CSV takes priority, fallback for missing
    lot_map = {**FALLBACK_LOT_SIZES, **live_lots}

    print("\n[4] Building F&O master entries...")
    entries = []
    missing_name = 0
    missing_lot = 0

    for sym in symbols:
        sym_up = sym.strip().upper()

        # Try exact match for name
        name = name_map.get(sym_up)
        if not name:
            # Try common NSE symbol variations stored differently in stock_master
            alt = sym_up.replace("-", "").replace("&", "")
            name = name_map.get(alt, sym_up)
            if name == sym_up:
                missing_name += 1

        lot = lot_map.get(sym_up)
        if not lot:
            missing_lot += 1
            lot = 0  # marked unknown — UI calculates from spot price

        entries.append({
            "symbol": sym_up,
            "name": name,
            "lot_size": lot,
            "exchange": "NSE",   # ← always NSE — BSE excluded
        })

    entries.sort(key=lambda x: x["symbol"])

    # Sanity: all should be NSE
    bse_count = sum(1 for e in entries if e["exchange"] != "NSE")
    print(f"\n  Total entries     : {len(entries)}")
    print(f"  Exchange          : all NSE ✅" if bse_count == 0 else f"  ⚠️ Non-NSE entries: {bse_count}")
    print(f"  Missing names     : {missing_name}")
    print(f"  Missing lot sizes : {missing_lot}")

    print(f"\n[5] Saving to {FNO_MASTER_FILE}...")
    with open(FNO_MASTER_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)

    print(f"\n✅  F&O master saved: {len(entries)} NSE stocks")
    print("   All option chains will be fetched from NSE using .NS yfinance suffix.")
    return entries


if __name__ == "__main__":
    result = refresh()
    print("\nSample entries:")
    for e in result[:5]:
        print(f"  {e}")
