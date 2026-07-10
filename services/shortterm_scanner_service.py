from __future__ import annotations

import io
import json
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests
import yfinance as yf
from ta.momentum import RSIIndicator
from ta.trend import MACD
from ta.volatility import AverageTrueRange, BollingerBands

from services.scanner_service import SYMBOL_SECTOR_MAP
from utils.logging import logger

# --- NSE CSV endpoints for universe lists ---
LARGECAP_100_URL = "https://archives.nseindia.com/content/indices/ind_nifty100list.csv"
MIDCAP_150_URL = "https://archives.nseindia.com/content/indices/ind_niftymidcap150list.csv"
NIFTY_NEXT_50_URL = "https://archives.nseindia.com/content/indices/ind_niftynext50list.csv"
SMALLCAP_250_URL = "https://archives.nseindia.com/content/indices/ind_niftysmallcap250list.csv"
MICROCAP_250_URL = "https://archives.nseindia.com/content/indices/ind_niftymicrocap250_list.csv"

# --- Hardcoded Fallback Lists (200+ Stocks Each) ---
LARGECAP_FALLBACK = [
    "ABB", "ADANIENSOL", "ADANIENT", "ADANIGREEN", "ADANIPORTS", "ADANIPOWER", "AMBUJACEM", "APOLLOHOSP", "ASIANPAINT", "DMART",
    "AXISBANK", "BAJAJ-AUTO", "BAJFINANCE", "BAJAJFINSV", "BAJAJHLDNG", "BANKBARODA", "BEL", "BPCL", "BHARTIARTL", "BOSCHLTD",
    "BRITANNIA", "CGPOWER", "CANBK", "CHOLAFIN", "CIPLA", "COALINDIA", "CUMMINSIND", "DLF", "DIVISLAB", "DRREDDY",
    "EICHERMOT", "ETERNAL", "GAIL", "GODREJCP", "GRASIM", "HCLTECH", "HDFCAMC", "HDFCBANK", "HDFCLIFE", "HINDALCO",
    "HAL", "HINDUNILVR", "HINDZINC", "HYUNDAI", "ICICIBANK", "ITC", "INDHOTEL", "IOC", "IRFC", "INFY",
    "INDIGO", "JSWSTEEL", "JINDALSTEL", "JIOFIN", "KOTAKBANK", "LTM", "LT", "LODHA", "M&M", "MARUTI",
    "MAXHEALTH", "MAZDOCK", "MUTHOOTFIN", "NTPC", "NESTLEIND", "ONGC", "PIDILITIND", "PFC", "POWERGRID", "PNB",
    "RECLTD", "RELIANCE", "SBILIFE", "MOTHERSON", "SHREECEM", "SHRIRAMFIN", "ENRIN", "SIEMENS", "SOLARINDS", "SBIN",
    "SUNPHARMA", "TVSMOTOR", "TATACAP", "TCS", "TATACONSUM", "TMCV", "TMPV", "TATAPOWER", "TATASTEEL", "TECHM",
    "TITAN", "TORNTPHARM", "TRENT", "ULTRACEMCO", "UNIONBANK", "UNITDSPR", "VBL", "VEDL", "WIPRO", "ZYDUSLIFE"
]

MIDCAP_FALLBACK = [
    "360ONE", "3MINDIA", "ACC", "AIAENG", "APLAPOLLO", "AUBANK", "AWL", "ABBOTINDIA", "ATGL", "ABCAPITAL",
    "AJANTPHARM", "ALKEM", "ANTHEM", "APARINDS", "APOLLOTYRE", "ASHOKLEY", "ASTRAL", "AUROPHARMA", "AIIL", "BSE",
    "BAJAJHFL", "BALKRISIND", "BANKINDIA", "MAHABANK", "BERGEPAINT", "BDL", "BHARATFORG", "BHEL", "BHARTIHEXA", "GROWW",
    "BIOCON", "BLUESTARCO", "CRISIL", "COCHINSHIP", "COFORGE", "COLPAL", "CONCOR", "COROMANDEL", "DABUR", "DALBHARAT",
    "DIXON", "ENDURANCE", "ESCORTS", "EXIDEIND", "NYKAA", "FEDERALBNK", "FORTIS", "GVT&D", "GMRAIRPORT", "GICRE",
    "GLAXO", "GLENMARK", "MEDANTA", "GODFRYPHLP", "GODREJIND", "GODREJPROP", "FLUOROCHEM", "HDBFS", "HAVELLS", "HEROMOTOCO",
    "HEXT", "HINDPETRO", "POWERINDIA", "HONAUT", "HUDCO", "ICICIGI", "ICICIAMC", "ICICIPRULI", "IDFCFIRSTB", "ITCHOTELS",
    "INDIANB", "IRCTC", "IREDA", "INDUSTOWER", "INDUSINDBK", "NAUKRI", "IPCALAB", "JKCEMENT", "JSWENERGY", "JSWINFRA",
    "JSL", "JUBLFOOD", "KPRMILL", "KEI", "KPITTECH", "KALYANKJIL", "LTF", "LTTS", "LGEINDIA", "LICHSGFIN",
    "LAURUSLABS", "LENSKART", "LICI", "LINDEINDIA", "LLOYDSME", "LUPIN", "MRF", "M&MFIN", "MANKIND", "MARICO",
    "MFSL", "MOTILALOFS", "MPHASIS", "MCX", "NHPC", "NLCINDIA", "NMDC", "NTPCGREEN", "NATIONALUM", "NAM-INDIA",
    "OBEROIRLTY", "OIL", "PAYTM", "OFSS", "POLICYBZR", "PIIND", "PAGEIND", "PATANJALI", "PERSISTENT", "PETRONET",
    "PHOENIXLTD", "POLYCAB", "PREMIERENE", "PRESTIGE", "RADICO", "RVNL", "SBICARD", "SJVN", "SRF", "SCHAEFFLER",
    "SAIL", "SUNDARMFIN", "SUPREMEIND", "SUZLON", "SWIGGY", "TATACOMM", "TATAELXSI", "TATAINVEST", "NIACL", "THERMAX",
    "TORNTPOWER", "TIINDIA", "UNOMINDA", "UPL", "UBL", "VMM", "IDEA", "VOLTAS", "WAAREEENER", "YESBANK",
    "ABB", "ADANIENSOL", "ADANIGREEN", "ADANIPOWER", "AMBUJACEM", "DMART", "BAJAJHLDNG", "BANKBARODA", "BPCL", "BOSCHLTD",
    "BRITANNIA", "CGPOWER", "CANBK", "CHOLAFIN", "CUMMINSIND", "DLF", "DIVISLAB", "GAIL", "GODREJCP", "HDFCAMC",
    "HAL", "HINDZINC", "HYUNDAI", "INDHOTEL", "IOC", "IRFC", "JINDALSTEL", "LTM", "LODHA", "MAZDOCK",
    "MUTHOOTFIN", "PIDILITIND", "PFC", "PNB", "RECLTD", "MOTHERSON", "SHREECEM", "ENRIN", "SIEMENS", "SOLARINDS",
    "TVSMOTOR", "TATACAP", "TMCV", "TATAPOWER", "TORNTPHARM", "UNIONBANK", "UNITDSPR", "VBL", "VEDL", "ZYDUSLIFE"
]

