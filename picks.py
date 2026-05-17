#!/usr/bin/env python3
"""NFL Picks Generator - Stupid Simple Output

Usage:
    python picks.py              # This week's picks
    python picks.py --week 5     # Specific week
    python picks.py --settle     # Record outcomes
    python picks.py --history    # View history
"""

import json
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Optional
import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler

# Lazy imports for optional deps
DATA_DIR = Path(__file__).parent / "data" / "raw"
PICKS_FILE = Path(__file__).parent / "PICKS.json"


@dataclass
class Pick:
    """A single pick with reasoning."""
    game_id: str
    week: int
    season: int

    # Teams
    home_team: str
    away_team: str

    # The pick
    pick: str  # "KC -3" or "BUF ML"
    pick_team: str
    confidence: float  # 0-100

    # Signal strength
    signal: str  # "🟢 STRONG", "🟡 LEAN", "⚫ SKIP"

    # Reasoning (list of bullet points)
    reasons: List[str]

    # Metadata
    model_version: str
    created_at: str

    # Outcome (filled after game)
    outcome: Optional[str] = None  # "W", "L", "P" (push)
    settled_at: Optional[str] = None


def load_model_and_data():
    """Load the validated RB-NGS model and current data."""
    try:
        import nfl_data_py as nfl
    except ImportError:
        print("ERROR: nfl_data_py not installed")
        print("Run: pip install nfl_data_py")
        return None, None, None

    # Load PBP
    pbp_path = DATA_DIR / "pbp_4seasons.parquet"
    if not pbp_path.exists():
        print("Downloading play-by-play data...")
        pbp = nfl.import_pbp_data([2022, 2023, 2024, 2025])
        pbp.to_parquet(pbp_path)
    else:
        pbp = pd.read_parquet(pbp_path)

    # Load NGS
    print("Loading Next Gen Stats...")
    seasons = list(range(2022, 2027))
    try:
        ngs_rushing = nfl.import_ngs_data('rushing', seasons)
    except:
        ngs_rushing = nfl.import_ngs_data('rushing', [2022, 2023, 2024])

    return pbp, ngs_rushing, nfl


def compute_features(pbp, ngs_rushing):
    """Compute validated features for all teams."""
    # Games
    games = pbp.groupby(['game_id', 'season', 'week', 'home_team', 'away_team']).agg({
        'total_home_score': 'max',
        'total_away_score': 'max',
    }).reset_index()
    games.columns = ['game_id', 'season', 'week', 'home_team', 'away_team', 'home_score', 'away_score']
    games = games.dropna(subset=['home_score', 'away_score'])
    games['home_win'] = (games['home_score'] > games['away_score']).astype(int)

    # EPA rolling
    team_epa = pbp[pbp['play_type'].isin(['pass', 'run']) & pbp['epa'].notna()].groupby(
        ['game_id', 'posteam']
    )['epa'].mean().reset_index()
    team_epa.columns = ['game_id', 'team', 'epa']

    game_info = games[['game_id', 'season', 'week']].drop_duplicates()
    team_epa = team_epa.merge(game_info, on='game_id')
    team_epa = team_epa.sort_values(['team', 'season', 'week'])
    team_epa['epa_roll'] = team_epa.groupby('team')['epa'].transform(
        lambda x: x.shift(1).rolling(5, min_periods=1).mean()
    )

    # RB NGS features
    rb_stats = ngs_rushing.groupby(['season', 'week', 'team_abbr']).agg({
        'efficiency': 'mean',
        'percent_attempts_gte_eight_defenders': 'mean',
        'avg_time_to_los': 'mean',
        'avg_rush_yards': 'mean',
    }).reset_index()
    rb_stats.columns = ['season', 'week', 'team', 'rb_efficiency', 'rb_stacked_box_pct', 'rb_time_to_los', 'rb_ypc']
    rb_stats = rb_stats.sort_values(['team', 'season', 'week'])

    for col in ['rb_efficiency', 'rb_stacked_box_pct', 'rb_time_to_los', 'rb_ypc']:
        rb_stats[f'{col}_roll'] = rb_stats.groupby('team')[col].transform(
            lambda x: x.shift(1).rolling(3, min_periods=1).mean()
        )

    return games, team_epa, rb_stats


