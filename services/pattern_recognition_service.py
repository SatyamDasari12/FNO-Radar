import pandas as pd
import numpy as np
from scipy.signal import find_peaks
from typing import List, Dict, Tuple, Any

def find_extrema(
    prices: pd.Series, 
    distance: int = 5, 
    prominence: float = 0.02
) -> Tuple[List[int], List[int]]:
    """
    Identify local peaks and valleys in a price series.
    
    Args:
        prices: pandas Series containing price data (e.g., Close).
        distance: Minimum number of bars between consecutive peaks/valleys.
        prominence: Minimum price drop/rise (as a percentage) to be considered an extremum.
        
    Returns:
        Tuple of (peak_indices, valley_indices).
    """
    price_array = prices.values
    
    # Calculate prominence in absolute price terms (using an approximation like median price * prominence ratio)
    # Alternatively, just use raw price values if prominence is provided as absolute, 
    # but since stocks vary widely in price, we convert percentage to an average absolute value or use a dynamic threshold.
    # To be robust, we'll use a rolling median or the mean price of the series to define the absolute prominence.
    avg_price = np.mean(price_array)
    abs_prominence = avg_price * prominence
    
    # Find Peaks
    peaks, _ = find_peaks(price_array, distance=distance, prominence=abs_prominence)
    
    # Find Valleys (by finding peaks of the inverted price array)
    valleys, _ = find_peaks(-price_array, distance=distance, prominence=abs_prominence)
    
    return peaks.tolist(), valleys.tolist()

def _is_within_threshold(p1: float, p2: float, threshold_pct: float) -> bool:
    """Check if two prices are within a certain percentage of each other."""
    avg_p = (p1 + p2) / 2
    return abs(p1 - p2) / avg_p <= threshold_pct

def detect_double_top(
    peaks: List[int], 
    valleys: List[int], 
    prices: pd.Series, 
    threshold_pct: float = 0.03
) -> List[Dict[str, Any]]:
    """
    Detect Double Top patterns.
    Pattern: Peak 1 -> Valley 1 -> Peak 2
    Condition: Peak 1 and Peak 2 are within threshold_pct of each other.
    """
    patterns = []
    if len(peaks) < 2:
        return patterns
        
    for i in range(len(peaks) - 1):
        p1_idx = peaks[i]
        p2_idx = peaks[i+1]
        
        p1_val = prices.iloc[p1_idx]
        p2_val = prices.iloc[p2_idx]
        
        if _is_within_threshold(p1_val, p2_val, threshold_pct):
            # Find a valley between these two peaks
            intermediate_valleys = [v for v in valleys if p1_idx < v < p2_idx]
            
            if intermediate_valleys:
                # Get the deepest valley between the peaks
                v1_idx = min(intermediate_valleys, key=lambda v: prices.iloc[v])
                v1_val = prices.iloc[v1_idx]
                
                # Check if the valley is significant (e.g. at least lower than the peaks)
                if v1_val < p1_val and v1_val < p2_val:
                    patterns.append({
                        "type": "Double Top",
                        "points": [
                            {"type": "Peak", "index": p1_idx, "price": p1_val},
                            {"type": "Valley", "index": v1_idx, "price": v1_val},
                            {"type": "Peak", "index": p2_idx, "price": p2_val}
                        ],
                        "end_idx": p2_idx
                    })
    return patterns

def detect_double_bottom(
    peaks: List[int], 
    valleys: List[int], 
    prices: pd.Series, 
    threshold_pct: float = 0.03
) -> List[Dict[str, Any]]:
    """
    Detect Double Bottom patterns.
    Pattern: Valley 1 -> Peak 1 -> Valley 2
    Condition: Valley 1 and Valley 2 are within threshold_pct of each other.
    """
    patterns = []
    if len(valleys) < 2:
        return patterns
        
    for i in range(len(valleys) - 1):
        v1_idx = valleys[i]
        v2_idx = valleys[i+1]
        
        v1_val = prices.iloc[v1_idx]
        v2_val = prices.iloc[v2_idx]
        
        if _is_within_threshold(v1_val, v2_val, threshold_pct):
            # Find a peak between these two valleys
            intermediate_peaks = [p for p in peaks if v1_idx < p < v2_idx]
            
            if intermediate_peaks:
                # Get the highest peak between the valleys
                p1_idx = max(intermediate_peaks, key=lambda p: prices.iloc[p])
                p1_val = prices.iloc[p1_idx]
                
                if p1_val > v1_val and p1_val > v2_val:
                    patterns.append({
                        "type": "Double Bottom",
                        "points": [
                            {"type": "Valley", "index": v1_idx, "price": v1_val},
                            {"type": "Peak", "index": p1_idx, "price": p1_val},
                            {"type": "Valley", "index": v2_idx, "price": v2_val}
                        ],
                        "end_idx": v2_idx
                    })
    return patterns

