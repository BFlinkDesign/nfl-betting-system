"""Player Props & SGP Builder

Generates player prop projections for same-game parlays.
Uses historical averages, matchup factors, and game script projections.

Prop Types:
- Passing: yards, TDs, completions, attempts
- Rushing: yards, attempts, TDs
- Receiving: yards, receptions, TDs
- Anytime TD scorer

For FUN beer money bets. Props have high variance.
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class PropProjection:
    """Single player prop projection."""
    player_name: str
    team: str
    prop_type: str  # pass_yards, rush_yards, receptions, etc.
    line: float  # The book's line
    projection: float  # Our projection
    direction: str  # over, under
    confidence: str  # high, medium, low
    edge: float  # projection vs line difference
    hit_rate: str  # e.g., "Hit 5/6 recent games"
    notes: str


@dataclass
class SGP:
    """Same-Game Parlay with correlated legs."""
    game_id: str
    game: str
    legs: List[PropProjection]
    combined_odds: int
    correlation_bonus: float  # Positive if legs correlate favorably
    risk_level: str


class PlayerPropsEngine:
    """
    Projects player props based on:
    1. Season averages
    2. Recent form (last 3-5 games)
    3. Matchup factors (opponent defense rank)
    4. Game script (projected pace, score)
    5. Weather (outdoor games)
    """

    # Average NFL stats for baseline
    LEAGUE_AVERAGES = {
        'pass_yards': 225,
        'pass_tds': 1.5,
        'completions': 22,
        'rush_yards': 75,
        'rush_attempts': 15,
        'receptions': 5,
        'receiving_yards': 60,
    }

    # Matchup adjustment factors by defense rank
    # Rank 1-8 = tough, 9-16 = average, 17-24 = soft, 25-32 = cake
    DEFENSE_ADJUSTMENTS = {
        'elite': 0.85,    # Ranks 1-5
        'good': 0.92,     # Ranks 6-12
        'average': 1.00,  # Ranks 13-20
        'poor': 1.08,     # Ranks 21-27
        'bad': 1.15,      # Ranks 28-32
    }

    def __init__(self):
        self.projections: List[PropProjection] = []

    def project_qb_props(
        self,
        qb_name: str,
        team: str,
        season_avg_yards: float,
        recent_avg_yards: float,  # Last 3 games
        opp_pass_defense_rank: int,
        projected_game_total: float,
        is_home: bool,
        is_dome: bool,
        book_line: float,
    ) -> PropProjection:
        """
        Project QB passing yards.

        Factors:
        - Season average (40%)
        - Recent form (30%)
        - Matchup (20%)
        - Game environment (10%)
        """
        # Base projection from averages
        base = 0.4 * season_avg_yards + 0.3 * recent_avg_yards + 0.3 * self.LEAGUE_AVERAGES['pass_yards']

        # Matchup adjustment
        defense_tier = self._get_defense_tier(opp_pass_defense_rank)
        matchup_adj = self.DEFENSE_ADJUSTMENTS[defense_tier]

        # Game total adjustment (high total = more passing)
        total_adj = 1 + (projected_game_total - 45) * 0.01

        # Home/dome bonus
        env_adj = 1.0
        if is_home:
            env_adj += 0.02
        if is_dome:
            env_adj += 0.02

        projection = base * matchup_adj * total_adj * env_adj

        # Determine direction and edge
        edge = (projection - book_line) / book_line
        direction = 'over' if projection > book_line else 'under'

        # Confidence based on edge magnitude
        if abs(edge) > 0.08:
            confidence = 'high'
        elif abs(edge) > 0.04:
            confidence = 'medium'
        else:
            confidence = 'low'

        # Hit rate estimation (simplified)
        if direction == 'over' and season_avg_yards > book_line:
            hit_rate = "Season avg above line"
        elif direction == 'under' and season_avg_yards < book_line:
            hit_rate = "Season avg below line"
        else:
            hit_rate = "Mixed recent results"

        return PropProjection(
            player_name=qb_name,
            team=team,
            prop_type='pass_yards',
            line=book_line,
            projection=round(projection, 1),
            direction=direction,
            confidence=confidence,
            edge=edge,
            hit_rate=hit_rate,
            notes=f"vs {defense_tier} pass D (rank {opp_pass_defense_rank})",
        )

    def project_rb_props(
        self,
        rb_name: str,
        team: str,
        season_avg_yards: float,
        recent_avg_yards: float,
        opp_rush_defense_rank: int,
        projected_spread: float,  # Team's spread
        book_line: float,
    ) -> PropProjection:
        """Project RB rushing yards."""
        base = 0.4 * season_avg_yards + 0.3 * recent_avg_yards + 0.3 * self.LEAGUE_AVERAGES['rush_yards']

        # Matchup
        defense_tier = self._get_defense_tier(opp_rush_defense_rank)
        matchup_adj = self.DEFENSE_ADJUSTMENTS[defense_tier]

        # Game script: favorites run more
        script_adj = 1 + (abs(projected_spread) * 0.01 if projected_spread < 0 else -0.02)

        projection = base * matchup_adj * script_adj

        edge = (projection - book_line) / book_line
        direction = 'over' if projection > book_line else 'under'

        if abs(edge) > 0.10:
            confidence = 'high'
        elif abs(edge) > 0.05:
            confidence = 'medium'
        else:
            confidence = 'low'

        return PropProjection(
            player_name=rb_name,
            team=team,
            prop_type='rush_yards',
            line=book_line,
            projection=round(projection, 1),
            direction=direction,
            confidence=confidence,
            edge=edge,
            hit_rate="Based on matchup + game script",
            notes=f"vs {defense_tier} rush D",
        )

    def project_wr_props(
        self,
        wr_name: str,
        team: str,
        season_avg_yards: float,
        target_share: float,  # % of team targets
        opp_pass_defense_rank: int,
        book_line: float,
    ) -> PropProjection:
        """Project WR receiving yards."""
        base = 0.5 * season_avg_yards + 0.5 * self.LEAGUE_AVERAGES['receiving_yards']

        # Target share boost
        share_adj = 1 + (target_share - 0.20) * 0.5

        # Matchup
        defense_tier = self._get_defense_tier(opp_pass_defense_rank)
        matchup_adj = self.DEFENSE_ADJUSTMENTS[defense_tier]

        projection = base * share_adj * matchup_adj

        edge = (projection - book_line) / book_line
        direction = 'over' if projection > book_line else 'under'

        if abs(edge) > 0.12:
            confidence = 'high'
        elif abs(edge) > 0.06:
            confidence = 'medium'
        else:
            confidence = 'low'

        return PropProjection(
            player_name=wr_name,
            team=team,
            prop_type='receiving_yards',
            line=book_line,
            projection=round(projection, 1),
            direction=direction,
            confidence=confidence,
            edge=edge,
            hit_rate=f"{target_share:.0%} target share",
            notes=f"vs {defense_tier} pass D",
        )

    def _get_defense_tier(self, rank: int) -> str:
        """Convert defense rank to tier."""
        if rank <= 5:
            return 'elite'
        elif rank <= 12:
            return 'good'
        elif rank <= 20:
            return 'average'
        elif rank <= 27:
            return 'poor'
        else:
            return 'bad'

    def build_sgp(
        self,
        game_id: str,
        game: str,
        props: List[PropProjection],
        base_odds: int = -110,
    ) -> SGP:
        """
        Build same-game parlay from props.

        Selects best 2-3 correlated props.
        """
        # Filter to positive edge props
        good_props = [p for p in props if p.edge > 0.03 or (p.direction == 'over' and p.edge > 0)]

        if len(good_props) < 2:
            good_props = props[:2]  # Take best available

        # Select top 2-3 by edge
        selected = sorted(good_props, key=lambda p: abs(p.edge), reverse=True)[:3]

        # Calculate correlation bonus
        # Overs tend to correlate in high-scoring games
        over_count = sum(1 for p in selected if p.direction == 'over')
        correlation_bonus = 0.05 if over_count >= 2 else 0.0

        # Estimate combined odds (simplified)
        # Each leg at ~-110 base, SGP correlation adjustment
        n_legs = len(selected)
        if n_legs == 2:
            combined_odds = 250 + int(correlation_bonus * 50)
        elif n_legs == 3:
            combined_odds = 500 + int(correlation_bonus * 100)
        else:
            combined_odds = 200

        return SGP(
            game_id=game_id,
            game=game,
            legs=selected,
            combined_odds=combined_odds,
            correlation_bonus=correlation_bonus,
            risk_level='moderate' if n_legs == 2 else 'aggressive',
        )


def format_prop_sheet(props: List[PropProjection], game: str) -> str:
    """Format props as a clean data sheet."""
    lines = []
    lines.append("")
    lines.append("=" * 55)
    lines.append(f"📊 PROP PROJECTIONS: {game}")
    lines.append("=" * 55)
    lines.append("")
    lines.append("🟩 = OVER  |  🟥 = UNDER")
    lines.append("")
    lines.append("-" * 55)

    for prop in props:
        emoji = "🟩" if prop.direction == 'over' else "🟥"
        conf_stars = {'high': '★★★', 'medium': '★★', 'low': '★'}[prop.confidence]

        lines.append(f"{emoji} [{prop.team}] {prop.player_name}")
        lines.append(f"   {prop.prop_type.replace('_', ' ').title()}: {prop.direction.upper()} {prop.line}")
        lines.append(f"   Projection: {prop.projection} | Edge: {prop.edge:+.0%} | {conf_stars}")
        lines.append(f"   {prop.hit_rate}")
        lines.append("")

    lines.append("-" * 55)
    lines.append("Use these to build your SGPs!")
    lines.append("=" * 55)

    return "\n".join(lines)


def format_sgp(sgp: SGP) -> str:
    """Format SGP for display."""
    lines = []
    lines.append("")
    lines.append("=" * 50)
    lines.append(f"🎯 SGP: {sgp.game}")
    lines.append("=" * 50)

    for i, prop in enumerate(sgp.legs, 1):
        emoji = "🟩" if prop.direction == 'over' else "🟥"
        lines.append(f"  {i}. {emoji} {prop.player_name} ({prop.team})")
        lines.append(f"     {prop.prop_type.replace('_', ' ').title()} {prop.direction.upper()} {prop.line}")
        lines.append(f"     Proj: {prop.projection} | Edge: {prop.edge:+.0%}")
        lines.append("")

    lines.append("-" * 50)
    lines.append(f"Combined Odds: +{sgp.combined_odds}")
    lines.append(f"Correlation: {'+' if sgp.correlation_bonus > 0 else ''}{sgp.correlation_bonus:.0%}")
    lines.append(f"Risk: {sgp.risk_level.upper()}")
    lines.append("=" * 50)

    return "\n".join(lines)


# Example usage / demo data
def generate_demo_props(home_team: str, away_team: str) -> List[PropProjection]:
    """Generate demo props for testing (would use real data in production)."""
    engine = PlayerPropsEngine()

    # Demo projections
    props = [
        PropProjection(
            player_name="Patrick Mahomes",
            team="KC",
            prop_type="pass_yards",
            line=275.5,
            projection=289,
            direction="over",
            confidence="medium",
            edge=0.05,
            hit_rate="Over in 4/6 recent",
            notes="vs average pass D"
        ),
        PropProjection(
            player_name="Travis Kelce",
            team="KC",
            prop_type="receptions",
            line=5.5,
            projection=6.2,
            direction="over",
            confidence="high",
            edge=0.13,
            hit_rate="Over in 5/6 recent",
            notes="High target share"
        ),
        PropProjection(
            player_name="Isiah Pacheco",
            team="KC",
            prop_type="rush_yards",
            line=55.5,
            projection=62,
            direction="over",
            confidence="medium",
            edge=0.12,
            hit_rate="Favorable script",
            notes="KC favored, run game"
        ),
    ]

    return props
