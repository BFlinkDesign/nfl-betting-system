"""Strength-of-schedule features.

Computes opponent-adjusted strength metrics using only past data
to avoid temporal leakage.
"""

import logging
from typing import List

import numpy as np
import pandas as pd

from .base import FeatureBuilder

logger = logging.getLogger(__name__)


class StrengthOfScheduleFeatures(FeatureBuilder):
    """
    Strength-of-schedule features.

    Creates:
    - sos_home: average win-rate of past opponents (home team)
    - sos_away: average win-rate of past opponents (away team)
    - sos_diff: sos_home - sos_away
    """

    def __init__(self, window: int = 8):
        self.window = window

    def get_required_columns(self) -> List[str]:
        return ["game_id", "gameday", "season", "home_team", "away_team"]

    def build(self, df: pd.DataFrame) -> pd.DataFrame:
        logger.info("Building strength-of-schedule features (window=%d)...", self.window)

        df = df.copy()
        df["gameday"] = pd.to_datetime(df["gameday"])
        df = df.sort_values(["season", "gameday"]).reset_index(drop=True)

        has_scores = "home_score" in df.columns and "away_score" in df.columns
        if has_scores:
            df["_home_win"] = (df["home_score"] > df["away_score"]).astype(int)
        elif "result" in df.columns:
            df["_home_win"] = (df["result"] > 0).astype(int)
        else:
            logger.warning("No score/result columns — SOS features zeroed out")
            df["sos_home"] = 0.0
            df["sos_away"] = 0.0
            df["sos_diff"] = 0.0
            return df

        team_records: dict = {}

        sos_home_vals = np.zeros(len(df))
        sos_away_vals = np.zeros(len(df))

        for i, row in df.iterrows():
            ht, at = row["home_team"], row["away_team"]

            sos_home_vals[i] = self._opponent_avg_wr(ht, team_records)
            sos_away_vals[i] = self._opponent_avg_wr(at, team_records)

            home_won = row["_home_win"]
            self._record_game(team_records, ht, at, home_won)

        df["sos_home"] = np.round(sos_home_vals, 4)
        df["sos_away"] = np.round(sos_away_vals, 4)
        df["sos_diff"] = np.round(sos_home_vals - sos_away_vals, 4)
        df.drop(columns=["_home_win"], inplace=True, errors="ignore")

        logger.info("SOS features created: %d features", len(self.get_feature_names()))
        return df

    def _record_game(self, records: dict, home: str, away: str, home_won: int):
        for team in (home, away):
            if team not in records:
                records[team] = {"wins": 0, "games": 0, "opponents": []}

        records[home]["games"] += 1
        records[away]["games"] += 1
        records[home]["opponents"].append(away)
        records[away]["opponents"].append(home)

        if home_won:
            records[home]["wins"] += 1
        else:
            records[away]["wins"] += 1

    def _opponent_avg_wr(self, team: str, records: dict) -> float:
        if team not in records or not records[team]["opponents"]:
            return 0.5

        opponents = records[team]["opponents"][-self.window :]
        win_rates = []
        for opp in opponents:
            if opp in records and records[opp]["games"] > 0:
                win_rates.append(records[opp]["wins"] / records[opp]["games"])
        return float(np.mean(win_rates)) if win_rates else 0.5

    def get_feature_names(self) -> List[str]:
        return ["sos_home", "sos_away", "sos_diff"]
