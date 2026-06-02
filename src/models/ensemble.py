"""Ensemble model combining multiple predictors."""

import logging
from pathlib import Path
from typing import Dict, List, Optional

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss, roc_auc_score

from .base import NFLModel

logger = logging.getLogger(__name__)


class EnsembleModel(NFLModel):
    """Weighted ensemble of heterogeneous models."""

    def __init__(
        self,
        models: Optional[List] = None,
        weights: Optional[List[float]] = None,
        method: str = "weighted_average",
    ):
        self.models = models or []
        self.weights = weights or [1.0 / max(len(self.models), 1)] * max(
            len(self.models), 1
        )
        self.method = method
        self.feature_names: list = []

    def train(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: pd.DataFrame = None,
        y_val: pd.Series = None,
    ) -> None:
        self.fit(X_train, y_train)

    def fit(self, X_train: pd.DataFrame, y_train: pd.Series) -> None:
        self.feature_names = list(X_train.columns)
        for i, m in enumerate(self.models):
            if not self._is_fitted(m):
                logger.info("Fitting ensemble member %d", i)
                if hasattr(m, "fit"):
                    m.fit(X_train, y_train)
                elif hasattr(m, "train"):
                    m.train(X_train, y_train)
        logger.info(
            "Ensemble ready with %d models, weights=%s", len(self.models), self.weights
        )

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        if not self.models:
            raise ValueError("No models in ensemble")

        probas = []
        for m in self.models:
            p = self._get_proba(m, X)
            probas.append(p)

        weighted = np.zeros_like(probas[0])
        for p, w in zip(probas, self.weights):
            weighted += p * w

        return weighted

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        proba = self.predict_proba(X)
        if proba.ndim == 2:
            return (proba[:, 1] >= 0.5).astype(int)
        return (proba >= 0.5).astype(int)

    def evaluate(self, X: pd.DataFrame, y: pd.Series) -> Dict[str, float]:
        proba = self.predict_proba(X)
        p1 = proba[:, 1] if proba.ndim == 2 else proba
        preds = (p1 >= 0.5).astype(int)

        return {
            "accuracy": float(accuracy_score(y, preds)),
            "brier_score": float(brier_score_loss(y, p1)),
            "log_loss": float(log_loss(y, p1)),
            "roc_auc": float(roc_auc_score(y, p1)),
        }

    def get_feature_importance(self) -> Dict[str, float]:
        combined: Dict[str, float] = {}
        for m, w in zip(self.models, self.weights):
            imp = {}
            if hasattr(m, "get_feature_importance"):
                imp = m.get_feature_importance()
            elif hasattr(m, "feature_importances_"):
                names = getattr(m, "feature_names_in_", self.feature_names) or []
                imp = dict(zip(names, map(float, m.feature_importances_)))
            for name, val in imp.items():
                combined[name] = combined.get(name, 0.0) + val * w
        return combined

    def save(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)
        logger.info("Ensemble saved to %s", path)

    @classmethod
    def load(cls, path: str) -> "EnsembleModel":
        return joblib.load(path)

    @staticmethod
    def _is_fitted(model) -> bool:
        try:
            if hasattr(model, "feature_importances_"):
                return True
            if hasattr(model, "model") and hasattr(model.model, "feature_importances_"):
                return True
            if hasattr(model, "classes_"):
                return True
        except Exception:
            pass
        return False

    @staticmethod
    def _get_proba(model, X: pd.DataFrame) -> np.ndarray:
        if hasattr(model, "predict_proba"):
            return model.predict_proba(X)
        p = model.predict(X)
        if p.ndim == 1:
            return np.column_stack([1 - p, p])
        return p
