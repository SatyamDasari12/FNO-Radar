import requests
import pandas as pd
import io

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*"
}

# Fetch Midcap 150
resp_mid = requests.get("https://archives.nseindia.com/content/indices/ind_niftymidcap150list.csv", headers=headers, timeout=8)
if resp_mid.status_code == 200:
    df_mid = pd.read_csv(io.StringIO(resp_mid.text))
    symbols_mid = df_mid["Symbol"].dropna().tolist()
    print("MIDCAP_150_FALLBACK = [")
    # print in chunks of 10
    for i in range(0, len(symbols_mid), 10):
        chunk = symbols_mid[i:i+10]
        print("    " + ", ".join(f"'{s}'" for s in chunk) + ",")
    print("]")

print("\n" + "="*50 + "\n")

# Fetch Smallcap 250
resp_small = requests.get("https://archives.nseindia.com/content/indices/ind_niftysmallcap250list.csv", headers=headers, timeout=8)
if resp_small.status_code == 200:
    df_small = pd.read_csv(io.StringIO(resp_small.text))
    symbols_small = df_small["Symbol"].dropna().tolist()
    print("SMALLCAP_250_FALLBACK = [")
    for i in range(0, len(symbols_small), 10):
        chunk = symbols_small[i:i+10]
        print("    " + ", ".join(f"'{s}'" for s in chunk) + ",")
    print("]")
