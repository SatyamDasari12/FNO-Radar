from __future__ import annotations

from typing import Union

import numpy as np
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import MACD
from ta.volatility import AverageTrueRange, BollingerBands


def add_indicators_to_ohlc(df: pd.DataFrame) -> pd.DataFrame:
    """
    Enrich an OHLCV dataframe with standard technical indicators.

    Expects columns: Open, High, Low, Close, Volume
    Index should be datetime.
    """
    if df.empty:
        return df

    n = len(df)
    MIN_ROWS_ATR = 14
    MIN_ROWS_RSI = 14
    MIN_ROWS_MACD = 26
    MIN_ROWS_BB = 20

    def _ensure_series(x: Union[pd.Series, pd.DataFrame]) -> pd.Series:
        if isinstance(x, pd.DataFrame):
            return x.iloc[:, 0]
        return x

    o = _ensure_series(df["Open"])
    h = _ensure_series(df["High"])
    l = _ensure_series(df["Low"])
    c = _ensure_series(df["Close"])
    v_raw = df.get("Volume")
    v = _ensure_series(v_raw) if v_raw is not None else None

    # Moving averages
    df["SMA_20"] = c.rolling(window=20, min_periods=10).mean()
    df["SMA_50"] = c.rolling(window=50, min_periods=25).mean()
    df["SMA_200"] = c.rolling(window=200, min_periods=100).mean()

    # RSI
    if n >= MIN_ROWS_RSI:
        rsi = RSIIndicator(close=c, window=14)
        df["RSI_14"] = rsi.rsi()
    else:
        df["RSI_14"] = np.nan

    # MACD
    if n >= MIN_ROWS_MACD:
        macd = MACD(close=c, window_slow=26, window_fast=12, window_sign=9)
        df["MACD"] = macd.macd()
        df["MACD_SIGNAL"] = macd.macd_signal()
        df["MACD_HIST"] = macd.macd_diff()
    else:
        df["MACD"] = np.nan
        df["MACD_SIGNAL"] = np.nan
        df["MACD_HIST"] = np.nan

    # ATR
    if n >= MIN_ROWS_ATR:
        atr = AverageTrueRange(high=h, low=l, close=c, window=14)
        df["ATR_14"] = atr.average_true_range()
    else:
        df["ATR_14"] = np.nan

    # Bollinger Bands
    if n >= MIN_ROWS_BB:
        bb = BollingerBands(close=c, window=20, window_dev=2)
        df["BB_HIGH"] = bb.bollinger_hband()
        df["BB_LOW"] = bb.bollinger_lband()
        df["BB_WIDTH"] = (df["BB_HIGH"] - df["BB_LOW"]) / c
    else:
        df["BB_HIGH"] = np.nan
        df["BB_LOW"] = np.nan
        df["BB_WIDTH"] = np.nan

    # VWAP (daily approximation on end-of-day data)
    if v is not None:
        typical_price = (h + l + c) / 3.0
        cum_vp = (typical_price * v).cumsum()
        cum_v = v.cumsum().replace(0, np.nan)
        df["VWAP"] = cum_vp / cum_v

        vol_mean = v.rolling(window=20, min_periods=10).mean()
        df["VOLUME_SPIKE"] = (v > 1.5 * vol_mean).astype(int)

    return df

