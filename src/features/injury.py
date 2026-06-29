"""Injury and roster features with position-based weighting.

Adds features related to team injuries and roster changes,
weighted by positional impact (QB injuries matter more than K injuries).
"""

import logging
from typing import Dict, List, Optional

import pandas as pd

from .base import FeatureBuilder

logger = logging.getLogger(__name__)

POSITION_WEIGHTS: Dict[str, float] = {
    "QB": 1.0,
    "LT": 0.55,
    "RT": 0.50,
    "C": 0.45,
    "LG": 0.40,
    "RG": 0.40,
    "WR": 0.45,
    "TE": 0.35,
    "RB": 0.40,
    "CB": 0.40,
    "EDGE": 0.40,
    "DE": 0.38,
    "DT": 0.30,
    "LB": 0.30,
    "ILB": 0.30,
    "OLB": 0.30,
    "S": 0.28,
    "SS": 0.28,
    "FS": 0.28,
    "K": 0.15,
    "P": 0.10,
    "LS": 0.05,
}


class InjuryFeatures(FeatureBuilder):
    """
    Position-weighted injury features from nflverse data.

    Creates:
    - injury_count_home/away: raw injury count (last 2 weeks)
    - roster_changes_home/away: roster change count
    - injury_impact_home/away: position-weighted injury severity score
    """

    def __init__(self, injury_data: Optional[pd.DataFrame] = None):
        """
        Initialize injury features.

        Args:
            injury_data: Injury DataFrame from nflverse
        """
        self.injury_data = injury_data

    def get_required_columns(self) -> List[str]:
        return ["game_id", "gameday", "season", "week", "home_team", "away_team"]

    def build(self, df: pd.DataFrame) -> pd.DataFrame:
        """Build injury features."""
        if self.injury_data is None or len(self.injury_data) == 0:
            logger.warning("No injury data provided, skipping injury features")
            df["injury_count_home"] = 0
            df["injury_count_away"] = 0
            df["roster_changes_home"] = 0
            df["roster_changes_away"] = 0
            df["injury_impact_home"] = 0.0
            df["injury_impact_away"] = 0.0
            return df

        logger.info("Building injury features...")

        # Ensure datetime
        df["gameday"] = pd.to_datetime(df["gameday"])
        df = df.sort_values(["season", "gameday"]).copy()

        # Process injury data
        injury_metrics = self._calculate_injury_metrics(df)

        # Merge home team injuries
        df = df.merge(
            injury_metrics,
            left_on=["game_id", "home_team"],
            right_on=["game_id", "team"],
            how="left",
            suffixes=("", "_home"),
        )
        df["injury_count_home"] = df["injury_count"].fillna(0)
        df["roster_changes_home"] = df["roster_changes"].fillna(0)
        df["injury_impact_home"] = df["injury_impact"].fillna(0.0)
        df = df.drop(
            columns=["team", "injury_count", "roster_changes", "injury_impact"],
            errors="ignore",
        )

        df = df.merge(
            injury_metrics,
            left_on=["game_id", "away_team"],
            right_on=["game_id", "team"],
            how="left",
            suffixes=("", "_away"),
        )
        df["injury_count_away"] = df["injury_count"].fillna(0)
        df["roster_changes_away"] = df["roster_changes"].fillna(0)
        df["injury_impact_away"] = df["injury_impact"].fillna(0.0)
        df = df.drop(
            columns=["team", "injury_count", "roster_changes", "injury_impact"],
            errors="ignore",
        )

        logger.info(
            f"✓ Injury features created: {len(self.get_feature_names())} features"
        )

        return df

    def _calculate_injury_metrics(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate injury metrics per game."""
        injuries = self.injury_data.copy()

        # Ensure date columns are datetime
        if "report_date" in injuries.columns:
            injuries["report_date"] = pd.to_datetime(
                injuries["report_date"], errors="coerce"
            )
        elif "date" in injuries.columns:
            injuries["report_date"] = pd.to_datetime(injuries["date"], errors="coerce")
        else:
            logger.warning(
                "No date column in injury data, using season-based approximation"
            )
            # Create approximate dates from season
            injuries["report_date"] = pd.to_datetime(
                injuries["season"].astype(int).astype(str) + "-09-01", errors="coerce"
            )

        # Filter to last 2 weeks before each game
        metrics_list = []
        for _, game in df.iterrows():
            game_date = pd.to_datetime(game["gameday"])
            cutoff_date = game_date - pd.Timedelta(days=14)

            # Get injuries in the 2 weeks before this game (or same season if no dates)
            if injuries["report_date"].notna().any():
                recent_injuries = injuries[
                    (injuries["report_date"] >= cutoff_date)
                    & (injuries["report_date"] < game_date)
                    & (injuries["season"] == game["season"])
                ]
            else:
                # Fallback: use same season but filter by week if available
                if "week" in injuries.columns and "week" in game:
                    # Only use injuries from weeks before this game
                    recent_injuries = injuries[
                        (injuries["season"] == game["season"])
                        & (injuries["week"] < game["week"])
                    ]
                else:
                    # Last resort: use same season (could leak future, but better than nothing)
                    logger.warning(
                        f"No date/week info for injuries, using entire season {game['season']} (potential future leakage)"
                    )
                    recent_injuries = injuries[injuries["season"] == game["season"]]

            for team in [game["home_team"], game["away_team"]]:
                team_injuries = recent_injuries[recent_injuries["team"] == team]
                count = len(team_injuries)

                impact = 0.0
                if "position" in team_injuries.columns:
                    for _, inj in team_injuries.iterrows():
                        pos = str(inj.get("position", "")).upper().strip()
                        impact += POSITION_WEIGHTS.get(pos, 0.20)
                else:
                    impact = count * 0.20

                roster_changes = (
                    len(team_injuries)
                    if "practice_status" in team_injuries.columns
                    else 0
                )

                metrics_list.append(
                    {
                        "game_id": game["game_id"],
                        "team": team,
                        "injury_count": count,
                        "roster_changes": roster_changes,
                        "injury_impact": round(impact, 3),
                    }
                )

        return pd.DataFrame(metrics_list)

    def get_feature_names(self) -> List[str]:
        return [
            "injury_count_home",
            "injury_count_away",
            "roster_changes_home",
            "roster_changes_away",
            "injury_impact_home",
            "injury_impact_away",
        ]
