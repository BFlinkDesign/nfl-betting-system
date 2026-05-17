#!/usr/bin/env python3
"""
Autonomous NFL Picks Generator

Downloads fresh data, runs predictions, detects market edges, outputs picks.
Designed to run daily with zero manual intervention.

Usage:
    python scripts/autonomous_picks.py          # Get this week's picks
    python scripts/autonomous_picks.py --train  # Train model first
    python scripts/autonomous_picks.py --week 5 # Specific week

This is for FUN beer money bets. Gamble responsibly.
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Setup path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import numpy as np
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def install_dependencies():
    """Install required packages if missing."""
    required = ['nfl_data_py', 'xgboost', 'scikit-learn']

    for pkg in required:
        try:
            __import__(pkg.replace('-', '_'))
        except ImportError:
            logger.info(f"Installing {pkg}...")
            os.system(f"pip install {pkg} -q")


def download_data(seasons=None):
    """Download NFL data."""
    from src.data.nfl_data import download_schedules, download_pbp, setup_data_directory

    setup_data_directory()

    if seasons is None:
        current_year = datetime.now().year
        current_month = datetime.now().month
        if current_month >= 9:
            seasons = list(range(2020, current_year + 1))
        else:
            seasons = list(range(2020, current_year))

    logger.info(f"Downloading data for {seasons}")

    # Schedules (includes betting lines)
    schedules = download_schedules(
        seasons,
        save_path=f"data/raw/schedules_{min(seasons)}_{max(seasons)}.parquet"
    )

    # Play-by-play (for EPA stats) - just last 3 years to save time
    recent_seasons = [s for s in seasons if s >= max(seasons) - 2]
    pbp = download_pbp(
        recent_seasons,
        save_path=f"data/raw/pbp_{min(recent_seasons)}_{max(recent_seasons)}.parquet"
    )

    return schedules, pbp


def build_features(schedules, pbp):
    """Build features from raw data."""
    from src.data.nfl_data import calculate_team_stats, prepare_features

    # Calculate team stats from PBP
    team_stats = calculate_team_stats(pbp)

    # Prepare features
    features_df = prepare_features(schedules, team_stats)

    # Save
    features_df.to_parquet("data/processed/features.parquet", index=False)

    return features_df


def train_model(features_df):
    """Train XGBoost model."""
    from src.models.xgboost_model import XGBoostNFLModel
    from src.models.calibration import ModelCalibrator

    logger.info("Training model...")

    # Split: train on all but most recent season
    max_season = features_df['season'].max()
    train_df = features_df[features_df['season'] < max_season]
    val_df = features_df[features_df['season'] == max_season]

    logger.info(f"Train: {len(train_df)} games, Val: {len(val_df)} games")

    # Feature columns
    exclude_cols = [
        'game_id', 'gameday', 'home_team', 'away_team', 'season', 'week',
        'home_score', 'away_score', 'target', 'result', 'total', 'game_type',
        'weekday', 'gametime', 'location', 'overtime', 'old_game_id',
        'stadium', 'stadium_id', 'referee', 'home_coach', 'away_coach',
        'home_qb_name', 'away_qb_name', 'home_qb_id', 'away_qb_id',
        'spread_line', 'total_line', 'home_moneyline', 'away_moneyline',
        'home_spread_odds', 'away_spread_odds', 'over_odds', 'under_odds',
        'roof', 'surface', 'pfr', 'pff', 'espn', 'ftn', 'gsis', 'nfl_detail_id',
        # Don't use spread features for prediction (that's the point of the model)
        'is_home_underdog', 'is_big_favorite', 'is_close_game',
        # Edge detection features (for output, not input)
        'edges_detected', 'edge_types', 'edge_confidence', 'edge_team', 'edge_recommendation',
    ]

    feature_cols = [c for c in train_df.columns
                    if c not in exclude_cols
                    and train_df[c].dtype in ['int64', 'float64']]

    logger.info(f"Using {len(feature_cols)} features: {feature_cols}")

    # Prepare data
    X_train = train_df[feature_cols].fillna(0)
    y_train = train_df['target']
    X_val = val_df[feature_cols].fillna(0)
    y_val = val_df['target']

    # Train
    config = {
        'params': {
            'n_estimators': 200,
            'max_depth': 4,  # Keep shallow to avoid overfit
            'learning_rate': 0.05,
            'early_stopping_rounds': 20,
        }
    }

    model = XGBoostNFLModel(config)
    model.train(X_train, y_train, X_val, y_val)

    # Evaluate
    metrics = model.evaluate(X_val, y_val)
    logger.info(f"Validation metrics: {metrics}")

    # Calibrate
    calibrator = ModelCalibrator(model, method='isotonic')
    calibrator.calibrate(X_val, y_val)

    cal_metrics = calibrator.evaluate_calibration(X_val, y_val)
    logger.info(f"Calibration: ECE={cal_metrics['ece_calibrated']:.4f}")

    # Save
    model.save("models/nfl_model.json")

    # Save feature columns for prediction
    with open("models/feature_cols.json", "w") as f:
        json.dump(feature_cols, f)

    return model, calibrator, feature_cols


def load_model():
    """Load trained model."""
    from src.models.xgboost_model import XGBoostNFLModel
    from src.models.calibration import ModelCalibrator

    model_path = Path("models/nfl_model.json")
    if not model_path.exists():
        return None, None, None

    model = XGBoostNFLModel.load(str(model_path))

    with open("models/feature_cols.json") as f:
        feature_cols = json.load(f)

    # Note: Calibrator needs to be refit - for now use raw model
    return model, None, feature_cols


def get_upcoming_games():
    """Get this week's games."""
    from src.data.nfl_data import get_current_week_games

    games = get_current_week_games()
    return games


