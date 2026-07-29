"""Fail-closed, paper-only parlay evidence evaluator.

The legacy generator multiplied marginal win probabilities, synthesized missing
prices, mixed best-leg prices from different books, and labeled the result a
recommendation. This replacement requires:

* one actual, fresh, same-book parlay offer;
* immutable market and model evidence hashes;
* qualified lower-bound probability evidence for every leg;
* one explicit validated joint-probability estimate for the exact leg set; and
* positive expected value at the probability lower bound.

The output may contain PAPER_TRACK candidates. It never authorizes, sizes, or
places a live wager.
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.betting.decision_contracts import (  # noqa: E402
    CONTRACT_VERSION,
    PAPER_AUTHORITY,
    DecisionContractError,
    DecisionStatus,
    MarketSnapshot,
    ModelEstimate,
    evaluate_for_paper_tracking,
    parse_utc_datetime,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

DEFAULT_MAX_COMBINATIONS = 1000
DEFAULT_MAX_RESULTS_PER_SIZE = 20


def _first_present(data: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in data and data[key] is not None:
            return data[key]
    return None


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _leg_id(recommendation: Mapping[str, Any], game_info: Mapping[str, Any]) -> str:
    explicit = _text(
        _first_present(recommendation, "selection_id", "leg_id", "candidate_id")
    )
    if explicit:
        return explicit
    event_id = _text(_first_present(recommendation, "event_id")) or _text(
        _first_present(game_info, "game_id", "event_id")
    )
    market_key = _text(_first_present(recommendation, "market_key", "bet_type"))
    selection_key = _text(
        _first_present(recommendation, "selection_key", "team", "side")
    )
    if event_id and market_key and selection_key:
        return f"{event_id}:{market_key}:{selection_key}"
    raise DecisionContractError(
        "leg requires selection_id or event_id + market_key + selection_key"
    )


def _game_label(game_info: Mapping[str, Any]) -> str:
    away = _text(game_info.get("away_team"))
    home = _text(game_info.get("home_team"))
    if away and home:
        return f"{away} @ {home}"
    return _text(_first_present(game_info, "event_name", "game_id")) or "unknown_event"


def _normalize_payload(payload: Any) -> tuple[list[Any], list[Any]]:
    if isinstance(payload, list):
        return payload, []
    if not isinstance(payload, Mapping):
        raise DecisionContractError("input root must be an object or array")

    analyses = _first_present(payload, "analyses", "games", "recommendation_sets")
    if analyses is None and "recommendations" in payload:
        analyses = [payload]
    if analyses is None:
        analyses = []
    joint_estimates = payload.get("joint_estimates", [])
    if not isinstance(analyses, list):
        raise DecisionContractError("analyses must be an array")
    if not isinstance(joint_estimates, list):
        raise DecisionContractError("joint_estimates must be an array")
    return analyses, joint_estimates


def _flatten_recommendations(analyses: Iterable[Any]) -> list[dict[str, Any]]:
    flattened: list[dict[str, Any]] = []
    for analysis_index, analysis in enumerate(analyses):
        if not isinstance(analysis, Mapping):
            flattened.append(
                {
                    "_invalid_analysis": f"analysis_{analysis_index + 1} must be an object"
                }
            )
            continue
        game_info = analysis.get("game_info", {})
        if not isinstance(game_info, Mapping):
            game_info = {}
        recommendations = analysis.get("recommendations", [])
        if not isinstance(recommendations, list):
            flattened.append(
                {
                    "_invalid_analysis": (
                        f"analysis_{analysis_index + 1}.recommendations must be an array"
                    )
                }
            )
            continue
        for recommendation in recommendations:
            if not isinstance(recommendation, Mapping):
                flattened.append(
                    {"_invalid_analysis": "recommendation must be an object"}
                )
                continue
            flattened.append(
                {
                    "recommendation": dict(recommendation),
                    "game_info": dict(game_info),
                    "analysis_defaults": dict(analysis),
                }
            )
    return flattened


def _market_mapping(
    recommendation: Mapping[str, Any],
    game_info: Mapping[str, Any],
    defaults: Mapping[str, Any],
    leg_id: str,
) -> Mapping[str, Any]:
    nested = recommendation.get("market_snapshot")
    if isinstance(nested, Mapping):
        return nested

    event_id = _first_present(recommendation, "event_id") or _first_present(
        game_info, "game_id", "event_id"
    )
    return {
        "snapshot_id": _first_present(recommendation, "snapshot_id"),
        "event_id": event_id,
        "market_key": _first_present(recommendation, "market_key", "bet_type"),
        "selection_key": _first_present(
            recommendation, "selection_key", "team", "side"
        ),
        "sportsbook": recommendation.get("sportsbook"),
        "source": _first_present(recommendation, "odds_source", "source")
        or _first_present(defaults, "odds_source"),
        "american_odds": recommendation.get("odds"),
        "observed_at": _first_present(recommendation, "odds_observed_at", "observed_at")
        or _first_present(defaults, "odds_observed_at"),
        "event_start_at": _first_present(
            recommendation, "event_start_at", "commence_time"
        )
        or _first_present(game_info, "event_start_at", "commence_time"),
        "source_hash": _first_present(
            recommendation, "odds_source_hash", "source_hash"
        ),
        "_leg_id": leg_id,
    }


def _estimate_mapping(
    recommendation: Mapping[str, Any], defaults: Mapping[str, Any]
) -> Mapping[str, Any]:
    nested = recommendation.get("model_estimate")
    if isinstance(nested, Mapping):
        return nested
    return {
        "estimate_id": recommendation.get("estimate_id"),
        "model_id": recommendation.get("model_id"),
        "evaluation_id": recommendation.get("evaluation_id"),
        "point_probability": _first_present(
            recommendation, "point_probability", "win_probability"
        ),
        "lower_probability_bound": _first_present(
            recommendation,
            "lower_probability_bound",
            "probability_lower_bound",
        ),
        "evidence_status": recommendation.get("evidence_status"),
        "generated_at": _first_present(
            recommendation, "estimate_generated_at", "generated_at"
        )
        or _first_present(defaults, "estimate_generated_at"),
        "data_cutoff_at": _first_present(
            recommendation, "data_cutoff_at", "feature_cutoff_at"
        ),
        "artifact_hash": _first_present(
            recommendation, "estimate_artifact_hash", "artifact_hash"
        ),
    }


def _diagnostic_product(values: Iterable[float]) -> float:
    product = 1.0
    for value in values:
        product *= value
    return product


class ParlayGenerator:
    """Evaluate exact, pre-registered parlay evidence for paper tracking."""

    def __init__(
        self,
        *,
        now: Optional[datetime] = None,
        max_age_seconds: int = 300,
        min_expected_value_lower_bound: float = 0.0,
        max_combinations: int = DEFAULT_MAX_COMBINATIONS,
        max_results_per_size: int = DEFAULT_MAX_RESULTS_PER_SIZE,
    ) -> None:
        self.now = parse_utc_datetime(now or datetime.now(timezone.utc), "now")
        if max_age_seconds <= 0:
            raise DecisionContractError("max_age_seconds must be positive")
        if max_combinations <= 0:
            raise DecisionContractError("max_combinations must be positive")
        if max_results_per_size <= 0:
            raise DecisionContractError("max_results_per_size must be positive")
        self.max_age_seconds = max_age_seconds
        self.min_expected_value_lower_bound = min_expected_value_lower_bound
        self.max_combinations = max_combinations
        self.max_results_per_size = max_results_per_size

    def _normalize_leg(self, raw: Mapping[str, Any]) -> dict[str, Any]:
        if "_invalid_analysis" in raw:
            raise DecisionContractError(str(raw["_invalid_analysis"]))
        recommendation = raw["recommendation"]
        game_info = raw["game_info"]
        defaults = raw["analysis_defaults"]
        leg_id = _leg_id(recommendation, game_info)
        snapshot = MarketSnapshot.from_mapping(
            _market_mapping(recommendation, game_info, defaults, leg_id)
        )
        estimate = ModelEstimate.from_mapping(
            _estimate_mapping(recommendation, defaults)
        )
        receipt = evaluate_for_paper_tracking(
            snapshot,
            estimate,
            now=self.now,
            max_age_seconds=self.max_age_seconds,
            min_expected_value_lower_bound=self.min_expected_value_lower_bound,
        )
        if receipt.status is not DecisionStatus.PAPER_TRACK:
            raise DecisionContractError(
                "individual leg is not paper-track eligible: "
                + ", ".join(receipt.blockers)
            )
        return {
            "leg_id": leg_id,
            "team": _text(recommendation.get("team")) or snapshot.selection_key,
            "bet_type": _text(recommendation.get("bet_type")) or snapshot.market_key,
            "game": _game_label(game_info),
            "event_id": snapshot.event_id,
            "sportsbook": snapshot.sportsbook,
            "market_snapshot": snapshot,
            "model_estimate": estimate,
            "individual_receipt": receipt,
        }

    @staticmethod
    def _joint_index(
        joint_estimates: Iterable[Any],
    ) -> dict[frozenset[str], Mapping[str, Any]]:
        indexed: dict[frozenset[str], Mapping[str, Any]] = {}
        for record in joint_estimates:
            if not isinstance(record, Mapping):
                continue
            leg_ids = record.get("leg_ids")
            if not isinstance(leg_ids, list) or len(leg_ids) < 2:
                continue
            normalized = frozenset(str(leg_id) for leg_id in leg_ids)
            if len(normalized) != len(leg_ids):
                continue
            if normalized in indexed:
                raise DecisionContractError(
                    "duplicate joint estimate for leg set: "
                    + ", ".join(sorted(normalized))
                )
            indexed[normalized] = record
        return indexed

    def _evaluate_combination(
        self,
        legs: tuple[dict[str, Any], ...],
        joint_record: Optional[Mapping[str, Any]],
    ) -> tuple[Optional[dict[str, Any]], Optional[dict[str, Any]]]:
        leg_ids = [leg["leg_id"] for leg in legs]
        diagnostic = {
            "point_marginal_product": _diagnostic_product(
                leg["model_estimate"].point_probability for leg in legs
            ),
            "lower_bound_marginal_product": _diagnostic_product(
                leg["model_estimate"].lower_probability_bound for leg in legs
            ),
            "warning": (
                "marginal products are diagnostics only and are never used as "
                "the joint probability"
            ),
        }
        blocked_base = {
            "leg_ids": leg_ids,
            "num_legs": len(legs),
            "games": [leg["game"] for leg in legs],
            "diagnostic": diagnostic,
        }

        sportsbooks = {leg["sportsbook"] for leg in legs}
        if len(sportsbooks) != 1:
            return None, {
                **blocked_base,
                "blockers": ["legs_do_not_share_one_placeable_sportsbook"],
            }
        if joint_record is None:
            return None, {
                **blocked_base,
                "blockers": [
                    "missing_pre_registered_joint_probability_and_exact_parlay_offer"
                ],
            }

        market_data = joint_record.get("market_snapshot", joint_record)
        estimate_data = joint_record.get("model_estimate", joint_record)
        try:
            snapshot = MarketSnapshot.from_mapping(market_data)
            estimate = ModelEstimate.from_mapping(estimate_data)
            only_book = next(iter(sportsbooks))
            blockers: list[str] = []
            if snapshot.sportsbook != only_book:
                blockers.append("parlay_offer_book_does_not_match_leg_book")
            declared_leg_ids = joint_record.get("leg_ids", [])
            if set(str(value) for value in declared_leg_ids) != set(leg_ids):
                blockers.append("joint_estimate_leg_set_mismatch")
            if estimate.estimate_id in {
                leg["model_estimate"].estimate_id for leg in legs
            }:
                blockers.append("joint_estimate_must_be_distinct_from_leg_estimates")
            if blockers:
                return None, {**blocked_base, "blockers": sorted(set(blockers))}

            receipt = evaluate_for_paper_tracking(
                snapshot,
                estimate,
                now=self.now,
                max_age_seconds=self.max_age_seconds,
                min_expected_value_lower_bound=self.min_expected_value_lower_bound,
            )
            candidate = {
                "decision": receipt.to_dict(),
                "num_legs": len(legs),
                "legs": [
                    {
                        "leg_id": leg["leg_id"],
                        "team": leg["team"],
                        "bet_type": leg["bet_type"],
                        "game": leg["game"],
                        "sportsbook": leg["sportsbook"],
                        "individual_decision_id": leg["individual_receipt"].decision_id,
                    }
                    for leg in legs
                ],
                "sportsbook": snapshot.sportsbook,
                "offered_american_odds": snapshot.american_odds,
                "joint_probability_point": estimate.point_probability,
                "joint_probability_lower_bound": estimate.lower_probability_bound,
                "diagnostic": diagnostic,
            }
            if receipt.status is DecisionStatus.PAPER_TRACK:
                return candidate, None
            return None, {
                **blocked_base,
                "blockers": list(receipt.blockers),
                "decision": receipt.to_dict(),
            }
        except (DecisionContractError, KeyError, TypeError) as exc:
            return None, {
                **blocked_base,
                "blockers": [f"joint_contract_error:{exc}"],
            }

    def generate_all_parlays(self, payload: Any) -> dict[str, Any]:
        analyses, joint_estimates = _normalize_payload(payload)
        raw_recommendations = _flatten_recommendations(analyses)
        valid_legs: list[dict[str, Any]] = []
        invalid_legs: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        for index, raw in enumerate(raw_recommendations):
            try:
                leg = self._normalize_leg(raw)
                if leg["leg_id"] in seen_ids:
                    raise DecisionContractError(f"duplicate leg_id: {leg['leg_id']}")
                seen_ids.add(leg["leg_id"])
                valid_legs.append(leg)
            except (DecisionContractError, KeyError, TypeError) as exc:
                invalid_legs.append(
                    {
                        "input_index": index,
                        "status": "NO_BET",
                        "blockers": [f"leg_contract_error:{exc}"],
                    }
                )

        joint_index = self._joint_index(joint_estimates)
        results: dict[str, list[dict[str, Any]]] = {"2_leg": [], "3_leg": []}
        blocked_candidates: list[dict[str, Any]] = []
        possible_combinations = sum(
            math.comb(len(valid_legs), size)
            for size in (2, 3)
            if len(valid_legs) >= size
        )
        if possible_combinations > self.max_combinations:
            return {
                "contract_version": CONTRACT_VERSION,
                "authority": PAPER_AUTHORITY,
                "2_leg": [],
                "3_leg": [],
                "invalid_legs": invalid_legs,
                "blocked_candidates": [
                    {
                        "blockers": [
                            "candidate_space_exceeds_bound; pre-register a smaller set"
                        ],
                        "possible_combinations": possible_combinations,
                        "max_combinations": self.max_combinations,
                    }
                ],
                "summary": {
                    "input_recommendations": len(raw_recommendations),
                    "valid_individual_legs": len(valid_legs),
                    "invalid_individual_legs": len(invalid_legs),
                    "paper_track_parlays": 0,
                    "live_wagers_authorized": False,
                },
            }

        for size, output_key in ((2, "2_leg"), (3, "3_leg")):
            if len(valid_legs) < size:
                continue
            for legs in combinations(valid_legs, size):
                key = frozenset(leg["leg_id"] for leg in legs)
                candidate, blocked = self._evaluate_combination(
                    legs, joint_index.get(key)
                )
                if candidate is not None:
                    results[output_key].append(candidate)
                if blocked is not None:
                    blocked_candidates.append(blocked)

            results[output_key].sort(
                key=lambda item: item["decision"]["expected_value_lower_bound"],
                reverse=True,
            )
            results[output_key] = results[output_key][: self.max_results_per_size]

        paper_count = len(results["2_leg"]) + len(results["3_leg"])
        return {
            "contract_version": CONTRACT_VERSION,
            "generated_at": self.now.isoformat(),
            "authority": PAPER_AUTHORITY,
            "2_leg": results["2_leg"],
            "3_leg": results["3_leg"],
            "invalid_legs": invalid_legs,
            "blocked_candidates": blocked_candidates,
            "summary": {
                "input_recommendations": len(raw_recommendations),
                "valid_individual_legs": len(valid_legs),
                "invalid_individual_legs": len(invalid_legs),
                "evaluated_combinations": possible_combinations,
                "blocked_combinations": len(blocked_candidates),
                "paper_track_parlays": paper_count,
                "live_wagers_authorized": False,
            },
        }

    def load_and_generate(self, input_file: str | Path) -> dict[str, Any]:
        with open(input_file, "r", encoding="utf-8") as handle:
            return self.generate_all_parlays(json.load(handle))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Evaluate parlay evidence for paper tracking only"
    )
    parser.add_argument("--input", required=True, help="Input JSON")
    parser.add_argument(
        "--output", default="reports/parlays.json", help="Output JSON file"
    )
    parser.add_argument("--now", help="Optional ISO-8601 evaluation time")
    parser.add_argument("--max-age-seconds", type=int, default=300)
    parser.add_argument("--min-ev-lower-bound", type=float, default=0.0)
    parser.add_argument(
        "--max-combinations", type=int, default=DEFAULT_MAX_COMBINATIONS
    )
    args = parser.parse_args()

    now = parse_utc_datetime(args.now, "now") if args.now else None
    generator = ParlayGenerator(
        now=now,
        max_age_seconds=args.max_age_seconds,
        min_expected_value_lower_bound=args.min_ev_lower_bound,
        max_combinations=args.max_combinations,
    )
    result = generator.load_and_generate(args.input)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(result, indent=2, sort_keys=True), encoding="utf-8"
    )
    logger.info("Parlay evidence evaluation written to %s", output_path)
    print(json.dumps(result["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
