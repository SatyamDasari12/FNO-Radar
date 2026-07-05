"""
Fetch complete equity lists from both NSE and BSE for the typeahead stock search.
Cross-listed stocks (most large-caps) appear as two entries: [NSE] and [BSE].
Falls back to a hardcoded list if network is unavailable.
"""
from __future__ import annotations

from typing import Dict, List, Optional
from io import StringIO

import re
import requests
import pandas as pd
import streamlit as st

from utils.logging import logger

# ── Public data sources ────────────────────────────────────────────────────
_NSE_URL = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
_BSE_URL = "https://api.bseindia.com/BseIndiaAPI/api/ListofScripData/w?segment=Equity&status=Active"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/csv, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
}

_FALLBACK: Dict[str, str] = {
    "RELIANCE": "Reliance Industries",
    "TCS": "Tata Consultancy Services",
    "HDFCBANK": "HDFC Bank",
    "ICICIBANK": "ICICI Bank",
    "INFY": "Infosys",
    "ITC": "ITC Limited",
    "SBIN": "State Bank of India",
    "KOTAKBANK": "Kotak Mahindra Bank",
    "AXISBANK": "Axis Bank",
    "LT": "Larsen & Toubro",
    "BEL": "Bharat Electronics",
    "HAL": "Hindustan Aeronautics",
    "IRCTC": "Indian Railway Catering & Tourism",
    "TATAMOTORS": "Tata Motors",
    "NTPC": "NTPC Limited",
    "WIPRO": "Wipro",
    "HCLTECH": "HCL Technologies",
    "ONGC": "Oil & Natural Gas Corp",
    "DLINKINDIA": "D-Link India",
    "SUNPHARMA": "Sun Pharmaceuticals",
    "ADANIENT": "Adani Enterprises",
    "BHARTIARTL": "Bharti Airtel",
    "ZOMATO": "Zomato",
    "NYKAA": "FSN E-Commerce (Nykaa)",
    "TITAN": "Titan Company",
    "MARUTI": "Maruti Suzuki",
}


# ── Individual loaders ─────────────────────────────────────────────────────

def _load_nse() -> Dict[str, str]:
    """Return {SYMBOL: 'Company Name'} for all NSE-listed equities."""
    try:
        resp = requests.get(_NSE_URL, headers=_HEADERS, timeout=12)
        resp.raise_for_status()
        df = pd.read_csv(StringIO(resp.text))
        if "SYMBOL" in df.columns and "NAME OF COMPANY" in df.columns:
            if "SERIES" in df.columns:
                df = df[df["SERIES"].isin(["EQ", "BE", "BZ", "SM", "ST"])]
            result = {
                str(r["SYMBOL"]).strip(): str(r["NAME OF COMPANY"]).strip()
                for _, r in df.iterrows()
                if pd.notna(r["SYMBOL"]) and pd.notna(r["NAME OF COMPANY"])
            }
            logger.info(f"NSE master loaded: {len(result)} stocks.")
            return result
        logger.warning(f"NSE CSV unexpected columns: {list(df.columns)}")
    except Exception as exc:
        logger.warning(f"NSE fetch failed: {exc}")
    return {}