def generate_picks(games_df, model, feature_cols, calibrator=None):
    """Generate picks for upcoming games."""
    from src.edges.market_edges import MarketEdgeDetector, detect_edges_for_week

    if len(games_df) == 0:
        logger.warning("No upcoming games found")
        return pd.DataFrame()

    logger.info(f"Generating picks for {len(games_df)} games...")

    # Prepare features (basic features only - no PBP stats for future games)
    games = games_df.copy()

    # Add basic features
    games['home_field'] = 1
    games['div_game'] = games.apply(
        lambda x: 1 if _same_division(x['home_team'], x['away_team']) else 0,
        axis=1
    )
    games['week_normalized'] = games['week'] / 18

    # Rest days (estimate from schedule)
    games['home_rest_days'] = 7
    games['away_rest_days'] = 7
    games['rest_advantage'] = 0

    games['is_prime_time'] = games['gametime'].apply(
        lambda x: 1 if pd.notna(x) and ('20:' in str(x) or '21:' in str(x)) else 0
    )

    # Weather features (if available)
    for col in ['temp_normalized', 'is_cold', 'is_dome', 'wind_normalized', 'high_wind']:
        if col not in games.columns:
            games[col] = 0

    # EPA features (use league average for unknown)
    for col in ['home_epa', 'away_epa', 'home_def_epa', 'away_def_epa']:
        if col not in games.columns:
            games[col] = 0

    for col in ['home_success', 'away_success']:
        if col not in games.columns:
            games[col] = 0.45

    games['epa_diff'] = games.get('home_epa', 0) - games.get('away_epa', 0)
    games['success_diff'] = games.get('home_success', 0.45) - games.get('away_success', 0.45)

    # Ensure all feature columns exist
    for col in feature_cols:
        if col not in games.columns:
            games[col] = 0

    # Predict
    X = games[feature_cols].fillna(0)
    probs = model.predict_proba(X)

    games['model_home_prob'] = probs
    games['model_away_prob'] = 1 - probs

    # Detect market edges
    if 'spread_line' in games.columns:
        games = detect_edges_for_week(games)
    else:
        games['edges_detected'] = 0
        games['edge_types'] = None
        games['edge_recommendation'] = None

    # Calculate implied probabilities from spread (rough conversion)
    if 'spread_line' in games.columns:
        # Rough: each point = ~3% probability
        games['spread_implied_prob'] = 0.5 - (games['spread_line'] * 0.03)
        games['spread_implied_prob'] = games['spread_implied_prob'].clip(0.1, 0.9)
    else:
        games['spread_implied_prob'] = 0.5

    # Find value
    games['edge_vs_market'] = games['model_home_prob'] - games['spread_implied_prob']
    games['has_value'] = games['edge_vs_market'].abs() > 0.05

    # Confidence
    games['confidence'] = games.apply(_calc_confidence, axis=1)

    # Pick
    games['pick'] = games.apply(_make_pick, axis=1)
    games['pick_side'] = games.apply(
        lambda x: x['home_team'] if x['model_home_prob'] > 0.5 else x['away_team'],
        axis=1
    )

    return games


def _same_division(home, away):
    """Check if same division."""
    divisions = {
        'AFC East': ['BUF', 'MIA', 'NE', 'NYJ'],
        'AFC North': ['BAL', 'CIN', 'CLE', 'PIT'],
        'AFC South': ['HOU', 'IND', 'JAX', 'TEN'],
        'AFC West': ['DEN', 'KC', 'LAC', 'LV'],
        'NFC East': ['DAL', 'NYG', 'PHI', 'WAS'],
        'NFC North': ['CHI', 'DET', 'GB', 'MIN'],
        'NFC South': ['ATL', 'CAR', 'NO', 'TB'],
        'NFC West': ['ARI', 'LAR', 'SEA', 'SF'],
    }
    for teams in divisions.values():
        if home in teams and away in teams:
            return True
    return False


