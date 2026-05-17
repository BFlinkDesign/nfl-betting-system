"""Conformal prediction for statistically valid prediction intervals.

Based on:
- Shafer & Vovk (2008) "A Tutorial on Conformal Prediction"
- ICML 2024 "Adaptive Conformal Inference by Betting"
- ICLR 2025 conformal prediction advances

Key advantage: Distribution-free coverage guarantees without
distributional assumptions.
"""

import logging
from typing import Dict, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class ConformalPredictor:
    """
    Conformal prediction wrapper for classification.

    Provides prediction sets with guaranteed coverage probability.
    If alpha=0.1, the true label is in the prediction set 90% of the time.
    """

    def __init__(self, base_model, alpha: float = 0.1):
        """
        Initialize conformal predictor.

        Args:
            base_model: Trained classifier with predict_proba method
            alpha: Miscoverage rate (1 - coverage). Default 0.1 = 90% coverage
        """
        self.base_model = base_model
        self.alpha = alpha
        self.calibration_scores: Optional[np.ndarray] = None
        self.threshold: Optional[float] = None
        self._is_calibrated = False

    def calibrate(self, X_cal: pd.DataFrame, y_cal: pd.Series) -> "ConformalPredictor":
        """
        Calibrate using held-out calibration data.

        CRITICAL: Use data NOT used for training or validation.

        Args:
            X_cal: Calibration features
            y_cal: True labels

        Returns:
            self for chaining
        """
        logger.info(f"Calibrating conformal predictor with {len(X_cal)} samples...")

        # Get probability predictions
        if hasattr(self.base_model, 'predict_proba'):
            proba = self.base_model.predict_proba(X_cal)
            if proba.ndim == 2:
                proba = proba[:, 1]
        else:
            raise ValueError("Base model must have predict_proba method")

        # Calculate nonconformity scores
        # Score = 1 - P(true class)
        # Higher score = less conforming prediction
        y_array = y_cal.values if hasattr(y_cal, 'values') else np.array(y_cal)
        self.calibration_scores = np.where(
            y_array == 1,
            1 - proba,  # For positive class
            proba       # For negative class (1 - (1-proba))
        )

        # Calculate threshold for desired coverage
        n = len(self.calibration_scores)
        q_level = np.ceil((n + 1) * (1 - self.alpha)) / n
        self.threshold = np.quantile(self.calibration_scores, q_level, method='higher')

        self._is_calibrated = True
        logger.info(f"Calibration complete. Threshold: {self.threshold:.4f}")

        return self

    def predict_with_sets(
        self, X: pd.DataFrame
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Predict with conformal prediction sets.

        Args:
            X: Features

        Returns:
            (point_predictions, prediction_sets, set_sizes)
            - point_predictions: Most likely class (0 or 1)
            - prediction_sets: Boolean array [n_samples, 2] indicating which classes are in set
            - set_sizes: Number of classes in each prediction set (1 or 2)
        """
        if not self._is_calibrated:
            raise ValueError("Must calibrate before predicting. Call calibrate() first.")

        # Get probabilities
        if hasattr(self.base_model, 'predict_proba'):
            proba = self.base_model.predict_proba(X)
            if proba.ndim == 2:
                proba_pos = proba[:, 1]
            else:
                proba_pos = proba
        else:
            raise ValueError("Base model must have predict_proba method")

        n_samples = len(X)

        # Point predictions
        point_preds = (proba_pos >= 0.5).astype(int)

        # Prediction sets
        # Class is in set if its nonconformity score <= threshold
        score_class0 = proba_pos      # Score for class 0
        score_class1 = 1 - proba_pos  # Score for class 1

        prediction_sets = np.zeros((n_samples, 2), dtype=bool)
        prediction_sets[:, 0] = score_class0 <= self.threshold
        prediction_sets[:, 1] = score_class1 <= self.threshold

        # Set sizes
        set_sizes = prediction_sets.sum(axis=1)

        return point_preds, prediction_sets, set_sizes

    def predict_with_uncertainty(
        self, X: pd.DataFrame
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Predict with uncertainty indicator based on prediction set size.

        Args:
            X: Features

        Returns:
            (predictions, probabilities, is_uncertain)
            - predictions: Point predictions
            - probabilities: Probability of positive class
            - is_uncertain: Boolean, True if prediction set contains both classes
        """
        point_preds, pred_sets, set_sizes = self.predict_with_sets(X)

        # Get probabilities
        if hasattr(self.base_model, 'predict_proba'):
            proba = self.base_model.predict_proba(X)
            if proba.ndim == 2:
                proba = proba[:, 1]

        # Uncertain if both classes are in prediction set
        is_uncertain = set_sizes == 2

        return point_preds, proba, is_uncertain

    def evaluate_coverage(
        self, X_test: pd.DataFrame, y_test: pd.Series
    ) -> Dict[str, float]:
        """
        Evaluate empirical coverage on test data.

        Args:
            X_test: Test features
            y_test: True labels

        Returns:
            Dict with coverage metrics
        """
        if not self._is_calibrated:
            raise ValueError("Must calibrate before evaluating.")

        point_preds, pred_sets, set_sizes = self.predict_with_sets(X_test)

        y_array = y_test.values if hasattr(y_test, 'values') else np.array(y_test)

        # Check if true label is in prediction set
        covered = pred_sets[np.arange(len(y_array)), y_array.astype(int)]
        empirical_coverage = covered.mean()

        # Set size statistics
        avg_set_size = set_sizes.mean()
        singleton_rate = (set_sizes == 1).mean()
        empty_rate = (set_sizes == 0).mean()

        metrics = {
            'target_coverage': 1 - self.alpha,
            'empirical_coverage': empirical_coverage,
            'coverage_gap': empirical_coverage - (1 - self.alpha),
            'avg_set_size': avg_set_size,
            'singleton_rate': singleton_rate,
            'empty_rate': empty_rate,
            'uncertain_rate': 1 - singleton_rate - empty_rate,
        }

        logger.info(f"Empirical coverage: {empirical_coverage:.3f} (target: {1-self.alpha:.3f})")
        logger.info(f"Average set size: {avg_set_size:.3f}")
        logger.info(f"Uncertain predictions: {metrics['uncertain_rate']:.1%}")

        return metrics


class AdaptiveConformalPredictor(ConformalPredictor):
    """
    Adaptive conformal prediction that adjusts to distribution shift.

    Based on ICML 2024 "Adaptive Conformal Inference by Betting"
    """

    def __init__(self, base_model, alpha: float = 0.1, gamma: float = 0.01):
        """
        Initialize adaptive conformal predictor.

        Args:
            base_model: Trained classifier
            alpha: Target miscoverage rate
            gamma: Learning rate for threshold adaptation
        """
        super().__init__(base_model, alpha)
        self.gamma = gamma
        self.threshold_history = []

    def update(self, X_new: pd.DataFrame, y_new: pd.Series) -> None:
        """
        Update threshold based on new observations.

        Implements online learning for non-stationary settings.
        """
        if not self._is_calibrated:
            raise ValueError("Must calibrate before updating.")

        # Get predictions
        _, pred_sets, _ = self.predict_with_sets(X_new)

        y_array = y_new.values if hasattr(y_new, 'values') else np.array(y_new)

        # Check coverage
        covered = pred_sets[np.arange(len(y_array)), y_array.astype(int)]

        # Update threshold
        for is_covered in covered:
            if is_covered:
                # Covered: can tighten threshold
                self.threshold -= self.gamma * self.alpha
            else:
                # Not covered: must loosen threshold
                self.threshold += self.gamma * (1 - self.alpha)

            # Keep threshold in valid range
            self.threshold = np.clip(self.threshold, 0.01, 0.99)
            self.threshold_history.append(self.threshold)

        logger.info(f"Updated threshold to {self.threshold:.4f}")


def should_bet_with_conformal(
    probability: float,
    is_uncertain: bool,
    edge: float,
    min_edge: float = 0.02
) -> bool:
    """
    Decision function combining conformal uncertainty with edge.

    Only bet when:
    1. Model is confident (singleton prediction set)
    2. Edge exceeds minimum threshold

    Args:
        probability: Model probability
        is_uncertain: From conformal prediction (True if both classes in set)
        edge: Expected edge (probability * odds - 1)
        min_edge: Minimum edge to bet

    Returns:
        True if should bet
    """
    if is_uncertain:
        return False

    if edge < min_edge:
        return False

    return True