SMALLCAP_FALLBACK = [
    "ACMESOLAR", "AADHARHFC", "AARTIIND", "AAVAS", "ACE", "ACUTAAS", "ABFRL", "ABLBL", "ABREL", "ABSLAMC",
    "CPPLUS", "AEGISLOG", "AEGISVOPAK", "AFCONS", "AFFLE", "ABDL", "ARE&M", "AMBER", "ANANDRATHI", "ANANTRAJ",
    "ANGELONE", "ANURAS", "APTUS", "ASAHIINDIA", "ASTERDM", "ATHERENERG", "ATUL", "BEML", "BLS", "BALRAMCHIN",
    "BANDHANBNK", "BATAINDIA", "BAYERCROP", "BELRISE", "BIKAJI", "BSOFT", "BLUEDART", "BLUEJET", "BBTC", "FIRSTCRY",
    "BRIGADE", "MAPMYINDIA", "CCL", "CESC", "CIEINDIA", "CANFINHOME", "CANHLIFE", "CAPLIPOINT", "CGCL", "CARBORUNIV",
    "CARTRADE", "CASTROLIND", "CEATLTD", "CEMPRO", "CENTRALBK", "CDSL", "CHALET", "CHAMBLFERT", "CHENNPETRO", "CHOICEIN",
    "CHOLAHLDNG", "CUB", "CLEAN", "COHANCE", "CAMS", "CONCORDBIO", "CRAFTSMAN", "CREDITACC", "CROMPTON", "CYIENT",
    "DCMSHRIRAM", "DOMS", "DATAPATTNS", "DEEPAKFERT", "DEEPAKNTR", "DELHIVERY", "DEVYANI", "LALPATHLAB", "EIDPARRY", "EIHOTEL",
    "ELECON", "ELGIEQUIP", "EMAMILTD", "EMCURE", "EMMVEE", "ENGINERSIN", "ERIS", "FACT", "FINCABLES", "FSL",
    "FIVESTAR", "FORCEMOT", "GABRIEL", "GALLANTT", "GRSE", "GILLETTE", "GLAND", "GODIGIT", "GPIL", "GRANULES",
    "GRAPHITE", "GRAVITA", "GESHIP", "GMDCLTD", "HEG", "HBLENGINE", "HFCL", "HSCL", "HINDCOPPER", "HOMEFIRST",
    "HONASA", "IDBI", "IFCI", "IIFL", "IRB", "IRCON", "ITI", "INDGN", "INDIACEM", "INDIAMART",
    "IEX", "IOB", "IGL", "INOXWIND", "INTELLECT", "IGIL", "IKS", "JBCHEPHARM", "JBMA", "JKTYRE",
    "JMFINANCIL", "JSWCEMENT", "JSWDULUX", "JAINREC", "JPPOWER", "J&KBANK", "JINDALSAW", "JUBLINGREA", "JUBLPHARMA", "JWL",
    "JYOTICNC", "KAJARIACER", "KPIL", "KARURVYSYA", "KAYNES", "KEC", "KFINTECH", "KIRLOSENG", "KIMS", "LTFOODS",
    "LATENTVIEW", "THELEELA", "LEMONTREE", "MMTC", "MGL", "MANAPPURAM", "MRPL", "MEESHO", "MINDACORP", "MSUMI",
    "NATCOPHARM", "NBCC", "NCC", "NSLNISP", "NH", "NAVA", "NAVINFLUOR", "NETWEB", "NEULANDLAB", "NEWGEN",
    "NIVABUPA", "NUVAMA", "NUVOCO", "OLAELEC", "OLECTRA", "ONESOURCE", "PCBL", "PGEL", "PNBHOUSING", "PTCIL",
    "PVRINOX", "PARADEEP", "PFIZER", "PWL", "PINELABS", "PIRAMALFIN", "PPLPHARMA", "POLYMED", "POONAWALLA", "RRKABEL",
    "RBLBANK", "RHIM", "RITES", "RAILTEL", "RAINBOW", "RKFORGE", "REDINGTON", "RPOWER", "SBFC", "SAGILITY"
]

