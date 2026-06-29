"""
Full NFL Betting Pipeline Orchestration

Runs the complete automated betting system:
1. Fetches today's NFL schedule
2. Calculates alert times (1 hour before each game)
3. Waits until alert time
4. Runs pre-game prediction engine
5. Generates smart parlays
6. Sends notifications via email/SMS/desktop
7. Logs all activity
8. Repeats for next game

Usage:
    python scripts/full_betting_pipeline.py
    python scripts/full_betting_pipeline.py --test --date 2025-11-24
    python scripts/full_betting_pipeline.py --dry-run
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import argparse
import json
import logging
import subprocess
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pytz

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


class NFLScheduleManager:
    """Manages NFL game schedule fetching."""

    def __init__(self):
        self.eastern = pytz.timezone("US/Eastern")

    def get_today_schedule(self) -> List[Dict]:
        """
        Get today's NFL games.

        Returns:
            List of game dictionaries with kickoff times
        """
        try:
            import nflreadpy as nfl

            # Get current season
            now = datetime.now()
            season = now.year if now.month >= 9 else now.year - 1

            # Load schedule
            schedule = nfl.import_schedules([season])

            # Filter for today's games
            today_str = now.strftime("%Y-%m-%d")
            today_games = schedule[schedule["gameday"] == today_str].to_dict("records")

            logger.info(f"Found {len(today_games)} games scheduled for today")
            return today_games

        except Exception as e:
            logger.error(f"Error fetching schedule: {e}")
            return []

    def get_games_by_date(self, date_str: str) -> List[Dict]:
        """
        Get games for specific date.

        Args:
            date_str: Date in YYYY-MM-DD format

        Returns:
            List of game dictionaries
        """
        try:
            import nflreadpy as nfl

            # Determine season from date
            date = datetime.strptime(date_str, "%Y-%m-%d")
            season = date.year if date.month >= 9 else date.year - 1

            # Load schedule
            schedule = nfl.import_schedules([season])

            # Filter for specific date
            games = schedule[schedule["gameday"] == date_str].to_dict("records")

            logger.info(f"Found {len(games)} games scheduled for {date_str}")
            return games

        except Exception as e:
            logger.error(f"Error fetching schedule: {e}")
            return []

    def parse_kickoff_time(self, game: Dict) -> Optional[datetime]:
        """
        Parse kickoff time from game dictionary.

        Args:
            game: Game dictionary from nflreadpy

        Returns:
            Datetime object in Eastern time
        """
        try:
            # Game has 'gametime' field (e.g., '13:00')
            gameday = game["gameday"]
            gametime = game.get("gametime", "13:00")

            # Combine date and time
            kickoff_str = f"{gameday} {gametime}"
            kickoff = datetime.strptime(kickoff_str, "%Y-%m-%d %H:%M")

            # Make timezone aware (Eastern time)
            kickoff = self.eastern.localize(kickoff)

            return kickoff

        except Exception as e:
            logger.error(f"Error parsing kickoff time: {e}")
            return None


class PipelineOrchestrator:
    """Orchestrates the complete betting pipeline."""

    def __init__(self, dry_run: bool = False):
        """
        Initialize orchestrator.

        Args:
            dry_run: If True, run through pipeline but don't send notifications
        """
        self.dry_run = dry_run
        self.schedule_mgr = NFLScheduleManager()
        self.eastern = pytz.timezone("US/Eastern")

        # Create logs directory if needed
        Path("logs").mkdir(exist_ok=True)

    def run_pregame_engine(self, games: List[Dict]) -> str:
        """
        Run pre-game prediction engine.

        Args:
            games: List of games to analyze

        Returns:
            Path to output file
        """
        logger.info("Running pre-game prediction engine...")

        output_file = "reports/pregame_analysis.json"

        try:
            # Write games to temp file for input
            temp_games = "reports/temp_games.json"
            with open(temp_games, "w") as f:
                json.dump(games, f)

            # Run pregame engine
            cmd = [
                sys.executable,
                "scripts/pregame_prediction_engine.py",
                "--all-today",
                "--output",
                output_file,
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

            if result.returncode == 0:
                logger.info("[SUCCESS] Pre-game engine completed successfully")
                logger.debug(result.stdout)
            else:
                logger.error(f"[FAILED] Pre-game engine failed: {result.stderr}")
                return None

            return output_file

        except Exception as e:
            logger.error(f"Error running pre-game engine: {e}")
            return None

    def run_parlay_generator(self, analysis_file: str) -> str:
        """
        Run parlay generator.

        Args:
            analysis_file: Path to pregame analysis JSON

        Returns:
            Path to output file
        """
        logger.info("Running parlay generator...")

        output_file = "reports/parlays.json"

        try:
            cmd = [
                sys.executable,
                "scripts/parlay_generator.py",
                "--input",
                analysis_file,
                "--output",
                output_file,
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            if result.returncode == 0:
                logger.info("[SUCCESS] Parlay generator completed successfully")
                logger.debug(result.stdout)
            else:
                logger.error(f"[FAILED] Parlay generator failed: {result.stderr}")
                return None

            return output_file

        except Exception as e:
            logger.error(f"Error running parlay generator: {e}")
            return None

    def send_notifications(self, analysis_file: str, parlays_file: str) -> bool:
        """
        Send notifications via all channels.

        Args:
            analysis_file: Path to pregame analysis JSON
            parlays_file: Path to parlays JSON

        Returns:
            True if successful, False otherwise
        """
        if self.dry_run:
            logger.info("DRY RUN: Skipping notification sending")
            return True

        logger.info("Sending notifications...")

        try:
            cmd = [
                sys.executable,
                "scripts/send_bet_notifications.py",
                "--analysis",
                analysis_file,
                "--parlays",
                parlays_file,
            ]

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            if result.returncode == 0:
                logger.info("[SUCCESS] Notifications sent successfully")
                logger.debug(result.stdout)
                return True
            else:
                logger.error(f"[FAILED] Notification sending failed: {result.stderr}")
                return False

        except Exception as e:
            logger.error(f"Error sending notifications: {e}")
            return False

    def run_full_pipeline(self, games: List[Dict]) -> bool:
        """
        Run complete pipeline for games.

        Args:
            games: List of games to process

        Returns:
            True if successful, False otherwise
        """
        logger.info(f"\n{'='*80}")
        logger.info("STARTING FULL PIPELINE")
        logger.info(f"Processing {len(games)} games")
        logger.info(f"{'='*80}\n")

        # Step 1: Run pre-game engine
        analysis_file = self.run_pregame_engine(games)
        if not analysis_file or not Path(analysis_file).exists():
            logger.error("Pre-game engine failed - aborting pipeline")
            return False

        # Step 2: Run parlay generator
        parlays_file = self.run_parlay_generator(analysis_file)
        if not parlays_file or not Path(parlays_file).exists():
            logger.error("Parlay generator failed - aborting pipeline")
            return False

        # Step 3: Send notifications
        success = self.send_notifications(analysis_file, parlays_file)
        if not success:
            logger.error("Notification sending failed")
            return False

        logger.info(f"\n{'='*80}")
        logger.info("[SUCCESS] PIPELINE COMPLETED SUCCESSFULLY")
        logger.info(f"{'='*80}\n")

        return True

    def wait_for_alert_time(self, kickoff: datetime, alert_minutes: int = 60):
        """
        Wait until alert time (X minutes before kickoff).

        Args:
            kickoff: Game kickoff time
            alert_minutes: Minutes before kickoff to alert
        """
        alert_time = kickoff - timedelta(minutes=alert_minutes)
        now = datetime.now(self.eastern)

        if now >= alert_time:
            logger.info("Alert time already passed - running immediately")
            return

        wait_seconds = (alert_time - now).total_seconds()
        wait_minutes = wait_seconds / 60

        logger.info(
            f"Waiting {wait_minutes:.1f} minutes until alert time ({alert_time.strftime('%I:%M %p ET')})"
        )

        # Sleep in 1-minute intervals so we can check for shutdown signals
        while datetime.now(self.eastern) < alert_time:
            time.sleep(60)
            remaining = (alert_time - datetime.now(self.eastern)).total_seconds() / 60
            if remaining > 0:
                logger.debug(f"  {remaining:.1f} minutes remaining...")

    def run_continuous(self):
        """
        Run pipeline continuously - check for games every day.
        """
        logger.info("Starting continuous pipeline mode...")
        logger.info("Checking for games every day during NFL season")

        while True:
            try:
                # Get today's games
                games = self.schedule_mgr.get_today_schedule()

                if not games:
                    logger.info("No games today - sleeping until tomorrow")
                    # Sleep until 8 AM tomorrow
                    now = datetime.now(self.eastern)
                    tomorrow_8am = (now + timedelta(days=1)).replace(
                        hour=8, minute=0, second=0
                    )
                    sleep_seconds = (tomorrow_8am - now).total_seconds()
                    time.sleep(sleep_seconds)
                    continue

                # Process each game
                for game in games:
                    kickoff = self.schedule_mgr.parse_kickoff_time(game)
                    if not kickoff:
                        logger.warning(
                            f"Could not parse kickoff time for game: {game.get('game_id')}"
                        )
                        continue

                    # Wait until 1 hour before kickoff
                    self.wait_for_alert_time(kickoff, alert_minutes=60)

                    # Run pipeline for this game
                    self.run_full_pipeline([game])

                # All games processed - sleep until tomorrow
                logger.info("All games processed for today - sleeping until tomorrow")
                now = datetime.now(self.eastern)
                tomorrow_8am = (now + timedelta(days=1)).replace(
                    hour=8, minute=0, second=0
                )
                sleep_seconds = (tomorrow_8am - now).total_seconds()
                time.sleep(sleep_seconds)

            except KeyboardInterrupt:
                logger.info("Pipeline stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in continuous pipeline: {e}", exc_info=True)
                # Sleep for 1 hour and try again
                time.sleep(3600)


def main():
    """Main execution."""
    parser = argparse.ArgumentParser(description="Full NFL Betting Pipeline")
    parser.add_argument(
        "--test", action="store_true", help="Test mode with specific date"
    )
    parser.add_argument(
        "--date", default=None, help="Specific date to test (YYYY-MM-DD)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run pipeline but skip sending notifications",
    )
    parser.add_argument(
        "--continuous", action="store_true", help="Run continuously (production mode)"
    )

    args = parser.parse_args()

    # Initialize orchestrator
    orchestrator = PipelineOrchestrator(dry_run=args.dry_run)

    if args.test or args.date:
        # Test mode - run once for specific date
        date_str = args.date or datetime.now().strftime("%Y-%m-%d")
        logger.info(f"Running in TEST mode for date: {date_str}")

        games = orchestrator.schedule_mgr.get_games_by_date(date_str)

        if not games:
            logger.warning(f"No games found for {date_str}")
            # Use sample data for testing
            logger.info("Using sample game data for testing")
            games = [
                {
                    "game_id": "test_001",
                    "home_team": "Kansas City Chiefs",
                    "away_team": "Denver Broncos",
                    "week": 12,
                    "season": 2025,
                    "gameday": date_str,
                    "gametime": "13:00",
                    "kickoff_str": f"{date_str} 13:00 ET",
                }
            ]

        # Run pipeline immediately (no waiting)
        success = orchestrator.run_full_pipeline(games)

        if success:
            logger.info("[SUCCESS] Test run completed successfully")
        else:
            logger.error("[FAILED] Test run failed")
            sys.exit(1)

    elif args.continuous:
        # Production mode - run continuously
        logger.info("Starting in CONTINUOUS mode (production)")
        logger.info("Pipeline will run 24/7 - press Ctrl+C to stop")
        orchestrator.run_continuous()

    else:
        # Default: run once for today's games
        logger.info("Running pipeline for today's games")
        games = orchestrator.schedule_mgr.get_today_schedule()

        if not games:
            logger.info("No games scheduled for today")
            return

        # Run pipeline for all games
        success = orchestrator.run_full_pipeline(games)

        if success:
            logger.info("[SUCCESS] Pipeline completed successfully")
        else:
            logger.error("[FAILED] Pipeline failed")
            sys.exit(1)


if __name__ == "__main__":
    main()
