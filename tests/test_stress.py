#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bounded stress tests for safety-critical analytical components."""

import sys
from pathlib import Path

import pandas as pd

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.backtest import filter_favorites_only  # noqa: E402
from src.betting.kelly import BetSizingBlockedError, KellyCriterion  # noqa: E402


def test_stress_kelly():
    """Kelly analysis remains non-negative, conservative, and non-actionable."""

    kelly = KellyCriterion(
        aggressive_mode=False,
        deployment_mode="paper",
        min_probability=0.10,
        max_bet_pct=0.02,
    )
    test_cases = [
        ("Extreme favorite", 0.95, 1.05, 0.90),
        ("Extreme underdog", 0.10, 5.00, 0.05),
        ("Positive edge", 0.80, 1.20, 0.75),
        ("No edge", 0.50, 2.00, 0.50),
        ("Negative edge", 0.40, 2.00, 0.35),
    ]

    for _, point_probability, odds, lower_bound in test_cases:
        fraction = kelly.calculate_fraction(
            point_probability,
            odds,
            probability_lower_bound=lower_bound,
            evidence_status="out_of_sample_validated",
        )
        assert 0.0 <= fraction <= 0.02

    try:
        kelly.calculate_bet_size(
            0.80,
            2.0,
            10000.0,
            probability_lower_bound=0.70,
            evidence_status="live_validated",
            live_wager_authorized=True,
        )
    except BetSizingBlockedError:
        pass
    else:
        raise AssertionError("paper mode must block dollar sizing")


def test_stress_filter():
    """Legacy favorites filtering remains bounded on edge cases."""

    test_cases = [
        [1.4, 1.5, 1.6, 1.7, 1.8, 1.9],
        [2.1, 2.5, 3.0, 4.0],
        [1.2, 1.5, 1.9, 2.1, 2.5],
        [1.3, 1.31, 1.99, 2.0],
        [],
        [1.75],
        [2.25],
    ]

    for odds_list in test_cases:
        frame = pd.DataFrame({"odds": odds_list})
        filtered = filter_favorites_only(frame)
        assert len(filtered) <= len(frame)
        if len(filtered) > 0:
            assert all((filtered["odds"] > 1.3) & (filtered["odds"] < 2.0))


def test_stress_data():
    """Large data loading is exercised only when the private dataset exists."""

    features_path = Path("data/processed/features_2016_2024_improved.parquet")
    if not features_path.exists():
        return
    frame = pd.read_parquet(features_path)
    assert len(frame) >= 0
    filtered = frame[frame["season"] == 2024]
    assert len(filtered) <= len(frame)
    assert frame.memory_usage(deep=True).sum() >= 0