def build_feature_matrix(games, team_epa, rb_stats):
    """Build feature matrix for prediction."""
    roll_cols = ['rb_efficiency_roll', 'rb_stacked_box_pct_roll', 'rb_time_to_los_roll', 'rb_ypc_roll']

    # Home RB stats
    home_rb = rb_stats[['season', 'week', 'team'] + roll_cols].copy()
    home_rb.columns = ['season', 'week', 'home_team'] + [f'home_{c}' for c in roll_cols]

    # Away RB stats
    away_rb = rb_stats[['season', 'week', 'team'] + roll_cols].copy()
    away_rb.columns = ['season', 'week', 'away_team'] + [f'away_{c}' for c in roll_cols]

    df = games.merge(home_rb, on=['season', 'week', 'home_team'], how='left')
    df = df.merge(away_rb, on=['season', 'week', 'away_team'], how='left')

    # EPA
    home_epa = team_epa[['game_id', 'team', 'epa_roll']].rename(
        columns={'team': 'home_team', 'epa_roll': 'home_epa'})
    away_epa = team_epa[['game_id', 'team', 'epa_roll']].rename(
        columns={'team': 'away_team', 'epa_roll': 'away_epa'})

    df = df.merge(home_epa, on=['game_id', 'home_team'], how='left')
    df = df.merge(away_epa, on=['game_id', 'away_team'], how='left')

    # Create differentials
    df['epa_diff'] = df['home_epa'].fillna(0) - df['away_epa'].fillna(0)
    for col in roll_cols:
        df[f'diff_{col}'] = df[f'home_{col}'].fillna(0) - df[f'away_{col}'].fillna(0)

    return df


def generate_reasoning(row, prob):
    """Generate human-readable reasoning for a pick."""
    reasons = []

    # EPA analysis
    epa_diff = row.get('epa_diff', 0)
    if abs(epa_diff) > 0.05:
        better_team = row['home_team'] if epa_diff > 0 else row['away_team']
        worse_team = row['away_team'] if epa_diff > 0 else row['home_team']
        reasons.append(f"{better_team} EPA +{abs(epa_diff):.2f} better than {worse_team}")

    # RB efficiency
    rb_eff_diff = row.get('diff_rb_efficiency_roll', 0)
    if abs(rb_eff_diff) > 0.3:
        better = row['home_team'] if rb_eff_diff > 0 else row['away_team']
        reasons.append(f"{better} rushing efficiency advantage")

    # Stacked box
    stacked_diff = row.get('diff_rb_stacked_box_pct_roll', 0)
    if abs(stacked_diff) > 5:
        better = row['home_team'] if stacked_diff < 0 else row['away_team']
        reasons.append(f"{better} faces fewer stacked boxes")

    # Confidence
    conf_pct = max(prob, 1-prob) * 100
    if conf_pct > 70:
        reasons.append(f"Model very confident ({conf_pct:.0f}%)")
    elif conf_pct > 65:
        reasons.append(f"Model confident ({conf_pct:.0f}%)")

    # Home field
    if prob > 0.5:
        reasons.append("Home field advantage")

    if not reasons:
        reasons.append("Multiple small edges combine")

    return reasons


