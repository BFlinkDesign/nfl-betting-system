"""Fail-closed compatibility entry point for historical daily-picks callers.

The previous module loaded unverified models, averaged bookmaker probabilities,
applied unverified favorites heuristics, and could force a non-zero stake after
Kelly returned zero. That execution path is retired.

Use ``scripts/evaluate_paper_decisions.py`` with immutable market and model
evidence. This module retains a small compatibility API so old imports produce
``NO BET`` instead of crashing or generating an actionable wager.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.evaluate_paper_decisions import evaluate_payload  # noqa: E402
from src.betting.decision_contracts import (  # noqa: E402
    PAPER_AUTHORITY,
    DecisionContractError,
    parse_utc_datetime,
)

logger = logging.getLogger(__name__)

LEGACY_RUNTIME_STATUS = "DISABLED_PENDING_PROVENANCE_BOUND_EVIDENCE"
_DISABLED_REASON = (
    "legacy daily-picks generation is disabled; submit immutable market and "
    "model evidence through scripts/evaluate_paper_decisions.py"
)


def _validate_bankroll(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("bankroll must be numeric")
    bankroll = float(value)
    if not math.isfinite(bankroll) or bankroll <= 0:
        raise ValueError("bankroll must be finite and greater than zero")
    return bankroll


def _no_bet(game: str, reason: str = _DISABLED_REASON) -> Dict[str, Any]:
    return {
        "recommendation": "NO BET",
        "status": "NO_BET",
        "game": game,
        "reason": reason,
        "authority": PAPER_AUTHORITY,
        "live_wagers_authorized": False,
        "paper_stake": 0.0,
    }


class DailyPicksGenerator:
    """Historical API retained as a non-actionable paper-evidence adapter."""

    def __init__(
        self,
        model_path: str = "models/xgboost_favorites_only.pkl",
        features_path: str = "data/processed/features_2016_2024_improved.parquet",
        bankroll: float = 10000.0,
        favorites_only: bool = True,
    ) -> None:
        self.model_path = model_path
        self.features_path = features_path
        self.bankroll = _validate_bankroll(bankroll)
        self.favorites_only = bool(favorites_only)
        self.model = None
        self.features_df = None

    def get_team_recent_stats(self, team: str, season: int = 2024) -> Dict[str, Any]:
        """Return no derived stats from this retired execution path."""

        return {}

    def predict_game(
        self,
        home_team: str,
        away_team: str,
        weather: Optional[Dict[str, Any]] = None,
        odds: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Refuse to manufacture a probability from unbound local artifacts."""

        return {
            "error": "legacy_unbound_prediction_path_disabled",
            "status": "NO_BET",
            "home_team": home_team,
            "away_team": away_team,
            "home_win_prob": None,
            "away_win_prob": None,
            "confidence": 0.0,
            "model_used": False,
            "evidence_status": "unverified",
            "authority": PAPER_AUTHORITY,
        }

    def generate_pick(
        self,
        game: Dict[str, Any],
        prediction: Dict[str, Any],
        line_shopping_report: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Evaluate an explicitly supplied canonical candidate or return NO BET."""

        home = str(prediction.get("home_team") or game.get("home_team") or "Home")
        away = str(prediction.get("away_team") or game.get("away_team") or "Away")
        game_label = f"{away} @ {home}"

        market_snapshot = prediction.get("market_snapshot")
        model_estimate = prediction.get("model_estimate")
        if not isinstance(market_snapshot, Mapping) or not isinstance(
            model_estimate, Mapping
        ):
            return _no_bet(game_label)

        result = evaluate_payload(
            {
                "candidates": [
                    {
                        "label": game_label,
                        "market_snapshot": dict(market_snapshot),
                        "model_estimate": dict(model_estimate),
                    }
                ]
            }
        )
        receipt = result["receipts"][0]
        status = receipt.get("status", "NO_BET")
        return {
            "recommendation": ("PAPER TRACK" if status == "PAPER_TRACK" else "NO BET"),
            "status": status,
            "game": game_label,
            "reason": (
                "canonical evidence contract passed for paper tracking"
                if status == "PAPER_TRACK"
                else "; ".join(receipt.get("blockers", [])) or "NO_BET"
            ),
            "authority": receipt.get("authority", PAPER_AUTHORITY),
            "live_wagers_authorized": False,
            "paper_stake": 0.0,
            "decision_receipt": receipt,
        }

    def generate_daily_picks(self, min_edge: float = 0.05) -> List[Dict[str, Any]]:
        """Return no picks; automatic legacy discovery is intentionally disabled."""

        logger.warning(_DISABLED_REASON)
        return []

    def save_picks(
        self, picks: List[Dict[str, Any]], filename: Optional[str] = None
    ) -> str:
        """Persist a clearly labeled non-live compatibility envelope."""

        if filename is None:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            filename = f"reports/paper_candidates_{timestamp}.json"
        output = Path(filename)
        output.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "runtime_status": LEGACY_RUNTIME_STATUS,
            "authority": PAPER_AUTHORITY,
            "live_wagers_authorized": False,
            "bankroll_used_for_action": False,
            "candidate_count": len(picks),
            "candidates": picks,
        }
        output.write_text(
            json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8"
        )
        return str(output)

    def print_picks_report(self, picks: List[Dict[str, Any]]) -> None:
        """Print the honest runtime status."""

        print("DAILY PICKS LEGACY PATH: DISABLED")
        print(_DISABLED_REASON)
        print(f"Canonical paper candidates supplied: {len(picks)}")


def _blocked_payload() -> Dict[str, Any]:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "runtime_status": LEGACY_RUNTIME_STATUS,
        "authority": PAPER_AUTHORITY,
        "live_wagers_authorized": False,
        "status": "NO_BET",
        "reason": _DISABLED_REASON,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compatibility wrapper for canonical paper-decision evaluation"
    )
    parser.add_argument(
        "--input",
        help="JSON containing canonical candidates; no input means explicit NO_BET",
    )
    parser.add_argument(
        "--output",
        default="reports/paper_decision_receipts.json",
        help="Output JSON file",
    )
    parser.add_argument("--now", help="Optional ISO-8601 evaluation time")
    parser.add_argument("--max-age-seconds", type=int, default=300)
    parser.add_argument("--min-ev-lower-bound", type=float, default=0.0)
    args = parser.parse_args()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    if not args.input:
        blocked = _blocked_payload()
        output.write_text(
            json.dumps(blocked, indent=2, sort_keys=True), encoding="utf-8"
        )
        print(json.dumps(blocked, indent=2, sort_keys=True))
        return 2

    try:
        payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
        now = parse_utc_datetime(args.now, "now") if args.now else None
        result = evaluate_payload(
            payload,
            now=now,
            max_age_seconds=args.max_age_seconds,
            min_expected_value_lower_bound=args.min_ev_lower_bound,
        )
    except (OSError, json.JSONDecodeError, DecisionContractError) as exc:
        error = {
            **_blocked_payload(),
            "reason": f"invalid_input:{exc}",
        }
        output.write_text(json.dumps(error, indent=2, sort_keys=True), encoding="utf-8")
        print(json.dumps(error, indent=2, sort_keys=True))
        return 64

    output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
