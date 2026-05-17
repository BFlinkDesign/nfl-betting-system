"""Advanced feature engineering based on peer-reviewed research.

Implements:
- Multi-window rolling averages (3, 5, 8 games) per research recommendations
- Opponent-adjusted metrics with ridge regularization
- Success rate and efficiency metrics
- Market-based features

Based on:
- Open Source Football methodology
- nflfastR advanced analytics
- Brad Congelio's NFL Analytics with R
"""

import logging
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge

try:
    from .base import FeatureBuilder
except ImportError:
    from src.features.base import FeatureBuilder

logger = logging.getLogger(__name__)


class AdvancedFeatures(FeatureBuilder):
    """
    Advanced features following state-of-the-art research.

    Key features:
    - Multi-window rolling stats (3, 5, 8 game windows)
    - Opponent-adjusted metrics (ridge regression)
    - Efficiency metrics (success rate, red zone, explosiveness)
    """

    def __init__(self, pbp_data: Optional[pd.DataFrame] = None):
        """
        Initialize with optional play-by-play data.

        Args:
            pbp_data: Play-by-play data for advanced stat calculation
        """
        self.pbp_data = pbp_data
        self.team_stats: Optional[pd.DataFrame] = None
        self.opponent_adjustments: Dict[str, float] = {}

    def get_feature_names(self) -> List[str]:
        """Return list of feature names created by this builder."""
        features = []

        # Multi-window rolling features
        metrics = ['points', 'yards', 'epa']
        windows = [3, 5, 8]
        for metric in metrics:
            for window in windows:
                features.append(f'home_{metric}_last{window}')
                features.append(f'away_{metric}_last{window}')

        # Efficiency metrics
        efficiency_features = [
            'home_success_rate', 'away_success_rate',
            'home_explosive_play_rate', 'away_explosive_play_rate',
            'home_rz_td_rate', 'away_rz_td_rate',
            'home_third_down_rate', 'away_third_down_rate',
        ]
        features.extend(efficiency_features)

        # Opponent-adjusted
        adj_features = [
            'home_adj_off_epa', 'away_adj_off_epa',
            'home_adj_def_epa', 'away_adj_def_epa',
        ]
        features.extend(adj_features)

        # Differential features
        diff_features = [
            'epa_diff_last3', 'epa_diff_last5', 'epa_diff_last8',
            'success_rate_diff', 'adj_epa_diff',
        ]
        features.extend(diff_features)

        return features

    def build(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Build all advanced features.

        Args:
            df: Schedule dataframe with basic columns

        Returns:
            DataFrame with advanced features added
        """
        df = df.copy()

        # Calculate team-level statistics if not provided
        if self.team_stats is None:
            self._calculate_team_stats(df)

        # Add multi-window rolling features
        df = self._add_rolling_features(df)

        # Add efficiency metrics
        df = self._add_efficiency_features(df)

        # Add opponent-adjusted features
        df = self._add_opponent_adjusted_features(df)

        # Add differential features
        df = self._add_differential_features(df)

        logger.info(f"Added {len(self.get_feature_names())} advanced features")

        return df

    def _calculate_team_stats(self, df: pd.DataFrame) -> None:
        """Calculate team-level statistics from schedule data."""
        # Group by team and calculate rolling stats
        team_stats = []

        for team in df['home_team'].unique():
            # Get all games for this team (home and away)
            home_games = df[df['home_team'] == team].copy()
            away_games = df[df['away_team'] == team].copy()

            # Standardize columns
            home_games['team'] = team
            home_games['is_home'] = True
            home_games['team_score'] = home_games.get('home_score', 0)
            home_games['opp_score'] = home_games.get('away_score', 0)

            away_games['team'] = team
            away_games['is_home'] = False
            away_games['team_score'] = away_games.get('away_score', 0)
            away_games['opp_score'] = away_games.get('home_score', 0)

            team_games = pd.concat([home_games, away_games])
            team_games = team_games.sort_values('gameday')

            team_stats.append(team_games)

        if team_stats:
            self.team_stats = pd.concat(team_stats)

    def _add_rolling_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add multi-window rolling average features."""
        windows = [3, 5, 8]
        metrics = ['points', 'yards', 'epa']

        for window in windows:
            for metric in metrics:
                home_col = f'home_{metric}_last{window}'
                away_col = f'away_{metric}_last{window}'

                # Initialize with defaults
                df[home_col] = 0.0
                df[away_col] = 0.0

                # Calculate rolling stats per team
                for idx, row in df.iterrows():
                    home_team = row['home_team']
                    away_team = row['away_team']
                    gameday = row['gameday']

                    # Get prior games for home team
                    home_prior = self._get_prior_games(home_team, gameday, window)
                    if len(home_prior) > 0:
                        if metric == 'points':
                            df.loc[idx, home_col] = home_prior['team_score'].mean()
                        elif metric == 'yards':
                            df.loc[idx, home_col] = home_prior.get('total_yards', pd.Series([300])).mean()
                        elif metric == 'epa':
                            df.loc[idx, home_col] = home_prior.get('epa_per_play', pd.Series([0])).mean()

                    # Get prior games for away team
                    away_prior = self._get_prior_games(away_team, gameday, window)
                    if len(away_prior) > 0:
                        if metric == 'points':
                            df.loc[idx, away_col] = away_prior['team_score'].mean()
                        elif metric == 'yards':
                            df.loc[idx, away_col] = away_prior.get('total_yards', pd.Series([300])).mean()
                        elif metric == 'epa':
                            df.loc[idx, away_col] = away_prior.get('epa_per_play', pd.Series([0])).mean()

        return df

    def _get_prior_games(
        self, team: str, gameday: pd.Timestamp, n_games: int
    ) -> pd.DataFrame:
        """Get n prior games for a team before gameday."""
        if self.team_stats is None:
            return pd.DataFrame()

        team_games = self.team_stats[self.team_stats['team'] == team]
        prior = team_games[team_games['gameday'] < gameday]

        return prior.tail(n_games)

    def _add_efficiency_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add efficiency-based features."""
        # Success rate: % of plays gaining 40%+ of yards needed
        df['home_success_rate'] = 0.45  # Default league average
        df['away_success_rate'] = 0.45

        # Explosive play rate: % of plays gaining 20+ yards
        df['home_explosive_play_rate'] = 0.08
        df['away_explosive_play_rate'] = 0.08

        # Red zone TD rate
        df['home_rz_td_rate'] = 0.55
        df['away_rz_td_rate'] = 0.55

        # Third down conversion rate
        df['home_third_down_rate'] = 0.40
        df['away_third_down_rate'] = 0.40

        # Calculate from play-by-play if available
        if self.pbp_data is not None:
            df = self._calculate_efficiency_from_pbp(df)

        return df

    def _calculate_efficiency_from_pbp(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate efficiency metrics from play-by-play data."""
        pbp = self.pbp_data

        # Group PBP by game and team
        for idx, row in df.iterrows():
            game_id = row.get('game_id')
            if game_id is None:
                continue

            game_pbp = pbp[pbp['game_id'] == game_id] if 'game_id' in pbp.columns else pd.DataFrame()

            if len(game_pbp) == 0:
                continue

            home_team = row['home_team']
            away_team = row['away_team']

            # Calculate success rate
            for team, prefix in [(home_team, 'home'), (away_team, 'away')]:
                team_plays = game_pbp[game_pbp.get('posteam', '') == team]

                if len(team_plays) > 0:
                    # Success = gaining required yards
                    if 'success' in team_plays.columns:
                        df.loc[idx, f'{prefix}_success_rate'] = team_plays['success'].mean()

                    # Explosive plays
                    if 'yards_gained' in team_plays.columns:
                        explosive = (team_plays['yards_gained'] >= 20).mean()
                        df.loc[idx, f'{prefix}_explosive_play_rate'] = explosive

        return df

    def _add_opponent_adjusted_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Add opponent-adjusted metrics using ridge regression.

        Adjusts raw stats for opponent strength to get true team ability.
        """
        # Initialize with raw values or defaults
        df['home_adj_off_epa'] = df.get('home_epa_last5', 0.0)
        df['away_adj_off_epa'] = df.get('away_epa_last5', 0.0)
        df['home_adj_def_epa'] = 0.0
        df['away_adj_def_epa'] = 0.0

        # Calculate opponent adjustments if we have enough data
        if self.team_stats is not None and len(df) >= 32:
            self._calculate_opponent_adjustments(df)
            df = self._apply_opponent_adjustments(df)

        return df

    def _calculate_opponent_adjustments(self, df: pd.DataFrame) -> None:
        """Calculate opponent strength adjustments using ridge regression."""
        # Create team encoding
        teams = list(df['home_team'].unique())
        n_teams = len(teams)
        team_to_idx = {team: i for i, team in enumerate(teams)}

        if n_teams < 2:
            return

        # Build design matrix for ridge regression
        # y = team_off + opp_def + home_field + noise
        n_games = len(df)
        X = np.zeros((n_games, n_teams * 2 + 1))  # off + def + home
        y = np.zeros(n_games)

        for i, (_, row) in enumerate(df.iterrows()):
            home_team = row['home_team']
            away_team = row['away_team']

            if home_team in team_to_idx and away_team in team_to_idx:
                # Home team offense
                X[i, team_to_idx[home_team]] = 1
                # Away team defense
                X[i, n_teams + team_to_idx[away_team]] = 1
                # Home field advantage
                X[i, -1] = 1

                # Target: home team points or EPA
                y[i] = row.get('home_score', 0) if 'home_score' in row else 0

        # Fit ridge regression
        try:
            ridge = Ridge(alpha=100.0)  # Strong regularization for small samples
            ridge.fit(X, y)

            # Extract team ratings
            off_ratings = ridge.coef_[:n_teams]
            def_ratings = ridge.coef_[n_teams:n_teams*2]

            for team, idx in team_to_idx.items():
                self.opponent_adjustments[f'{team}_off'] = off_ratings[idx]
                self.opponent_adjustments[f'{team}_def'] = def_ratings[idx]

            logger.info("Calculated opponent adjustments for {} teams".format(n_teams))

        except Exception as e:
            logger.warning(f"Could not calculate opponent adjustments: {e}")

    def _apply_opponent_adjustments(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply opponent adjustments to features."""
        for idx, row in df.iterrows():
            home_team = row['home_team']
            away_team = row['away_team']

            # Home adjusted offense = raw + opponent def adjustment
            home_off_adj = self.opponent_adjustments.get(f'{home_team}_off', 0)
            away_def_adj = self.opponent_adjustments.get(f'{away_team}_def', 0)
            df.loc[idx, 'home_adj_off_epa'] = home_off_adj - away_def_adj

            # Away adjusted offense
            away_off_adj = self.opponent_adjustments.get(f'{away_team}_off', 0)
            home_def_adj = self.opponent_adjustments.get(f'{home_team}_def', 0)
            df.loc[idx, 'away_adj_off_epa'] = away_off_adj - home_def_adj

            # Defensive adjustments
            df.loc[idx, 'home_adj_def_epa'] = home_def_adj
            df.loc[idx, 'away_adj_def_epa'] = away_def_adj

        return df

    def _add_differential_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add differential features (home - away)."""
        # EPA differentials by window
        for window in [3, 5, 8]:
            home_col = f'home_epa_last{window}'
            away_col = f'away_epa_last{window}'
            diff_col = f'epa_diff_last{window}'

            if home_col in df.columns and away_col in df.columns:
                df[diff_col] = df[home_col] - df[away_col]
            else:
                df[diff_col] = 0.0

        # Success rate differential
        df['success_rate_diff'] = df['home_success_rate'] - df['away_success_rate']

        # Adjusted EPA differential
        df['adj_epa_diff'] = df['home_adj_off_epa'] - df['away_adj_off_epa']

        return df


class MarketFeatures(FeatureBuilder):
    """
    Market-based features for edge detection.

    Requires real-time odds data integration.
    """

    def __init__(self):
        self.odds_history: Dict[str, List] = {}

    def get_feature_names(self) -> List[str]:
        return [
            'opening_spread',
            'current_spread',
            'spread_movement',
            'line_direction',
            'steam_move_flag',
            'reverse_line_flag',
            'consensus_pct',
            'sharp_indicator',
        ]

    def build(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add market-based features."""
        df = df.copy()

        # Initialize with defaults (requires odds API for real values)
        df['opening_spread'] = df.get('spread_line', 0.0)
        df['current_spread'] = df.get('spread_line', 0.0)
        df['spread_movement'] = 0.0
        df['line_direction'] = 0  # -1, 0, 1
        df['steam_move_flag'] = 0
        df['reverse_line_flag'] = 0
        df['consensus_pct'] = 50.0
        df['sharp_indicator'] = 0.0

        logger.info("Added market features (requires odds API for live values)")

        return df