def detect_head_and_shoulders(
    peaks: List[int], 
    valleys: List[int], 
    prices: pd.Series, 
    threshold_pct: float = 0.04
) -> List[Dict[str, Any]]:
    """
    Detect Head and Shoulders patterns.
    Pattern: Peak 1 (LS) -> Valley 1 -> Peak 2 (Head) -> Valley 2 -> Peak 3 (RS)
    Condition: Head > LS, Head > RS. LS and RS within threshold.
    """
    patterns = []
    if len(peaks) < 3:
        return patterns
        
    for i in range(len(peaks) - 2):
        p1_idx, p2_idx, p3_idx = peaks[i], peaks[i+1], peaks[i+2]
        p1_val, p2_val, p3_val = prices.iloc[p1_idx], prices.iloc[p2_idx], prices.iloc[p3_idx]
        
        if p2_val > p1_val and p2_val > p3_val:
            if _is_within_threshold(p1_val, p3_val, threshold_pct):
                v1_candidates = [v for v in valleys if p1_idx < v < p2_idx]
                v2_candidates = [v for v in valleys if p2_idx < v < p3_idx]
                
                if v1_candidates and v2_candidates:
                    v1_idx = min(v1_candidates, key=lambda v: prices.iloc[v])
                    v2_idx = min(v2_candidates, key=lambda v: prices.iloc[v])
                    v1_val, v2_val = prices.iloc[v1_idx], prices.iloc[v2_idx]
                    
                    patterns.append({
                        "type": "Head and Shoulders",
                        "points": [
                            {"type": "Peak", "index": p1_idx, "price": p1_val},
                            {"type": "Valley", "index": v1_idx, "price": v1_val},
                            {"type": "Peak", "index": p2_idx, "price": p2_val},
                            {"type": "Valley", "index": v2_idx, "price": v2_val},
                            {"type": "Peak", "index": p3_idx, "price": p3_val}
                        ],
                        "end_idx": p3_idx
                    })
    return patterns

def detect_inverse_head_and_shoulders(
    peaks: List[int], 
    valleys: List[int], 
    prices: pd.Series, 
    threshold_pct: float = 0.04
) -> List[Dict[str, Any]]:
    """
    Detect Inverse Head and Shoulders patterns.
    Pattern: Valley 1 (LS) -> Peak 1 -> Valley 2 (Head) -> Peak 2 -> Valley 3 (RS)
    Condition: Head < LS, Head < RS. LS and RS within threshold.
    """
    patterns = []
    if len(valleys) < 3:
        return patterns
        
    for i in range(len(valleys) - 2):
        v1_idx, v2_idx, v3_idx = valleys[i], valleys[i+1], valleys[i+2]
        v1_val, v2_val, v3_val = prices.iloc[v1_idx], prices.iloc[v2_idx], prices.iloc[v3_idx]
        
        if v2_val < v1_val and v2_val < v3_val:
            if _is_within_threshold(v1_val, v3_val, threshold_pct):
                p1_candidates = [p for p in peaks if v1_idx < p < v2_idx]
                p2_candidates = [p for p in peaks if v2_idx < p < v3_idx]
                
                if p1_candidates and p2_candidates:
                    p1_idx = max(p1_candidates, key=lambda p: prices.iloc[p])
                    p2_idx = max(p2_candidates, key=lambda p: prices.iloc[p])
                    p1_val, p2_val = prices.iloc[p1_idx], prices.iloc[p2_idx]
                    
                    patterns.append({
                        "type": "Inverse Head and Shoulders",
                        "points": [
                            {"type": "Valley", "index": v1_idx, "price": v1_val},
                            {"type": "Peak", "index": p1_idx, "price": p1_val},
                            {"type": "Valley", "index": v2_idx, "price": v2_val},
                            {"type": "Peak", "index": p2_idx, "price": p2_val},
                            {"type": "Valley", "index": v3_idx, "price": v3_val}
                        ],
                        "end_idx": v3_idx
                    })
    return patterns

def analyze_patterns(
    df: pd.DataFrame, 
    price_col: str = "Close",
    distance: int = 5,
    prominence: float = 0.02,
    threshold_pct: float = 0.03
) -> Dict[str, Any]:
    """
    Main entry point for chart pattern recognition.
    
    Args:
        df: DataFrame containing price history.
        price_col: Column to use for detection (default 'Close').
        
    Returns:
        Dictionary containing:
        - 'peaks': list of peak indices
        - 'valleys': list of valley indices
        - 'patterns': list of detected pattern dictionaries
    """
    if df.empty or len(df) < 20 or price_col not in df.columns:
        return {"peaks": [], "valleys": [], "patterns": []}
        
    prices = df[price_col]
    peaks, valleys = find_extrema(prices, distance=distance, prominence=prominence)
    
    patterns = []
    patterns.extend(detect_double_top(peaks, valleys, prices, threshold_pct))
    patterns.extend(detect_double_bottom(peaks, valleys, prices, threshold_pct))
    patterns.extend(detect_head_and_shoulders(peaks, valleys, prices, threshold_pct + 0.01))
    patterns.extend(detect_inverse_head_and_shoulders(peaks, valleys, prices, threshold_pct + 0.01))
    
    # Sort patterns by when they occurred (end index)
    patterns.sort(key=lambda x: x['end_idx'])
    
    # We only care about patterns that have completed recently 
    # (e.g. within the last 30 bars) to be relevant for the scanner
    recent_patterns = []
    max_idx = len(df) - 1
    for p in patterns:
        if max_idx - p['end_idx'] <= 30:
            recent_patterns.append(p)
            
    # Also convert local indices to string dates for UI if index is datetime
    # We will keep raw integer indices as well for easy Plotly mapping
    for p in recent_patterns:
        for pt in p["points"]:
            idx = pt["index"]
            if isinstance(df.index, pd.DatetimeIndex):
                pt["date"] = df.index[idx].strftime("%Y-%m-%d")
            else:
                pt["date"] = str(idx)
                
    peak_dates = [df.index[i].strftime("%Y-%m-%d") if isinstance(df.index, pd.DatetimeIndex) else str(i) for i in peaks]
    valley_dates = [df.index[i].strftime("%Y-%m-%d") if isinstance(df.index, pd.DatetimeIndex) else str(i) for i in valleys]
                
    return {
        "peaks": peak_dates,
        "valleys": valley_dates,
        "patterns": recent_patterns
    }
