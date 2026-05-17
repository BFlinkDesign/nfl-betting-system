"""NFL Data Acquisition - Direct from nflverse

Downloads real NFL data for predictions. No mock data, no placeholders.
Uses nflverse (the industry standard for NFL analytics).

Data sources:
- nflverse schedules: Game info, scores, weather, betting lines
- nflverse play-by-play: EPA, success rate, CPOE (for team stats)
- nflverse rosters: Player info for injury impact
"""

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)


def download_schedules(seasons: List[int], save_path: Optional[str] = None) -> pd.DataFrame:
    """
    Download NFL schedules with betting lines and weather.

    Args:
        seasons: List of seasons to download
        save_path: Optional path to save parquet

    Returns:
        DataFrame with schedule data
    """
    logger.info(f"Downloading schedules for {seasons}...")

    try:
        import nfl_data_py as nfl
        schedules = nfl.import_schedules(seasons)
        logger.info(f"Downloaded {len(schedules)} games")
    except ImportError:
        logger.error("nfl_data_py not installed. Run: pip install nfl_data_py")
        raise

    if save_path:
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        schedules.to_parquet(save_path, index=False)
        logger.info(f"Saved to {save_path}")

    return schedules


def download_pbp(seasons: List[int], save_path: Optional[str] = None) -> pd.DataFrame:
    """
    Download play-by-play data with EPA and advanced stats.

    Args:
        seasons: List of seasons
        save_path: Optional save path

    Returns:
        DataFrame with play-by-play
    """
    logger.info(f"Downloading play-by-play for {seasons}...")

    try:
        import nfl_data_py as nfl
        pbp = nfl.import_pbp_data(seasons)
        logger.info(f"Downloaded {len(pbp)} plays")
    except ImportError:
        logger.error("nfl_data_py not installed")
        raise

    if save_path:
        Path(save_path).parent.mkdir(parents=True, exist_ok=True)
        pbp.to_parquet(save_path, index=False)
        logger.info(f"Saved to {save_path}")

    return pbp


def calculate_team_stats(pbp_df: pd.DataFrame, n_games: int = 5) -> pd.DataFrame:
    """
    Calculate rolling team statistics from play-by-play.

    Creates EPA, success rate, and explosive play metrics.

    Args:
        pbp_df: Play-by-play DataFrame
        n_games: Rolling window size

    Returns:
        DataFrame with team stats per game
    """
    logger.info("Calculating team stats from play-by-play...")

    # Filter to regular plays (exclude special teams, penalties)
    plays = pbp_df[
        (pbp_df['play_type'].isin(['pass', 'run'])) &
        (pbp_df['epa'].notna())
    ].copy()

    # Group by game and team
    game_stats = []

    for game_id in plays['game_id'].unique():
        game_plays = plays[plays['game_id'] == game_id]

        for team in game_plays['posteam'].dropna().unique():
            team_plays = game_plays[game_plays['posteam'] == team]

            if len(team_plays) == 0:
                continue

            # Offensive stats
            off_stats = {
                'game_id': game_id,
                'team': team,
                'epa_per_play': team_plays['epa'].mean(),
                'success_rate': (team_plays['epa'] > 0).mean(),
                'explosive_rate': (team_plays['epa'] > 1.5).mean(),
                'pass_rate': (team_plays['play_type'] == 'pass').mean(),
                'total_plays': len(team_plays),
            }

            # Defensive stats (when team is on defense)
            def_plays = game_plays[game_plays['defteam'] == team]
            if len(def_plays) > 0:
                off_stats['def_epa_per_play'] = def_plays['epa'].mean()
                off_stats['def_success_rate'] = (def_plays['epa'] > 0).mean()
            else:
                off_stats['def_epa_per_play'] = 0
                off_stats['def_success_rate'] = 0.5

            game_stats.append(off_stats)

    stats_df = pd.DataFrame(game_stats)
    logger.info(f"Calculated stats for {len(stats_df)} team-games")

    return stats_df