MICROCAP_FALLBACK = [
    "ASKAUTOLTD", "AXISCADES", "AARTIDRUGS", "AARTIPHARM", "AVL", "ADVENZYMES", "AEQUS", "AETHER", "AHLUCONT", "AKUMS",
    "APLLTD", "ALIVUS", "ALKYLAMINE", "AGL", "ALOKINDS", "APOLLO", "ACI", "ARVINDFASN", "ARVIND", "ASHAPURMIN",
    "ASHOKA", "ASTRAMICRO", "ATLANTAELE", "AURIONPRO", "AVALON", "AVANTIFEED", "CCAVENUE", "AWFIS", "AZAD", "BAJAJELEC",
    "BALAMINES", "BALUFORGE", "BANCOINDIA", "BIRLACORPN", "BBOX", "BLACKBUCK", "BLUESTONE", "BORORENEW", "CMSINFO", "CORONA",
    "CSBBANK", "CAMPUS", "CRAMC", "CAPILLARY", "CELLO", "CENTURYPLY", "CERA", "CRIZAC", "CUPID", "DCBBANK",
    "DATAMATICS", "DIACABS", "DBL", "AGARWALEYE", "DYNAMATECH", "EPL", "EDELWEISS", "EMIL", "ELECTCAST", "ELLEN",
    "EMBDL", "ENTERO", "EIEL", "EQUITASBNK", "ETHOSLTD", "EUREKAFORB", "FEDFINA", "FIEMIND", "FINPIPE", "UTLSOLAR",
    "GHCL", "GMMPFAUDLR", "GMRP&UI", "GRWRHITECH", "GODREJAGRO", "GOKEX", "GOKULAGRO", "GREAVESCOT", "GAEL", "GNFC",
    "GPPL", "GSFC", "HGINFRA", "HAPPSTMNDS", "HCG", "HEMIPROP", "HERITGFOOD", "HCC", "IFBIND", "IIFLCAPS",
    "INOXINDIA", "INDIAGLYCO", "INDIASHLTR", "IMFA", "INDIGOPNTS", "ICIL", "INOXGREEN", "IONEXCHANG", "JKLAKSHMI", "JKPAPER",
    "JAIBALAJI", "JAMNAAUTO", "JSFB", "JAYNECOIND", "JSLL", "JLHL", "JUSTDIAL", "JYOTHYLAB", "KNRCON", "KPIGREEN",
    "KRBL", "KRN", "KSB", "KANSAINER", "KTKBANK", "KSCL", "KIRLOSBROS", "KIRLPNU", "KITEX", "LXCHEM",
    "IXIGO", "LLOYDSENGG", "LLOYDSENT", "LUMAXTECH", "MOIL", "MSTCLTD", "MTARTECH", "MAHSCOOTER", "MAHSEAMLES", "MANORAMA",
    "MARKSANS", "MASTEK", "MEDPLUS", "METROPOLIS", "MIDHANI", "BECTORFOOD", "NEOGEN", "NESCO", "NFL", "NAZARA",
    "NETWORK18", "OPTIEMUS", "ORIENTCEM", "ORKLAINDIA", "OSWALPUMPS", "PNGJL", "PCJEWELLER", "PNCINFRA", "PTC", "PARAS",
    "PARKHOSPS", "PGIL", "PICCADIL", "POWERMECH", "PRAJIND", "PRICOLLTD", "PFOCUS", "PRSMJOHNSN", "PRIVISCL", "PRUDENT",
    "PURVA", "QPOWER", "QUESS", "RAIN", "RALLIS", "RCF", "RATEGAIN", "RATNAMANI", "RTNINDIA", "RTNPOWER",
    "RAYMONDLSL", "REDTAPE", "REFEX", "RELAXO", "RELIGARE", "RBA", "ROUTE", "RUBICON", "SKFINDUS", "SKFINDIA",
    "SKYGOLD", "SMLMAH", "SHRIPISTON", "SAATVIKGL", "SAFARI", "SAMHI", "SANDUMA", "SANOFICONR", "SANSERA", "SENCO",
    "STYL", "SHAILY", "SHAKTIPUMP", "SHARDACROP", "SHAREINDIA", "SFL", "SHILPAMED", "RENUKA", "SKIPPER", "SMARTWORKS",
    "SOUTHBANK", "LOTUSDEV", "STARCEMENT", "SWSOLAR", "STLTECH", "STAR", "STYRENIX", "SUBROS", "SUDARSCHEM", "SUDEEPPHRM",
    "SPARC", "SUNTECK", "SUPRIYA", "SURYAROSNI", "TARC", "TDPOWERSYS", "TSFINV", "TVSSCS", "TMB", "TANLA",
    "TEXRAIL", "THANGAMAYL", "ANUP", "THOMASCOOK", "THYROCARE", "TI", "TIMETECHNO", "TIPSMUSIC", "TRANSRAILL", "TRIVENI",
    "UJJIVANSFB", "VGUARD", "VMART", "VIPIND", "V2RETAIL", "WABAG", "VAIBHAVGBL", "DBREALTY", "VARROC", "MANYAVAR",
    "VIKRAMSOLR", "VIYASH", "VOLTAMP", "WAAREERTL", "WAKEFIT", "WEWORK", "WEBELSOLAR", "WELENT", "WESTLIFE", "YATHARTH",
    "ZAGGLE"
]

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*"
}

