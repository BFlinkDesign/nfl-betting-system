"""Regression tests for high-risk historical entry points."""

from __future__ import annotations

import asyncio

import pytest
from scripts import backfill_2025_season
from scripts.generate_daily_picks_with_grok import GrokEnhancedPicksGenerator
from scripts.pregame_prediction_engine import OddsAPIClient, PreGameEngine
from scripts.start_autonomous_system import (
    AutonomousExecutionBlockedError,
    AutonomousSystem,
)
from src.agents.risk_management_agent import RiskManagementAgent
from src.agents.strategy_analyst_agent import StrategyAnalystAgent


def test_pregame_engine_never_manufactures_recommendations() -> None:
    result = PreGameEngine().analyze_game(
        {"game_id": "fixture", "home_team": "Home", "away_team": "Away"}
    )

    assert result["status"] == "NO_BET"
    assert result["prediction"]["home_win_prob"] is None
    assert result["recommendations"] == []
    assert result["live_wagers_authorized"] is False


def test_pregame_odds_client_performs_no_network_work() -> None:
    assert OddsAPIClient("secret-not-used").get_nfl_odds() == []


def test_grok_cannot_upgrade_or_generate_a_pick() -> None:
    generator = GrokEnhancedPicksGenerator(bankroll=10_000, use_grok=True)

    assert generator.use_grok is False
    assert generator.generate_daily_picks_with_grok() == []
    enhanced = generator.enhance_pick_with_grok(
        {"recommendation": "NO BET"}, {"grok_available": True}
    )
    assert enhanced["grok_enhanced"] is False
    assert enhanced["live_wagers_authorized"] is False


def test_autonomous_runtime_is_blocked() -> None:
    system = AutonomousSystem()

    with pytest.raises(AutonomousExecutionBlockedError):
        asyncio.run(system.start())
    assert system.receipt()["agents_started"] == 0


def test_risk_agent_never_returns_dollar_sizing() -> None:
    agent = RiskManagementAgent()
    result = asyncio.run(
        agent._calculate_bet_size(
            bankroll=10_000,
            edge=0.25,
            prob=0.90,
            odds=2.0,
            probability_lower_bound=0.80,
            evidence_status="live_validated",
        )
    )

    assert result["bet_size"] == 0.0
    assert result["blocked"] is True
    assert result["live_wagers_authorized"] is False


def test_strategy_agent_does_not_self_validate_mock_metrics() -> None:
    agent = StrategyAnalystAgent()
    result = asyncio.run(agent._backtest_strategy({"id": "hypothesis-1"}))

    assert result["status"] == "UNVERIFIED"
    assert result["roi"] is None
    assert result["win_rate"] is None
    assert result["blockers"]


def test_sample_backfill_is_non_mutating(tmp_path) -> None:
    output = tmp_path / "blocked.json"

    assert backfill_2025_season.main(str(output)) == 2
    assert output.exists()
    assert not (tmp_path / "bet_history.csv").exists()
