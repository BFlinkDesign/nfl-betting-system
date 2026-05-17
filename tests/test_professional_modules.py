"""Test all professional operations modules."""

import os
import tempfile
from datetime import datetime

import numpy as np
import pandas as pd
import pytest


class TestStatisticalValidator:
    """Test statistical validation module."""

    def test_validator_runs(self):
        from src.validation.statistical_validator import ProfessionalValidator

        np.random.seed(42)
        n = 500
        test_df = pd.DataFrame({
            'bet_odds': np.random.uniform(1.8, 2.2, n),
            'closing_odds': np.random.uniform(1.85, 2.15, n),
            'result': np.random.binomial(1, 0.54, n),
            'pred_prob': np.random.uniform(0.48, 0.62, n),
            'season': np.random.choice([2022, 2023, 2024], n)
        })

        validator = ProfessionalValidator(test_df)
        passed, results = validator.validate_all()

        assert len(results) > 0
        assert all(hasattr(r, 'passed') for r in results)

    def test_sample_size_check(self):
        from src.validation.statistical_validator import ProfessionalValidator

        # Small sample
        small_df = pd.DataFrame({
            'result': [1, 0, 1],
            'season': [2024, 2024, 2024]
        })

        validator = ProfessionalValidator(small_df)
        passed, results = validator.validate_all()

        sample_check = next(r for r in results if r.metric_name == 'sample_size_minimum')
        assert not sample_check.passed  # Should fail with 3 bets


class TestPositionTracker:
    """Test position tracking module."""

    def test_tracker_initialization(self):
        from src.operations.position_tracker import PositionTracker, Account

        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name

        try:
            tracker = PositionTracker(db_path=db_path, initial_bankroll=10000)
            assert tracker.get_total_bankroll() == 10000

            # Add account
            tracker.add_account(Account(
                book='TestBook',
                balance=5000,
                deposited=5000,
                withdrawn=0,
                status='active'
            ))

            assert tracker.get_total_bankroll() == 5000
        finally:
            os.unlink(db_path)

    def test_exposure_limits(self):
        from src.operations.position_tracker import PositionTracker, Account, Bet, ExposureLimits

        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            db_path = f.name

        try:
            limits = ExposureLimits(max_single_bet_pct=0.01)
            tracker = PositionTracker(db_path=db_path, initial_bankroll=10000, limits=limits)

            tracker.add_account(Account(
                book='TestBook',
                balance=10000,
                deposited=10000,
                withdrawn=0,
                status='active'
            ))

            # Try to place bet exceeding limit
            big_bet = Bet(
                bet_id='big_1',
                timestamp=datetime.now(),
                game_id='game_1',
                book='TestBook',
                market='moneyline',
                selection='KC',
                odds=2.0,
                stake=500,  # 5% of bankroll, exceeds 1% limit
                potential_payout=1000,
                model_prob=0.55,
                model_edge=0.05,
                result='pending'
            )

            success, msg = tracker.record_bet(big_bet)
            assert not success
            assert 'single bet limit' in msg.lower()
        finally:
            os.unlink(db_path)


class TestLineShopper:
    """Test line shopping module."""

    def test_find_best_line(self):
        from src.operations.line_shopper import LineShopper

        shopper = LineShopper()
        best = shopper.find_best_line(
            game_id='test_1',
            market='moneyline',
            selection='KC',
            current_odds={'Pinnacle': 1.95, 'DraftKings': 1.91, 'FanDuel': 1.93},
            model_prob=0.55
        )

        assert best.best_odds == 1.95
        assert best.best_book == 'Pinnacle'
        assert len(best.all_odds) == 3

    def test_line_value_calculation(self):
        from src.operations.line_shopper import LineShopper

        shopper = LineShopper()
        value = shopper.get_line_shopping_value(
            worst_odds=1.91,  # -110
            best_odds=2.00,   # +100
            stake=100
        )

        # Win $91 at 1.91, win $100 at 2.00, difference = $9
        assert abs(value - 9) < 0.01

    def test_odds_conversion(self):
        from src.operations.line_shopper import LineShopper

        shopper = LineShopper()

        # -110 American = 1.909 decimal
        assert abs(shopper.american_to_decimal(-110) - 1.909) < 0.01

        # +150 American = 2.50 decimal
        assert abs(shopper.american_to_decimal(150) - 2.50) < 0.01


class TestDailyWorkflow:
    """Test daily workflow module."""

    def test_morning_routine(self):
        from src.operations.daily_workflow import DailyWorkflow

        workflow = DailyWorkflow(min_edge=0.02, min_probability=0.52)

        games = pd.DataFrame({
            'game_id': ['g1', 'g2'],
            'home_team': ['KC', 'BUF'],
            'away_team': ['LV', 'MIA']
        })

        plan = workflow.run_morning_routine(games)

        assert plan.games_analyzed == 2
        assert isinstance(plan.value_bets, list)
        assert plan.generated_at is not None

    def test_kelly_calculation(self):
        from src.operations.daily_workflow import DailyWorkflow

        workflow = DailyWorkflow()

        # With 55% prob and 2.0 odds, full Kelly = 10%
        # Fractional Kelly (25%) = 2.5%
        stake = workflow._calculate_kelly_stake(prob=0.55, odds=2.0, fraction=0.25)

        assert stake > 0
        assert stake <= 0.03  # Capped at 3%


class TestPerformanceDashboard:
    """Test performance dashboard module."""

    def test_metrics_calculation(self):
        from src.operations.performance_dashboard import PerformanceDashboard
        from src.operations.position_tracker import Bet
        from datetime import datetime

        dashboard = PerformanceDashboard()

        # Create sample bets
        bets = [
            Bet(bet_id='1', timestamp=datetime.now(), game_id='g1', book='Test',
                market='ml', selection='KC', odds=2.0, stake=100, potential_payout=200,
                model_prob=0.55, model_edge=0.05, closing_odds=1.95, clv=0.025,
                result='win', profit=100),
            Bet(bet_id='2', timestamp=datetime.now(), game_id='g2', book='Test',
                market='ml', selection='BUF', odds=1.9, stake=100, potential_payout=190,
                model_prob=0.56, model_edge=0.04, closing_odds=1.85, clv=0.027,
                result='loss', profit=-100),
        ]

        metrics = dashboard.calculate_metrics(bets)

        assert metrics['total_bets'] == 2
        assert metrics['wins'] == 1
        assert metrics['losses'] == 1
        assert metrics['win_rate'] == 0.5
        assert metrics['avg_clv'] > 0

    def test_health_assessment(self):
        from src.operations.performance_dashboard import PerformanceDashboard

        dashboard = PerformanceDashboard()

        # Healthy metrics
        healthy_metrics = {
            'avg_clv': 0.025,  # 2.5%
            'positive_clv_rate': 0.55,
            'clv_significant': True,
            'ece': 0.03,
            'total_bets': 200
        }

        status, issues = dashboard.assess_health(healthy_metrics)
        assert status == 'healthy'

        # Critical metrics (negative CLV)
        bad_metrics = {
            'avg_clv': -0.01,
            'positive_clv_rate': 0.45,
            'clv_significant': False,
            'ece': 0.08,
            'total_bets': 200
        }

        status, issues = dashboard.assess_health(bad_metrics)
        assert status == 'critical'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