def load_universe_symbols(universe: str) -> List[str]:
    """Fetch symbols for Largecap 100, Midcap 200, Smallcap 200, or Microcap 250 dynamically, falling back to static lists."""
    univ_lower = universe.lower()
    if "f&o" in univ_lower or "fno" in univ_lower:
        fno_syms = load_fno_symbols()
        if fno_syms:
            logger.info(f"Loaded {len(fno_syms)} F&O symbols.")
            return [f"{s}.NS" for s in fno_syms]
        # fallback to top largecaps if no fno data
        univ_lower = "large"
    
    if "large" in univ_lower:
        fallback = LARGECAP_FALLBACK
        url = LARGECAP_100_URL
        try:
            resp = requests.get(url, headers=_HEADERS, timeout=8)
            if resp.status_code == 200:
                df = pd.read_csv(io.StringIO(resp.text))
                if "Symbol" in df.columns:
                    syms = [f"{str(s).strip()}.NS" for s in df["Symbol"].dropna().tolist()]
                    logger.info(f"Loaded {len(syms)} symbols dynamically from NSE for {universe}.")
                    return syms
        except Exception as e:
            logger.warning(f"Error fetching {universe} from NSE: {e}. Using fallback list.")
            
    elif "mid" in univ_lower:
        fallback = MIDCAP_FALLBACK
        try:
            resp_mid = requests.get(MIDCAP_150_URL, headers=_HEADERS, timeout=8)
            resp_next = requests.get(NIFTY_NEXT_50_URL, headers=_HEADERS, timeout=8)
            
            syms = []
            if resp_mid.status_code == 200:
                df_mid = pd.read_csv(io.StringIO(resp_mid.text))
                if "Symbol" in df_mid.columns:
                    syms.extend([f"{str(s).strip()}.NS" for s in df_mid["Symbol"].dropna().tolist()])
            if resp_next.status_code == 200:
                df_next = pd.read_csv(io.StringIO(resp_next.text))
                if "Symbol" in df_next.columns:
                    syms.extend([f"{str(s).strip()}.NS" for s in df_next["Symbol"].dropna().tolist()])
            
            syms = list(dict.fromkeys(syms))
            if len(syms) >= 150:
                logger.info(f"Loaded {len(syms)} symbols dynamically from NSE for {universe}.")
                return syms
        except Exception as e:
            logger.warning(f"Error fetching {universe} from NSE: {e}. Using fallback list.")
            
    elif "small" in univ_lower:
        fallback = SMALLCAP_FALLBACK
        try:
            resp = requests.get(SMALLCAP_250_URL, headers=_HEADERS, timeout=8)
            if resp.status_code == 200:
                df = pd.read_csv(io.StringIO(resp.text))
                if "Symbol" in df.columns:
                    syms = [f"{str(s).strip()}.NS" for s in df["Symbol"].dropna().tolist()][:200]
                    logger.info(f"Loaded {len(syms)} symbols dynamically from NSE for {universe}.")
                    return syms
        except Exception as e:
            logger.warning(f"Error fetching {universe} from NSE: {e}. Using fallback list.")
            
    else:  # microcap / maco
        fallback = MICROCAP_FALLBACK
        url = MICROCAP_250_URL
        try:
            resp = requests.get(url, headers=_HEADERS, timeout=8)
            if resp.status_code == 200:
                df = pd.read_csv(io.StringIO(resp.text))
                if "Symbol" in df.columns:
                    syms = [f"{str(s).strip()}.NS" for s in df["Symbol"].dropna().tolist()]
                    logger.info(f"Loaded {len(syms)} symbols dynamically from NSE for {universe}.")
                    return syms
        except Exception as e:
            logger.warning(f"Error fetching {universe} from NSE: {e}. Using fallback list.")

    logger.warning(f"Failed to fetch {universe} from NSE. Using fallback list.")
    return [f"{s}.NS" for s in fallback]

def load_fno_symbols() -> set[str]:
    """Load list of F&O symbols to identify derivatives status."""
    fno_path = "data/fno_master.json"
    if os.path.exists(fno_path):
        try:
            with open(fno_path, "r", encoding="utf-8") as f:
                entries = json.load(f)
            return {str(e["symbol"]).strip().upper() for e in entries if "symbol" in e}
        except Exception as e:
            logger.error(f"Error loading fno_master.json: {e}")
    return set()

def fetch_india_vix() -> float:
    """Fetch the latest closing price of India VIX from Yahoo Finance."""
    try:
        vix = yf.Ticker("^INDIAVIX")
        df = vix.history(period="5d")
        if not df.empty:
            # Flatten multi-index if present
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [col[0] for col in df.columns]
            return float(df["Close"].iloc[-1])
    except Exception as e:
        logger.warning(f"Could not fetch India VIX: {e}")
    return 13.5  # Neutral default VIX

