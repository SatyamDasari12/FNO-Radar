from __future__ import annotations

from typing import Optional

import pandas as pd

from models.types import StockScorecard


def build_scorecard_from_history(df: pd.DataFrame) -> Optional[StockScorecard]:
    if df is None or df.empty:
        return None

    latest = df.iloc[-1]

    # --- Trend score (0–3) ---
    trend_score = 0
    close = latest.get("Close", pd.NA) if hasattr(latest, "get") else df["Close"].iloc[-1]
    ma20 = df["SMA_20"].iloc[-1] if "SMA_20" in df.columns else pd.NA
    ma50 = df["SMA_50"].iloc[-1] if "SMA_50" in df.columns else pd.NA
    ma200 = df["SMA_200"].iloc[-1] if "SMA_200" in df.columns else pd.NA

    close_val = df["Close"].iloc[-1] if "Close" in df.columns else pd.NA

    if pd.notna(close_val) and pd.notna(ma20) and float(close_val) > float(ma20):
        trend_score += 1
    if pd.notna(ma20) and pd.notna(ma50) and float(ma20) > float(ma50):
        trend_score += 1
    if pd.notna(ma50) and pd.notna(ma200) and float(ma50) > float(ma200):
        trend_score += 1

    # --- Momentum score (0–3) ---
    momentum_score = 0
    rsi = df["RSI_14"].iloc[-1] if "RSI_14" in df.columns else pd.NA
    macd = df["MACD"].iloc[-1] if "MACD" in df.columns else pd.NA
    macd_hist = df["MACD_HIST"].iloc[-1] if "MACD_HIST" in df.columns else pd.NA

    if pd.notna(rsi) and 55 <= float(rsi) <= 70:
        momentum_score += 1
    if pd.notna(macd) and float(macd) > 0:
        momentum_score += 1
    if pd.notna(macd_hist) and float(macd_hist) > 0:
        momentum_score += 1

    # --- Volume score (0–2) ---
    volume_score = 0
    vol_spike = df["VOLUME_SPIKE"].iloc[-1] if "VOLUME_SPIKE" in df.columns else 0
    if pd.notna(vol_spike) and int(vol_spike):
        volume_score += 1

    if "Volume" in df.columns:
        v = df["Volume"].astype(float)
        vol_mean = v.rolling(20, min_periods=10).mean()
        vol_std = v.rolling(20, min_periods=10).std()
        last_mean = vol_mean.iloc[-1]
        last_std = vol_std.iloc[-1]
        last_vol = float(v.iloc[-1])
        if pd.notna(last_mean) and pd.notna(last_std) and last_std > 0:
            vol_z = (last_vol - float(last_mean)) / float(last_std)
            if abs(vol_z) > 1.0:
                volume_score += 1

    # --- Volatility score (0–2) ---
    volatility_score = 0
    if "BB_WIDTH" in df.columns:
        width = df["BB_WIDTH"]
        current_w = width.iloc[-1]
        base_w = width.rolling(50, min_periods=20).median().iloc[-1]
        if pd.notna(current_w) and pd.notna(base_w) and current_w > base_w * 1.2:
            volatility_score += 1
    if "ATR_14" in df.columns:
        atr = df["ATR_14"]
        close_series = df["Close"].replace(0, float("nan"))
        atr_rel = atr / close_series
        current_a = atr_rel.iloc[-1]
        base_a = atr_rel.rolling(50, min_periods=20).median().iloc[-1]
        if pd.notna(current_a) and pd.notna(base_a) and current_a > base_a * 1.1:
            volatility_score += 1

    return StockScorecard(
        trend_score=int(trend_score),
        momentum_score=int(momentum_score),
        volume_score=int(volume_score),
        volatility_score=int(volatility_score),
    )
