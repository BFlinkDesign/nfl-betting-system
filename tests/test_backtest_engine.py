"""Tests for backtesting engine."""

import numpy as np
import pandas as pd
import pytest

from src.backtesting.engine import BacktestEngine


@pytest.fixture
def sample_predictions():
    """Create a minimal predictions DataFrame."""
    rng = np.random.default_rng(42)
    n = 50
    return pd.DataFrame(
        {
            "game_id": [f"game_{i}" for i in range(n)],
            "gameday": pd.date_range("2024-09-08", periods=n, freq="7D"),
            "home_team": ["KC"] * n,
            "away_team": ["BUF"] * n,
            "pred_prob": rng.uniform(0.50, 0.80, n),
            "actual": rng.choice([0, 1], n, p=[0.4, 0.6]),
            "odds": rng.uniform(1.5, 3.0, n),
        }
    )


class TestBacktestEngine:
    def test_basic_backtest(self, sample_predictions):
        engine = BacktestEngine(
            initial_bankroll=10000,
            config={"kelly_fraction": 0.25, "min_edge": 0.01, "min_probability": 0.50},
        )
        metrics, history = engine.run_backtest(sample_predictions)

        assert "total_bets" in metrics
        assert "win_rate" in metrics
        assert "roi" in metrics
        assert "max_drawdown" in metrics
        assert "sharpe_ratio" in metrics
        assert metrics["total_bets"] > 0
        assert len(history) == metrics["total_bets"]

    def test_no_bets_when_no_edge(self):
        df = pd.DataFrame(
            {
                "game_id": ["g1"],
                "gameday": ["2024-09-08"],
                "home_team": ["KC"],
                "away_team": ["BUF"],
                "pred_prob": [0.50],
                "actual": [1],
                "odds": [2.0],
            }
        )
        engine = BacktestEngine(config={"min_edge": 0.10, "min_probability": 0.70})
        metrics, _ = engine.run_backtest(df)
        assert (
            metrics.get("error") == "No bets placed"
            or metrics.get("total_bets", 0) == 0
        )

    def test_reset_clears_state(self, sample_predictions):
        engine = BacktestEngine(initial_bankroll=5000)
        engine.run_backtest(sample_predictions)
        assert engine.bet_count > 0

        engine.reset()
        assert engine.bankroll == 5000
        assert engine.bet_count == 0
        assert engine.win_count == 0
        assert len(engine.history) == 0

    def test_bankroll_never_negative(self, sample_predictions):
        engine = BacktestEngine(
            initial_bankroll=100,
            config={"kelly_fraction": 0.25, "min_edge": 0.01, "min_probability": 0.50},
        )
        metrics, history = engine.run_backtest(sample_predictions)
        if len(history) > 0:
            assert history["bankroll"].min() >= 0

    def test_monte_carlo(self, sample_predictions):
        engine = BacktestEngine(
            initial_bankroll=10000,
            config={"kelly_fraction": 0.25, "min_edge": 0.01, "min_probability": 0.50},
        )
        mc = engine.run_monte_carlo(sample_predictions, n_simulations=100, seed=42)

        assert "roi_mean" in mc
        assert "roi_ci_5" in mc
        assert "roi_ci_95" in mc
        assert "prob_profitable" in mc
        assert mc["n_simulations"] == 100
        assert mc["roi_ci_5"] <= mc["roi_ci_95"]
        assert 0 <= mc["prob_profitable"] <= 1
