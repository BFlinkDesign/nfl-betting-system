"""
Self-Improving NFL Betting System
Automates data collection, model retraining, and performance optimization
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict

import joblib
import pandas as pd

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.performance_tracker import PerformanceTracker
from src.data_pipeline import NFLDataPipeline
from src.features.pipeline import create_features

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SelfImprovingSystem:
    """
    Self-improving betting system that automatically:
    1. Collects new data weekly
    2. Retrains model monthly
    3. Backtests new models
    4. Updates if performance improves
    5. Tracks feature importance
    6. Discovers new edges
    """

    def __init__(
        self,
        data_dir: str = "data",
        models_dir: str = "models",
        reports_dir: str = "reports",
    ):
        """Initialize self-improving system."""
        self.data_dir = Path(data_dir)
        self.models_dir = Path(models_dir)
        self.reports_dir = Path(reports_dir)

        # Create directories
        for directory in [self.data_dir, self.models_dir, self.reports_dir]:
            directory.mkdir(parents=True, exist_ok=True)

        self.tracker = PerformanceTracker()

    def should_update_data(self) -> bool:
        """Check if data needs updating."""
        # Check last modification time of schedules file
        schedules_file = self.data_dir / "raw" / "schedules_2016_2024.parquet"

        if not schedules_file.exists():
            logger.info("Data files missing - need to download")
            return True

        # Update if older than 7 days
        mtime = datetime.fromtimestamp(schedules_file.stat().st_mtime)
        age_days = (datetime.now() - mtime).days

        if age_days > 7:
            logger.info(f"Data is {age_days} days old - need to update")
            return True

        logger.info(f"Data is {age_days} days old - still fresh")
        return False

    def update_data(self):
        """Download latest NFL data."""
        logger.info("=" * 80)
        logger.info("UPDATING DATA")
        logger.info("=" * 80)

        try:
            # Download new data
            pipeline = NFLDataPipeline()
            pipeline.download_all(seasons=list(range(2016, 2025)))
            logger.info("[OK] Data updated successfully")

            # Regenerate features
            logger.info("\nRegenerating features...")
            create_features(
                seasons=list(range(2016, 2025)),
                output_path="data/processed/features_2016_2024_improved.parquet",
            )
            logger.info("[OK] Features regenerated")

            return True

        except Exception as e:
            logger.error(f"Data update failed: {e}")
            return False

    def should_retrain_model(self) -> bool:
        """Check if model needs retraining."""
        model_file = self.models_dir / "xgboost_improved.pkl"

        if not model_file.exists():
            logger.info("Model doesn't exist - need to train")
            return True

        # Retrain monthly
        mtime = datetime.fromtimestamp(model_file.stat().st_mtime)
        age_days = (datetime.now() - mtime).days

        if age_days > 30:
            logger.info(f"Model is {age_days} days old - need to retrain")
            return True

        # Check if we have enough new data
        tracker_df = self.tracker.df
        completed = tracker_df[tracker_df["result"] != "PENDING"]

        if len(completed) >= 50:  # 50 new bets since last training
            logger.info(f"Have {len(completed)} new results - should retrain")
            return True

        logger.info(
            f"Model is {age_days} days old with {len(completed)} new results - no retrain needed"
        )
        return False

    def train_new_model(self, model_suffix: str = None):
        """
        Train a new model with latest data.

        Args:
            model_suffix: Optional suffix for model name (e.g., 'v2')

        Returns:
            Path to trained model
        """
        logger.info("=" * 80)
        logger.info("TRAINING NEW MODEL")
        logger.info("=" * 80)

        timestamp = datetime.now().strftime("%Y%m%d")
        model_name = f"xgboost_improved_{timestamp}"
        if model_suffix:
            model_name += f"_{model_suffix}"

        try:
            # Train model
            from scripts.train_improved_model import main as train_improved

            model_path = train_improved(output_name=model_name)

            logger.info(f"[OK] Model trained: {model_path}")
            return model_path

        except Exception as e:
            logger.error(f"Model training failed: {e}")
            return None

    def evaluate_model(self, model_path: str) -> Dict:
        """
        Evaluate model performance via backtest.

        Args:
            model_path: Path to model file

        Returns:
            Dict with performance metrics
        """
        logger.info("=" * 80)
        logger.info("EVALUATING MODEL")
        logger.info("=" * 80)

        try:
            # Load model
            model = joblib.load(model_path)

            # Run backtest
            from scripts.backtest import calculate_metrics, prepare_predictions

            # Load features
            df = pd.read_parquet("data/processed/features_2016_2024_improved.parquet")

            # Get feature columns
            feature_cols = [
                col
                for col in df.columns
                if col
                not in [
                    "gameday",
                    "game_id",
                    "season",
                    "week",
                    "home_team",
                    "away_team",
                    "result",
                    "home_score",
                    "away_score",
                ]
            ]

            # Prepare predictions
            df = prepare_predictions(df, model, feature_cols)

            # Calculate metrics
            metrics = calculate_metrics(df)

            logger.info("[RESULTS]")
            logger.info(f"  Win Rate: {metrics['win_rate']:.2f}%")
            logger.info(f"  ROI: {metrics['roi']:.2f}%")
            logger.info(f"  Profit: ${metrics['total_profit']:.0f}")

            return metrics

        except Exception as e:
            logger.error(f"Model evaluation failed: {e}")
            return {}

    def compare_models(self, new_model_path: str, old_model_path: str) -> bool:
        """
        Compare new model vs old model.

        Args:
            new_model_path: Path to new model
            old_model_path: Path to current production model

        Returns:
            True if new model is better
        """
        logger.info("=" * 80)
        logger.info("COMPARING MODELS")
        logger.info("=" * 80)

        # Evaluate both models
        logger.info("\n[1] Evaluating NEW model...")
        new_metrics = self.evaluate_model(new_model_path)

        logger.info("\n[2] Evaluating OLD model...")
        old_metrics = self.evaluate_model(old_model_path)

        if not new_metrics or not old_metrics:
            logger.error("Could not compare models")
            return False

        # Compare metrics
        logger.info("\n[3] COMPARISON:")
        logger.info(
            f"  Win Rate:  {old_metrics['win_rate']:.2f}% → {new_metrics['win_rate']:.2f}% "
            f"({new_metrics['win_rate']-old_metrics['win_rate']:+.2f}%)"
        )
        logger.info(
            f"  ROI:       {old_metrics['roi']:.2f}% → {new_metrics['roi']:.2f}% "
            f"({new_metrics['roi']-old_metrics['roi']:+.2f}%)"
        )
        logger.info(
            f"  Profit:    ${old_metrics['total_profit']:.0f} → ${new_metrics['total_profit']:.0f} "
            f"({new_metrics['total_profit']-old_metrics['total_profit']:+.0f})"
        )

        # Decision: new model must have better ROI or (win rate + profit)
        better_roi = new_metrics["roi"] > old_metrics["roi"]
        better_overall = (
            new_metrics["win_rate"] > old_metrics["win_rate"]
            and new_metrics["total_profit"] > old_metrics["total_profit"]
        )

        is_better = better_roi or better_overall

        logger.info(
            f"\n[DECISION] New model is {'BETTER' if is_better else 'NOT BETTER'}"
        )

        return is_better

    def deploy_model(self, model_path: str):
        """
        Deploy new model to production.

        Args:
            model_path: Path to model to deploy
        """
        logger.info("=" * 80)
        logger.info("DEPLOYING MODEL")
        logger.info("=" * 80)

        production_path = self.models_dir / "xgboost_improved.pkl"

        # Backup old model
        if production_path.exists():
            backup_path = (
                self.models_dir
                / f'xgboost_improved_backup_{datetime.now().strftime("%Y%m%d")}.pkl'
            )
            production_path.rename(backup_path)
            logger.info(f"[BACKUP] Old model saved to: {backup_path}")

        # Copy new model to production
        import shutil

        shutil.copy(model_path, production_path)

        logger.info(f"[OK] Deployed: {model_path} → {production_path}")

    def analyze_feature_importance(self):
        """Analyze which features are most important."""
        logger.info("=" * 80)
        logger.info("ANALYZING FEATURE IMPORTANCE")
        logger.info("=" * 80)

        try:
            # Load model
            model = joblib.load(self.models_dir / "xgboost_improved.pkl")

            # Get feature importance
            importance = model.feature_importances_
            feature_names = model.get_booster().feature_names

            # Create DataFrame
            importance_df = pd.DataFrame(
                {"feature": feature_names, "importance": importance}
            ).sort_values("importance", ascending=False)

            # Save
            importance_file = self.reports_dir / "feature_importance.csv"
            importance_df.to_csv(importance_file, index=False)

            # Print top 10
            logger.info("\nTOP 10 FEATURES:")
            for idx, row in importance_df.head(10).iterrows():
                logger.info(f"  {row['feature']:<30} {row['importance']:.4f}")

            logger.info(f"\n[OK] Saved to: {importance_file}")

            return importance_df

        except Exception as e:
            logger.error(f"Feature importance analysis failed: {e}")
            return pd.DataFrame()

    def run_maintenance(self):
        """Run full system maintenance cycle."""
        logger.info("\n" + "=" * 80)
        logger.info("SELF-IMPROVING SYSTEM - MAINTENANCE CYCLE")
        logger.info("=" * 80 + "\n")

        # Step 1: Check and update data
        if self.should_update_data():
            logger.info("\n[STEP 1] Updating data...")
            self.update_data()
        else:
            logger.info("\n[STEP 1] Data is up-to-date, skipping")

        # Step 2: Check if retraining needed
        if self.should_retrain_model():
            logger.info("\n[STEP 2] Retraining model...")

            # Train new model
            new_model_path = self.train_new_model()

            if new_model_path:
                # Compare with current production model
                old_model_path = str(self.models_dir / "xgboost_improved.pkl")

                if os.path.exists(old_model_path):
                    is_better = self.compare_models(new_model_path, old_model_path)

                    if is_better:
                        logger.info("\n[STEP 3] Deploying new model...")
                        self.deploy_model(new_model_path)
                    else:
                        logger.info("\n[STEP 3] Keeping old model (better performance)")
                else:
                    # No existing model, deploy new one
                    logger.info("\n[STEP 3] Deploying first model...")
                    self.deploy_model(new_model_path)
        else:
            logger.info("\n[STEP 2] Model retraining not needed, skipping")

        # Step 3: Analyze feature importance
        logger.info("\n[STEP 4] Analyzing feature importance...")
        self.analyze_feature_importance()

        # Step 4: Generate performance report
        logger.info("\n[STEP 5] Generating performance report...")
        print(self.tracker.generate_report())

        logger.info("\n" + "=" * 80)
        logger.info("MAINTENANCE CYCLE COMPLETE")
        logger.info("=" * 80 + "\n")


def main():
    """Run self-improving system maintenance."""
    system = SelfImprovingSystem()
    system.run_maintenance()


if __name__ == "__main__":
    main()
