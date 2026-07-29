"""LightGBM model wrapper for NFL predictions."""

import logging
from pathlib import Path
from typing import Any, Dict, Optional

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss, roc_auc_score

from .base import NFLModel

logger = logging.getLogger(__name__)


class LightGBMModel(NFLModel):
    """LightGBM classifier for fast inference and ensemble diversity."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        import lightgbm as lgb

        config = config or {}
        params = config.get("params", config)

        self.model = lgb.LGBMClassifier(
            n_estimators=params.get("n_estimators", 200),
            max_depth=params.get("max_depth", 6),
            learning_rate=params.get("learning_rate", 0.05),
            subsample=params.get("subsample", 0.8),
            colsample_bytree=params.get("colsample_bytree", 0.8),
            min_child_samples=params.get("min_child_samples", 20),
            reg_alpha=params.get("reg_alpha", 0.0),
            reg_lambda=params.get("reg_lambda", 1.0),
            random_state=params.get("random_state", 42),
            verbose=-1,
        )
        self.feature_names: list = []

    def train(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: pd.DataFrame = None,
        y_val: pd.Series = None,
    ) -> None:
        self.fit(X_train, y_train, X_val, y_val)

    def fit(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: pd.DataFrame = None,
        y_val: pd.Series = None,
    ) -> None:
        self.feature_names = list(X_train.columns)

        fit_params: Dict[str, Any] = {}
        if X_val is not None and y_val is not None:
            fit_params["eval_set"] = [(X_val, y_val)]
            fit_params["eval_metric"] = "logloss"

        self.model.fit(X_train, y_train, **fit_params)
        logger.info(
            "LightGBM trained on %d samples with %d features",
            len(X_train),
            len(self.feature_names),
        )

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        return self.model.predict_proba(X)

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        return self.model.predict(X)

    def evaluate(self, X: pd.DataFrame, y: pd.Series) -> Dict[str, float]:
        proba = self.predict_proba(X)[:, 1]
        preds = (proba >= 0.5).astype(int)

        return {
            "accuracy": float(accuracy_score(y, preds)),
            "brier_score": float(brier_score_loss(y, proba)),
            "log_loss": float(log_loss(y, proba)),
            "roc_auc": float(roc_auc_score(y, proba)),
        }

    def get_feature_importance(self) -> Dict[str, float]:
        importances = self.model.feature_importances_
        names = self.feature_names or [f"f{i}" for i in range(len(importances))]
        return dict(zip(names, map(float, importances)))

    def save(self, path: str) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)
        logger.info("LightGBM model saved to %s", path)

    @classmethod
    def load(cls, path: str) -> "LightGBMModel":
        return joblib.load(path)
