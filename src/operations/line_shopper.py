"""Line shopping system for finding best available odds.

Per professional practice: "-110 instead of -115 can be difference between profit and loss"

Sources:
- GamblingSite Professional Bettor Daily Habits
- Boyd's Bets Professional Lifestyle
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class OddsSnapshot:
    """Odds from a single book at a point in time."""
    book: str
    odds: float  # decimal
    timestamp: datetime
    max_stake: Optional[float] = None
    available: bool = True


@dataclass
class BestLine:
    """Best available line across all books."""
    game_id: str
    market: str
    selection: str
    best_odds: float
    best_book: str
    all_odds: List[OddsSnapshot]
    model_prob: float
    edge_at_best: float
    timestamp: datetime


class LineShopper:
    """
    Find best available odds across multiple sportsbooks.

    Professional practice: Always shop for best line before placing any bet.
    """

    def __init__(self, odds_client=None):
        """
        Initialize line shopper.

        Args:
            odds_client: Odds API client for fetching live odds
        """
        self.odds_client = odds_client
        self.odds_cache: Dict[str, List[OddsSnapshot]] = {}
        self.alerts: List[BestLine] = []

    def find_best_line(
        self,
        game_id: str,
        market: str,
        selection: str,
        current_odds: Dict[str, float],
        model_prob: float
    ) -> BestLine:
        """
        Find best available line across all books.

        Args:
            game_id: Game identifier
            market: Market type (moneyline, spread, total)
            selection: Selection (team or over/under)
            current_odds: Dict mapping book name to decimal odds
            model_prob: Model's probability estimate

        Returns:
            BestLine with best available odds
        """
        now = datetime.now()

        # Create snapshots
        snapshots = [
            OddsSnapshot(book=book, odds=odds, timestamp=now)
            for book, odds in current_odds.items()
        ]

        # Find best
        best_snapshot = max(snapshots, key=lambda x: x.odds)

        # Calculate edge
        implied_prob = 1 / best_snapshot.odds
        edge = model_prob - implied_prob

        best_line = BestLine(
            game_id=game_id,
            market=market,
            selection=selection,
            best_odds=best_snapshot.odds,
            best_book=best_snapshot.book,
            all_odds=snapshots,
            model_prob=model_prob,
            edge_at_best=edge,
            timestamp=now
        )

        return best_line

    def calculate_line_value(
        self,
        odds_a: float,
        odds_b: float
    ) -> Tuple[float, float]:
        """
        Calculate value difference between two lines.

        Args:
            odds_a: Odds at book A (decimal)
            odds_b: Odds at book B (decimal)

        Returns:
            (absolute_diff, percentage_diff)
        """
        # Implied probability difference
        implied_a = 1 / odds_a
        implied_b = 1 / odds_b

        abs_diff = implied_b - implied_a
        pct_diff = (odds_a - odds_b) / odds_b * 100

        return abs_diff, pct_diff

    def american_to_decimal(self, american: int) -> float:
        """Convert American odds to decimal."""
        if american > 0:
            return 1 + (american / 100)
        else:
            return 1 + (100 / abs(american))

    def decimal_to_american(self, decimal: float) -> int:
        """Convert decimal odds to American."""
        if decimal >= 2.0:
            return int((decimal - 1) * 100)
        else:
            return int(-100 / (decimal - 1))

    def get_line_shopping_value(
        self,
        worst_odds: float,
        best_odds: float,
        stake: float
    ) -> float:
        """
        Calculate dollar value of line shopping.

        Shows how much extra you win by getting the best line.

        Args:
            worst_odds: Worst available odds (decimal)
            best_odds: Best available odds (decimal)
            stake: Bet amount

        Returns:
            Extra profit from line shopping
        """
        worst_payout = stake * (worst_odds - 1)
        best_payout = stake * (best_odds - 1)

        return best_payout - worst_payout

    def print_line_comparison(self, best_line: BestLine, stake: float = 100) -> None:
        """Print formatted line comparison."""
        print(f"\nLINE SHOPPING: {best_line.selection}")
        print("-" * 50)

        sorted_odds = sorted(best_line.all_odds, key=lambda x: x.odds, reverse=True)

        for i, snapshot in enumerate(sorted_odds):
            indicator = "★" if snapshot.book == best_line.best_book else " "
            american = self.decimal_to_american(snapshot.odds)
            payout = stake * (snapshot.odds - 1)
            print(f"  {indicator} {snapshot.book:15} {american:+4d} ({snapshot.odds:.3f})  Win: ${payout:.2f}")

        # Value of shopping
        if len(sorted_odds) > 1:
            best = sorted_odds[0].odds
            worst = sorted_odds[-1].odds
            value = self.get_line_shopping_value(worst, best, stake)
            print(f"\n  Line shopping value: ${value:.2f} on ${stake:.0f} bet")

        print(f"\n  Model prob: {best_line.model_prob:.1%}")
        print(f"  Edge at best: {best_line.edge_at_best:.2%}")


class LineMovementTracker:
    """
    Track line movements over time for sharp detection.
    """

    def __init__(self):
        self.movement_history: Dict[str, List[Tuple[datetime, float, str]]] = {}

    def record_movement(
        self,
        game_id: str,
        odds: float,
        book: str,
        timestamp: Optional[datetime] = None
    ) -> None:
        """Record a line movement."""
        ts = timestamp or datetime.now()

        if game_id not in self.movement_history:
            self.movement_history[game_id] = []

        self.movement_history[game_id].append((ts, odds, book))

    def detect_steam_move(
        self,
        game_id: str,
        threshold_books: int = 3,
        time_window_seconds: int = 60
    ) -> bool:
        """
        Detect steam move (simultaneous movement across books).

        Steam = Sharp syndicate hitting multiple books at once

        Args:
            game_id: Game to check
            threshold_books: Minimum books moving together
            time_window_seconds: Time window for simultaneous moves

        Returns:
            True if steam move detected
        """
        if game_id not in self.movement_history:
            return False

        history = self.movement_history[game_id]
        if len(history) < threshold_books:
            return False

        # Group by time window
        sorted_history = sorted(history, key=lambda x: x[0])

        for i in range(len(sorted_history) - threshold_books + 1):
            window_start = sorted_history[i][0]
            books_in_window = set()

            for ts, odds, book in sorted_history[i:]:
                if (ts - window_start).total_seconds() <= time_window_seconds:
                    books_in_window.add(book)
                else:
                    break

            if len(books_in_window) >= threshold_books:
                logger.warning(f"STEAM MOVE DETECTED: {game_id} - {len(books_in_window)} books moved in {time_window_seconds}s")
                return True

        return False

    def detect_reverse_line_movement(
        self,
        game_id: str,
        public_side: str,
        public_pct: float,
        opening_odds: float,
        current_odds: float
    ) -> bool:
        """
        Detect reverse line movement.

        RLM = Line moves opposite to public betting percentage

        Args:
            game_id: Game to check
            public_side: Which side public is betting
            public_pct: Percentage on public side
            opening_odds: Opening line
            current_odds: Current line

        Returns:
            True if reverse line movement detected
        """
        # Public heavily on one side but line moves other way
        if public_pct >= 60:  # 60%+ on public side
            # Check if line moved against public
            # For favorite: if public on favorite but line got worse (moved up)
            # For underdog: if public on underdog but line got better (moved down)

            line_moved_against_public = (
                (current_odds > opening_odds and public_pct >= 60) or
                (current_odds < opening_odds and public_pct <= 40)
            )

            if line_moved_against_public:
                logger.warning(f"REVERSE LINE MOVEMENT: {game_id} - {public_pct:.0f}% public but line moved opposite")
                return True

        return False

    def get_opening_to_current_movement(self, game_id: str) -> Optional[float]:
        """Get total line movement from open to current."""
        if game_id not in self.movement_history:
            return None

        history = sorted(self.movement_history[game_id], key=lambda x: x[0])
        if len(history) < 2:
            return None

        opening = history[0][1]
        current = history[-1][1]

        return current - opening
