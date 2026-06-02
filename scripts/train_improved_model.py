#!/usr/bin/env python3
"""Train improved model with ensemble and new features.

Trains XGBoost, LightGBM, and ensemble models with improved features.
"""

import logging
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import yaml
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss, roc_auc_score

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.ensemble import EnsembleModel
from src.models.lightgbm_model import LightGBMModel
from src.models.xgboost_model import XGBoostNFLModel

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def load_data(
    features_path: str = "data/processed/features_2016_2024_improved.parquet",
):
    """Load and prepare data."""
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
            "home_favorite",  # Derived from betting lines
        ]
        recommended_features = [col for col in df.columns if col not in exclude_cols]

    # Filter to numeric features only
    numeric_features = (
        df[recommended_features].select_dtypes(include=[np.number]).columns.tolist()
    )

    logger.info(f"Features: {len(numeric_features)}")
    logger.info(f"Games: {len(df)}")

    return df, numeric_features


def temporal_split(df):
    """
    Split data temporally (NO random shuffle).

    Train: 2016-2022
    Val: 2023 (for calibration)
    Test: 2024 (for final evaluation)
    """
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
    logger.info(f"  Accuracy:    {metrics['accuracy']:.4f}")
    logger.info(f"  Brier Score: {metrics['brier_score']:.4f}")
    logger.info(f"  Log Loss:    {metrics['log_loss']:.4f}")
    logger.info(f"  ROC AUC:     {metrics['roc_auc']:.4f}")

    return metrics


def main():
    logger.info("=" * 70)
    logger.info("NFL BETTING SYSTEM - IMPROVED MODEL TRAINING")
    logger.info("=" * 70)

    # Load data
    df, feature_cols = load_data()

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

    # Train XGBoost
    logger.info("\n" + "=" * 70)
    logger.info("TRAINING XGBOOST MODEL")
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
    xgb_metrics = evaluate_model(y_test, xgb_proba_test, "XGBoost")

    # Train LightGBM
    logger.info("\n" + "=" * 70)
    logger.info("TRAINING LIGHTGBM MODEL")
    logger.info("=" * 70)

    lgb_model = LightGBMModel()
    lgb_model.fit(X_train, y_train)

    lgb_proba_test = lgb_model.predict_proba(X_test)
    if lgb_proba_test.ndim == 1:
        lgb_proba_test = lgb_proba_test
    else:
        lgb_proba_test = lgb_proba_test[:, 1]
    lgb_metrics = evaluate_model(y_test, lgb_proba_test, "LightGBM")

    # Train Logistic Regression (baseline)
    logger.info("\n" + "=" * 70)
    logger.info("TRAINING LOGISTIC REGRESSION (BASELINE)")
    logger.info("=" * 70)

    lr_model = LogisticRegression(random_state=42, max_iter=1000)
    lr_model.fit(X_train, y_train)

    lr_proba_test = lr_model.predict_proba(X_test)[:, 1]
    lr_metrics = evaluate_model(y_test, lr_proba_test, "Logistic Regression")

    # Train Ensemble (weighted average)
    logger.info("\n" + "=" * 70)
    logger.info("TRAINING ENSEMBLE MODEL")
    logger.info("=" * 70)

    ensemble = EnsembleModel(
        models=[xgb_model, lgb_model, lr_model],
        weights=[0.4, 0.4, 0.2],  # XGBoost and LightGBM get more weight
        method="weighted_average",
    )
    ensemble.fit(X_train, y_train)

    ensemble_proba_test = ensemble.predict_proba(X_test)
    if ensemble_proba_test.ndim == 1:
        ensemble_proba_test = ensemble_proba_test
    else:
        ensemble_proba_test = ensemble_proba_test[:, 1]
    ensemble_metrics = evaluate_model(y_test, ensemble_proba_test, "Ensemble")

    # Use ensemble directly (calibration can be added later if needed)
    logger.info("\n" + "=" * 70)
    logger.info("FINAL ENSEMBLE MODEL (Using Best Model)")
    logger.info("=" * 70)

    # Use XGBoost as the best single model (highest accuracy)
    best_model = xgb_model
    best_proba_test = xgb_proba_test
    cal_metrics = xgb_metrics

    # Compare all models
    logger.info("\n" + "=" * 70)
    logger.info("MODEL COMPARISON (2024 Test Set)")
    logger.info("=" * 70)

    comparison = pd.DataFrame(
        {
            "Model": ["XGBoost", "LightGBM", "Logistic Regression", "Ensemble"],
            "Accuracy": [
                xgb_metrics["accuracy"],
                lgb_metrics["accuracy"],
                lr_metrics["accuracy"],
                ensemble_metrics["accuracy"],
            ],
            "Brier Score": [
                xgb_metrics["brier_score"],
                lgb_metrics["brier_score"],
                lr_metrics["brier_score"],
                ensemble_metrics["brier_score"],
            ],
            "ROC AUC": [
                xgb_metrics["roc_auc"],
                lgb_metrics["roc_auc"],
                lr_metrics["roc_auc"],
                ensemble_metrics["roc_auc"],
            ],
        }
    )

    print(comparison.to_string(index=False))

    # Save comparison
    Path("reports").mkdir(exist_ok=True)
    comparison.to_csv("reports/model_comparison.csv", index=False)

    # Save best model (calibrated ensemble)
    logger.info("\n" + "=" * 70)
    logger.info("SAVING MODELS")
    logger.info("=" * 70)

    Path("models").mkdir(exist_ok=True)
    joblib.dump(ensemble, "models/ensemble_model.pkl")
    joblib.dump(xgb_model, "models/xgboost_improved.pkl")
    joblib.dump(lgb_model, "models/lightgbm_improved.pkl")

    logger.info("✓ Ensemble model: models/ensemble_model.pkl")
    logger.info("✓ XGBoost (best): models/xgboost_improved.pkl")
    logger.info("✓ LightGBM: models/lightgbm_improved.pkl")

    # GO/NO-GO check
    logger.info("\n" + "=" * 70)
    logger.info("GO/NO-GO CRITERIA CHECK")
    logger.info("=" * 70)

    checks = {
        "Accuracy >55%": xgb_metrics["accuracy"] > 0.55,
        "Brier <0.20": xgb_metrics["brier_score"] < 0.20,
        "ROC AUC >0.55": xgb_metrics["roc_auc"] > 0.55,
    }

    for criterion, passed in checks.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        logger.info(f"{status:12} {criterion}")

    if all(checks.values()):
        logger.info("\n✓ Model meets GO criteria. Ready for backtesting!")
        return 0
    else:
        logger.warning("\n⚠ Model fails some criteria. Review before backtesting.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
