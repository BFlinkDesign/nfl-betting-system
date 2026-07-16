"""Pure validation primitives for betting-strategy promotion decisions."""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import NormalDist
from typing import Iterable, Sequence


@dataclass(frozen=True)
class PromotionPolicy:
    """Minimum evidence required before a candidate can leave research status."""

    min_discovery_sample: int = 100
    min_holdout_sample: int = 50
    max_adjusted_p_value: float = 0.05
    break_even_probability: float = 0.524
    min_holdout_roi: float = 0.0
    confidence_level: float = 0.95


@dataclass(frozen=True)
class PromotionDecision:
    eligible: bool
    blockers: tuple[str, ...]
    holdout_wilson_lower_bound: float


def american_to_decimal(american_odds: float) -> float:
    """Convert American odds to decimal odds with strict validation."""

    if isinstance(american_odds, bool) or not isinstance(american_odds, (int, float)):
        raise ValueError("american_odds must be numeric")
    odds = float(american_odds)
    if not math.isfinite(odds) or odds == 0:
        raise ValueError("american_odds must be finite and non-zero")
    if odds > 0:
        return 1.0 + odds / 100.0
    return 1.0 + 100.0 / abs(odds)


def flat_stake_roi(outcomes: Sequence[int], decimal_odds: Sequence[float]) -> float:
    """Calculate flat-stake ROI; outcomes are 1=win, 0=loss, -1=push."""

    if len(outcomes) != len(decimal_odds):
        raise ValueError("outcomes and decimal_odds must have equal length")
    if not outcomes:
        raise ValueError("at least one outcome is required")

    total_staked = 0.0
    profit = 0.0
    for outcome, raw_odds in zip(outcomes, decimal_odds):
        if outcome not in (-1, 0, 1):
            raise ValueError("outcomes must use 1=win, 0=loss, -1=push")
        odds = float(raw_odds)
        if not math.isfinite(odds) or odds <= 1.0:
            raise ValueError("decimal odds must be finite and greater than 1.0")
        if outcome == -1:
            continue
        total_staked += 1.0
        profit += odds - 1.0 if outcome == 1 else -1.0

    if total_staked == 0:
        raise ValueError("ROI is undefined when every result is a push")
    return profit / total_staked


def benjamini_hochberg(p_values: Iterable[float]) -> list[float]:
    """Return Benjamini-Hochberg false-discovery-rate adjusted p-values."""

    values = [float(value) for value in p_values]
    if not values:
        return []
    for value in values:
        if not math.isfinite(value) or not 0.0 <= value <= 1.0:
            raise ValueError("p-values must be finite values between 0 and 1")

    count = len(values)
    ordered = sorted(enumerate(values), key=lambda item: item[1])
    adjusted_sorted = [0.0] * count
    running_min = 1.0
    for reverse_index in range(count - 1, -1, -1):
        _, p_value = ordered[reverse_index]
        rank = reverse_index + 1
        candidate = min(1.0, p_value * count / rank)
        running_min = min(running_min, candidate)
        adjusted_sorted[reverse_index] = running_min

    adjusted = [0.0] * count
    for ordered_index, (original_index, _) in enumerate(ordered):
        adjusted[original_index] = adjusted_sorted[ordered_index]
    return adjusted


def wilson_lower_bound(wins: int, total: int, confidence_level: float = 0.95) -> float:
    """Lower bound of a two-sided Wilson score interval for a binomial rate."""

    if isinstance(wins, bool) or isinstance(total, bool):
        raise ValueError("wins and total must be integers")
    if not isinstance(wins, int) or not isinstance(total, int):
        raise ValueError("wins and total must be integers")
    if total <= 0 or wins < 0 or wins > total:
        raise ValueError("require 0 <= wins <= total and total > 0")
    if not 0.0 < confidence_level < 1.0:
        raise ValueError("confidence_level must be between 0 and 1")

    z_score = NormalDist().inv_cdf(1.0 - (1.0 - confidence_level) / 2.0)
    proportion = wins / total
    denominator = 1.0 + z_score**2 / total
    center = proportion + z_score**2 / (2.0 * total)
    margin = z_score * math.sqrt(
        proportion * (1.0 - proportion) / total + z_score**2 / (4.0 * total**2)
    )
    return (center - margin) / denominator


def assess_promotion(
    *,
    discovery_sample_size: int,
    holdout_sample_size: int,
    holdout_wins: int,
    holdout_roi: float,
    adjusted_p_value: float,
    uses_actual_market_prices: bool,
    has_temporal_holdout: bool,
    has_reproducible_condition: bool,
    policy: PromotionPolicy | None = None,
) -> PromotionDecision:
    """Fail closed unless every evidence and reproducibility gate passes."""

    policy = policy or PromotionPolicy()
    blockers: list[str] = []

    if discovery_sample_size < policy.min_discovery_sample:
        blockers.append(
            f"discovery sample {discovery_sample_size} < {policy.min_discovery_sample}"
        )
    if holdout_sample_size < policy.min_holdout_sample:
        blockers.append(
            f"holdout sample {holdout_sample_size} < {policy.min_holdout_sample}"
        )
    if not 0 <= holdout_wins <= holdout_sample_size:
        raise ValueError("holdout_wins must be between zero and holdout_sample_size")
    if not math.isfinite(float(holdout_roi)):
        raise ValueError("holdout_roi must be finite")
    if not math.isfinite(float(adjusted_p_value)) or not 0 <= adjusted_p_value <= 1:
        raise ValueError("adjusted_p_value must be between 0 and 1")

    lower_bound = (
        wilson_lower_bound(holdout_wins, holdout_sample_size, policy.confidence_level)
        if holdout_sample_size > 0
        else 0.0
    )

    if adjusted_p_value > policy.max_adjusted_p_value:
        blockers.append(
            f"adjusted p-value {adjusted_p_value:.4f} > "
            f"{policy.max_adjusted_p_value:.4f}"
        )
    if lower_bound <= policy.break_even_probability:
        blockers.append(
            f"holdout Wilson lower bound {lower_bound:.4f} <= break-even "
            f"{policy.break_even_probability:.4f}"
        )
    if holdout_roi <= policy.min_holdout_roi:
        blockers.append(
            f"holdout ROI {holdout_roi:.4f} <= {policy.min_holdout_roi:.4f}"
        )
    if not uses_actual_market_prices:
        blockers.append("actual market prices were not used")
    if not has_temporal_holdout:
        blockers.append("independent temporal holdout is missing")
    if not has_reproducible_condition:
        blockers.append("strategy condition is not executable and reproducible")

    return PromotionDecision(
        eligible=not blockers,
        blockers=tuple(blockers),
        holdout_wilson_lower_bound=lower_bound,
    )
