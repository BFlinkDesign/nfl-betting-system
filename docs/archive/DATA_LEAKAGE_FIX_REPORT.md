# Data Leakage Fix Report

**Date**: 2025-01-27  
**Status**: ✅ **FIXES APPLIED - HONEST RESULTS OBTAINED**  
**Decision**: 🔴 **NO-GO** (2/6 criteria passed)

---

## Critical Issue Identified

### Problem: Data Leakage via Betting Lines

**Original Issue**: Model was using Vegas betting lines as features:
- `home_moneyline` (26.8% importance)
- `away_moneyline` (6.6% importance)
- `spread_line` (7.5% importance)
- `home_favorite` (derived from spread_line)

**Why This is Wrong**:
- Vegas odds already encode all public information
- Model was learning to read Vegas, not make independent predictions
- Results were circular: "When Vegas says team will win, they usually do"

---

## Fixes Applied

### Fix 1: Removed Betting Line Features ✅

**Files Modified**:
- `scripts/train_model.py` - Added betting lines to exclude list
- `scripts/backtest.py` - Added betting lines to exclude list

**Features Removed**:
- `home_moneyline`, `away_moneyline`
- `spread_line`, `home_spread_odds`, `away_spread_odds`
- `total_line`, `over_odds`, `under_odds`
- `line_movement`, `total_movement`, `home_favorite` (derived features)

### Fix 2: Use Actual Moneyline Odds ✅

**File Modified**: `scripts/backtest.py`

**Change**: Convert American odds to decimal odds instead of fixed 1.91

```python
def american_to_decimal(american_odds):
    if american_odds > 0:
        return (american_odds / 100) + 1
    else:
        return (100 / abs(american_odds)) + 1

df['odds'] = df['home_moneyline'].apply(american_to_decimal)
```

### Fix 3: Documented EPA Limitation ✅

**File Modified**: `src/features/epa.py`

**Status**: EPA features return zeros (no PBP data available)
- Documented why this happens
- Will work when PBP data is downloaded

---

## Results Comparison

### Before Fixes (With Data Leakage)

| Metric | Value | Status |
|--------|-------|--------|
| Accuracy | 61.4% | ✅ PASS |
| Win Rate | 67.22% | ✅ PASS |
| ROI | 428.04% | ✅ PASS |
| Max Drawdown | -16.17% | ✅ PASS |
| Sharpe Ratio | 5.00 | ✅ PASS |
| Total Bets | 302 | ✅ PASS |
| **Decision** | **GO** | ✅ |

**Top Features**: `home_moneyline` (26.8%), `spread_line` (7.5%), `away_moneyline` (6.6%)

### After Fixes (Honest Results)

| Metric | Value | Status |
|--------|-------|--------|
| Accuracy | 60.7% | ✅ PASS |
| Win Rate | 49.57% | ❌ FAIL |
| ROI | -23.62% | ❌ FAIL |
| Max Drawdown | -25.15% | ❌ FAIL |
| Sharpe Ratio | -1.72 | ❌ FAIL |
| Total Bets | 117 | ✅ PASS |
| Avg CLV | 33.97% | ✅ PASS |
| **Decision** | **NO-GO** | ❌ |

**Top Features**: `elo_prob_home` (17.5%), `point_diff_away` (8.1%), `win_pct_home` (7.3%)

---

## Analysis

### Why Results Changed

1. **Fewer Bets**: 117 vs 302 (61% reduction)
   - Without betting lines, model is less confident
   - Kelly criterion filters more aggressively (min_edge 2%, min_prob 55%)

2. **Lower Win Rate**: 49.57% vs 67.22%
   - Model no longer has Vegas's knowledge
   - Must rely on Elo, form, rest days, weather only

3. **Negative ROI**: -23.62% vs +428.04%
   - Without edge from betting lines, model loses money
   - Realistic odds vary (not all 1.91), reducing profitability

4. **Higher Drawdown**: -25.15% vs -16.17%
   - More volatile without consistent edge
   - Losing streaks more impactful

### Why CLV is Still Positive

**Observation**: Avg CLV = 33.97% but ROI = -23.62%

**Explanation**:
- CLV measures expected value: `(pred_prob × odds) - 1`
- Model predicts 55%+ probability, gets 1.91 odds
- Minimum CLV: `(0.55 × 1.91) - 1 = 0.05 = +5%`
- But actual win rate (49.57%) < predicted (55%+)
- Model is overconfident → loses money despite positive CLV

**This is a calibration issue**: Model probabilities are too high.

---

## GO/NO-GO Decision

### Criteria Evaluation

| Criterion | Required | Actual | Status |
|-----------|----------|--------|--------|
| Win Rate >55% | ✅ | 49.57% | ❌ FAIL |
| ROI >3% | ✅ | -23.62% | ❌ FAIL |
| Max Drawdown <20% | ✅ | -25.15% | ❌ FAIL |
| Total Bets >50 | ✅ | 117 | ✅ PASS |
| Sharpe Ratio >0.5 | ✅ | -1.72 | ❌ FAIL |
| Positive CLV | ✅ | 33.97% | ✅ PASS |

**Result**: 2/6 criteria passed → **NO-GO DECISION**

---

## Recommendations

### Immediate Actions

1. **DO NOT proceed to live trading**
   - System loses money without betting line features
   - Win rate below threshold (49.57% < 55%)

2. **Improve Model Calibration**
   - Current probabilities are overconfident
   - Need better probability estimates for Kelly sizing

3. **Feature Engineering Improvements**
   - Add EPA features (download PBP data)
   - Add injury data
   - Add referee statistics
   - Add team matchup history

4. **Betting Strategy Adjustments**
   - Reduce minimum probability threshold (maybe 52% instead of 55%)
   - Adjust Kelly fraction (maybe 1/8 instead of 1/4)
   - Add stop-loss rules

### Future Work

1. **Hyperparameter Tuning**
   - Use Optuna for XGBoost optimization
   - Focus on probability calibration

2. **Ensemble Methods**
   - Combine multiple models
   - Use stacking or voting

3. **Alternative Approaches**
   - Consider regression (predict margin) instead of classification
   - Use deep learning for sequence modeling
   - Add market efficiency features (without using lines directly)

---

## Lessons Learned

### What Went Wrong

1. **Data Leakage**: Used betting lines as features without recognizing circular logic
2. **Unrealistic Odds**: Fixed 1.91 odds masked true performance
3. **Overconfidence**: Model probabilities too high, leading to losses

### What Went Right

1. **Temporal Split**: Proper train/val/test split (no random shuffle)
2. **Feature Engineering**: Elo, form, rest days implemented correctly
3. **Code Quality**: Good structure, tests, documentation
4. **Audit Process**: Caught the issue before deployment

---

## Conclusion

The system is **technically complete** but **not profitable** without betting line features.

**Status**: 🔴 **NO-GO**

**Next Steps**:
1. Improve feature engineering (EPA, injuries, etc.)
2. Better probability calibration
3. Adjust betting strategy parameters
4. Re-test with improvements

**Estimated Time to Fix**: 10-20 hours

---

**Report Generated**: 2025-01-27  
**Fixes Applied**: ✅ Complete  
**Honest Results**: ✅ Obtained  
**Decision**: 🔴 NO-GO