def _load_bse(nse_master: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """
    Return {ticker_symbol: 'Company Name'} for BSE-listed equities.

    BSE's API returns numeric SCRIP_CD (e.g. '500002'), not ticker symbols.
    Strategy:
    1. Fetch BSE list (Scrip_Name + SCRIP_CD).
    2. Build a reverse name→symbol map from the NSE master.
    3. Match BSE company names against NSE names (exact + normalised).
       → Matched stocks: symbol = NSE ticker (e.g. 'ABB')
       → Unmatched stocks (BSE-only): symbol = SCRIP_CD (e.g. '500002')
         so yfinance can still look them up as '500002.BO'
    """
    try:
        bse_headers = {**_HEADERS, "Referer": "https://www.bseindia.com/", "Origin": "https://www.bseindia.com"}
        resp = requests.get(_BSE_URL, headers=bse_headers, timeout=15)
        resp.raise_for_status()
        rows = resp.json()
        if not isinstance(rows, list) or not rows:
            raise ValueError(f"Unexpected BSE response format: {type(rows)}")

        # Build normalised name → NSE symbol lookup
        def _norm(s: str) -> str:
            # Common suffixes/words to remove from both NSE and BSE names
            s = str(s).upper().strip()
            # Remove common business suffixes as whole words
            # We want to keep the core name to match even if one says 'LTD' and other says 'LIMITED'
            words_to_strip = [
                r"LIMITED", r"LTD", r"CORP", r"CORPORATION", r"INDIA", r"PVT", r"PRIVATE",
                r"INDUSTRIES", r"INDUSTRIAL", r"IND", r"SERIES", r"OFFERING", r"ENTERPRISES",
                r"PHARMA", r"PHARMACEUTICALS", r"CHEMICALS", r"VENTURES", r"HOLDINGS", r"GROUP",
                r"SERVICES", r"FINANCE", r"FINANCIAL", r"SYSTEMS", r"TECHNOLOGIES", r"INFRASTRUCTURE",
                r"COMMUNICATIONS", r"PROJECTS", r"SOLUTIONS", r"MANAGEMENT", r"LOGISTICS",
            ]
            # Match them as whole words only
            pattern = r"\b(" + "|".join(words_to_strip) + r")\b\.?"
            s = re.sub(pattern, "", s)

            # Also handle common abbreviations like 'INDL' for INDUSTRIAL etc. if needed
            # But usually stripping all non-alphanumeric is the best fuzzy matcher
            s = re.sub(r"[^A-Z0-9]", "", s)
            return s.strip()

        nse_name_to_sym: Dict[str, str] = {}
        if nse_master:
            for sym, name in nse_master.items():
                nse_name_to_sym[_norm(name)] = sym

        result: Dict[str, str] = {}
        unmatched = 0
        for row in rows:
            scrip_name = str(row.get("Scrip_Name", "")).strip()
            scrip_cd   = str(row.get("SCRIP_CD", "")).strip()
            if not scrip_name or not scrip_cd:
                continue

            # Try to map to NSE ticker via company name
            norm_name = _norm(scrip_name)
            if norm_name in nse_name_to_sym:
                sym = nse_name_to_sym[norm_name]
            else:
                # BSE-only stock — use numeric scrip code as symbol key
                sym = scrip_cd
                unmatched += 1

            result[sym] = scrip_name

        logger.info(
            f"BSE master loaded: {len(result)} stocks "
            f"({len(result) - unmatched} matched to NSE tickers, {unmatched} BSE-only by scrip code)."
        )
        return result
    except Exception as exc:
        logger.warning(f"BSE fetch failed: {exc}")
    return {}



import json
import os

_DATA_DIR = "data"
_STOCK_MASTER_FILE = os.path.join(_DATA_DIR, "stock_master.json")


@st.cache_data(ttl=86400, show_spinner=False)
def load_combined_stock_master() -> List[tuple]:
    """
    Return a list of (symbol, company_name, exchange) tuples.
    Loads from pre-generated JSON file for performance.
    """
    if os.path.exists(_STOCK_MASTER_FILE):
        try:
            with open(_STOCK_MASTER_FILE, "r", encoding="utf-8") as f:
                entries = json.load(f)
            # JSON load gives List[List], convert back to List[Tuple]
            entries = [tuple(e) for e in entries]
            logger.info(f"Combined stock master loaded from file: {len(entries)} entries.")
            return entries
        except Exception as e:
            logger.error(f"Failed to load stock master file: {e}")

    # Fallback to loading directly (if script wasn't run)
    logger.info("Stock master file not found or failed to load. Fetching directly...")
    nse = _load_nse()
    if not nse:
        nse = _FALLBACK
    
    bse = _load_bse(nse_master=nse)

    entries = []
    for sym, name in nse.items():
        entries.append((sym, name, "NSE"))
    for sym, name in bse.items():
        entries.append((sym, name, "BSE"))

    entries.sort(key=lambda x: (str(x[0]), str(x[2])))
    return entries


# Keep for backward compatibility
@st.cache_data(ttl=86400, show_spinner=False)
def load_nse_stock_master() -> Dict[str, str]:
    """Return {SYMBOL: 'Company Name'} for NSE stocks (backward compat.)."""
    entries = load_combined_stock_master()
    return {sym: name for sym, name, exch in entries if exch == "NSE"}


def build_all_labels(entries: List[tuple]) -> List[str]:
    """
    Build sorted selectbox option labels from the combined entries list.
    Format: 'SYMBOL — Company Name [NSE]' or 'SYMBOL — Company Name [BSE]'
    """
    labels = [f"{sym} — {name} [{exch}]" for sym, name, exch in entries]
    return sorted(labels, key=lambda x: (x.split(" — ")[0], x))
