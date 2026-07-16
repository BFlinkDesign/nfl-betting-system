#!/usr/bin/env python3
"""Create a sealed, fail-closed research/paper-trading decision receipt.

The command never places a wager. Exit codes:

* 0 for NO_BET or PAPER_CANDIDATE;
* 2 for BLOCKED;
* 64 for malformed input.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.betting.decision_receipt import (  # noqa: E402
    DecisionCode,
    DecisionPolicy,
    EvidenceStatus,
    JointProbabilityEstimate,
    MarketSnapshot,
    MarketStatus,
    OutcomeQuote,
    ParlayQuote,
    ProbabilityEstimate,
    UserIntent,
    evaluate_parlay,
    evaluate_single_market,
)


def parse_datetime(value: str, name: str) -> datetime:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{name} must be a valid ISO-8601 datetime") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{name} must include a timezone offset")
    return parsed


def build_policy(raw: dict[str, Any] | None) -> DecisionPolicy:
    if not raw:
        return DecisionPolicy()
    values = dict(raw)
    if "min_evidence_status" in values:
        values["min_evidence_status"] = EvidenceStatus(values["min_evidence_status"])
    return DecisionPolicy(**values)


def build_single(payload: dict[str, Any]) -> dict[str, Any]:
    raw_market = payload["market"]
    raw_estimate = payload["estimate"]
    snapshot = MarketSnapshot(
        event_id=raw_market["event_id"],
        competition=raw_market["competition"],
        market_id=raw_market["market_id"],
        market_type=raw_market["market_type"],
        bookmaker=raw_market["bookmaker"],
        observed_at=parse_datetime(raw_market["observed_at"], "market.observed_at"),
        starts_at=parse_datetime(raw_market["starts_at"], "market.starts_at"),
        outcomes=tuple(
            OutcomeQuote(outcome["selection"], outcome["american_odds"])
            for outcome in raw_market["outcomes"]
        ),
        status=MarketStatus(raw_market.get("status", "open")),
        source_receipt_id=raw_market.get("source_receipt_id", ""),
    )
    estimate = ProbabilityEstimate(
        event_id=raw_estimate["event_id"],
        market_id=raw_estimate["market_id"],
        selection=raw_estimate["selection"],
        win_probability=raw_estimate["win_probability"],
        generated_at=parse_datetime(
            raw_estimate["generated_at"], "estimate.generated_at"
        ),
        model_id=raw_estimate["model_id"],
        model_version=raw_estimate["model_version"],
        model_artifact_sha256=raw_estimate["model_artifact_sha256"],
        dataset_id=raw_estimate["dataset_id"],
        source_commit=raw_estimate["source_commit"],
        evidence_status=EvidenceStatus(raw_estimate["evidence_status"]),
    )
    return evaluate_single_market(
        intent=UserIntent(payload["intent"]),
        snapshot=snapshot,
        estimate=estimate,
        now=parse_datetime(payload["evaluated_at"], "evaluated_at"),
        policy=build_policy(payload.get("policy")),
    )


def build_parlay(payload: dict[str, Any]) -> dict[str, Any]:
    raw_quote = payload["quote"]
    raw_estimate = payload["estimate"]
    quote = ParlayQuote(
        parlay_id=raw_quote["parlay_id"],
        bookmaker=raw_quote["bookmaker"],
        leg_market_ids=tuple(raw_quote["leg_market_ids"]),
        leg_american_odds=tuple(raw_quote["leg_american_odds"]),
        quoted_american_odds=raw_quote["quoted_american_odds"],
        observed_at=parse_datetime(raw_quote["observed_at"], "quote.observed_at"),
        earliest_start_at=parse_datetime(
            raw_quote["earliest_start_at"], "quote.earliest_start_at"
        ),
        status=MarketStatus(raw_quote.get("status", "open")),
        pricing_adjustment_id=raw_quote.get("pricing_adjustment_id", ""),
        source_receipt_id=raw_quote.get("source_receipt_id", ""),
    )
    estimate = JointProbabilityEstimate(
        parlay_id=raw_estimate["parlay_id"],
        leg_market_ids=tuple(raw_estimate["leg_market_ids"]),
        joint_probability=raw_estimate["joint_probability"],
        generated_at=parse_datetime(
            raw_estimate["generated_at"], "estimate.generated_at"
        ),
        model_id=raw_estimate["model_id"],
        model_version=raw_estimate["model_version"],
        model_artifact_sha256=raw_estimate["model_artifact_sha256"],
        dataset_id=raw_estimate["dataset_id"],
        source_commit=raw_estimate["source_commit"],
        evidence_status=EvidenceStatus(raw_estimate["evidence_status"]),
        correlation_evidence_id=raw_estimate.get("correlation_evidence_id", ""),
    )
    return evaluate_parlay(
        intent=UserIntent(payload["intent"]),
        quote=quote,
        estimate=estimate,
        now=parse_datetime(payload["evaluated_at"], "evaluated_at"),
        policy=build_policy(payload.get("policy")),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Evaluate a market into a sealed paper-trading decision receipt."
    )
    parser.add_argument("input", type=Path, help="Input JSON file")
    parser.add_argument("--output", type=Path, help="Optional receipt output path")
    args = parser.parse_args()

    try:
        payload = json.loads(args.input.read_text(encoding="utf-8"))
        receipt_type = payload.get("receipt_type", "single_market_decision")
        if receipt_type == "single_market_decision":
            receipt = build_single(payload)
        elif receipt_type == "parlay_decision":
            receipt = build_parlay(payload)
        else:
            raise ValueError(
                "receipt_type must be single_market_decision or parlay_decision"
            )
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({"decision": "BLOCKED", "input_error": str(exc)}, indent=2))
        return 64

    rendered = json.dumps(receipt, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 2 if receipt["decision"] == DecisionCode.BLOCKED.value else 0


if __name__ == "__main__":
    raise SystemExit(main())
