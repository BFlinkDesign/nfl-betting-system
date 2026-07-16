import pytest

from src.betting.kelly import BetSizingBlockedError, KellyCriterion


def test_aggressive_mode_is_rejected():
    with pytest.raises(ValueError, match="aggressive_mode was removed"):
        KellyCriterion(aggressive_mode=True)


def test_fraction_uses_probability_lower_bound_and_two_percent_cap():
    kelly = KellyCriterion(max_bet_pct=0.02)

    fraction = kelly.calculate_fraction(
        0.80,
        2.0,
        probability_lower_bound=0.70,
        evidence_status="out_of_sample_validated",
    )

    assert fraction == pytest.approx(0.02)


def test_unverified_or_negative_lower_bound_edge_returns_zero():
    kelly = KellyCriterion(min_probability=0.50)

    assert (
        kelly.calculate_fraction(
            0.70,
            1.8,
            probability_lower_bound=0.65,
            evidence_status="research_only",
        )
        == 0.0
    )
    assert (
        kelly.calculate_fraction(
            0.70,
            1.4,
            probability_lower_bound=0.55,
            evidence_status="out_of_sample_validated",
        )
        == 0.0
    )


def test_hot_streak_multiplier_is_prohibited():
    kelly = KellyCriterion()
    with pytest.raises(ValueError, match="hot-streak"):
        kelly.calculate_fraction(
            0.70,
            2.0,
            probability_lower_bound=0.65,
            evidence_status="paper_trading",
            recent_performance={"win_rate_last_10": 0.9},
        )


def test_paper_mode_blocks_dollar_sizing():
    kelly = KellyCriterion(deployment_mode="paper")

    with pytest.raises(BetSizingBlockedError, match="deployment_mode"):
        kelly.calculate_bet_size(
            0.70,
            2.0,
            1000.0,
            probability_lower_bound=0.65,
            evidence_status="live_validated",
            live_wager_authorized=True,
        )


def test_live_mode_requires_authority_and_live_validated_evidence():
    kelly = KellyCriterion(deployment_mode="live")

    with pytest.raises(BetSizingBlockedError, match="authorization"):
        kelly.calculate_bet_size(
            0.70,
            2.0,
            1000.0,
            probability_lower_bound=0.65,
            evidence_status="live_validated",
        )
    with pytest.raises(BetSizingBlockedError, match="live_validated"):
        kelly.calculate_bet_size(
            0.70,
            2.0,
            1000.0,
            probability_lower_bound=0.65,
            evidence_status="paper_trading",
            live_wager_authorized=True,
        )


def test_explicit_live_path_remains_capped():
    kelly = KellyCriterion(deployment_mode="live", max_bet_pct=0.02)

    size = kelly.calculate_bet_size(
        0.80,
        2.0,
        1000.0,
        probability_lower_bound=0.70,
        evidence_status="live_validated",
        live_wager_authorized=True,
    )

    assert size == pytest.approx(20.0)
