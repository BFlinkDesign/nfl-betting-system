"""Recreational Betting Router - Popular bet types for recreational bettors.

Endpoints focused on what bettors actually bet on:
- Most popular props (receiving yards, anytime TD, rushing yards)
- Popular SGP combinations (QB+WR, RB dual-threat)
- Optimal leg counts (3-4 legs = sweet spot)
"""

from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from datetime import datetime

import sys
from pathlib import Path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.recreational import (
    RecreationalBettingEngine,
    RecProp,
    POPULAR_COMBINATIONS,
    EMPIRICAL_CORRELATIONS,
)


router = APIRouter(prefix="/api/recreational", tags=["recreational"])


# ==================== Response Models ====================

class PropResponse(BaseModel):
    """Single prop response."""
    player: str
    team: str
    prop_type: str
    line: float
    direction: str
    projection: float
    hit_rate: float
    edge: float
    odds: int
    popularity_rank: int


class SGPLegResponse(BaseModel):
    """SGP leg response."""
    player: str
    team: str
    prop_type: str
    line: float
    direction: str
    odds: int


class SGPResponse(BaseModel):
    """SGP response."""
    template_name: str
    legs: List[SGPLegResponse]
    leg_count: int
    correlation_score: float
    combined_odds: int
    implied_prob: float
    model_prob: float
    ev: float
    fun_rating: str


class PopularTemplateResponse(BaseModel):
    """Popular SGP template."""
    name: str
    description: str
    legs: List[str]
    correlation: float
    typical_odds: str
    popularity: str


class RecreationalCardResponse(BaseModel):
    """Full recreational betting card."""
    single_props: List[PropResponse]
    featured_sgps: List[SGPResponse]
    lottery_ticket: Optional[SGPResponse]
    betting_allocation: dict
    generated_at: str


# ==================== Endpoints ====================

@router.get("/templates", response_model=List[PopularTemplateResponse])
async def get_popular_templates():
    """
    Get the most popular SGP templates.

    Based on 2023-2026 recreational betting trends:
    - QB + WR Stack (most popular)
    - RB Dual Threat (CMC, Achane type plays)
    - Volume Receiver (Kelce, CeeDee type)
    - TD Scorer Stack (lottery tickets)

    Returns:
        List of popular SGP templates with correlation data.
    """
    engine = RecreationalBettingEngine()

    return [
        PopularTemplateResponse(
            name=t['name'],
            description=t['description'],
            legs=t['legs'],
            correlation=t['correlation'],
            typical_odds=t['typical_odds'],
            popularity=t['popularity'],
        )
        for t in engine.popular_templates.values()
    ]


@router.get("/leg-counts")
async def get_optimal_leg_counts():
    """
    Get information about optimal parlay leg counts.

    Research shows:
    - 3-4 legs = sweet spot for recreational bettors
    - 5+ legs only with high confidence

    Returns:
        Leg count recommendations and typical payouts.
    """
    return {
        'recommendations': POPULAR_COMBINATIONS,
        'sweet_spot': '3-4 legs',
        'note': '3-leg and 4-leg SGPs are by far the most popular among recreational bettors',
    }


@router.get("/correlations")
async def get_correlation_data():
    """
    Get empirical correlation values for prop combinations.

    Use these to build correlated SGPs:
    - High positive (0.65+): QB+WR yards
    - Moderate (0.35-0.50): RB rushing+receiving
    - Negative (-0.35): RB yards vs QB yards same team

    Returns:
        Correlation values for common prop combinations.
    """
    formatted = []
    for (p1, p2, same_team), corr in EMPIRICAL_CORRELATIONS.items():
        formatted.append({
            'prop1': p1,
            'prop2': p2,
            'same_team': same_team,
            'correlation': corr,
            'strength': 'high' if abs(corr) > 0.5 else 'moderate' if abs(corr) > 0.25 else 'low',
            'direction': 'positive' if corr > 0 else 'negative',
        })

    return {
        'correlations': sorted(formatted, key=lambda x: -abs(x['correlation'])),
        'usage_note': 'High positive correlations are best for OVER+OVER or UNDER+UNDER parlays',
    }


