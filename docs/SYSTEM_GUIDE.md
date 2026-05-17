# NFL Betting System - Quick Reference Guide

**Purpose:** Fun beer money bets using research-backed edges  
**Philosophy:** Simple to use, complex under the hood, fully autonomous

## Quick Start

```bash
# First time setup - download data and train model
python scripts/enhanced_picks.py --download --train

# Get this week's picks
python scripts/enhanced_picks.py

# Validate historical edges
python scripts/enhanced_picks.py --validate
```

## What You Get

1. **Weekly Picks** with confidence ratings (★★★ STRONG / ★★ LEAN / ★ SMALL)
2. **Edge Detection** - Research-proven market inefficiencies flagged automatically
3. **Multi-Signal Analysis** - Model + Market + Situational factors combined
4. **Bet Sizing** - Units based on confidence (0.5 to 2.0)

## The Edges (Research-Backed)

| Edge Type | Historical Rate | Source |
|-----------|----------------|--------|
| Divisional Underdog | 71% ATS | NxtBets 2014-2024 |
| Home Underdog in Division | 56% ATS | Sharp Football |
| Rest Advantage (7+ vs 6-) | 54% ATS | Warren Sharp |
| Letdown Spot | 55% ATS | Situational analysis |
| Lookahead Spot | 54% ATS | Market psychology |

## System Components

### 1. Data Layer (`src/data/`)
- **nfl_data.py**: Downloads from nflverse (schedules, play-by-play)
- Calculates EPA, success rate, team stats

### 2. Model Layer (`src/models/`)
- **xgboost_model.py**: XGBoost with calibration
- **probability_stacking.py**: Combines model + market + situational
- **conformal.py**: Uncertainty quantification

### 3. Edge Detection (`src/edges/`)
- **market_edges.py**: Detects divisional, rest, psychological edges
- **rest_disparity.py**: Warren Sharp framework for rest analysis

### 4. Validation (`src/validation/`)
- **hypothesis_testing.py**: Statistical validation of edges
- **statistical_validator.py**: Professional-grade validation

### 5. Tracking (`src/tracking/`)
- **clv_tracker.py**: Closing Line Value tracking (truth metric)

## Key Metrics to Track

### CLV (Closing Line Value)
The **only** metric that predicts long-term profitability:
- If you consistently beat closing lines → you have real edge
- If you don't → you got lucky/unlucky

```python
from src.tracking.clv_tracker import CLVTracker
tracker = CLVTracker()
# Record bets, track CLV over time
tracker.print_clv_report()
```

### Hypothesis Testing
Validate edges before trusting them:

```python
from src.validation.hypothesis_testing import validate_historical_edges
# Returns statistical significance for each claimed edge
```

## Probability Stacking

Combines three probability sources:
1. **Model (40%)**: XGBoost prediction
2. **Market (45%)**: Implied from spread/odds
3. **Situational (15%)**: Edge adjustments

```
Final Prob = w_model × model_logit + w_market × market_logit + situational_adj
```

## File Outputs

Picks are saved to `data/predictions/`:
- `enhanced_picks_YYYYMMDD.csv` - Spreadsheet format
- `enhanced_picks_YYYYMMDD.json` - Programmatic access

## Important Reminders

1. **This is for FUN** - Beer money bets, not professional gambling
2. **Track CLV** - It's the truth metric, not win/loss record
3. **Sample Size Matters** - Edges need 100+ bets to validate
4. **Past ≠ Future** - Historical rates can change
5. **Gamble Responsibly** - Only bet what you can afford to lose

## Research Sources

- nflfastR / nflverse (Ben Baldwin, @benbbaldwin)
- Warren Sharp (@SharpFootball)
- PlusEV Analytics (@PlusEVAnalytics)
- Academic: Guo et al. 2017 (calibration), Shafer & Vovk (conformal)

---

*"If your edge doesn't show up in a pivot table, your ML model is lying to you."*
