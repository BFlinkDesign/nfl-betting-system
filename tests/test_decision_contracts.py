from datetime import datetime, timedelta, timezone

import pytest

from src.betting.decision_contracts import (
    DecisionContractError,
    DecisionStatus,
    MarketSnapshot,
    ModelEstimate,
    evaluate_for_paper_tracking,
    expected_value,
    minimum_acceptable_odds,
)

NOW = datetime(2026, 9, 10, 18, 0, tzinfo=timezone.utc)
HASH_A = "a" * 64
HASH_B = "b" * 64


def market_mapping(**overrides):
    data = {
        "snapshot_id": "snap-001",
        "event_id": "event-001",
        "market_key": "h2h",
        "selection_key": "home",
        "sportsbook": "ExampleBook",
        "source": "odds-api-archive",
        "american_odds": 150,
        "observed_at": (NOW - timedelta(seconds=30)).isoformat(),
        "event_start_at": (NOW + timedelta(hours=2)).isoformat(),
        "source_hash": HASH_A,
    }
    data.update(overrides)
    return data


def estimate_mapping(**overrides):
    data = {
        "estimate_id": "estimate-001",
        "model_id": "model@abc123",
        "evaluation_id": "walk-forward-2026-01",
        "point_probability": 0.50,
        "lower_probability_bound": 0.45,
        "evidence_status": "out_of_sample_validated",
        "generated_at": (NOW - timedelta(minutes=5)).isoformat(),
        "data_cutoff_at": (NOW - timedelta(hours=1)).isoformat(),
        "artifact_hash": HASH_B,
    }
    data.update(overrides)
    return data


def test_positive_lower_bound_ev_creates_paper_track_receipt():
    snapshot = MarketSnapshot.from_mapping(market_mapping())
    estimate = ModelEstimate.from_mapping(estimate_mapping())

    receipt = evaluate_for_paper_tracking(snapshot, estimate, now=NOW)

    assert receipt.status is DecisionStatus.PAPER_TRACK
    assert receipt.authority == "paper_only_no_live_wager_authority"
    assert receipt.expected_value_point == pytest.approx(0.25)
    assert receipt.expected_value_lower_bound == pytest.approx(0.125)
    assert receipt.minimum_acceptable_decimal_odds == pytest.approx(1 / 0.45)
    assert receipt.fallback == "NO_BET"
    assert len(receipt.decision_id) == 64


def test_stale_price_fails_closed_even_when_point_ev_is_positive():
    snapshot = MarketSnapshot.from_mapping(
        market_mapping(observed_at=(NOW - timedelta(minutes=10)).isoformat())
    )
    estimate = ModelEstimate.from_mapping(estimate_mapping())

    receipt = evaluate_for_paper_tracking(
        snapshot, estimate, now=NOW, max_age_seconds=300
    )

    assert receipt.status is DecisionStatus.NO_BET
    assert "market_snapshot_stale" in receipt.blockers


def test_unqualified_model_evidence_fails_closed():
    snapshot = MarketSnapshot.from_mapping(market_mapping())
    estimate = ModelEstimate.from_mapping(
        estimate_mapping(evidence_status="research_only")
    )

    receipt = evaluate_for_paper_tracking(snapshot, estimate, now=NOW)

    assert receipt.status is DecisionStatus.NO_BET
    assert "model_evidence_not_qualified:research_only" in receipt.blockers


def test_event_started_and_post_event_cutoff_are_blocked():
    snapshot = MarketSnapshot.from_mapping(
        market_mapping(
            observed_at=(NOW - timedelta(hours=2)).isoformat(),
            event_start_at=(NOW - timedelta(hours=1)).isoformat(),
        )
    )
    estimate = ModelEstimate.from_mapping(
        estimate_mapping(data_cutoff_at=(NOW - timedelta(minutes=30)).isoformat())
    )

    receipt = evaluate_for_paper_tracking(
        snapshot, estimate, now=NOW, max_age_seconds=10000
    )

    assert receipt.status is DecisionStatus.NO_BET
    assert "event_already_started" in receipt.blockers
    assert "model_data_cutoff_not_pregame" in receipt.blockers


def test_market_contract_requires_timezone_and_hash():
    with pytest.raises(DecisionContractError, match="timezone"):
        MarketSnapshot.from_mapping(market_mapping(observed_at="2026-09-10T17:59:30"))
    with pytest.raises(DecisionContractError, match="SHA-256"):
        MarketSnapshot.from_mapping(market_mapping(source_hash="not-a-hash"))


def test_lower_bound_not_point_estimate_controls_decision():
    snapshot = MarketSnapshot.from_mapping(market_mapping(american_odds=-120))
    estimate = ModelEstimate.from_mapping(
        estimate_mapping(point_probability=0.70, lower_probability_bound=0.50)
    )

    receipt = evaluate_for_paper_tracking(snapshot, estimate, now=NOW)

    assert expected_value(0.70, -120) > 0
    assert receipt.expected_value_lower_bound < 0
    assert receipt.status is DecisionStatus.NO_BET
    assert "lower_bound_expected_value_not_above_threshold" in receipt.blockers


def test_minimum_price_threshold_is_price_sensitive():
    decimal_odds, american_odds = minimum_acceptable_odds(0.60, 0.05)

    assert decimal_odds == pytest.approx(1.75)
    assert american_odds == pytest.approx(-133.3333333)
