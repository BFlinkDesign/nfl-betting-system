from datetime import datetime, timedelta, timezone

import pytest

from src.betting.decision_receipt import (
    DecisionCode,
    DecisionPolicy,
    EvidenceStatus,
    JointProbabilityEstimate,
    MarketSnapshot,
    OutcomeQuote,
    ParlayQuote,
    ProbabilityEstimate,
    UserIntent,
    evaluate_parlay,
    evaluate_single_market,
    payout_breakdown,
    reconcile_parlay_price,
)

NOW = datetime(2026, 7, 16, 12, 0, tzinfo=timezone.utc)
HASH = "a" * 64
COMMIT = "abcdef1234567890"


def market(*, observed_at=None, status="open"):
    from src.betting.decision_receipt import MarketStatus

    return MarketSnapshot(
        event_id="2026-W01-BUF-KC",
        competition="NFL 2026",
        market_id="2026-W01-BUF-KC:moneyline",
        market_type="moneyline_2way",
        bookmaker="example-book",
        observed_at=observed_at or NOW - timedelta(seconds=30),
        starts_at=NOW + timedelta(hours=2),
        outcomes=(OutcomeQuote("BUF", -110), OutcomeQuote("KC", -110)),
        status=MarketStatus(status),
        source_receipt_id="quote-receipt-1",
    )


def estimate(*, probability=0.58, evidence=EvidenceStatus.OUT_OF_SAMPLE_VALIDATED):
    return ProbabilityEstimate(
        event_id="2026-W01-BUF-KC",
        market_id="2026-W01-BUF-KC:moneyline",
        selection="BUF",
        win_probability=probability,
        generated_at=NOW - timedelta(minutes=5),
        model_id="nfl-calibrated-v1",
        model_version="1.0.0",
        model_artifact_sha256=HASH,
        dataset_id="nfl-snapshot-2026-07-16",
        source_commit=COMMIT,
        evidence_status=evidence,
    )


def test_information_request_never_turns_into_bet_offer():
    receipt = evaluate_single_market(
        intent=UserIntent.INFORMATION,
        snapshot=market(),
        estimate=estimate(),
        now=NOW,
    )
    assert receipt["decision"] == DecisionCode.NO_BET.value
    assert "information_request_must_be_answered_without_a_wager_recommendation" in receipt["reasons"]
    assert receipt["metrics"] == {}


def test_live_money_request_is_blocked_by_default():
    receipt = evaluate_single_market(
        intent=UserIntent.LIVE_BET_REQUEST,
        snapshot=market(),
        estimate=estimate(),
        now=NOW,
    )
    assert receipt["decision"] == DecisionCode.BLOCKED.value
    assert "live_money_not_authorized" in receipt["blockers"]


def test_stale_market_snapshot_fails_closed():
    receipt = evaluate_single_market(
        intent=UserIntent.PAPER_BET_EVALUATION,
        snapshot=market(observed_at=NOW - timedelta(minutes=10)),
        estimate=estimate(),
        now=NOW,
    )
    assert receipt["decision"] == DecisionCode.BLOCKED.value
    assert "market_snapshot_stale" in receipt["blockers"]


def test_research_only_model_cannot_be_promoted_to_paper_candidate():
    receipt = evaluate_single_market(
        intent=UserIntent.PAPER_BET_EVALUATION,
        snapshot=market(),
        estimate=estimate(evidence=EvidenceStatus.RESEARCH_ONLY),
        now=NOW,
    )
    assert receipt["decision"] == DecisionCode.BLOCKED.value
    assert "model_evidence_below_policy_minimum" in receipt["blockers"]


def test_evidenced_positive_edge_becomes_capped_paper_candidate():
    receipt = evaluate_single_market(
        intent=UserIntent.PAPER_BET_EVALUATION,
        snapshot=market(),
        estimate=estimate(probability=0.58),
        now=NOW,
    )
    assert receipt["decision"] == DecisionCode.PAPER_CANDIDATE.value
    assert receipt["metrics"]["expected_value_per_unit"] > 0.03
    assert receipt["metrics"]["paper_stake_fraction"] == pytest.approx(0.005)
    assert len(receipt["receipt_sha256"]) == 64

    repeated = evaluate_single_market(
        intent=UserIntent.PAPER_BET_EVALUATION,
        snapshot=market(),
        estimate=estimate(probability=0.58),
        now=NOW,
    )
    assert repeated["receipt_sha256"] == receipt["receipt_sha256"]


