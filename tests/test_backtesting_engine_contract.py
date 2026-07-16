"""Tests for provenance-bound paper backtesting."""

from __future__ import annotations

import pandas as pd
import pytest

from src.backtesting.engine import BacktestContractError, BacktestEngine


def _config() -> dict:
    return {
        "source_commit": "a" * 40,
        "dataset_snapshot_id": "dataset:fixture-v1",
        "evaluation_id": "evaluation:fixture-v1",
        "max_bet_size": 0.01,
    }


def test_backtest_requires_run_provenance() -> None:
    with pytest.raises(BacktestContractError, match="missing run provenance"):
        BacktestEngine(config={})


def test_backtest_requires_lower_bound_and_evidence_columns() -> None:
    engine = BacktestEngine(config=_config())
    frame = pd.DataFrame(
        [{"game_id": "g1", "gameday": "2026-01-01", "pred_prob": 0.60}]
    )

    with pytest.raises(BacktestContractError, match="missing prediction columns"):
        engine.run_backtest(frame)


def test_backtest_uses_lower_bound_and_logs_no_bet() -> None:
    engine = BacktestEngine(config=_config())
    frame = pd.DataFrame(
        [
            {
                "game_id": "g1",
                "gameday": "2026-01-01",
                "home_team": "Home",
                "away_team": "Away",
                "pred_prob": 0.65,
                "probability_lower_bound": 0.60,
                "actual": 1,
                "odds": 2.0,
                "closing_odds": 1.8,
                "evidence_status": "out_of_sample_validated",
            },
            {
                "game_id": "g2",
                "gameday": "2026-01-02",
                "home_team": "Home2",
                "away_team": "Away2",
                "pred_prob": 0.60,
                "probability_lower_bound": 0.55,
                "actual": 0,
                "odds": 1.5,
                "closing_odds": 1.5,
                "evidence_status": "out_of_sample_validated",
            },
        ]
    )
    original = frame.copy(deep=True)

    metrics, history = engine.run_backtest(frame)

    pd.testing.assert_frame_equal(frame, original)
    assert metrics["status"] == "PAPER_SIMULATION"
    assert metrics["paper_tracks"] == 1
    assert metrics["no_bets"] == 1
    assert metrics["total_staked"] == pytest.approx(100.0)
    assert metrics["total_profit"] == pytest.approx(100.0)
    assert metrics["roi_on_staked_capital"] == pytest.approx(100.0)
    assert metrics["avg_closing_price_value"] == pytest.approx(
        (2.0 / 1.8 - 1.0) * 100
    )
    assert list(history["decision_status"]) == ["PAPER_TRACK", "NO_BET"]
    assert list(history["paper_stake"]) == [pytest.approx(100.0), 0.0]


def test_research_only_estimate_cannot_create_paper_stake() -> None:
    engine = BacktestEngine(config=_config())
    frame = pd.DataFrame(
        [
            {
                "game_id": "g1",
                "gameday": "2026-01-01",
                "pred_prob": 0.90,
                "probability_lower_bound": 0.80,
                "actual": 1,
                "odds": 2.0,
                "evidence_status": "research_only",
            }
        ]
    )

    metrics, history = engine.run_backtest(frame)

    assert metrics["paper_tracks"] == 0
    assert metrics["no_bets"] == 1
    assert history.iloc[0]["paper_stake"] == 0.0
