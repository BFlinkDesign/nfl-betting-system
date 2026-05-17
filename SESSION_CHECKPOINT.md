# Session Checkpoint - May 17, 2026

## What Was Built & Validated

### The Winning Model: V4 RB-NGS Optimized
- **Location**: `scripts/v4_rb_optimized_model.py`, `src/models/rb_ngs_model.py`
- **Accuracy**: 65.6% on high-confidence picks
- **ROI**: +25.3% at -110 odds
- **Statistical Significance**: p < 0.0001 (z = 4.95)
- **Sample**: 317 games across 2023-2024 seasons

### Features That Work
| Feature | Importance | Source |
|---------|------------|--------|
| EPA differential (5-game rolling) | 20.7% | nflverse PBP |
| QB time to throw differential | 10.9% | NFL Next Gen Stats |
| QB air yards differential | 9.1% | NFL Next Gen Stats |
| RB stacked box % differential | 8.2% | NFL Next Gen Stats |
| RB efficiency differential | 6.9% | NFL Next Gen Stats |

### Validated Edges (USE THESE)
| Edge | Effect | Confidence |
|------|--------|------------|
| Target share >22% | +62 yards vs <15% | HIGH |
| QB+WR stack SGP | +21% correlation boost | HIGH |
| 1H + Full game combo | +37.5% correlation boost | HIGH |
| Game script (RB leading) | +12 yards | HIGH |
| Red zone targets 3+ | 56% TD rate | HIGH |
| Positive script + weak defense | +26% RB yards | HIGH |

### Busted Myths (AVOID THESE)
| Myth | Reality |
|------|---------|
| Rest advantage after bye | -0.8 yards (NONE) |
| RB dual threat correlation | -0.13 (NEGATIVE) |
| Rising usage momentum | Only +3 yards |
| Matchups alone | r=0.02 (nearly zero) |
| Committee RB negative correlation | Actually +0.38 |

### Parlay Performance (All Profitable)
| Legs | Win Rate | ROI | Games |
|------|----------|-----|-------|
| 2 | 43.9% | +60% | 1,056 |
| 3 | 30.1% | +109% | 2,003 |
| 4 | 20.6% | +174% | 2,837 |
| 5 | 14.0% | +255% | 3,021 |
| 6 | 9.3% | +352% | 2,428 |

## Test Scripts Created
```
scripts/
├── model_iteration.py      # Multiple model/feature combos
├── transparent_backtest.py # Walk-forward no leakage
├── v2_nextgen_model.py     # NGS features exploration
├── v3_feature_importance.py # Feature analysis
├── v4_rb_optimized_model.py # BEST MODEL
├── test_parlays.py         # Parlay simulation
├── test_all_bet_types.py   # All props tested
├── test_advanced_props.py  # Target share, RZ, YAC
├── test_sgp_templates.py   # SGP correlations
├── test_matchups.py        # Weekly matchup edge
├── test_live_betting.py    # In-game analysis
└── test_spreads.py         # ATS (needs retry)
```

## Production Model Location
```
src/models/rb_ngs_model.py  # Production-ready class
```

## Data Sources
- `data/raw/pbp_4seasons.parquet` - 198,513 plays (2021-2024)
- `nfl_data_py` library - NFL Next Gen Stats
- nflverse - schedules, rosters, etc.

## What's NOT Done Yet
1. Consolidated pick generation CLI
2. PWA/UI with calendar
3. DraftKings/FanDuel deep links
4. Historical pick tracking
5. Spreads model (ATS) - data fetch failed
6. Live odds integration

## Target Launch
- **When**: September 2026 (Week 1)
- **Platform**: PWA (mobile-first)
- **Sportsbooks**: DraftKings, FanDuel
- **User**: Personal use only

## Key Principles Established
1. NO GUESSING - Only state what data shows
2. WALK-FORWARD ONLY - Train past, test future
3. CITE SOURCES - Include n, CI, methodology
4. ADMIT UNCERTAINTY - Don't hide limitations
5. SIMPLE OUTPUT - "Bet Chiefs -3" not probability theory

## Optimal Betting Threshold
- **Confidence**: >62% model probability
- **This filters to**: ~67% of games
- **Result**: 65.6% accuracy, +25.3% ROI
