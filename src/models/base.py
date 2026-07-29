"""Abstract base class for NFL prediction models."""

from abc import ABC, abstractmethod
from typing import Dict

import numpy as np
import pandas as pd


class NFLModel(ABC):
    """Abstract base for all NFL prediction models."""

    @abstractmethod
    def train(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
        X_val: pd.DataFrame = None,
        y_val: pd.Series = None,
    ) -> None:
        """Train the model."""

    @abstractmethod
    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """Return probability predictions as (n_samples, 2) array."""

    @abstractmethod
    def evaluate(self, X: pd.DataFrame, y: pd.Series) -> Dict[str, float]:
        """Evaluate model and return metrics dict."""

    @abstractmethod
    def get_feature_importance(self) -> Dict[str, float]:
        """Return feature name -> importance mapping."""

    @abstractmethod
    def save(self, path: str) -> None:
        """Persist model to disk."""

    @classmethod
    @abstractmethod
    def load(cls, path: str) -> "NFLModel":
        """Load model from disk."""