def calculate_shortterm_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Compute all technical indicators for the ShortTerm Scanner.

    Indicators computed:
        - EMA 20, SMA 20, SMA 50 (Moving Averages)
        - RSI 14 (Momentum oscillator)
        - MACD / MACD Signal / MACD Histogram (Trend acceleration)
        - ATR 14 (Volatility — used for stop loss and targets)
        - Bollinger Bands 20,2 (Volatility squeeze/breakout)
        - 5-day Rolling VWAP (Short-term value anchor)
        - 5-day Momentum % (Speed of price move)
        - 10-day High Breakout flag (Breakout strength)
        - Volume Spike flag (1.5x 20-day avg)
        - Volume Ratio (continuous, for scoring)
    """
    if df.empty:
        return df

    # Ensure single level columns
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [col[0] for col in df.columns]

    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df.get("Volume")

    n = len(df)

    # ── Moving Averages ───────────────────────────────────────────────
    df["EMA_20"] = close.ewm(span=20, adjust=False).mean()
    df["SMA_20"] = close.rolling(window=20, min_periods=10).mean()
    df["SMA_50"] = close.rolling(window=50, min_periods=25).mean()

    # ── RSI (14) ──────────────────────────────────────────────────────
    if n >= 14:
        df["RSI_14"] = RSIIndicator(close=close, window=14).rsi()
    else:
        df["RSI_14"] = 50.0

    # ── MACD (12, 26, 9) ─────────────────────────────────────────────
    if n >= 26:
        macd_obj = MACD(close=close, window_slow=26, window_fast=12, window_sign=9)
        df["MACD"] = macd_obj.macd()
        df["MACD_SIGNAL"] = macd_obj.macd_signal()
        df["MACD_HIST"] = macd_obj.macd_diff()
    else:
        df["MACD"] = 0.0
        df["MACD_SIGNAL"] = 0.0
        df["MACD_HIST"] = 0.0

    # ── ATR (14) ──────────────────────────────────────────────────────
    if n >= 14:
        atr_obj = AverageTrueRange(high=high, low=low, close=close, window=14)
        df["ATR_14"] = atr_obj.average_true_range()
    else:
        df["ATR_14"] = close * 0.04  # 4% fallback for very short data

    # ── Bollinger Bands (20, 2) ───────────────────────────────────────
    if n >= 20:
        bb = BollingerBands(close=close, window=20, window_dev=2)
        df["BB_HIGH"] = bb.bollinger_hband()
        df["BB_MID"] = bb.bollinger_mavg()
        df["BB_LOW"] = bb.bollinger_lband()
        df["BB_WIDTH"] = (df["BB_HIGH"] - df["BB_LOW"]) / close
    else:
        df["BB_HIGH"] = close * 1.05
        df["BB_MID"] = close
        df["BB_LOW"] = close * 0.95
        df["BB_WIDTH"] = 0.1

    # ── 5-Day Rolling VWAP (fixes cumulative VWAP bias) ───────────────
    if volume is not None:
        tp = (high + low + close) / 3.0
        vp = tp * volume
        df["VWAP"] = vp.rolling(window=5, min_periods=1).sum() / volume.rolling(window=5, min_periods=1).sum().replace(0, 1.0)

        # Volume Spike (1.5x 20-day average — standardised)
        vol_mean = volume.rolling(window=20, min_periods=10).mean()
        df["VOLUME_SPIKE"] = (volume > 1.5 * vol_mean).astype(int)

        # Continuous volume ratio for scoring
        df["VOLUME_RATIO"] = (volume / vol_mean.replace(0, 1.0)).fillna(1.0)
    else:
        df["VWAP"] = close
        df["VOLUME_SPIKE"] = 0
        df["VOLUME_RATIO"] = 1.0

    # ── 5-Day Momentum % ─────────────────────────────────────────────
    if n >= 6:
        df["MOMENTUM_5D"] = (close / close.shift(5) - 1.0) * 100.0
    else:
        df["MOMENTUM_5D"] = 0.0

    # ── 10-Day High Breakout ──────────────────────────────────────────
    if n >= 10:
        df["HIGH_10D"] = high.rolling(window=10, min_periods=5).max()
        df["BREAKOUT_10D"] = (close > df["HIGH_10D"].shift(1)).astype(int)
    else:
        df["HIGH_10D"] = high
        df["BREAKOUT_10D"] = 0

    return df

def fetch_nifty_return_10d() -> float:
    """Fetch Nifty 50's 10-day return for relative strength calculation."""
    try:
        nifty = yf.Ticker("^NSEI")
        df = nifty.history(period="15d")
        if not df.empty:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = [c[0] for c in df.columns]
            if len(df) >= 10:
                return (float(df["Close"].iloc[-1]) / float(df["Close"].iloc[-10]) - 1.0) * 100.0
    except Exception as e:
        logger.warning(f"Could not fetch Nifty return: {e}")
    return 0.0


