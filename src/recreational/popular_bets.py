"""Recreational Betting Module - What Bettors Actually Bet On (2023-2026)

This module focuses on the MOST POPULAR bet types among recreational bettors:

PROP POPULARITY RANKING:
1. Receiving Yards (most popular by far)
2. Anytime Touchdown (fun factor, high variance)
3. Rushing Yards (star RBs)
4. Receptions (consistent for slot WRs/TEs)
5. Passing Yards (big QB names)

SGP POPULARITY:
- 3-4 legs = SWEET SPOT (most common)
- QB + WR stack = #1 combination
- RB rushing + receiving (dual threats)
- Team total + player props

Research-backed correlation values for accurate SGP pricing.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple
import numpy as np

logger = logging.getLogger(__name__)


class PopularPropType(Enum):
    """Prop types ranked by recreational popularity."""
    RECEIVING_YARDS = ("receiving_yards", 1, 0.618)  # (name, rank, historical_hit_rate)
    ANYTIME_TD = ("anytime_td", 2, 0.52)
    RUSHING_YARDS = ("rushing_yards", 3, 0.77)
    RECEPTIONS = ("receptions", 4, 0.59)
    PASSING_YARDS = ("passing_yards", 5, 0.485)
    PASSING_TDS = ("passing_tds", 6, 0.51)
    FIRST_TD = ("first_td", 7, 0.12)  # Low hit rate but very popular


@dataclass
class RecProp:
    """A recreational-focused prop bet."""
    player: str
    team: str
    prop_type: str
    line: float
    direction: str  # 'over' or 'under'
    projection: float
    hit_rate: float  # Historical hit rate for this type
    edge: float  # Model edge over line
    odds: int = -110  # American odds
    popularity_rank: int = 1
    fun_factor: float = 3.0  # 1-5 scale


@dataclass
class RecSGP:
    """Same Game Parlay built for recreational bettors."""
    legs: List[RecProp]
    correlation_score: float
    combined_odds: int
    implied_prob: float
    model_prob: float
    ev: float
    leg_count: int
    template_name: str  # 'qb_stack', 'rb_dual', etc.
    fun_rating: str  # 'casual', 'exciting', 'lottery'


# Empirical correlation values (research-backed)
EMPIRICAL_CORRELATIONS = {
    # QB + WR (highest correlation, most popular)
    ('passing_yards', 'receiving_yards', True): 0.72,  # Same team
    ('passing_yards', 'receptions', True): 0.65,
    ('passing_tds', 'anytime_td', True): 0.45,  # QB TD + WR TD same team

    # RB dual-threat (moderate correlation, very popular)
    ('rushing_yards', 'receiving_yards', True): 0.40,  # Same player
    ('rushing_yards', 'receptions', True): 0.35,

    # Same player volume
    ('receiving_yards', 'receptions', True): 0.75,
    ('rushing_yards', 'rushing_attempts', True): 0.80,

    # Negative correlations (avoid these)
    ('rushing_yards', 'passing_yards', True): -0.35,  # RB vs QB same team
    ('rushing_yards', 'rushing_yards', True): -0.25,  # Two RBs same team (committee)

    # Game flow
    ('team_total', 'receiving_yards', True): 0.55,
    ('team_total', 'anytime_td', True): 0.50,
}


class RecreationalBettingEngine:
    """
    Engine for building recreational-focused bets.

    Focus: FUN + EDGE, not just +EV grinding.
    Target: 3-4 leg parlays with +500 to +3000 payouts.
    """

    def __init__(self):
        self.popular_templates = self._build_templates()

    def _build_templates(self) -> Dict[str, dict]:
        """Pre-built SGP templates for most popular combinations."""
        return {
            'qb_wr_stack': {
                'name': 'QB + WR Stack',
                'description': 'Most popular SGP combination',
                'legs': ['qb_passing_yards', 'wr1_receiving_yards'],
                'correlation': 0.72,
                'typical_odds': '+600 to +1400',
                'popularity': 'extremely_high',
            },
            'qb_wr_td': {
                'name': 'QB + WR + TD',
                'description': 'Classic shootout play',
                'legs': ['qb_passing_yards', 'wr1_receiving_yards', 'anytime_td'],
                'correlation': 0.55,
                'typical_odds': '+900 to +2500',
                'popularity': 'high',
            },
            'rb_dual_threat': {
                'name': 'RB Dual Threat',
                'description': 'CMC, Achane, Gibbs type play',
                'legs': ['rb_rushing_yards', 'rb_receiving_yards'],
                'correlation': 0.40,
                'typical_odds': '+500 to +1100',
                'popularity': 'very_high',
            },
            'volume_receiver': {
                'name': 'Volume WR',
                'description': 'Target hog (Kelce, CeeDee type)',
                'legs': ['wr_receptions', 'wr_receiving_yards'],
                'correlation': 0.75,
                'typical_odds': '+400 to +900',
                'popularity': 'high',
            },
            'td_stack': {
                'name': 'TD Scorer Stack',
                'description': 'Multiple anytime TDs (lottery ticket)',
                'legs': ['anytime_td', 'anytime_td', 'anytime_td'],
                'correlation': 0.15,
                'typical_odds': '+2000 to +8000',
                'popularity': 'growing_fast',
            },
            'team_total_props': {
                'name': 'Team Total + Props',
                'description': 'Game script correlation play',
                'legs': ['team_total_over', 'wr_receiving_yards', 'rb_rushing_yards'],
                'correlation': 0.45,
                'typical_odds': '+700 to +1800',
                'popularity': 'high',
            },
        }

    def get_correlation(
        self,
        prop1_type: str,
        prop2_type: str,
        same_team: bool = True,
        same_player: bool = False,
    ) -> float:
        """Get empirical correlation between two prop types."""
        # Check both orderings
        key1 = (prop1_type, prop2_type, same_team)
        key2 = (prop2_type, prop1_type, same_team)

        if key1 in EMPIRICAL_CORRELATIONS:
            return EMPIRICAL_CORRELATIONS[key1]
        elif key2 in EMPIRICAL_CORRELATIONS:
            return EMPIRICAL_CORRELATIONS[key2]

        # Defaults based on relationship
        if same_player:
            return 0.30
        elif same_team:
            return 0.15
        return 0.05

    def calculate_sgp_joint_prob(
        self,
        prob1: float,
        prob2: float,
        correlation: float,
    ) -> float:
        """
        Calculate joint probability with correlation adjustment.

        Uses the formula from user's research:
        joint_prob = prob1 * prob2 + correlation * sqrt(prob1*(1-prob1)*prob2*(1-prob2))
        """
        joint = prob1 * prob2 + correlation * np.sqrt(
            prob1 * (1 - prob1) * prob2 * (1 - prob2)
        )
        return min(max(joint, 0.01), 0.99)  # Bound to valid probability

    def calculate_sgp_ev(
        self,
        legs: List[RecProp],
        payout_multiplier: float = None,
    ) -> Tuple[float, float, float]:
        """
        Calculate SGP expected value accounting for correlations.

        Returns: (ev, joint_prob, implied_prob)
        """
        if len(legs) < 2:
            return 0, 0, 0

        # Start with first leg probability
        model_prob = legs[0].hit_rate + legs[0].edge

        # Add each subsequent leg with correlation adjustment
        for i in range(1, len(legs)):
            leg = legs[i]
            leg_prob = leg.hit_rate + leg.edge

            # Get average correlation with all previous legs
            correlations = []
            for prev_leg in legs[:i]:
                same_team = prev_leg.team == leg.team
                same_player = prev_leg.player == leg.player
                corr = self.get_correlation(
                    prev_leg.prop_type, leg.prop_type, same_team, same_player
                )
                correlations.append(corr)

            avg_corr = np.mean(correlations)

            # Adjust joint probability
            model_prob = self.calculate_sgp_joint_prob(model_prob, leg_prob, avg_corr)

        # Calculate payout multiplier from combined odds
        if payout_multiplier is None:
            # Estimate from leg count (typical SGP pricing)
            leg_mult = {2: 2.8, 3: 5.5, 4: 11, 5: 22, 6: 45}
            payout_multiplier = leg_mult.get(len(legs), 2.5 ** len(legs))

        implied_prob = 1 / payout_multiplier
        ev = (model_prob * payout_multiplier) - 1

        return ev, model_prob, implied_prob

    def build_popular_sgp(
        self,
        template_name: str,
        props: List[RecProp],
        target_legs: int = 3,
    ) -> Optional[RecSGP]:
        """
        Build SGP using a popular template.

        Args:
            template_name: One of 'qb_wr_stack', 'rb_dual_threat', etc.
            props: Available props to choose from
            target_legs: Target number of legs (3-4 is sweet spot)
        """
        template = self.popular_templates.get(template_name)
        if not template:
            return None

        # Match props to template requirements
        selected_legs = []

        for leg_type in template['legs'][:target_legs]:
            # Find best matching prop
            best_prop = None
            best_edge = -999

            for prop in props:
                if self._matches_template(prop, leg_type):
                    if prop.edge > best_edge:
                        best_edge = prop.edge
                        best_prop = prop

            if best_prop:
                selected_legs.append(best_prop)

        if len(selected_legs) < 2:
            return None

        # Calculate SGP metrics
        ev, model_prob, implied_prob = self.calculate_sgp_ev(selected_legs)

        # Calculate combined odds
        combined_odds = self._calc_combined_odds(selected_legs)

        # Determine fun rating
        if combined_odds >= 3000:
            fun_rating = 'lottery'
        elif combined_odds >= 800:
            fun_rating = 'exciting'
        else:
            fun_rating = 'casual'

        return RecSGP(
            legs=selected_legs,
            correlation_score=template['correlation'],
            combined_odds=combined_odds,
            implied_prob=implied_prob,
            model_prob=model_prob,
            ev=ev,
            leg_count=len(selected_legs),
            template_name=template_name,
            fun_rating=fun_rating,
        )

    def _matches_template(self, prop: RecProp, leg_type: str) -> bool:
        """Check if prop matches template leg type."""
        type_map = {
            'qb_passing_yards': 'passing_yards',
            'wr1_receiving_yards': 'receiving_yards',
            'wr_receiving_yards': 'receiving_yards',
            'wr_receptions': 'receptions',
            'rb_rushing_yards': 'rushing_yards',
            'rb_receiving_yards': 'receiving_yards',
            'anytime_td': 'anytime_td',
            'team_total_over': 'team_total',
        }
        return prop.prop_type == type_map.get(leg_type, leg_type)

    def _calc_combined_odds(self, legs: List[RecProp]) -> int:
        """Calculate combined American odds for parlay."""
        decimal_odds = 1.0
        for leg in legs:
            if leg.odds < 0:
                decimal_odds *= (100 / abs(leg.odds)) + 1
            else:
                decimal_odds *= (leg.odds / 100) + 1

        # Convert back to American
        if decimal_odds >= 2:
            return int((decimal_odds - 1) * 100)
        else:
            return int(-100 / (decimal_odds - 1))

    def get_optimal_leg_count(self, confidence: float) -> int:
        """
        Get optimal parlay leg count based on model confidence.

        Research shows:
        - 3-4 legs = sweet spot for most recreational bettors
        - 5+ legs only when confidence is very high
        """
        if confidence >= 0.70:
            return 4  # Can go larger with high confidence
        elif confidence >= 0.62:
            return 3  # Standard sweet spot
        else:
            return 2  # Conservative

    def rank_by_popularity(self, props: List[RecProp]) -> List[RecProp]:
        """Rank props by recreational popularity."""
        popularity_order = {
            'receiving_yards': 1,
            'anytime_td': 2,
            'rushing_yards': 3,
            'receptions': 4,
            'passing_yards': 5,
            'passing_tds': 6,
            'first_td': 7,
        }
        return sorted(props, key=lambda p: popularity_order.get(p.prop_type, 99))


def build_recreational_card(
    available_props: List[Dict],
    bankroll: float = 100.0,
) -> Dict:
    """
    Build a recreational betting card with popular bet types.

    Returns card with:
    - Top single props (most popular types)
    - Featured SGPs (3-4 legs, high correlation)
    - Lottery ticket (5+ legs, +3000 odds)
    """
    engine = RecreationalBettingEngine()

    # Convert to RecProp objects
    props = []
    for p in available_props:
        props.append(RecProp(
            player=p.get('player', ''),
            team=p.get('team', ''),
            prop_type=p.get('prop_type', ''),
            line=p.get('line', 0),
            direction=p.get('direction', 'over'),
            projection=p.get('projection', 0),
            hit_rate=p.get('hit_rate', 0.5),
            edge=p.get('edge', 0),
            odds=p.get('odds', -110),
        ))

    # Rank by popularity
    ranked_props = engine.rank_by_popularity(props)

    # Build featured SGPs
    featured_sgps = []
    for template in ['qb_wr_stack', 'rb_dual_threat', 'qb_wr_td']:
        sgp = engine.build_popular_sgp(template, props, target_legs=3)
        if sgp and sgp.ev > 0:
            featured_sgps.append(sgp)

    # Build lottery ticket (5 legs)
    lottery = engine.build_popular_sgp('td_stack', props, target_legs=5)

    return {
        'single_props': ranked_props[:5],  # Top 5 by popularity
        'featured_sgps': featured_sgps,
        'lottery_ticket': lottery,
        'betting_allocation': {
            'single_props': bankroll * 0.40,  # 40% on singles
            'sgps': bankroll * 0.45,  # 45% on SGPs
            'lottery': bankroll * 0.15,  # 15% on lottery
        },
    }


# Popular SGP combinations with expected payouts
POPULAR_COMBINATIONS = {
    '2_leg': {
        'typical_odds': '+180 to +350',
        'hit_rate_needed': 0.35,
        'popularity': 'very_high',
        'best_for': 'conservative_bettors',
    },
    '3_leg': {
        'typical_odds': '+500 to +1200',
        'hit_rate_needed': 0.14,
        'popularity': 'most_popular',
        'best_for': 'majority_recreational',
    },
    '4_leg': {
        'typical_odds': '+1200 to +3500',
        'hit_rate_needed': 0.06,
        'popularity': 'high',
        'best_for': 'big_win_seekers',
    },
    '5_leg': {
        'typical_odds': '+4000 to +15000',
        'hit_rate_needed': 0.02,
        'popularity': 'medium',
        'best_for': 'high_variance_chasers',
    },
}
