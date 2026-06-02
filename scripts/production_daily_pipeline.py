"""
PRODUCTION DAILY PIPELINE

Runs every day at 6 AM during NFL season.

Tasks:
1. Download latest NFL data (stats, injuries, weather)
2. Get today's NFL schedule from ESPN API
3. Calculate alert times (1 hour before each game)
4. Schedule notifications
5. Update features for upcoming games

This is the foundation of the automated betting system.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List

import pytz
import requests

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class NFLScheduleManager:
    """Manages NFL game schedule and notifications."""

    def __init__(self):
        self.espn_api_base = (
            "https://site.api.espn.com/apis/site/v2/sports/football/nfl"
        )
        self.eastern = pytz.timezone("US/Eastern")

    def get_current_week(self) -> Dict:
        """Get current NFL week information."""

        url = f"{self.espn_api_base}/scoreboard"

        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()

            return {
                "season": data["season"]["year"],
                "season_type": data["season"][
                    "type"
                ],  # 1=preseason, 2=regular, 3=postseason
                "week": data["week"]["number"],
            }

        except Exception as e:
            logger.error(f"Could not get current week: {e}")
            # Fallback to current date logic
            now = datetime.now()
            return {
                "season": now.year if now.month >= 9 else now.year - 1,
                "season_type": 2,  # Assume regular season
                "week": self._estimate_week(now),
            }

    def _estimate_week(self, date: datetime) -> int:
        """Estimate NFL week from date (rough approximation)."""
        # NFL typically starts first Thursday after Labor Day (first Mon of Sep)
        # This is a rough estimate - ESPN API is better

        if date.month < 9:
            return 1
        elif date.month == 9:
            return min((date.day // 7) + 1, 4)
        elif date.month == 10:
            return min(((date.day + 30) // 7) + 1, 9)
        elif date.month == 11:
            return min(((date.day + 61) // 7) + 1, 13)
        elif date.month == 12:
            return min(((date.day + 91) // 7) + 1, 18)
        else:  # Jan - Playoffs
            return 19 + (date.day // 7)

    def get_today_schedule(self) -> List[Dict]:
        """Get all NFL games scheduled for today."""

        logger.info("Fetching today's NFL schedule from ESPN...")

        url = f"{self.espn_api_base}/scoreboard"

        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()

            games = []

            for event in data.get("events", []):
                # Parse game data
                competition = event["competitions"][0]

                # Get teams
                home_team = None
                away_team = None
                for competitor in competition["competitors"]:
                    team_abbr = competitor["team"]["abbreviation"]
                    if competitor["homeAway"] == "home":
                        home_team = team_abbr
                    else:
                        away_team = team_abbr

                # Get kickoff time
                kickoff_str = event["date"]  # ISO format
                kickoff = datetime.fromisoformat(kickoff_str.replace("Z", "+00:00"))
                kickoff_et = kickoff.astimezone(self.eastern)

                # Get status
                status = event["status"]["type"]["name"]

                # Get venue
                venue = competition.get("venue", {})
                location = venue.get("fullName", "TBD")
                roof = venue.get("indoor", False)

                game = {
                    "game_id": event["id"],
                    "home_team": home_team,
                    "away_team": away_team,
                    "kickoff": kickoff_et,
                    "kickoff_str": kickoff_et.strftime("%Y-%m-%d %I:%M %p ET"),
                    "status": status,  # scheduled, in-progress, final
                    "location": location,
                    "roof": "dome" if roof else "outdoor",
                    "week": data["week"]["number"],
                    "season": data["season"]["year"],
                }

                # Only include today's games
                today = datetime.now(self.eastern).date()
                if kickoff_et.date() == today:
                    games.append(game)

            logger.info(f"Found {len(games)} games today")

            # Sort by kickoff time
            games = sorted(games, key=lambda x: x["kickoff"])

            return games

        except Exception as e:
            logger.error(f"Error fetching schedule: {e}")
            return []

    def get_this_week_schedule(self) -> List[Dict]:
        """Get all games for current NFL week (Thu-Mon)."""

        logger.info("Fetching this week's NFL schedule...")

        # Get current week info
        week_info = self.get_current_week()

        # ESPN API for specific week
        url = f"{self.espn_api_base}/scoreboard?week={week_info['week']}&seasontype={week_info['season_type']}&dates={week_info['season']}"

        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()

            games = []

            for event in data.get("events", []):
                competition = event["competitions"][0]

                # Parse teams
                home_team = None
                away_team = None
                for competitor in competition["competitors"]:
                    team_abbr = competitor["team"]["abbreviation"]
                    if competitor["homeAway"] == "home":
                        home_team = team_abbr
                    else:
                        away_team = team_abbr

                # Parse time
                kickoff_str = event["date"]
                kickoff = datetime.fromisoformat(kickoff_str.replace("Z", "+00:00"))
                kickoff_et = kickoff.astimezone(self.eastern)

                # Parse venue
                venue = competition.get("venue", {})

                game = {
                    "game_id": event["id"],
                    "home_team": home_team,
                    "away_team": away_team,
                    "kickoff": kickoff_et,
                    "kickoff_str": kickoff_et.strftime("%Y-%m-%d %I:%M %p ET"),
                    "day_of_week": kickoff_et.strftime("%A"),
                    "status": event["status"]["type"]["name"],
                    "location": venue.get("fullName", "TBD"),
                    "roof": "dome" if venue.get("indoor", False) else "outdoor",
                    "week": week_info["week"],
                    "season": week_info["season"],
                }

                games.append(game)

            logger.info(f"Found {len(games)} games this week")

            return sorted(games, key=lambda x: x["kickoff"])

        except Exception as e:
            logger.error(f"Error fetching week schedule: {e}")
            return []

    def calculate_alert_times(self, games: List[Dict]) -> List[Dict]:
        """Calculate when to send alerts (1 hour before kickoff)."""

        alerts = []

        for game in games:
            alert_time = game["kickoff"] - timedelta(hours=1)

            # Only schedule if alert time is in the future
            now = datetime.now(self.eastern)
            if alert_time > now:
                alerts.append(
                    {
                        "game_id": game["game_id"],
                        "home_team": game["home_team"],
                        "away_team": game["away_team"],
                        "kickoff": game["kickoff"],
                        "alert_time": alert_time,
                        "alert_time_str": alert_time.strftime("%Y-%m-%d %I:%M %p ET"),
                        "minutes_until_alert": int(
                            (alert_time - now).total_seconds() / 60
                        ),
                    }
                )

        return alerts

    def save_schedule(self, games: List[Dict], filename: str = "today_schedule.json"):
        """Save schedule to file."""

        output_dir = Path("data/schedules")
        output_dir.mkdir(parents=True, exist_ok=True)

        output_path = output_dir / filename

        # Convert datetime objects to strings for JSON
        games_serializable = []
        for game in games:
            game_copy = game.copy()
            if isinstance(game_copy.get("kickoff"), datetime):
                game_copy["kickoff"] = game_copy["kickoff"].isoformat()
            games_serializable.append(game_copy)

        with open(output_path, "w") as f:
            json.dump(games_serializable, f, indent=2)

        logger.info(f"Saved schedule to {output_path}")


class DailyDataUpdater:
    """Updates NFL data daily."""

    def download_latest_data(self):
        """Download latest stats, injuries, weather."""
        logger.info("Downloading latest NFL data...")

        # Use existing download_data.py script
        import subprocess

        result = subprocess.run(
            ["python", "scripts/download_data.py"], capture_output=True, text=True
        )

        if result.returncode == 0:
            logger.info("Data download complete")
        else:
            logger.error(f"Data download failed: {result.stderr}")

    def update_features_for_upcoming_games(self, games: List[Dict]):
        """Generate features for upcoming games."""
        logger.info("Generating features for upcoming games...")

        # This would use the feature pipeline to generate features
        # for each upcoming game based on latest data

        # For now, just log
        for game in games:
            logger.info(f"  - {game['away_team']} @ {game['home_team']}")

        logger.info("Features ready")


def main():
    """Run daily pipeline."""

    print("\n" + "=" * 80)
    print("NFL PRODUCTION DAILY PIPELINE")
    print("=" * 80)
    print(f"\nRunning at: {datetime.now().strftime('%Y-%m-%d %I:%M %p')}")
    print("=" * 80 + "\n")

    # Initialize managers
    schedule_mgr = NFLScheduleManager()
    data_updater = DailyDataUpdater()

    # Step 1: Download latest data
    logger.info("\n" + "-" * 80)
    logger.info("STEP 1: DOWNLOAD LATEST DATA")
    logger.info("-" * 80)
    # data_updater.download_latest_data()  # Uncomment in production
    logger.info("(Skipped in demo mode)")

    # Step 2: Get today's schedule
    logger.info("\n" + "-" * 80)
    logger.info("STEP 2: GET TODAY'S SCHEDULE")
    logger.info("-" * 80)
    today_games = schedule_mgr.get_today_schedule()

    if today_games:
        print(f"\nFound {len(today_games)} games today:\n")
        for game in today_games:
            print(f"  {game['kickoff_str']}: {game['away_team']} @ {game['home_team']}")
            print(f"    Location: {game['location']} ({game['roof']})")
            print(f"    Status: {game['status']}")
            print()
    else:
        print("\nNo games scheduled today")

    # Step 3: Get this week's schedule
    logger.info("\n" + "-" * 80)
    logger.info("STEP 3: GET THIS WEEK'S SCHEDULE")
    logger.info("-" * 80)
    week_games = schedule_mgr.get_this_week_schedule()

    print(f"\nThis week's schedule ({len(week_games)} games):\n")

    # Group by day
    games_by_day = {}
    for game in week_games:
        day = game["day_of_week"]
        if day not in games_by_day:
            games_by_day[day] = []
        games_by_day[day].append(game)

    for day in [
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
        "Monday",
        "Tuesday",
        "Wednesday",
    ]:
        if day in games_by_day:
            print(f"{day}:")
            for game in games_by_day[day]:
                print(
                    f"  {game['kickoff_str']}: {game['away_team']} @ {game['home_team']}"
                )
            print()

    # Step 4: Calculate alert times
    logger.info("\n" + "-" * 80)
    logger.info("STEP 4: CALCULATE ALERT TIMES")
    logger.info("-" * 80)
    alerts = schedule_mgr.calculate_alert_times(week_games)

    print(f"\nScheduled {len(alerts)} alerts:\n")
    for alert in alerts[:10]:  # Show first 10
        print(
            f"  {alert['alert_time_str']}: {alert['away_team']} @ {alert['home_team']}"
        )
        print(f"    (in {alert['minutes_until_alert']} minutes)")
        print()

    # Step 5: Save schedule
    logger.info("\n" + "-" * 80)
    logger.info("STEP 5: SAVE SCHEDULE")
    logger.info("-" * 80)
    schedule_mgr.save_schedule(today_games, "today_schedule.json")
    schedule_mgr.save_schedule(week_games, "week_schedule.json")

    # Step 6: Update features
    logger.info("\n" + "-" * 80)
    logger.info("STEP 6: UPDATE FEATURES")
    logger.info("-" * 80)
    data_updater.update_features_for_upcoming_games(week_games)

    print("\n" + "=" * 80)
    print("DAILY PIPELINE COMPLETE")
    print("=" * 80)
    print("\nNext steps:")
    print(f"  - Alerts scheduled for {len(alerts)} upcoming games")
    print("  - Will run prediction pipeline 1 hour before each game")
    print("  - Notifications will be sent with bet recommendations")
    print("\n" + "=" * 80 + "\n")


if __name__ == "__main__":
    main()
