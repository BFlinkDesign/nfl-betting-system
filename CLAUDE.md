# CLAUDE.md - Project Guidelines & Honest Assessment

## Self-Reflection (May 2026 Session)

### What I Did Wrong

1. **Speculated without data**: Said "books probably know this" about RB dual-threat pricing without any evidence.

2. **Accepted theoretical values uncritically**: Used correlation values from "research" (0.40 for RB dual-threat) that turned out to be completely wrong (-0.13 empirically).

3. **Previous sessions inflated metrics**: The README claims 428% ROI and 67% win rate. Transparent backtest shows **63.1%** - the previous numbers had data leakage.

4. **Confused descriptive stats with predictions**: Reported "77% rushing hit rate" which is just how often players exceed a line historically, NOT a predictive model output.

### Rules for This Project

1. **NO GUESSING**: Only state what the data shows. If you don't have data, say "I don't know."

2. **VALIDATE EVERYTHING**: Check against empirical data. 4 seasons of nflverse available.

3. **WALK-FORWARD ONLY**: Train on past, test on future. No exceptions.

4. **CITE YOUR SOURCES**: Include sample size (n=), confidence intervals, data source.

5. **ADMIT UNCERTAINTY**: Don't hide limitations.

6. **NO DATA LEAKAGE**: Never use same-game data to predict same-game outcomes.

---

## Project Overview

NFL betting system for **recreational bettors** focused on:
- High accuracy / hit rates over ROI grinding
- Popular bet types (props, SGPs, parlays)
- Fun factor alongside +EV

### ACTUAL Performance (Walk-Forward, No Leakage)

Tested: May 2026 | Data: nflverse 2021-2024 | Method: Train on prior seasons, test on future

| Test Year | Accuracy | 95% CI | N Games |
|-----------|----------|--------|---------|
| 2023 | 61.2% | 55.0% - 67.4% | 237 |
| 2024 | 65.0% | 58.9% - 71.1% | 237 |
| **Overall** | **63.1%** | **58.8% - 67.4%** | **474** |

**Baseline (always pick home): 55.9%**
**Model lift: +7.2 percentage points**

### What These Numbers Mean

- The model is better than random (55.9% baseline)
- It is NOT 67% or 428% ROI as README claims
- 63% accuracy with -110 odds = roughly break-even to small profit
- This is realistic for NFL game prediction

### Prop Hit Rates (DESCRIPTIVE, Not Predictive)

These are historical rates, NOT model predictions:

| Prop Type | Line | Historical Hit Rate | N |
|-----------|------|---------------------|---|
| Rushing yards | >55.5 | 18.9% +/- 0.8% | 8,627 |
| Rushing yards | >65.5 | 14.0% +/- 0.7% | 8,627 |
| Receiving yards | >45.5 | 26.8% +/- 0.7% | 15,907 |
| Receiving yards | >55.5 | 19.8% +/- 0.6% | 15,907 |

**Important**: These are how often players exceed lines historically. They are NOT predictions. Saying "77% hit rate" was misleading.

---

## Empirically Validated Correlations

From analysis of 198,513 plays (2021-2024 nflverse data):

| Correlation | Theoretical | **Empirical** | N | Status |
|-------------|-------------|---------------|---|--------|
| QB + WR1 yards | 0.72 | **0.68** | 2,278 | ✅ Validated |
| WR receptions + yards | 0.75 | **0.80** | 16,327 | ✅ Validated |
| WR1 + WR2 yards | 0.15 | **0.49** | 2,278 | ⚠️ Theory wrong |
| RB rush + rec (same player) | 0.40 | **-0.13** | 4,581 | ❌ Theory wrong |
| Team total yards + TDs | 0.55 | **0.61** | 2,278 | ✅ Validated |

### Key Finding: RB Dual-Threat is NEGATIVE Correlation

The popular bet of stacking RB rushing + receiving yards is **negatively correlated**. Game script explains this:
- Run game working → keep running → fewer catches
- Run game not working → pass more → more catches, fewer rush yards

**I do not know how books price these SGPs.** I have no data on sportsbook correlation pricing.

---

## Data Sources

### Real Data (Use These)
- `data/raw/pbp_4seasons.parquet` - 198,513 plays from 2021-2024
- `data/raw/schedules.parquet` - nflverse schedules with spreads
- nfl_data_py library - live nflverse access

### What's NOT Validated
- The 428% ROI in README - needs walk-forward verification
- The 67% win rate in README - needs walk-forward verification
- Any metrics from previous sessions without cited methodology

---

## Code Structure

```
src/
├── models/
│   ├── advanced_copula.py      # Gaussian/Multivariate copula
│   ├── empirical_correlations.py # Data-validated correlations
│   └── ...
├── recreational/
│   └── popular_bets.py         # Focus on popular bet types
├── services/
│   ├── unified_data_service.py # Single data interface
│   └── model_service.py        # XGBoost with calibration
├── props/
│   ├── correlation_engine.py   # SGP correlation scoring
│   └── hit_rate_tracker.py     # Track prop performance
└── ...

backend/
├── main.py                     # FastAPI server
└── routers/
    ├── recreational.py         # Popular bet endpoints
    └── ...

models/
└── game_outcome_*.pkl          # Trained XGBoost models
```

---

## Commands

```bash
# Refresh data from nflverse
python cli.py refresh

# Train model (walk-forward)
python cli.py train

# Generate predictions
python cli.py predict

# Start API server
python cli.py serve

# Run correlation audit
python scripts/deep_correlation_audit.py
```

---

## What Needs Work

1. **Fix README**: Remove false claims of 428% ROI and 67% win rate. Replace with actual 63.1%.

2. **Build actual prop models**: Current "hit rates" are just historical distributions, not predictions.

3. **Live testing**: All metrics are from backtesting. Need paper trading on live games.

4. **Get sportsbook data**: Cannot calculate true edge without knowing how books price correlations.

5. **Confidence calibration**: Model probabilities may not be well-calibrated.

---

## What This System Actually Does Well

1. **Correlation discovery**: Found real empirical correlations from 198,513 plays
2. **Data pipeline**: Clean nflverse data loading and processing
3. **Walk-forward methodology**: Proper backtesting without leakage (when done correctly)
4. **Recreational focus**: Prioritizes popular bet types

## What This System Does NOT Do

1. **Guarantee profits**: 63% accuracy at -110 odds is roughly break-even
2. **Predict props**: No validated predictive prop models exist
3. **Know book pricing**: Cannot determine if books misprice correlations
4. **Beat the market**: No evidence of consistent edge

---

## Principles

1. The model serves the bettor, not the other way around
2. Recreational betting should be fun AND informed
3. Honesty about limitations builds trust
4. Data beats theory every time
5. If you don't know, say you don't know
6. Never confuse descriptive stats with predictions
7. Always validate with walk-forward testing
