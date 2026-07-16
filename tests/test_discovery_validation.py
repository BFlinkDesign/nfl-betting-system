import pytest

from src.discovery_validation import (
    PromotionPolicy,
    american_to_decimal,
    assess_promotion,
    benjamini_hochberg,
    flat_stake_roi,
    wilson_lower_bound,
)


def test_american_to_decimal():
    assert american_to_decimal(150) == pytest.approx(2.5)
    assert american_to_decimal(-200) == pytest.approx(1.5)
    with pytest.raises(ValueError):
        american_to_decimal(0)


def test_flat_stake_roi_handles_pushes_and_actual_prices():
    # +1.0 profit at 2.0, -1.0 loss, push excluded => zero ROI.
    assert flat_stake_roi([1, 0, -1], [2.0, 1.91, 1.91]) == pytest.approx(0.0)
    with pytest.raises(ValueError):
        flat_stake_roi([-1], [1.91])


def test_benjamini_hochberg_adjustment_is_monotonic_and_order_preserving():
    adjusted = benjamini_hochberg([0.01, 0.04, 0.03, 0.20])
    assert adjusted == pytest.approx([0.04, 0.0533333333, 0.0533333333, 0.20])


def test_wilson_lower_bound_rewards_evidence_not_point_estimate_alone():
    assert wilson_lower_bound(70, 100) < 0.70
    assert wilson_lower_bound(700, 1000) > wilson_lower_bound(70, 100)


def test_promotion_fails_closed_without_prices_holdout_and_reproducibility():
    decision = assess_promotion(
        discovery_sample_size=200,
        holdout_sample_size=100,
        holdout_wins=65,
        holdout_roi=0.10,
        holdout_roi_lower_bound=None,
        adjusted_p_value=0.01,
        uses_actual_market_prices=False,
        has_temporal_holdout=False,
        has_reproducible_condition=False,
        policy=PromotionPolicy(break_even_probability=0.50),
    )
    assert not decision.eligible
    assert "holdout ROI uncertainty bound is missing" in decision.blockers
    assert "actual market prices were not used" in decision.blockers
    assert "independent temporal holdout is missing" in decision.blockers
    assert "strategy condition is not executable and reproducible" in decision.blockers


def test_promotion_can_pass_when_every_gate_is_evidenced():
    decision = assess_promotion(
        discovery_sample_size=500,
        holdout_sample_size=300,
        holdout_wins=190,
        holdout_roi=0.08,
        holdout_roi_lower_bound=0.02,
        adjusted_p_value=0.01,
        uses_actual_market_prices=True,
        has_temporal_holdout=True,
        has_reproducible_condition=True,
        policy=PromotionPolicy(break_even_probability=0.524),
    )
    assert decision.eligible
    assert decision.blockers == ()


def test_default_policy_does_not_assume_universal_break_even_win_rate():
    decision = assess_promotion(
        discovery_sample_size=500,
        holdout_sample_size=300,
        holdout_wins=135,
        holdout_roi=0.06,
        holdout_roi_lower_bound=0.01,
        adjusted_p_value=0.01,
        uses_actual_market_prices=True,
        has_temporal_holdout=True,
        has_reproducible_condition=True,
    )
    assert decision.eligible
    assert decision.holdout_wilson_lower_bound < 0.50
