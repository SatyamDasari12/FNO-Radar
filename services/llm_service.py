from __future__ import annotations

from typing import Any, Optional, Sequence, List, Dict

from groq import Groq

from models.types import PortfolioRecommendation, StockScorecard, WeeklyPredictionResult
from utils.config import get_app_config
from utils.logging import logger


# ---------------------------------------------------------------------------
# Intent classification
# ---------------------------------------------------------------------------

INTENT_SYSTEM_PROMPT = (
    "You are an intent classifier for an Indian stock market assistant.\n"
    "Classify the user query into exactly one intent label from this list:\n"
    "  weekly_prediction, intraday_scan, options_scan, portfolio_advice, general\n"
    "Return ONLY the label, nothing else."
)


def classify_intent(query: str) -> str:
    """Use LLM to classify user query intent. Falls back to 'general' on failure."""
    cfg = get_app_config().groq
    if not cfg.api_key:
        return "general"
    try:
        client = Groq(api_key=cfg.api_key)
        resp = client.chat.completions.create(
            model=cfg.model,
            messages=[
                {"role": "system", "content": INTENT_SYSTEM_PROMPT},
                {"role": "user", "content": query},
            ],
            temperature=0.0,
            max_tokens=20,
        )
        label = (resp.choices[0].message.content or "general").strip().lower()
        valid = {"weekly_prediction", "intraday_scan", "options_scan", "portfolio_advice", "general"}
        return label if label in valid else "general"
    except Exception as exc:
        logger.exception(f"Intent classification failed: {exc}")
        return "general"


# ---------------------------------------------------------------------------
# Weekly outlook explanation
# ---------------------------------------------------------------------------

def _build_weekly_messages(
    symbol: str,
    scorecard: Optional[StockScorecard],
    prediction: WeeklyPredictionResult,
    news_summaries: Optional[Sequence[str]] = None,
) -> List[Dict[str, Any]]:
    news_block = ""
    if news_summaries:
        joined = "\n".join(f"- {n}" for n in news_summaries)
        news_block = f"\nRelevant news/headlines:\n{joined}\n"

    tech_block = ""
    if scorecard is not None:
        tech_block = (
            f"Trend score: {scorecard.trend_score}/3\n"
            f"Momentum score: {scorecard.momentum_score}/3\n"
            f"Volume score: {scorecard.volume_score}/2\n"
            f"Volatility score: {scorecard.volatility_score}/2\n"
            f"Total technical score (0-10): {scorecard.total_score}\n"
            f"Interpretation: {scorecard.interpretation}\n"
        )

    user_content = (
        "You are an expert equity portfolio analyst offering simulated actionable insights for Indian markets.\n"
        f"Stock: {symbol} (NSE/BSE)\n"
        f"One-week statistical outlook: trend={prediction.trend}, "
        f"probability={prediction.probability:.0%}, "
        f"expected range={prediction.expected_low:.2f}–{prediction.expected_high:.2f}.\n"
        f"{tech_block}"
        f"{news_block}"
        "Provide a concise, simulated 5-point summary covering:\n"
        "1) Verdict: Buy / Sell / Hold decision.\n"
        "2) Holding Period: Expected timeframe.\n"
        "3) Quantity Allocation: Suggested percentage of portfolio or number of shares (assuming an arbitrary ₹1,00,000 risk capital).\n"
        "4) Risk Level & Bounds: (Low/Medium/High) + Stop-loss guidance.\n"
        "5) Logical Reasoning: Short primary reason validating your verdict."
    )

    return [
        {
            "role": "system",
            "content": (
                "You are an experienced Indian stock market advisor offering comprehensive scenario-based insights."
                "You format output as direct point summaries incorporating expected explicit simulated advice for users seeking direct structure."
            ),
        },
        {"role": "user", "content": user_content},
    ]


