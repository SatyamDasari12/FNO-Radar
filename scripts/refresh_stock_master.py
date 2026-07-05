import requests
import pandas as pd
import json
import re
import os
from io import StringIO
from typing import Dict, List

# --- Configuration ---
NSE_URL = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
BSE_URL = "https://api.bseindia.com/BseIndiaAPI/api/ListofScripData/w?Group=&Scripcode=&segment=Equity&status=Active"
DATA_DIR = "data"
OUTPUT_FILE = os.path.join(DATA_DIR, "stock_master.json")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.bseindia.com/",
    "Origin": "https://www.bseindia.com"
}

def clean_stock_name(name: str) -> str:
    """Remove special characters like $, #, etc. from stock names."""
    if not name:
        return ""
    # Remove $, #, @, %, ^, *, and other common non-name symbols
    cleaned = re.sub(r'[\$#@%\^\*\[\]\(\)\+=\{}:;\"\'<>\?|\\_]', '', name)
    # Generic cleanup of multiple spaces
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned

def refresh():
    print("Starting stock master refresh...")
    
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

    # 1. Load NSE
    print("Fetching NSE data...")
    try:
        resp = requests.get(NSE_URL, headers=HEADERS, timeout=30)
        resp.raise_for_status()
        df = pd.read_csv(StringIO(resp.text))
        if "SERIES" in df.columns:
            df = df[df["SERIES"].isin(["EQ", "BE", "BZ", "SM", "ST"])]
        
        nse_master = {
            str(r["SYMBOL"]).strip(): clean_stock_name(str(r["NAME OF COMPANY"]))
            for _, r in df.iterrows()
            if pd.notna(r["SYMBOL"]) and pd.notna(r["NAME OF COMPANY"])
        }
        print(f"Loaded {len(nse_master)} NSE stocks.")
    except Exception as e:
        print(f"Error loading NSE: {e}")
        return

    # 2. Load BSE
    print("Fetching BSE data...")
    try:
        # Use the specific headers the user mentioned
        bse_headers = {
            'accept': 'application/json, text/plain, */*',
            'accept-language': 'en-US,en-IN;q=0.9,en;q=0.8',
            'origin': 'https://www.bseindia.com',
            'referer': 'https://www.bseindia.com/',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36'
        }
        resp = requests.get(BSE_URL, headers=bse_headers, timeout=30)
        resp.raise_for_status()
        rows = resp.json()
        
        bse_master = {}
        for row in rows:
            scrip_cd = str(row.get("SCRIP_CD", "")).strip()
            # As per user: scrip_id is the stock symbol
            scrip_id = str(row.get("scrip_id", "")).strip()
            scrip_name = clean_stock_name(str(row.get("Scrip_Name", "")))
            
            if not scrip_cd:
                continue
                
            # Use alphanumeric scrip_id if available, fallback to numeric SCRIP_CD
            sym = scrip_id if scrip_id else scrip_cd
            bse_master[sym] = scrip_name
            
        print(f"Loaded {len(bse_master)} BSE stocks.")
            
    except Exception as e:
        print(f"Error loading BSE: {e}")
        return

    # 3. Combine and Save
    print("Combining results...")
    entries = []
    for sym, name in nse_master.items():
        entries.append([sym, name, "NSE"])
    for sym, name in bse_master.items():
        entries.append([sym, name, "BSE"])

    # Sort
    entries.sort(key=lambda x: (str(x[0]), str(x[2])))

    print(f"Saving {len(entries)} entries to {OUTPUT_FILE}...")
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2)
    
    print("Refresh complete!")

if __name__ == "__main__":
    refresh()
