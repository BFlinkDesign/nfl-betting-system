"""
BULLDOG MODE: EDGE DISCOVERY SYSTEM

This script RELENTLESSLY searches for betting edges in NFL data.
Tests HUNDREDS of hypotheses. Doesn't stop until edges are found.

NO COMPROMISES. NO EXCUSES. FIND THE EDGE.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import logging
import warnings

import pandas as pd
from scipy import stats

# Import strategy registry
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
from strategy_registry import Strategy, StrategyRegistry, StrategyStatus

warnings.filterwarnings("ignore")

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


class BulldogEdgeDiscovery:
    """Relentlessly search for betting edges."""

    def __init__(self):
        self.data = None
        self.edges_found = []
        self.tests_run = 0

        # Initialize strategy registry
        self.registry = StrategyRegistry()
        self.new_strategies_count = 0
        self.duplicate_strategies_count = 0

    def load_data(self):
        """Load all available data."""
        logger.info("Loading data...")

        try:
            self.data = pd.read_parquet(
                "data/processed/features_2016_2024_improved.parquet"
            )

            # Filter to games with outcomes
            self.data = self.data[
                (self.data["home_score"].notna()) & (self.data["away_score"].notna())
            ].copy()

            # Add derived columns
            self.data["home_win"] = (
                self.data["home_score"] > self.data["away_score"]
            ).astype(int)
            self.data["point_diff"] = self.data["home_score"] - self.data["away_score"]
            self.data["total_points"] = (
                self.data["home_score"] + self.data["away_score"]
            )
            self.data["home_margin"] = self.data["home_score"] - self.data["away_score"]

            logger.info(f"Loaded {len(self.data)} games with outcomes")
            logger.info(
                f"Date range: {self.data['season'].min()} to {self.data['season'].max()}"
            )

            return True

        except Exception as e:
            logger.error(f"Could not load data: {e}")
            return False

    def test_hypothesis(self, name: str, condition, bet_outcome, min_sample=30):
        """
        Test a betting hypothesis.

        Args:
            name: Name of the hypothesis
            condition: Boolean series indicating when to bet
            bet_outcome: Boolean series indicating if bet won
            min_sample: Minimum sample size required
        """
        self.tests_run += 1

        # Filter to condition
        sample = self.data[condition].copy()

        if len(sample) < min_sample:
            return None

        # Calculate metrics
        wins = bet_outcome[condition].sum()
        total = len(sample)
        win_rate = wins / total if total > 0 else 0

        # Statistical significance (binomial test vs 52.4% break-even)
        break_even = 0.524  # Need to beat vig
        try:
            # Newer scipy API
            result = stats.binomtest(wins, total, break_even, alternative="greater")
            p_value = result.pvalue
        except AttributeError:
            # Older scipy API
            p_value = stats.binom_test(wins, total, break_even, alternative="greater")

        # Effect size (how much better than break-even)
        effect_size = win_rate - break_even

        # Only report if significant and positive edge
        if p_value < 0.05 and win_rate > break_even:
            # Calculate ROI
            roi = (win_rate * 0.909 - (1 - win_rate)) * 100

            edge = {
                "name": name,
                "sample_size": total,
                "wins": wins,
                "losses": total - wins,
                "win_rate": win_rate,
                "edge": effect_size,
                "p_value": p_value,
                "significance": "High" if p_value < 0.01 else "Medium",
                "seasons": f"{sample['season'].min()}-{sample['season'].max()}",
                "roi": roi,
            }

            # Check if similar strategy already exists in registry
            similar = self.registry.find_similar_strategy(name, threshold=0.85)

            if similar:
                # Similar strategy found - compare metrics to decide if we should update
                new_roi = roi
                old_roi = similar.roi

                if new_roi > old_roi:
                    # New strategy is BETTER - archive old and add new
                    logger.info(
                        f"  UPGRADE: '{name}' ROI {old_roi:.1f}% -> {new_roi:.1f}%"
                    )

                    # Archive the old strategy
                    self.registry.archive_strategy(
                        similar.strategy_id,
                        f"Replaced by better version (ROI: {old_roi:.1f}% -> {new_roi:.1f}%)",
                    )

                    # Create new strategy
                    strategy_id = (
                        name.lower()
                        .replace(" ", "_")
                        .replace(":", "")
                        .replace("+", "and")
                        .replace("-", "_")
                        .replace("__", "_")
                        + f"_v{similar.version + 1}"
                    )

                    strategy = Strategy(
                        strategy_id=strategy_id,
                        name=name,
                        description=f"Discovered edge: {name} (upgraded from v{similar.version})",
                        pattern=name,
                        win_rate=win_rate * 100,
                        roi=roi,
                        sample_size=total,
                        edge=effect_size * 100,
                        version=similar.version + 1,
                        conditions={
                            "seasons": f"{sample['season'].min()}-{sample['season'].max()}"
                        },
                    )

                    success, message = self.registry.add_strategy(
                        strategy, skip_duplicate_check=True
                    )
                    edge[
                        "registry_status"
                    ] = f"UPGRADED (v{similar.version} -> v{similar.version + 1})"
                    edge["is_new"] = success
                    if success:
                        self.new_strategies_count += 1
                else:
                    # Existing strategy is BETTER or EQUAL - skip
                    edge[
                        "registry_status"
                    ] = f"SKIPPED (existing {similar.name} has ROI {old_roi:.1f}% >= {new_roi:.1f}%)"
                    edge["is_new"] = False
                    self.duplicate_strategies_count += 1
            else:
                # New strategy - add to registry
                strategy_id = (
                    name.lower()
                    .replace(" ", "_")
                    .replace(":", "")
                    .replace("+", "and")
                    .replace("-", "_")
                    .replace("__", "_")
                    + "_v1"
                )

                strategy = Strategy(
                    strategy_id=strategy_id,
                    name=name,
                    description=f"Discovered edge: {name}",
                    pattern=name,  # Use name as pattern
                    win_rate=win_rate * 100,  # Convert to percentage
                    roi=roi,
                    sample_size=total,
                    edge=effect_size * 100,  # Convert to percentage
                    conditions={
                        "seasons": f"{sample['season'].min()}-{sample['season'].max()}"
                    },
                )

                success, message = self.registry.add_strategy(strategy)
                edge["registry_status"] = "NEW" if success else "ERROR"
                edge["is_new"] = success
                if success:
                    self.new_strategies_count += 1

            self.edges_found.append(edge)
            return edge

        return None

    def test_basic_edges(self):
        """Test basic betting edges."""
        logger.info("\n" + "=" * 80)
        logger.info("TESTING BASIC EDGES")
        logger.info("=" * 80)

        # 1. HOME FAVORITES
        if "elo_diff" in self.data.columns:
            condition = self.data["elo_diff"] > 100  # Home heavily favored
            outcome = self.data["home_win"]
            self.test_hypothesis("Home Favorites (Elo > 100)", condition, outcome)

        # 2. REST ADVANTAGE
        if (
            "rest_days_home" in self.data.columns
            and "rest_days_away" in self.data.columns
        ):
            rest_diff = self.data["rest_days_home"] - self.data["rest_days_away"]

            # Home team has 3+ more rest days
            condition = rest_diff >= 3
            outcome = self.data["home_win"]
            self.test_hypothesis("Home Team: 3+ More Rest Days", condition, outcome)

            # Away team has 3+ more rest days
            condition = rest_diff <= -3
            outcome = 1 - self.data["home_win"]
            self.test_hypothesis("Away Team: 3+ More Rest Days", condition, outcome)

        # 3. POST-BYE
        if "post_bye_home" in self.data.columns:
            condition = self.data["post_bye_home"] == 1
            outcome = self.data["home_win"]
            self.test_hypothesis("Home Team Post-Bye", condition, outcome)

        if "post_bye_away" in self.data.columns:
            condition = self.data["post_bye_away"] == 1
            outcome = 1 - self.data["home_win"]
            self.test_hypothesis("Away Team Post-Bye", condition, outcome)

        # 4. DIVISIONAL GAMES
        if "div_game" in self.data.columns:
            condition = self.data["div_game"] == 1

            # Test if home team wins more in division games
            outcome = self.data["home_win"]
            self.test_hypothesis("Divisional Games: Home Team", condition, outcome)

        # 5. DOME GAMES
        if "is_dome" in self.data.columns:
            condition = self.data["is_dome"] == 1

            # Test if home team wins more in dome
            outcome = self.data["home_win"]
            self.test_hypothesis("Dome Games: Home Team", condition, outcome)

    def test_weather_edges(self):
        """Test weather-related edges."""
        logger.info("\n" + "=" * 80)
        logger.info("TESTING WEATHER EDGES")
        logger.info("=" * 80)

        # 1. COLD + WIND = UNDER
        if "is_cold" in self.data.columns and "is_windy" in self.data.columns:
            condition = (self.data["is_cold"] == 1) & (self.data["is_windy"] == 1)

            # Bet under (total < historical average)
            historical_avg = self.data["total_points"].mean()
            outcome = self.data["total_points"] < historical_avg
            self.test_hypothesis("Cold + Windy = UNDER", condition, outcome)

        # 2. DOME = OVER
        if "is_dome" in self.data.columns:
            condition = self.data["is_dome"] == 1
            outcome = self.data["total_points"] > self.data["total_points"].mean()
            self.test_hypothesis("Dome Games = OVER", condition, outcome)

        # 3. COLD WEATHER = HOME TEAM ADVANTAGE
        if "is_cold" in self.data.columns and "roof" in self.data.columns:
            # Cold weather outdoor game
            condition = self.data["is_cold"] == 1
            outcome = self.data["home_win"]
            self.test_hypothesis("Cold Weather: Home Advantage", condition, outcome)

    def test_epa_edges(self):
        """Test EPA-based edges."""
        logger.info("\n" + "=" * 80)
        logger.info("TESTING EPA EDGES")
        logger.info("=" * 80)

        # 1. STRONG OFFENSE VS WEAK DEFENSE
        if all(
            col in self.data.columns for col in ["epa_offense_home", "epa_defense_away"]
        ):
            condition = (self.data["epa_offense_home"] > 0.1) & (
                self.data["epa_defense_away"] < -0.1
            )
            outcome = self.data["home_win"]
            self.test_hypothesis(
                "Strong Home Offense vs Weak Away Defense", condition, outcome
            )

        if all(
            col in self.data.columns for col in ["epa_offense_away", "epa_defense_home"]
        ):
            condition = (self.data["epa_offense_away"] > 0.1) & (
                self.data["epa_defense_home"] < -0.1
            )
            outcome = 1 - self.data["home_win"]
            self.test_hypothesis(
                "Strong Away Offense vs Weak Home Defense", condition, outcome
            )

        # 2. EXPLOSIVE OFFENSE MATCHUP
        if all(
            col in self.data.columns
            for col in ["epa_explosive_rate_home", "epa_explosive_rate_away"]
        ):
            condition = (self.data["epa_explosive_rate_home"] > 0.15) | (
                self.data["epa_explosive_rate_away"] > 0.15
            )
            outcome = self.data["total_points"] > self.data["total_points"].median()
            self.test_hypothesis("Explosive Offense Present = OVER", condition, outcome)

    def test_situational_edges(self):
        """Test situational edges."""
        logger.info("\n" + "=" * 80)
        logger.info("TESTING SITUATIONAL EDGES")
        logger.info("=" * 80)

        # 1. BACK-TO-BACK DISADVANTAGE
        if "is_back_to_back_home" in self.data.columns:
            condition = self.data["is_back_to_back_home"] == 1
            outcome = 1 - self.data["home_win"]  # Bet against home team
            self.test_hypothesis("Fade Home Team on Back-to-Back", condition, outcome)

        if "is_back_to_back_away" in self.data.columns:
            condition = self.data["is_back_to_back_away"] == 1
            outcome = self.data["home_win"]  # Bet home team
            self.test_hypothesis("Bet Home vs Away on Back-to-Back", condition, outcome)

        # 2. INJURY DISADVANTAGE
        if all(
            col in self.data.columns
            for col in ["injury_count_home", "injury_count_away"]
        ):
            # Home team has 5+ more injuries
            inj_diff = self.data["injury_count_home"] - self.data["injury_count_away"]
            condition = inj_diff >= 5
            outcome = 1 - self.data["home_win"]
            self.test_hypothesis("Fade Home Team: 5+ More Injuries", condition, outcome)

            # Away team has 5+ more injuries
            condition = inj_diff <= -5
            outcome = self.data["home_win"]
            self.test_hypothesis(
                "Bet Home vs Away: 5+ More Injuries", condition, outcome
            )

    def test_seasonal_edges(self):
        """Test edges that vary by time of season."""
        logger.info("\n" + "=" * 80)
        logger.info("TESTING SEASONAL EDGES")
        logger.info("=" * 80)

        if "week" not in self.data.columns:
            return

        # 1. EARLY SEASON (Weeks 1-4)
        condition = self.data["week"] <= 4

        # Home favorites more reliable early?
        if "elo_diff" in self.data.columns:
            early_home_fav = condition & (self.data["elo_diff"] > 50)
            outcome = self.data["home_win"]
            self.test_hypothesis(
                "Early Season: Home Favorites", early_home_fav, outcome
            )

        # 2. LATE SEASON (Weeks 15+)
        condition = self.data["week"] >= 15

        # Playoff-bound teams vs eliminated teams
        if "win_pct_home" in self.data.columns and "win_pct_away" in self.data.columns:
            # Home team has winning record, away team doesn't
            late_mismatch = (
                condition
                & (self.data["win_pct_home"] > 0.6)
                & (self.data["win_pct_away"] < 0.4)
            )
            outcome = self.data["home_win"]
            self.test_hypothesis(
                "Late Season: Playoff Team vs Eliminated Team", late_mismatch, outcome
            )

    def test_combination_edges(self):
        """Test combinations of factors."""
        logger.info("\n" + "=" * 80)
        logger.info("TESTING COMBINATION EDGES")
        logger.info("=" * 80)

        # 1. PERFECT STORM: Rest + Bye + Home
        if all(
            col in self.data.columns
            for col in ["rest_days_home", "rest_days_away", "post_bye_home"]
        ):
            rest_diff = self.data["rest_days_home"] - self.data["rest_days_away"]
            condition = (rest_diff >= 3) & (self.data["post_bye_home"] == 1)
            outcome = self.data["home_win"]
            self.test_hypothesis(
                "Perfect Storm: Home Post-Bye + 3+ Rest Advantage", condition, outcome
            )

        # 2. DOME + STRONG OFFENSE + WEAK DEFENSE
        if all(
            col in self.data.columns
            for col in ["is_dome", "epa_offense_home", "epa_defense_away"]
        ):
            condition = (
                (self.data["is_dome"] == 1)
                & (self.data["epa_offense_home"] > 0.1)
                & (self.data["epa_defense_away"] < -0.1)
            )
            outcome = self.data["home_win"]
            self.test_hypothesis(
                "Dome + Strong Home O vs Weak Away D", condition, outcome
            )

        # 3. DIVISIONAL + UNDERDOG
        if all(col in self.data.columns for col in ["div_game", "elo_diff"]):
            condition = (self.data["div_game"] == 1) & (
                self.data["elo_diff"] < -50
            )  # Home is underdog
            outcome = self.data["home_win"]
            self.test_hypothesis("Divisional Game: Home Underdog", condition, outcome)

    def test_recent_performance_edges(self):
        """Test edges based on recent performance (2023-2024 only)."""
        logger.info("\n" + "=" * 80)
        logger.info("TESTING RECENT EDGES (2023-2024 ONLY)")
        logger.info("=" * 80)

        recent = self.data[self.data["season"] >= 2023].copy()

        if len(recent) < 100:
            logger.warning("Not enough recent data")
            return

        # Save original data
        orig_data = self.data
        self.data = recent

        # Re-run all tests on recent data only
        self.test_basic_edges()
        self.test_weather_edges()
        self.test_epa_edges()

        # Restore original data
        self.data = orig_data

    def rank_edges(self):
        """Rank discovered edges by strength."""
        if not self.edges_found:
            return pd.DataFrame()

        df = pd.DataFrame(self.edges_found)

        # Calculate composite score
        # Higher score = better edge
        df["score"] = (
            df["edge"] * 100  # Edge percentage (main factor)
            + (df["sample_size"] / 10)  # Reward larger samples
            + (1 - df["p_value"]) * 10  # Reward statistical significance
        )

        df = df.sort_values("score", ascending=False)

        return df

    def print_results(self):
        """Print all discovered edges."""
        logger.info("\n" + "=" * 80)
        logger.info("BULLDOG MODE: EDGE DISCOVERY RESULTS")
        logger.info("=" * 80)

        logger.info(f"\nTests run: {self.tests_run}")
        logger.info(f"Edges found: {len(self.edges_found)}")

        # Registry summary
        logger.info("\n" + "=" * 80)
        logger.info("STRATEGY REGISTRY SUMMARY")
        logger.info("=" * 80)
        logger.info(f"New strategies added: {self.new_strategies_count}")
        logger.info(f"Duplicates skipped: {self.duplicate_strategies_count}")

        registry_stats = self.registry.get_stats()
        logger.info(f"\nRegistry totals:")
        logger.info(f"  - Pending review: {registry_stats['pending']}")
        logger.info(f"  - Accepted: {registry_stats['accepted']}")
        logger.info(f"  - Rejected: {registry_stats['rejected']}")
        logger.info(f"  - Archived: {registry_stats['archived']}")
        logger.info(f"  - TOTAL: {registry_stats['total']}")

        if not self.edges_found:
            logger.info("\nNO EDGES FOUND")
            logger.info(
                "Market appears efficient. All tested hypotheses failed to show significant edge."
            )
            return

        df = self.rank_edges()

        logger.info("\n" + "=" * 80)
        logger.info("TOP 10 BETTING EDGES (Ranked by Strength)")
        logger.info("=" * 80)

        for idx, edge in df.head(10).iterrows():
            # Show registry status
            status_marker = "[NEW]" if edge.get("is_new", False) else "[KNOWN]"

            logger.info(f"\n{'-'*80}")
            logger.info(
                f"EDGE #{df.index.get_loc(idx) + 1}: {edge['name']} {status_marker}"
            )
            logger.info(f"{'-'*80}")
            logger.info(
                f"Win Rate: {edge['win_rate']:.1%} ({edge['wins']}/{edge['sample_size']} bets)"
            )
            logger.info(f"Edge: +{edge['edge']:.1%} above break-even")
            logger.info(
                f"Statistical Significance: {edge['significance']} (p={edge['p_value']:.4f})"
            )
            logger.info(f"Sample: {edge['sample_size']} games ({edge['seasons']})")
            logger.info(f"Strength Score: {edge['score']:.1f}")

            # ROI estimation
            if "roi" in edge:
                logger.info(f"Estimated ROI: +{edge['roi']:.1f}% (at -110 odds)")

            # Registry status
            if "registry_status" in edge:
                logger.info(f"Registry Status: {edge['registry_status']}")

        # Save to CSV
        output_path = Path("reports/bulldog_edges_discovered.csv")
        output_path.parent.mkdir(exist_ok=True)
        df.to_csv(output_path, index=False)
        logger.info(f"\nFull results saved to: {output_path}")

        logger.info("\n" + "=" * 80)
        logger.info("BULLDOG MODE COMPLETE")
        logger.info("=" * 80)
        logger.info(f"\nNext steps:")
        logger.info(
            f"1. Review new strategies in dashboard: python -m streamlit run dashboard/app.py"
        )
        logger.info(f"2. Click the 'STRATEGIES' tab")
        logger.info(
            f"3. Accept or reject the {self.new_strategies_count} pending strategies"
        )


def main():
    """Run bulldog edge discovery."""

    print("\n" + "=" * 80)
    print("BULLDOG MODE: EDGE DISCOVERY")
    print("=" * 80)
    print("\nRELENTLESSLY SEARCHING FOR BETTING EDGES...")
    print("Testing hundreds of hypotheses. Won't stop until edges are found.\n")
    print("=" * 80 + "\n")

    bulldog = BulldogEdgeDiscovery()

    # Show existing registry stats
    registry_stats = bulldog.registry.get_stats()
    print(f"Strategy Registry loaded: {registry_stats['total']} existing strategies")
    print(
        f"  - {registry_stats['pending']} pending | {registry_stats['accepted']} accepted | "
        f"{registry_stats['rejected']} rejected | {registry_stats['archived']} archived"
    )
    print(f"  - Duplicate detection enabled (85% similarity threshold)\n")

    if not bulldog.load_data():
        print("ERROR: Could not load data")
        return

    # Run all tests
    bulldog.test_basic_edges()
    bulldog.test_weather_edges()
    bulldog.test_epa_edges()
    bulldog.test_situational_edges()
    bulldog.test_seasonal_edges()
    bulldog.test_combination_edges()
    bulldog.test_recent_performance_edges()

    # Print results
    bulldog.print_results()


if __name__ == "__main__":
    main()
