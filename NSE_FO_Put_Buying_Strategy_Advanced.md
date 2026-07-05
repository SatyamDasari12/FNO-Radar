# NSE F&O Put Buying Strategy (Advanced Version with Formulas)

Monthly Expiry | 3–7 Day Hold | Puts Only

------------------------------------------------------------------------

# 🎯 Strategy Objective

Select high-probability PUT option trades across 200+ NSE F&O stocks.
Focus on short-term bearish acceleration with controlled theta and IV
risk.

Holding Period: 3–7 trading days.

------------------------------------------------------------------------

# 1️⃣ Hard Filters (Pre-Qualification Layer)

A stock must satisfy ALL conditions before scoring:

## Liquidity Conditions

-   Option Volume ≥ 500 lots
-   Bid-Ask Spread ≤ 1.5%
-   Stock Volume ≥ 1.2 × 20-day Avg Volume

## Structural Conditions

-   Close < 20 DMA
-   No earnings within next 7 days
-   IV Rank ≤ 40 (we want cheap implied volatility to avoid overpaying/volatility crush)

## Stability Conditions

-   ATR(14) / Price ≥ 1.5%
-   3-day price change ≥ -8% (avoid chasing a stock that has already crashed)

Filtered Universe Target: ~40–60 stocks.

------------------------------------------------------------------------

# 2️⃣ Indicator Normalization (0–100 Scale)

Each factor is normalized to 0–100.

## (A) Negative Momentum Score (25%)

Momentum = (1 - Close / Close_5daysAgo) × 100

Normalized: Momentum_Score = Min(100, Max(0, Momentum × 5))

------------------------------------------------------------------------

## (B) Breakdown Strength (15%)

Breakdown = (LowestLow_10 - Close) / LowestLow_10

If Close < LowestLow_10: Breakdown_Score = 100 Else: Breakdown_Score = 0

------------------------------------------------------------------------

## (C) Volume Expansion (15%)

Volume_Ratio = CurrentVolume / AvgVolume_20

Volume_Score = Min(100, Volume_Ratio × 50)

------------------------------------------------------------------------

## (D) OI Short Buildup (15%)

Short buildup condition (proxy due to API limitations): - Price ↓ - Volume ↑

OI_Score = Min(100, (Volume_Score - 50) × 2)

If price not decreasing, OI_Score = 0

------------------------------------------------------------------------

## (E) RSI Zone Score (10%)

Ideal Bearish RSI Zone = 35–55 (or recently rolled over from overbought >70)

RSI_Score: If RSI between 35–55 (or recently declined from >70) → 100 If RSI between 28–35 → 60 If RSI < 28 (oversold) → 20 Else → 40

------------------------------------------------------------------------

## (F) IV Sweet Spot Score (10%)

Ideal IV Rank = ≤ 40 (Cheap Puts)

IV_Score: If IV Rank ≤ 40 → 100 If 40–55 → 60 Else → 20

------------------------------------------------------------------------

## (G) Nifty Alignment (10%)

If Nifty Close < 20 DMA: Nifty_Score = 100 Else: Nifty_Score = 40

------------------------------------------------------------------------

# 3️⃣ Final Composite Score

Final_Score =

(0.25 × Momentum_Score) + (0.15 × Breakdown_Score) + (0.15 ×
Volume_Score) + (0.15 × OI_Score) + (0.10 × RSI_Score) + (0.10 ×
IV_Score) + (0.10 × Nifty_Score)

Maximum = 100

Rank stocks descending by Final_Score. Select Top 5 candidates only.

------------------------------------------------------------------------

# 4️⃣ Option Contract Selection Formula

For each selected stock:

Choose strike where: -0.55 ≤ Delta ≤ -0.40 (Negative Delta for Puts)

Theta Constraint: Daily Theta Loss ≤ 0.5% of Option Premium

Premium Efficiency Check: Reward_Risk_Ratio ≥ 1.8

Where:

Reward = TargetPriceMove × |Delta|
Risk = OptionPremium × 0.30 (Assuming 30% stop loss)

------------------------------------------------------------------------

# 5️⃣ Exit Rules

Exit if ANY condition met:

1.  Stock closes above 5 EMA (bearish trend reversed)
2.  Option premium drops 30%
3.  Momentum_Score drops below 50
4.  5 trading days completed

------------------------------------------------------------------------

# 6️⃣ Advanced Enhancements (Optional)

## Relative Weakness Boost

RW = (Stock_Return_10D - Nifty_Return_10D)

If RW < 0: Add 5 bonus points (stock is weaker than Nifty)

------------------------------------------------------------------------

# 🧠 System Architecture Flow

Universe (200+ F&O stocks) ↓ Hard Filters ↓ Indicator Normalization ↓
Composite Score Calculation ↓ Rank & Select Top 5 ↓ Contract Filtering
(Delta + Theta constraints) ↓ Execution

------------------------------------------------------------------------

# Core Philosophy

You are not selecting "bearish stocks." You are selecting short-term
acceleration opportunities optimized for put option payoff.

Speed > Confirmation > Narrative
