"""Parlay & SGP Builder

Generates parlays and same-game parlays from model outputs.
For FUN beer money bets - parlays are high variance but entertaining.

Types:
1. Multi-game parlays (2-4 legs across different games)
2. Same-Game Parlays (SGP) - correlated props within one game
3. Teaser parlays (adjusted spreads)

Key principle: Only parlay picks where we have identified edge.
Don't parlay random games just for juice.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class ParlayLeg:
    """Single leg of a parlay."""
    game_id: str
    game: str  # "KC @ BUF"
    pick: str  # "KC +3"
    odds: int  # American odds (-110)
    prob: float  # Our estimated probability
    edge: float  # Edge vs market
    leg_type: str  # spread, moneyline, total, prop
    confidence: str  # high, medium, low


@dataclass
class Parlay:
    """Complete parlay with all legs."""
    parlay_id: str
    legs: List[ParlayLeg]
    combined_odds: int
    implied_prob: float  # Market implied
    model_prob: float  # Our estimated
    expected_value: float
    parlay_type: str  # standard, sgp, teaser
    risk_level: str  # conservative, moderate, aggressive
    recommended_units: float


class ParlayBuilder:
    """
    Builds intelligent parlays from model picks.

    Rules:
    - Only include legs with positive edge
    - Limit to 2-4 legs (variance management)
    - Avoid correlated legs in multi-game parlays
    - SGPs: leverage correlation intentionally
    """

    # Correlation adjustments for SGP legs
    SGP_CORRELATIONS = {
        ('spread', 'total_over'): 0.15,   # Favorites covering often means more points
        ('spread', 'total_under'): -0.10,
        ('moneyline', 'total_over'): 0.20,
        ('pass_yards_over', 'team_total_over'): 0.35,
        ('rush_yards_over', 'team_spread'): 0.20,
    }

    def __init__(self, min_edge: float = 0.03, max_legs: int = 4):
        """
        Initialize builder.

        Args:
            min_edge: Minimum edge required per leg
            max_legs: Maximum legs per parlay
        """
        self.min_edge = min_edge
        self.max_legs = max_legs

    def build_best_parlay(
        self,
        picks_df: pd.DataFrame,
        num_legs: int = 3,
        parlay_type: str = 'standard',
    ) -> Optional[Parlay]:
        """
        Build the best parlay from available picks.

        Args:
            picks_df: DataFrame with picks and edges
            num_legs: Target number of legs
            parlay_type: 'standard', 'conservative', 'aggressive'

        Returns:
            Best Parlay or None if insufficient edges
        """
        # Filter to positive edge picks
        edge_col = 'total_edge' if 'total_edge' in picks_df.columns else 'edge_vs_market'
        if edge_col not in picks_df.columns:
            logger.warning("No edge column found in picks")
            return None

        positive_edge = picks_df[picks_df[edge_col] > self.min_edge].copy()

        if len(positive_edge) < 2:
            logger.info("Not enough positive edge picks for parlay")
            return None

        # Sort by edge (best first)
        positive_edge = positive_edge.sort_values(edge_col, ascending=False)

        # Select top N non-correlated legs
        selected = positive_edge.head(min(num_legs, len(positive_edge)))

        legs = []
        for _, row in selected.iterrows():
            leg = ParlayLeg(
                game_id=row.get('game_id', ''),
                game=f"{row['away_team']} @ {row['home_team']}",
                pick=self._format_pick(row),
                odds=int(row.get('spread_odds', -110)),
                prob=row.get('model_home_prob', 0.5) if row.get('model_home_prob', 0.5) > 0.5 else 1 - row.get('model_home_prob', 0.5),
                edge=row[edge_col],
                leg_type='spread',
                confidence=self._get_confidence(row),
            )
            legs.append(leg)

        if len(legs) < 2:
            return None

        return self._create_parlay(legs, 'standard')

    def build_conservative_parlay(self, picks_df: pd.DataFrame) -> Optional[Parlay]:
        """Build a 2-leg parlay with highest confidence picks."""
        return self.build_best_parlay(picks_df, num_legs=2, parlay_type='conservative')

    def build_aggressive_parlay(self, picks_df: pd.DataFrame) -> Optional[Parlay]:
        """Build a 4-leg parlay for bigger payout."""
        return self.build_best_parlay(picks_df, num_legs=4, parlay_type='aggressive')

    def build_moneyline_parlay(
        self,
        picks_df: pd.DataFrame,
        favorite_only: bool = True,
    ) -> Optional[Parlay]:
        """
        Build moneyline parlay (typically favorites).

        Lower odds per leg but higher hit rate.
        """
        # Filter to strong favorites (>60% model prob)
        prob_col = 'model_home_prob'
        if prob_col not in picks_df.columns:
            return None

        # Get favorites
        picks = picks_df.copy()
        picks['favorite_prob'] = picks[prob_col].apply(lambda x: max(x, 1-x))
        picks['favorite_team'] = picks.apply(
            lambda r: r['home_team'] if r[prob_col] > 0.5 else r['away_team'],
            axis=1
        )

        if favorite_only:
            strong_faves = picks[picks['favorite_prob'] > 0.60]
        else:
            strong_faves = picks[picks['favorite_prob'] > 0.55]

        if len(strong_faves) < 2:
            return None

        # Sort by probability
        strong_faves = strong_faves.sort_values('favorite_prob', ascending=False)
        selected = strong_faves.head(3)

        legs = []
        for _, row in selected.iterrows():
            # Estimate ML odds from probability
            prob = row['favorite_prob']
            ml_odds = self._prob_to_ml_odds(prob)

            leg = ParlayLeg(
                game_id=row.get('game_id', ''),
                game=f"{row['away_team']} @ {row['home_team']}",
                pick=f"{row['favorite_team']} ML",
                odds=ml_odds,
                prob=prob,
                edge=prob - self._ml_odds_to_prob(ml_odds),
                leg_type='moneyline',
                confidence='high' if prob > 0.65 else 'medium',
            )
            legs.append(leg)

        return self._create_parlay(legs, 'moneyline')

    def build_underdog_parlay(self, picks_df: pd.DataFrame) -> Optional[Parlay]:
        """
        Build underdog parlay for big payout potential.

        Only includes underdogs where we have edge.
        """
        edge_col = 'total_edge' if 'total_edge' in picks_df.columns else 'edge_vs_market'

        # Find underdog picks with edge
        picks = picks_df.copy()
        if 'spread_line' not in picks.columns:
            return None

        # Home underdogs (positive spread)
        picks['is_home_dog'] = picks['spread_line'] > 0
        picks['dog_has_edge'] = (
            (picks['is_home_dog'] & (picks.get('model_home_prob', 0.5) > 0.45)) |
            (~picks['is_home_dog'] & (picks.get('model_home_prob', 0.5) < 0.55))
        )

        dogs_with_edge = picks[picks['dog_has_edge'] & (picks[edge_col] > 0.02)]

        if len(dogs_with_edge) < 2:
            return None

        selected = dogs_with_edge.head(3)

        legs = []
        for _, row in selected.iterrows():
            is_home_dog = row['spread_line'] > 0
            dog_team = row['home_team'] if is_home_dog else row['away_team']
            spread = row['spread_line'] if is_home_dog else -row['spread_line']

            leg = ParlayLeg(
                game_id=row.get('game_id', ''),
                game=f"{row['away_team']} @ {row['home_team']}",
                pick=f"{dog_team} +{abs(spread):.1f}",
                odds=-110,
                prob=row.get('model_home_prob', 0.5) if is_home_dog else 1 - row.get('model_home_prob', 0.5),
                edge=row[edge_col],
                leg_type='spread',
                confidence='medium',
            )
            legs.append(leg)

        return self._create_parlay(legs, 'underdog')

    def _format_pick(self, row) -> str:
        """Format pick string from row."""
        spread = row.get('spread_line', 0)
        home_prob = row.get('model_home_prob', 0.5)

        if home_prob > 0.5:
            team = row['home_team']
            line = spread
        else:
            team = row['away_team']
            line = -spread

        if line >= 0:
            return f"{team} +{abs(line):.1f}"
        else:
            return f"{team} {line:.1f}"

    def _get_confidence(self, row) -> str:
        """Get confidence level from row."""
        conf_score = row.get('confidence_score', 50)
        if conf_score >= 70:
            return 'high'
        elif conf_score >= 55:
            return 'medium'
        else:
            return 'low'

    def _create_parlay(self, legs: List[ParlayLeg], parlay_type: str) -> Parlay:
        """Create parlay from legs."""
        # Calculate combined odds
        combined_decimal = 1.0
        for leg in legs:
            combined_decimal *= self._american_to_decimal(leg.odds)

        combined_odds = self._decimal_to_american(combined_decimal)
        implied_prob = 1 / combined_decimal

        # Calculate model probability (multiply independent probs)
        model_prob = 1.0
        for leg in legs:
            model_prob *= leg.prob

        # Expected value
        ev = (model_prob * (combined_decimal - 1)) - (1 - model_prob)

        # Risk level
        if len(legs) <= 2:
            risk_level = 'conservative'
        elif len(legs) == 3:
            risk_level = 'moderate'
        else:
            risk_level = 'aggressive'

        # Recommended units (lower for more legs)
        if risk_level == 'conservative':
            units = 1.0
        elif risk_level == 'moderate':
            units = 0.5
        else:
            units = 0.25

        parlay_id = f"parlay_{datetime.now().strftime('%Y%m%d%H%M%S')}_{len(legs)}leg"

        return Parlay(
            parlay_id=parlay_id,
            legs=legs,
            combined_odds=combined_odds,
            implied_prob=implied_prob,
            model_prob=model_prob,
            expected_value=ev,
            parlay_type=parlay_type,
            risk_level=risk_level,
            recommended_units=units,
        )

    def _american_to_decimal(self, odds: int) -> float:
        """Convert American odds to decimal."""
        if odds > 0:
            return 1 + (odds / 100)
        else:
            return 1 + (100 / abs(odds))

    def _decimal_to_american(self, decimal: float) -> int:
        """Convert decimal odds to American."""
        if decimal >= 2.0:
            return int((decimal - 1) * 100)
        else:
            return int(-100 / (decimal - 1))

    def _prob_to_ml_odds(self, prob: float) -> int:
        """Convert probability to moneyline odds."""
        if prob >= 0.5:
            return int(-100 * prob / (1 - prob))
        else:
            return int(100 * (1 - prob) / prob)

    def _ml_odds_to_prob(self, odds: int) -> float:
        """Convert moneyline odds to implied probability."""
        if odds < 0:
            return abs(odds) / (abs(odds) + 100)
        else:
            return 100 / (odds + 100)


def format_parlay(parlay: Parlay) -> str:
    """Format parlay for display."""
    lines = []
    lines.append("")
    lines.append("=" * 50)
    lines.append(f"🎯 {parlay.parlay_type.upper()} PARLAY ({len(parlay.legs)} legs)")
    lines.append("=" * 50)

    for i, leg in enumerate(parlay.legs, 1):
        conf_emoji = {'high': '🟢', 'medium': '🟡', 'low': '⚪'}[leg.confidence]
        lines.append(f"  {i}. {conf_emoji} {leg.game}")
        lines.append(f"     {leg.pick} ({leg.odds:+d})")
        lines.append(f"     Edge: {leg.edge:+.1%} | Model: {leg.prob:.0%}")
        lines.append("")

    lines.append("-" * 50)
    lines.append(f"Combined Odds: {parlay.combined_odds:+d}")
    lines.append(f"Model Win Prob: {parlay.model_prob:.1%}")
    lines.append(f"Expected Value: {parlay.expected_value:+.1%}")
    lines.append(f"Risk Level: {parlay.risk_level.upper()}")
    lines.append(f"Recommended: {parlay.recommended_units}u")
    lines.append("=" * 50)

    return "\n".join(lines)


def generate_all_parlays(picks_df: pd.DataFrame) -> Dict[str, Parlay]:
    """Generate all parlay types from picks."""
    builder = ParlayBuilder()
    parlays = {}

    # Standard 3-leg
    std = builder.build_best_parlay(picks_df, num_legs=3)
    if std:
        parlays['standard'] = std

    # Conservative 2-leg
    cons = builder.build_conservative_parlay(picks_df)
    if cons:
        parlays['conservative'] = cons

    # ML parlay
    ml = builder.build_moneyline_parlay(picks_df)
    if ml:
        parlays['moneyline'] = ml

    # Underdog parlay
    dog = builder.build_underdog_parlay(picks_df)
    if dog:
        parlays['underdog'] = dog

    return parlays


def print_all_parlays(picks_df: pd.DataFrame):
    """Generate and print all parlays."""
    parlays = generate_all_parlays(picks_df)

    if not parlays:
        print("\nNo parlays available (insufficient edges)")
        return

    print("\n" + "=" * 60)
    print("🎰 PARLAY OPTIONS")
    print("=" * 60)

    for name, parlay in parlays.items():
        print(format_parlay(parlay))
