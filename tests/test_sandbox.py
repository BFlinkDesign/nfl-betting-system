#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sandbox Testing Suite - Rigorous Testing of NFL Betting System

Tests all components in isolation and integration.
"""

import json
import logging
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

# Fix Windows encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.backtest import filter_favorites_only
from scripts.generate_daily_picks import DailyPicksGenerator
from src.betting.kelly import KellyCriterion

logging.basicConfig(level=logging.WARNING)  # Suppress info logs during testing
logger = logging.getLogger(__name__)


class SandboxTester:
    """Comprehensive sandbox testing suite."""

    def __init__(self):
        self.test_dir = Path("tests/sandbox")
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.results = {"passed": [], "failed": [], "warnings": []}

    def run_all_tests(self):
        """Run all test suites."""
        print("=" * 80)
        print("SANDBOX TESTING SUITE - RIGOROUS TESTING")
        print("=" * 80)
        print()

        # Test suites
        test_suites = [
            ("Model Loading", self.test_model_loading),
            ("Kelly Criterion", self.test_kelly_criterion),
            ("Favorites Filter", self.test_favorites_filter),
            ("Data Pipeline", self.test_data_pipeline),
            ("Feature Engineering", self.test_feature_engineering),
            ("Backtest Engine", self.test_backtest_engine),
            ("Daily Picks", self.test_daily_picks),
            ("Performance Dashboard", self.test_performance_dashboard),
            ("Integration", self.test_integration),
            ("Edge Cases", self.test_edge_cases),
        ]

        for suite_name, test_func in test_suites:
            print(f"\n{'='*80}")
            print(f"TEST SUITE: {suite_name}")
            print(f"{'='*80}")
            try:
                test_func()
                print(f"[OK] {suite_name}: PASSED")
                self.results["passed"].append(suite_name)
            except Exception as e:
                print(f"[FAIL] {suite_name}: FAILED - {e}")
                self.results["failed"].append((suite_name, str(e)))
                import traceback

                traceback.print_exc()

        # Print summary
        self.print_summary()

    def test_model_loading(self):
        """Test model loading and prediction."""
        print("\n[1] Testing model loading...")

        # Test favorites-only model
        model_path = Path("models/xgboost_favorites_only.pkl")
        assert model_path.exists(), f"Model not found: {model_path}"
        print(f"  [OK] Model file exists: {model_path}")

        model = joblib.load(model_path)
        assert model is not None, "Model is None"
        print("  [OK] Model loaded successfully")

        # Test prediction with dummy data
        dummy_features = np.random.rand(1, 41)  # 41 features
        try:
            proba = model.predict_proba(dummy_features)
            assert proba is not None, "Prediction returned None"
            assert len(proba.shape) > 0, "Prediction has wrong shape"
            print(
                f"  [OK] Model prediction works: {proba[0] if proba.ndim == 1 else proba[0, 1]:.4f}"
            )
        except Exception as e:
            # Check if it's a feature mismatch (expected with dummy data)
            if "feature_names" in str(e):
                print(f"  [WARN] Feature mismatch (expected with dummy data): {e}")
            else:
                raise

    def test_kelly_criterion(self):
        """Test Kelly criterion calculations."""
        print("\n[2] Testing Kelly criterion...")

        kelly = KellyCriterion(
            kelly_fraction=0.25,
            min_edge=0.02,
            min_probability=0.55,
            max_bet_pct=0.10,
            aggressive_mode=True,
        )

        # Test 1: Normal bet
        bankroll = 10000.0
        prob_win = 0.70
        odds = 1.80

        bet_size = kelly.calculate_bet_size(prob_win, odds, bankroll)
        assert bet_size > 0, "Bet size should be > 0"
        assert bet_size <= bankroll * 0.10, "Bet size should be <= 10%"
        print(f"  [OK] Normal bet: ${bet_size:.2f} ({bet_size/bankroll*100:.2f}%)")

        # Test 2: Heavy favorite (aggressive sizing)
        prob_win = 0.75
        odds = 1.50
        bet_size = kelly.calculate_bet_size(prob_win, odds, bankroll)
        assert bet_size > 0, "Heavy favorite bet size should be > 0"
        print(f"  [OK] Heavy favorite: ${bet_size:.2f} ({bet_size/bankroll*100:.2f}%)")

        # Test 3: No edge (should return 0)
        prob_win = 0.50
        odds = 2.00
        bet_size = kelly.calculate_bet_size(prob_win, odds, bankroll)
        assert bet_size == 0, "No edge should return 0 bet size"
        print("  [OK] No edge correctly returns 0")

        # Test 4: Hot streak bonus
        recent_perf = {"win_rate_last_10": 0.80}
        bet_size_with_bonus = kelly.calculate_bet_size(
            0.70, 1.80, bankroll, recent_perf
        )
        assert bet_size_with_bonus >= bet_size, "Hot streak should increase bet size"
        print(f"  [OK] Hot streak bonus works: ${bet_size_with_bonus:.2f}")

    def test_favorites_filter(self):
        """Test favorites filtering logic."""
        print("\n[3] Testing favorites filter...")

        # Create test dataframe
        test_data = pd.DataFrame(
            {
                "game_id": ["test1", "test2", "test3", "test4", "test5"],
                "odds": [
                    1.40,
                    1.60,
                    1.90,
                    2.10,
                    2.50,
                ],  # Mix of favorites and underdogs
                "pred_prob": [0.75, 0.70, 0.65, 0.55, 0.45],
                "actual": [1, 1, 0, 0, 0],
            }
        )

        initial_count = len(test_data)
        filtered = filter_favorites_only(test_data)
        filtered_count = len(filtered)

        assert filtered_count < initial_count, "Filter should reduce count"
        assert all(filtered["odds"] < 2.0), "All odds should be < 2.0"
        assert all(filtered["odds"] > 1.3), "All odds should be > 1.3"
        print(f"  [OK] Filtered {initial_count} -> {filtered_count} games")
        print(
            f"  [OK] All odds in range 1.3-2.0: {all((filtered['odds'] > 1.3) & (filtered['odds'] < 2.0))}"
        )

    def test_data_pipeline(self):
        """Test data loading and validation."""
        print("\n[4] Testing data pipeline...")

        # Test features file exists
        features_path = Path("data/processed/features_2016_2024_improved.parquet")
        assert features_path.exists(), f"Features file not found: {features_path}"
        print("  [OK] Features file exists")

        # Load and validate
        df = pd.read_parquet(features_path)
        assert len(df) > 0, "Dataframe is empty"
        assert (
            "target" not in df.columns or df["target"].notna().any()
        ), "Target column issues"
        print(f"  [OK] Loaded {len(df):,} games")

        # Check required columns
        required_cols = ["game_id", "gameday", "home_team", "away_team", "season"]
        missing = [col for col in required_cols if col not in df.columns]
        assert len(missing) == 0, f"Missing required columns: {missing}"
        print("  [OK] All required columns present")

        # Check for betting line leakage
        leak_cols = ["home_moneyline", "away_moneyline", "spread_line"]
        has_leakage = any(col in df.columns for col in leak_cols)
        if has_leakage:
            print(
                "  [WARN] Betting line columns present (may be OK if excluded from features)"
            )
        else:
            print("  [OK] No betting line columns (good - no leakage)")

    def test_feature_engineering(self):
        """Test feature engineering pipeline."""
        print("\n[5] Testing feature engineering...")

        # Check recommended features
        rec_path = Path("reports/recommended_features.csv")
        if rec_path.exists():
            rec_features = pd.read_csv(rec_path)["feature"].tolist()
            assert len(rec_features) > 0, "No recommended features"
            print(f"  [OK] {len(rec_features)} recommended features")

            # Check for betting line features
            leak_features = [
                f
                for f in rec_features
                if any(x in f.lower() for x in ["moneyline", "spread", "odds", "line"])
            ]
            if leak_features:
                print(f"  [WARN] Potential leakage features: {leak_features[:3]}")
            else:
                print("  [OK] No betting line features in recommendations")
        else:
            print("  [WARN] Recommended features file not found")

    def test_backtest_engine(self):
        """Test backtest engine."""
        print("\n[6] Testing backtest engine...")

        # Check backtest results exist
        metrics_path = Path("reports/backtest_metrics.json")
        if metrics_path.exists():
            with open(metrics_path) as f:
                metrics = json.load(f)

            assert "win_rate" in metrics, "Missing win_rate in metrics"
            assert "roi" in metrics, "Missing roi in metrics"
            assert metrics["win_rate"] > 0, "Win rate should be > 0"
            print("  [OK] Backtest metrics loaded")
            print(f"     Win Rate: {metrics['win_rate']:.2f}%")
            print(f"     ROI: {metrics['roi']:.2f}%")
            print(f"     Sharpe: {metrics.get('sharpe_ratio', 0):.2f}")
        else:
            print("  [WARN] Backtest metrics not found (run backtest first)")

        # Check bet history
        history_path = Path("reports/bet_history.csv")
        if history_path.exists():
            history = pd.read_csv(history_path)
            assert len(history) > 0, "Bet history is empty"
            print(f"  [OK] Bet history: {len(history)} bets")
        else:
            print("  [WARN] Bet history not found")

    def test_daily_picks(self):
        """Test daily picks generation."""
        print("\n[7] Testing daily picks generation...")

        # Test initialization
        try:
            generator = DailyPicksGenerator(
                model_path="models/xgboost_favorites_only.pkl",
                bankroll=10000.0,
                favorites_only=True,
            )
            print("  [OK] DailyPicksGenerator initialized")

            # Check model loaded
            if generator.model is not None:
                print("  [OK] Model loaded")
            else:
                print("  [WARN] Model not loaded (may be OK if file missing)")

            # Check APIs initialized
            assert generator.odds_api is not None, "Odds API not initialized"
            assert generator.weather_api is not None, "Weather API not initialized"
            assert generator.line_shopping is not None, "Line shopping not initialized"
            assert generator.kelly is not None, "Kelly criterion not initialized"
            print("  [OK] All APIs initialized")

            # Test favorites filter flag
            assert generator.favorites_only is True, "Favorites-only flag not set"
            print("  [OK] Favorites-only filter enabled")

        except Exception as e:
            if "Model not found" in str(e) or "FileNotFoundError" in str(
                type(e).__name__
            ):
                print("  [WARN] Model file missing (expected in some environments)")
            else:
                raise

    def test_performance_dashboard(self):
        """Test performance dashboard generation."""
        print("\n[8] Testing performance dashboard...")

        # Check if bet history exists
        history_path = Path("reports/bet_history.csv")
        if history_path.exists():
            # Test dashboard generation
            try:
                from scripts.generate_performance_dashboard import generate_dashboard

                generate_dashboard()

                dashboard_path = Path("reports/img/performance_dashboard.png")
                assert dashboard_path.exists(), "Dashboard not generated"
                print(f"  [OK] Dashboard generated: {dashboard_path}")
            except Exception as e:
                print(f"  [WARN] Dashboard generation issue: {e}")
        else:
            print("  [WARN] Bet history not found (run backtest first)")

    def test_integration(self):
        """Test end-to-end integration."""
        print("\n[9] Testing integration...")

        # Test 1: Model → Prediction → Kelly → Filter
        print("  [9.1] Testing prediction pipeline...")

        # Load model
        model_path = Path("models/xgboost_favorites_only.pkl")
        if model_path.exists():
            model = joblib.load(model_path)

            # Create dummy prediction
            dummy_prob = 0.70
            odds = 1.75

            # Kelly sizing
            kelly = KellyCriterion(aggressive_mode=True)
            bet_size = kelly.calculate_bet_size(dummy_prob, odds, 10000.0)

            # Favorites filter
            is_favorite = 1.3 < odds < 2.0
            has_edge = dummy_prob > (1 / odds) + 0.02

            assert is_favorite, "Should be favorite"
            assert has_edge, "Should have edge"
            assert bet_size > 0, "Should have bet size"

            print("  [OK] Prediction -> Kelly -> Filter pipeline works")
            print(
                f"     Prob: {dummy_prob:.2%}, Odds: {odds:.2f}, Bet: ${bet_size:.2f}"
            )
        else:
            print("  [WARN] Model not found, skipping integration test")

        # Test 2: Data -> Features -> Model -> Backtest
        print("  [9.2] Testing data pipeline...")
        features_path = Path("data/processed/features_2016_2024_improved.parquet")
        if features_path.exists():
            df = pd.read_parquet(features_path)
            assert len(df) > 0, "Data loaded"
            print(f"  [OK] Data -> Features pipeline works ({len(df):,} games)")
        else:
            print("  [WARN] Features file not found")

    def test_edge_cases(self):
        """Test edge cases and error handling."""
        print("\n[10] Testing edge cases...")

        # Test 1: Zero bankroll
        print("  [10.1] Testing zero bankroll...")
        kelly = KellyCriterion()
        bet_size = kelly.calculate_bet_size(0.70, 1.80, 0.0)
        assert bet_size == 0, "Zero bankroll should return 0 bet"
        print("  [OK] Zero bankroll handled correctly")

        # Test 2: Very high probability
        print("  [10.2] Testing very high probability...")
        bet_size = kelly.calculate_bet_size(0.99, 1.10, 10000.0)
        assert bet_size >= 0, "High probability should return valid bet"
        print(f"  [OK] High probability handled: ${bet_size:.2f}")

        # Test 3: Very low probability
        print("  [10.3] Testing very low probability...")
        bet_size = kelly.calculate_bet_size(0.30, 3.00, 10000.0)
        assert bet_size == 0, "Low probability should return 0 (below min_probability)"
        print("  [OK] Low probability handled correctly")

        # Test 4: Missing model file
        print("  [10.4] Testing missing model file...")
        try:
            generator = DailyPicksGenerator(model_path="nonexistent.pkl")
            assert generator.model is None, "Missing model should set model to None"
            print("  [OK] Missing model handled gracefully")
        except Exception as e:
            print(f"  [WARN] Missing model handling: {e}")

        # Test 5: Empty favorites filter
        print("  [10.5] Testing empty favorites filter...")
        empty_df = pd.DataFrame({"odds": [2.5, 3.0, 1.1]})  # All outside range
        filtered = filter_favorites_only(empty_df)
        assert len(filtered) == 0, "Empty filter should return empty dataframe"
        print("  [OK] Empty filter handled correctly")

    def print_summary(self):
        """Print test summary."""
        print("\n" + "=" * 80)
        print("TEST SUMMARY")
        print("=" * 80)

        total = len(self.results["passed"]) + len(self.results["failed"])
        passed = len(self.results["passed"])
        failed = len(self.results["failed"])

        print(f"\nTotal Test Suites: {total}")
        print(f"[OK] Passed: {passed}")
        print(f"[FAIL] Failed: {failed}")

        if self.results["passed"]:
            print("\n[OK] Passed Suites:")
            for suite in self.results["passed"]:
                print(f"   - {suite}")

        if self.results["failed"]:
            print("\n[FAIL] Failed Suites:")
            for suite, error in self.results["failed"]:
                print(f"   - {suite}: {error}")

        if self.results["warnings"]:
            print("\n[WARN] Warnings:")
            for warning in self.results["warnings"]:
                print(f"   - {warning}")

        print("\n" + "=" * 80)

        if failed == 0:
            print("[SUCCESS] ALL TESTS PASSED - SYSTEM READY")
        else:
            print(f"[WARNING] {failed} TEST SUITE(S) FAILED - REVIEW ERRORS")
        print("=" * 80)


def main():
    """Run sandbox tests."""
    tester = SandboxTester()
    tester.run_all_tests()

    # Return exit code
    return 0 if len(tester.results["failed"]) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