def explain_weekly_outlook(
    symbol: str,
    scorecard: Optional[StockScorecard],
    prediction: WeeklyPredictionResult,
    news_summaries: Optional[Sequence[str]] = None,
) -> str:
    cfg = get_app_config().groq
    if not cfg.api_key:
        logger.info("GROQ_API_KEY not set; falling back to rule-based explanation.")
        return _fallback_weekly_explanation(scorecard, prediction)

    try:
        client = Groq(api_key=cfg.api_key)
        messages = _build_weekly_messages(symbol, scorecard, prediction, news_summaries)
        resp = client.chat.completions.create(
            model=cfg.model,
            messages=messages,
            temperature=cfg.temperature,
            max_tokens=320,
        )
        return resp.choices[0].message.content or _fallback_weekly_explanation(
            scorecard, prediction
        )
    except Exception as exc:
        logger.exception(f"Groq explanation failed: {exc}")
        return _fallback_weekly_explanation(scorecard, prediction)


def _fallback_weekly_explanation(
    scorecard: Optional[StockScorecard],
    prediction: WeeklyPredictionResult,
) -> str:
    base = (
        f"Model expects a {prediction.trend.lower()} bias for the coming week "
        f"with an indicative range between {prediction.expected_low:.2f} and "
        f"{prediction.expected_high:.2f}."
    )
    if not scorecard:
        return (
            base
            + " Technical scorecard is unavailable, so treat this as a rough, "
            "volatility-based projection."
        )

    if scorecard.total_score >= 7:
        extra = (
            " Technical structure is supportive with healthy trend and momentum "
            "scores, but price can still whipsaw near resistance levels."
        )
    elif scorecard.total_score >= 5:
        extra = (
            " Technicals are mixed; follow-through will depend on how price reacts "
            "to key moving averages and recent swing highs."
        )
    else:
        extra = (
            " Technical backdrop is weak or choppy, so breakouts may fail and "
            "risk management is important."
        )
    return base + extra


# ---------------------------------------------------------------------------
# Portfolio advice (LLM-enhanced)
# ---------------------------------------------------------------------------

def explain_portfolio_advice(
    symbol: str,
    buy_price: float,
    quantity: int,
    latest_price: float,
    recommendation_action: str,
    recommendation_reason: str,
    scorecard: Optional[StockScorecard],
    news_summaries: Optional[Sequence[str]] = None,
) -> Optional[str]:
    """Generate LLM-enhanced portfolio advice explanation."""
    cfg = get_app_config().groq
    if not cfg.api_key:
        return None

    pnl_pct = (latest_price - buy_price) / buy_price * 100 if buy_price > 0 else 0.0
    total_value = latest_price * quantity
    invested_value = buy_price * quantity

    tech_block = ""
    if scorecard is not None:
        tech_block = (
            f"Technical score: {scorecard.total_score}/10 ({scorecard.interpretation})\n"
        )

    news_block = ""
    if news_summaries:
        joined = "\n".join(f"- {n}" for n in news_summaries[:3])
        news_block = f"Recent news:\n{joined}\n"

    user_content = (
        "You are an Indian equity portfolio advisor.\n"
        f"Stock: {symbol}\n"
        f"Buy price: ₹{buy_price:.2f} | Current price: ₹{latest_price:.2f}\n"
        f"Quantity: {quantity} | P&L: {pnl_pct:+.1f}% | "
        f"Invested: ₹{invested_value:,.0f} | Current value: ₹{total_value:,.0f}\n"
        f"Rule-based recommendation: {recommendation_action}\n"
        f"Reason: {recommendation_reason}\n"
        f"{tech_block}"
        f"{news_block}"
        "Provide a structured, simulated 4-point response:\n"
        "1) Portfolio Verdict: Confirm whether the rule-based approach fits technicals.\n"
        "2) P&L Context: Brief situation analysis.\n"
        "3) Allocation/Sizing: General guidance on accumulation or offloading proportion depending on rule strategy.\n"
        "4) Key Risk: Highlight one primary risk to watch out for."
    )

    try:
        client = Groq(api_key=cfg.api_key)
        resp = client.chat.completions.create(
            model=cfg.model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful Indian stock market advisor. "
                        "You provide logical, direct point summaries and assume position planning structuring."
                    ),
                },
                {"role": "user", "content": user_content},
            ],
            temperature=cfg.temperature,
            max_tokens=280,
        )
        return resp.choices[0].message.content
    except Exception as exc:
        logger.exception(f"Portfolio LLM explanation failed: {exc}")
        return None

