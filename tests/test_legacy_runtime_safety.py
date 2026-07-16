"""Regression tests for retired operational paths."""

from __future__ import annotations

import asyncio
import json

import pytest

from agents.aggressive_kelly import AggressiveKellyCalculator
from scripts.generate_daily_picks import DailyPicksGenerator
from src.orchestrator.master_pipeline import MasterPipeline, PipelineConfig


def test_aggressive_kelly_is_zero_stake_and_blocked() -> None:
    result = AggressiveKellyCalculator(bankroll=10_000).calculate_bet_size(
        edge=0.25,
        confidence=0.99,
        situational_edge=0.25,
        weather_confidence="VERY HIGH",
        recent_performance={"win_rate": 1.0},
    )

    assert result["blocked"] is True
    assert result["bet_size"] == 0.0
    assert result["bet_pct"] == 0.0
    assert result["tier"] == "NO BET"


def test_daily_generator_does_not_manufacture_probability() -> None:
    generator = DailyPicksGenerator(bankroll=10_000)
    prediction = generator.predict_game("Home", "Away")

    assert prediction["model_used"] is False
    assert prediction["home_win_prob"] is None
    assert prediction["status"] == "NO_BET"


def test_daily_generator_requires_canonical_evidence() -> None:
    generator = DailyPicksGenerator(bankroll=10_000)
    result = generator.generate_pick(
        {"home_team": "Home", "away_team": "Away"},
        {"home_team": "Home", "away_team": "Away", "model_used": True},
        {},
    )

    assert result["recommendation"] == "NO BET"
    assert result["paper_stake"] == 0.0
    assert result["live_wagers_authorized"] is False


def test_daily_generator_automatic_discovery_is_disabled() -> None:
    generator = DailyPicksGenerator(bankroll=10_000)
    assert generator.generate_daily_picks() == []


def test_master_pipeline_rejects_live_authority() -> None:
    with pytest.raises(ValueError, match="live_money_authorized"):
        PipelineConfig(live_money_authorized=True)


def test_master_pipeline_has_zero_sizing_authority(tmp_path) -> None:
    pipeline = MasterPipeline(PipelineConfig(output_dir=str(tmp_path)))
    sizing = pipeline.calculate_bet_size(0.99, -110, 0.99)

    assert sizing == {
        "kelly_full": 0.0,
        "kelly_fraction": 0.0,
        "bet_pct": 0.0,
        "bet_amount": 0.0,
    }


def test_master_pipeline_without_evidence_emits_no_bet_receipt(tmp_path) -> None:
    pipeline = MasterPipeline(PipelineConfig(output_dir=str(tmp_path)))

    assert asyncio.run(pipeline.run_daily_pipeline()) == []
    assert pipeline.last_receipt_path is not None

    payload = json.loads(pipeline.last_receipt_path.read_text(encoding="utf-8"))
    assert payload["status"] == "NO_BET"
    assert payload["live_wagers_authorized"] is False
