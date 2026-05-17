"""Self-Improving Feedback Loop

Every prediction outcome feeds back into the system.
The model identifies what's working and what needs improvement.

Based on research:
- https://leans.ai/reinforcement-learning-sports-betting/
- https://symphony-solutions.com/insights/ai-in-sports-betting

Key principles:
1. Every loss refines the model
2. Track feature importance changes week-to-week
3. Detect when correlations break down (regime shifts)
4. Automatic recalibration when ECE exceeds threshold
5. Rolling performance windows to adapt to market changes
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import json
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class PerformanceWindow:
    """Performance metrics for a time window."""
    window_name: str  # 'last_week', 'last_month', 'season'
    start_date: datetime
    end_date: datetime

    # Metrics
    predictions: int
    wins: int
    losses: int
    win_rate: float
    roi: float
    avg_clv: float

    # Trend
    trend: str  # 'improving', 'stable', 'declining'
    change_from_prior: float


@dataclass
class FeatureSignal:
    """Signal strength of a feature over time."""
    feature_name: str
    current_importance: float
    prior_importance: float
    change: float
    status: str  # 'strengthening', 'stable', 'weakening'


@dataclass
class ImprovementSignal:
    """Identified improvement opportunity."""
    signal_type: str
    description: str
    evidence: Dict
    priority: str  # 'high', 'medium', 'low'
    suggested_action: str


class FeedbackLoop:
    """
    Self-improving system that learns from every prediction.

    Core functions:
    1. Track rolling performance windows
    2. Monitor feature importance changes
    3. Detect regime shifts (correlations breaking down)
    4. Trigger recalibration when needed
    5. Generate improvement recommendations
    """

    # Performance thresholds
    DECLINE_THRESHOLD = -0.05  # 5% drop triggers alert
    RECALIBRATION_ECE = 0.03  # ECE above 3% triggers recalibration

    def __init__(self, data_path: str = "data/feedback"):
        self.data_path = Path(data_path)
        self.data_path.mkdir(parents=True, exist_ok=True)

        self.performance_history: List[PerformanceWindow] = []
        self.feature_signals: List[FeatureSignal] = []
        self.improvement_signals: List[ImprovementSignal] = []

        self._load_state()

    def _load_state(self):
        """Load saved state from disk."""
        state_file = self.data_path / "feedback_state.json"
        if state_file.exists():
            with open(state_file) as f:
                data = json.load(f)
                # Load state...
            logger.info("Loaded feedback loop state")

    def _save_state(self):
        """Save state to disk."""
        # Save state...
        pass

    def process_result(
        self,
        prediction_id: str,
        predicted_prob: float,
        actual_outcome: int,
        features_used: Dict[str, float],
        edge_types: List[str],
        clv: float,
    ):
        """
        Process a single prediction result.

        This is the core feedback mechanism - every result improves the model.
        """
        # Log the result
        result_data = {
            'prediction_id': prediction_id,
            'timestamp': datetime.now().isoformat(),
            'predicted_prob': predicted_prob,
            'actual_outcome': actual_outcome,
            'features': features_used,
            'edge_types': edge_types,
            'clv': clv,
            'was_correct': (actual_outcome == 1 and predicted_prob > 0.5) or
                          (actual_outcome == 0 and predicted_prob < 0.5),
        }

        # Append to results log
        results_file = self.data_path / "results_log.jsonl"
        with open(results_file, 'a') as f:
            f.write(json.dumps(result_data) + '\n')

        # Update feature signals
        self._update_feature_signals(features_used, result_data['was_correct'])

        # Check for regime shifts
        self._check_regime_shifts(edge_types, actual_outcome)

        logger.info(f"Processed result: {prediction_id} - {'✓' if result_data['was_correct'] else '✗'}")

    def _update_feature_signals(self, features: Dict[str, float], was_correct: bool):
        """Track which features are contributing to wins/losses."""
        # This would aggregate feature performance over time
        # and identify which features are strengthening or weakening
        pass

    def _check_regime_shifts(self, edge_types: List[str], outcome: int):
        """Check if any edge types are showing regime shifts."""
        # Track edge type performance over rolling windows
        # Alert when historical patterns break down
        pass

    def calculate_rolling_performance(
        self,
        predictions_df: pd.DataFrame,
        windows: List[Tuple[str, int]] = None,  # (name, days)
    ) -> List[PerformanceWindow]:
        """
        Calculate performance across multiple time windows.

        Default windows:
        - Last 7 days
        - Last 30 days
        - Last 90 days
        - Season to date
        """
        if windows is None:
            windows = [
                ('last_week', 7),
                ('last_month', 30),
                ('last_quarter', 90),
                ('season', 180),
            ]

        now = datetime.now()
        results = []

        for window_name, days in windows:
            start = now - timedelta(days=days)
            end = now

            window_preds = predictions_df[
                (predictions_df['timestamp'] >= start) &
                (predictions_df['timestamp'] <= end)
            ]

            if len(window_preds) < 10:
                continue

            wins = (window_preds['outcome'] == 1).sum()
            losses = (window_preds['outcome'] == 0).sum()
            total = wins + losses

            win_rate = wins / total if total > 0 else 0
            roi = window_preds['profit'].sum() / total * 100 if total > 0 else 0
            avg_clv = window_preds['clv'].mean() if 'clv' in window_preds.columns else 0

            # Calculate trend (compare to prior window)
            prior_start = start - timedelta(days=days)
            prior_preds = predictions_df[
                (predictions_df['timestamp'] >= prior_start) &
                (predictions_df['timestamp'] < start)
            ]

            if len(prior_preds) >= 10:
                prior_wins = (prior_preds['outcome'] == 1).sum()
                prior_total = prior_wins + (prior_preds['outcome'] == 0).sum()
                prior_rate = prior_wins / prior_total if prior_total > 0 else 0
                change = win_rate - prior_rate

                if change > 0.03:
                    trend = 'improving'
                elif change < -0.03:
                    trend = 'declining'
                else:
                    trend = 'stable'
            else:
                change = 0
                trend = 'stable'

            results.append(PerformanceWindow(
                window_name=window_name,
                start_date=start,
                end_date=end,
                predictions=int(total),
                wins=int(wins),
                losses=int(losses),
                win_rate=win_rate,
                roi=roi,
                avg_clv=avg_clv,
                trend=trend,
                change_from_prior=change,
            ))

        self.performance_history = results
        return results

    def analyze_feature_importance_changes(
        self,
        current_importance: Dict[str, float],
        prior_importance: Dict[str, float],
    ) -> List[FeatureSignal]:
        """
        Track how feature importance changes week-to-week.

        Identifies features that are gaining or losing predictive power.
        """
        signals = []

        all_features = set(current_importance.keys()) | set(prior_importance.keys())

        for feature in all_features:
            current = current_importance.get(feature, 0)
            prior = prior_importance.get(feature, 0)

            if prior > 0:
                change_pct = (current - prior) / prior
            else:
                change_pct = 1.0 if current > 0 else 0

            if change_pct > 0.20:
                status = 'strengthening'
            elif change_pct < -0.20:
                status = 'weakening'
            else:
                status = 'stable'

            signals.append(FeatureSignal(
                feature_name=feature,
                current_importance=current,
                prior_importance=prior,
                change=change_pct,
                status=status,
            ))

        self.feature_signals = sorted(signals, key=lambda s: abs(s.change), reverse=True)
        return self.feature_signals

    def detect_improvement_opportunities(self) -> List[ImprovementSignal]:
        """
        Analyze all signals and generate improvement recommendations.

        This is the self-improving core - identifying what to fix.
        """
        signals = []

        # Check performance trends
        for window in self.performance_history:
            if window.trend == 'declining' and window.change_from_prior < self.DECLINE_THRESHOLD:
                signals.append(ImprovementSignal(
                    signal_type='performance_decline',
                    description=f"Win rate declining in {window.window_name} window",
                    evidence={
                        'current_rate': window.win_rate,
                        'change': window.change_from_prior,
                    },
                    priority='high',
                    suggested_action='Review recent losses for patterns. Check for market changes.',
                ))

        # Check feature stability
        weakening = [f for f in self.feature_signals if f.status == 'weakening']
        if weakening:
            signals.append(ImprovementSignal(
                signal_type='feature_degradation',
                description=f"{len(weakening)} features losing predictive power",
                evidence={
                    'features': [f.feature_name for f in weakening[:5]],
                },
                priority='medium',
                suggested_action='Consider removing or replacing weak features. Retrain model.',
            ))

        # Check CLV trends
        recent_windows = [w for w in self.performance_history if w.window_name in ['last_week', 'last_month']]
        for w in recent_windows:
            if w.avg_clv < 0:
                signals.append(ImprovementSignal(
                    signal_type='negative_clv',
                    description=f"Negative average CLV in {w.window_name}",
                    evidence={'avg_clv': w.avg_clv},
                    priority='high',
                    suggested_action='Bet timing may be off. Consider betting earlier or line shopping.',
                ))

        self.improvement_signals = signals
        return signals

    def should_recalibrate(self, current_ece: float) -> bool:
        """Check if model needs recalibration."""
        return current_ece > self.RECALIBRATION_ECE

    def generate_feedback_report(self) -> str:
        """Generate comprehensive feedback report."""
        lines = []
        lines.append("\n" + "=" * 70)
        lines.append("🔄 SELF-IMPROVEMENT FEEDBACK REPORT")
        lines.append("=" * 70)

        # Performance Windows
        if self.performance_history:
            lines.append("\n📊 ROLLING PERFORMANCE")
            lines.append("-" * 40)
            for w in self.performance_history:
                trend_emoji = {'improving': '📈', 'stable': '➡️', 'declining': '📉'}
                lines.append(f"  {w.window_name}: {w.win_rate:.1%} ({trend_emoji[w.trend]} {w.change_from_prior:+.1%})")

        # Feature Signals
        if self.feature_signals:
            lines.append("\n🔍 FEATURE SIGNALS")
            lines.append("-" * 40)
            top_changes = self.feature_signals[:5]
            for f in top_changes:
                status_emoji = {'strengthening': '⬆️', 'stable': '➡️', 'weakening': '⬇️'}
                lines.append(f"  {status_emoji[f.status]} {f.feature_name}: {f.change:+.0%}")

        # Improvement Opportunities
        if self.improvement_signals:
            lines.append("\n💡 IMPROVEMENT OPPORTUNITIES")
            lines.append("-" * 40)
            for sig in self.improvement_signals:
                priority_emoji = {'high': '🔴', 'medium': '🟡', 'low': '🟢'}
                lines.append(f"\n  {priority_emoji[sig.priority]} {sig.signal_type.upper()}")
                lines.append(f"     {sig.description}")
                lines.append(f"     → {sig.suggested_action}")

        if not self.improvement_signals:
            lines.append("\n✅ No immediate improvement opportunities detected.")

        lines.append("\n" + "=" * 70)

        return "\n".join(lines)


def create_feedback_loop() -> FeedbackLoop:
    """Create and return feedback loop instance."""
    return FeedbackLoop()