# ---------------------------------------------------------------------------
# Options Scanner explanation
# ---------------------------------------------------------------------------

def explain_option_contract(row_data: dict[str, Any]) -> str:
    """Generate LLM-enhanced explanation for a scanned option contract."""
    cfg = get_app_config().groq
    if not cfg.api_key:
        return "LLM API Key not configured. Please add GROQ_API_KEY in settings."

    contract = row_data.get("Contract", "")
    spot = row_data.get("Underlying Spot (₹)", 0)
    strike = row_data.get("Strike (₹)", 0)
    cur_prem = row_data.get("Current Premium (₹)", 0)
    exp_prem = row_data.get("Expected Premium @ Target (₹)", 0)
    target = row_data.get("Target Spot Price (₹)", 0)
    profit = row_data.get("Est Profit / Lot (₹)", 0)
    ret_pct = row_data.get("Return%", 0)
    score = row_data.get("Final Score (0-100)", 0)
    news = row_data.get("Latest News", "")

    user_content = (
        "You are a friendly stock market coach explaining an options trade to a complete beginner.\n"
        "Use only plain, everyday English. Do NOT use technical words like 'theta', 'delta', 'greeks',\n"
        "'IV', 'ATM', 'OTM', 'volatility crush', 'time decay', etc. Replace them with simple phrases:\n"
        "  - instead of 'theta decay'  → say 'the option loses value every day it sits'\n"
        "  - instead of 'IV' → say 'how jumpy the stock has been'\n"
        "  - instead of 'ATM/OTM' → describe the price gap in rupees\n\n"
        f"Stock/Contract  : {contract}\n"
        f"Stock price now : ₹{spot}   |   Option strike (our target level) : ₹{strike}\n"
        f"Cost to enter   : ₹{cur_prem} per share (one lot)\n"
        f"Expected value at target : ₹{exp_prem} per share\n"
        f"Target stock price : ₹{target}  |  Estimated profit per lot if we hit target : ₹{profit} ({ret_pct}% return)\n"
        f"System rating for this trade : {score}/100\n"
        f"Latest news about this stock : {news}\n\n"
        "Write exactly 5 short bullet points (1–2 sentences each) in this order:\n"
        "1) 🎯 **What is this trade?** — What are we doing and why does the stock look interesting right now?\n"
        "2) 💰 **What is the potential gain?** — How much could we make, and what does it cost to try?\n"
        "3) 📈 **What needs to happen?** — How much does the stock price need to rise (or fall) for this to work?\n"
        "4) ⚠️ **What could go wrong?** — Explain the main risks in simple words (e.g. the stock doesn't move, time runs out, etc.)\n"
        "5) 📰 **Does the news help or hurt?** — Based on the recent news, is this trade idea supported or not?\n"
        "Total length: 200 words maximum. Friendly, conversational tone.\n"
    )

    try:
        from groq import Groq
        client = Groq(api_key=cfg.api_key)
        resp = client.chat.completions.create(
            model=cfg.model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a friendly stock market coach. Explain options trades in simple, plain English that anyone can understand. Avoid all technical jargon.",
                },
                {"role": "user", "content": user_content},
            ],
            temperature=0.5,
            max_tokens=400,
        )
        return resp.choices[0].message.content or "Failed to generate AI analysis."
    except Exception as exc:
        logger.exception(f"Option LLM explanation failed: {exc}")
        return "Failed to generate AI analysis. Please try again."

