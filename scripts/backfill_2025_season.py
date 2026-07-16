"""Disabled historical sample-data backfill.

The former script wrote invented 2025 games, probabilities, prices, outcomes,
and bankroll results into ``reports/bet_history.csv``. Synthetic fixtures must
never be appended to an operational or performance ledger.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from src.betting.decision_contracts import PAPER_AUTHORITY

_DISABLED_REASON = (
    "sample-data backfill is disabled; provide an immutable historical event, "
    "price, prediction, and settlement ledger to a dedicated evaluator"
)


def build_blocked_receipt() -> Dict[str, Any]:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "BLOCKED",
        "reason": _DISABLED_REASON,
        "authority": PAPER_AUTHORITY,
        "live_wagers_authorized": False,
        "synthetic_rows_written": 0,
        "operational_history_mutated": False,
    }


def main(output: str = "reports/backfill_2025_blocked.json") -> int:
    receipt = build_blocked_receipt()
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8"
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