def predict_week(season: int, week: int):
    """Generate picks for a specific week."""
    print(f"\n{'='*60}")
    print(f"GENERATING PICKS: {season} WEEK {week}")
    print(f"{'='*60}\n")

    pbp, ngs_rushing, nfl = load_model_and_data()
    if pbp is None:
        return []

    games, team_epa, rb_stats = compute_features(pbp, ngs_rushing)
    df = build_feature_matrix(games, team_epa, rb_stats)

    # Filter to completed games for training
    features = ['epa_diff', 'diff_rb_efficiency_roll', 'diff_rb_stacked_box_pct_roll',
                'diff_rb_time_to_los_roll', 'diff_rb_ypc_roll']

    # Train on all prior data
    train = df[(df['season'] < season) | ((df['season'] == season) & (df['week'] < week))]
    train = train[train['week'] >= 4].dropna(subset=['home_win'])

    if len(train) < 100:
        print("Not enough training data")
        return []

    X_train = train[features].fillna(0)
    y_train = train['home_win']

    scaler = StandardScaler()
    X_train_s = scaler.fit_transform(X_train)

    model = GradientBoostingClassifier(n_estimators=100, max_depth=3, learning_rate=0.1, random_state=42)
    model.fit(X_train_s, y_train)

    # Get this week's games
    week_games = df[(df['season'] == season) & (df['week'] == week)]

    if len(week_games) == 0:
        print(f"No games found for {season} Week {week}")
        return []

    picks = []

    for _, row in week_games.iterrows():
        X_game = pd.DataFrame([row[features].fillna(0).values], columns=features)
        X_game_s = scaler.transform(X_game)

        prob = model.predict_proba(X_game_s)[0, 1]
        confidence = max(prob, 1-prob)

        # Determine pick
        if prob > 0.5:
            pick_team = row['home_team']
            pick_str = f"{row['home_team']} ML"
        else:
            pick_team = row['away_team']
            pick_str = f"{row['away_team']} ML"

        # Determine signal
        if confidence >= 0.68:
            signal = "🟢 STRONG"
        elif confidence >= 0.62:
            signal = "🟡 LEAN"
        else:
            signal = "⚫ SKIP"

        # Generate reasoning
        reasons = generate_reasoning(row, prob)

        pick = Pick(
            game_id=row['game_id'],
            week=int(row['week']),
            season=int(row['season']),
            home_team=row['home_team'],
            away_team=row['away_team'],
            pick=pick_str,
            pick_team=pick_team,
            confidence=round(confidence * 100, 1),
            signal=signal,
            reasons=reasons,
            model_version="v4-rb-ngs",
            created_at=datetime.now().isoformat(),
        )
        picks.append(pick)

    return picks


def display_picks(picks: List[Pick]):
    """Display picks in simple format."""
    # Sort by confidence
    picks = sorted(picks, key=lambda p: p.confidence, reverse=True)

    strong = [p for p in picks if "STRONG" in p.signal]
    lean = [p for p in picks if "LEAN" in p.signal]
    skip = [p for p in picks if "SKIP" in p.signal]

    if strong:
        print("\n" + "="*50)
        print("🟢 STRONG PICKS (Bet These)")
        print("="*50)
        for p in strong:
            print(f"\n  {p.pick}")
            print(f"  {p.away_team} @ {p.home_team}")
            print(f"  Confidence: {p.confidence}%")
            print(f"  Why:")
            for r in p.reasons:
                print(f"    • {r}")

    if lean:
        print("\n" + "-"*50)
        print("🟡 LEAN (Consider These)")
        print("-"*50)
        for p in lean:
            print(f"\n  {p.pick} ({p.confidence}%)")
            print(f"  {p.away_team} @ {p.home_team}")

    print(f"\n⚫ SKIP: {len(skip)} games (confidence < 62%)")

    print(f"\n{'='*50}")
    print(f"SUMMARY: {len(strong)} strong, {len(lean)} lean, {len(skip)} skip")
    print(f"{'='*50}\n")


def save_picks(picks: List[Pick]):
    """Append picks to history file."""
    history = []
    if PICKS_FILE.exists():
        with open(PICKS_FILE) as f:
            history = json.load(f)

    for p in picks:
        history.append(asdict(p))

    with open(PICKS_FILE, 'w') as f:
        json.dump(history, f, indent=2)

    print(f"Saved {len(picks)} picks to {PICKS_FILE}")


def main():
    import argparse
    parser = argparse.ArgumentParser(description="NFL Picks Generator")
    parser.add_argument('--week', type=int, help='Week number')
    parser.add_argument('--season', type=int, default=2026, help='Season year')
    parser.add_argument('--settle', action='store_true', help='Record outcomes')
    parser.add_argument('--history', action='store_true', help='View history')
    parser.add_argument('--save', action='store_true', help='Save picks to history')
    args = parser.parse_args()

    if args.history:
        if PICKS_FILE.exists():
            with open(PICKS_FILE) as f:
                history = json.load(f)
            wins = sum(1 for p in history if p.get('outcome') == 'W')
            losses = sum(1 for p in history if p.get('outcome') == 'L')
            pending = sum(1 for p in history if p.get('outcome') is None)
            print(f"\nHistory: {wins}W - {losses}L ({pending} pending)")
            if wins + losses > 0:
                print(f"Win Rate: {wins/(wins+losses)*100:.1f}%")
        else:
            print("No history yet")
        return

    # Default to "current" week (placeholder)
    week = args.week or 1
    season = args.season

    picks = predict_week(season, week)

    if picks:
        display_picks(picks)

        if args.save:
            save_picks(picks)


if __name__ == "__main__":
    main()
