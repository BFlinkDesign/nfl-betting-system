"""Tests for Kelly criterion bet sizing."""

from src.betting.kelly import KellyCriterion


class TestKellyCriterion:
    def test_no_bet_below_min_probability(self):
        kelly = KellyCriterion(min_probability=0.55)
        assert kelly.calculate_bet_size(prob_win=0.50, odds=2.0, bankroll=1000) == 0.0

    def test_no_bet_below_min_edge(self):
        kelly = KellyCriterion(min_edge=0.02)
        assert kelly.calculate_bet_size(prob_win=0.55, odds=1.82, bankroll=1000) == 0.0

    def test_positive_bet_with_edge(self):
        kelly = KellyCriterion(
            kelly_fraction=0.25,
            min_edge=0.01,
            min_probability=0.50,
            aggressive_mode=False,
        )
        bet = kelly.calculate_bet_size(prob_win=0.65, odds=2.0, bankroll=10000)
        assert bet > 0
        assert bet <= 10000 * 0.02

    def test_bankroll_proportional(self):
        kelly = KellyCriterion(aggressive_mode=False)
        small = kelly.calculate_bet_size(prob_win=0.65, odds=2.0, bankroll=1000)
        large = kelly.calculate_bet_size(prob_win=0.65, odds=2.0, bankroll=10000)
        assert large > small

    def test_aggressive_multiplier_heavy_favorite(self):
        conservative = KellyCriterion(
            aggressive_mode=False, min_probability=0.50, min_edge=0.01
        )
        aggressive = KellyCriterion(
            aggressive_mode=True, min_probability=0.50, min_edge=0.01
        )

        c_bet = conservative.calculate_bet_size(prob_win=0.75, odds=1.5, bankroll=10000)
        a_bet = aggressive.calculate_bet_size(prob_win=0.75, odds=1.5, bankroll=10000)
        assert a_bet > c_bet

    def test_max_cap_conservative(self):
        kelly = KellyCriterion(
            max_bet_pct=0.02, aggressive_mode=False, min_probability=0.50, min_edge=0.0
        )
        bet = kelly.calculate_bet_size(prob_win=0.99, odds=10.0, bankroll=10000)
        assert bet <= 10000 * 0.02 + 0.01

    def test_zero_bankroll(self):
        kelly = KellyCriterion(min_probability=0.50, min_edge=0.0)
        bet = kelly.calculate_bet_size(prob_win=0.70, odds=2.0, bankroll=0)
        assert bet == 0.0

    def test_non_negative(self):
        kelly = KellyCriterion(
            min_probability=0.50, min_edge=0.0, aggressive_mode=False
        )
        bet = kelly.calculate_bet_size(prob_win=0.51, odds=1.01, bankroll=10000)
        assert bet >= 0.0
