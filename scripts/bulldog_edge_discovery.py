"""Research-only NFL hypothesis screening.

This module screens a bounded hypothesis set for statistical associations.  It
never writes candidates into the strategy registry and never calls an
association a profitable betting edge.  Promotion requires a separate,
independent temporal holdout with actual market lines/prices and an executable
strategy definition.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
from scipy import stats

from src.discovery_validation import benjamini_hochberg, wilson_lower_bound
from src.strategy_registry import StrategyRegistry

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

DEFAULT_DATA_PATH = PROJECT_ROOT / "data" / "processed" / "features_2016_2024_improved.parquet"
DEFAULT_REPORT_DIR = PROJECT_ROOT / "reports"


class BulldogEdgeDiscovery:
    """Screen historical hypotheses without changing deployable state."""

    def __init__(
        self,
        data_path: str | Path | None = None,
        registry_path: str | Path | None = None,
        report_dir: str | Path | None = None,
    ):
        self.data_path = Path(data_path) if data_path else DEFAULT_DATA_PATH
        self.report_dir = Path(report_dir) if report_dir else DEFAULT_REPORT_DIR
        self.data: Optional[pd.DataFrame] = None
        self.tests_run = 0
        self.hypotheses: list[dict[str, Any]] = []
        self.research_candidates: list[dict[str, Any]] = []
        # Backward-compatible safety boundary: validated/deployable edges remain empty.
        self.edges_found: list[dict[str, Any]] = []
        self.analysis_window = "all_available_seasons"
        self._finalized = False
        self.registry = StrategyRegistry(registry_path)

    def load_data(self) -> bool:
        """Load historical outcomes and derive research-only targets."""

        logger.info("Loading research data from %s", self.data_path)
        try:
            data = pd.read_parquet(self.data_path)
            required = {"home_score", "away_score", "season"}
            missing = sorted(required - set(data.columns))
            if missing:
                raise ValueError(f"missing required columns: {', '.join(missing)}")

            data = data[
                data["home_score"].notna() & data["away_score"].notna()
            ].copy()
            if data.empty:
                raise ValueError("no completed games are available")

            data["home_win"] = (data["home_score"] > data["away_score"]).astype(int)
            data["point_diff"] = data["home_score"] - data["away_score"]
            data["total_points"] = data["home_score"] + data["away_score"]
            data["home_margin"] = data["point_diff"]
            self.data = data
            logger.info(
                "Loaded %s completed games (%s-%s)",
                len(data),
                data["season"].min(),
                data["season"].max(),
            )
            return True
        except (OSError, ValueError, KeyError, ImportError) as exc:
            logger.error("Could not load research data: %s", exc)
            return False

    def test_hypothesis(
        self,
        name: str,
        condition: pd.Series,
        outcome: pd.Series,
        *,
        min_sample: int = 30,
        family: str = "unspecified",
        outcome_definition: str = "binary historical outcome association",
        null_probability: float = 0.5,
    ) -> Optional[dict[str, Any]]:
        """Record one in-sample association; never promote or estimate ROI."""

        if self.data is None:
            raise RuntimeError("load_data must succeed before testing hypotheses")
        self.tests_run += 1
        self._finalized = False

        mask = pd.Series(condition, index=self.data.index).fillna(False).astype(bool)
        outcome_series = pd.Series(outcome, index=self.data.index)
        valid = mask & outcome_series.notna()
        total = int(valid.sum())
        if total < min_sample:
            return None

        selected = outcome_series[valid]
        invalid_values = set(selected.unique()) - {0, 1, False, True}
        if invalid_values:
            raise ValueError(f"outcome contains non-binary values: {invalid_values}")

        wins = int(selected.astype(int).sum())
        win_rate = wins / total
        p_value = float(
            stats.binomtest(
                wins, total, null_probability, alternative="greater"
            ).pvalue
        )
        sample = self.data.loc[valid]

        result = {
            "test_id": f"{self.analysis_window}:{len(self.hypotheses) + 1}",
            "name": name,
            "family": family,
            "analysis_window": self.analysis_window,
            "sample_size": total,
            "wins": wins,
            "losses": total - wins,
            "win_rate": win_rate,
            "null_probability": null_probability,
            "association_lift": win_rate - null_probability,
            "raw_p_value": p_value,
            "wilson_lower_bound": wilson_lower_bound(wins, total),
            "seasons": f"{sample['season'].min()}-{sample['season'].max()}",
            "outcome_definition": outcome_definition,
            "evidence_status": "research_only",
            "uses_actual_market_prices": False,
            "has_independent_temporal_holdout": False,
            "has_executable_condition": False,
            "promotion_eligible": False,
        }
        self.hypotheses.append(result)
        return result

    def test_basic_edges(self) -> None:
        logger.info("Testing basic historical associations")
        if self.data is None:
            raise RuntimeError("data not loaded")

        if "elo_diff" in self.data.columns:
            self.test_hypothesis(
                "Home Favorites (Elo > 100)",
                self.data["elo_diff"] > 100,
                self.data["home_win"],
                family="moneyline_outcome",
                outcome_definition="home team won outright; no moneyline price evaluated",
            )

        if {"rest_days_home", "rest_days_away"}.issubset(self.data.columns):
            rest_diff = self.data["rest_days_home"] - self.data["rest_days_away"]
            self.test_hypothesis(
                "Home Team: 3+ More Rest Days",
                rest_diff >= 3,
                self.data["home_win"],
                family="moneyline_outcome",
                outcome_definition="home team won outright; no moneyline price evaluated",
            )
            self.test_hypothesis(
                "Away Team: 3+ More Rest Days",
                rest_diff <= -3,
                1 - self.data["home_win"],
                family="moneyline_outcome",
                outcome_definition="away team won outright; no moneyline price evaluated",
            )

        if "post_bye_home" in self.data.columns:
            self.test_hypothesis(
                "Home Team Post-Bye",
                self.data["post_bye_home"] == 1,
                self.data["home_win"],
                family="moneyline_outcome",
                outcome_definition="home team won outright; no moneyline price evaluated",
            )
        if "post_bye_away" in self.data.columns:
            self.test_hypothesis(
                "Away Team Post-Bye",
                self.data["post_bye_away"] == 1,
                1 - self.data["home_win"],
                family="moneyline_outcome",
                outcome_definition="away team won outright; no moneyline price evaluated",
            )
        if "div_game" in self.data.columns:
            self.test_hypothesis(
                "Divisional Games: Home Team",
                self.data["div_game"] == 1,
                self.data["home_win"],
                family="moneyline_outcome",
                outcome_definition="home team won outright; no moneyline price evaluated",
            )
        if "is_dome" in self.data.columns:
            self.test_hypothesis(
                "Dome Games: Home Team",
                self.data["is_dome"] == 1,
                self.data["home_win"],
                family="moneyline_outcome",
                outcome_definition="home team won outright; no moneyline price evaluated",
            )

    def test_weather_edges(self) -> None:
        logger.info("Testing weather/scoring associations")
        if self.data is None:
            raise RuntimeError("data not loaded")

        historical_mean = self.data["total_points"].mean()
        if {"is_cold", "is_windy"}.issubset(self.data.columns):
            self.test_hypothesis(
                "Cold + Windy: Below Dataset Mean Total",
                (self.data["is_cold"] == 1) & (self.data["is_windy"] == 1),
                self.data["total_points"] < historical_mean,
                family="scoring_association",
                outcome_definition=(
                    "total points below the full-dataset mean; this is not a sportsbook "
                    "under result"
                ),
            )
        if "is_dome" in self.data.columns:
            self.test_hypothesis(
                "Dome Games: Above Dataset Mean Total",
                self.data["is_dome"] == 1,
                self.data["total_points"] > historical_mean,
                family="scoring_association",
                outcome_definition=(
                    "total points above the full-dataset mean; this is not a sportsbook "
                    "over result"
                ),
            )
        if "is_cold" in self.data.columns:
            self.test_hypothesis(
                "Cold Weather: Home Win Association",
                self.data["is_cold"] == 1,
                self.data["home_win"],
                family="moneyline_outcome",
                outcome_definition="home team won outright; no moneyline price evaluated",
            )

    def test_epa_edges(self) -> None:
        logger.info("Testing EPA associations")
        if self.data is None:
            raise RuntimeError("data not loaded")

        if {"epa_offense_home", "epa_defense_away"}.issubset(self.data.columns):
            self.test_hypothesis(
                "Strong Home Offense vs Weak Away Defense",
                (self.data["epa_offense_home"] > 0.1)
                & (self.data["epa_defense_away"] < -0.1),
                self.data["home_win"],
                family="moneyline_outcome",
                outcome_definition="home team won outright; no moneyline price evaluated",
            )
        if {"epa_offense_away", "epa_defense_home"}.issubset(self.data.columns):
            self.test_hypothesis(
                "Strong Away Offense vs Weak Home Defense",
                (self.data["epa_offense_away"] > 0.1)
                & (self.data["epa_defense_home"] < -0.1),
                1 - self.data["home_win"],
                family="moneyline_outcome",
                outcome_definition="away team won outright; no moneyline price evaluated",
            )
        if {"epa_explosive_rate_home", "epa_explosive_rate_away"}.issubset(
            self.data.columns
        ):
            self.test_hypothesis(
                "Explosive Offense Present: Above Dataset Median Total",
                (self.data["epa_explosive_rate_home"] > 0.15)
                | (self.data["epa_explosive_rate_away"] > 0.15),
                self.data["total_points"] > self.data["total_points"].median(),
                family="scoring_association",
                outcome_definition=(
                    "total points above the full-dataset median; this is not a "
                    "sportsbook over result"
                ),
            )

    def test_situational_edges(self) -> None:
        logger.info("Testing situational associations")
        if self.data is None:
            raise RuntimeError("data not loaded")

        if "is_back_to_back_home" in self.data.columns:
            self.test_hypothesis(
                "Fade Home Team on Back-to-Back",
                self.data["is_back_to_back_home"] == 1,
                1 - self.data["home_win"],
                family="moneyline_outcome",
                outcome_definition="away team won outright; no moneyline price evaluated",
            )
        if "is_back_to_back_away" in self.data.columns:
            self.test_hypothesis(
                "Bet Home vs Away on Back-to-Back",
                self.data["is_back_to_back_away"] == 1,
                self.data["home_win"],
                family="moneyline_outcome",
                outcome_definition="home team won outright; no moneyline price evaluated",
            )
        if {"injury_count_home", "injury_count_away"}.issubset(self.data.columns):
            injury_diff = self.data["injury_count_home"] - self.data["injury_count_away"]
            self.test_hypothesis(
                "Fade Home Team: 5+ More Injuries",
                injury_diff >= 5,
                1 - self.data["home_win"],
                family="moneyline_outcome",
                outcome_definition="away team won outright; no moneyline price evaluated",
            )
            self.test_hypothesis(
                "Bet Home vs Away: 5+ More Injuries",
                injury_diff <= -5,
                self.data["home_win"],
                family="moneyline_outcome",
                outcome_definition="home team won outright; no moneyline price evaluated",
            )

    def test_seasonal_edges(self) -> None:
        logger.info("Testing seasonal associations")
        if self.data is None:
            raise RuntimeError("data not loaded")
        if "week" not in self.data.columns:
            return

        if "elo_diff" in self.data.columns:
            self.test_hypothesis(
                "Early Season: Home Favorites",
                (self.data["week"] <= 4) & (self.data["elo_diff"] > 50),
                self.data["home_win"],
                family="moneyline_outcome",
                outcome_definition="home team won outright; no moneyline price evaluated",
            )
        if {"win_pct_home", "win_pct_away"}.issubset(self.data.columns):
            self.test_hypothesis(
                "Late Season: Winning Home vs Losing Away",
                (self.data["week"] >= 15)
                & (self.data["win_pct_home"] > 0.6)
                & (self.data["win_pct_away"] < 0.4),
                self.data["home_win"],
                family="moneyline_outcome",
                outcome_definition="home team won outright; no moneyline price evaluated",
            )

    def test_combination_edges(self) -> None:
        logger.info("Testing combination associations")
        if self.data is None:
            raise RuntimeError("data not loaded")

        if {"rest_days_home", "rest_days_away", "post_bye_home"}.issubset(
            self.data.columns
        ):
            rest_diff = self.data["rest_days_home"] - self.data["rest_days_away"]
            self.test_hypothesis(
                "Home Post-Bye + 3+ Rest Advantage",
                (rest_diff >= 3) & (self.data["post_bye_home"] == 1),
                self.data["home_win"],
                family="moneyline_outcome",
                outcome_definition="home team won outright; no moneyline price evaluated",
            )
        if {"is_dome", "epa_offense_home", "epa_defense_away"}.issubset(
            self.data.columns
        ):
            self.test_hypothesis(
                "Dome + Strong Home Offense vs Weak Away Defense",
                (self.data["is_dome"] == 1)
                & (self.data["epa_offense_home"] > 0.1)
                & (self.data["epa_defense_away"] < -0.1),
                self.data["home_win"],
                family="moneyline_outcome",
                outcome_definition="home team won outright; no moneyline price evaluated",
            )
        if {"div_game", "elo_diff"}.issubset(self.data.columns):
            self.test_hypothesis(
                "Divisional Game: Home Elo Underdog",
                (self.data["div_game"] == 1) & (self.data["elo_diff"] < -50),
                self.data["home_win"],
                family="moneyline_outcome",
                outcome_definition="home team won outright; no moneyline price evaluated",
            )

    def test_recent_performance_edges(self) -> None:
        """Repeat selected screens on recent seasons without treating them as holdout."""

        if self.data is None:
            raise RuntimeError("data not loaded")
        recent = self.data[self.data["season"] >= 2023].copy()
        if len(recent) < 100:
            logger.warning("Not enough recent data for the recent-window screen")
            return

        original_data = self.data
        original_window = self.analysis_window
        try:
            self.data = recent
            self.analysis_window = "recent_2023_plus_reused_for_screening"
            self.test_basic_edges()
            self.test_weather_edges()
            self.test_epa_edges()
        finally:
            self.data = original_data
            self.analysis_window = original_window

    def finalize_results(self, max_adjusted_p_value: float = 0.05) -> list[dict[str, Any]]:
        """Apply FDR correction and classify research candidates read-only."""

        if not self.hypotheses:
            self.research_candidates = []
            self._finalized = True
            return []

        adjusted = benjamini_hochberg(
            result["raw_p_value"] for result in self.hypotheses
        )
        candidates: list[dict[str, Any]] = []
        for result, adjusted_p_value in zip(self.hypotheses, adjusted):
            result["adjusted_p_value"] = adjusted_p_value
            result["passes_fdr_screen"] = (
                adjusted_p_value <= max_adjusted_p_value
                and result["association_lift"] > 0
            )
            result["promotion_blockers"] = (
                "same sample used for screening and estimation; "
                "no independent temporal holdout; actual market line/price absent; "
                "condition not serialized as executable code"
            )
            if result["passes_fdr_screen"]:
                candidate = dict(result)
                similar = self.registry.find_similar_strategy(
                    candidate["name"], candidate["name"], threshold=0.85
                )
                candidate["registry_match"] = (
                    f"{similar.strategy_id} ({similar.name})" if similar else "none"
                )
                candidates.append(candidate)

        self.research_candidates = candidates
        self.edges_found = []
        self._finalized = True
        return candidates

    def rank_candidates(self) -> pd.DataFrame:
        if not self._finalized:
            self.finalize_results()
        if not self.research_candidates:
            return pd.DataFrame()
        frame = pd.DataFrame(self.research_candidates)
        return frame.sort_values(
            ["wilson_lower_bound", "adjusted_p_value", "sample_size"],
            ascending=[False, True, False],
        )

    def print_results(self) -> None:
        if not self._finalized:
            self.finalize_results()

        logger.info("\n%s", "=" * 80)
        logger.info("BULLDOG RESEARCH SCREEN RESULTS")
        logger.info("%s", "=" * 80)
        logger.info("Tests attempted: %s", self.tests_run)
        logger.info("Evaluable hypotheses: %s", len(self.hypotheses))
        logger.info("FDR-passing research candidates: %s", len(self.research_candidates))
        logger.info("Registry writes: 0 (enforced)")

        self.report_dir.mkdir(parents=True, exist_ok=True)
        all_path = self.report_dir / "bulldog_hypotheses_all.csv"
        pd.DataFrame(self.hypotheses).to_csv(all_path, index=False)

        ranked = self.rank_candidates()
        candidate_path = self.report_dir / "bulldog_research_candidates.csv"
        ranked.to_csv(candidate_path, index=False)

        if ranked.empty:
            logger.info("No associations survived the FDR screen.")
        else:
            logger.info("\nTop research candidates (not betting recommendations):")
            for rank, (_, candidate) in enumerate(ranked.head(10).iterrows(), start=1):
                logger.info(
                    "%s. %s | WR %.1f%% | n=%s | adjusted p=%.4g | Wilson LB=%.1f%%",
                    rank,
                    candidate["name"],
                    candidate["win_rate"] * 100,
                    candidate["sample_size"],
                    candidate["adjusted_p_value"],
                    candidate["wilson_lower_bound"] * 100,
                )

        logger.info("All hypothesis results: %s", all_path)
        logger.info("Research candidates: %s", candidate_path)
        logger.info(
            "Promotion remains blocked until a separate temporal holdout is tested "
            "against actual market lines/prices with an executable condition."
        )


def main() -> None:
    print("\n" + "=" * 80)
    print("BULLDOG RESEARCH-ONLY HYPOTHESIS SCREEN")
    print("=" * 80)
    print("No strategy-registry writes and no profitability claims are permitted.\n")

    bulldog = BulldogEdgeDiscovery()
    registry_stats = bulldog.registry.get_stats()
    print(
        "Strategy Registry loaded read-only: "
        f"{registry_stats['total']} records; {registry_stats['deployable']} evidence-deployable"
    )

    if not bulldog.load_data():
        raise SystemExit("Could not load historical data")

    bulldog.test_basic_edges()
    bulldog.test_weather_edges()
    bulldog.test_epa_edges()
    bulldog.test_situational_edges()
    bulldog.test_seasonal_edges()
    bulldog.test_combination_edges()
    bulldog.test_recent_performance_edges()
    bulldog.finalize_results()
    bulldog.print_results()


if __name__ == "__main__":
    main()