def score_stock(
    symbol_bare: str,
    df: pd.DataFrame,
    vix: float,
    fno_symbols: set[str],
    nifty_return_10d: float = 0.0
) -> Tuple[float, Dict[str, float]]:
    """
    Calculate the ShortTerm Composite Score (0 – 100) using continuous normalisation.

    Revised weight allocation:
        Momentum 5D       : 20%  (speed of move — primary edge)
        Moving Averages    : 15%  (trend confirmation)
        Volume Expansion   : 15%  (breakout validation)
        Bollinger Bands    : 10%  (squeeze/breakout detection)
        MACD Histogram     : 10%  (momentum acceleration)
        Breakout Strength  : 10%  (10-day high breakout)
        RSI Sweet Spot     : 10%  (momentum zone)
        Relative Strength  :  5%  (vs Nifty)
        India VIX          :  5%  (market risk)
    """
    if df.empty or len(df) < 5:
        return 0.0, {}

    last = df.iloc[-1]
    close = float(last["Close"])
    prev_close = float(df["Close"].iloc[-2]) if len(df) >= 2 else close

    # Initialize sub-scores (each normalised to its max weight)
    scores: Dict[str, float] = {}

    # ── 1. 5-Day Momentum (20%) ──────────────────────────────────────
    #    Normalized: clamp to [0, 20]. Raw momentum * 2.5, capped at 20.
    momentum_raw = float(last.get("MOMENTUM_5D", 0.0)) if pd.notna(last.get("MOMENTUM_5D")) else 0.0
    # Positive momentum is good; negative gets 0
    momentum_norm = min(20.0, max(0.0, momentum_raw * 2.5))
    scores["momentum"] = round(momentum_norm, 1)

    # ── 2. Moving Averages (15%) ─────────────────────────────────────
    #    Continuous: measure % distance above/below EMA 20 and EMA vs SMA 50
    ema20 = float(last["EMA_20"]) if pd.notna(last.get("EMA_20")) else close
    sma50 = float(last["SMA_50"]) if pd.notna(last.get("SMA_50")) else close

    ma_points = 0.0
    # How far above EMA 20 (0-10 pts, scaled by distance up to 5%)
    ema_dist_pct = (close - ema20) / ema20 * 100.0 if ema20 > 0 else 0.0
    ma_points += min(10.0, max(0.0, ema_dist_pct * 2.0))
    # EMA 20 above SMA 50 (0-5 pts)
    ema_sma_dist = (ema20 - sma50) / sma50 * 100.0 if sma50 > 0 else 0.0
    ma_points += min(5.0, max(0.0, ema_sma_dist * 1.0))
    scores["ma"] = round(min(15.0, ma_points), 1)

    # ── 3. Volume Expansion (15%) ────────────────────────────────────
    #    Continuous scoring using volume ratio
    vol_ratio = float(last.get("VOLUME_RATIO", 1.0)) if pd.notna(last.get("VOLUME_RATIO")) else 1.0
    change_pct = (close - prev_close) / prev_close * 100.0 if prev_close > 0 else 0.0
    is_fno = symbol_bare in fno_symbols

    # Volume score: ratio mapped to 0-10 (1x=0, 2x=10)
    vol_score = min(10.0, max(0.0, (vol_ratio - 1.0) * 10.0))
    # Directional bonus: volume + price up = long buildup (0-5 pts)
    if change_pct > 0 and vol_ratio > 1.2:
        vol_score += min(5.0, change_pct * 1.0)
        if is_fno:
            vol_score = min(15.0, vol_score + 1.0)  # F&O bonus
    scores["volume"] = round(min(15.0, vol_score), 1)

    # ── 4. Bollinger Bands (10%) ─────────────────────────────────────
    bb_high = float(last["BB_HIGH"]) if pd.notna(last.get("BB_HIGH")) else close * 1.05
    bb_mid = float(last["BB_MID"]) if pd.notna(last.get("BB_MID")) else close
    bb_low = float(last["BB_LOW"]) if pd.notna(last.get("BB_LOW")) else close * 0.95
    bb_width = float(last["BB_WIDTH"]) if pd.notna(last.get("BB_WIDTH")) else 0.1

    avg_bb_width = float(df["BB_WIDTH"].rolling(window=20).mean().iloc[-1]) if "BB_WIDTH" in df.columns and pd.notna(df["BB_WIDTH"].rolling(window=20).mean().iloc[-1]) else 0.15

    bb_range = bb_high - bb_low if bb_high > bb_low else 1.0
    bb_position = (close - bb_low) / bb_range  # 0 = at lower band, 1 = at upper band

    bb_points = 0.0
    if close > bb_high:
        bb_points = 10.0  # Breakout above upper band
    elif bb_width < avg_bb_width and bb_position > 0.5:
        bb_points = 7.0   # Squeeze + upper half = potential breakout
    else:
        bb_points = min(8.0, max(0.0, bb_position * 8.0))  # Continuous position score
    scores["bb"] = round(bb_points, 1)

    # ── 5. MACD Histogram (10%) ──────────────────────────────────────
    macd_hist = float(last.get("MACD_HIST", 0.0)) if pd.notna(last.get("MACD_HIST")) else 0.0
    prev_macd_hist = float(df["MACD_HIST"].iloc[-2]) if len(df) >= 2 and "MACD_HIST" in df.columns and pd.notna(df["MACD_HIST"].iloc[-2]) else 0.0

    macd_points = 0.0
    if macd_hist > 0:
        macd_points += 5.0  # Histogram positive
        if macd_hist > prev_macd_hist:
            macd_points += 5.0  # AND increasing = strong acceleration
        else:
            macd_points += 2.0  # Positive but decelerating
    elif macd_hist > prev_macd_hist:
        macd_points += 3.0  # Negative but improving (potential crossover)
    scores["macd"] = round(min(10.0, macd_points), 1)

    # ── 6. Breakout Strength (10%) ───────────────────────────────────
    is_breakout = bool(last.get("BREAKOUT_10D", 0)) if pd.notna(last.get("BREAKOUT_10D")) else False
    breakout_points = 10.0 if is_breakout else 0.0
    scores["breakout"] = breakout_points

    # ── 7. RSI Sweet Spot (10%) ──────────────────────────────────────
    #    Optimal zone shifted to 55-68 for short-term acceleration
    rsi = float(last.get("RSI_14", 50.0)) if pd.notna(last.get("RSI_14")) else 50.0

    if 55.0 <= rsi <= 68.0:
        rsi_points = 10.0  # Acceleration sweet spot
    elif 50.0 <= rsi < 55.0:
        rsi_points = 7.0   # Building momentum
    elif 68.0 < rsi <= 75.0:
        rsi_points = 6.0   # Strong but approaching overbought
    elif 45.0 <= rsi < 50.0:
        rsi_points = 4.0   # Neutral
    elif rsi > 75.0:
        rsi_points = 2.0   # Overbought risk
    else:
        rsi_points = 1.0   # Below 45 — weak
    scores["rsi"] = rsi_points

    # ── 8. Relative Strength vs Nifty (5%) ───────────────────────────
    if len(df) >= 10:
        stock_return_10d = (close / float(df["Close"].iloc[-10]) - 1.0) * 100.0
        rs_diff = stock_return_10d - nifty_return_10d
        rs_points = min(5.0, max(0.0, rs_diff * 1.0))  # 1 pt per 1% outperformance
    else:
        rs_points = 0.0
    scores["rs"] = round(rs_points, 1)

    # ── 9. India VIX (5%) ────────────────────────────────────────────
    if vix < 13:
        scores["vix"] = 5.0
    elif vix < 16:
        scores["vix"] = 4.0
    elif vix <= 20:
        scores["vix"] = 3.0
    elif vix <= 25:
        scores["vix"] = 1.5
    else:
        scores["vix"] = 0.5

    total_score = sum(scores.values())
    return round(min(100.0, total_score), 1), scores

