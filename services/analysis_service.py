from __future__ import annotations

from datetime import date
from typing import Optional

import pandas as pd

from features.scoring import build_scorecard_from_history
from models.prediction_models import predict_weekly_movement
from models.types import StockScorecard, WeeklyPredictionResult
from services.llm_service import explain_weekly_outlook
from services.market_data_service import get_history_with_indicators
from rag.news_rag_service import get_symbol_news_summaries
from utils.logging import logger


def get_stock_history_with_indicators(
    symbol: str,
    start: date,
    end: date,
    interval: str = "1d",
) -> Optional[pd.DataFrame]:
    return get_history_with_indicators(symbol, start, end, interval=interval)


def build_stock_scorecard(df: pd.DataFrame) -> Optional[StockScorecard]:
    try:
        return build_scorecard_from_history(df)
    except Exception as exc:
        logger.exception(f"Failed to build scorecard: {exc}")
        return None


def analyze_stock_for_week(
    symbol: str,
    history_df: pd.DataFrame,
) -> Optional[WeeklyPredictionResult]:
    if history_df is None or history_df.empty:
        return None

    try:
        base_pred = predict_weekly_movement(history_df)
    except Exception as exc:
        logger.exception(f"Weekly prediction failed for {symbol}: {exc}")
        return None

    scorecard = build_stock_scorecard(history_df)

    try:
        news_summaries = get_symbol_news_summaries(symbol, top_k=5)
        explanation = explain_weekly_outlook(
            symbol=symbol,
            scorecard=scorecard,
            prediction=base_pred,
            news_summaries=news_summaries,
        )
    except Exception as exc:
        logger.exception(f"LLM explanation failed for {symbol}: {exc}")
        explanation = None

    base_pred.reasoning = explanation
    return base_pred
