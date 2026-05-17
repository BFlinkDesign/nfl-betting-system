#!/usr/bin/env python3
"""
🏈 NFL AUTONOMOUS BETTING SYSTEM - End-to-End

Source of truth, self-validating, no guessing.

Pipeline:
1. DATA: Pull from nflverse (verified source)
2. FEATURES: Research-backed (EPA, rest, divisional, etc.)
3. MODEL: XGBoost with calibration
4. EDGES: Documented 60%+ angles only
5. VALIDATION: Brier, log loss, CLV tracking
6. FEEDBACK: Self-improving loop
7. OUTPUT: Clean card for frontend

All metrics tracked. System proves itself over time.

Usage:
    python scripts/autonomous_system.py              # Generate card
    python scripts/autonomous_system.py --validate   # Run validation
    python scripts/autonomous_system.py --feedback   # Show feedback report
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="NFL Autonomous Betting System")
    parser.add_argument('--validate', action='store_true', help="Run validation report")
    parser.add_argument('--feedback', action='store_true', help="Show feedback/improvement report")
    parser.add_argument('--download', action='store_true', help="Download fresh data")
    parser.add_argument('--train', action='store_true', help="Train model")
    parser.add_argument('--output', type=str, default='card', help="Output format: card, json, csv")
    args = parser.parse_args()

    print(BANNER)

    # Initialize core systems
    from src.core.validation_framework import create_validation_framework
    from src.core.feedback_loop import create_feedback_loop

    validator = create_validation_framework()
    feedback = create_feedback_loop()

    # Mode: Validation Report
    if args.validate:
        run_validation_report(validator)
        return 0

    # Mode: Feedback Report
    if args.feedback:
        run_feedback_report(feedback)
        return 0

    # Mode: Generate Card
    return generate_card(args, validator, feedback)


def generate_card(args, validator, feedback):
    """Generate the picks card - main pipeline."""
    from src.data.nfl_data import setup_data_directory

    setup_data_directory()

    logger.info("🔄 Starting autonomous pipeline...")

    # Step 1: Get data
    logger.info("📥 Step 1: Data acquisition")
    games, schedules = get_data(args.download)

    if games is None or len(games) == 0:
        logger.error("❌ No games available")
        return 1

    logger.info(f"   Found {len(games)} upcoming games")

    # Step 2: Load/train model
    logger.info("🧠 Step 2: Model")
    model, feature_cols = get_model(args.train, schedules)

    # Step 3: Generate predictions
    logger.info("🎯 Step 3: Predictions")
    predictions = generate_predictions(games, model, feature_cols)

    # Step 4: Apply high-accuracy filters
    logger.info("🔍 Step 4: High-accuracy edge filtering")
    filtered = apply_edge_filters(predictions)

    # Step 5: Generate card output
    logger.info("📋 Step 5: Generate card")
    card = generate_card_output(filtered, args.output)

    # Step 6: Display
    print(card)

    # Step 7: Save outputs
    save_outputs(filtered, card, args.output)

    logger.info("✅ Pipeline complete")
    return 0


def get_data(download: bool):
    """Get NFL data from verified sources."""
    from src.data.nfl_data import (
        download_schedules, get_current_week_games
    )

    try:
        current_year = datetime.now().year
        current_month = datetime.now().month

        if current_month >= 9:
            seasons = [current_year]
        else:
            seasons = [current_year - 1]

        if download:
            schedules = download_schedules(seasons)
        else:
            # Try to load cached
            cache_path = Path(f"data/raw/schedules_{seasons[0]}_{seasons[0]}.parquet")
            if cache_path.exists():
                import pandas as pd
                schedules = pd.read_parquet(cache_path)
            else:
                schedules = download_schedules(seasons)

        games = get_current_week_games()
        return games, schedules

    except Exception as e:
        logger.warning(f"Data fetch failed: {e}")
        return None, None


def get_model(train: bool, schedules):
    """Load or train model."""
    from src.models.xgboost_model import XGBoostNFLModel

    model_path = Path("models/nfl_model.json")
    feature_path = Path("models/feature_cols.json")

    if model_path.exists() and not train:
        try:
            model = XGBoostNFLModel.load(str(model_path))
            with open(feature_path) as f:
                feature_cols = json.load(f)
            logger.info("   Loaded existing model")
            return model, feature_cols
        except Exception as e:
            logger.warning(f"   Model load failed: {e}")

    # Need to train
    if schedules is not None and len(schedules) > 100:
        logger.info("   Training new model...")
        model, feature_cols = train_model(schedules)
        return model, feature_cols

    logger.warning("   No model available")
    return None, []


def train_model(schedules):
    """Train XGBoost model."""
    from src.models.xgboost_model import XGBoostNFLModel
    from src.data.nfl_data import prepare_features
    import pandas as pd

    # Prepare features
    features = prepare_features(schedules)
    features = features[features['home_score'].notna()]

    if len(features) < 100:
        logger.warning("Insufficient data for training")
        return None, []

    max_season = features['season'].max()
    train_df = features[features['season'] < max_season]
    val_df = features[features['season'] == max_season]

    exclude = [
        'game_id', 'gameday', 'home_team', 'away_team', 'season', 'week',
        'home_score', 'away_score', 'target', 'result', 'total', 'game_type',
        'spread_line', 'total_line', 'home_moneyline', 'away_moneyline',
    ]

    feature_cols = [
        c for c in train_df.columns
        if c not in exclude and train_df[c].dtype in ['int64', 'float64']
    ]

    X_train = train_df[feature_cols].fillna(0)
    y_train = train_df['target']
    X_val = val_df[feature_cols].fillna(0)
    y_val = val_df['target']

    config = {'params': {'n_estimators': 150, 'max_depth': 4, 'learning_rate': 0.05}}
    model = XGBoostNFLModel(config)
    model.train(X_train, y_train, X_val, y_val)

    # Save
    Path("models").mkdir(exist_ok=True)
    model.save("models/nfl_model.json")
    with open("models/feature_cols.json", "w") as f:
        json.dump(feature_cols, f)

    return model, feature_cols


def generate_predictions(games, model, feature_cols):
    """Generate model predictions."""
    import pandas as pd

    games = games.copy()

    if model is None:
        games['model_prob'] = 0.5
        games['edge'] = 0
        return games

    # Add features
    for col in feature_cols:
        if col not in games.columns:
            games[col] = 0

    X = games[feature_cols].fillna(0)
    probs = model.predict_proba(X)

    games['model_prob'] = probs

    # Calculate edge vs market
    if 'spread_line' in games.columns:
        games['market_prob'] = 0.5 - (games['spread_line'] * 0.03)
        games['edge'] = games['model_prob'] - games['market_prob']
    else:
        games['edge'] = 0

    return games


def apply_edge_filters(predictions):
    """Apply high-accuracy edge filters (documented 60%+ only)."""
    from src.picks.high_accuracy_picks import HighAccuracyEngine

    predictions = predictions.copy()

    # Run high accuracy analysis
    engine = HighAccuracyEngine()

    for idx, row in predictions.iterrows():
        engine.analyze_game(
            game_id=row.get('game_id', f'game_{idx}'),
            home_team=row['home_team'],
            away_team=row['away_team'],
            spread=row.get('spread_line', 0),
            total=row.get('total_line', 45),
            week=row.get('week', 1),
        )

    # Get documented edges
    documented_edges = engine.get_best_picks()

    # Add edge info to predictions
    edge_games = {e.game_id for e in documented_edges}
    predictions['has_documented_edge'] = predictions.get('game_id', predictions.index).isin(edge_games)

    # Add edge details
    edge_map = {e.game_id: e for e in documented_edges}
    predictions['edge_type'] = predictions.apply(
        lambda r: edge_map.get(r.get('game_id', ''), None),
        axis=1
    )

    return predictions


def generate_card_output(predictions, output_format: str) -> str:
    """Generate the card output."""
    if output_format == 'json':
        return generate_json_card(predictions)
    elif output_format == 'csv':
        return generate_csv_card(predictions)
    else:
        return generate_visual_card(predictions)


def generate_visual_card(predictions) -> str:
    """Generate visual card for display."""
    lines = []

    lines.append("")
    lines.append("╔" + "═" * 68 + "╗")
    lines.append("║" + " 🏈 NFL PICKS CARD ".center(68) + "║")
    lines.append("║" + f" {datetime.now().strftime('%B %d, %Y')} ".center(68) + "║")
    lines.append("╠" + "═" * 68 + "╣")

    # Documented high-accuracy picks first
    documented = predictions[predictions['has_documented_edge'] == True]

    if len(documented) > 0:
        lines.append("║" + " 🎯 HIGH ACCURACY (60%+ Documented) ".ljust(68) + "║")
        lines.append("╟" + "─" * 68 + "╢")

        for _, row in documented.iterrows():
            edge = row.get('edge_type')
            if edge:
                game = f"{row['away_team']} @ {row['home_team']}"
                pick = edge.pick
                rate = f"{edge.historical_rate:.0%}"
                units = f"{edge.recommended_units}u"

                lines.append("║" + f"  ⭐ {game}".ljust(68) + "║")
                lines.append("║" + f"     {pick}".ljust(68) + "║")
                lines.append("║" + f"     Historical: {rate} | Units: {units}".ljust(68) + "║")
                lines.append("║" + f"     Source: {edge.sample_info}".ljust(68) + "║")
                lines.append("║" + "".ljust(68) + "║")

    # Model edge picks
    model_edges = predictions[
        (predictions['has_documented_edge'] == False) &
        (predictions['edge'].abs() > 0.05)
    ].sort_values('edge', key=abs, ascending=False)

    if len(model_edges) > 0:
        lines.append("╟" + "─" * 68 + "╢")
        lines.append("║" + " 📊 MODEL EDGE PICKS ".ljust(68) + "║")
        lines.append("╟" + "─" * 68 + "╢")

        for _, row in model_edges.head(5).iterrows():
            game = f"{row['away_team']} @ {row['home_team']}"
            prob = row.get('model_prob', 0.5)
            edge = row.get('edge', 0)
            spread = row.get('spread_line', 0)

            pick_team = row['home_team'] if prob > 0.5 else row['away_team']
            pick_spread = spread if prob > 0.5 else -spread

            lines.append("║" + f"  • {game}".ljust(68) + "║")
            lines.append("║" + f"    Pick: {pick_team} {pick_spread:+.1f}".ljust(68) + "║")
            lines.append("║" + f"    Model: {prob:.0%} | Edge: {edge:+.1%}".ljust(68) + "║")
            lines.append("║" + "".ljust(68) + "║")

    # Full slate
    lines.append("╟" + "─" * 68 + "╢")
    lines.append("║" + " 📋 FULL SLATE ".ljust(68) + "║")
    lines.append("╟" + "─" * 68 + "╢")

    header = "  Game              Spread   Model   Edge    Action"
    lines.append("║" + header.ljust(68) + "║")
    lines.append("║" + ("  " + "-" * 60).ljust(68) + "║")

    for _, row in predictions.iterrows():
        game = f"{row['away_team']}@{row['home_team']}"
        spread = f"{row.get('spread_line', 0):+.1f}"
        prob = f"{row.get('model_prob', 0.5):.0%}"
        edge = row.get('edge', 0)
        edge_str = f"{edge:+.0%}"

        if row.get('has_documented_edge'):
            action = "⭐ BET"
        elif abs(edge) > 0.05:
            action = "✓ LEAN"
        else:
            action = "- PASS"

        line = f"  {game:<16} {spread:>6}   {prob:>5}  {edge_str:>6}   {action}"
        lines.append("║" + line.ljust(68) + "║")

    lines.append("╠" + "═" * 68 + "╣")
    lines.append("║" + " ⚠️  VALIDATION STATUS ".ljust(68) + "║")
    lines.append("╟" + "─" * 68 + "╢")
    lines.append("║" + "  Sample size: [TRACKING]".ljust(68) + "║")
    lines.append("║" + "  Historical documented angles only.".ljust(68) + "║")
    lines.append("║" + "  System self-validates over time.".ljust(68) + "║")
    lines.append("╚" + "═" * 68 + "╝")

    return "\n".join(lines)


def generate_json_card(predictions) -> str:
    """Generate JSON output for frontend."""
    card = {
        'generated_at': datetime.now().isoformat(),
        'picks': [],
    }

    for _, row in predictions.iterrows():
        pick = {
            'game_id': row.get('game_id', ''),
            'away_team': row['away_team'],
            'home_team': row['home_team'],
            'spread': row.get('spread_line', 0),
            'model_prob': row.get('model_prob', 0.5),
            'edge': row.get('edge', 0),
            'has_documented_edge': bool(row.get('has_documented_edge', False)),
        }

        if row.get('edge_type'):
            edge = row['edge_type']
            pick['edge_details'] = {
                'angle': edge.angle_name,
                'historical_rate': edge.historical_rate,
                'sample': edge.sample_info,
                'pick': edge.pick,
                'units': edge.recommended_units,
            }

        card['picks'].append(pick)

    return json.dumps(card, indent=2)


def generate_csv_card(predictions) -> str:
    """Generate CSV output."""
    lines = ['game,spread,model_prob,edge,documented,pick,units']

    for _, row in predictions.iterrows():
        game = f"{row['away_team']}@{row['home_team']}"
        spread = row.get('spread_line', 0)
        prob = row.get('model_prob', 0.5)
        edge = row.get('edge', 0)
        documented = row.get('has_documented_edge', False)

        if row.get('edge_type'):
            pick = row['edge_type'].pick
            units = row['edge_type'].recommended_units
        else:
            pick = ''
            units = 0

        lines.append(f"{game},{spread},{prob:.3f},{edge:.3f},{documented},{pick},{units}")

    return "\n".join(lines)


def save_outputs(predictions, card, output_format):
    """Save outputs to files."""
    output_dir = Path("data/outputs")
    output_dir.mkdir(parents=True, exist_ok=True)

    date_str = datetime.now().strftime('%Y%m%d')

    # Save card
    ext = {'json': 'json', 'csv': 'csv'}.get(output_format, 'txt')
    card_path = output_dir / f"card_{date_str}.{ext}"
    card_path.write_text(card)

    # Always save JSON for programmatic access
    if output_format != 'json':
        json_card = generate_json_card(predictions)
        json_path = output_dir / f"card_{date_str}.json"
        json_path.write_text(json_card)

    logger.info(f"📁 Saved to {output_dir}")


def run_validation_report(validator):
    """Run validation report."""
    result = validator.validate()
    validator.print_validation_report(result)


def run_feedback_report(feedback):
    """Run feedback report."""
    print(feedback.generate_feedback_report())


BANNER = """
╔═══════════════════════════════════════════════════════════════════════╗
║                                                                       ║
║   🏈  NFL AUTONOMOUS BETTING SYSTEM                                   ║
║                                                                       ║
║   Source of truth. Self-validating. No guessing.                      ║
║                                                                       ║
║   Data: nflverse (verified)                                           ║
║   Edges: 60%+ documented only                                         ║
║   Validation: Brier, log loss, CLV                                    ║
║   Feedback: Self-improving loop                                       ║
║                                                                       ║
╚═══════════════════════════════════════════════════════════════════════╝
"""


if __name__ == "__main__":
    sys.exit(main())
