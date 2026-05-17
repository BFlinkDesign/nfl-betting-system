#!/usr/bin/env python3
"""
Enhanced NFL Picks System - Full Pipeline

Integrates all components from competitive intelligence research:
- Rest disparity analysis (Warren Sharp framework)
- Hypothesis-tested edges
- Multi-layer probability stacking
- CLV tracking ready

This builds on autonomous_picks.py with the full professional toolkit.

Usage:
    python scripts/enhanced_picks.py          # This week's picks
    python scripts/enhanced_picks.py --train  # Train model first
    python scripts/enhanced_picks.py --validate  # Validate edges against history

For FUN beer money bets. Gamble responsibly.
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import numpy as np
import pandas as pd

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def run_full_pipeline(args):
    """Run the complete enhanced picks pipeline."""
    from src.data.nfl_data import (
        download_schedules, download_pbp, calculate_team_stats,
        prepare_features, get_current_week_games, setup_data_directory
    )
    from src.edges.market_edges import detect_edges_for_week
    from src.edges.rest_disparity import analyze_week_rest
    from src.models.probability_stacking import stack_for_week, ProbabilityStacker

    # Setup
    setup_data_directory()

    # 1. Data
    if args.download or args.train or not Path("data/raw").exists():
        logger.info("Downloading fresh data...")
        schedules, pbp = download_data()
        features = build_features(schedules, pbp)
    elif Path("data/processed/features.parquet").exists():
        features = pd.read_parquet("data/processed/features.parquet")
    else:
        logger.error("No data found. Run with --download first.")
        return 1

    # 2. Model
    if args.train or not Path("models/nfl_model.json").exists():
        logger.info("Training model...")
        model, calibrator, feature_cols = train_model(features)
    else:
        model, calibrator, feature_cols = load_model()
        if model is None:
            logger.error("No model found. Run with --train first.")
            return 1

    # 3. Validate edges (optional)
    if args.validate:
        logger.info("Validating historical edges...")
        validate_edges(features)

    # 4. Get upcoming games
    games = get_current_week_games()
    if len(games) == 0:
        logger.warning("No upcoming games found")
        return 0

    # 5. Generate base predictions
    picks = generate_base_picks(games, model, feature_cols)

    # 6. Detect market edges
    picks = detect_edges_for_week(picks)

    # 7. Analyze rest disparity
    picks = analyze_week_rest(picks)

    # 8. Stack probabilities
    picks = stack_for_week(picks, picks['model_home_prob'].values)

    # 9. Generate final recommendations
    picks = make_final_picks(picks)

    # 10. Output
    print_enhanced_picks(picks)
    save_enhanced_picks(picks)

    return 0


def download_data():
    """Download NFL data."""
    from src.data.nfl_data import download_schedules, download_pbp, setup_data_directory

    setup_data_directory()

    current_year = datetime.now().year
    current_month = datetime.now().month

    if current_month >= 9:
        seasons = list(range(2020, current_year + 1))
    else:
        seasons = list(range(2020, current_year))

    logger.info(f"Downloading data for {seasons}")

    schedules = download_schedules(
        seasons,
        save_path=f"data/raw/schedules_{min(seasons)}_{max(seasons)}.parquet"
    )

    recent_seasons = [s for s in seasons if s >= max(seasons) - 2]
    pbp = download_pbp(
        recent_seasons,
        save_path=f"data/raw/pbp_{min(recent_seasons)}_{max(recent_seasons)}.parquet"
    )

    return schedules, pbp


def build_features(schedules, pbp):
    """Build features from raw data."""
    from src.data.nfl_data import calculate_team_stats, prepare_features

    team_stats = calculate_team_stats(pbp)
    features_df = prepare_features(schedules, team_stats)
    features_df.to_parquet("data/processed/features.parquet", index=False)

    return features_df


def train_model(features_df):
    """Train XGBoost model."""
    from src.models.xgboost_model import XGBoostNFLModel

    logger.info("Training model...")

    max_season = features_df['season'].max()
    train_df = features_df[features_df['season'] < max_season]
    val_df = features_df[features_df['season'] == max_season]

    exclude_cols = [
        'game_id', 'gameday', 'home_team', 'away_team', 'season', 'week',
        'home_score', 'away_score', 'target', 'result', 'total', 'game_type',
        'weekday', 'gametime', 'location', 'overtime', 'old_game_id',
        'stadium', 'stadium_id', 'referee', 'home_coach', 'away_coach',
        'home_qb_name', 'away_qb_name', 'home_qb_id', 'away_qb_id',
        'spread_line', 'total_line', 'home_moneyline', 'away_moneyline',
        'home_spread_odds', 'away_spread_odds', 'over_odds', 'under_odds',
        'roof', 'surface', 'pfr', 'pff', 'espn', 'ftn', 'gsis', 'nfl_detail_id',
        'is_home_underdog', 'is_big_favorite', 'is_close_game',
        'edges_detected', 'edge_types', 'edge_confidence', 'edge_team', 'edge_recommendation',
    ]

    feature_cols = [c for c in train_df.columns
                    if c not in exclude_cols
                    and train_df[c].dtype in ['int64', 'float64']]

    X_train = train_df[feature_cols].fillna(0)
    y_train = train_df['target']
    X_val = val_df[feature_cols].fillna(0)
    y_val = val_df['target']

    config = {
        'params': {
            'n_estimators': 200,
            'max_depth': 4,
            'learning_rate': 0.05,
            'early_stopping_rounds': 20,
        }
    }

    model = XGBoostNFLModel(config)
    model.train(X_train, y_train, X_val, y_val)

    metrics = model.evaluate(X_val, y_val)
    logger.info(f"Validation metrics: {metrics}")

    model.save("models/nfl_model.json")

    with open("models/feature_cols.json", "w") as f:
        json.dump(feature_cols, f)

    return model, None, feature_cols


def load_model():
    """Load trained model."""
    from src.models.xgboost_model import XGBoostNFLModel

    model_path = Path("models/nfl_model.json")
    if not model_path.exists():
        return None, None, None

    model = XGBoostNFLModel.load(str(model_path))

    with open("models/feature_cols.json") as f:
        feature_cols = json.load(f)

    return model, None, feature_cols


def validate_edges(features_df):
    """Validate claimed edges against historical data."""
    from src.validation.hypothesis_testing import validate_historical_edges, quick_pivot_analysis

    df = features_df.copy()
    df = df[df['home_score'].notna()]

    if 'spread_line' not in df.columns:
        logger.warning("No spread data for edge validation")
        return

    results = validate_historical_edges(df)

    print("\n" + "="*70)
    print("EDGE VALIDATION AGAINST HISTORICAL DATA")
    print("="*70)

    for edge_name, result in results.items():
        status = "✓" if result.is_significant else "✗"
        print(f"\n{status} {edge_name}:")
        print(f"   Rate: {result.observed_rate:.1%} (n={result.sample_size})")
        print(f"   p-value: {result.p_value:.4f}")
        print(f"   Verdict: {result.verdict}")


def generate_base_picks(games_df, model, feature_cols):
    """Generate base model predictions."""
    games = games_df.copy()

    # Add basic features
    games['home_field'] = 1
    games['div_game'] = games.apply(
        lambda x: 1 if _same_division(x['home_team'], x['away_team']) else 0,
        axis=1
    )
    games['week_normalized'] = games['week'] / 18
    games['home_rest_days'] = 7
    games['away_rest_days'] = 7
    games['rest_advantage'] = 0

    games['is_prime_time'] = games['gametime'].apply(
        lambda x: 1 if pd.notna(x) and ('20:' in str(x) or '21:' in str(x)) else 0
    )

    for col in ['temp_normalized', 'is_cold', 'is_dome', 'wind_normalized', 'high_wind']:
        if col not in games.columns:
            games[col] = 0

    for col in ['home_epa', 'away_epa', 'home_def_epa', 'away_def_epa']:
        if col not in games.columns:
            games[col] = 0

    for col in ['home_success', 'away_success']:
        if col not in games.columns:
            games[col] = 0.45

    games['epa_diff'] = games.get('home_epa', 0) - games.get('away_epa', 0)
    games['success_diff'] = games.get('home_success', 0.45) - games.get('away_success', 0.45)

    for col in feature_cols:
        if col not in games.columns:
            games[col] = 0

    X = games[feature_cols].fillna(0)
    probs = model.predict_proba(X)

    games['model_home_prob'] = probs
    games['model_away_prob'] = 1 - probs

    return games


def make_final_picks(picks_df):
    """Generate final pick recommendations integrating all signals."""
    picks = picks_df.copy()

    # Use stacked probability if available, else model
    prob_col = 'stacked_prob' if 'stacked_prob' in picks.columns else 'model_home_prob'

    # Calculate edge magnitude
    if 'spread_line' in picks.columns:
        picks['market_prob'] = 0.5 - (picks['spread_line'] * 0.03)
        picks['market_prob'] = picks['market_prob'].clip(0.1, 0.9)
    else:
        picks['market_prob'] = 0.5

    picks['total_edge'] = picks[prob_col] - picks['market_prob']

    # Rest edge bonus
    if 'rest_edge_magnitude' in picks.columns:
        picks['total_edge'] += picks['rest_edge_magnitude'] * 0.02

    # Confidence scoring
    picks['confidence_score'] = picks.apply(_calc_confidence_score, axis=1)

    # Final pick
    picks['final_pick'] = picks.apply(_make_final_pick, axis=1)
    picks['bet_units'] = picks.apply(_calc_bet_units, axis=1)

    return picks


def _calc_confidence_score(row):
    """Calculate confidence score 0-100."""
    score = 50  # Base

    # Edge magnitude (biggest factor)
    edge = abs(row.get('total_edge', 0))
    score += edge * 200  # +20 for 10% edge

    # Market edges detected
    edges = row.get('edges_detected', 0)
    score += edges * 10

    # Rest advantage
    rest_conf = row.get('rest_confidence', 'none')
    if rest_conf == 'high':
        score += 15
    elif rest_conf == 'medium':
        score += 8

    # Model-market agreement
    model_prob = row.get('model_home_prob', 0.5)
    market_prob = row.get('market_prob', 0.5)
    if (model_prob > 0.5) == (market_prob > 0.5):
        score += 5  # Agreement bonus

    return min(100, max(0, score))


def _make_final_pick(row):
    """Generate final pick recommendation."""
    prob_col = 'stacked_prob' if 'stacked_prob' in row.index else 'model_home_prob'
    home_prob = row[prob_col]
    spread = row.get('spread_line', 0)
    confidence = row.get('confidence_score', 50)

    # Determine pick side
    if home_prob > 0.55:
        pick_team = row['home_team']
        pick_spread = spread
    elif home_prob < 0.45:
        pick_team = row['away_team']
        pick_spread = -spread
    else:
        return "PASS - No clear edge"

    # Format pick
    if confidence >= 70:
        prefix = "★★★ STRONG"
    elif confidence >= 55:
        prefix = "★★ LEAN"
    else:
        prefix = "★ SMALL"

    # Add edge context
    edge_types = row.get('edge_types', '')
    rest_rec = row.get('rest_recommendation', '')

    context = []
    if edge_types:
        context.append(f"Edges: {edge_types}")
    if rest_rec and 'No rest edge' not in rest_rec:
        context.append(f"Rest: {rest_rec[:30]}")

    context_str = f" ({'; '.join(context)})" if context else ""

    if pick_spread >= 0:
        return f"{prefix}: {pick_team} +{abs(pick_spread)}{context_str}"
    else:
        return f"{prefix}: {pick_team} {pick_spread}{context_str}"


def _calc_bet_units(row):
    """Calculate recommended bet size in units."""
    confidence = row.get('confidence_score', 50)

    if confidence >= 75:
        return 2.0
    elif confidence >= 65:
        return 1.5
    elif confidence >= 55:
        return 1.0
    elif confidence >= 45:
        return 0.5
    else:
        return 0


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


def print_enhanced_picks(picks_df):
    """Print enhanced picks with all analysis."""
    print("\n" + "=" * 90)
    print("NFL ENHANCED PICKS - MULTI-SIGNAL ANALYSIS")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 90)

    if len(picks_df) == 0:
        print("\nNo games to analyze.")
        return

    # Sort by confidence
    picks = picks_df.sort_values('confidence_score', ascending=False)

    # Top picks section
    top_picks = picks[picks['confidence_score'] >= 55]

    print("\n" + "-" * 90)
    print("TOP PLAYS (Confidence 55+)")
    print("-" * 90)

    for _, row in top_picks.iterrows():
        print(f"\n{row['away_team']:>4} @ {row['home_team']:<4}")
        print(f"   Spread: {row.get('spread_line', 'N/A')}")

        # Probabilities
        prob_col = 'stacked_prob' if 'stacked_prob' in row.index else 'model_home_prob'
        print(f"   Model Prob: {row['model_home_prob']:.0%} | Stacked: {row.get('stacked_prob', row['model_home_prob']):.0%}")
        print(f"   Edge vs Market: {row.get('total_edge', 0):.1%}")

        # Edges
        if row.get('edges_detected', 0) > 0:
            print(f"   ⚡ Market Edges: {row.get('edge_types', 'N/A')}")

        # Rest
        if row.get('rest_situation', 'neutral') != 'neutral':
            print(f"   💤 Rest: {row.get('rest_recommendation', 'N/A')[:50]}")

        # Final pick
        print(f"\n   >>> {row.get('final_pick', 'N/A')}")
        print(f"   >>> Units: {row.get('bet_units', 0)}")

    # All games summary
    print("\n" + "-" * 90)
    print("FULL CARD")
    print("-" * 90)
    print(f"{'Game':<15} {'Spread':>7} {'Model':>7} {'Edge':>7} {'Conf':>5} {'Pick':<40}")
    print("-" * 90)

    for _, row in picks.iterrows():
        game = f"{row['away_team']}@{row['home_team']}"
        spread = f"{row.get('spread_line', 0):+.1f}"
        model = f"{row['model_home_prob']:.0%}"
        edge = f"{row.get('total_edge', 0):+.0%}"
        conf = f"{row.get('confidence_score', 0):.0f}"
        pick = row.get('final_pick', 'PASS')[:38]

        print(f"{game:<15} {spread:>7} {model:>7} {edge:>7} {conf:>5} {pick:<40}")

    print("\n" + "=" * 90)
    print("METHODOLOGY:")
    print("  • Model: XGBoost trained on EPA, success rate, situational factors")
    print("  • Edges: Divisional underdogs (71% ATS), rest advantages, letdown spots")
    print("  • Stacking: Model + Market + Situational weights combined")
    print("  • Track CLV to validate edge over time")
    print("\nThis is for FUN. Gamble responsibly. Past performance ≠ future results.")
    print("=" * 90)


def save_enhanced_picks(picks_df):
    """Save enhanced picks to file."""
    Path("data/predictions").mkdir(parents=True, exist_ok=True)

    date_str = datetime.now().strftime('%Y%m%d')
    filepath = f"data/predictions/enhanced_picks_{date_str}.csv"

    cols = [
        'game_id', 'gameday', 'away_team', 'home_team',
        'spread_line', 'model_home_prob', 'stacked_prob',
        'total_edge', 'confidence_score', 'final_pick', 'bet_units',
        'edges_detected', 'edge_types', 'rest_situation', 'rest_recommendation',
    ]

    save_cols = [c for c in cols if c in picks_df.columns]
    picks_df[save_cols].to_csv(filepath, index=False)

    logger.info(f"Saved enhanced picks to {filepath}")

    # Also save JSON for programmatic access
    json_path = f"data/predictions/enhanced_picks_{date_str}.json"
    picks_df[save_cols].to_json(json_path, orient='records', indent=2)


def main():
    parser = argparse.ArgumentParser(description="Enhanced NFL Picks System")
    parser.add_argument('--train', action='store_true', help="Train model from scratch")
    parser.add_argument('--download', action='store_true', help="Download fresh data")
    parser.add_argument('--validate', action='store_true', help="Validate edges against history")
    args = parser.parse_args()

    return run_full_pipeline(args)


if __name__ == "__main__":
    sys.exit(main())
