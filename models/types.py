from dataclasses import dataclass
from typing import Optional

import pandas as pd


@dataclass
class WeeklyPredictionResult:
    trend: str
    probability: float
    expected_low: float
    expected_high: float
    reasoning: Optional[str] = None


@dataclass
class StockScorecard:
    trend_score: int
    momentum_score: int
    volume_score: int
    volatility_score: int

    @property
    def total_score(self) -> int:
        return (
            self.trend_score
            + self.momentum_score
            + self.volume_score
            + self.volatility_score
        )

    @property
    def interpretation(self) -> str:
        score = self.total_score
        if score >= 7:
            return "Strong opportunity zone (trend + momentum aligned)."
        if score >= 5:
            return "Moderate opportunity. Confirm with price action."
        return "Weak / noisy setup. Better to avoid for now."


@dataclass
class Quote:
    symbol: str
    last_price: float
    history_df: pd.DataFrame


@dataclass
class PortfolioRecommendation:
    action: str
    reason: str
    target_price: Optional[float] = None
    stop_loss: Optional[float] = None
    holding_period: Optional[str] = None
    risk_reward: Optional[float] = None
    atr_percent: Optional[float] = None