def _calc_confidence(row):
    """Calculate confidence level."""
    prob = max(row['model_home_prob'], row['model_away_prob'])
    edge = abs(row.get('edge_vs_market', 0))
    has_edge = row.get('edges_detected', 0) > 0

    if prob > 0.65 and edge > 0.08 and has_edge:
        return 'HIGH'
    elif prob > 0.58 and edge > 0.05:
        return 'MEDIUM'
    elif prob > 0.52:
        return 'LOW'
    else:
        return 'SKIP'


def _make_pick(row):
    """Make pick recommendation."""
    home_prob = row['model_home_prob']
    spread = row.get('spread_line', 0)
    edges = row.get('edges_detected', 0)
    edge_rec = row.get('edge_recommendation', None)

    # If market edge detected, that takes priority
    if edges > 0 and edge_rec:
        return f"EDGE: {edge_rec}"

    # Model-based pick
    if home_prob > 0.58:
        if spread < -7:
            return f"{row['home_team']} ML (big favorite, skip spread)"
        else:
            return f"{row['home_team']} {spread}"
    elif home_prob < 0.42:
        if spread > 7:
            return f"{row['away_team']} ML (big favorite, skip spread)"
        else:
            return f"{row['away_team']} +{abs(spread)}"
    else:
        return "NO PLAY (too close)"


def print_picks(picks_df):
    """Print picks in readable format."""
    print("\n" + "=" * 80)
    print("NFL PICKS - AUTONOMOUS SYSTEM")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 80)

    if len(picks_df) == 0:
        print("\nNo games to analyze.")
        return

    # Sort by confidence
    conf_order = {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2, 'SKIP': 3}
    picks_df['conf_order'] = picks_df['confidence'].map(conf_order)
    picks_df = picks_df.sort_values('conf_order')

    print("\n" + "-" * 80)
    print("TOP PLAYS")
    print("-" * 80)

    for _, row in picks_df[picks_df['confidence'].isin(['HIGH', 'MEDIUM'])].iterrows():
        conf_icon = {'HIGH': '★★★', 'MEDIUM': '★★'}[row['confidence']]

        print(f"\n{conf_icon} {row['away_team']} @ {row['home_team']}")
        print(f"   Spread: {row.get('spread_line', 'N/A')}")
        print(f"   Model: {row['model_home_prob']:.0%} home win")
        print(f"   Edge: {row.get('edge_vs_market', 0):.1%} vs market")

        if row.get('edges_detected', 0) > 0:
            print(f"   ⚡ Market Edge: {row.get('edge_types', 'N/A')}")

        print(f"   >>> PICK: {row['pick']}")

    # All games summary
    print("\n" + "-" * 80)
    print("ALL GAMES")
    print("-" * 80)

    for _, row in picks_df.iterrows():
        marker = {
            'HIGH': '★★★',
            'MEDIUM': '★★',
            'LOW': '★',
            'SKIP': '   '
        }[row['confidence']]

        print(f"{marker} {row['away_team']:>4} @ {row['home_team']:<4} | "
              f"Model: {row['model_home_prob']:>5.0%} | "
              f"{row['pick'][:40]}")

    print("\n" + "=" * 80)
    print("REMEMBER: This is for FUN. Bet responsibly. Past performance ≠ future results.")
    print("=" * 80)


def save_picks(picks_df):
    """Save picks to file."""
    Path("data/predictions").mkdir(parents=True, exist_ok=True)

    date_str = datetime.now().strftime('%Y%m%d')
    filepath = f"data/predictions/picks_{date_str}.csv"

    cols = [
        'game_id', 'gameday', 'away_team', 'home_team',
        'spread_line', 'model_home_prob', 'model_away_prob',
        'edge_vs_market', 'confidence', 'pick', 'pick_side',
        'edges_detected', 'edge_types', 'edge_recommendation'
    ]

    save_cols = [c for c in cols if c in picks_df.columns]
    picks_df[save_cols].to_csv(filepath, index=False)

    logger.info(f"Saved picks to {filepath}")


def main():
    parser = argparse.ArgumentParser(description="Autonomous NFL Picks Generator")
    parser.add_argument('--train', action='store_true', help="Train model from scratch")
    parser.add_argument('--download', action='store_true', help="Download fresh data")
    parser.add_argument('--week', type=int, help="Specific week to analyze")
    args = parser.parse_args()

    # Install dependencies
    install_dependencies()

    # Download data if needed
    if args.download or args.train or not Path("data/raw").exists():
        schedules, pbp = download_data()
        features = build_features(schedules, pbp)

    # Train if needed
    if args.train or not Path("models/nfl_model.json").exists():
        if 'features' not in dir():
            features = pd.read_parquet("data/processed/features.parquet")
        model, calibrator, feature_cols = train_model(features)
    else:
        model, calibrator, feature_cols = load_model()
        if model is None:
            logger.error("No model found. Run with --train first.")
            return 1

    # Get upcoming games
    games = get_upcoming_games()

    # Generate picks
    picks = generate_picks(games, model, feature_cols, calibrator)

    # Print and save
    print_picks(picks)
    save_picks(picks)

    return 0


if __name__ == "__main__":
    sys.exit(main())
