#!/usr/bin/env python3
"""Track line movement over time to detect sharp money."""

import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.api_integrations import TheOddsAPI

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LineMovementTracker:
    """Track betting line movements to detect sharp money."""

    def __init__(self):
        self.odds_api = TheOddsAPI()
        self.history_file = Path("reports/line_movement_history.json")
        self.history = self._load_history()

    def _load_history(self) -> Dict:
        """Load historical line data."""
        if self.history_file.exists():
            with open(self.history_file) as f:
                return json.load(f)
        return {}

    def _save_history(self):
        """Save historical line data."""
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.history_file, "w") as f:
            json.dump(self.history, f, indent=2)

    def update_lines(self) -> Dict:
        """Fetch current lines and compare to history."""
        logger.info("Fetching current odds...")
        games = self.odds_api.get_nfl_odds()

        if not games:
            logger.error("No games available")
            return {}

        movements = {}
        current_time = datetime.now().isoformat()

        for game in games:
            game_id = f"{game['home_team']} vs {game['away_team']}"

            # Extract current lines
            current_lines = self._extract_lines(game)

            # Compare to history
            if game_id in self.history:
                old_lines = self.history[game_id].get("lines", [])
                if old_lines:
                    latest_old = old_lines[-1]
                    movement = self._calculate_movement(latest_old, current_lines)

                    if movement["significant"]:
                        movements[game_id] = movement
                        logger.info(f"Significant movement detected: {game_id}")
                        logger.info(f"  Spread: {movement.get('spread_change', 'N/A')}")
                        logger.info(f"  Total: {movement.get('total_change', 'N/A')}")

            # Update history
            if game_id not in self.history:
                self.history[game_id] = {"lines": []}

            self.history[game_id]["lines"].append(
                {"timestamp": current_time, "lines": current_lines}
            )

            # Keep only last 24 hours
            cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
            self.history[game_id]["lines"] = [
                l for l in self.history[game_id]["lines"] if l["timestamp"] > cutoff
            ]

        self._save_history()
        return movements

    def _extract_lines(self, game: Dict) -> Dict:
        """Extract lines from game data."""
        lines = {"spread": {}, "total": {}, "moneyline": {}}

        for bookmaker in game.get("bookmakers", []):
            for market in bookmaker.get("markets", []):
                if market["key"] == "spreads":
                    for outcome in market["outcomes"]:
                        team = outcome["name"]
                        point = outcome.get("point", 0)
                        if team not in lines["spread"]:
                            lines["spread"][team] = []
                        lines["spread"][team].append(
                            {
                                "point": point,
                                "price": outcome.get("price", 0),
                                "book": bookmaker["title"],
                            }
                        )

                elif market["key"] == "totals":
                    for outcome in market["outcomes"]:
                        point = outcome.get("point", 0)
                        if "total" not in lines["total"]:
                            lines["total"]["total"] = []
                        lines["total"]["total"].append(
                            {
                                "point": point,
                                "price": outcome.get("price", 0),
                                "book": bookmaker["title"],
                            }
                        )

        return lines

    def _calculate_movement(self, old_lines: Dict, new_lines: Dict) -> Dict:
        """Calculate line movement between two snapshots."""
        movement = {
            "significant": False,
            "spread_change": None,
            "total_change": None,
            "sharp_indicator": False,
        }

        # Check spread movement
        if old_lines.get("spread") and new_lines.get("spread"):
            old_spreads = {}
            new_spreads = {}

            for team, lines in old_lines["spread"].items():
                if lines:
                    old_spreads[team] = lines[0]["point"]

            for team, lines in new_lines["spread"].items():
                if lines:
                    new_spreads[team] = lines[0]["point"]

            # Calculate change
            for team in set(old_spreads.keys()) & set(new_spreads.keys()):
                change = new_spreads[team] - old_spreads[team]
                if abs(change) >= 1.0:  # Significant movement
                    movement["significant"] = True
                    movement["spread_change"] = (
                        f"{team}: {old_spreads[team]} → {new_spreads[team]} ({change:+.1f})"
                    )

        # Check total movement
        if old_lines.get("total") and new_lines.get("total"):
            old_total = old_lines["total"].get("total", [{}])[0].get("point", 0)
            new_total = new_lines["total"].get("total", [{}])[0].get("point", 0)

            if old_total and new_total:
                change = new_total - old_total
                if abs(change) >= 1.0:  # Significant movement
                    movement["significant"] = True
                    movement["total_change"] = (
                        f"{old_total} → {new_total} ({change:+.1f})"
                    )

        # Sharp money indicator: Line moves against public betting
        # (This would require public betting % data, simplified here)
        if movement["significant"]:
            movement["sharp_indicator"] = True

        return movement

    def get_alerts(self) -> List[Dict]:
        """Get alerts for significant line movements."""
        movements = self.update_lines()

        alerts = []
        for game_id, movement in movements.items():
            alerts.append(
                {
                    "game": game_id,
                    "spread_change": movement.get("spread_change"),
                    "total_change": movement.get("total_change"),
                    "sharp_indicator": movement.get("sharp_indicator"),
                    "timestamp": datetime.now().isoformat(),
                }
            )

        return alerts


def main():
    """Track line movements and generate alerts."""
    logger.info("=" * 70)
    logger.info("LINE MOVEMENT TRACKER")
    logger.info("=" * 70)

    tracker = LineMovementTracker()
    alerts = tracker.get_alerts()

    if alerts:
        logger.info(f"\nFound {len(alerts)} significant movements:")
        for alert in alerts:
            logger.info(f"\n{alert['game']}:")
            if alert["spread_change"]:
                logger.info(f"  Spread: {alert['spread_change']}")
            if alert["total_change"]:
                logger.info(f"  Total: {alert['total_change']}")
            if alert["sharp_indicator"]:
                logger.info("  ⚠️  SHARP MONEY DETECTED")
    else:
        logger.info("\nNo significant line movements detected")

    return 0


if __name__ == "__main__":
    sys.exit(main())