def scan_shortterm_stocks(
    universe: str,
    top_n: int = 15,
    progress_callback = None
) -> pd.DataFrame:
    """Scan the selected universe and return ranked candidates with scores."""
    symbols = load_universe_symbols(universe)
    if not symbols:
        return pd.DataFrame()

    fno_symbols = load_fno_symbols()
    vix = fetch_india_vix()
    nifty_ret = fetch_nifty_return_10d()
    
    end_date = datetime.now().date() + timedelta(days=1)
    start_date = end_date - timedelta(days=365)  # Fetch 1 year of data for macro context
    
    rows = []
    total_symbols = len(symbols)
    
    for i, symbol in enumerate(symbols):
        symbol_bare = symbol.replace(".NS", "")
        if progress_callback:
            progress_callback(i + 1, total_symbols, symbol_bare)
            
        try:
            time.sleep(0.05)  # Respect rate limits
            df = yf.download(
                symbol,
                start=start_date,
                end=end_date,
                interval="1d",
                progress=False,
                auto_adjust=False
            )
            if df is None or df.empty or len(df) < 10:
                continue

            df = calculate_shortterm_indicators(df)
            score, sub_scores = score_stock(symbol_bare, df, vix, fno_symbols, nifty_ret)
            
            last_close = float(df["Close"].iloc[-1])
            prev_close = float(df["Close"].iloc[-2]) if len(df) >= 2 else last_close
            change_pct = (last_close - prev_close) / prev_close * 100.0 if prev_close > 0 else 0.0
            
            # Check if breakout or trend started in the last 2 days (Early Entry)
            is_early_entry = False
            if len(df) >= 4:
                ema_crossover = (df["Close"].iloc[-1] > df["EMA_20"].iloc[-1]) and (
                    df["Close"].iloc[-2] <= df["EMA_20"].iloc[-2] or
                    df["Close"].iloc[-3] <= df["EMA_20"].iloc[-3]
                )
                bb_breakout_recent = (df["Close"].iloc[-1] > df["BB_HIGH"].iloc[-1]) and (
                    df["Close"].iloc[-2] <= df["BB_HIGH"].iloc[-2] or
                    df["Close"].iloc[-3] <= df["BB_HIGH"].iloc[-3]
                )
                golden_cross_recent = (df["EMA_20"].iloc[-1] > df["SMA_50"].iloc[-1]) and (
                    df["EMA_20"].iloc[-2] <= df["SMA_50"].iloc[-2] or
                    df["EMA_20"].iloc[-3] <= df["SMA_50"].iloc[-3]
                )
                is_early_entry = bool(ema_crossover or bb_breakout_recent or golden_cross_recent)

            # Check for sideways breakout (consolidated for many days, broke out recently)
            is_sideways_breakout = False
            if len(df) >= 20:
                consolidation_window = df["Close"].iloc[-17:-2]
                max_c = float(consolidation_window.max())
                min_c = float(consolidation_window.min())
                range_pct = (max_c - min_c) / min_c * 100.0 if min_c > 0 else 999.0
                is_sideways = (range_pct <= 7.5)  # tight sideways consolidation
                
                recent_closes = df["Close"].iloc[-2:]
                has_breakout = (recent_closes > max_c).any()
                
                is_uptrend = float(df["Close"].iloc[-1]) > float(df["EMA_20"].iloc[-1])
                is_sideways_breakout = bool(is_sideways and has_breakout and is_uptrend)

            if is_sideways_breakout:
                score = min(100.0, score + 5.0)

            # 6-Month Sideways Indicator (approx 125 trading days)
            is_6m_sideways = False
            is_6m_breakout = False
            if len(df) >= 125:
                macro_window = df["Close"].iloc[-125:-2]
                macro_max = float(macro_window.max())
                macro_min = float(macro_window.min())
                macro_range_pct = (macro_max - macro_min) / macro_min * 100.0 if macro_min > 0 else 999.0
                
                # 20% range over 6 months defines macro consolidation
                is_6m_sideways = (macro_range_pct <= 20.0)
                
                recent_closes = df["Close"].iloc[-2:]
                is_6m_breakout = bool(is_6m_sideways and (recent_closes > macro_max).any())

            if is_6m_breakout:
                score = min(100.0, score + 7.5)  # Macro breakout gets higher bonus

            # Calculate ATR-based stop loss, targets, and risk:reward
            atr_val = float(df["ATR_14"].iloc[-1]) if ("ATR_14" in df.columns and pd.notna(df["ATR_14"].iloc[-1])) else (last_close * 0.04)
            if atr_val <= 0:
                atr_val = last_close * 0.04
            
            stop_loss = max(0.01, round(last_close - 1.5 * atr_val, 2))
            target1 = round(last_close + 1.5 * atr_val, 2)
            target2 = round(last_close + 3.0 * atr_val, 2)
            expected_price = target1

            # ── 1-Year Context & 2-Week Estimates ─────────────────────
            high_52w = float(df["High"].max()) if len(df) > 0 else last_close
            low_52w = float(df["Low"].min()) if len(df) > 0 else last_close
            close_1y_ago = float(df["Close"].iloc[0]) if len(df) > 0 else last_close
            
            return_1y = (last_close - close_1y_ago) / close_1y_ago * 100.0 if close_1y_ago > 0 else 0.0
            dist_from_high = (last_close - high_52w) / high_52w * 100.0 if high_52w > 0 else 0.0
            
            # Short-Term Estimate (14-day ATR * sqrt(10))
            micro_move = atr_val * 3.16
            
            # Macro Estimate (1-year daily volatility * close * sqrt(10))
            if len(df) > 20:
                daily_vol = float(df["Close"].pct_change().std())
                macro_move = daily_vol * last_close * 3.16 if pd.notna(daily_vol) else micro_move
            else:
                macro_move = micro_move
                
            est_micro_high = last_close + micro_move
            est_micro_low = max(0.01, last_close - micro_move)
            est_macro_high = last_close + macro_move
            est_macro_low = max(0.01, last_close - macro_move)
            # ─────────────────────────────────────────────────────────────

            # Risk:Reward ratio
            risk = last_close - stop_loss
            reward = target1 - last_close
            rr_ratio = round(reward / risk, 2) if risk > 0 else 0.0

            # Filter: skip candidates with poor risk:reward
            if rr_ratio < 1.0:
                continue

            # Calculate Expected Profit for ₹1 Lakh investment
            est_shares = 100000.0 / last_close
            profit_1lakh = round(est_shares * (target1 - last_close), 2)

            # Estimate holding period (days) based on momentum and volume
            rsi_val = float(df["RSI_14"].iloc[-1]) if "RSI_14" in df.columns else 50.0
            vol_ratio = float(df["VOLUME_RATIO"].iloc[-1]) if "VOLUME_RATIO" in df.columns else 1.0
            
            if rsi_val > 65 and vol_ratio > 1.5:
                holding_period = "5 - 8 days"
            elif rsi_val >= 55:
                holding_period = "8 - 12 days"
            else:
                holding_period = "12 - 18 days"

            # 5-day momentum for display
            momentum_5d = float(df["MOMENTUM_5D"].iloc[-1]) if ("MOMENTUM_5D" in df.columns and pd.notna(df["MOMENTUM_5D"].iloc[-1])) else 0.0

            # Identify special technical labels for display
            is_vol_spike = bool(df["VOLUME_SPIKE"].iloc[-1]) if "VOLUME_SPIKE" in df.columns else False
            bb_high = float(df["BB_HIGH"].iloc[-1]) if "BB_HIGH" in df.columns else last_close
            is_bb_breakout = last_close > bb_high
            is_10d_breakout = bool(df["BREAKOUT_10D"].iloc[-1]) if "BREAKOUT_10D" in df.columns else False
            macd_hist_val = float(df["MACD_HIST"].iloc[-1]) if "MACD_HIST" in df.columns and pd.notna(df["MACD_HIST"].iloc[-1]) else 0.0
            
            # Compile technical tags
            tags = []
            if is_early_entry:
                tags.append("Early Entry 🌟")
            if is_6m_breakout:
                tags.append("6M Breakout 🌋")
            elif is_6m_sideways:
                tags.append("6M Sideways 🧱")
            if is_sideways_breakout:
                tags.append("Sideways Breakout 🚀")
            if is_10d_breakout:
                tags.append("10D Breakout 🔥")
            if is_bb_breakout:
                tags.append("BB Breakout 🚀")
            if is_vol_spike:
                tags.append("Vol Spike ⚡")
            if macd_hist_val > 0:
                tags.append("MACD+ 📶")
            if symbol_bare in fno_symbols:
                tags.append("F&O 📊")
            
            rows.append({
                "Symbol": symbol_bare,
                "Company Name": symbol_bare,
                "Sector": SYMBOL_SECTOR_MAP.get(symbol, "Other"),
                "Close (₹)": round(last_close, 2),
                "Change%": round(change_pct, 2),
                "Momentum 5D%": round(momentum_5d, 2),
                "Score": score,
                "RSI": round(float(df["RSI_14"].iloc[-1]) if "RSI_14" in df.columns else 50.0, 1),
                "Momentum (20)": sub_scores.get("momentum", 0.0),
                "MA (15)": sub_scores.get("ma", 0.0),
                "Volume (15)": sub_scores.get("volume", 0.0),
                "BB (10)": sub_scores.get("bb", 0.0),
                "MACD (10)": sub_scores.get("macd", 0.0),
                "Breakout (10)": sub_scores.get("breakout", 0.0),
                "RSI (10)": sub_scores.get("rsi", 0.0),
                "RS (5)": sub_scores.get("rs", 0.0),
                "VIX (5)": sub_scores.get("vix", 0.0),
                "Technical Tags": ", ".join(tags) if tags else "Neutral",
                "Early Entry": is_early_entry,
                "Stop Loss (₹)": stop_loss,
                "Target 1 (₹)": target1,
                "Target 2 (₹)": target2,
                "Expected Price (₹)": expected_price,
                "R:R Ratio": rr_ratio,
                "Exp. Profit (₹1L)": profit_1lakh,
                "Holding Period": holding_period,
                "Return 1Y%": round(return_1y, 2),
                "High 52W (₹)": round(high_52w, 2),
                "Low 52W (₹)": round(low_52w, 2),
                "Dist from 52W High%": round(dist_from_high, 2),
                "Est 2W Micro Low": round(est_micro_low, 2),
                "Est 2W Micro High": round(est_micro_high, 2),
                "Est 2W Macro Low": round(est_macro_low, 2),
                "Est 2W Macro High": round(est_macro_high, 2)
            })
        except Exception as e:
            logger.exception(f"Error scanning stock {symbol_bare}: {e}")
            continue

    if not rows:
        return pd.DataFrame()

    df_results = pd.DataFrame(rows)
    df_results = df_results.sort_values(by="Score", ascending=False).head(top_n)
    return df_results.reset_index(drop=True)
