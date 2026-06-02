"""
Enhanced Daily Picks System with Grok AI Integration
Combines XGBoost model + Grok's real-time analysis for maximum edge
"""

import json
import os
import sys
from datetime import datetime
from typing import Dict, List

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging

from agents.xai_grok_agent import GrokAgent
from scripts.generate_daily_picks import DailyPicksGenerator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GrokEnhancedPicksGenerator(DailyPicksGenerator):
    """
    Enhanced picks generator with Grok AI integration.

    Benefits of Grok:
    - Real-time news and injury updates (via X/Twitter access)
    - Advanced reasoning about game situations
    - Weather edge validation
    - Sentiment analysis (public vs sharp money)
    - Second opinion on model predictions
    """

    def __init__(self, *args, use_grok: bool = True, **kwargs):
        """
        Initialize with Grok integration.

        Args:
            use_grok: Whether to use Grok AI (requires XAI_API_KEY and credits)
        """
        super().__init__(*args, **kwargs)

        self.use_grok = use_grok

        if use_grok:
            xai_key = os.getenv("XAI_API_KEY", "your_xai_api_key_here")
            try:
                self.grok = GrokAgent(api_key=xai_key)
                logger.info("[OK] Grok AI initialized")
            except Exception as e:
                logger.warning(f"Grok AI unavailable: {e}")
                self.use_grok = False
                self.grok = None
        else:
            self.grok = None

    def get_grok_analysis(
        self, game: Dict, prediction: Dict, weather: Dict = None
    ) -> Dict:
        """
        Get Grok's AI analysis of the game.

        Args:
            game: Game data from odds API
            prediction: Model prediction
            weather: Weather data

        Returns:
            Dict with Grok's analysis and recommendations
        """
        if not self.use_grok or not self.grok:
            return {}

        try:
            # Get comprehensive game analysis
            analysis = self.grok.analyze_game(
                home_team=game["home_team"],
                away_team=game["away_team"],
                weather=weather,
                odds=game,
            )

            # If weather is significant, get weather edge analysis
            weather_edge = None
            if weather:
                wind_speed = float(weather.get("wind_speed", "0").split()[0])
                temp = weather.get("temperature", 70)

                # Check if weather is significant
                if wind_speed > 12 or temp < 32:
                    # Find total from odds
                    total = None
                    for bookmaker in game.get("bookmakers", []):
                        for market in bookmaker.get("markets", []):
                            if market["key"] == "totals":
                                if market["outcomes"]:
                                    total = market["outcomes"][0]["point"]
                                    break
                        if total:
                            break

                    if total:
                        weather_edge = self.grok.analyze_weather_edge(
                            game=f"{game['away_team']} @ {game['home_team']}",
                            weather=weather,
                            total=total,
                        )

            return {
                "game_analysis": analysis,
                "weather_edge": weather_edge,
                "grok_available": True,
            }

        except Exception as e:
            logger.warning(f"Grok analysis failed: {e}")
            return {"grok_available": False, "error": str(e)}

    def enhance_pick_with_grok(self, pick: Dict, grok_analysis: Dict) -> Dict:
        """
        Enhance pick recommendation with Grok's insights.

        Args:
            pick: Original pick from model
            grok_analysis: Grok's analysis

        Returns:
            Enhanced pick with Grok insights
        """
        if not grok_analysis or not grok_analysis.get("grok_available"):
            return pick

        # Add Grok's reasoning
        game_analysis = grok_analysis.get("game_analysis", "")
        weather_edge = grok_analysis.get("weather_edge", "")

        # Parse Grok's analysis for key insights
        if game_analysis:
            # Check if Grok agrees with our pick
            pick_team = pick.get("pick", "")

            if pick_team.lower() in game_analysis.lower():
                # Grok mentions our pick - likely agrees
                pick["reasoning"].append("Grok AI agrees: Favorable matchup")

                # Check for strong confidence indicators
                strong_words = [
                    "strong",
                    "significant",
                    "advantage",
                    "dominant",
                    "elite",
                ]
                if any(word in game_analysis.lower() for word in strong_words):
                    pick["reasoning"].append("Grok AI: Strong confidence indicators")

                    # Upgrade tier if Grok is very confident
                    if pick["tier"] == "B":
                        pick["tier"] = "A"
                        pick["reasoning"].append(
                            "UPGRADED to Tier A (Grok confirmation)"
                        )
                    elif pick["tier"] == "C":
                        pick["tier"] = "B"
                        pick["reasoning"].append(
                            "UPGRADED to Tier B (Grok confirmation)"
                        )

        # Weather edge insights
        if (
            weather_edge
            and "under" in weather_edge.lower()
            and "bet" in weather_edge.lower()
        ):
            pick["reasoning"].append("Grok AI: Weather creates UNDER edge")

        # Add Grok metadata
        pick["grok_enhanced"] = True
        pick["grok_summary"] = (
            game_analysis[:200] + "..." if len(game_analysis) > 200 else game_analysis
        )

        return pick

    def generate_daily_picks_with_grok(self, min_edge: float = 0.05) -> List[Dict]:
        """
        Generate picks with Grok AI enhancement.

        Args:
            min_edge: Minimum edge to consider

        Returns:
            List of enhanced picks
        """
        logger.info("=" * 80)
        logger.info("GENERATING GROK-ENHANCED NFL PICKS")
        logger.info("=" * 80)

        if self.use_grok:
            logger.info("[OK] Grok AI active - real-time analysis enabled")
        else:
            logger.info("[!] Grok AI disabled - using model only")

        # Fetch odds
        logger.info("\n[1] Fetching current odds...")
        games = self.odds_api.get_nfl_odds()

        if not games:
            logger.error("No games available")
            return []

        logger.info(f"[OK] Found {len(games)} games")

        picks = []

        for game in games:
            home = game["home_team"]
            away = game["away_team"]

            logger.info(f"\n[2] Analyzing: {away} @ {home}")

            # Get weather
            weather = None
            if home in self.stadium_coords:
                lat, lon = self.stadium_coords[home]
                try:
                    weather = self.weather_api.get_forecast_for_point(lat, lon)
                    if weather:
                        logger.info(
                            f"    Weather: {weather.get('temperature')}°F, Wind: {weather.get('wind_speed')}"
                        )
                except Exception:
                    logger.warning("    Weather data unavailable")

            # Generate base prediction
            prediction = self.predict_game(home, away, weather, game)

            # Get Grok analysis
            grok_analysis = self.get_grok_analysis(game, prediction, weather)

            # Get line shopping report
            line_report = self.line_shopping.generate_line_shopping_report(game)

            # Generate pick
            pick = self.generate_pick(game, prediction, line_report)

            # Enhance with Grok
            if pick["recommendation"] == "BET" and grok_analysis:
                pick = self.enhance_pick_with_grok(pick, grok_analysis)

            if pick["recommendation"] == "BET":
                picks.append(pick)
                logger.info(
                    f"    [PICK] {pick['tier']}-Tier: {pick['pick']} {pick['line']} @ {pick['best_book']}"
                )
                logger.info(
                    f"           Edge: {pick['edge']}, Bet: {pick['bet_size']} ({pick['bet_size_pct']})"
                )

                if pick.get("grok_enhanced"):
                    logger.info(
                        f"           [GROK] {pick.get('grok_summary', 'Enhanced')}"
                    )
            else:
                logger.info(f"    [SKIP] {pick['reason']}")

        logger.info(f"\n{'='*80}")
        logger.info(f"TOTAL PICKS: {len(picks)}")
        if self.use_grok:
            grok_enhanced_count = sum(1 for p in picks if p.get("grok_enhanced"))
            logger.info(f"GROK ENHANCED: {grok_enhanced_count}")
        logger.info(f"{'='*80}\n")

        return picks

    def save_picks(self, picks: List[Dict], filename: str = None):
        """Save enhanced picks to file."""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            prefix = "grok_enhanced" if self.use_grok else "daily"
            filename = f"reports/{prefix}_picks_{timestamp}.json"

        os.makedirs(os.path.dirname(filename), exist_ok=True)

        with open(filename, "w") as f:
            json.dump(
                {
                    "generated_at": datetime.now().isoformat(),
                    "bankroll": self.bankroll,
                    "picks_count": len(picks),
                    "grok_enhanced": self.use_grok,
                    "picks": picks,
                },
                f,
                indent=2,
            )

        logger.info(f"Picks saved to: {filename}")
        return filename


def main():
    """Run Grok-enhanced picks generator."""
    import sys

    sys.stdout.reconfigure(encoding="utf-8")

    # Check if Grok should be used
    use_grok = os.getenv("XAI_API_KEY") is not None or "your_xai_api_key_here"

    print(f"\nGrok AI: {'ENABLED' if use_grok else 'DISABLED'}")
    print("=" * 80)

    # Initialize generator
    generator = GrokEnhancedPicksGenerator(
        bankroll=10000.0, use_grok=True  # Force enable for testing
    )

    # Generate picks
    picks = generator.generate_daily_picks_with_grok(min_edge=0.05)

    # Print report
    generator.print_picks_report(picks)

    # Save picks
    if picks:
        filename = generator.save_picks(picks)
        print(f"\nPicks saved to: {filename}")


if __name__ == "__main__":
    main()
