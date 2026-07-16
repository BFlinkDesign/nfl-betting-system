"""Provenance-bound paper backtesting engine.

The engine requires a conservative probability lower bound, qualified evidence
status, actual offered decimal odds, and run-level provenance. It produces a
paper simulation only. Missing evidence becomes ``NO_BET`` rather than a
manufactured stake.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd
from src.betting.decision_contracts import PAPER_AUTHORITY
from src.betting.kelly import KellyCriterion

_REQUIRED_COLUMNS = frozenset(
    {
        "game_id",
        "gameday",
        "pred_prob",
        "probability_lower_bound",
        "actual",
        "odds",
        "evidence_status",
    }
)
_REQUIRED_PROVENANCE = ("source_commit", "dataset_snapshot_id", "evaluation_id")


class BacktestContractError(ValueError):
    """Raised when a paper backtest lacks required evidence."""


def _finite_float(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float, np.number)):
        raise BacktestContractError(f"{field_name} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise BacktestContractError(f"{field_name} must be finite")
    return number


class BacktestEngine:
    """Deterministic forward-ordered paper simulation."""

    def __init__(
        self, initial_bankroll: float = 10000.0, config: Optional[dict] = None
    ) -> None:
        self.initial_bankroll = _finite_float(initial_bankroll, "initial_bankroll")
        if self.initial_bankroll <= 0:
            raise BacktestContractError("initial_bankroll must be greater than zero")
        self.config = dict(config or {})
        missing = [key for key in _REQUIRED_PROVENANCE if not self.config.get(key)]
        if missing:
            raise BacktestContractError(
                "missing run provenance: " + ", ".join(sorted(missing))
            )

        max_bet_pct = _finite_float(
            self.config.get("max_bet_size", 0.005), "max_bet_size"
        )
        if not 0 < max_bet_pct <= 0.02:
            raise BacktestContractError(
                "max_bet_size must be greater than zero and at most 2%"
            )
        self.kelly = KellyCriterion(
            kelly_fraction=self.config.get("kelly_fraction", 0.25),
            min_edge=self.config.get("min_edge", 0.02),
            min_probability=self.config.get("min_probability", 0.55),
            max_bet_pct=max_bet_pct,
            deployment_mode="paper",
        )
        self.reset()

    def reset(self) -> None:
        self.bankroll = self.initial_bankroll
        self.history: list[dict[str, Any]] = []
        self.paper_track_count = 0
        self.win_count = 0

    def run_backtest(self, predictions_df: pd.DataFrame) -> Tuple[Dict, pd.DataFrame]:
        if not isinstance(predictions_df, pd.DataFrame):
            raise BacktestContractError("predictions_df must be a pandas DataFrame")
        missing_columns = sorted(_REQUIRED_COLUMNS - set(predictions_df.columns))
        if missing_columns:
            raise BacktestContractError(
                "missing prediction columns: " + ", ".join(missing_columns)
            )

        self.reset()
        ordered = predictions_df.copy(deep=True).sort_values(
            ["gameday", "game_id"], kind="mergesort"
        )

        for _, row in ordered.iterrows():
            point = _finite_float(row["pred_prob"], "pred_prob")
            lower = _finite_float(
                row["probability_lower_bound"], "probability_lower_bound"
            )
            odds = _finite_float(row["odds"], "odds")
            if not 0 <= lower <= point <= 1:
                raise BacktestContractError(
                    "probabilities must satisfy 0 <= lower_bound <= point <= 1"
                )
            if odds <= 1:
                raise BacktestContractError(
                    "odds must be decimal odds greater than one"
                )
            actual = int(row["actual"])
            if actual not in {0, 1}:
                raise BacktestContractError("actual must be 0 or 1")

            fraction = self.kelly.calculate_fraction(
                point,
                odds,
                probability_lower_bound=lower,
                evidence_status=str(row["evidence_status"]),
            )
            stake = self.bankroll * fraction
            status = "PAPER_TRACK" if stake > 0 else "NO_BET"
            result = "no_bet"
            profit = 0.0
            if stake > 0:
                self.paper_track_count += 1
                if actual == 1:
                    profit = stake * (odds - 1.0)
                    self.win_count += 1
                    result = "win"
                else:
                    profit = -stake
                    result = "loss"
                self.bankroll += profit

            closing_price_value: Optional[float] = None
            if "closing_odds" in ordered.columns and pd.notna(row.get("closing_odds")):
                closing_odds = _finite_float(row["closing_odds"], "closing_odds")
                if closing_odds <= 1:
                    raise BacktestContractError(
                        "closing_odds must be decimal odds greater than one"
                    )
                closing_price_value = odds / closing_odds - 1.0

            self.history.append(
                {
                    "game_id": row["game_id"],
                    "gameday": row["gameday"],
                    "home_team": row.get("home_team", ""),
                    "away_team": row.get("away_team", ""),
                    "decision_status": status,
                    "paper_stake": stake,
                    "odds": odds,
                    "pred_prob": point,
                    "probability_lower_bound": lower,
                    "evidence_status": str(row["evidence_status"]),
                    "actual": actual,
                    "result": result,
                    "profit": profit,
                    "bankroll": self.bankroll,
                    "closing_price_value": closing_price_value,
                    "authority": PAPER_AUTHORITY,
                }
            )

        return self._calculate_metrics()

    def _calculate_metrics(self) -> Tuple[Dict, pd.DataFrame]:
        history_df = pd.DataFrame(self.history)
        if history_df.empty:
            return self._empty_metrics(), history_df

        tracked = history_df[history_df["decision_status"] == "PAPER_TRACK"].copy()
        total_staked = float(tracked["paper_stake"].sum()) if not tracked.empty else 0.0
        total_profit = float(tracked["profit"].sum()) if not tracked.empty else 0.0
        roi = total_profit / total_staked * 100 if total_staked > 0 else 0.0
        win_rate = (
            self.win_count / self.paper_track_count * 100
            if self.paper_track_count > 0
            else 0.0
        )

        bankroll_path = pd.Series(
            [self.initial_bankroll, *history_df["bankroll"].astype(float).tolist()]
        )
        running_max = bankroll_path.cummax()
        drawdowns = (bankroll_path - running_max) / running_max
        max_drawdown = float(drawdowns.min() * 100)

        returns = (
            tracked["profit"] / tracked["paper_stake"]
            if not tracked.empty
            else pd.Series(dtype=float)
        )
        return_mean_over_std = (
            float(returns.mean() / returns.std(ddof=1))
            if len(returns) > 1 and returns.std(ddof=1) > 0
            else None
        )
        closing_values = history_df["closing_price_value"].dropna()
        avg_closing_price_value = (
            float(closing_values.mean() * 100) if not closing_values.empty else None
        )

        metrics = {
            "status": "PAPER_SIMULATION",
            "authority": PAPER_AUTHORITY,
            "live_wagers_authorized": False,
            "source_commit": self.config["source_commit"],
            "dataset_snapshot_id": self.config["dataset_snapshot_id"],
            "evaluation_id": self.config["evaluation_id"],
            "total_candidates": len(history_df),
            "paper_tracks": self.paper_track_count,
            "no_bets": len(history_df) - self.paper_track_count,
            "wins": self.win_count,
            "losses": self.paper_track_count - self.win_count,
            "win_rate": win_rate,
            "total_staked": total_staked,
            "total_profit": total_profit,
            "roi_on_staked_capital": roi,
            "max_drawdown": max_drawdown,
            "return_mean_over_std": return_mean_over_std,
            "sharpe_ratio": None,
            "sharpe_blocker": "betting cadence and risk-free convention not defined",
            "final_bankroll": self.bankroll,
            "avg_closing_price_value": avg_closing_price_value,
        }
        return metrics, history_df

    def _empty_metrics(self) -> Dict[str, Any]:
        return {
            "status": "PAPER_SIMULATION",
            "authority": PAPER_AUTHORITY,
            "live_wagers_authorized": False,
            "source_commit": self.config["source_commit"],
            "dataset_snapshot_id": self.config["dataset_snapshot_id"],
            "evaluation_id": self.config["evaluation_id"],
            "total_candidates": 0,
            "paper_tracks": 0,
            "no_bets": 0,
            "wins": 0,
            "losses": 0,
            "win_rate": 0.0,
            "total_staked": 0.0,
            "total_profit": 0.0,
            "roi_on_staked_capital": 0.0,
            "max_drawdown": 0.0,
            "return_mean_over_std": None,
            "sharpe_ratio": None,
            "sharpe_blocker": "no paper-tracked decisions",
            "final_bankroll": self.bankroll,
            "avg_closing_price_value": None,
        }
