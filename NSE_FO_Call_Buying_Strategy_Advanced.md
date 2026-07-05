# NSE F&O Call Buying Strategy (Advanced Version with Formulas)

Monthly Expiry \| 3--7 Day Hold \| Calls Only

------------------------------------------------------------------------

# 🎯 Strategy Objective

Select high-probability CALL option trades across 200+ NSE F&O stocks.
Focus on short-term bullish acceleration with controlled theta and IV
risk.

Holding Period: 3--7 trading days.

------------------------------------------------------------------------

# 1️⃣ Hard Filters (Pre-Qualification Layer)

A stock must satisfy ALL conditions before scoring:

## Liquidity Conditions

-   Option Volume ≥ 500 lots
-   Bid-Ask Spread ≤ 1.5%
-   Stock Volume ≥ 1.2 × 20-day Avg Volume

## Structural Conditions

-   Close \> 20 DMA
-   No earnings within next 7 days
-   IV Rank ∈ \[25, 65\]

## Stability Conditions

-   ATR(14) / Price ≥ 1.5%
-   3-day price gain ≤ 8%

Filtered Universe Target: \~40--60 stocks.

------------------------------------------------------------------------

# 2️⃣ Indicator Normalization (0--100 Scale)

Each factor is normalized to 0--100.

## (A) Momentum Score (25%)

Momentum = ((Close / Close_5daysAgo) - 1) × 100

Normalized: Momentum_Score = Min(100, Max(0, Momentum × 5))

------------------------------------------------------------------------

## (B) Breakout Strength (15%)

Breakout = (Close - HighestHigh_10) / HighestHigh_10

If Close \> HighestHigh_10: Breakout_Score = 100 Else: Breakout_Score =
0

------------------------------------------------------------------------

## (C) Volume Expansion (15%)

Volume_Ratio = CurrentVolume / AvgVolume_20

Volume_Score = Min(100, Volume_Ratio × 50)

------------------------------------------------------------------------

## (D) OI Long Buildup (15%)

Long buildup condition: - Price ↑ - OI ↑

OI_Change% = ((OI_today - OI_yesterday) / OI_yesterday) × 100

OI_Score = Min(100, OI_Change% × 10)

If price not increasing, OI_Score = 0

------------------------------------------------------------------------

## (E) RSI Zone Score (10%)

Ideal RSI Zone = 45--65

RSI_Score: If RSI between 45--65 → 100 If RSI between 65--72 → 60 If RSI
\> 72 → 20 Else → 40

------------------------------------------------------------------------

## (F) IV Sweet Spot Score (10%)

Ideal IV Rank = 30--60

IV_Score: If IV Rank between 30--60 → 100 If 20--30 or 60--70 → 60 Else
→ 20

------------------------------------------------------------------------

## (G) Nifty Alignment (10%)

If Nifty Close \> 20 DMA: Nifty_Score = 100 Else: Nifty_Score = 40

------------------------------------------------------------------------

# 3️⃣ Final Composite Score

Final_Score =

(0.25 × Momentum_Score) + (0.15 × Breakout_Score) + (0.15 ×
Volume_Score) + (0.15 × OI_Score) + (0.10 × RSI_Score) + (0.10 ×
IV_Score) + (0.10 × Nifty_Score)

Maximum = 100

Rank stocks descending by Final_Score. Select Top 5 candidates only.

------------------------------------------------------------------------

# 4️⃣ Option Contract Selection Formula

For each selected stock:

Choose strike where: 0.40 ≤ Delta ≤ 0.55

Theta Constraint: Daily Theta Loss ≤ 0.5% of Option Premium

Premium Efficiency Check: Reward_Risk_Ratio ≥ 1.8

Where:

Reward = TargetPriceMove × Delta Risk = OptionPremium × 0.30

------------------------------------------------------------------------

# 5️⃣ Exit Rules

Exit if ANY condition met:

1.  Stock closes below 5 EMA
2.  Option premium drops 30%
3.  Momentum_Score drops below 50
4.  5 trading days completed

------------------------------------------------------------------------

# 6️⃣ Advanced Enhancements (Optional)

## Relative Strength Boost

RS = (Stock_Return_10D - Nifty_Return_10D)

If RS \> 0: Add 5 bonus points

## Sector Momentum Boost

If Sector Index \> 20 DMA: Add 5 bonus points

------------------------------------------------------------------------

# 🧠 System Architecture Flow

Universe (200+ F&O stocks) ↓ Hard Filters ↓ Indicator Normalization ↓
Composite Score Calculation ↓ Rank & Select Top 5 ↓ Contract Filtering
(Delta + Theta constraints) ↓ Execution

------------------------------------------------------------------------

# Core Philosophy

You are not selecting "bullish stocks." You are selecting short-term
acceleration opportunities optimized for call option payoff.

Speed \> Confirmation \> Narrative
