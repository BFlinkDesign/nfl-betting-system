"""Validation Framework - Source of Truth System

NO GUESSING. All metrics grounded in research:

Validation Metrics (per academic/industry standards):
- Brier Score: Mean squared error of probabilities (lower = better)
- Log Loss: Cross-entropy loss (more sensitive to confidence)
- Calibration (ECE): Expected Calibration Error
- CLV Rate: % of bets beating closing line (65%+ = edge)
- ROI: Profit / Total Wagered

Sample Size Requirements (per Predictology, BallDontLie research):
- Minimum 300 bets for statistical significance
- 1000+ bets for confident edge validation
- Walk-forward validation: only use pre-game data

Sources:
- https://www.predictology.co/blog/how-to-avoid-the-biggest-backtesting-pitfalls/
- https://www.dratings.com/log-loss-vs-brier-score/
- https://www.sports-ai.dev/blog/ai-model-calibration-brier-score
- https://pikkit.com/blog/how-to-track-closing-line-value-clv-in-sports-betting
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import json
from pathlib import Path

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# Industry-standard thresholds
THRESHOLDS = {
    'min_sample_exploratory': 50,
    'min_sample_actionable': 300,
    'min_sample_confident': 1000,
    'break_even_rate': 0.524,  # At -110 juice
    'good_win_rate': 0.54,
    'elite_win_rate': 0.56,
    'good_clv_rate': 0.55,  # 55% of bets beat closing
    'elite_clv_rate': 0.65,  # 65%+ = strong edge signal
    'max_acceptable_brier': 0.25,  # Random = 0.25
    'target_ece': 0.02,  # 2% calibration error target
}


@dataclass
class ValidationResult:
    """Complete validation results for a model/system."""
    timestamp: datetime
    sample_size: int
    is_valid_sample: bool  # Meets minimum sample requirement

    # Record
    wins: int
    losses: int
    pushes: int
    win_rate: float

    # Profitability
    units_wagered: float
    units_profit: float
    roi_percent: float

    # Probability Quality
    brier_score: float
    log_loss: float
    calibration_ece: float

    # CLV (edge validation)
    clv_positive_count: int
    clv_negative_count: int
    clv_rate: float
    avg_clv_cents: float

    # Assessment
    status: str  # 'insufficient_data', 'not_profitable', 'marginal', 'profitable', 'elite'
    confidence_level: str  # 'none', 'low', 'medium', 'high'
    recommendations: List[str] = field(default_factory=list)


@dataclass
class PredictionRecord:
    """Single prediction for validation tracking."""
    prediction_id: str
    game_id: str
    timestamp: datetime  # When prediction was made
    game_time: datetime  # When game started

    # Prediction
    predicted_prob: float  # Our probability
    predicted_side: str  # Team or over/under
    line_at_prediction: float
    odds_at_prediction: int

    # Closing (filled after game)
    closing_line: Optional[float] = None
    closing_odds: Optional[int] = None

    # Result (filled after game)
    actual_outcome: Optional[int] = None  # 1 = win, 0 = loss, -1 = push
    profit_units: Optional[float] = None

    # CLV
    clv_points: Optional[float] = None
    beat_closing: Optional[bool] = None


class ValidationFramework:
    """
    Rigorous validation system that proves model performance.

    Implements walk-forward validation:
    - Only uses data available BEFORE each game
    - Tracks all predictions with timestamps
    - Calculates proper metrics
    - Identifies areas for improvement
    """

    def __init__(self, data_path: str = "data/validation"):
        self.data_path = Path(data_path)
        self.data_path.mkdir(parents=True, exist_ok=True)
        self.predictions: List[PredictionRecord] = []
        self._load_history()

    def _load_history(self):
        """Load historical predictions from disk."""
        history_file = self.data_path / "prediction_history.json"
        if history_file.exists():
            with open(history_file) as f:
                data = json.load(f)
                for p in data.get('predictions', []):
                    p['timestamp'] = datetime.fromisoformat(p['timestamp'])
                    p['game_time'] = datetime.fromisoformat(p['game_time'])
                    self.predictions.append(PredictionRecord(**p))
            logger.info(f"Loaded {len(self.predictions)} historical predictions")

    def _save_history(self):
        """Save predictions to disk."""
        data = {
            'last_updated': datetime.now().isoformat(),
            'predictions': []
        }
        for p in self.predictions:
            pred_dict = {
                'prediction_id': p.prediction_id,
                'game_id': p.game_id,
                'timestamp': p.timestamp.isoformat(),
                'game_time': p.game_time.isoformat(),
                'predicted_prob': p.predicted_prob,
                'predicted_side': p.predicted_side,
                'line_at_prediction': p.line_at_prediction,
                'odds_at_prediction': p.odds_at_prediction,
                'closing_line': p.closing_line,
                'closing_odds': p.closing_odds,
                'actual_outcome': p.actual_outcome,
                'profit_units': p.profit_units,
                'clv_points': p.clv_points,
                'beat_closing': p.beat_closing,
            }
            data['predictions'].append(pred_dict)

        with open(self.data_path / "prediction_history.json", 'w') as f:
            json.dump(data, f, indent=2)

    def log_prediction(
        self,
        game_id: str,
        game_time: datetime,
        predicted_prob: float,
        predicted_side: str,
        line: float,
        odds: int,
    ) -> PredictionRecord:
        """
        Log a prediction BEFORE the game.

        Critical: timestamp must be before game_time for valid walk-forward.
        """
        now = datetime.now()

        if now >= game_time:
            raise ValueError(
                f"Cannot log prediction after game start. "
                f"Now: {now}, Game: {game_time}"
            )

        pred_id = f"{game_id}_{now.strftime('%Y%m%d%H%M%S')}"

        record = PredictionRecord(
            prediction_id=pred_id,
            game_id=game_id,
            timestamp=now,
            game_time=game_time,
            predicted_prob=predicted_prob,
            predicted_side=predicted_side,
            line_at_prediction=line,
            odds_at_prediction=odds,
        )

        self.predictions.append(record)
        self._save_history()

        logger.info(f"Logged prediction: {pred_id} | {predicted_side} @ {line} ({odds})")
        return record

    def record_result(
        self,
        prediction_id: str,
        actual_outcome: int,
        closing_line: float,
        closing_odds: int,
    ):
        """Record the result of a prediction."""
        pred = self._find_prediction(prediction_id)
        if not pred:
            logger.warning(f"Prediction {prediction_id} not found")
            return

        pred.actual_outcome = actual_outcome
        pred.closing_line = closing_line
        pred.closing_odds = closing_odds

        # Calculate profit
        if actual_outcome == 1:  # Win
            if pred.odds_at_prediction > 0:
                pred.profit_units = pred.odds_at_prediction / 100
            else:
                pred.profit_units = 100 / abs(pred.odds_at_prediction)
        elif actual_outcome == 0:  # Loss
            pred.profit_units = -1.0
        else:  # Push
            pred.profit_units = 0.0

        # Calculate CLV
        pred.clv_points = closing_line - pred.line_at_prediction
        # For spread bets on underdog, positive CLV = got more points
        pred.beat_closing = pred.clv_points > 0

        self._save_history()
        logger.info(f"Recorded result: {prediction_id} = {actual_outcome} (CLV: {pred.clv_points:+.1f})")

    def _find_prediction(self, prediction_id: str) -> Optional[PredictionRecord]:
        for p in self.predictions:
            if p.prediction_id == prediction_id:
                return p
        return None

    def validate(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> ValidationResult:
        """
        Run full validation on predictions.

        Returns comprehensive metrics with honest assessment.
        """
        # Filter predictions
        preds = [p for p in self.predictions if p.actual_outcome is not None]

        if start_date:
            preds = [p for p in preds if p.timestamp >= start_date]
        if end_date:
            preds = [p for p in preds if p.timestamp <= end_date]

        sample_size = len(preds)

        # Check sample size
        if sample_size < THRESHOLDS['min_sample_exploratory']:
            return ValidationResult(
                timestamp=datetime.now(),
                sample_size=sample_size,
                is_valid_sample=False,
                wins=0, losses=0, pushes=0, win_rate=0,
                units_wagered=0, units_profit=0, roi_percent=0,
                brier_score=0, log_loss=0, calibration_ece=0,
                clv_positive_count=0, clv_negative_count=0, clv_rate=0, avg_clv_cents=0,
                status='insufficient_data',
                confidence_level='none',
                recommendations=[f"Need {THRESHOLDS['min_sample_exploratory']} predictions minimum, have {sample_size}"],
            )

        # Calculate metrics
        wins = sum(1 for p in preds if p.actual_outcome == 1)
        losses = sum(1 for p in preds if p.actual_outcome == 0)
        pushes = sum(1 for p in preds if p.actual_outcome == -1)

        decided = wins + losses
        win_rate = wins / decided if decided > 0 else 0

        units_wagered = float(decided)
        units_profit = sum(p.profit_units or 0 for p in preds)
        roi = (units_profit / units_wagered * 100) if units_wagered > 0 else 0

        # Probability metrics
        brier = self._calculate_brier(preds)
        logloss = self._calculate_log_loss(preds)
        ece = self._calculate_ece(preds)

        # CLV metrics
        clv_preds = [p for p in preds if p.beat_closing is not None]
        clv_positive = sum(1 for p in clv_preds if p.beat_closing)
        clv_negative = len(clv_preds) - clv_positive
        clv_rate = clv_positive / len(clv_preds) if clv_preds else 0
        avg_clv = np.mean([p.clv_points or 0 for p in clv_preds]) if clv_preds else 0

        # Assessment
        status, confidence, recommendations = self._assess(
            sample_size, win_rate, roi, brier, clv_rate, ece
        )

        return ValidationResult(
            timestamp=datetime.now(),
            sample_size=sample_size,
            is_valid_sample=sample_size >= THRESHOLDS['min_sample_actionable'],
            wins=wins,
            losses=losses,
            pushes=pushes,
            win_rate=win_rate,
            units_wagered=units_wagered,
            units_profit=units_profit,
            roi_percent=roi,
            brier_score=brier,
            log_loss=logloss,
            calibration_ece=ece,
            clv_positive_count=clv_positive,
            clv_negative_count=clv_negative,
            clv_rate=clv_rate,
            avg_clv_cents=avg_clv * 10,  # Convert to cents
            status=status,
            confidence_level=confidence,
            recommendations=recommendations,
        )

    def _calculate_brier(self, preds: List[PredictionRecord]) -> float:
        """Calculate Brier score (lower = better, 0.25 = random)."""
        if not preds:
            return 1.0

        scores = []
        for p in preds:
            if p.actual_outcome in [0, 1]:
                prob = p.predicted_prob
                outcome = p.actual_outcome
                scores.append((prob - outcome) ** 2)

        return np.mean(scores) if scores else 1.0

    def _calculate_log_loss(self, preds: List[PredictionRecord]) -> float:
        """Calculate log loss (lower = better)."""
        if not preds:
            return float('inf')

        eps = 1e-7
        losses = []
        for p in preds:
            if p.actual_outcome in [0, 1]:
                prob = np.clip(p.predicted_prob, eps, 1 - eps)
                outcome = p.actual_outcome
                loss = -(outcome * np.log(prob) + (1 - outcome) * np.log(1 - prob))
                losses.append(loss)

        return np.mean(losses) if losses else float('inf')

    def _calculate_ece(self, preds: List[PredictionRecord], n_bins: int = 10) -> float:
        """Calculate Expected Calibration Error."""
        if not preds:
            return 1.0

        bins = [[] for _ in range(n_bins)]

        for p in preds:
            if p.actual_outcome in [0, 1]:
                bin_idx = min(int(p.predicted_prob * n_bins), n_bins - 1)
                bins[bin_idx].append((p.predicted_prob, p.actual_outcome))

        ece = 0.0
        total = sum(len(b) for b in bins)

        for b in bins:
            if len(b) > 0:
                avg_prob = np.mean([x[0] for x in b])
                avg_outcome = np.mean([x[1] for x in b])
                ece += (len(b) / total) * abs(avg_prob - avg_outcome)

        return ece

    def _assess(
        self,
        sample_size: int,
        win_rate: float,
        roi: float,
        brier: float,
        clv_rate: float,
        ece: float,
    ) -> Tuple[str, str, List[str]]:
        """Generate honest assessment and recommendations."""
        recommendations = []

        # Sample size check
        if sample_size < THRESHOLDS['min_sample_actionable']:
            recommendations.append(
                f"Sample size ({sample_size}) below actionable threshold ({THRESHOLDS['min_sample_actionable']}). "
                "Results may be noise."
            )
            confidence = 'low'
        elif sample_size < THRESHOLDS['min_sample_confident']:
            confidence = 'medium'
        else:
            confidence = 'high'

        # Profitability check
        if win_rate < THRESHOLDS['break_even_rate']:
            status = 'not_profitable'
            recommendations.append(
                f"Win rate ({win_rate:.1%}) below break-even ({THRESHOLDS['break_even_rate']:.1%}). "
                "Review model features."
            )
        elif win_rate < THRESHOLDS['good_win_rate']:
            status = 'marginal'
            recommendations.append("Win rate is marginal. Consider higher-confidence selections only.")
        elif win_rate < THRESHOLDS['elite_win_rate']:
            status = 'profitable'
        else:
            status = 'elite'

        # CLV check (most important non-result signal)
        if clv_rate < 0.50:
            recommendations.append(
                f"CLV rate ({clv_rate:.0%}) below 50%. Getting bad numbers - improve timing."
            )
        elif clv_rate >= THRESHOLDS['elite_clv_rate']:
            recommendations.append(
                f"Strong CLV rate ({clv_rate:.0%}). Model captures genuine edge."
            )

        # Calibration check
        if ece > THRESHOLDS['target_ece']:
            recommendations.append(
                f"Calibration error ({ece:.3f}) above target ({THRESHOLDS['target_ece']}). "
                "Consider recalibration."
            )

        # Brier check
        if brier > THRESHOLDS['max_acceptable_brier']:
            recommendations.append(
                f"Brier score ({brier:.3f}) near random. Probability estimates need improvement."
            )

        return status, confidence, recommendations

    def print_validation_report(self, result: ValidationResult):
        """Print comprehensive validation report."""
        print("\n" + "=" * 70)
        print("📊 MODEL VALIDATION REPORT")
        print(f"Generated: {result.timestamp.strftime('%Y-%m-%d %H:%M')}")
        print("=" * 70)

        # Sample
        validity = "✅ VALID" if result.is_valid_sample else "⚠️ INSUFFICIENT"
        print(f"\nSample Size: {result.sample_size} ({validity})")
        print(f"Required for confidence: {THRESHOLDS['min_sample_confident']}")

        # Record
        print(f"\n📈 RECORD")
        print(f"   {result.wins}-{result.losses}-{result.pushes}")
        print(f"   Win Rate: {result.win_rate:.1%} (break-even: {THRESHOLDS['break_even_rate']:.1%})")

        # Profitability
        print(f"\n💰 PROFITABILITY")
        print(f"   Units Wagered: {result.units_wagered:.1f}")
        print(f"   Units Profit: {result.units_profit:+.2f}")
        print(f"   ROI: {result.roi_percent:+.1f}%")

        # Probability Quality
        print(f"\n🎯 PROBABILITY QUALITY")
        print(f"   Brier Score: {result.brier_score:.4f} (random=0.25, lower=better)")
        print(f"   Log Loss: {result.log_loss:.4f}")
        print(f"   Calibration (ECE): {result.calibration_ece:.4f} (target<{THRESHOLDS['target_ece']})")

        # CLV
        print(f"\n📉 CLOSING LINE VALUE")
        print(f"   Beat Closing: {result.clv_positive_count}/{result.clv_positive_count + result.clv_negative_count}")
        print(f"   CLV Rate: {result.clv_rate:.0%} (elite>{THRESHOLDS['elite_clv_rate']:.0%})")
        print(f"   Avg CLV: {result.avg_clv_cents:+.1f} cents")

        # Assessment
        status_emoji = {
            'insufficient_data': '⏳',
            'not_profitable': '❌',
            'marginal': '⚠️',
            'profitable': '✅',
            'elite': '🏆',
        }
        print(f"\n📋 ASSESSMENT")
        print(f"   Status: {status_emoji.get(result.status, '?')} {result.status.upper()}")
        print(f"   Confidence: {result.confidence_level.upper()}")

        # Recommendations
        if result.recommendations:
            print(f"\n💡 RECOMMENDATIONS")
            for rec in result.recommendations:
                print(f"   • {rec}")

        print("\n" + "=" * 70)


def create_validation_framework() -> ValidationFramework:
    """Create and return validation framework instance."""
    return ValidationFramework()
