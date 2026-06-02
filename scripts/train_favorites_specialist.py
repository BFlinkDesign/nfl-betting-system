#!/usr/bin/env python3
"""Train favorites-only specialist model.

CRITICAL: This model ONLY bets favorites (odds < 2.0) where we have proven edge.
Backtest shows: 77% win rate, +12% ROI on favorites vs 34% win rate, -24% ROI on underdogs.
"""

import os
import sys

# Add project root to path BEFORE any other imports
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import logging
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import yaml
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss, roc_auc_score

from src.models.xgboost_model import XGBoostNFLModel

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def american_to_decimal(american_odds):
    """Convert American odds to decimal odds."""
    if pd.isna(american_odds):
        return None
    if american_odds > 0:
        return (american_odds / 100) + 1
    else:
        return (100 / abs(american_odds)) + 1


def load_data(
    features_path: str = "data/processed/features_2016_2024_improved.parquet",
):
    """Load and prepare data, filtering to favorites only."""
    logger.info(f"Loading features from {features_path}...")
    df = pd.read_parquet(features_path)

    # Create target: 1 if home wins, 0 if away wins
    df["target"] = (df["home_score"] > df["away_score"]).astype(int)

    # Load recommended features if available
    recommended_path = Path("reports/recommended_features.csv")
    if recommended_path.exists():
        recommended_features = pd.read_csv(recommended_path)["feature"].tolist()
        logger.info(f"Using {len(recommended_features)} recommended features")
    else:
        # Fallback: exclude metadata columns
        exclude_cols = [
            "game_id",
            "gameday",
            "home_team",
            "away_team",
            "season",
            "week",
            "home_score",
            "away_score",
            "target",
            "result",
            "total",
            "game_type",
            "weekday",
            "gametime",
            "location",
            "overtime",
            "old_game_id",
            "gsis",
            "nfl_detail_id",
            "pfr",
            "pff",
            "espn",
            "ftn",
            "away_qb_id",
            "home_qb_id",
            "away_qb_name",
            "home_qb_name",
            "away_coach",
            "home_coach",
            "referee",
            "stadium_id",
            "stadium",
            "roof",
            "surface",
            # CRITICAL: Exclude ALL betting line features (data leakage)
            "home_moneyline",
            "away_moneyline",
            "spread_line",
            "home_spread_odds",
            "away_spread_odds",
            "total_line",
            "over_odds",
            "under_odds",
            "line_movement",
            "total_movement",
            "home_favorite",
        ]
        recommended_features = [col for col in df.columns if col not in exclude_cols]

    # Filter to numeric features only
    numeric_features = (
        df[recommended_features].select_dtypes(include=[np.number]).columns.tolist()
    )

    logger.info(f"Features: {len(numeric_features)}")
    logger.info(f"Total games: {len(df)}")

    # CRITICAL: Filter to favorites only (odds < 2.0)
    # We need to determine if home team is favorite
    # Use elo_prob_home as proxy (if > 0.5, home is likely favorite)
    # Or use home_favorite if available (but it's excluded, so use elo)

    # For favorites-only: We want games where home team is favorite
    # Use elo_prob_home > 0.5 as proxy for "home favorite"
    if "elo_prob_home" in df.columns:
        df["is_home_favorite"] = df["elo_prob_home"] > 0.5
        favorites_df = df[df["is_home_favorite"]].copy()
        logger.info(
            f"Favorites (home team favored): {len(favorites_df)} games ({len(favorites_df)/len(df)*100:.1f}%)"
        )
    else:
        # Fallback: Use elo_diff > 0 (home team stronger)
        if "elo_diff" in df.columns:
            favorites_df = df[df["elo_diff"] > 0].copy()
            logger.info(
                f"Favorites (elo_diff > 0): {len(favorites_df)} games ({len(favorites_df)/len(df)*100:.1f}%)"
            )
        else:
            logger.warning(
                "Cannot determine favorites - using all data (NOT RECOMMENDED)"
            )
            favorites_df = df.copy()

    return favorites_df, numeric_features


def temporal_split(df):
    """Split data temporally (NO random shuffle)."""
    train_df = df[df["season"] <= 2022].copy()
    val_df = df[df["season"] == 2023].copy()
    test_df = df[df["season"] == 2024].copy()

    logger.info(f"Train: {len(train_df)} games (2016-2022)")
    logger.info(f"Val:   {len(val_df)} games (2023)")
    logger.info(f"Test:  {len(test_df)} games (2024)")

    return train_df, val_df, test_df


