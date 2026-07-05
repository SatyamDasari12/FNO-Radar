from __future__ import annotations

from typing import Optional, Tuple

import numpy as np
import pandas as pd

from models.types import WeeklyPredictionResult


def _build_ml_features_and_label(df: pd.DataFrame) -> Tuple[pd.DataFrame, np.ndarray, Optional[object]]:
    """
    Build feature matrix and 5-day forward return label from OHLC + indicators.
    Returns (X, y_class, last_index) where last_index is the index of the row to predict for.
    """
    req = ["Close", "RSI_14", "MACD_HIST", "SMA_20", "SMA_50", "SMA_200", "ATR_14"]
    if not all(c in df.columns for c in req):
        return pd.DataFrame(), np.array([]), None

    close = df["Close"].astype(float)
    fwd_5 = close.shift(-5)
    ret_5d = (fwd_5 - close) / close.replace(0, np.nan)
    valid = ret_5d.notna()
    if valid.sum() < 20:
        return pd.DataFrame(), np.array([]), None

    df = df.loc[valid].copy()
    ret_5d = ret_5d.loc[valid]
    thresh = 0.01
    y_class = np.where(ret_5d > thresh, 1, np.where(ret_5d < -thresh, -1, 0))

    sma20 = df["SMA_20"].replace(0, np.nan).ffill().bfill()
    sma50 = df["SMA_50"].replace(0, np.nan).ffill().bfill()
    sma200 = df["SMA_200"].replace(0, np.nan).ffill().bfill()
    atr = df["ATR_14"].replace(0, np.nan).ffill().bfill()
    X = pd.DataFrame({
        "rsi": df["RSI_14"].fillna(50),
        "macd_hist": df["MACD_HIST"].fillna(0),
        "close_sma20": (df["Close"] / sma20 - 1.0).fillna(0),
        "close_sma50": (df["Close"] / sma50 - 1.0).fillna(0),
        "close_sma200": (df["Close"] / sma200 - 1.0).fillna(0),
        "atr_pct": (atr / df["Close"]).fillna(0),
    }, index=df.index)
    X = X.fillna(0)
    last_idx = X.index[-1]
    return X, y_class, last_idx


def _try_ml_ensemble(df: pd.DataFrame) -> Optional[Tuple[str, float]]:
    """
    Train Random Forest and Gradient Boosting on 5-day forward return; predict trend and probability.
    Returns (trend, probability) or None if ML unavailable / insufficient data.
    """
    try:
        from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
    except Exception:
        return None

    X, y_class, last_idx = _build_ml_features_and_label(df)
    if X.empty or len(X) < 30 or last_idx is None:
        return None

    try:
        rf = RandomForestClassifier(n_estimators=50, max_depth=5, random_state=42)
        gb = GradientBoostingClassifier(n_estimators=50, max_depth=3, random_state=42)
        rf.fit(X, y_class)
        gb.fit(X, y_class)

        last_row = X.loc[[last_idx]]
        p_rf = rf.predict_proba(last_row)[0]
        p_gb = gb.predict_proba(last_row)[0]
        classes = list(rf.classes_)
        prob_bull = (p_rf[classes.index(1)] + p_gb[classes.index(1)]) / 2.0 if 1 in classes else 0.33
        prob_bear = (p_rf[classes.index(-1)] + p_gb[classes.index(-1)]) / 2.0 if -1 in classes else 0.33
        prob_side = max(0.0, 1.0 - prob_bull - prob_bear)
        if prob_bull >= prob_bear and prob_bull >= prob_side:
            return "Bullish", float(np.clip(prob_bull, 0.2, 0.9))
        if prob_bear >= prob_bull and prob_bear >= prob_side:
            return "Bearish", float(np.clip(prob_bear, 0.2, 0.9))
        return "Sideways", float(np.clip(prob_side, 0.2, 0.9))
    except Exception:
        return None


def _volatility_based_range(df: pd.DataFrame) -> tuple[float, float]:
    close = df["Close"]
    last = float(close.iloc[-1])
    returns = close.pct_change().dropna()
    if returns.empty:
        return last * 0.95, last * 1.05

    avg_daily_vol = returns.std()
    weekly_vol = avg_daily_vol * np.sqrt(5)
    low = last * (1 - weekly_vol)
    high = last * (1 + weekly_vol)
    return low, high


def _try_prophet_forecast(df: pd.DataFrame) -> Optional[tuple[float, float]]:
    try:
        from prophet import Prophet  # type: ignore
    except Exception:
        return None

    hist = df["Close"].reset_index()
    hist.columns = ["ds", "y"]
    if len(hist) < 60:
        return None

    try:
        m = Prophet(daily_seasonality=True)
        m.fit(hist)
        future = m.make_future_dataframe(periods=5, freq="D")
        forecast = m.predict(future).tail(5)
        low = float(forecast["yhat_lower"].min())
        high = float(forecast["yhat_upper"].max())
        return low, high
    except Exception:
        return None


def predict_weekly_movement(df: pd.DataFrame) -> WeeklyPredictionResult:
    """
    Ensemble weekly outlook: RF + GB trend/probability, Prophet/volatility for range.

    Uses Random Forest and Gradient Boosting (when sklearn and enough data) for trend
    and probability; Prophet + volatility-based range for expected low/high.
    """
    last_close = float(df["Close"].iloc[-1])

    prophet_range = _try_prophet_forecast(df)
    vol_low, vol_high = _volatility_based_range(df)

    if prophet_range is not None:
        low, high = prophet_range
        low = 0.5 * low + 0.5 * vol_low
        high = 0.5 * high + 0.5 * vol_high
    else:
        low, high = vol_low, vol_high

    ml_result = _try_ml_ensemble(df)
    if ml_result is not None:
        trend, probability = ml_result
    else:
        mid = (low + high) / 2
        if mid > last_close * 1.01:
            trend = "Bullish"
            probability = 0.6
        elif mid < last_close * 0.99:
            trend = "Bearish"
            probability = 0.6
        else:
            trend = "Sideways"
            probability = 0.5

    return WeeklyPredictionResult(
        trend=trend,
        probability=probability,
        expected_low=low,
        expected_high=high,
    )

