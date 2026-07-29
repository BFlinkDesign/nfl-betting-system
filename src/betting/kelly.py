"""Conservative Kelly analysis with an explicit execution authority boundary.

The previous implementation amplified favorite bets and recent winning streaks
using historical claims that are not independently reproducible. This module
removes those multipliers. It can calculate a capped analytical fraction from a
qualified probability lower bound, but dollar bet sizing is blocked unless the
caller explicitly enters live mode, supplies live-validated evidence, and
provides one-time execution authorization.
"""

from __future__ import annotations

import math
from typing import Optional

QUALIFIED_ANALYSIS_STATUSES = frozenset(
    {"out_of_sample_validated", "paper_trading", "live_validated"}
)


class BetSizingBlockedError(RuntimeError):
    """Raised when a caller attempts actionable sizing without authority."""


class KellyCriterion:
    """Fail-closed fractional Kelly calculator."""

    def __init__(
        self,
        kelly_fraction: float = 0.25,
        min_edge: float = 0.02,
        min_probability: float = 0.55,
        max_bet_pct: float = 0.02,
        aggressive_mode: bool = False,
        deployment_mode: str = "paper",
    ) -> None:
        if aggressive_mode:
            raise ValueError(
                "aggressive_mode was removed: favorite and hot-streak multipliers "
                "are not supported by reproducible evidence"
            )
        for name, value in {
            "kelly_fraction": kelly_fraction,
            "min_edge": min_edge,
            "min_probability": min_probability,
            "max_bet_pct": max_bet_pct,
        }.items():
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"{name} must be numeric")
            if not math.isfinite(float(value)):
                raise ValueError(f"{name} must be finite")
        if not 0.0 < float(kelly_fraction) <= 1.0:
            raise ValueError("kelly_fraction must be greater than zero and at most one")
        if not 0.0 <= float(min_edge) < 1.0:
            raise ValueError("min_edge must be between zero and one")
        if not 0.0 < float(min_probability) < 1.0:
            raise ValueError("min_probability must be between zero and one")
        if not 0.0 < float(max_bet_pct) <= 0.02:
            raise ValueError("max_bet_pct must be greater than zero and at most 2%")
        if deployment_mode not in {"paper", "live"}:
            raise ValueError("deployment_mode must be 'paper' or 'live'")

        self.kelly_fraction = float(kelly_fraction)
        self.min_edge = float(min_edge)
        self.min_probability = float(min_probability)
        self.max_bet_pct = float(max_bet_pct)
        self.deployment_mode = deployment_mode

    @staticmethod
    def _validate_probability(value: float, name: str) -> float:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"{name} must be numeric")
        probability = float(value)
        if not math.isfinite(probability) or not 0.0 <= probability <= 1.0:
            raise ValueError(f"{name} must be between zero and one")
        return probability

    @staticmethod
    def _validate_decimal_odds(odds: float) -> float:
        if isinstance(odds, bool) or not isinstance(odds, (int, float)):
            raise ValueError("odds must be numeric decimal odds")
        decimal_odds = float(odds)
        if not math.isfinite(decimal_odds) or decimal_odds <= 1.0:
            raise ValueError("odds must be finite decimal odds greater than one")
        return decimal_odds

    def calculate_fraction(
        self,
        prob_win: float,
        odds: float,
        *,
        probability_lower_bound: float,
        evidence_status: str,
        recent_performance: Optional[dict] = None,
    ) -> float:
        """Calculate a non-actionable fraction using conservative evidence.

        The result is an analysis value only. It cannot authorize a wager.
        """

        if recent_performance is not None:
            raise ValueError(
                "recent-performance or hot-streak multipliers are prohibited"
            )
        point_probability = self._validate_probability(prob_win, "prob_win")
        lower_probability = self._validate_probability(
            probability_lower_bound, "probability_lower_bound"
        )
        if lower_probability > point_probability:
            raise ValueError("probability_lower_bound cannot exceed prob_win")
        decimal_odds = self._validate_decimal_odds(odds)
        if evidence_status not in QUALIFIED_ANALYSIS_STATUSES:
            return 0.0
        if lower_probability < self.min_probability:
            return 0.0

        implied_probability = 1.0 / decimal_odds
        edge = lower_probability - implied_probability
        if edge < self.min_edge:
            return 0.0

        net_odds = decimal_odds - 1.0
        full_kelly = (
            lower_probability * net_odds - (1.0 - lower_probability)
        ) / net_odds
        fraction = max(0.0, full_kelly * self.kelly_fraction)
        return min(fraction, self.max_bet_pct)

    def calculate_bet_size(
        self,
        prob_win: float,
        odds: float,
        bankroll: float,
        recent_performance: Optional[dict] = None,
        *,
        probability_lower_bound: Optional[float] = None,
        evidence_status: str = "unverified",
        live_wager_authorized: bool = False,
    ) -> float:
        """Calculate dollars only under explicit live authority and evidence.

        Paper/research mode raises instead of returning a number that downstream
        code could silently reinterpret as permission to wager.
        """

        if self.deployment_mode != "live":
            raise BetSizingBlockedError(
                "dollar bet sizing is disabled while deployment_mode is not live"
            )
        if not live_wager_authorized:
            raise BetSizingBlockedError("live wager authorization is missing")
        if evidence_status != "live_validated":
            raise BetSizingBlockedError(
                "live sizing requires evidence_status='live_validated'"
            )
        if probability_lower_bound is None:
            raise BetSizingBlockedError(
                "live sizing requires a validated probability lower bound"
            )
        if isinstance(bankroll, bool) or not isinstance(bankroll, (int, float)):
            raise ValueError("bankroll must be numeric")
        bankroll_value = float(bankroll)
        if not math.isfinite(bankroll_value) or bankroll_value <= 0.0:
            raise ValueError("bankroll must be finite and greater than zero")

        fraction = self.calculate_fraction(
            prob_win,
            odds,
            probability_lower_bound=probability_lower_bound,
            evidence_status=evidence_status,
            recent_performance=recent_performance,
        )
        return bankroll_value * fraction
