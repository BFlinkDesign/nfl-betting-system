"""
BET RESEARCH & DECISION SUPPORT TOOL

This tool helps you make informed betting decisions by providing:
- All available bets for upcoming games
- Key stats and data points
- Model predictions (if available)
- Market insights and edges
- Hidden correlations and patterns

YOU make the final decision. This tool just arms you with data.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
import warnings
from typing import Dict, List

import pandas as pd

warnings.filterwarnings("ignore")

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


class BetResearchTool:
    """Research tool to help make informed betting decisions."""

    def __init__(self):
        self.games_df = None
        self.odds_df = None
        self.model = None
        self.features_df = None

    def load_data(self):
        """Load all available data."""
        logger.info("Loading data...")

        # Try to load schedule
        try:
            self.games_df = pd.read_parquet("data/raw/schedules_2016_2024.parquet")
            logger.info(f"✓ Loaded {len(self.games_df)} games")
        except Exception as e:
            logger.warning(f"Could not load schedule: {e}")

        # Try to load features
        try:
            self.features_df = pd.read_parquet(
                "data/processed/features_2016_2024_improved.parquet"
            )
            logger.info(f"✓ Loaded features for {len(self.features_df)} games")
        except Exception as e:
            logger.warning(f"Could not load features: {e}")

        # Try to load model
        try:
            import joblib

            self.model = joblib.load("models/xgboost_improved.pkl")
            logger.info("✓ Loaded model")
        except Exception as e:
            logger.warning(f"Could not load model: {e}")

    def get_upcoming_games(self, weeks_ahead: int = 1) -> pd.DataFrame:
        """Get upcoming games."""
        if self.games_df is None:
            return pd.DataFrame()

        today = pd.Timestamp.now()
        future = today + pd.Timedelta(days=weeks_ahead * 7)

        upcoming = self.games_df[
            (pd.to_datetime(self.games_df["gameday"]) >= today)
            & (pd.to_datetime(self.games_df["gameday"]) <= future)
        ].copy()

        return upcoming.sort_values("gameday")

    def analyze_game(self, game_id: str) -> Dict:
        """Deep analysis of a single game for betting decisions."""

        analysis = {
            "game_id": game_id,
            "basic_info": {},
            "team_stats": {},
            "model_prediction": {},
            "betting_insights": {},
            "hidden_edges": {},
            "recommendations": [],
        }

        # Get game info
        if self.games_df is not None:
            game = self.games_df[self.games_df["game_id"] == game_id]
            if len(game) > 0:
                game = game.iloc[0]
                analysis["basic_info"] = {
                    "date": str(game.get("gameday", "N/A")),
                    "time": str(game.get("gametime", "N/A")),
                    "away_team": game.get("away_team", "N/A"),
                    "home_team": game.get("home_team", "N/A"),
                    "location": game.get("location", "N/A"),
                    "roof": game.get("roof", "N/A"),
                    "surface": game.get("surface", "N/A"),
                }

        # Get features
        if self.features_df is not None:
            features = self.features_df[self.features_df["game_id"] == game_id]
            if len(features) > 0:
                feat = features.iloc[0]

                # Team stats
                analysis["team_stats"] = {
                    "home": {
                        "elo": feat.get("elo_home", "N/A"),
                        "win_pct": feat.get("win_pct_home", "N/A"),
                        "point_diff": feat.get("point_diff_home", "N/A"),
                        "rest_days": feat.get("rest_days_home", "N/A"),
                        "post_bye": feat.get("post_bye_home", "N/A"),
                        "epa_offense": feat.get("epa_offense_home", "N/A"),
                        "epa_defense": feat.get("epa_defense_home", "N/A"),
                        "injuries": feat.get("injury_count_home", "N/A"),
                    },
                    "away": {
                        "elo": feat.get("elo_away", "N/A"),
                        "win_pct": feat.get("win_pct_away", "N/A"),
                        "point_diff": feat.get("point_diff_away", "N/A"),
                        "rest_days": feat.get("rest_days_away", "N/A"),
                        "post_bye": feat.get("post_bye_away", "N/A"),
                        "epa_offense": feat.get("epa_offense_away", "N/A"),
                        "epa_defense": feat.get("epa_defense_away", "N/A"),
                        "injuries": feat.get("injury_count_away", "N/A"),
                    },
                }

                # Model prediction
                if self.model is not None:
                    try:
                        # Get feature columns
                        feature_cols = [
                            col
                            for col in feat.index
                            if col
                            not in [
                                "game_id",
                                "gameday",
                                "home_team",
                                "away_team",
                                "season",
                                "week",
                                "home_score",
                                "away_score",
                            ]
                        ]

                        X = feat[feature_cols].values.reshape(1, -1)

                        # Align features with model
                        if hasattr(self.model, "get_booster"):
                            model_features = self.model.get_booster().feature_names
                            X_df = pd.DataFrame(X, columns=feature_cols)

                            # Fill missing features
                            for col in model_features:
                                if col not in X_df.columns:
                                    X_df[col] = 0

                            X = X_df[model_features].values

                        # Predict
                        if hasattr(self.model, "predict_proba"):
                            prob = self.model.predict_proba(X)[0]
                            home_win_prob = prob[1] if len(prob) > 1 else prob[0]
                        else:
                            home_win_prob = self.model.predict(X)[0]

                        analysis["model_prediction"] = {
                            "home_win_probability": f"{home_win_prob:.1%}",
                            "away_win_probability": f"{1-home_win_prob:.1%}",
                            "confidence": (
                                "High"
                                if abs(home_win_prob - 0.5) > 0.2
                                else (
                                    "Medium"
                                    if abs(home_win_prob - 0.5) > 0.1
                                    else "Low"
                                )
                            ),
                            "predicted_winner": (
                                analysis["basic_info"].get("home_team")
                                if home_win_prob > 0.5
                                else analysis["basic_info"].get("away_team")
                            ),
                        }

                    except Exception as e:
                        logger.debug(f"Could not generate prediction: {e}")

                # Hidden edges
                insights = []

                # Rest advantage
                rest_diff = feat.get("rest_days_home", 0) - feat.get(
                    "rest_days_away", 0
                )
                if abs(rest_diff) >= 3:
                    team = "home" if rest_diff > 0 else "away"
                    insights.append(
                        f"[REST] {team.upper()} has {abs(rest_diff)} more days rest (potential edge)"
                    )

                # Post-bye advantage
                if (
                    feat.get("post_bye_home", 0) == 1
                    and feat.get("post_bye_away", 0) == 0
                ):
                    insights.append(
                        "[BYE] HOME coming off BYE week (historically +2.5 points)"
                    )
                elif (
                    feat.get("post_bye_away", 0) == 1
                    and feat.get("post_bye_home", 0) == 0
                ):
                    insights.append(
                        "[BYE] AWAY coming off BYE week (historically +2.5 points)"
                    )

                # Dome advantage
                if feat.get("is_dome", 0) == 1:
                    insights.append(
                        "[DOME] DOME game (higher scoring, favors passing offenses)"
                    )

                # Weather
                if feat.get("is_cold", 0) == 1:
                    insights.append(
                        "[WEATHER] COLD weather game (favors rushing offenses, lower totals)"
                    )
                if feat.get("is_windy", 0) == 1:
                    insights.append(
                        "[WEATHER] WINDY conditions (harder to pass, bet UNDER)"
                    )

                # Divisional game
                if feat.get("div_game", 0) == 1:
                    insights.append(
                        "[DIVISION] DIVISIONAL game (closer spreads, lower scoring)"
                    )

                # EPA mismatches
                home_epa_off = feat.get("epa_offense_home", 0)
                away_epa_def = feat.get("epa_defense_away", 0)
                if home_epa_off > 0.1 and away_epa_def < -0.1:
                    insights.append(
                        "[MISMATCH] HOME offense vs weak AWAY defense (mismatch!)"
                    )

                away_epa_off = feat.get("epa_offense_away", 0)
                home_epa_def = feat.get("epa_defense_home", 0)
                if away_epa_off > 0.1 and home_epa_def < -0.1:
                    insights.append(
                        "[MISMATCH] AWAY offense vs weak HOME defense (mismatch!)"
                    )

                # Injuries
                home_inj = feat.get("injury_count_home", 0)
                away_inj = feat.get("injury_count_away", 0)
                if home_inj > away_inj + 3:
                    insights.append(
                        f"[INJURIES] HOME has {int(home_inj)} injuries (fade home team)"
                    )
                elif away_inj > home_inj + 3:
                    insights.append(
                        f"[INJURIES] AWAY has {int(away_inj)} injuries (fade away team)"
                    )

                analysis["hidden_edges"] = insights

        return analysis

    def generate_bet_ideas(self, game_id: str) -> List[Dict]:
        """Generate specific bet ideas for a game."""

        analysis = self.analyze_game(game_id)
        bet_ideas = []

        # Get basic info
        home_team = analysis["basic_info"].get("home_team", "HOME")
        away_team = analysis["basic_info"].get("away_team", "AWAY")

        # Model-based bets
        if analysis["model_prediction"]:
            prob = analysis["model_prediction"].get("home_win_probability", "N/A")
            winner = analysis["model_prediction"].get("predicted_winner", "N/A")
            conf = analysis["model_prediction"].get("confidence", "Low")

            if conf in ["High", "Medium"]:
                bet_ideas.append(
                    {
                        "type": "Moneyline",
                        "bet": f"{winner} ML",
                        "reason": f"Model predicts {winner} wins ({prob} confidence: {conf})",
                        "confidence": conf,
                    }
                )

        # Weather-based bets
        for insight in analysis["hidden_edges"]:
            if "WINDY" in insight:
                bet_ideas.append(
                    {
                        "type": "Total",
                        "bet": "UNDER",
                        "reason": "Windy conditions make passing difficult",
                        "confidence": "Medium",
                    }
                )
            elif "COLD" in insight:
                bet_ideas.append(
                    {
                        "type": "Total",
                        "bet": "UNDER (slightly)",
                        "reason": "Cold weather typically lowers scoring",
                        "confidence": "Low",
                    }
                )
            elif "DOME" in insight:
                bet_ideas.append(
                    {
                        "type": "Total",
                        "bet": "OVER (slightly)",
                        "reason": "Dome games typically score more",
                        "confidence": "Low",
                    }
                )

        # Rest-based bets
        for insight in analysis["hidden_edges"]:
            if "more days rest" in insight:
                team = "home" if "HOME" in insight else "away"
                team_name = home_team if team == "home" else away_team
                bet_ideas.append(
                    {
                        "type": "Spread",
                        "bet": f"{team_name} +spread",
                        "reason": insight,
                        "confidence": "Medium",
                    }
                )
            elif "coming off BYE" in insight:
                team = "home" if "HOME" in insight else "away"
                team_name = home_team if team == "home" else away_team
                bet_ideas.append(
                    {
                        "type": "Spread",
                        "bet": f"{team_name} -spread",
                        "reason": "Post-bye teams historically cover spread better",
                        "confidence": "Medium",
                    }
                )

        # EPA mismatch bets
        for insight in analysis["hidden_edges"]:
            if "mismatch!" in insight.lower():
                if "HOME offense" in insight:
                    bet_ideas.append(
                        {
                            "type": "Player Prop",
                            "bet": f"{home_team} QB/WR props OVER",
                            "reason": "Strong offense vs weak defense matchup",
                            "confidence": "High",
                        }
                    )
                elif "AWAY offense" in insight:
                    bet_ideas.append(
                        {
                            "type": "Player Prop",
                            "bet": f"{away_team} QB/WR props OVER",
                            "reason": "Strong offense vs weak defense matchup",
                            "confidence": "High",
                        }
                    )

        return bet_ideas

    def print_game_report(self, game_id: str):
        """Print a comprehensive betting report for a game."""

        analysis = self.analyze_game(game_id)
        bet_ideas = self.generate_bet_ideas(game_id)

        print("\n" + "=" * 80)
        print("BETTING RESEARCH REPORT")
        print("=" * 80)

        # Basic info
        info = analysis["basic_info"]
        print(f"\nDATE: {info.get('date', 'N/A')} @ {info.get('time', 'N/A')}")
        print(f"GAME: {info.get('away_team', 'N/A')} @ {info.get('home_team', 'N/A')}")
        print(
            f"VENUE: {info.get('location', 'N/A')} ({info.get('roof', 'N/A')}, {info.get('surface', 'N/A')})"
        )

        # Model prediction
        if analysis["model_prediction"]:
            print("\nMODEL PREDICTION:")
            pred = analysis["model_prediction"]
            print(f"   Winner: {pred.get('predicted_winner', 'N/A')}")
            print(f"   Home Win Probability: {pred.get('home_win_probability', 'N/A')}")
            print(f"   Confidence: {pred.get('confidence', 'N/A')}")

        # Team stats
        if analysis["team_stats"]:
            print("\nTEAM STATS:")

            home_stats = analysis["team_stats"]["home"]
            away_stats = analysis["team_stats"]["away"]

            print(f"\n   {info.get('home_team', 'HOME')} (Home):")
            print(
                f"      Elo: {home_stats.get('elo', 'N/A'):.0f}  |  Win %: {home_stats.get('win_pct', 0):.1%}"
            )
            print(
                f"      EPA Off: {home_stats.get('epa_offense', 0):+.3f}  |  EPA Def: {home_stats.get('epa_defense', 0):+.3f}"
            )
            print(
                f"      Rest: {home_stats.get('rest_days', 0):.0f} days  |  Injuries: {home_stats.get('injuries', 0):.0f}"
            )

            print(f"\n   {info.get('away_team', 'AWAY')} (Away):")
            print(
                f"      Elo: {away_stats.get('elo', 'N/A'):.0f}  |  Win %: {away_stats.get('win_pct', 0):.1%}"
            )
            print(
                f"      EPA Off: {away_stats.get('epa_offense', 0):+.3f}  |  EPA Def: {away_stats.get('epa_defense', 0):+.3f}"
            )
            print(
                f"      Rest: {away_stats.get('rest_days', 0):.0f} days  |  Injuries: {away_stats.get('injuries', 0):.0f}"
            )

        # Hidden edges
        if analysis["hidden_edges"]:
            print("\nHIDDEN EDGES:")
            for insight in analysis["hidden_edges"]:
                print(f"   {insight}")

        # Bet ideas
        if bet_ideas:
            print("\nBET IDEAS:")
            for i, idea in enumerate(bet_ideas, 1):
                conf_marker = (
                    "[HIGH]"
                    if idea["confidence"] == "High"
                    else "[MED]" if idea["confidence"] == "Medium" else "[LOW]"
                )
                print(f"\n   {conf_marker} Bet #{i} ({idea['type']}):")
                print(f"      {idea['bet']}")
                print(f"      Reason: {idea['reason']}")
                print(f"      Confidence: {idea['confidence']}")
        else:
            print("\nBET IDEAS: No strong edges identified")

        print("\n" + "=" * 80)
        print("WARNING: These are research insights, not predictions.")
        print("         Do your own due diligence. Bet responsibly.")
        print("=" * 80 + "\n")


def main():
    """Run the bet research tool."""

    print("\n" + "=" * 80)
    print("NFL BET RESEARCH & DECISION SUPPORT TOOL")
    print("=" * 80)
    print(
        "\nThis tool provides data-driven insights to help YOU make betting decisions."
    )
    print("It does NOT make bets automatically. YOU are in control.\n")

    tool = BetResearchTool()
    tool.load_data()

    # Get upcoming games
    print("\nFetching upcoming games...")
    upcoming = tool.get_upcoming_games(weeks_ahead=2)

    if len(upcoming) == 0:
        print("\nWARNING: No upcoming games found in database.")
        print("         The data includes games through 2024 season.")
        print("\n>>> Let's analyze a recent game as an example:")

        # Get a recent game from 2024
        if tool.games_df is not None:
            recent_2024 = tool.games_df[tool.games_df["season"] == 2024].tail(10)
            if len(recent_2024) > 0:
                example_game = recent_2024.iloc[0]
                game_id = example_game["game_id"]
                print(
                    f"\n    Analyzing: {example_game['away_team']} @ {example_game['home_team']}"
                )
                print(f"    Game ID: {game_id}")

                tool.print_game_report(game_id)
    else:
        print(f"\n✓ Found {len(upcoming)} upcoming games")
        print("\nUpcoming games:")
        for idx, game in upcoming.head(10).iterrows():
            print(
                f"  - {game['gameday']}: {game['away_team']} @ {game['home_team']} (ID: {game['game_id']})"
            )

        # Analyze first upcoming game
        if len(upcoming) > 0:
            first_game = upcoming.iloc[0]
            game_id = first_game["game_id"]

            print("\n\nANALYZING FIRST UPCOMING GAME:")
            tool.print_game_report(game_id)

    print("\n" + "=" * 80)
    print("HOW TO USE THIS TOOL:")
    print("=" * 80)
    print("\n1. Find game_id from upcoming games list")
    print("2. Run: tool.print_game_report('game_id')")
    print("3. Review insights and make YOUR betting decision")
    print("4. Track your bets and results")
    print("\n" + "=" * 80 + "\n")


if __name__ == "__main__":
    main()