def test_system_can_return_no_bet_without_forcing_a_stake():
    receipt = evaluate_single_market(
        intent=UserIntent.PAPER_BET_EVALUATION,
        snapshot=market(),
        estimate=estimate(probability=0.52),
        now=NOW,
    )
    assert receipt["decision"] == DecisionCode.NO_BET.value
    assert receipt["metrics"]["paper_stake_fraction"] == 0.0
    assert "expected_value_below_policy_minimum" in receipt["reasons"]


def test_profit_and_total_return_are_not_conflated():
    assert payout_breakdown(10, 998) == {
        "stake": 10.0,
        "profit": 99.8,
        "total_return": 109.8,
    }


def test_world_cup_visible_leg_prices_do_not_reconcile_to_reported_total():
    audit = reconcile_parlay_price((-650, 430, -500), 998)
    assert audit["status"] == "UNEXPLAINED_PRICE_DIFFERENCE"
    assert audit["expected_american_from_visible_legs"] == pytest.approx(633.85, abs=0.02)

    documented = reconcile_parlay_price(
        (-650, 430, -500),
        998,
        pricing_adjustment_id="sportsbook-boost-receipt-123",
    )
    assert documented["status"] == "RECONCILED_EXPLICIT_ADJUSTMENT"


def parlay_quote(*, pricing_adjustment_id=""):
    from src.betting.decision_receipt import MarketStatus

    return ParlayQuote(
        parlay_id="parlay-1",
        bookmaker="example-book",
        leg_market_ids=("game-a:ml", "game-b:ml", "game-c:ml"),
        leg_american_odds=(-650, 430, -500),
        quoted_american_odds=998,
        observed_at=NOW - timedelta(seconds=20),
        earliest_start_at=NOW + timedelta(hours=1),
        status=MarketStatus.OPEN,
        pricing_adjustment_id=pricing_adjustment_id,
        source_receipt_id="betslip-raw-1",
    )


def joint_estimate(*, correlation_evidence_id="corr-study-1"):
    return JointProbabilityEstimate(
        parlay_id="parlay-1",
        leg_market_ids=("game-a:ml", "game-b:ml", "game-c:ml"),
        joint_probability=0.12,
        generated_at=NOW - timedelta(minutes=3),
        model_id="joint-market-model",
        model_version="1.0.0",
        model_artifact_sha256=HASH,
        dataset_id="joint-snapshot-2026-07-16",
        source_commit=COMMIT,
        evidence_status=EvidenceStatus.OUT_OF_SAMPLE_VALIDATED,
        correlation_evidence_id=correlation_evidence_id,
    )


def test_parlays_are_disabled_by_default_even_with_joint_model():
    receipt = evaluate_parlay(
        intent=UserIntent.PAPER_BET_EVALUATION,
        quote=parlay_quote(pricing_adjustment_id="boost-1"),
        estimate=joint_estimate(),
        now=NOW,
    )
    assert receipt["decision"] == DecisionCode.BLOCKED.value
    assert "parlays_disabled_by_policy" in receipt["blockers"]


def test_enabled_parlay_requires_joint_and_price_evidence():
    policy = DecisionPolicy(parlays_authorized=True)
    receipt = evaluate_parlay(
        intent=UserIntent.PAPER_BET_EVALUATION,
        quote=parlay_quote(pricing_adjustment_id="boost-1"),
        estimate=joint_estimate(),
        now=NOW,
        policy=policy,
    )
    assert receipt["decision"] == DecisionCode.PAPER_CANDIDATE.value
    assert receipt["metrics"]["paper_stake_fraction"] <= policy.max_parlay_paper_stake_fraction

    missing_correlation = evaluate_parlay(
        intent=UserIntent.PAPER_BET_EVALUATION,
        quote=parlay_quote(pricing_adjustment_id="boost-1"),
        estimate=joint_estimate(correlation_evidence_id=""),
        now=NOW,
        policy=policy,
    )
    assert missing_correlation["decision"] == DecisionCode.BLOCKED.value
    assert "correlation_evidence_missing" in missing_correlation["blockers"]


def test_unexplained_parlay_price_blocks_even_when_parlays_enabled():
    receipt = evaluate_parlay(
        intent=UserIntent.PAPER_BET_EVALUATION,
        quote=parlay_quote(),
        estimate=joint_estimate(),
        now=NOW,
        policy=DecisionPolicy(parlays_authorized=True),
    )
    assert receipt["decision"] == DecisionCode.BLOCKED.value
    assert "parlay_price_does_not_reconcile_and_no_adjustment_is_documented" in receipt["blockers"]