def prepare_features(
    schedules_df: pd.DataFrame,
    team_stats_df: Optional[pd.DataFrame] = None,
    n_rolling: int = 5
) -> pd.DataFrame:
    """
    Prepare features for prediction.

    Args:
        schedules_df: Schedule data
        team_stats_df: Team stats from PBP
        n_rolling: Rolling window for averages

    Returns:
        DataFrame with features ready for modeling
    """
    logger.info("Preparing features...")

    df = schedules_df.copy()

    # Filter to completed games for training
    df = df[df['home_score'].notna()].copy()

    # Create target
    df['target'] = (df['home_score'] > df['away_score']).astype(int)

    # Basic features that are always available
    features = []

    # 1. Home field advantage (baseline)
    df['home_field'] = 1

    # 2. Rest days
    df = df.sort_values(['home_team', 'gameday'])
    df['home_rest_days'] = df.groupby('home_team')['gameday'].diff().dt.days.fillna(7)

    df = df.sort_values(['away_team', 'gameday'])
    df['away_rest_days'] = df.groupby('away_team')['gameday'].diff().dt.days.fillna(7)

    df['rest_advantage'] = df['home_rest_days'] - df['away_rest_days']

    # 3. Division game flag
    df['div_game'] = df.apply(
        lambda x: _same_division(x['home_team'], x['away_team']),
        axis=1
    ).astype(int)

    # 4. Week of season (early vs late)
    df['week_normalized'] = df['week'] / 18

    # 5. Prime time flag
    df['is_prime_time'] = df['gametime'].apply(
        lambda x: 1 if pd.notna(x) and (
            '20:' in str(x) or '21:' in str(x) or '19:' in str(x)
        ) else 0
    )

    # 6. Weather features (if available)
    if 'temp' in df.columns:
        df['temp_normalized'] = (df['temp'] - 50) / 30  # Center around 50F
        df['is_cold'] = (df['temp'] < 35).astype(int)
        df['is_dome'] = (df['roof'] == 'dome').astype(int) if 'roof' in df.columns else 0
    else:
        df['temp_normalized'] = 0
        df['is_cold'] = 0
        df['is_dome'] = 0

    if 'wind' in df.columns:
        df['wind_normalized'] = df['wind'].fillna(0) / 20
        df['high_wind'] = (df['wind'] > 15).astype(int)
    else:
        df['wind_normalized'] = 0
        df['high_wind'] = 0

    # 7. Add team stats if available
    if team_stats_df is not None:
        df = _merge_team_stats(df, team_stats_df, n_rolling)

    # 8. Spread features (for edge detection, NOT for prediction)
    if 'spread_line' in df.columns:
        df['spread_line'] = df['spread_line'].fillna(0)
        df['is_home_underdog'] = (df['spread_line'] > 0).astype(int)
        df['is_big_favorite'] = (df['spread_line'] < -7).astype(int)
        df['is_close_game'] = (df['spread_line'].abs() <= 3).astype(int)

    logger.info(f"Prepared {len(df)} games with features")

    return df


def _same_division(home: str, away: str) -> bool:
    """Check if teams are in same division."""
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


def _merge_team_stats(
    games_df: pd.DataFrame,
    stats_df: pd.DataFrame,
    n_rolling: int = 5
) -> pd.DataFrame:
    """Merge rolling team stats into games."""

    # Calculate rolling averages per team
    stats_df = stats_df.sort_values(['team', 'game_id'])

    for col in ['epa_per_play', 'success_rate', 'explosive_rate', 'def_epa_per_play']:
        if col in stats_df.columns:
            stats_df[f'{col}_rolling'] = stats_df.groupby('team')[col].transform(
                lambda x: x.rolling(n_rolling, min_periods=1).mean().shift(1)
            )

    # Merge for home team
    home_stats = stats_df[['game_id', 'team', 'epa_per_play_rolling',
                            'success_rate_rolling', 'def_epa_per_play_rolling']].copy()
    home_stats.columns = ['game_id', 'home_team', 'home_epa', 'home_success', 'home_def_epa']
    games_df = games_df.merge(home_stats, on=['game_id', 'home_team'], how='left')

    # Merge for away team
    away_stats = stats_df[['game_id', 'team', 'epa_per_play_rolling',
                            'success_rate_rolling', 'def_epa_per_play_rolling']].copy()
    away_stats.columns = ['game_id', 'away_team', 'away_epa', 'away_success', 'away_def_epa']
    games_df = games_df.merge(away_stats, on=['game_id', 'away_team'], how='left')

    # Fill NAs with league average
    for col in ['home_epa', 'away_epa', 'home_def_epa', 'away_def_epa']:
        if col in games_df.columns:
            games_df[col] = games_df[col].fillna(0)

    for col in ['home_success', 'away_success']:
        if col in games_df.columns:
            games_df[col] = games_df[col].fillna(0.45)

    # Create differentials
    games_df['epa_diff'] = games_df['home_epa'] - games_df['away_epa']
    games_df['success_diff'] = games_df['home_success'] - games_df['away_success']

    return games_df


def get_current_week_games() -> pd.DataFrame:
    """
    Get games for current NFL week.

    Returns:
        DataFrame with upcoming games
    """
    import nfl_data_py as nfl

    # Get current season
    current_year = datetime.now().year
    current_month = datetime.now().month

    # NFL season runs Sep-Feb
    if current_month < 3:
        season = current_year - 1
    elif current_month >= 9:
        season = current_year
    else:
        season = current_year  # Offseason, use upcoming

    # Download schedule
    schedule = nfl.import_schedules([season])

    # Filter to upcoming games (no score yet)
    upcoming = schedule[schedule['home_score'].isna()].copy()

    # Get the minimum week with games
    if len(upcoming) > 0:
        current_week = upcoming['week'].min()
        upcoming = upcoming[upcoming['week'] == current_week]

    logger.info(f"Found {len(upcoming)} games for week {current_week} of {season}")

    return upcoming


def setup_data_directory():
    """Create data directory structure."""
    dirs = [
        'data/raw',
        'data/processed',
        'data/predictions',
        'models',
    ]

    for d in dirs:
        Path(d).mkdir(parents=True, exist_ok=True)
        logger.info(f"Created {d}")
