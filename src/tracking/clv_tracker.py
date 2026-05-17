"""Closing Line Value (CLV) Tracker

CLV is the TRUTH METRIC for betting edge validation.
If you consistently beat closing lines, you have real edge.
If you don't, you got lucky (or unlucky).

"CLV is the only metric that predicts long-term profitability."
- Every professional sports bettor

This module tracks:
1. CLV per bet (how much did line move in your favor?)
2. Rolling CLV averages
3. CLV by edge type (which edges produce best CLV?)
4. Statistical significance of CLV
5. Expected value calculations

References:
- Pinnacle Sports research on CLV
- Unabated Sports / Captain Jack Andrews methodology
- Academic papers on market efficiency in sports betting
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class BetRecord:
    """Record of a single bet for CLV tracking."""
    bet_id: str
    game_id: str
    placed_at: datetime
    team: str
    side: str  # 'spread', 'moneyline', 'total'
    line_at_bet: float  # Spread or total when bet was placed
    odds_at_bet: float  # American odds when placed
    closing_line: float  # Line at game start
    closing_odds: float  # Odds at game start
    stake: float
    result: Optional[str] = None  # 'win', 'loss', 'push'
    profit: Optional[float] = None
    edge_types: List[str] = field(default_factory=list)


@dataclass
class CLVAnalysis:
    """CLV analysis for a bet or set of bets."""
    line_clv: float  # Points of line movement in favor
    odds_clv: float  # Cents of odds improvement
    implied_prob_clv: float  # Probability points gained
    ev_at_bet: float  # Expected value at time of bet
    ev_at_close: float  # EV if we had bet at close
    clv_quality: str  # 'excellent', 'good', 'neutral', 'poor'


class CLVTracker:
    """
    Tracks Closing Line Value for all bets.

    CLV = Closing Line - Line at Bet Time
    Positive CLV = Line moved in your favor = You got a good number

    Professional benchmark: +1.5% average CLV is elite.
    """

    # CLV quality thresholds
    EXCELLENT_CLV = 0.03  # 3+ point move in your favor
    GOOD_CLV = 0.01      # 1-3 points
    POOR_CLV = -0.01     # Line moved against you

    def __init__(self):
        self.bets: List[BetRecord] = []
        self.clv_history: List[Tuple[datetime, float]] = []

    def record_bet(
        self,
        bet_id: str,
        game_id: str,
        team: str,
        side: str,
        line: float,
        odds: float,
        stake: float,
        edge_types: Optional[List[str]] = None,
    ) -> BetRecord:
        """
        Record a new bet (before closing line known).

        Args:
            bet_id: Unique bet identifier
            game_id: Game identifier
            team: Team bet on
            side: 'spread', 'moneyline', 'total'
            line: Line at time of bet
            odds: American odds at time of bet
            stake: Amount wagered
            edge_types: What edges triggered this bet

        Returns:
            BetRecord
        """
        bet = BetRecord(
            bet_id=bet_id,
            game_id=game_id,
            placed_at=datetime.now(),
            team=team,
            side=side,
            line_at_bet=line,
            odds_at_bet=odds,
            closing_line=line,  # Will be updated
            closing_odds=odds,  # Will be updated
            stake=stake,
            edge_types=edge_types or [],
        )

        self.bets.append(bet)
        logger.info(f"Recorded bet {bet_id}: {team} {line} @ {odds}")
        return bet

    def update_closing_line(
        self,
        bet_id: str,
        closing_line: float,
        closing_odds: float,
    ) -> Optional[CLVAnalysis]:
        """
        Update bet with closing line and calculate CLV.

        Args:
            bet_id: Bet to update
            closing_line: Line at game time
            closing_odds: Odds at game time

        Returns:
            CLVAnalysis or None if bet not found
        """
        bet = self._find_bet(bet_id)
        if not bet:
            logger.warning(f"Bet {bet_id} not found")
            return None

        bet.closing_line = closing_line
        bet.closing_odds = closing_odds

        # Calculate CLV
        clv = self._calculate_clv(bet)

        # Record CLV in history
        self.clv_history.append((datetime.now(), clv.implied_prob_clv))

        logger.info(f"CLV for {bet_id}: {clv.line_clv:+.1f} pts, {clv.implied_prob_clv:+.1%} prob")
        return clv

    def record_result(
        self,
        bet_id: str,
        result: str,
        profit: float,
    ):
        """Record bet result."""
        bet = self._find_bet(bet_id)
        if bet:
            bet.result = result
            bet.profit = profit

    def _find_bet(self, bet_id: str) -> Optional[BetRecord]:
        """Find bet by ID."""
        for bet in self.bets:
            if bet.bet_id == bet_id:
                return bet
        return None

    def _calculate_clv(self, bet: BetRecord) -> CLVAnalysis:
        """Calculate CLV for a bet."""
        # Line CLV (positive = line moved in your favor)
        if bet.side == 'spread':
            # For spread bets, if you took team at +3 and it closed +2, that's +1 CLV
            # (You got a better number)
            line_clv = bet.closing_line - bet.line_at_bet
            # Flip sign if you bet the favorite (negative line)
            # Actually: if betting underdog, higher closing = better
            # if betting favorite, lower closing = better
        else:
            line_clv = bet.closing_line - bet.line_at_bet

        # Odds CLV (convert to implied probability)
        prob_at_bet = self._odds_to_prob(bet.odds_at_bet)
        prob_at_close = self._odds_to_prob(bet.closing_odds)

        # Higher implied prob at close = market thinks team is stronger
        # If you bet team early, and prob increased, you got value
        implied_prob_clv = prob_at_close - prob_at_bet

        # Odds CLV in cents (standard measure)
        odds_clv = self._odds_diff_cents(bet.odds_at_bet, bet.closing_odds)

        # EV calculations (simplified)
        # True probability estimate = average of bet and close probs (rough)
        true_prob = (prob_at_bet + prob_at_close) / 2

        ev_at_bet = self._calculate_ev(prob_at_bet, true_prob)
        ev_at_close = self._calculate_ev(prob_at_close, true_prob)

        # Quality assessment
        if implied_prob_clv >= self.EXCELLENT_CLV:
            quality = 'excellent'
        elif implied_prob_clv >= self.GOOD_CLV:
            quality = 'good'
        elif implied_prob_clv >= self.POOR_CLV:
            quality = 'neutral'
        else:
            quality = 'poor'

        return CLVAnalysis(
            line_clv=line_clv,
            odds_clv=odds_clv,
            implied_prob_clv=implied_prob_clv,
            ev_at_bet=ev_at_bet,
            ev_at_close=ev_at_close,
            clv_quality=quality,
        )

    def _odds_to_prob(self, american_odds: float) -> float:
        """Convert American odds to no-vig probability estimate."""
        if american_odds < 0:
            return abs(american_odds) / (abs(american_odds) + 100)
        else:
            return 100 / (american_odds + 100)

    def _odds_diff_cents(self, odds1: float, odds2: float) -> float:
        """Calculate odds difference in cents."""
        return odds2 - odds1

    def _calculate_ev(self, our_prob: float, true_prob: float) -> float:
        """Calculate expected value at given odds."""
        # Simplified: EV = (true_prob - break_even_prob) / break_even_prob
        break_even = 0.5238  # At -110
        return (true_prob - break_even) / break_even

    def get_clv_summary(self, min_bets: int = 10) -> Dict:
        """
        Get summary statistics of CLV performance.

        Args:
            min_bets: Minimum bets required for meaningful stats

        Returns:
            Dict with CLV statistics
        """
        if len(self.bets) < min_bets:
            return {
                'status': 'insufficient_data',
                'bets_recorded': len(self.bets),
                'min_required': min_bets,
            }

        # Calculate CLV for all bets with closing lines
        clvs = []
        for bet in self.bets:
            if bet.closing_line != bet.line_at_bet:  # Has closing line
                clv = self._calculate_clv(bet)
                clvs.append(clv.implied_prob_clv)

        if len(clvs) < min_bets:
            return {
                'status': 'insufficient_closing_data',
                'bets_with_closing': len(clvs),
            }

        clvs = np.array(clvs)

        return {
            'status': 'ok',
            'total_bets': len(self.bets),
            'bets_with_clv': len(clvs),
            'mean_clv': float(np.mean(clvs)),
            'median_clv': float(np.median(clvs)),
            'std_clv': float(np.std(clvs)),
            'clv_positive_pct': float((clvs > 0).mean()),
            'clv_excellent_pct': float((clvs >= self.EXCELLENT_CLV).mean()),
            'assessment': self._assess_clv_performance(clvs),
        }

    def _assess_clv_performance(self, clvs: np.ndarray) -> str:
        """Assess overall CLV performance."""
        mean_clv = np.mean(clvs)
        positive_rate = (clvs > 0).mean()

        if mean_clv >= 0.015 and positive_rate >= 0.55:
            return "ELITE - Consistently beating closing lines"
        elif mean_clv >= 0.008 and positive_rate >= 0.52:
            return "STRONG - Positive CLV indicates real edge"
        elif mean_clv >= 0.003 and positive_rate >= 0.50:
            return "MODERATE - Slight positive CLV, continue monitoring"
        elif mean_clv >= -0.003:
            return "BREAK-EVEN - No clear edge from CLV, may be variance"
        else:
            return "NEGATIVE - Taking bad numbers, improve timing"

    def clv_by_edge_type(self) -> pd.DataFrame:
        """Analyze CLV by edge type."""
        records = []

        for bet in self.bets:
            if bet.closing_line != bet.line_at_bet:
                clv = self._calculate_clv(bet)

                for edge in bet.edge_types:
                    records.append({
                        'edge_type': edge,
                        'clv': clv.implied_prob_clv,
                        'quality': clv.clv_quality,
                    })

                if not bet.edge_types:
                    records.append({
                        'edge_type': 'model_only',
                        'clv': clv.implied_prob_clv,
                        'quality': clv.clv_quality,
                    })

        if not records:
            return pd.DataFrame()

        df = pd.DataFrame(records)

        summary = df.groupby('edge_type').agg({
            'clv': ['mean', 'std', 'count'],
            'quality': lambda x: (x == 'excellent').sum() + (x == 'good').sum()
        }).round(4)

        summary.columns = ['mean_clv', 'std_clv', 'count', 'positive_quality_count']
        return summary.sort_values('mean_clv', ascending=False)

    def print_clv_report(self):
        """Print CLV performance report."""
        summary = self.get_clv_summary()

        print("\n" + "=" * 70)
        print("CLOSING LINE VALUE (CLV) REPORT")
        print("=" * 70)

        if summary['status'] != 'ok':
            print(f"\nStatus: {summary['status']}")
            print("Need more data for meaningful CLV analysis.")
            return

        print(f"\nTotal Bets: {summary['total_bets']}")
        print(f"Bets with CLV Data: {summary['bets_with_clv']}")

        print(f"\nCLV Statistics:")
        print(f"  Mean CLV: {summary['mean_clv']:+.2%}")
        print(f"  Median CLV: {summary['median_clv']:+.2%}")
        print(f"  Std Dev: {summary['std_clv']:.2%}")

        print(f"\nCLV Distribution:")
        print(f"  Positive CLV: {summary['clv_positive_pct']:.0%} of bets")
        print(f"  Excellent CLV (>3%): {summary['clv_excellent_pct']:.0%} of bets")

        print(f"\nAssessment: {summary['assessment']}")

        # By edge type
        edge_clv = self.clv_by_edge_type()
        if len(edge_clv) > 0:
            print(f"\nCLV by Edge Type:")
            print("-" * 50)
            for edge_type, row in edge_clv.iterrows():
                print(f"  {edge_type}: {row['mean_clv']:+.2%} avg (n={int(row['count'])})")

        print("\n" + "=" * 70)
        print("Remember: Consistent positive CLV is the ONLY reliable indicator")
        print("of long-term betting edge. Results can be variance; CLV is truth.")
        print("=" * 70)


def track_week_clv(
    picks_df: pd.DataFrame,
    closing_lines_df: pd.DataFrame,
    tracker: Optional[CLVTracker] = None,
) -> CLVTracker:
    """
    Track CLV for a week of picks.

    Args:
        picks_df: DataFrame with picks (must have bet info)
        closing_lines_df: DataFrame with closing lines
        tracker: Existing tracker to update (creates new if None)

    Returns:
        Updated CLVTracker
    """
    if tracker is None:
        tracker = CLVTracker()

    for idx, pick in picks_df.iterrows():
        game_id = pick.get('game_id', f'game_{idx}')

        # Find closing line
        closing = closing_lines_df[closing_lines_df['game_id'] == game_id]

        if len(closing) == 0:
            continue

        closing_line = closing.iloc[0].get('spread_line', pick.get('spread_line', 0))
        closing_odds = closing.iloc[0].get('spread_odds', -110)

        # Record bet if not already recorded
        bet_id = f"{game_id}_{pick.get('pick_side', 'unknown')}"

        existing = tracker._find_bet(bet_id)
        if existing:
            # Update closing line
            tracker.update_closing_line(bet_id, closing_line, closing_odds)
        else:
            # Record new bet
            edge_types = []
            if pick.get('edge_types'):
                edge_types = pick['edge_types'].split(',')

            tracker.record_bet(
                bet_id=bet_id,
                game_id=game_id,
                team=pick.get('pick_side', ''),
                side='spread',
                line=pick.get('spread_line', 0),
                odds=pick.get('spread_odds', -110),
                stake=1.0,  # Unit bet
                edge_types=edge_types,
            )

            tracker.update_closing_line(bet_id, closing_line, closing_odds)

    return tracker


# Convenience functions for analysis
def calculate_single_clv(
    line_at_bet: float,
    closing_line: float,
    is_underdog: bool = True,
) -> float:
    """
    Quick CLV calculation for a single spread bet.

    Args:
        line_at_bet: Spread when bet was placed
        closing_line: Spread at game time
        is_underdog: True if betting the underdog

    Returns:
        CLV in points (positive = got better number)
    """
    line_movement = closing_line - line_at_bet

    # If betting underdog, higher closing line = better (got more points)
    # If betting favorite, lower closing line = better (laying fewer points)
    if is_underdog:
        return line_movement
    else:
        return -line_movement
