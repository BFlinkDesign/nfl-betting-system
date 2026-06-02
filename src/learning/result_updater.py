"""Result updater — closes the adaptive learning loop.

Fetches game results from ESPN and updates prediction outcomes
in the adaptive learning database.
"""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, List

logger = logging.getLogger(__name__)


class ResultUpdater:
    """Fetches final scores and updates prediction outcomes."""

    def __init__(self, db_path: str = "data/adaptive_learning.db"):
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            logger.warning("Adaptive learning DB not found at %s", self.db_path)

    def get_pending_predictions(self) -> List[Dict]:
        """Get predictions that don't have results yet."""
        if not self.db_path.exists():
            return []

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """
                SELECT prediction_id, game_id, home_team, away_team,
                       pick, bet_type, odds, timestamp
                FROM predictions
                WHERE actual_result IS NULL
                ORDER BY timestamp DESC
                LIMIT 100
                """
            ).fetchall()
        return [dict(r) for r in rows]

    def update_from_scores(
        self,
        prediction_id: str,
        home_score: int,
        away_score: int,
        pick: str,
        odds: float,
    ) -> Dict:
        """
        Update a prediction with the final score.

        Args:
            prediction_id: The prediction to update
            home_score: Final home team score
            away_score: Final away team score
            pick: Original pick ("home" or "away")
            odds: Decimal or American odds at time of bet

        Returns:
            Dict with result and profit
        """
        home_won = home_score > away_score

        if pick == "home":
            won = home_won
        elif pick == "away":
            won = not home_won
        else:
            won = False

        if home_score == away_score:
            result = "push"
            profit = 0.0
        elif won:
            result = "win"
            if odds > 0:
                profit = odds / 100.0
            else:
                profit = 100.0 / abs(odds)
        else:
            result = "loss"
            profit = -1.0

        try:
            from src.learning.adaptive_engine import get_adaptive_engine

            engine = get_adaptive_engine()
            engine.update_result(
                prediction_id=prediction_id,
                result=result,
                score_home=home_score,
                score_away=away_score,
                profit=profit,
            )
            logger.info(
                "Updated %s: %s (home=%d away=%d profit=%.2f)",
                prediction_id,
                result,
                home_score,
                away_score,
                profit,
            )
        except Exception as e:
            logger.error("Failed to update result for %s: %s", prediction_id, e)

        return {"prediction_id": prediction_id, "result": result, "profit": profit}

    def update_from_espn(self) -> List[Dict]:
        """
        Fetch completed game scores from ESPN and update all pending predictions.

        Returns:
            List of update results
        """
        pending = self.get_pending_predictions()
        if not pending:
            logger.info("No pending predictions to update")
            return []

        try:
            from agents.api_integrations import ESPNAPI

            espn = ESPNAPI()
        except ImportError:
            logger.error("Cannot import ESPNAPI for result updates")
            return []

        current_year = datetime.now().year
        scoreboard = espn.get_scoreboard(current_year)

        completed_games: Dict[str, Dict] = {}
        for event in scoreboard.get("events", []):
            status = event.get("status", {}).get("type", {}).get("name", "")
            if status != "STATUS_FINAL":
                continue

            competition = event.get("competitions", [{}])[0]
            competitors = competition.get("competitors", [])

            home = next((c for c in competitors if c.get("homeAway") == "home"), {})
            away = next((c for c in competitors if c.get("homeAway") == "away"), {})

            home_name = home.get("team", {}).get("displayName", "")
            away_name = away.get("team", {}).get("displayName", "")
            home_score = int(home.get("score", 0))
            away_score = int(away.get("score", 0))

            key = f"{away_name}@{home_name}"
            completed_games[key] = {
                "home_score": home_score,
                "away_score": away_score,
            }

        results = []
        for pred in pending:
            key = f"{pred['away_team']}@{pred['home_team']}"
            if key in completed_games:
                scores = completed_games[key]
                r = self.update_from_scores(
                    prediction_id=pred["prediction_id"],
                    home_score=scores["home_score"],
                    away_score=scores["away_score"],
                    pick=pred["pick"],
                    odds=pred["odds"],
                )
                results.append(r)

        logger.info(
            "Updated %d/%d pending predictions from ESPN",
            len(results),
            len(pending),
        )
        return results
