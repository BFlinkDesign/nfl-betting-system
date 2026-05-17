"""Multi-Layer Probability Stacking

Combines multiple probability sources into calibrated final estimates.
This is a key differentiator identified in competitive intelligence.

Layers:
1. Base model probability (XGBoost)
2. Market-implied probability (from odds)
3. Situational edge adjustments
4. Historical regime factors

The stacker learns optimal weights for each source and produces
calibrated final probabilities with uncertainty bounds.

References:
- Ensemble methods in sports betting (academic)
- PlusEV Analytics methodology
- Bayesian model averaging
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.special import expit, logit  # Sigmoid and inverse

logger = logging.getLogger(__name__)


@dataclass
class StackedProbability:
    """Final stacked probability with components."""
    game_id: str
    final_prob: float
    uncertainty: float
    model_prob: float
    market_prob: float
    situational_adj: float
    edge_vs_market: float
    confidence_tier: str
    components: Dict[str, float]


class ProbabilityStacker:
    """
    Combines multiple probability sources into calibrated estimates.

    Uses log-odds space for combination (more stable than raw probs)
    and learns optimal weights from historical performance.
    """

    # Default weights (can be learned from data)
    DEFAULT_WEIGHTS = {
        'model': 0.40,
        'market': 0.45,
        'situational': 0.15,
    }

    # Situational edge magnitudes (from research)
    SITUATIONAL_ADJUSTMENTS = {
        'divisional_underdog': 0.08,      # +8% to underdog
        'home_underdog_division': 0.06,   # +6% to home team
        'rest_advantage_strong': 0.05,    # +5% to rested team
        'rest_advantage_moderate': 0.03,  # +3% to rested team
        'letdown_spot': 0.04,             # +4% to underdog
        'lookahead_spot': 0.03,           # +3% to underdog
        'primetime_home': 0.02,           # +2% to home in primetime
        'weather_dome': 0.02,             # +2% to dome team in cold
    }

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        """
        Initialize stacker.

        Args:
            weights: Custom weights for probability sources
        """
        self.weights = weights or self.DEFAULT_WEIGHTS.copy()
        self._validate_weights()

    def _validate_weights(self):
        """Ensure weights sum to 1."""
        total = sum(self.weights.values())
        if abs(total - 1.0) > 0.001:
            # Normalize
            for k in self.weights:
                self.weights[k] /= total

    def stack_probabilities(
        self,
        game_id: str,
        model_prob: float,
        market_prob: float,
        situational_edges: Optional[List[str]] = None,
        edge_team_is_home: bool = True,
    ) -> StackedProbability:
        """
        Stack probabilities from multiple sources.

        Args:
            game_id: Game identifier
            model_prob: Model's home win probability
            market_prob: Market-implied home win probability
            situational_edges: List of detected edge types
            edge_team_is_home: Whether edge favors home team

        Returns:
            StackedProbability with final estimate
        """
        # Calculate situational adjustment
        sit_adj = 0.0
        if situational_edges:
            for edge in situational_edges:
                adj = self.SITUATIONAL_ADJUSTMENTS.get(edge, 0.0)
                if edge_team_is_home:
                    sit_adj += adj
                else:
                    sit_adj -= adj

        # Clamp situational adjustment
        sit_adj = np.clip(sit_adj, -0.15, 0.15)

        # Convert to log-odds for stable combination
        model_logit = self._safe_logit(model_prob)
        market_logit = self._safe_logit(market_prob)

        # Weighted combination in log-odds space
        combined_logit = (
            self.weights['model'] * model_logit +
            self.weights['market'] * market_logit
        )

        # Add situational adjustment (directly in probability space)
        combined_prob = expit(combined_logit)
        final_prob = np.clip(combined_prob + sit_adj * self.weights['situational'], 0.02, 0.98)

        # Estimate uncertainty from disagreement
        uncertainty = self._estimate_uncertainty(model_prob, market_prob, sit_adj)

        # Edge vs market
        edge_vs_market = final_prob - market_prob

        # Confidence tier
        confidence_tier = self._get_confidence_tier(
            abs(edge_vs_market), uncertainty, bool(situational_edges)
        )

        return StackedProbability(
            game_id=game_id,
            final_prob=final_prob,
            uncertainty=uncertainty,
            model_prob=model_prob,
            market_prob=market_prob,
            situational_adj=sit_adj,
            edge_vs_market=edge_vs_market,
            confidence_tier=confidence_tier,
            components={
                'model_weight': self.weights['model'],
                'market_weight': self.weights['market'],
                'situational_weight': self.weights['situational'],
                'model_logit': model_logit,
                'market_logit': market_logit,
            }
        )

    def _safe_logit(self, p: float) -> float:
        """Logit with clamping to avoid inf."""
        p = np.clip(p, 0.01, 0.99)
        return logit(p)

    def _estimate_uncertainty(
        self,
        model_prob: float,
        market_prob: float,
        sit_adj: float,
    ) -> float:
        """
        Estimate uncertainty from source disagreement.

        Higher disagreement = higher uncertainty.
        """
        # Base uncertainty from model-market disagreement
        disagreement = abs(model_prob - market_prob)

        # Uncertainty increases with disagreement
        base_uncertainty = 0.05 + disagreement * 0.5

        # Situational adjustments add uncertainty
        sit_uncertainty = abs(sit_adj) * 0.3

        return min(base_uncertainty + sit_uncertainty, 0.25)

    def _get_confidence_tier(
        self,
        edge_magnitude: float,
        uncertainty: float,
        has_situational: bool,
    ) -> str:
        """Determine confidence tier."""
        if edge_magnitude < 0.03:
            return 'NO_EDGE'

        if uncertainty > 0.15:
            return 'LOW'

        if edge_magnitude > 0.08 and uncertainty < 0.10:
            if has_situational:
                return 'HIGH'
            else:
                return 'MEDIUM_HIGH'

        if edge_magnitude > 0.05:
            return 'MEDIUM'

        return 'LOW'

    def learn_weights(
        self,
        historical_df: pd.DataFrame,
        model_col: str = 'model_prob',
        market_col: str = 'market_prob',
        result_col: str = 'home_win',
    ) -> Dict[str, float]:
        """
        Learn optimal weights from historical data.

        Uses log-loss minimization to find weights.

        Args:
            historical_df: DataFrame with probabilities and results
            model_col: Column with model probabilities
            market_col: Column with market probabilities
            result_col: Column with actual results (0/1)

        Returns:
            Optimized weights dictionary
        """
        from scipy.optimize import minimize

        def log_loss(weights, model_probs, market_probs, results):
            w_model, w_market = weights
            # Combine in logit space
            combined = w_model * self._safe_logit(model_probs) + w_market * self._safe_logit(market_probs)
            probs = expit(combined)
            probs = np.clip(probs, 1e-7, 1 - 1e-7)
            return -np.mean(results * np.log(probs) + (1 - results) * np.log(1 - probs))

        model_probs = historical_df[model_col].values
        market_probs = historical_df[market_col].values
        results = historical_df[result_col].values

        # Optimize
        result = minimize(
            log_loss,
            [0.5, 0.5],
            args=(model_probs, market_probs, results),
            bounds=[(0.1, 0.9), (0.1, 0.9)],
            constraints={'type': 'eq', 'fun': lambda w: w[0] + w[1] - 0.85}  # Leave 15% for situational
        )

        if result.success:
            self.weights['model'] = result.x[0]
            self.weights['market'] = result.x[1]
            self.weights['situational'] = 1 - result.x[0] - result.x[1]
            logger.info(f"Learned weights: {self.weights}")

        return self.weights


def odds_to_probability(american_odds: float) -> float:
    """
    Convert American odds to implied probability.

    Args:
        american_odds: American odds (e.g., -110, +150)

    Returns:
        Implied probability (0-1)
    """
    if american_odds < 0:
        return abs(american_odds) / (abs(american_odds) + 100)
    else:
        return 100 / (american_odds + 100)


def spread_to_probability(spread: float, home_field: float = 2.5) -> float:
    """
    Convert point spread to rough win probability.

    Uses empirical relationship: ~3% per point from 50%.

    Args:
        spread: Point spread (negative = home favorite)
        home_field: Home field advantage points (default 2.5)

    Returns:
        Home win probability
    """
    # Adjust spread for home field
    adjusted_spread = spread - home_field

    # Each point ≈ 3% probability
    prob = 0.50 - adjusted_spread * 0.03

    return np.clip(prob, 0.05, 0.95)


def combine_odds_sources(
    odds_dict: Dict[str, float],
    method: str = 'mean',
) -> float:
    """
    Combine odds from multiple sportsbooks.

    Args:
        odds_dict: Dict of sportsbook -> American odds
        method: 'mean', 'median', 'best' (highest implied prob)

    Returns:
        Combined implied probability
    """
    probs = [odds_to_probability(odds) for odds in odds_dict.values()]

    if method == 'mean':
        return np.mean(probs)
    elif method == 'median':
        return np.median(probs)
    elif method == 'best':
        return max(probs)
    else:
        return np.mean(probs)


def stack_for_week(
    games_df: pd.DataFrame,
    model_probs: np.ndarray,
    stacker: Optional[ProbabilityStacker] = None,
) -> pd.DataFrame:
    """
    Apply probability stacking to a week of games.

    Args:
        games_df: DataFrame with game info
        model_probs: Array of model probabilities
        stacker: ProbabilityStacker instance (uses default if None)

    Returns:
        DataFrame with stacked probability columns added
    """
    if stacker is None:
        stacker = ProbabilityStacker()

    games = games_df.copy()
    games['model_prob'] = model_probs

    # Get market probability from spread
    if 'spread_line' in games.columns:
        games['market_prob'] = games['spread_line'].apply(spread_to_probability)
    else:
        games['market_prob'] = 0.5

    # Stack each game
    stacked_results = []

    for idx, row in games.iterrows():
        # Gather situational edges if available
        edges = []
        if row.get('edges_detected', 0) > 0:
            edge_types = row.get('edge_types', '')
            if edge_types:
                edges = edge_types.split(',')

        # Determine if edge favors home
        edge_team = row.get('edge_team', None)
        edge_is_home = edge_team == row['home_team'] if edge_team else True

        result = stacker.stack_probabilities(
            game_id=row.get('game_id', f'game_{idx}'),
            model_prob=row['model_prob'],
            market_prob=row['market_prob'],
            situational_edges=edges if edges else None,
            edge_team_is_home=edge_is_home,
        )

        stacked_results.append({
            'game_id': row.get('game_id', f'game_{idx}'),
            'stacked_prob': result.final_prob,
            'stacked_uncertainty': result.uncertainty,
            'stacked_edge': result.edge_vs_market,
            'stacked_confidence': result.confidence_tier,
            'prob_components': str(result.components),
        })

    stacked_df = pd.DataFrame(stacked_results)
    return games.merge(stacked_df, on='game_id', how='left')


def print_stacked_analysis(result: StackedProbability, home_team: str, away_team: str):
    """Print stacked probability analysis."""
    print(f"\n{'='*60}")
    print(f"STACKED PROBABILITY: {away_team} @ {home_team}")
    print(f"{'='*60}")

    print(f"\nComponent Probabilities (Home Win):")
    print(f"  Model:   {result.model_prob:.1%}")
    print(f"  Market:  {result.market_prob:.1%}")
    print(f"  Sit Adj: {result.situational_adj:+.1%}")

    print(f"\nWeights:")
    print(f"  Model:   {result.components['model_weight']:.0%}")
    print(f"  Market:  {result.components['market_weight']:.0%}")
    print(f"  Situational: {result.components['situational_weight']:.0%}")

    print(f"\nFinal Stacked Probability:")
    print(f"  >>> {result.final_prob:.1%} (±{result.uncertainty:.1%})")

    print(f"\nEdge vs Market: {result.edge_vs_market:+.1%}")
    print(f"Confidence Tier: {result.confidence_tier}")

    if result.edge_vs_market > 0.05:
        print(f"\n>>> POTENTIAL VALUE: Model + situational favors HOME ({home_team})")
    elif result.edge_vs_market < -0.05:
        print(f"\n>>> POTENTIAL VALUE: Model + situational favors AWAY ({away_team})")
    else:
        print(f"\n>>> NO CLEAR EDGE: Stay away or reduce position size")

    print(f"{'='*60}")
