"""Evaluate exact market/model evidence into paper-only decision receipts.

Input format:
{
  "candidates": [
    {
      "label": "KC moneyline",
      "market_snapshot": {...},
      "model_estimate": {...}
    }
  ]
}

This script never places, sizes, or recommends a live wager.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.betting.decision_contracts import (  # noqa: E402
    CONTRACT_VERSION,
    PAPER_AUTHORITY,
    DecisionContractError,
    MarketSnapshot,
    ModelEstimate,
    evaluate_for_paper_tracking,
    parse_utc_datetime,
)


def evaluate_payload(
    payload: Any,
    *,
    now: Optional[datetime] = None,
    max_age_seconds: int = 300,
    min_expected_value_lower_bound: float = 0.0,
) -> dict[str, Any]:
    """Evaluate a candidate list and preserve failures as NO_BET records."""

    if isinstance(payload, list):
        candidates = payload
    elif isinstance(payload, Mapping):
        candidates = payload.get("candidates", [])
    else:
        raise DecisionContractError("input root must be an object or array")
    if not isinstance(candidates, list):
        raise DecisionContractError("candidates must be an array")

    current_time = now or datetime.now(timezone.utc)
    current_time = parse_utc_datetime(current_time, "now")
    receipts: list[dict[str, Any]] = []
    for index, candidate in enumerate(candidates):
        label = f"candidate_{index + 1}"
        if isinstance(candidate, Mapping) and isinstance(candidate.get("label"), str):
            label = candidate["label"].strip() or label
        try:
            if not isinstance(candidate, Mapping):
                raise DecisionContractError("candidate must be an object")
            snapshot = MarketSnapshot.from_mapping(candidate["market_snapshot"])
            estimate = ModelEstimate.from_mapping(candidate["model_estimate"])
            receipt = evaluate_for_paper_tracking(
                snapshot,
                estimate,
                now=current_time,
                max_age_seconds=max_age_seconds,
                min_expected_value_lower_bound=min_expected_value_lower_bound,
            ).to_dict()
            receipt["label"] = label
        except (DecisionContractError, KeyError, TypeError) as exc:
            receipt = {
                "contract_version": CONTRACT_VERSION,
                "label": label,
                "status": "NO_BET",
                "action": "do_not_place_or_recommend_a_wager",
                "authority": PAPER_AUTHORITY,
                "blockers": [f"contract_error:{exc}"],
                "evidence": [],
                "next_checkpoint": "supply complete immutable evidence and re-evaluate",
                "fallback": "NO_BET",
            }
        receipts.append(receipt)

    counts = {
        status: sum(1 for receipt in receipts if receipt.get("status") == status)
        for status in ("PAPER_TRACK", "HOLD", "NO_BET")
    }
    return {
        "contract_version": CONTRACT_VERSION,
        "generated_at": current_time.isoformat(),
        "authority": PAPER_AUTHORITY,
        "receipts": receipts,
        "summary": {
            "candidate_count": len(receipts),
            "status_counts": counts,
            "live_wagers_authorized": False,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create fail-closed paper-only decision receipts"
    )
    parser.add_argument("--input", required=True, help="Candidate JSON file")
    parser.add_argument(
        "--output", default="reports/paper_decision_receipts.json", help="Output JSON"
    )
    parser.add_argument("--now", help="Optional ISO-8601 evaluation time")
    parser.add_argument("--max-age-seconds", type=int, default=300)
    parser.add_argument("--min-ev-lower-bound", type=float, default=0.0)
    args = parser.parse_args()

    with open(args.input, "r", encoding="utf-8") as handle:
        payload = json.load(handle)
    now = parse_utc_datetime(args.now, "now") if args.now else None
    result = evaluate_payload(
        payload,
        now=now,
        max_age_seconds=args.max_age_seconds,
        min_expected_value_lower_bound=args.min_ev_lower_bound,
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    print(f"Receipts written to {output_path}")


if __name__ == "__main__":
    main()
