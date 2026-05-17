"""Recreational Betting Module - Focus on what bettors actually bet on.

This module prioritizes:
1. POPULAR prop types (receiving yards, anytime TD, rushing yards)
2. POPULAR SGP combinations (QB+WR, RB dual-threat)
3. OPTIMAL leg counts (3-4 = sweet spot)
4. FUN factor alongside +EV

Based on 2023-2026 recreational betting trends.
"""

from .popular_bets import (
    RecreationalBettingEngine,
    RecProp,
    RecSGP,
    PopularPropType,
    build_recreational_card,
    POPULAR_COMBINATIONS,
    EMPIRICAL_CORRELATIONS,
)

__all__ = [
    'RecreationalBettingEngine',
    'RecProp',
    'RecSGP',
    'PopularPropType',
    'build_recreational_card',
    'POPULAR_COMBINATIONS',
    'EMPIRICAL_CORRELATIONS',
]
