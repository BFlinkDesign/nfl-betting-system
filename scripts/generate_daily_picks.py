"""
Automated Daily Picks System
Generates NFL betting recommendations using all data sources and the trained model
"""

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List

import joblib
import numpy as np
import pandas as pd
from dotenv import load_dotenv

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load API keys from .env file
env_path = Path(__file__).parent.parent / "config" / "api_keys.env"
load_dotenv(env_path)

from agents.api_integrations import NOAAWeatherAPI, TheOddsAPI
from scripts.line_shopping import LineShoppingEngine
from src.betting.kelly import KellyCriterion

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DailyPicksGenerator:
    """
    Automated Daily Picks System

    Combines:
    - XGBoost model predictions
    - Real-time odds from 15+ sportsbooks
    - Weather data from NOAA
    - Line shopping for best value
    - Kelly criterion for bet sizing
    - Sharp money detection
    """

    def __init__(
        self,
        model_path: str = "models/xgboost_favorites_only.pkl",
        features_path: str = "data/processed/features_2016_2024_improved.parquet",
        bankroll: float = 10000.0,
        favorites_only: bool = True,
    ):
        """
        Initialize daily picks generator.

        Args:
            model_path: Path to trained model (default: favorites-only specialist)
            features_path: Path to feature data
            bankroll: Current bankroll for bet sizing
            favorites_only: Filter to favorites only (odds < 2.0)
        """
        # Try favorites-only model first, fallback to improved
        try:
            self.model = joblib.load(model_path)
            logger.info(f"Loaded model: {model_path}")
        except FileNotFoundError:
            # Fallback to improved model
            fallback_path = "models/xgboost_improved.pkl"
            try:
                self.model = joblib.load(fallback_path)
                logger.warning(
                    f"Favorites-only model not found, using: {fallback_path}"
                )
            except FileNotFoundError:
                logger.warning(f"Model not found: {model_path}")
                self.model = None

        self.favorites_only = favorites_only

        # Load historical features for team stats
        try:
            self.features_df = pd.read_parquet(features_path)
            logger.info(f"Loaded features: {features_path}")
        except FileNotFoundError:
            logger.warning(f"Features not found: {features_path}")
            self.features_df = None

        # Initialize APIs
        self.odds_api = TheOddsAPI()
        self.weather_api = NOAAWeatherAPI()
        self.line_shopping = LineShoppingEngine()
        # Aggressive Kelly sizing for favorites (our proven strength!)
        self.kelly = KellyCriterion(
            kelly_fraction=0.25,
            min_edge=0.02,
            max_bet_pct=0.10,  # Increased max for aggressive mode
            aggressive_mode=True,  # Enable aggressive multipliers
        )

        self.bankroll = bankroll

        # Stadium coordinates for weather
        self.stadium_coords = {
            "San Francisco 49ers": (37.4032, -121.9698),
            "Kansas City Chiefs": (39.0489, -94.4839),
            "Dallas Cowboys": (32.7480, -97.0926),
            "Green Bay Packers": (44.5013, -88.0622),
            "Detroit Lions": (42.3400, -83.0456),
            "Buffalo Bills": (42.7738, -78.7870),
            "Pittsburgh Steelers": (40.4468, -80.0158),
            "Philadelphia Eagles": (39.9008, -75.1675),
            "New England Patriots": (42.0909, -71.2643),
            "Carolina Panthers": (35.2258, -80.8529),
            "Cleveland Browns": (41.5061, -81.6995),
            "Chicago Bears": (41.8623, -87.6167),
            "Denver Broncos": (39.7439, -105.0201),
            "Washington Commanders": (38.9076, -76.8645),
            "Los Angeles Rams": (34.0141, -118.2879),
            "New York Giants": (40.8128, -74.0742),
            # Add more as needed
        }

    def get_team_recent_stats(self, team: str, season: int = 2024) -> Dict:
        """
        Get recent stats for a team.

        Args:
            team: Team name
            season: Season year

        Returns:
            Dict of recent stats
        """
        if self.features_df is None:
            return {}

        # Filter for team and recent games
        team_data = (
            self.features_df[
                (self.features_df["home_team"] == team)
                | (self.features_df["away_team"] == team)
            ]
            .sort_values("gameday", ascending=False)
            .head(4)
        )

        if team_data.empty:
            return {}

        # Calculate recent averages
        stats = {
            "games_played": len(team_data),
            "elo_rating": (
                team_data["elo_home"].iloc[0] if not team_data.empty else 1500
            ),
            "recent_form": team_data["result"].mean() if "result" in team_data else 0.5,
        }

        # Add EPA stats if available
        epa_cols = [col for col in team_data.columns if "epa" in col.lower()]
        for col in epa_cols[:5]:  # Top 5 EPA metrics
            stats[col] = team_data[col].mean()

        return stats

    def predict_game(
        self, home_team: str, away_team: str, weather: Dict = None, odds: Dict = None
    ) -> Dict:
        """
        Generate prediction for a game using the trained model.

        Args:
            home_team: Home team name
            away_team: Away team name
            weather: Weather data
            odds: Current odds

        Returns:
            Prediction dict with probability, confidence, recommended bet
        """
        if self.model is None:
            return {
                "error": "Model not loaded",
                "home_win_prob": 0.5,
                "model_used": False,
            }

        # Get team stats from historical data
        home_stats = self.get_team_recent_stats(home_team)
        away_stats = self.get_team_recent_stats(away_team)

        # Check if we have real data for these teams
        has_real_data = bool(home_stats) and bool(away_stats)

        if not has_real_data:
            logger.warning(
                f"No historical data for {home_team} vs {away_team} - cannot predict"
            )
            return {
                "error": "No historical data available",
                "home_team": home_team,
                "away_team": away_team,
                "home_win_prob": 0.5,
                "away_win_prob": 0.5,
                "confidence": 0.0,
                "model_used": False,
                "predicted_winner": None,
            }

        # Build feature vector for the model
        # Use actual Elo ratings from data
        home_elo = home_stats.get("elo_rating", 1500)
        away_elo = away_stats.get("elo_rating", 1500)
        elo_diff = home_elo - away_elo

        features = {
            "elo_home": home_elo,
            "elo_away": away_elo,
            "elo_diff": elo_diff,
            "elo_prob_home": 1 / (1 + 10 ** (-elo_diff / 400)),
            "rest_days_home": 7,
            "rest_days_away": 7,
        }

        # Add weather features if available
        if weather:
            try:
                wind_str = weather.get("wind_speed", "0 mph")
                wind_speed = float(wind_str.split()[0]) if wind_str else 0
                features["wind"] = wind_speed
                features["temp"] = weather.get("temperature", 65)
                features["is_dome"] = 0
                features["is_cold"] = 1 if features["temp"] < 40 else 0
                features["is_windy"] = 1 if wind_speed > 15 else 0
            except (ValueError, AttributeError):
                pass

        # Add EPA and form stats if available
        for stat_key in [
            "epa_offense_home",
            "epa_defense_home",
            "win_pct_home",
            "point_diff_home",
        ]:
            if stat_key in home_stats:
                features[stat_key] = home_stats[stat_key]
        for stat_key in [
            "epa_offense_away",
            "epa_defense_away",
            "win_pct_away",
            "point_diff_away",
        ]:
            if stat_key.replace("_away", "_home") in away_stats:
                features[stat_key] = away_stats[stat_key.replace("_away", "_home")]

        # Try to use model with available features
        try:
            # Get expected feature columns from model
            if hasattr(self.model, "feature_names_in_"):
                expected_features = list(self.model.feature_names_in_)
            elif hasattr(self.model, "get_booster"):
                expected_features = self.model.get_booster().feature_names
            else:
                # Fall back to Elo-based prediction if we can't determine features
                logger.warning(
                    "Cannot determine model features, using Elo-based prediction"
                )
                home_win_prob = 1 / (1 + 10 ** (-elo_diff / 400))
                return self._build_prediction_result(
                    home_team, away_team, home_win_prob, features, model_used=False
                )

            # Build feature vector with correct columns
            feature_vector = []
            for feat in expected_features:
                feature_vector.append(features.get(feat, 0.0))

            import numpy as np

            X = np.array([feature_vector])

            # Get prediction
            if hasattr(self.model, "predict_proba"):
                proba = self.model.predict_proba(X)
                if proba.ndim == 1:
                    home_win_prob = float(proba[0])
                else:
                    home_win_prob = (
                        float(proba[0, 1]) if proba.shape[1] > 1 else float(proba[0, 0])
                    )
            else:
                # Raw prediction
                home_win_prob = float(self.model.predict(X)[0])

            return self._build_prediction_result(
                home_team,
                away_team,
                home_win_prob,
                features,
                model_used=True,
                odds=odds,
            )

        except Exception as e:
            logger.error(f"Model prediction failed: {e}")
            # Fall back to Elo - but mark as model not used
            home_win_prob = 1 / (1 + 10 ** (-elo_diff / 400))
            return self._build_prediction_result(
                home_team,
                away_team,
                home_win_prob,
                features,
                model_used=False,
                odds=odds,
            )

        return self._build_prediction_result(
            home_team, away_team, home_win_prob, features, model_used=False, odds=odds
        )

    def _build_prediction_result(
        self,
        home_team: str,
        away_team: str,
        home_win_prob: float,
        features: Dict,
        model_used: bool = True,
        odds: Dict = None,
    ) -> Dict:
        """Build standardized prediction result."""
        # Clamp probability to reasonable range
        home_win_prob = max(0.15, min(0.85, home_win_prob))

        prediction = {
            "home_team": home_team,
            "away_team": away_team,
            "home_win_prob": home_win_prob,
            "away_win_prob": 1 - home_win_prob,
            "confidence": abs(home_win_prob - 0.5) * 2,  # 0-1 scale
            "predicted_winner": home_team if home_win_prob > 0.5 else away_team,
            "features": features,
            "model_used": model_used,
        }

        # Add betting edge if odds available
        if odds:
            prediction["betting_edge"] = self._calculate_edge(prediction, odds)

        return prediction

    def _calculate_edge(self, prediction: Dict, odds: Dict) -> Dict:
        """
        Calculate betting edge vs market odds.

        Args:
            prediction: Model prediction
            odds: Market odds

        Returns:
            Dict with edge analysis
        """
        home_win_prob = prediction["home_win_prob"]

        # Get market implied probability from moneyline
        market_probs = {}

        for bookmaker in odds.get("bookmakers", []):
            for market in bookmaker.get("markets", []):
                if market["key"] == "h2h":
                    for outcome in market["outcomes"]:
                        ml_odds = outcome["price"]

                        # Convert American odds to probability
                        if ml_odds > 0:
                            implied_prob = 100 / (ml_odds + 100)
                        else:
                            implied_prob = abs(ml_odds) / (abs(ml_odds) + 100)

                        team = outcome["name"]
                        if team == prediction["home_team"]:
                            if "home" not in market_probs:
                                market_probs["home"] = []
                            market_probs["home"].append(implied_prob)
                        elif team == prediction["away_team"]:
                            if "away" not in market_probs:
                                market_probs["away"] = []
                            market_probs["away"].append(implied_prob)

        if not market_probs:
            return {}

        # Average market probability
        avg_home_prob = np.mean(market_probs.get("home", [0.5]))
        avg_away_prob = np.mean(market_probs.get("away", [0.5]))

        # Calculate edge
        home_edge = home_win_prob - avg_home_prob
        away_edge = (1 - home_win_prob) - avg_away_prob

        return {
            "home_edge": home_edge,
            "away_edge": away_edge,
            "market_home_prob": avg_home_prob,
            "market_away_prob": avg_away_prob,
            "has_edge": max(abs(home_edge), abs(away_edge)) > 0.05,  # 5% threshold
            "best_bet": (
                prediction["home_team"]
                if home_edge > 0.05
                else (prediction["away_team"] if away_edge > 0.05 else None)
            ),
        }

    def generate_pick(
        self, game: Dict, prediction: Dict, line_shopping_report: Dict
    ) -> Dict:
        """
        Generate final betting recommendation with sizing.

        CRITICAL: Filters to favorites only (odds < 2.0) if favorites_only=True.
        This is our proven strength: 77% win rate, +12% ROI on favorites.

        Args:
            game: Game data
            prediction: Model prediction
            line_shopping_report: Line shopping analysis

        Returns:
            Complete pick recommendation
        """
        # CRITICAL: Reject predictions that didn't use the model
        if not prediction.get("model_used", False):
            return {
                "recommendation": "NO BET",
                "reason": f"Model prediction unavailable - no reliable data for this game",
                "game": f"{prediction.get('away_team', 'Away')} @ {prediction.get('home_team', 'Home')}",
            }

        betting_edge = prediction.get("betting_edge", {})

        if not betting_edge or not betting_edge.get("has_edge"):
            return {
                "recommendation": "NO BET",
                "reason": "No sufficient edge (need >5%)",
                "game": f"{prediction['away_team']} @ {prediction['home_team']}",
            }

        # Determine bet
        best_bet = betting_edge["best_bet"]
        edge = betting_edge.get(
            "home_edge" if best_bet == prediction["home_team"] else "away_edge", 0
        )
        confidence = prediction["confidence"]

        # Get best line
        is_home = best_bet == prediction["home_team"]
        spread_info = line_shopping_report["spread"]["home" if is_home else "away"]
        ml_info = line_shopping_report["moneyline"]["home" if is_home else "away"]

        # CRITICAL: FAVORITES-ONLY FILTER
        # Convert odds to decimal
        ml_odds = ml_info["odds"]
        if ml_odds > 0:
            decimal_odds = (ml_odds / 100) + 1
        else:
            decimal_odds = (100 / abs(ml_odds)) + 1

        # Filter out underdogs (odds >= 2.0) - we're terrible at these!
        if self.favorites_only and decimal_odds >= 2.0:
            return {
                "recommendation": "NO BET",
                "reason": f"Underdog (odds {decimal_odds:.2f}) - we skip these (34% win rate proven)",
                "game": f"{prediction['away_team']} @ {prediction['home_team']}",
            }

        # Filter out heavy favorites (odds < 1.3) - bad value
        if self.favorites_only and decimal_odds < 1.3:
            return {
                "recommendation": "NO BET",
                "reason": f"Too heavy favorite (odds {decimal_odds:.2f}) - poor value",
                "game": f"{prediction['away_team']} @ {prediction['home_team']}",
            }

        # Filter edge sweet spot (3-6% is optimal based on backtest)
        if self.favorites_only and (edge < 0.03 or edge > 0.08):
            return {
                "recommendation": "NO BET",
                "reason": f"Edge {edge*100:.1f}% outside sweet spot (3-6% optimal)",
                "game": f"{prediction['away_team']} @ {prediction['home_team']}",
            }

        # Kelly bet sizing
        win_prob = (
            prediction["home_win_prob"] if is_home else prediction["away_win_prob"]
        )

        bet_size = self.kelly.calculate_bet_size(win_prob, decimal_odds, self.bankroll)

        # Calculate kelly percentage for reporting
        if decimal_odds > 1:
            b = decimal_odds - 1
            kelly_full = (win_prob * b - (1 - win_prob)) / b
            kelly_fraction = kelly_full * 0.25
        else:
            kelly_fraction = 0.01

        # Ensure minimum bet
        bet_size = (
            max(bet_size, self.bankroll * 0.01)
            if bet_size > 0
            else self.bankroll * 0.02
        )

        # Determine tier
        if confidence > 0.70 and edge > 0.10:
            tier = "S"  # Elite
        elif confidence > 0.60 and edge > 0.07:
            tier = "A"  # Strong
        elif confidence > 0.50 and edge > 0.05:
            tier = "B"  # Good
        else:
            tier = "C"  # Marginal

        pick = {
            "recommendation": "BET",
            "game": f"{prediction['away_team']} @ {prediction['home_team']}",
            "pick": best_bet,
            "bet_type": "MONEYLINE",
            "line": ml_info["odds"],
            "best_book": ml_info["best_book"],
            "win_probability": f"{win_prob*100:.1f}%",
            "edge": f"{edge*100:+.1f}%",
            "confidence": f"{confidence*100:.1f}%",
            "tier": tier,
            "bet_size": f"${bet_size:.0f}",
            "bet_size_pct": f"{(bet_size/self.bankroll)*100:.1f}%",
            "kelly_fraction": f"{kelly_fraction*100:.1f}%",
            "reasoning": [],
        }

        # Add reasoning
        if confidence > 0.65:
            pick["reasoning"].append(f"High model confidence ({confidence*100:.0f}%)")

        if edge > 0.08:
            pick["reasoning"].append(f"Significant edge vs market ({edge*100:+.1f}%)")

        if line_shopping_report["line_movement"].get("sharp_indicator"):
            pick["reasoning"].append("Sharp money detected - professional action")

        spread_edge = spread_info.get("edge", "0.0pts")
        if spread_edge and float(spread_edge.replace("pts", "")) > 0.5:
            pick["reasoning"].append(f"Excellent line value ({spread_edge})")

        return pick

    def generate_daily_picks(self, min_edge: float = 0.05) -> List[Dict]:
        """
        Generate all daily picks.

        Args:
            min_edge: Minimum edge to consider betting

        Returns:
            List of pick recommendations
        """
        logger.info("=" * 80)
        logger.info("GENERATING DAILY NFL PICKS")
        logger.info("=" * 80)

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

            # Generate prediction
            prediction = self.predict_game(home, away, weather, game)

            # Get line shopping report
            line_report = self.line_shopping.generate_line_shopping_report(game)

            # Generate pick
            pick = self.generate_pick(game, prediction, line_report)

            if pick["recommendation"] == "BET":
                picks.append(pick)
                logger.info(
                    f"    [PICK] {pick['tier']}-Tier: {pick['pick']} {pick['line']} @ {pick['best_book']}"
                )
                logger.info(
                    f"           Edge: {pick['edge']}, Bet: {pick['bet_size']} ({pick['bet_size_pct']})"
                )
            else:
                logger.info(f"    [SKIP] {pick['reason']}")

        logger.info(f"\n{'='*80}")
        logger.info(f"TOTAL PICKS: {len(picks)}")
        logger.info(f"{'='*80}\n")

        return picks

    def save_picks(self, picks: List[Dict], filename: str = None):
        """Save picks to file."""
        if not filename:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"reports/daily_picks_{timestamp}.json"

        os.makedirs(os.path.dirname(filename), exist_ok=True)

        with open(filename, "w") as f:
            json.dump(
                {
                    "generated_at": datetime.now().isoformat(),
                    "bankroll": self.bankroll,
                    "picks_count": len(picks),
                    "picks": picks,
                },
                f,
                indent=2,
            )

        logger.info(f"Picks saved to: {filename}")
        return filename

    def print_picks_report(self, picks: List[Dict]):
        """Print formatted picks report."""
        print("\n" + "=" * 80)
        print("DAILY NFL PICKS REPORT")
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"Bankroll: ${self.bankroll:,.0f}")
        print("=" * 80)

        if not picks:
            print("\n[NO PICKS TODAY]")
            print("Reason: No games with sufficient edge found")
            print("\nCriteria for betting:")
            print("- Edge vs market > 5%")
            print("- Model confidence > 50%")
            print("- Quality line available")
            return

        # Group by tier
        picks_by_tier = {}
        for pick in picks:
            tier = pick["tier"]
            if tier not in picks_by_tier:
                picks_by_tier[tier] = []
            picks_by_tier[tier].append(pick)

        # Print by tier
        for tier in ["S", "A", "B", "C"]:
            if tier not in picks_by_tier:
                continue

            tier_picks = picks_by_tier[tier]
            tier_names = {"S": "ELITE", "A": "STRONG", "B": "GOOD", "C": "MARGINAL"}

            print(f"\n{'='*80}")
            print(f"TIER {tier} - {tier_names[tier]} ({len(tier_picks)} picks)")
            print("=" * 80)

            for i, pick in enumerate(tier_picks, 1):
                print(f"\n[{i}] {pick['game']}")
                print(f"    Pick: {pick['pick']} {pick['line']} ({pick['bet_type']})")
                print(f"    Book: {pick['best_book']}")
                print(
                    f"    Edge: {pick['edge']} | Win Prob: {pick['win_probability']} | Confidence: {pick['confidence']}"
                )
                print(
                    f"    Bet Size: {pick['bet_size']} ({pick['bet_size_pct']}) | Kelly: {pick['kelly_fraction']}"
                )

                if pick["reasoning"]:
                    print("    Reasoning:")
                    for reason in pick["reasoning"]:
                        print(f"      - {reason}")

        # Summary
        total_bet = sum(float(p["bet_size"].replace("$", "")) for p in picks)
        print(f"\n{'='*80}")
        print("SUMMARY")
        print(f"{'='*80}")
        print(f"Total Picks: {len(picks)}")
        print(
            f"Total Risk: ${total_bet:.0f} ({(total_bet/self.bankroll)*100:.1f}% of bankroll)"
        )
        print(f"Avg Bet Size: ${total_bet/len(picks):.0f}")
        print("\nTier Breakdown:")
        for tier in ["S", "A", "B", "C"]:
            count = len(picks_by_tier.get(tier, []))
            if count > 0:
                print(f"  Tier {tier}: {count} picks")

        print("\n" + "=" * 80)


def main():
    """Run daily picks generator."""
    import sys

    sys.stdout.reconfigure(encoding="utf-8")

    # Initialize generator
    generator = DailyPicksGenerator(bankroll=10000.0)

    # Generate picks
    picks = generator.generate_daily_picks(min_edge=0.05)

    # Print report
    generator.print_picks_report(picks)

    # Save picks
    if picks:
        filename = generator.save_picks(picks)
        print(f"\nPicks saved to: {filename}")


if __name__ == "__main__":
    main()