@router.post("/build-sgp")
async def build_custom_sgp(
    template: str = Query(..., description="Template: qb_wr_stack, rb_dual_threat, qb_wr_td, volume_receiver, td_stack"),
    legs: int = Query(3, ge=2, le=6, description="Number of legs (3-4 recommended)"),
):
    """
    Build an SGP using a popular template.

    Most popular templates:
    - qb_wr_stack: QB passing + WR receiving (most popular)
    - rb_dual_threat: RB rushing + receiving (CMC, Achane, Gibbs)
    - qb_wr_td: QB + WR + anytime TD
    - volume_receiver: Receptions + receiving yards
    - td_stack: Multiple anytime TDs (lottery ticket)

    Args:
        template: Template name
        legs: Target number of legs

    Returns:
        Built SGP with correlation and EV analysis.
    """
    engine = RecreationalBettingEngine()

    if template not in engine.popular_templates:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown template. Choose from: {list(engine.popular_templates.keys())}"
        )

    template_data = engine.popular_templates[template]

    return {
        'template': template,
        'template_info': template_data,
        'target_legs': legs,
        'optimal_legs': engine.get_optimal_leg_count(0.65),  # Default confidence
        'note': 'Use /api/recreational/card for full betting card with real props',
    }


@router.get("/card", response_model=RecreationalCardResponse)
async def get_recreational_card():
    """
    Get a full recreational betting card.

    Includes:
    - Top 5 single props by popularity (receiving yards > anytime TD > rushing)
    - Featured SGPs (3-4 legs, high correlation)
    - Lottery ticket (5+ legs, +3000 odds)
    - Betting allocation recommendations

    This is what recreational bettors actually want to see!

    Returns:
        Complete betting card focused on popular bet types.
    """
    engine = RecreationalBettingEngine()

    # Generate demo props (in production, fetch from data service)
    demo_props = [
        {'player': 'Travis Kelce', 'team': 'KC', 'prop_type': 'receiving_yards',
         'line': 65.5, 'direction': 'over', 'projection': 72, 'hit_rate': 0.62, 'edge': 0.08, 'odds': -110},
        {'player': 'Patrick Mahomes', 'team': 'KC', 'prop_type': 'passing_yards',
         'line': 275.5, 'direction': 'over', 'projection': 289, 'hit_rate': 0.52, 'edge': 0.05, 'odds': -110},
        {'player': 'Isiah Pacheco', 'team': 'KC', 'prop_type': 'rushing_yards',
         'line': 55.5, 'direction': 'over', 'projection': 62, 'hit_rate': 0.77, 'edge': 0.10, 'odds': -110},
        {'player': 'Travis Kelce', 'team': 'KC', 'prop_type': 'anytime_td',
         'line': 0.5, 'direction': 'over', 'projection': 0.6, 'hit_rate': 0.45, 'edge': 0.05, 'odds': +120},
        {'player': 'Travis Kelce', 'team': 'KC', 'prop_type': 'receptions',
         'line': 5.5, 'direction': 'over', 'projection': 6.2, 'hit_rate': 0.59, 'edge': 0.07, 'odds': -110},
        {'player': 'CeeDee Lamb', 'team': 'DAL', 'prop_type': 'receiving_yards',
         'line': 85.5, 'direction': 'over', 'projection': 92, 'hit_rate': 0.61, 'edge': 0.06, 'odds': -110},
        {'player': 'Dak Prescott', 'team': 'DAL', 'prop_type': 'passing_yards',
         'line': 265.5, 'direction': 'over', 'projection': 278, 'hit_rate': 0.53, 'edge': 0.04, 'odds': -110},
        {'player': 'CeeDee Lamb', 'team': 'DAL', 'prop_type': 'anytime_td',
         'line': 0.5, 'direction': 'over', 'projection': 0.55, 'hit_rate': 0.42, 'edge': 0.03, 'odds': +140},
    ]

    # Build card
    props = [RecProp(**p) for p in demo_props]
    ranked_props = engine.rank_by_popularity(props)

    # Build SGPs
    featured_sgps = []

    # QB + WR Stack (most popular)
    qb_wr_legs = [
        props[1],  # Mahomes passing
        props[0],  # Kelce receiving
    ]
    ev1, prob1, imp1 = engine.calculate_sgp_ev(qb_wr_legs)
    featured_sgps.append(SGPResponse(
        template_name='qb_wr_stack',
        legs=[SGPLegResponse(
            player=l.player, team=l.team, prop_type=l.prop_type,
            line=l.line, direction=l.direction, odds=l.odds
        ) for l in qb_wr_legs],
        leg_count=2,
        correlation_score=0.72,
        combined_odds=264,
        implied_prob=imp1,
        model_prob=prob1,
        ev=ev1,
        fun_rating='casual',
    ))

    # 3-leg QB + WR + TD
    three_leg = [
        props[1],  # Mahomes passing
        props[0],  # Kelce receiving
        props[3],  # Kelce TD
    ]
    ev2, prob2, imp2 = engine.calculate_sgp_ev(three_leg)
    featured_sgps.append(SGPResponse(
        template_name='qb_wr_td',
        legs=[SGPLegResponse(
            player=l.player, team=l.team, prop_type=l.prop_type,
            line=l.line, direction=l.direction, odds=l.odds
        ) for l in three_leg],
        leg_count=3,
        correlation_score=0.55,
        combined_odds=850,
        implied_prob=imp2,
        model_prob=prob2,
        ev=ev2,
        fun_rating='exciting',
    ))

    # 4-leg with RB
    four_leg = [
        props[1],  # Mahomes passing
        props[0],  # Kelce receiving
        props[2],  # Pacheco rushing
        props[3],  # Kelce TD
    ]
    ev3, prob3, imp3 = engine.calculate_sgp_ev(four_leg)
    featured_sgps.append(SGPResponse(
        template_name='full_stack',
        legs=[SGPLegResponse(
            player=l.player, team=l.team, prop_type=l.prop_type,
            line=l.line, direction=l.direction, odds=l.odds
        ) for l in four_leg],
        leg_count=4,
        correlation_score=0.45,
        combined_odds=2100,
        implied_prob=imp3,
        model_prob=prob3,
        ev=ev3,
        fun_rating='exciting',
    ))

    return RecreationalCardResponse(
        single_props=[PropResponse(
            player=p.player, team=p.team, prop_type=p.prop_type,
            line=p.line, direction=p.direction, projection=p.projection,
            hit_rate=p.hit_rate, edge=p.edge, odds=p.odds,
            popularity_rank=i+1
        ) for i, p in enumerate(ranked_props[:5])],
        featured_sgps=featured_sgps,
        lottery_ticket=None,  # Add when 5+ leg data available
        betting_allocation={
            'single_props': '40% of bankroll',
            'sgps_3_4_leg': '45% of bankroll',
            'lottery_5_plus': '15% of bankroll',
        },
        generated_at=datetime.now().isoformat(),
    )


