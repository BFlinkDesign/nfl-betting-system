"""Market-derived features.

Captures line movement, implied probability gap, and market efficiency
signals from betting odds data.
"""

import logging
from typing import List

import numpy as np
import pandas as pd

from .base import FeatureBuilder

logger = logging.getLogger(__name__)


class MarketFeatures(FeatureBuilder):
    """
    Market-derived features from betting odds.

    Creates:
    - market_implied_prob: implied probability from spread_line
    - model_vs_market_gap: difference between model prob and market implied prob
    - line_movement_abs: absolute value of line movement
    - total_movement_abs: absolute value of total movement
    - sharp_indicator: binary flag for significant reverse line movement
    """

    def get_required_columns(self) -> List[str]:
        return ["game_id"]

    def build(self, df: pd.DataFrame) -> pd.DataFrame:
        logger.info("Building market features...")
        df = df.copy()

        if "spread_line" in df.columns:
            spread = df["spread_line"].fillna(0).values
            df["market_implied_prob"] = np.clip(0.50 - spread * 0.03, 0.10, 0.90)
        else:
            df["market_implied_prob"] = 0.50

        if "line_movement" in df.columns:
            df["line_movement_abs"] = df["line_movement"].fillna(0).abs()
            spread_now = df.get("spread_line", pd.Series(0, index=df.index)).fillna(0)
            opening = spread_now - df["line_movement"].fillna(0)
            df["sharp_indicator"] = (
                (opening < 0) & (df["line_movement"].fillna(0) > 0.5)
            ).astype(int) | (
                (opening > 0) & (df["line_movement"].fillna(0) < -0.5)
            ).astype(
                int
            )
        else:
            df["line_movement_abs"] = 0.0
            df["sharp_indicator"] = 0

        if "total_movement" in df.columns:
            df["total_movement_abs"] = df["total_movement"].fillna(0).abs()
        else:
            df["total_movement_abs"] = 0.0

        df["model_vs_market_gap"] = 0.0

        logger.info(
            "Market features created: %d features", len(self.get_feature_names())
        )
        return df

    def get_feature_names(self) -> List[str]:
        return [
            "market_implied_prob",
            "model_vs_market_gap",
            "line_movement_abs",
            "total_movement_abs",
            "sharp_indicator",
        ]
