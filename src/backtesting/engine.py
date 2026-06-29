"""Walk-forward backtesting engine.

Simulates betting on historical games with realistic constraints.
Supports single-pass backtesting and Monte Carlo confidence intervals.
"""

import logging
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd

from src.betting.kelly import KellyCriterion

logger = logging.getLogger(__name__)


class BacktestEngine:
    """Walk-forward backtest with Kelly criterion."""

    def __init__(self, initial_bankroll: float = 10000, config: dict = None):
        self.initial_bankroll = initial_bankroll
        self.config = config or {}

        self.kelly = KellyCriterion(
            kelly_fraction=self.config.get("kelly_fraction", 0.25),
            min_edge=self.config.get("min_edge", 0.02),
            min_probability=self.config.get("min_probability", 0.55),
            max_bet_pct=self.config.get("max_bet_size", 0.02),
        )

        self.reset()

    def reset(self):
        """Reset state."""
        self.bankroll = self.initial_bankroll
        self.history: List[Dict] = []
        self.bet_count = 0
        self.win_count = 0

    def run_backtest(self, predictions_df: pd.DataFrame) -> Tuple[Dict, pd.DataFrame]:
        """
        Run backtest on predictions.

        Args:
            predictions_df: DataFrame with game_id, gameday, home_team, away_team,
                pred_prob (0-1), actual (0 or 1), odds (decimal).

        Returns:
            (metrics_dict, history_df)
        """
        self.reset()

        logger.info("Running backtest on %d games...", len(predictions_df))

        predictions_df = predictions_df.sort_values("gameday")

        for _, row in predictions_df.iterrows():
            bet_size = self.kelly.calculate_bet_size(
                prob_win=row["pred_prob"], odds=row["odds"], bankroll=self.bankroll
            )

            if bet_size <= 0:
                continue

            self.bet_count += 1

            if row["actual"] == 1:
                profit = bet_size * (row["odds"] - 1)
                self.win_count += 1
                result = "win"
            else:
                profit = -bet_size
                result = "loss"

            self.bankroll += profit

            edge = row["pred_prob"] - (1.0 / row["odds"])

            self.history.append(
                {
                    "game_id": row["game_id"],
                    "gameday": row["gameday"],
                    "home_team": row.get("home_team", ""),
                    "away_team": row.get("away_team", ""),
                    "bet_size": bet_size,
                    "odds": row["odds"],
                    "pred_prob": row["pred_prob"],
                    "actual": row["actual"],
                    "result": result,
                    "profit": profit,
                    "bankroll": self.bankroll,
                    "edge": edge,
                }
            )

        metrics, history_df = self._calculate_metrics()

        logger.info(
            "Backtest complete: %d bets, %d wins", self.bet_count, self.win_count
        )

        return metrics, history_df

    def run_monte_carlo(
        self,
        predictions_df: pd.DataFrame,
        n_simulations: int = 1000,
        seed: int = 42,
    ) -> Dict:
        """
        Run Monte Carlo simulation by resampling bet outcomes.

        Returns distribution of ROI, max drawdown, and final bankroll across
        `n_simulations` bootstrap samples of the bet history.
        """
        base_metrics, base_history = self.run_backtest(predictions_df)
        if not self.history:
            return {"error": "No bets to simulate", "base_metrics": base_metrics}

        rng = np.random.default_rng(seed)
        profits = np.array([h["profit"] for h in self.history])
        n_bets = len(profits)

        sim_rois = []
        sim_drawdowns = []
        sim_finals = []

        for _ in range(n_simulations):
            indices = rng.choice(n_bets, size=n_bets, replace=True)
            sim_profits = profits[indices]
            sim_bankroll = np.cumsum(sim_profits) + self.initial_bankroll

            final = float(sim_bankroll[-1])
            roi = (final - self.initial_bankroll) / self.initial_bankroll * 100.0

            cummax = np.maximum.accumulate(sim_bankroll)
            drawdowns = (sim_bankroll - cummax) / cummax
            max_dd = float(drawdowns.min()) * 100.0

            sim_rois.append(roi)
            sim_drawdowns.append(max_dd)
            sim_finals.append(final)

        sim_rois = np.array(sim_rois)
        sim_drawdowns = np.array(sim_drawdowns)
        sim_finals = np.array(sim_finals)

        return {
            "base_metrics": base_metrics,
            "n_simulations": n_simulations,
            "roi_mean": float(sim_rois.mean()),
            "roi_median": float(np.median(sim_rois)),
            "roi_ci_5": float(np.percentile(sim_rois, 5)),
            "roi_ci_95": float(np.percentile(sim_rois, 95)),
            "max_drawdown_mean": float(sim_drawdowns.mean()),
            "max_drawdown_ci_5": float(np.percentile(sim_drawdowns, 5)),
            "max_drawdown_ci_95": float(np.percentile(sim_drawdowns, 95)),
            "final_bankroll_mean": float(sim_finals.mean()),
            "final_bankroll_ci_5": float(np.percentile(sim_finals, 5)),
            "final_bankroll_ci_95": float(np.percentile(sim_finals, 95)),
            "prob_profitable": float((sim_rois > 0).mean()),
        }

    def _calculate_metrics(self) -> Tuple[Dict, pd.DataFrame]:
        """Calculate performance metrics."""
        if not self.history:
            return {"error": "No bets placed"}, pd.DataFrame()

        history_df = pd.DataFrame(self.history)

        total_profit = self.bankroll - self.initial_bankroll
        roi = (total_profit / self.initial_bankroll) * 100
        win_rate = (self.win_count / self.bet_count) * 100

        history_df["cumulative_max"] = history_df["bankroll"].cummax()
        history_df["drawdown"] = (
            history_df["bankroll"] - history_df["cumulative_max"]
        ) / history_df["cumulative_max"]
        max_drawdown = history_df["drawdown"].min() * 100

        returns = history_df["profit"] / history_df["bet_size"]
        n_weeks = max(1, history_df["gameday"].nunique())
        sharpe = (
            (returns.mean() / returns.std()) * np.sqrt(n_weeks)
            if returns.std() > 0
            else 0
        )

        avg_edge = history_df["edge"].mean() * 100
        positive_edge_pct = (history_df["edge"] > 0).sum() / len(history_df) * 100

        metrics = {
            "total_bets": self.bet_count,
            "wins": self.win_count,
            "losses": self.bet_count - self.win_count,
            "win_rate": win_rate,
            "total_profit": total_profit,
            "roi": roi,
            "max_drawdown": max_drawdown,
            "sharpe_ratio": sharpe,
            "final_bankroll": self.bankroll,
            "avg_edge": avg_edge,
            "positive_edge_pct": positive_edge_pct,
        }

        return metrics, history_df
