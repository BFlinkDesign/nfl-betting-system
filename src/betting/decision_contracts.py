"""Fail-closed decision contracts for market and model evidence.

This module does not place wagers. It converts archived market snapshots and
qualified model estimates into auditable paper-tracking receipts. A positive
point estimate is insufficient: every promotable decision uses a probability
lower bound, an exact offered price, freshness checks, and immutable evidence
identifiers.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Mapping, Optional

CONTRACT_VERSION = "1.0.0"
PAPER_AUTHORITY = "paper_only_no_live_wager_authority"
QUALIFIED_EVIDENCE_STATUSES = frozenset(
    {
        "out_of_sample_validated",
        "paper_trading",
        "live_validated",
    }
)
_SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")


class DecisionContractError(ValueError):
    """Raised when evidence cannot satisfy the decision contract."""


class DecisionStatus(str, Enum):
    """Allowed outcomes from the decision contract."""

    NO_BET = "NO_BET"
    HOLD = "HOLD"
    PAPER_TRACK = "PAPER_TRACK"


def _require_text(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DecisionContractError(f"{field_name} must be a non-empty string")
    return value.strip()


def _require_hash(value: Any, field_name: str) -> str:
    text = _require_text(value, field_name).lower()
    if not _SHA256_RE.fullmatch(text):
        raise DecisionContractError(f"{field_name} must be a 64-character SHA-256")
    return text


def _require_probability(value: Any, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DecisionContractError(f"{field_name} must be numeric")
    probability = float(value)
    if not math.isfinite(probability) or not 0.0 <= probability <= 1.0:
        raise DecisionContractError(f"{field_name} must be between zero and one")
    return probability


def _first_present(data: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in data and data[key] is not None:
            return data[key]
    raise DecisionContractError(
        f"missing required field; expected one of: {', '.join(keys)}"
    )


def parse_utc_datetime(value: Any, field_name: str) -> datetime:
    """Parse a timezone-aware timestamp and normalize it to UTC."""

    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        normalized = value.strip().replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise DecisionContractError(
                f"{field_name} must be an ISO-8601 timestamp"
            ) from exc
    else:
        raise DecisionContractError(f"{field_name} must be a timestamp")

    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise DecisionContractError(f"{field_name} must include a timezone")
    return parsed.astimezone(timezone.utc)


def american_to_decimal(american_odds: float) -> float:
    """Convert American odds to decimal odds with strict validation."""

    if isinstance(american_odds, bool) or not isinstance(american_odds, (int, float)):
        raise DecisionContractError("american_odds must be numeric")
    odds = float(american_odds)
    if not math.isfinite(odds) or odds == 0:
        raise DecisionContractError("american_odds must be finite and non-zero")
    if odds > 0:
        return 1.0 + odds / 100.0
    return 1.0 + 100.0 / abs(odds)


def decimal_to_american(decimal_odds: float) -> float:
    """Convert decimal odds greater than one to American odds."""

    if isinstance(decimal_odds, bool) or not isinstance(decimal_odds, (int, float)):
        raise DecisionContractError("decimal_odds must be numeric")
    odds = float(decimal_odds)
    if not math.isfinite(odds) or odds <= 1.0:
        raise DecisionContractError("decimal_odds must be finite and greater than one")
    if odds >= 2.0:
        return (odds - 1.0) * 100.0
    return -100.0 / (odds - 1.0)


def expected_value(probability: float, american_odds: float) -> float:
    """Return flat-stake expected value as profit per unit staked."""

    probability = _require_probability(probability, "probability")
    return probability * american_to_decimal(american_odds) - 1.0


def minimum_acceptable_odds(
    probability_lower_bound: float, min_expected_value: float = 0.0
) -> tuple[float, float]:
    """Return minimum decimal and American odds for a lower-bound EV target."""

    probability = _require_probability(
        probability_lower_bound, "probability_lower_bound"
    )
    if probability <= 0.0:
        raise DecisionContractError("probability_lower_bound must be greater than zero")
    if isinstance(min_expected_value, bool) or not isinstance(
        min_expected_value, (int, float)
    ):
        raise DecisionContractError("min_expected_value must be numeric")
    min_ev = float(min_expected_value)
    if not math.isfinite(min_ev) or min_ev < 0.0:
        raise DecisionContractError(
            "min_expected_value must be finite and greater than or equal to zero"
        )

    minimum_decimal = (1.0 + min_ev) / probability
    if minimum_decimal <= 1.0:
        minimum_decimal = math.nextafter(1.0, math.inf)
    return minimum_decimal, decimal_to_american(minimum_decimal)


@dataclass(frozen=True)
class MarketSnapshot:
    """Immutable price evidence for one exact event, market, and selection."""

    snapshot_id: str
    event_id: str
    market_key: str
    selection_key: str
    sportsbook: str
    source: str
    american_odds: float
    observed_at: datetime
    event_start_at: datetime
    source_hash: str

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "MarketSnapshot":
        if not isinstance(data, Mapping):
            raise DecisionContractError("market snapshot must be an object")

        observed_at = parse_utc_datetime(
            _first_present(data, "observed_at", "odds_observed_at"), "observed_at"
        )
        event_start_at = parse_utc_datetime(
            _first_present(data, "event_start_at", "commence_time"),
            "event_start_at",
        )
        if observed_at >= event_start_at:
            raise DecisionContractError(
                "market snapshot must be captured before the event starts"
            )

        raw_odds = _first_present(
            data, "american_odds", "offered_american_odds", "odds"
        )
        american_to_decimal(raw_odds)

        sportsbook = _require_text(data.get("sportsbook"), "sportsbook")
        if sportsbook.casefold() in {"n/a", "na", "unknown", "none"}:
            raise DecisionContractError("sportsbook must identify an actual book")

        return cls(
            snapshot_id=_require_text(data.get("snapshot_id"), "snapshot_id"),
            event_id=_require_text(data.get("event_id"), "event_id"),
            market_key=_require_text(data.get("market_key"), "market_key"),
            selection_key=_require_text(data.get("selection_key"), "selection_key"),
            sportsbook=sportsbook,
            source=_require_text(data.get("source"), "source"),
            american_odds=float(raw_odds),
            observed_at=observed_at,
            event_start_at=event_start_at,
            source_hash=_require_hash(data.get("source_hash"), "source_hash"),
        )

    def age_seconds(self, now: datetime) -> float:
        now_utc = parse_utc_datetime(now, "now")
        return (now_utc - self.observed_at).total_seconds()

    def expires_at(self, max_age_seconds: int) -> datetime:
        if max_age_seconds <= 0:
            raise DecisionContractError("max_age_seconds must be positive")
        return min(
            self.observed_at + timedelta(seconds=max_age_seconds), self.event_start_at
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "event_id": self.event_id,
            "market_key": self.market_key,
            "selection_key": self.selection_key,
            "sportsbook": self.sportsbook,
            "source": self.source,
            "american_odds": self.american_odds,
            "observed_at": self.observed_at.isoformat(),
            "event_start_at": self.event_start_at.isoformat(),
            "source_hash": self.source_hash,
        }


@dataclass(frozen=True)
class ModelEstimate:
    """Versioned probability estimate with a conservative uncertainty bound."""

    estimate_id: str
    model_id: str
    evaluation_id: str
    point_probability: float
    lower_probability_bound: float
    evidence_status: str
    generated_at: datetime
    data_cutoff_at: datetime
    artifact_hash: str

    @classmethod
    def from_mapping(cls, data: Mapping[str, Any]) -> "ModelEstimate":
        if not isinstance(data, Mapping):
            raise DecisionContractError("model estimate must be an object")

        point = _require_probability(
            _first_present(
                data,
                "point_probability",
                "joint_probability",
                "win_probability",
                "probability",
            ),
            "point_probability",
        )
        lower = _require_probability(
            _first_present(
                data,
                "lower_probability_bound",
                "joint_probability_lower_bound",
                "probability_lower_bound",
            ),
            "lower_probability_bound",
        )
        if lower > point:
            raise DecisionContractError(
                "lower_probability_bound cannot exceed point_probability"
            )

        generated_at = parse_utc_datetime(
            _first_present(data, "generated_at", "estimated_at"), "generated_at"
        )
        data_cutoff_at = parse_utc_datetime(
            _first_present(data, "data_cutoff_at", "feature_cutoff_at"),
            "data_cutoff_at",
        )
        if data_cutoff_at > generated_at:
            raise DecisionContractError(
                "data_cutoff_at cannot be later than generated_at"
            )

        return cls(
            estimate_id=_require_text(data.get("estimate_id"), "estimate_id"),
            model_id=_require_text(data.get("model_id"), "model_id"),
            evaluation_id=_require_text(data.get("evaluation_id"), "evaluation_id"),
            point_probability=point,
            lower_probability_bound=lower,
            evidence_status=_require_text(
                data.get("evidence_status"), "evidence_status"
            ),
            generated_at=generated_at,
            data_cutoff_at=data_cutoff_at,
            artifact_hash=_require_hash(data.get("artifact_hash"), "artifact_hash"),
        )

    @property
    def is_qualified(self) -> bool:
        return self.evidence_status in QUALIFIED_EVIDENCE_STATUSES

    def to_dict(self) -> dict[str, Any]:
        return {
            "estimate_id": self.estimate_id,
            "model_id": self.model_id,
            "evaluation_id": self.evaluation_id,
            "point_probability": self.point_probability,
            "lower_probability_bound": self.lower_probability_bound,
            "evidence_status": self.evidence_status,
            "generated_at": self.generated_at.isoformat(),
            "data_cutoff_at": self.data_cutoff_at.isoformat(),
            "artifact_hash": self.artifact_hash,
        }


@dataclass(frozen=True)
class DecisionReceipt:
    """Auditable output from a fail-closed paper decision evaluation."""

    decision_id: str
    status: DecisionStatus
    action: str
    authority: str
    blockers: tuple[str, ...]
    evidence: tuple[str, ...]
    next_checkpoint: str
    fallback: str
    expected_value_point: Optional[float]
    expected_value_lower_bound: Optional[float]
    minimum_acceptable_decimal_odds: Optional[float]
    minimum_acceptable_american_odds: Optional[float]
    expires_at: datetime
    market_snapshot: MarketSnapshot
    model_estimate: ModelEstimate

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_version": CONTRACT_VERSION,
            "decision_id": self.decision_id,
            "status": self.status.value,
            "action": self.action,
            "authority": self.authority,
            "blockers": list(self.blockers),
            "evidence": list(self.evidence),
            "next_checkpoint": self.next_checkpoint,
            "fallback": self.fallback,
            "expected_value_point": self.expected_value_point,
            "expected_value_lower_bound": self.expected_value_lower_bound,
            "minimum_acceptable_decimal_odds": self.minimum_acceptable_decimal_odds,
            "minimum_acceptable_american_odds": self.minimum_acceptable_american_odds,
            "expires_at": self.expires_at.isoformat(),
            "market_snapshot": self.market_snapshot.to_dict(),
            "model_estimate": self.model_estimate.to_dict(),
        }


def _decision_id(
    snapshot: MarketSnapshot,
    estimate: ModelEstimate,
    status: DecisionStatus,
    blockers: tuple[str, ...],
) -> str:
    payload = {
        "contract_version": CONTRACT_VERSION,
        "snapshot_id": snapshot.snapshot_id,
        "snapshot_hash": snapshot.source_hash,
        "estimate_id": estimate.estimate_id,
        "estimate_hash": estimate.artifact_hash,
        "status": status.value,
        "blockers": blockers,
    }
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(serialized).hexdigest()


def evaluate_for_paper_tracking(
    snapshot: MarketSnapshot,
    estimate: ModelEstimate,
    *,
    now: Optional[datetime] = None,
    max_age_seconds: int = 300,
    min_expected_value_lower_bound: float = 0.0,
) -> DecisionReceipt:
    """Evaluate one exact market for forward paper tracking, never live wagering."""

    if max_age_seconds <= 0:
        raise DecisionContractError("max_age_seconds must be positive")
    current_time = now or datetime.now(timezone.utc)
    current_time = parse_utc_datetime(current_time, "now")
    if current_time < snapshot.observed_at:
        raise DecisionContractError("now cannot be earlier than observed_at")

    blockers: list[str] = []
    if current_time >= snapshot.event_start_at:
        blockers.append("event_already_started")
    if snapshot.age_seconds(current_time) > max_age_seconds:
        blockers.append("market_snapshot_stale")
    if estimate.generated_at > current_time:
        blockers.append("model_estimate_generated_in_the_future")
    if estimate.data_cutoff_at >= snapshot.event_start_at:
        blockers.append("model_data_cutoff_not_pregame")
    if not estimate.is_qualified:
        blockers.append(f"model_evidence_not_qualified:{estimate.evidence_status}")

    minimum_decimal: Optional[float]
    minimum_american: Optional[float]
    ev_point: Optional[float]
    ev_lower: Optional[float]
    try:
        minimum_decimal, minimum_american = minimum_acceptable_odds(
            estimate.lower_probability_bound, min_expected_value_lower_bound
        )
        ev_point = expected_value(estimate.point_probability, snapshot.american_odds)
        ev_lower = expected_value(
            estimate.lower_probability_bound, snapshot.american_odds
        )
        if ev_lower <= min_expected_value_lower_bound:
            blockers.append("lower_bound_expected_value_not_above_threshold")
    except DecisionContractError:
        minimum_decimal = None
        minimum_american = None
        ev_point = None
        ev_lower = None
        blockers.append("probability_or_price_cannot_support_ev_evaluation")

    blockers_tuple = tuple(sorted(set(blockers)))
    expires_at = snapshot.expires_at(max_age_seconds)
    if blockers_tuple:
        status = DecisionStatus.NO_BET
        action = "do_not_place_or_recommend_a_wager"
        next_checkpoint = "repair evidence or refresh the exact price, then re-evaluate"
    else:
        status = DecisionStatus.PAPER_TRACK
        action = "record_candidate_for_forward_paper_tracking_only"
        next_checkpoint = (
            "archive the pre-event receipt and settle against the final result"
        )

    evidence = (
        f"market_snapshot:{snapshot.snapshot_id}:{snapshot.source_hash}",
        f"model_estimate:{estimate.estimate_id}:{estimate.artifact_hash}",
        f"evaluation:{estimate.evaluation_id}",
    )
    return DecisionReceipt(
        decision_id=_decision_id(snapshot, estimate, status, blockers_tuple),
        status=status,
        action=action,
        authority=PAPER_AUTHORITY,
        blockers=blockers_tuple,
        evidence=evidence,
        next_checkpoint=next_checkpoint,
        fallback="NO_BET",
        expected_value_point=ev_point,
        expected_value_lower_bound=ev_lower,
        minimum_acceptable_decimal_odds=minimum_decimal,
        minimum_acceptable_american_odds=minimum_american,
        expires_at=expires_at,
        market_snapshot=snapshot,
        model_estimate=estimate,
    )
