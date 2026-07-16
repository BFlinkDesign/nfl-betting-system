"""Fail-closed compatibility entry point for historical pregame prediction.

The former module could emit fixed probabilities, placeholder features, sample
schedule rows, and recommendations without executable prices. This replacement
never fetches odds, manufactures probabilities, or recommends a wager. Canonical
market/model evidence must be evaluated through the paper-decision contract.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.evaluate_paper_decisions import evaluate_payload  # noqa: E402

from src.betting.decision_contracts import (  # noqa: E402
    PAPER_AUTHORITY,
    DecisionContractError,
    parse_utc_datetime,
)

logger = logging.getLogger(__name__)

_DISABLED_REASON = (
    "legacy pregame prediction is disabled; fixed probabilities, sample games, "
    "and price-free recommendations are not evidence"
)


class OddsAPIClient:
    """Compatibility shell that performs no network calls."""

    def __init__(self, api_key: str = "") -> None:
        self.api_key_present = bool(api_key)

    def get_nfl_odds(self, markets: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        logger.warning(_DISABLED_REASON)
        return []

    def find_best_odds(
        self, game_odds: Dict[str, Any], bet_type: str, team: str
    ) -> Tuple[None, None]:
        return None, None


class EdgeFilter:
    """Compatibility shell; exploratory edge files cannot authorize picks."""

    def __init__(
        self, edges_file: str = "reports/bulldog_edges_discovered.csv"
    ) -> None:
        self.edges_file = edges_file

    def check_edge(self, game_features: Dict[str, Any], edge_name: str) -> bool:
        return False

    def find_matching_edges(
        self, game_features: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        return []


class PreGameEngine:
    """Non-actionable compatibility adapter."""

    def __init__(self, model_path: str = "models/calibrated_model.pkl") -> None:
        self.model_path = model_path
        self.model = None
        self.feature_pipeline = None
        self.edge_filter = EdgeFilter()
        self.odds_client = OddsAPIClient()

    def generate_features(self, game_info: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "status": "UNAVAILABLE",
            "blockers": ["provenance_bound_feature_pipeline_required"],
            "game_id": game_info.get("game_id"),
        }

    def predict_game(self, features: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "home_win_prob": None,
            "away_win_prob": None,
            "confidence": 0.0,
            "model_used": False,
            "evidence_status": "unverified",
            "status": "NO_BET",
        }

    def analyze_game(self, game_info: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "game_info": dict(game_info),
            "features": self.generate_features(game_info),
            "prediction": self.predict_game({}),
            "odds": None,
            "matching_edges": [],
            "recommendations": [],
            "status": "NO_BET",
            "reason": _DISABLED_REASON,
            "authority": PAPER_AUTHORITY,
            "live_wagers_authorized": False,
        }


def _blocked_payload(reason: str = _DISABLED_REASON) -> Dict[str, Any]:
    return {
        "status": "NO_BET",
        "reason": reason,
        "authority": PAPER_AUTHORITY,
        "live_wagers_authorized": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compatibility wrapper for canonical paper-decision evaluation"
    )
    parser.add_argument("--input", help="Canonical candidate JSON")
    parser.add_argument(
        "--output", default="reports/pregame_paper_decisions.json", help="Output JSON"
    )
    parser.add_argument("--now", help="Optional ISO-8601 evaluation time")
    parser.add_argument("--max-age-seconds", type=int, default=300)
    parser.add_argument("--min-ev-lower-bound", type=float, default=0.0)
    parser.add_argument(
        "--game-id", help="Legacy argument; does not authorize analysis"
    )
    parser.add_argument("--all-today", action="store_true")
    parser.add_argument("--test", action="store_true")
    args = parser.parse_args()

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)

    if not args.input:
        result = _blocked_payload()
        output.write_text(
            json.dumps(result, indent=2, sort_keys=True), encoding="utf-8"
        )
        print(json.dumps(result, indent=2, sort_keys=True))
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
        result = _blocked_payload(f"invalid_input:{exc}")
        output.write_text(
            json.dumps(result, indent=2, sort_keys=True), encoding="utf-8"
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 64

    output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(result["summary"], indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
