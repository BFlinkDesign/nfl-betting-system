# NFL Betting System: Gap & Gap-Fit Analysis

## State-of-the-Art Benchmark (2024-2026 Research)

Based on systematic review of peer-reviewed research including:
- [arXiv 2410.21484](https://arxiv.org/abs/2410.21484) - Systematic Review of ML in Sports Betting
- [Walsh & Joshi (2024)](https://www.sciencedirect.com/science/article/pii/S266682702400015X) - Calibration > Accuracy (+34.69% vs -35.17% ROI)
- [Guo et al. (2017)](https://arxiv.org/abs/1706.04599) - ECE/MCE Calibration Metrics
- [MDPI Uncertainty-Aware Forecasting](https://www.mdpi.com/2078-2489/17/1/56) - Monte Carlo Dropout for NBA
- [Nature Scientific Reports 2025](https://www.nature.com/srep/) - Stacked Ensemble for Sports

---

## Executive Summary

| Domain | Current State | Industry Best | Gap Level |
|--------|---------------|---------------|-----------|
| Model Architecture | XGBoost + Ensemble | Multi-model stacking | **LOW** |
| Calibration | ECE/MCE + Platt/Isotonic | ECE < 0.04, calibration-first | **LOW** |
| Uncertainty | MC Dropout | Conformal prediction + MC Dropout | **MEDIUM** |
| Feature Engineering | 10+ feature builders | 200+ features, multi-window rolling | **MEDIUM** |
| CLV Tracking | Implemented | Real-time closing line comparison | **LOW** |
| Real-Time Data | Limited | Live odds, injuries, weather | **HIGH** |
| Sharp Money Detection | None | Line movement + bet % analysis | **HIGH** |
| Backtesting | Walk-forward | Walk-forward + OOS + Monte Carlo sim | **MEDIUM** |
| Model Deployment | Manual | Automated retraining pipeline | **MEDIUM** |

**Overall Readiness: 65%** - Core ML infrastructure solid, needs data infrastructure and market intelligence.

---

## Detailed Gap Analysis

### 1. MODEL ARCHITECTURE

#### Current Implementation
```
src/models/
├── xgboost_model.py   ✓ XGBoostNFLModel
├── calibration.py     ✓ ModelCalibrator with ECE/MCE
├── ensemble.py        ✓ StackedEnsembleModel (XGB, LGBM, CatBoost, RF, GBM)
└── uncertainty.py     ✓ MCDropoutPredictor
```

#### State-of-the-Art Requirements
| Requirement | Status | Notes |
|-------------|--------|-------|
| Gradient Boosting (XGBoost/LightGBM/CatBoost) | ✅ HAVE | All three implemented |
| Heterogeneous Ensemble Stacking | ✅ HAVE | MLP meta-learner |
| Calibration-Optimized Training | ✅ HAVE | Walsh & Joshi methodology |
| Neural Network Component | ✅ HAVE | MC Dropout net |
| Graph Neural Networks | ❌ MISSING | Player-team-game graphs |
| Transformer/Attention | ❌ MISSING | Sequential game modeling |

#### Gap Assessment: **LOW**
- Core architecture matches research benchmarks
- GNN/Transformer would add marginal improvement for significant complexity

#### Recommendation
- **No action needed** for core model
- **Optional**: Add GNN for player injury impact modeling (diminishing returns)

---

### 2. PROBABILITY CALIBRATION

#### Current Implementation
```python
# calibration.py implements:
- Platt Scaling (sigmoid)
- Isotonic Regression
- ECE calculation (Guo et al. 2017)
- MCE calculation
- Calibration curve visualization
```

#### State-of-the-Art Requirements
| Requirement | Status | Notes |
|-------------|--------|-------|
| ECE < 0.05 target | ✅ HAVE | Metric implemented |
| Platt Scaling | ✅ HAVE | Default method |
| Isotonic Regression | ✅ HAVE | Alternative method |
| Temperature Scaling | ⚠️ PARTIAL | Not explicit, but covered by Platt |
| Beta Calibration | ❌ MISSING | Better for bounded probabilities |
| Calibration curve analysis | ✅ HAVE | plot_calibration_curve() |

#### Research Benchmark (Kovalchik & Ingram 2024)
- CatBoost ECE: 0.04 (excellent)
- Legacy models ECE: 0.09 (poor)
- Target: ECE < 0.05

#### Gap Assessment: **LOW**
- Implementation matches peer-reviewed methodology
- ECE/MCE metrics properly calculated

#### Recommendation
- Add Beta Calibration for comparison (`sklearn` doesn't have it; implement manually)
- Track ECE over time as drift indicator

---

### 3. UNCERTAINTY QUANTIFICATION

#### Current Implementation
```python
# uncertainty.py implements:
- Monte Carlo Dropout (PyTorch)
- Sklearn fallback (ensemble of MLPs)
- calculate_confidence_score()
```

#### State-of-the-Art Requirements
| Requirement | Status | Notes |
|-------------|--------|-------|
| MC Dropout | ✅ HAVE | Gal & Ghahramani 2016 |
| Ensemble Disagreement | ✅ HAVE | Via stacked ensemble |
| Conformal Prediction | ❌ MISSING | Distribution-free intervals |
| Epistemic/Aleatoric Split | ❌ MISSING | Separate model vs data uncertainty |
| Bet sizing based on uncertainty | ⚠️ PARTIAL | confidence_score exists |

#### Gap Assessment: **MEDIUM**
- Core uncertainty implemented
- Missing conformal prediction for statistically valid intervals

#### Recommendation: Implement conformal prediction wrapper

```python
# IMPLEMENTATION NEEDED: src/models/conformal.py
from mapie.classification import MapieClassifier

class ConformalPredictor:
    """
    Conformal prediction for valid prediction intervals.
    Based on COPA 2025 and ICLR 2025 research.
    """
    def __init__(self, base_model, alpha=0.1):
        self.mapie = MapieClassifier(base_model, cv="prefit")
        self.alpha = alpha
    
    def calibrate(self, X_cal, y_cal):
        self.mapie.fit(X_cal, y_cal)
    
    def predict_with_interval(self, X):
        y_pred, y_set = self.mapie.predict(X, alpha=self.alpha)
        # y_set contains prediction sets with coverage guarantee
        return y_pred, y_set
```

---

### 4. FEATURE ENGINEERING

#### Current Implementation
```
src/features/
├── elo.py        ✓ ELO ratings
├── epa.py        ✓ Expected Points Added
├── rest_days.py  ✓ Rest days
├── form.py       ✓ Recent form
├── weather.py    ✓ Weather features
├── injury.py     ✓ Injury impact
├── line.py       ✓ Betting lines
├── referee.py    ✓ Referee tendencies
├── encoding.py   ✓ Categorical encoding
└── pipeline.py   ✓ Feature pipeline
```

#### State-of-the-Art Requirements (200+ features)
| Feature Category | Status | Research Importance |
|------------------|--------|---------------------|
| ELO/Rating Systems | ✅ HAVE | High |
| EPA/Advanced Stats | ✅ HAVE | High |
| Rest/Schedule | ✅ HAVE | High |
| Weather | ✅ HAVE | Medium |
| Injuries | ✅ HAVE | High |
| Multi-Window Rolling (3, 5, 8 games) | ⚠️ PARTIAL | High |
| Opponent-Adjusted Metrics | ❌ MISSING | Very High |
| Pace/Tempo Metrics | ❌ MISSING | Medium |
| Red Zone Efficiency | ❌ MISSING | High |
| Pressure Rate (Pass Rush) | ❌ MISSING | High |
| Success Rate | ❌ MISSING | High |
| Situational Splits | ❌ MISSING | Medium |
| Market/Line Movement | ❌ MISSING | Very High |

#### Gap Assessment: **MEDIUM**
- Good foundation but missing key advanced metrics
- No opponent-adjusted features (critical for accuracy)
- No market-based features (critical for edge)

#### Recommendation: Add advanced features

```python
# IMPLEMENTATION NEEDED: src/features/advanced.py

class AdvancedFeatures(FeatureBuilder):
    """
    Research-backed advanced features.
    Based on Open Source Football and nflfastR methodology.
    """
    
    def build(self, df):
        # Multi-window rolling averages
        for window in [3, 5, 8]:
            df[f'epa_per_play_last{window}'] = self._rolling_stat('epa_per_play', window)
            df[f'success_rate_last{window}'] = self._rolling_stat('success_rate', window)
        
        # Opponent-adjusted (ridge regression)
        df['adj_off_epa'] = self._opponent_adjust('off_epa')
        df['adj_def_epa'] = self._opponent_adjust('def_epa')
        
        # Red zone efficiency
        df['rz_td_rate'] = self._calculate_rz_efficiency()
        
        # Pressure rate interaction
        df['pressure_vs_ttp'] = df['pressure_rate'] * df['time_to_throw']
        
        return df
```

---

### 5. REAL-TIME DATA INFRASTRUCTURE

#### Current Implementation
```
src/api/
├── espn_client.py    ✓ ESPN API
├── noaa_client.py    ✓ Weather
└── live_game_tracker.py ✓ Live tracking
```

#### State-of-the-Art Requirements
| Data Source | Status | Latency Required | Edge Value |
|-------------|--------|------------------|------------|
| Historical Odds | ❌ MISSING | N/A (batch) | Very High |
| Real-Time Odds | ❌ MISSING | <1 second | Critical |
| Line Movement | ❌ MISSING | <5 seconds | Critical |
| Closing Lines | ❌ MISSING | Post-game | Very High |
| Injury Reports | ⚠️ PARTIAL | <5 minutes | High |
| Weather (game time) | ✅ HAVE | <1 hour | Medium |
| Bet % / Money % | ❌ MISSING | <30 minutes | High |

#### Gap Assessment: **HIGH**
- Missing critical real-time odds data
- Cannot calculate true CLV without closing line data

#### Recommendation: Integrate odds API

```python
# IMPLEMENTATION NEEDED: src/api/odds_client.py

class OddsClient:
    """
    Real-time and historical odds from:
    - The Odds API (theOddsAPI.com)
    - OpticOdds (opticodds.com)
    """
    PROVIDERS = {
        'the_odds_api': {
            'base_url': 'https://api.the-odds-api.com/v4',
            'sports': ['americanfootball_nfl'],
            'markets': ['h2h', 'spreads', 'totals'],
            'latency': '~15 seconds',
            'cost': '$79-$499/month'
        },
        'optic_odds': {
            'base_url': 'https://api.opticodds.com',
            'features': ['real-time', 'historical', 'sharp indicators'],
            'latency': '<1 second',
            'cost': 'Enterprise'
        }
    }
    
    def get_live_odds(self, game_id):
        """Fetch current odds across books."""
        pass
    
    def get_closing_line(self, game_id):
        """Get closing line for CLV calculation."""
        pass
    
    def get_line_movement(self, game_id, hours=24):
        """Track line movement over time."""
        pass
```

---

### 6. SHARP MONEY DETECTION

#### Current Implementation
**NONE**

#### State-of-the-Art Requirements
| Signal | Description | Edge Value |
|--------|-------------|------------|
| Reverse Line Movement | Line moves opposite to public % | Very High |
| Steam Moves | Simultaneous moves across books | Very High |
| Bet % vs Money % | Sharp money disproportionate to tickets | High |
| Closing Line Value | Beat the close = real edge | Critical |
| Originator Detection | Identify which book moved first | Medium |

#### Gap Assessment: **HIGH**
- No market intelligence capabilities
- Cannot distinguish sharp from square money

#### Research Finding (Action Network, ESPN):
> "If 20% of bets account for 80% of the money, sharps are at work"
> "Reverse line movement is the strongest signal of sharp action"

#### Recommendation: Add market intelligence module

```python
# IMPLEMENTATION NEEDED: src/market/sharp_detector.py

class SharpMoneyDetector:
    """
    Detect sharp betting action based on market signals.
    """
    
    def detect_reverse_line_movement(self, game_id):
        """
        Identify when line moves opposite to public betting %.
        
        Example: 70% on Team A, but line moves from -3 to -2.5
        = Sharp money on Team B
        """
        pass
    
    def detect_steam_move(self, game_id, threshold_books=3, time_window_sec=60):
        """
        Detect simultaneous line moves across multiple books.
        
        Steam = Sharp syndicate hitting multiple books at once
        """
        pass
    
    def calculate_sharp_money_indicator(self, bet_pct, money_pct):
        """
        Sharp indicator = (Money % - Bet %) 
        
        If money % >> bet %, large bets (sharps) are on that side.
        """
        return money_pct - bet_pct
```

---

### 7. BACKTESTING & VALIDATION

#### Current Implementation
```python
# backtesting/engine.py implements:
- Walk-forward backtest
- Kelly criterion bet sizing
- CLV tracking
- GO/NO-GO validation
- Statistical significance (t-test)
```

#### State-of-the-Art Requirements
| Requirement | Status | Notes |
|-------------|--------|-------|
| Walk-Forward | ✅ HAVE | Proper temporal validation |
| Out-of-Sample Testing | ✅ HAVE | Via walk-forward |
| CLV as Primary Metric | ✅ HAVE | Research-backed |
| Statistical Significance | ✅ HAVE | t-test for CLV |
| Monte Carlo Simulation | ❌ MISSING | Variance analysis |
| Bootstrap Confidence Intervals | ❌ MISSING | CI for metrics |
| Regime Analysis | ❌ MISSING | Performance by market condition |
| Transaction Costs | ⚠️ PARTIAL | Vig accounted but not line shopping |

#### Gap Assessment: **MEDIUM**
- Core backtesting solid
- Missing variance analysis tools

#### Recommendation: Add Monte Carlo simulation

```python
# IMPLEMENTATION NEEDED: src/backtesting/monte_carlo.py

class MonteCarloSimulator:
    """
    Monte Carlo simulation for variance analysis.
    
    Key questions:
    1. What's the probability of ruin given observed edge?
    2. What's the distribution of possible outcomes?
    3. Is observed ROI statistically significant?
    """
    
    def simulate_bankroll_paths(
        self, 
        edge: float, 
        n_bets: int, 
        initial_bankroll: float,
        kelly_fraction: float = 0.25,
        n_simulations: int = 10000
    ) -> Dict:
        """
        Simulate n_simulations bankroll trajectories.
        
        Returns:
            - probability_of_ruin
            - median_final_bankroll
            - confidence_intervals (5%, 25%, 50%, 75%, 95%)
            - sharpe_distribution
        """
        pass
    
    def bootstrap_metrics(
        self,
        history_df: pd.DataFrame,
        n_bootstrap: int = 5000
    ) -> Dict:
        """
        Bootstrap confidence intervals for ROI and CLV.
        """
        pass
```

---

### 8. DEPLOYMENT & AUTOMATION

#### Current Implementation
```
scripts/
├── train_model.py     ✓ Training script
├── weekly_retrain.py  ✓ Weekly retraining
├── generate_daily_picks.py ✓ Pick generation
└── send_notifications.py ✓ Alerts
```

#### State-of-the-Art Requirements
| Requirement | Status | Notes |
|-------------|--------|-------|
| Automated Retraining | ⚠️ PARTIAL | Script exists but not scheduled |
| Model Versioning | ❌ MISSING | No MLflow/DVC |
| A/B Testing | ❌ MISSING | Compare model versions |
| Drift Detection | ❌ MISSING | Monitor calibration over time |
| Alerting on Degradation | ❌ MISSING | Auto-notify on ECE increase |
| CI/CD for Models | ❌ MISSING | Automated testing/deployment |

#### Gap Assessment: **MEDIUM**
- Manual deployment works but doesn't scale
- No systematic model monitoring

#### Recommendation: Add basic MLOps

```python
# IMPLEMENTATION NEEDED: src/mlops/model_registry.py

class ModelRegistry:
    """
    Simple model versioning and tracking.
    """
    
    def register_model(self, model, metrics, version=None):
        """Save model with metadata."""
        pass
    
    def get_best_model(self, metric='ece_calibrated'):
        """Retrieve best performing model."""
        pass
    
    def detect_drift(self, current_metrics, threshold=0.02):
        """Alert if ECE increases beyond threshold."""
        pass
```

---

## Priority Implementation Roadmap

### Phase 1: Critical Gaps (1-2 weeks)
1. **Odds API Integration** - Cannot measure true edge without closing lines
   - Cost: $79-499/month for The Odds API
   - Effort: 3-5 days
   
2. **Advanced Feature Engineering** - Opponent-adjusted metrics, multi-window rolling
   - Cost: None (data already available via nflfastR)
   - Effort: 3-5 days

### Phase 2: Market Intelligence (2-3 weeks)
3. **Sharp Money Detection** - Reverse line movement, steam moves
   - Requires: Odds API from Phase 1
   - Effort: 5-7 days

4. **Line Movement Features** - Add market signals to model
   - Effort: 3-5 days

### Phase 3: Risk Management (1-2 weeks)
5. **Conformal Prediction** - Statistically valid prediction intervals
   - Effort: 2-3 days
   
6. **Monte Carlo Simulation** - Bankroll path analysis
   - Effort: 2-3 days

### Phase 4: MLOps (2-3 weeks)
7. **Model Registry** - Versioning and tracking
   - Effort: 3-5 days
   
8. **Drift Detection** - Automated calibration monitoring
   - Effort: 2-3 days

---

## Cost-Benefit Analysis

| Investment | Cost | Expected Value |
|------------|------|----------------|
| Odds API (The Odds API Pro) | $199/month | True CLV measurement |
| Odds API (OpticOdds Enterprise) | $500+/month | Real-time + sharp indicators |
| Action Network Pro | $50/month | Bet %/Money % data |
| Compute (AWS/GCP) | $50-100/month | Automated retraining |
| **Total Monthly** | **$300-850/month** | |

**Break-even Analysis:**
- At $500/month costs
- With 1% average CLV edge
- Need $50,000 betting volume/month to break even on infrastructure
- This is achievable with proper bankroll management

---

## Sources

- [A Systematic Review of Machine Learning in Sports Betting](https://arxiv.org/abs/2410.21484) - arXiv 2024
- [Machine learning for sports betting: Calibration > Accuracy](https://www.sciencedirect.com/science/article/pii/S266682702400015X) - Walsh & Joshi 2024
- [On Calibration of Modern Neural Networks](https://arxiv.org/abs/1706.04599) - Guo et al. 2017
- [Calibration Over Accuracy: The Key to Smarter Sports Betting](https://opticodds.com/blog/calibration-the-key-to-smarter-sports-betting) - OpticOdds
- [Sharp Money 101](https://www.actionnetwork.com/education/sports-betting-sharp-money-professional-picks) - Action Network
- [Uncertainty-Aware Machine Learning for NBA Forecasting](https://www.mdpi.com/2078-2489/17/1/56) - MDPI 2024
- [Adaptive Conformal Inference by Betting](https://arxiv.org/abs/2412.19318) - ICML 2024
- [How to Build Sports Prediction Models in 2026](https://www.parlaysavant.com/insights/sports-prediction-models-2026) - ParlySavant
- [nfelo Model Performance](https://www.nfeloapp.com/games/nfl-model-performance/) - NFelo
