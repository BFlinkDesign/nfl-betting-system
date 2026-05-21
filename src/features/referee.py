"""Referee and officiating crew features.

Adds features related to referee statistics and tendencies,
using play-by-play penalty data when available.
"""

import logging
from typing import List, Optional

import numpy as np
import pandas as pd

from .base import FeatureBuilder

logger = logging.getLogger(__name__)


class RefereeFeatures(FeatureBuilder):
    """
    Referee and officiating crew features derived from historical data.

    Creates:
    - referee_home_win_rate: Historical home team win rate with this referee
    - referee_penalty_rate: Average penalties per game (from PBP if available)
    - referee_home_penalty_rate: Fraction of penalties called on the home team
    """

    def __init__(self, pbp_data: Optional[pd.DataFrame] = None):
        self.pbp_data = pbp_data
        self._penalty_cache: Optional[pd.DataFrame] = None

    def get_required_columns(self) -> List[str]:
        return ["referee", "game_id", "home_team", "result"]

    def build(self, df: pd.DataFrame) -> pd.DataFrame:
        """Build referee features."""
        missing = [col for col in self.get_required_columns() if col not in df.columns]
        if missing:
            logger.warning(
                "Missing columns for referee features: %s, using defaults", missing
            )
            for col in self.get_feature_names():
                df[col] = 0.0
            return df

        logger.info("Building referee features...")

        if self.pbp_data is not None and len(self.pbp_data) > 0:
            self._penalty_cache = self._build_penalty_stats_from_pbp()

        referee_stats = self._calculate_referee_stats(df)

        df = df.merge(referee_stats, on="game_id", how="left", suffixes=("", "_ref"))

        for col in self.get_feature_names():
            df[col] = df[col].fillna(0.5)

        logger.info(
            "Referee features created: %d features", len(self.get_feature_names())
        )

        return df

    def _build_penalty_stats_from_pbp(self) -> pd.DataFrame:
        """Aggregate penalty counts per game from play-by-play data."""
        pbp = self.pbp_data
        required = {"game_id", "penalty", "penalty_team", "posteam"}
        if not required.issubset(set(pbp.columns)):
            logger.warning("PBP data missing penalty columns, skipping penalty stats")
            return pd.DataFrame()

        penalties = pbp[pbp["penalty"] == 1].copy()
        if len(penalties) == 0:
            return pd.DataFrame()

        game_stats = (
            penalties.groupby("game_id")
            .agg(total_penalties=("penalty", "sum"))
            .reset_index()
        )

        if "home_team" in pbp.columns:
            home_penalties = (
                penalties[penalties["penalty_team"] == penalties.get("home_team")]
                .groupby("game_id")
                .agg(home_penalties=("penalty", "sum"))
                .reset_index()
            )
            game_stats = game_stats.merge(home_penalties, on="game_id", how="left")
            game_stats["home_penalties"] = game_stats["home_penalties"].fillna(0)
        else:
            game_stats["home_penalties"] = game_stats["total_penalties"] / 2

        return game_stats

    def _calculate_referee_stats(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate historical referee statistics.
        Uses only PAST games to avoid temporal leakage.
        """
        df = df.sort_values(["season", "gameday"]).copy()
        df["gameday"] = pd.to_datetime(df["gameday"])

        if self._penalty_cache is not None and len(self._penalty_cache) > 0:
            df = df.merge(self._penalty_cache, on="game_id", how="left")
        else:
            df["total_penalties"] = np.nan
            df["home_penalties"] = np.nan

        stats_list = []
        for _, game in df.iterrows():
            referee = game["referee"]
            if pd.isna(referee):
                stats_list.append(
                    {
                        "game_id": game["game_id"],
                        "referee_home_win_rate": 0.5,
                        "referee_penalty_rate": 0.5,
                        "referee_home_penalty_rate": 0.5,
                    }
                )
                continue

            past = df[(df["gameday"] < game["gameday"]) & (df["referee"] == referee)]

            if len(past) > 0:
                home_win_rate = float((past["result"] > 0).mean())

                if past["total_penalties"].notna().any():
                    valid = past.dropna(subset=["total_penalties"])
                    avg_pen = float(valid["total_penalties"].mean())
                    penalty_rate = min(avg_pen / 20.0, 1.0)

                    home_pen = float(valid["home_penalties"].mean())
                    total_pen = float(valid["total_penalties"].mean())
                    home_penalty_rate = home_pen / total_pen if total_pen > 0 else 0.5
                else:
                    penalty_rate = 0.5
                    home_penalty_rate = 0.5
            else:
                home_win_rate = 0.5
                penalty_rate = 0.5
                home_penalty_rate = 0.5

            stats_list.append(
                {
                    "game_id": game["game_id"],
                    "referee_home_win_rate": round(home_win_rate, 4),
                    "referee_penalty_rate": round(penalty_rate, 4),
                    "referee_home_penalty_rate": round(home_penalty_rate, 4),
                }
            )

        result = pd.DataFrame(stats_list)

        df.drop(
            columns=["total_penalties", "home_penalties"], errors="ignore", inplace=True
        )

        return result

    def get_feature_names(self) -> List[str]:
        return [
            "referee_home_win_rate",
            "referee_penalty_rate",
            "referee_home_penalty_rate",
        ]
