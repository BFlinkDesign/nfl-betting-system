"""Probability calibration for NFL prediction models."""

import logging
from pathlib import Path
from typing import Dict, Optional

import joblib
import matplotlib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV, calibration_curve
from sklearn.metrics import brier_score_loss

matplotlib.use("Agg")
import matplotlib.pyplot as plt

logger = logging.getLogger(__name__)


class ModelCalibrator:
    """Wraps a trained model with probability calibration (Platt scaling / isotonic)."""

    def __init__(
        self,
        model,
        method: str = "sigmoid",
        cv: str = "prefit",
    ):
        self.base_model = model
        self.method = method
        self.cv = cv
        self.calibrated_model: Optional[CalibratedClassifierCV] = None

    def _get_estimator(self):
        """Extract the sklearn-compatible estimator from the wrapper."""
        if hasattr(self.base_model, "model"):
            return self.base_model.model
        return self.base_model

    def calibrate(self, X_val: pd.DataFrame, y_val: pd.Series) -> None:
        estimator = self._get_estimator()
        if self.cv == "prefit":
            try:
                from sklearn.frozen import FrozenEstimator

                self.calibrated_model = CalibratedClassifierCV(
                    FrozenEstimator(estimator),
                    method=self.method,
                )
            except ImportError:
                self.calibrated_model = CalibratedClassifierCV(
                    estimator,
                    method=self.method,
                    cv="prefit",
                )
        else:
            self.calibrated_model = CalibratedClassifierCV(
                estimator,
                method=self.method,
                cv=int(self.cv) if str(self.cv).isdigit() else 5,
            )
        self.calibrated_model.fit(X_val, y_val)
        logger.info("Calibration complete (method=%s)", self.method)

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        if self.calibrated_model is not None:
            return self.calibrated_model.predict_proba(X)
        return self._get_estimator().predict_proba(X)

    def evaluate_calibration(
        self, X_test: pd.DataFrame, y_test: pd.Series
    ) -> Dict[str, float]:
        raw_proba = self._get_estimator().predict_proba(X_test)[:, 1]
        brier_raw = float(brier_score_loss(y_test, raw_proba))

        if self.calibrated_model is not None:
            cal_proba = self.calibrated_model.predict_proba(X_test)[:, 1]
            brier_cal = float(brier_score_loss(y_test, cal_proba))
        else:
            brier_cal = brier_raw

        improvement = (
            ((brier_raw - brier_cal) / brier_raw * 100) if brier_raw > 0 else 0.0
        )

        return {
            "brier_uncalibrated": brier_raw,
            "brier_calibrated": brier_cal,
            "improvement_pct": improvement,
        }

    def plot_calibration_curve(
        self,
        X_test: pd.DataFrame,
        y_test: pd.Series,
        save_path: Optional[str] = None,
        n_bins: int = 10,
    ) -> None:
        raw_proba = self._get_estimator().predict_proba(X_test)[:, 1]

        fig, axes = plt.subplots(1, 2, figsize=(12, 5))

        fraction_pos, mean_pred = calibration_curve(y_test, raw_proba, n_bins=n_bins)
        axes[0].plot(mean_pred, fraction_pos, "s-", label="Uncalibrated")
        axes[0].plot([0, 1], [0, 1], "k--", label="Perfect")
        axes[0].set_title("Uncalibrated")
        axes[0].set_xlabel("Mean predicted probability")
        axes[0].set_ylabel("Fraction of positives")
        axes[0].legend()

        if self.calibrated_model is not None:
            cal_proba = self.calibrated_model.predict_proba(X_test)[:, 1]
            frac_cal, mean_cal = calibration_curve(y_test, cal_proba, n_bins=n_bins)
            axes[1].plot(mean_cal, frac_cal, "s-", label="Calibrated", color="green")
        axes[1].plot([0, 1], [0, 1], "k--", label="Perfect")
        axes[1].set_title("Calibrated")
        axes[1].set_xlabel("Mean predicted probability")
        axes[1].set_ylabel("Fraction of positives")
        axes[1].legend()

        plt.tight_layout()

        if save_path:
            Path(save_path).parent.mkdir(parents=True, exist_ok=True)
            plt.savefig(save_path, dpi=150)
            logger.info("Calibration curve saved to %s", save_path)
        plt.close(fig)

    def save(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)

    @classmethod
    def load(cls, path: str) -> "ModelCalibrator":
        return joblib.load(path)
