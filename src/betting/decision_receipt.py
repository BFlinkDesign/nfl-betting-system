"""Fail-closed market decision receipts for research and paper trading.

This module intentionally does not place wagers. It converts a user intent, an
actual bookmaker market snapshot, and a provenance-bound probability estimate
into BLOCKED, NO_BET, or PAPER_CANDIDATE.

The design forbids synthetic odds, forced bets, silent market reinterpretation,
and naive multiplication of parlay-leg probabilities.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, fields, is_dataclass
from datetime import datetime, timezone
from enum import Enum
from functools import reduce
from operator import mul
from typing import Any, Mapping, Sequence

_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
_COMMIT_RE = re.compile(r"^[0-9a-fA-F]{7,64}$")
_CLOCK_SKEW_SECONDS = 5.0


class UserIntent(str, Enum):
    INFORMATION = "information"
    PAPER_BET_EVALUATION = "paper_bet_evaluation"
    LIVE_BET_REQUEST = "live_bet_request"


class EvidenceStatus(str, Enum):
    UNVERIFIED = "unverified"
    RESEARCH_ONLY = "research_only"
    OUT_OF_SAMPLE_VALIDATED = "out_of_sample_validated"
    PAPER_TRADING = "paper_trading"
    LIVE_VALIDATED = "live_validated"


_EVIDENCE_RANK = {
    EvidenceStatus.UNVERIFIED: 0,
    EvidenceStatus.RESEARCH_ONLY: 1,
    EvidenceStatus.OUT_OF_SAMPLE_VALIDATED: 2,
    EvidenceStatus.PAPER_TRADING: 3,
    EvidenceStatus.LIVE_VALIDATED: 4,
}


class MarketStatus(str, Enum):
    OPEN = "open"
    SUSPENDED = "suspended"
    CLOSED = "closed"


class DecisionCode(str, Enum):
    BLOCKED = "BLOCKED"
    NO_BET = "NO_BET"
    PAPER_CANDIDATE = "PAPER_CANDIDATE"


def _require_nonempty(value: str, name: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")


def _require_aware(value: datetime, name: str) -> None:
    if (
        not isinstance(value, datetime)
        or value.tzinfo is None
        or value.utcoffset() is None
    ):
        raise ValueError(f"{name} must be a timezone-aware datetime")


def _require_probability(value: float, name: str) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    if not math.isfinite(float(value)) or not 0.0 < float(value) < 1.0:
        raise ValueError(f"{name} must be strictly between 0 and 1")


def _require_american_odds(value: float, name: str = "american_odds") -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    odds = float(value)
    if not math.isfinite(odds) or odds == 0 or abs(odds) < 100:
        raise ValueError(f"{name} must be finite American odds with abs(value) >= 100")


def _require_sha256(value: str, name: str) -> None:
    if not isinstance(value, str) or not _SHA256_RE.fullmatch(value):
        raise ValueError(f"{name} must be a 64-character SHA-256 hex digest")


def _require_commit(value: str) -> None:
    if not isinstance(value, str) or not _COMMIT_RE.fullmatch(value):
        raise ValueError("source_commit must be a 7-64 character hexadecimal Git SHA")


@dataclass(frozen=True)
class OutcomeQuote:
    selection: str
    american_odds: float

    def __post_init__(self) -> None:
        _require_nonempty(self.selection, "selection")
        _require_american_odds(self.american_odds)


@dataclass(frozen=True)
class MarketSnapshot:
    event_id: str
    competition: str
    market_id: str
    market_type: str
    bookmaker: str
    observed_at: datetime
    starts_at: datetime
    outcomes: tuple[OutcomeQuote, ...]
    status: MarketStatus = MarketStatus.OPEN
    source_receipt_id: str = ""

    def __post_init__(self) -> None:
        for name in (
            "event_id",
            "competition",
            "market_id",
            "market_type",
            "bookmaker",
        ):
            _require_nonempty(getattr(self, name), name)
        _require_aware(self.observed_at, "observed_at")
        _require_aware(self.starts_at, "starts_at")
        if self.starts_at <= self.observed_at:
            raise ValueError("starts_at must be later than observed_at")
        if len(self.outcomes) < 2:
            raise ValueError("a market snapshot must include at least two outcomes")
        selections = [outcome.selection for outcome in self.outcomes]
        if len(selections) != len(set(selections)):
            raise ValueError("market outcome selections must be unique")

    def quote_for(self, selection: str) -> OutcomeQuote | None:
        return next(
            (quote for quote in self.outcomes if quote.selection == selection), None
        )


@dataclass(frozen=True)
class ProbabilityEstimate:
    event_id: str
    market_id: str
    selection: str
    win_probability: float
    generated_at: datetime
    model_id: str
    model_version: str
    model_artifact_sha256: str
    dataset_id: str
    source_commit: str
    evidence_status: EvidenceStatus

    def __post_init__(self) -> None:
        for name in (
            "event_id",
            "market_id",
            "selection",
            "model_id",
            "model_version",
            "dataset_id",
        ):
            _require_nonempty(getattr(self, name), name)
        _require_probability(self.win_probability, "win_probability")
        _require_aware(self.generated_at, "generated_at")
        _require_sha256(self.model_artifact_sha256, "model_artifact_sha256")
        _require_commit(self.source_commit)


@dataclass(frozen=True)
class DecisionPolicy:
    policy_id: str = "paper-gate-v1"
    max_market_age_seconds: float = 120.0
    max_model_age_seconds: float = 3600.0
    min_expected_value: float = 0.03
    min_probability_advantage: float = 0.02
    min_evidence_status: EvidenceStatus = EvidenceStatus.OUT_OF_SAMPLE_VALIDATED
    fractional_kelly: float = 0.25
    max_paper_stake_fraction: float = 0.005
    max_parlay_paper_stake_fraction: float = 0.0025
    live_money_authorized: bool = False
    parlays_authorized: bool = False

    def __post_init__(self) -> None:
        _require_nonempty(self.policy_id, "policy_id")
        if self.max_market_age_seconds <= 0 or self.max_model_age_seconds <= 0:
            raise ValueError("freshness limits must be positive")
        if not 0.0 <= self.min_expected_value < 1.0:
            raise ValueError("min_expected_value must be in [0, 1)")
        if not 0.0 <= self.min_probability_advantage < 1.0:
            raise ValueError("min_probability_advantage must be in [0, 1)")
        if not 0.0 < self.fractional_kelly <= 1.0:
            raise ValueError("fractional_kelly must be in (0, 1]")
        for name in ("max_paper_stake_fraction", "max_parlay_paper_stake_fraction"):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 0.05:
                raise ValueError(f"{name} must be in [0, 0.05]")


@dataclass(frozen=True)
class ParlayQuote:
    parlay_id: str
    bookmaker: str
    leg_market_ids: tuple[str, ...]
    leg_american_odds: tuple[float, ...]
    quoted_american_odds: float
    observed_at: datetime
    earliest_start_at: datetime
    status: MarketStatus = MarketStatus.OPEN
    pricing_adjustment_id: str = ""
    source_receipt_id: str = ""

    def __post_init__(self) -> None:
        _require_nonempty(self.parlay_id, "parlay_id")
        _require_nonempty(self.bookmaker, "bookmaker")
        _require_aware(self.observed_at, "observed_at")
        _require_aware(self.earliest_start_at, "earliest_start_at")
        if self.earliest_start_at <= self.observed_at:
            raise ValueError("earliest_start_at must be later than observed_at")
        if len(self.leg_market_ids) < 2:
            raise ValueError("a parlay requires at least two legs")
        if len(self.leg_market_ids) != len(self.leg_american_odds):
            raise ValueError(
                "leg_market_ids and leg_american_odds must have equal length"
            )
        if len(set(self.leg_market_ids)) != len(self.leg_market_ids):
            raise ValueError("parlay leg market IDs must be unique")
        for market_id in self.leg_market_ids:
            _require_nonempty(market_id, "leg_market_id")
        for odds in self.leg_american_odds:
            _require_american_odds(odds, "leg_american_odds")
        _require_american_odds(self.quoted_american_odds, "quoted_american_odds")


@dataclass(frozen=True)
class JointProbabilityEstimate:
    parlay_id: str
    leg_market_ids: tuple[str, ...]
    joint_probability: float
    generated_at: datetime
    model_id: str
    model_version: str
    model_artifact_sha256: str
    dataset_id: str
    source_commit: str
    evidence_status: EvidenceStatus
    correlation_evidence_id: str

    def __post_init__(self) -> None:
        for name in ("parlay_id", "model_id", "model_version", "dataset_id"):
            _require_nonempty(getattr(self, name), name)
        if len(self.leg_market_ids) < 2:
            raise ValueError("joint estimate requires at least two legs")
        if len(set(self.leg_market_ids)) != len(self.leg_market_ids):
            raise ValueError("joint-estimate leg market IDs must be unique")
        _require_probability(self.joint_probability, "joint_probability")
        _require_aware(self.generated_at, "generated_at")
        _require_sha256(self.model_artifact_sha256, "model_artifact_sha256")
        _require_commit(self.source_commit)


def american_to_decimal(american_odds: float) -> float:
    _require_american_odds(american_odds)
    odds = float(american_odds)
    return 1.0 + odds / 100.0 if odds > 0 else 1.0 + 100.0 / abs(odds)


def decimal_to_american(decimal_odds: float) -> float:
    if isinstance(decimal_odds, bool) or not isinstance(decimal_odds, (int, float)):
        raise ValueError("decimal_odds must be numeric")
    odds = float(decimal_odds)
    if not math.isfinite(odds) or odds <= 1.0:
        raise ValueError("decimal_odds must be finite and greater than 1")
    return (odds - 1.0) * 100.0 if odds >= 2.0 else -100.0 / (odds - 1.0)


def raw_implied_probability(american_odds: float) -> float:
    return 1.0 / american_to_decimal(american_odds)


def no_vig_probabilities(outcomes: Sequence[OutcomeQuote]) -> dict[str, float]:
    if len(outcomes) < 2:
        raise ValueError("at least two outcomes are required to remove vig")
    raw = {
        outcome.selection: raw_implied_probability(outcome.american_odds)
        for outcome in outcomes
    }
    denominator = sum(raw.values())
    if denominator <= 0.0 or not math.isfinite(denominator):
        raise ValueError("market implied probabilities are invalid")
    return {
        selection: probability / denominator for selection, probability in raw.items()
    }


def full_kelly_fraction(win_probability: float, decimal_odds: float) -> float:
    _require_probability(win_probability, "win_probability")
    if decimal_odds <= 1.0 or not math.isfinite(decimal_odds):
        raise ValueError("decimal_odds must be finite and greater than 1")
    net_odds = decimal_odds - 1.0
    loss_probability = 1.0 - float(win_probability)
    return max(0.0, (net_odds * float(win_probability) - loss_probability) / net_odds)


def payout_breakdown(stake: float, american_odds: float) -> dict[str, float]:
    if isinstance(stake, bool) or not isinstance(stake, (int, float)):
        raise ValueError("stake must be numeric")
    stake_value = float(stake)
    if not math.isfinite(stake_value) or stake_value <= 0.0:
        raise ValueError("stake must be finite and positive")
    decimal_odds = american_to_decimal(american_odds)
    profit = stake_value * (decimal_odds - 1.0)
    return {
        "stake": round(stake_value, 2),
        "profit": round(profit, 2),
        "total_return": round(stake_value + profit, 2),
    }


def reconcile_parlay_price(
    leg_american_odds: Sequence[float],
    quoted_american_odds: float,
    *,
    pricing_adjustment_id: str = "",
    relative_tolerance: float = 0.005,
) -> dict[str, Any]:
    if len(leg_american_odds) < 2:
        raise ValueError("at least two leg prices are required")
    if relative_tolerance < 0.0:
        raise ValueError("relative_tolerance cannot be negative")
    expected_decimal = reduce(
        mul, (american_to_decimal(odds) for odds in leg_american_odds), 1.0
    )
    quoted_decimal = american_to_decimal(quoted_american_odds)
    relative_difference = abs(quoted_decimal - expected_decimal) / expected_decimal
    arithmetic_match = relative_difference <= relative_tolerance
    adjustment_documented = bool(pricing_adjustment_id.strip())
    if arithmetic_match:
        status = "RECONCILED_VISIBLE_LEGS"
    elif adjustment_documented:
        status = "RECONCILED_EXPLICIT_ADJUSTMENT"
    else:
        status = "UNEXPLAINED_PRICE_DIFFERENCE"
    return {
        "status": status,
        "expected_decimal_from_visible_legs": round(expected_decimal, 8),
        "expected_american_from_visible_legs": round(
            decimal_to_american(expected_decimal), 2
        ),
        "quoted_decimal": round(quoted_decimal, 8),
        "quoted_american": float(quoted_american_odds),
        "relative_difference": round(relative_difference, 8),
        "pricing_adjustment_id": pricing_adjustment_id,
    }


def _utc_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return _utc_iso(value)
    if is_dataclass(value):
        return {
            field.name: _jsonable(getattr(value, field.name)) for field in fields(value)
        }
    if isinstance(value, Mapping):
        return {
            str(key): _jsonable(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    return value


def _seal_receipt(payload: Mapping[str, Any]) -> dict[str, Any]:
    jsonable = _jsonable(dict(payload))
    canonical = json.dumps(
        jsonable, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    sealed = dict(jsonable)
    sealed["receipt_sha256"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return sealed


def _age_seconds(now: datetime, timestamp: datetime) -> float:
    return (now - timestamp).total_seconds()


def _minimum_acceptable_odds(
    win_probability: float, min_expected_value: float
) -> tuple[float, float]:
    minimum_decimal = max((1.0 + min_expected_value) / win_probability, 1.000000001)
    return minimum_decimal, decimal_to_american(minimum_decimal)


def evaluate_single_market(
    *,
    intent: UserIntent,
    snapshot: MarketSnapshot,
    estimate: ProbabilityEstimate,
    now: datetime,
    policy: DecisionPolicy | None = None,
) -> dict[str, Any]:
    policy = policy or DecisionPolicy()
    _require_aware(now, "now")
    blockers: list[str] = []
    reasons: list[str] = []

    if intent == UserIntent.INFORMATION:
        reasons.append(
            "information_request_must_be_answered_without_a_wager_recommendation"
        )
        return _seal_receipt(
            {
                "receipt_type": "single_market_decision",
                "decision": DecisionCode.NO_BET,
                "intent": intent,
                "policy": policy,
                "evaluated_at": now,
                "reasons": reasons,
                "blockers": blockers,
                "market": snapshot,
                "estimate": estimate,
                "metrics": {},
            }
        )

    if intent == UserIntent.LIVE_BET_REQUEST and not policy.live_money_authorized:
        blockers.append("live_money_not_authorized")
    if snapshot.status != MarketStatus.OPEN:
        blockers.append(f"market_status_{snapshot.status.value}")
    if snapshot.event_id != estimate.event_id:
        blockers.append("event_id_mismatch")
    if snapshot.market_id != estimate.market_id:
        blockers.append("market_id_mismatch")
    quote = snapshot.quote_for(estimate.selection)
    if quote is None:
        blockers.append("exact_selection_not_quoted")

    market_age = _age_seconds(now, snapshot.observed_at)
    model_age = _age_seconds(now, estimate.generated_at)
    if market_age < -_CLOCK_SKEW_SECONDS:
        blockers.append("market_timestamp_is_in_the_future")
    elif market_age > policy.max_market_age_seconds:
        blockers.append("market_snapshot_stale")
    if model_age < -_CLOCK_SKEW_SECONDS:
        blockers.append("model_timestamp_is_in_the_future")
    elif model_age > policy.max_model_age_seconds:
        blockers.append("model_estimate_stale")
    if snapshot.starts_at <= now:
        blockers.append("event_started_or_start_time_passed")
    if (
        _EVIDENCE_RANK[estimate.evidence_status]
        < _EVIDENCE_RANK[policy.min_evidence_status]
    ):
        blockers.append("model_evidence_below_policy_minimum")

    metrics: dict[str, Any] = {
        "market_age_seconds": round(market_age, 3),
        "model_age_seconds": round(model_age, 3),
    }
    if blockers:
        decision = DecisionCode.BLOCKED
    else:
        assert quote is not None
        decimal_odds = american_to_decimal(quote.american_odds)
        fair_market = no_vig_probabilities(snapshot.outcomes)[estimate.selection]
        probability_advantage = estimate.win_probability - fair_market
        expected_value = estimate.win_probability * decimal_odds - 1.0
        minimum_decimal, minimum_american = _minimum_acceptable_odds(
            estimate.win_probability, policy.min_expected_value
        )
        full_kelly = full_kelly_fraction(estimate.win_probability, decimal_odds)
        paper_stake = min(
            policy.max_paper_stake_fraction, full_kelly * policy.fractional_kelly
        )
        metrics.update(
            {
                "quoted_american_odds": float(quote.american_odds),
                "quoted_decimal_odds": round(decimal_odds, 8),
                "raw_implied_probability": round(
                    raw_implied_probability(quote.american_odds), 8
                ),
                "no_vig_market_probability": round(fair_market, 8),
                "model_probability": round(estimate.win_probability, 8),
                "probability_advantage": round(probability_advantage, 8),
                "expected_value_per_unit": round(expected_value, 8),
                "minimum_acceptable_decimal_odds": round(minimum_decimal, 8),
                "minimum_acceptable_american_odds": round(minimum_american, 2),
                "full_kelly_fraction": round(full_kelly, 8),
                "paper_stake_fraction": round(paper_stake, 8),
            }
        )
        if expected_value < policy.min_expected_value:
            reasons.append("expected_value_below_policy_minimum")
        if probability_advantage < policy.min_probability_advantage:
            reasons.append("probability_advantage_below_policy_minimum")
        if reasons:
            decision = DecisionCode.NO_BET
            metrics["paper_stake_fraction"] = 0.0
        else:
            decision = DecisionCode.PAPER_CANDIDATE

    return _seal_receipt(
        {
            "receipt_type": "single_market_decision",
            "decision": decision,
            "intent": intent,
            "policy": policy,
            "evaluated_at": now,
            "reasons": reasons,
            "blockers": blockers,
            "market": snapshot,
            "estimate": estimate,
            "metrics": metrics,
        }
    )


def evaluate_parlay(
    *,
    intent: UserIntent,
    quote: ParlayQuote,
    estimate: JointProbabilityEstimate,
    now: datetime,
    policy: DecisionPolicy | None = None,
) -> dict[str, Any]:
    """Evaluate only an explicit dependency-aware joint probability.

    Individual leg probabilities are deliberately not accepted by this API.
    """

    policy = policy or DecisionPolicy()
    _require_aware(now, "now")
    blockers: list[str] = []
    reasons: list[str] = []

    if intent == UserIntent.INFORMATION:
        reasons.append(
            "information_request_must_be_answered_without_a_wager_recommendation"
        )
    if intent == UserIntent.LIVE_BET_REQUEST and not policy.live_money_authorized:
        blockers.append("live_money_not_authorized")
    if not policy.parlays_authorized:
        blockers.append("parlays_disabled_by_policy")
    if quote.status != MarketStatus.OPEN:
        blockers.append(f"market_status_{quote.status.value}")
    if quote.parlay_id != estimate.parlay_id:
        blockers.append("parlay_id_mismatch")
    if tuple(quote.leg_market_ids) != tuple(estimate.leg_market_ids):
        blockers.append("parlay_leg_identity_or_order_mismatch")
    if not estimate.correlation_evidence_id.strip():
        blockers.append("correlation_evidence_missing")

    market_age = _age_seconds(now, quote.observed_at)
    model_age = _age_seconds(now, estimate.generated_at)
    if market_age < -_CLOCK_SKEW_SECONDS:
        blockers.append("market_timestamp_is_in_the_future")
    elif market_age > policy.max_market_age_seconds:
        blockers.append("parlay_quote_stale")
    if model_age < -_CLOCK_SKEW_SECONDS:
        blockers.append("model_timestamp_is_in_the_future")
    elif model_age > policy.max_model_age_seconds:
        blockers.append("joint_estimate_stale")
    if quote.earliest_start_at <= now:
        blockers.append("one_or_more_events_started")
    if (
        _EVIDENCE_RANK[estimate.evidence_status]
        < _EVIDENCE_RANK[policy.min_evidence_status]
    ):
        blockers.append("joint_model_evidence_below_policy_minimum")

    reconciliation = reconcile_parlay_price(
        quote.leg_american_odds,
        quote.quoted_american_odds,
        pricing_adjustment_id=quote.pricing_adjustment_id,
    )
    if reconciliation["status"] == "UNEXPLAINED_PRICE_DIFFERENCE":
        blockers.append(
            "parlay_price_does_not_reconcile_and_no_adjustment_is_documented"
        )

    metrics: dict[str, Any] = {
        "market_age_seconds": round(market_age, 3),
        "model_age_seconds": round(model_age, 3),
        "price_reconciliation": reconciliation,
    }
    if reasons and not blockers:
        decision = DecisionCode.NO_BET
    elif blockers:
        decision = DecisionCode.BLOCKED
    else:
        decimal_odds = american_to_decimal(quote.quoted_american_odds)
        expected_value = estimate.joint_probability * decimal_odds - 1.0
        full_kelly = full_kelly_fraction(estimate.joint_probability, decimal_odds)
        paper_stake = min(
            policy.max_parlay_paper_stake_fraction, full_kelly * policy.fractional_kelly
        )
        minimum_decimal, minimum_american = _minimum_acceptable_odds(
            estimate.joint_probability, policy.min_expected_value
        )
        metrics.update(
            {
                "quoted_decimal_odds": round(decimal_odds, 8),
                "joint_model_probability": round(estimate.joint_probability, 8),
                "expected_value_per_unit": round(expected_value, 8),
                "minimum_acceptable_decimal_odds": round(minimum_decimal, 8),
                "minimum_acceptable_american_odds": round(minimum_american, 2),
                "full_kelly_fraction": round(full_kelly, 8),
                "paper_stake_fraction": round(paper_stake, 8),
            }
        )
        if expected_value < policy.min_expected_value:
            reasons.append("expected_value_below_policy_minimum")
            metrics["paper_stake_fraction"] = 0.0
            decision = DecisionCode.NO_BET
        else:
            decision = DecisionCode.PAPER_CANDIDATE

    return _seal_receipt(
        {
            "receipt_type": "parlay_decision",
            "decision": decision,
            "intent": intent,
            "policy": policy,
            "evaluated_at": now,
            "reasons": reasons,
            "blockers": blockers,
            "quote": quote,
            "estimate": estimate,
            "metrics": metrics,
        }
    )
