from __future__ import annotations

from typing import Optional

from models.types import PortfolioRecommendation, StockScorecard


def build_portfolio_recommendation(
    symbol: str,
    buy_price: float,
    quantity: int,
    latest_price: float,
    scorecard: Optional[StockScorecard],
    atr: Optional[float] = None,
) -> PortfolioRecommendation:
    pnl_pct = (latest_price - buy_price) / buy_price * 100 if buy_price > 0 else 0.0
    total_score = scorecard.total_score if scorecard else 0

    # Basic rule set based on P&L and technical backing
    if pnl_pct > 20 and total_score < 7:
        action = "SELL"
        reason = (
            f"Position is up about {pnl_pct:.1f}% while the technical score "
            "is only moderate, so it may be prudent to book profits."
        )
        target = latest_price
        stop = latest_price * 0.95
        horizon = "Exit gradually over the next few sessions."
    elif pnl_pct < -12 and total_score < 5:
        action = "REDUCE / EXIT"
        reason = (
            f"Drawdown of roughly {pnl_pct:.1f}% with a weak technical score "
            "suggests capital protection should take priority."
        )
        target = latest_price * 0.9
        stop = latest_price * 0.92
        horizon = "Review within the next 1–3 sessions."
    elif total_score >= 7:
        action = "HOLD"
        reason = (
            "Trend and momentum are supportive (high technical score). "
            "If your risk profile allows, you can ride the trend with a "
            "defined stop loss."
        )
        target = latest_price * 1.1
        stop = latest_price * 0.95
        horizon = "1–3 weeks, subject to trend staying intact."
    elif 5 <= total_score < 7:
        action = "HOLD / TIGHTEN SL"
        reason = (
            "Structure is mixed but not weak. It can be held with a "
            "relatively tight stop until price resolves."
        )
        target = latest_price * 1.05
        stop = latest_price * 0.96
        horizon = "Up to 1–2 weeks with frequent review."
    else:
        action = "AVOID FRESH ADDITIONS"
        reason = (
            "Technical context is not very favorable. Focus on risk "
            "management rather than adding more to this position."
        )
        target = latest_price * 1.03
        stop = latest_price * 0.95
        horizon = "Short-term only; reconsider if technicals improve."

    # Simple risk engine: risk/reward and ATR‑based volatility
    risk_reward = None
    if latest_price > 0 and stop is not None and target is not None:
        risk = max(latest_price - stop, 0.0)
        reward = max(target - latest_price, 0.0)
        if risk > 0:
            risk_reward = reward / risk if reward > 0 else 0.0

    atr_percent = None
    if atr is not None and latest_price > 0:
        atr_percent = atr / latest_price * 100.0

    return PortfolioRecommendation(
        action=action,
        reason=reason,
        target_price=target,
        stop_loss=stop,
        holding_period=horizon,
        risk_reward=risk_reward,
        atr_percent=atr_percent,
    )