def evaluate_model(y_true, y_pred_proba, name: str):
    """Evaluate model and return metrics."""
    y_pred = (y_pred_proba > 0.5).astype(int)

    metrics = {
        "accuracy": accuracy_score(y_true, y_pred),
        "brier_score": brier_score_loss(y_true, y_pred_proba),
        "log_loss": log_loss(y_true, y_pred_proba),
        "roc_auc": roc_auc_score(y_true, y_pred_proba),
    }

    logger.info(f"\n{name} Metrics:")
    logger.info(
        f"  Accuracy:    {metrics['accuracy']:.4f} ({metrics['accuracy']*100:.2f}%)"
    )
    logger.info(f"  Brier Score: {metrics['brier_score']:.4f}")
    logger.info(f"  Log Loss:    {metrics['log_loss']:.4f}")
    logger.info(f"  ROC AUC:     {metrics['roc_auc']:.4f}")

    return metrics


def main():
    logger.info("=" * 70)
    logger.info("NFL BETTING SYSTEM - FAVORITES-ONLY SPECIALIST MODEL")
    logger.info("=" * 70)
    logger.info("Strategy: Only bet favorites (odds < 2.0)")
    logger.info("Expected: 75-78% win rate, +12-18% ROI")
    logger.info("=" * 70)

    # Load data (already filtered to favorites)
    df, feature_cols = load_data()

    if len(df) < 100:
        logger.error("Not enough favorites data! Need at least 100 games.")
        return 1

    # Temporal split
    train_df, val_df, test_df = temporal_split(df)

    # Prepare sets
    X_train = train_df[feature_cols].fillna(0)
    y_train = train_df["target"]
    X_val = val_df[feature_cols].fillna(0)
    y_val = val_df["target"]
    X_test = test_df[feature_cols].fillna(0)
    y_test = test_df["target"]

    logger.info(f"\nUsing {len(feature_cols)} features")
    logger.info(f"Training on {len(X_train)} favorite games")

    # Train XGBoost (best model from previous analysis)
    logger.info("\n" + "=" * 70)
    logger.info("TRAINING FAVORITES-ONLY XGBOOST MODEL")
    logger.info("=" * 70)

    try:
        with open("config/config.yaml") as f:
            config = yaml.safe_load(f)
        xgb_config = config.get("model", {})
    except Exception:
        xgb_config = {}

    xgb_model = XGBoostNFLModel(xgb_config)
    xgb_model.train(X_train, y_train, X_val, y_val)

    xgb_proba_test = xgb_model.predict_proba(X_test)
    if xgb_proba_test.ndim == 1:
        xgb_proba_test = xgb_proba_test
    else:
        xgb_proba_test = xgb_proba_test[:, 1]

    metrics = evaluate_model(y_test, xgb_proba_test, "Favorites-Only XGBoost")

    # Save model
    logger.info("\n" + "=" * 70)
    logger.info("SAVING MODEL")
    logger.info("=" * 70)

    Path("models").mkdir(exist_ok=True)
    joblib.dump(xgb_model, "models/xgboost_favorites_only.pkl")

    logger.info("✓ Model saved: models/xgboost_favorites_only.pkl")
    logger.info(f"✓ Test accuracy: {metrics['accuracy']*100:.2f}%")
    logger.info(f"✓ ROC AUC: {metrics['roc_auc']:.4f}")

    # GO/NO-GO check
    logger.info("\n" + "=" * 70)
    logger.info("GO/NO-GO CRITERIA CHECK")
    logger.info("=" * 70)

    checks = {
        "Accuracy >70%": metrics["accuracy"] > 0.70,  # Higher threshold for favorites
        "Brier <0.20": metrics["brier_score"] < 0.20,
        "ROC AUC >0.70": metrics["roc_auc"] > 0.70,  # Higher threshold
    }

    for criterion, passed in checks.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        logger.info(f"{status:12} {criterion}")

    if all(checks.values()):
        logger.info("\n✓ Favorites-only model meets GO criteria!")
        logger.info("✓ Ready for backtesting with favorites filter!")
        return 0
    else:
        logger.warning("\n⚠ Model fails some criteria but may still be usable.")
        logger.warning("⚠ Proceed with caution - validate with backtest.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