@router.get("/popularity-rankings")
async def get_prop_popularity():
    """
    Get prop types ranked by recreational bettor popularity.

    Based on betting volume data from 2023-2026:
    1. Receiving Yards - most popular by far
    2. Anytime TD - fun factor, high variance
    3. Rushing Yards - star RBs (CMC, Henry, Bijan)
    4. Receptions - consistent for slot WRs/TEs
    5. Passing Yards - big QB names

    Returns:
        Prop types ranked by popularity with notes.
    """
    return {
        'rankings': [
            {'rank': 1, 'prop_type': 'receiving_yards', 'typical_line': '45-85 yards',
             'note': 'Most popular by far - easy to understand, high variance'},
            {'rank': 2, 'prop_type': 'anytime_td', 'typical_line': '+120 to +300',
             'note': '"He\'s due", fun to root for'},
            {'rank': 3, 'prop_type': 'rushing_yards', 'typical_line': '45-80 yards',
             'note': 'Popular for star RBs (CMC, Bijan, Henry)'},
            {'rank': 4, 'prop_type': 'receptions', 'typical_line': '4.5-7.5',
             'note': 'Very consistent for slot WRs/TEs'},
            {'rank': 5, 'prop_type': 'passing_yards', 'typical_line': '225-275 yards',
             'note': 'Big names (Mahomes, Allen, Burrow)'},
            {'rank': 6, 'prop_type': 'passing_tds', 'typical_line': '1.5-2.5',
             'note': 'High payout, exciting'},
            {'rank': 7, 'prop_type': 'first_td', 'typical_line': '+400 to +1200',
             'note': 'Low hit rate but very popular lottery bet'},
        ],
    }
