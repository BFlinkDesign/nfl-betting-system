"""Position tracking and account management for professional operations.

Implements:
- Real-time position tracking across all accounts
- Exposure limits per game/day/correlation
- Account status monitoring (limits, restrictions)
- Bet logging with CLV calculation

Sources:
- Sports Insights Bankroll Management
- Betting Syndicate Operations
- Professional bettor practices
"""

import json
import logging
import sqlite3
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class Bet:
    """Individual bet record."""
    bet_id: str
    timestamp: datetime
    game_id: str
    book: str
    market: str  # moneyline, spread, total
    selection: str  # team name or over/under
    odds: float  # decimal
    stake: float
    potential_payout: float
    model_prob: float
    model_edge: float
    closing_odds: Optional[float] = None
    clv: Optional[float] = None
    result: Optional[str] = None  # win, loss, push, pending
    profit: Optional[float] = None


@dataclass
class Account:
    """Sportsbook account record."""
    book: str
    balance: float
    deposited: float
    withdrawn: float
    status: str  # active, limited, restricted, closed
    max_bet: Optional[float] = None
    notes: str = ""
    last_updated: Optional[datetime] = None


@dataclass
class ExposureLimits:
    """Exposure limit configuration."""
    max_per_game_pct: float = 0.02  # 2% max per game
    max_per_day_pct: float = 0.10   # 10% max per day
    max_correlated_pct: float = 0.05  # 5% max correlated
    max_single_bet_pct: float = 0.03  # 3% max single bet
    daily_loss_limit_pct: float = 0.10  # Stop after 10% daily loss


class PositionTracker:
    """
    Professional position and account management.

    Tracks all bets, calculates exposure, enforces limits.
    """

    def __init__(
        self,
        db_path: str = "data/positions.db",
        initial_bankroll: float = 10000.0,
        limits: Optional[ExposureLimits] = None
    ):
        """
        Initialize position tracker.

        Args:
            db_path: Path to SQLite database
            initial_bankroll: Starting bankroll
            limits: Exposure limit configuration
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.initial_bankroll = initial_bankroll
        self.limits = limits or ExposureLimits()

        self._init_database()

    def _init_database(self) -> None:
        """Initialize SQLite database with schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Bets table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bets (
                bet_id TEXT PRIMARY KEY,
                timestamp TEXT,
                game_id TEXT,
                book TEXT,
                market TEXT,
                selection TEXT,
                odds REAL,
                stake REAL,
                potential_payout REAL,
                model_prob REAL,
                model_edge REAL,
                closing_odds REAL,
                clv REAL,
                result TEXT,
                profit REAL
            )
        """)

        # Accounts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                book TEXT PRIMARY KEY,
                balance REAL,
                deposited REAL,
                withdrawn REAL,
                status TEXT,
                max_bet REAL,
                notes TEXT,
                last_updated TEXT
            )
        """)

        # Bankroll history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bankroll_history (
                timestamp TEXT PRIMARY KEY,
                total_bankroll REAL,
                daily_pnl REAL,
                total_pnl REAL
            )
        """)

        conn.commit()
        conn.close()

    def record_bet(self, bet: Bet) -> Tuple[bool, str]:
        """
        Record a bet after checking exposure limits.

        Args:
            bet: Bet to record

        Returns:
            (success, message)
        """
        # Check exposure limits
        can_bet, reason = self._check_exposure_limits(bet)
        if not can_bet:
            logger.warning(f"Bet rejected: {reason}")
            return False, reason

        # Record bet
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO bets
            (bet_id, timestamp, game_id, book, market, selection, odds, stake,
             potential_payout, model_prob, model_edge, closing_odds, clv, result, profit)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            bet.bet_id,
            bet.timestamp.isoformat(),
            bet.game_id,
            bet.book,
            bet.market,
            bet.selection,
            bet.odds,
            bet.stake,
            bet.potential_payout,
            bet.model_prob,
            bet.model_edge,
            bet.closing_odds,
            bet.clv,
            bet.result,
            bet.profit
        ))

        # Update account balance
        cursor.execute("""
            UPDATE accounts SET balance = balance - ?, last_updated = ?
            WHERE book = ?
        """, (bet.stake, datetime.now().isoformat(), bet.book))

        conn.commit()
        conn.close()

        logger.info(f"Recorded bet: {bet.bet_id} - ${bet.stake:.2f} on {bet.selection}")
        return True, "Bet recorded"

    def update_bet_result(
        self,
        bet_id: str,
        result: str,
        closing_odds: Optional[float] = None
    ) -> None:
        """
        Update bet with result and calculate CLV.

        Args:
            bet_id: Bet identifier
            result: win, loss, or push
            closing_odds: Final odds before game start
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get bet details
        cursor.execute("SELECT * FROM bets WHERE bet_id = ?", (bet_id,))
        row = cursor.fetchone()

        if not row:
            logger.error(f"Bet not found: {bet_id}")
            conn.close()
            return

        bet_odds = row[6]  # odds column
        stake = row[7]

        # Calculate profit
        if result == 'win':
            profit = stake * (bet_odds - 1)
        elif result == 'loss':
            profit = -stake
        else:  # push
            profit = 0

        # Calculate CLV
        clv = None
        if closing_odds:
            clv = (bet_odds / closing_odds) - 1

        # Update bet
        cursor.execute("""
            UPDATE bets SET result = ?, profit = ?, closing_odds = ?, clv = ?
            WHERE bet_id = ?
        """, (result, profit, closing_odds, clv, bet_id))

        # Update account balance (return stake + profit)
        book = row[3]
        cursor.execute("""
            UPDATE accounts SET balance = balance + ?, last_updated = ?
            WHERE book = ?
        """, (stake + profit, datetime.now().isoformat(), book))

        conn.commit()
        conn.close()

        logger.info(f"Updated bet {bet_id}: {result}, profit=${profit:.2f}, CLV={clv:.2%}" if clv else f"Updated bet {bet_id}: {result}, profit=${profit:.2f}")

    def _check_exposure_limits(self, bet: Bet) -> Tuple[bool, str]:
        """Check if bet violates any exposure limits."""
        bankroll = self.get_total_bankroll()

        # Single bet limit
        if bet.stake > bankroll * self.limits.max_single_bet_pct:
            return False, f"Exceeds single bet limit ({self.limits.max_single_bet_pct:.0%} of bankroll)"

        # Game exposure
        game_exposure = self._get_game_exposure(bet.game_id)
        if game_exposure + bet.stake > bankroll * self.limits.max_per_game_pct:
            return False, f"Exceeds per-game limit ({self.limits.max_per_game_pct:.0%} of bankroll)"

        # Daily exposure
        daily_exposure = self._get_daily_exposure()
        if daily_exposure + bet.stake > bankroll * self.limits.max_per_day_pct:
            return False, f"Exceeds daily limit ({self.limits.max_per_day_pct:.0%} of bankroll)"

        # Daily loss limit
        daily_pnl = self._get_daily_pnl()
        if daily_pnl < -bankroll * self.limits.daily_loss_limit_pct:
            return False, f"Daily loss limit reached ({self.limits.daily_loss_limit_pct:.0%})"

        return True, "OK"

    def _get_game_exposure(self, game_id: str) -> float:
        """Get total exposure on a specific game."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT SUM(stake) FROM bets
            WHERE game_id = ? AND result = 'pending'
        """, (game_id,))

        result = cursor.fetchone()[0]
        conn.close()

        return result or 0.0

    def _get_daily_exposure(self) -> float:
        """Get total exposure for today."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        today = datetime.now().date().isoformat()
        cursor.execute("""
            SELECT SUM(stake) FROM bets
            WHERE date(timestamp) = ? AND result = 'pending'
        """, (today,))

        result = cursor.fetchone()[0]
        conn.close()

        return result or 0.0

    def _get_daily_pnl(self) -> float:
        """Get P&L for today."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        today = datetime.now().date().isoformat()
        cursor.execute("""
            SELECT SUM(profit) FROM bets
            WHERE date(timestamp) = ? AND result IN ('win', 'loss')
        """, (today,))

        result = cursor.fetchone()[0]
        conn.close()

        return result or 0.0

    def get_total_bankroll(self) -> float:
        """Get total bankroll across all accounts."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT SUM(balance) FROM accounts WHERE status != 'closed'")
        result = cursor.fetchone()[0]
        conn.close()

        return result or self.initial_bankroll

    def add_account(self, account: Account) -> None:
        """Add or update a sportsbook account."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO accounts
            (book, balance, deposited, withdrawn, status, max_bet, notes, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            account.book,
            account.balance,
            account.deposited,
            account.withdrawn,
            account.status,
            account.max_bet,
            account.notes,
            datetime.now().isoformat()
        ))

        conn.commit()
        conn.close()

        logger.info(f"Added/updated account: {account.book} - ${account.balance:.2f}")

    def get_accounts(self) -> List[Account]:
        """Get all accounts."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM accounts")
        rows = cursor.fetchall()
        conn.close()

        accounts = []
        for row in rows:
            accounts.append(Account(
                book=row[0],
                balance=row[1],
                deposited=row[2],
                withdrawn=row[3],
                status=row[4],
                max_bet=row[5],
                notes=row[6],
                last_updated=datetime.fromisoformat(row[7]) if row[7] else None
            ))

        return accounts

    def get_pending_bets(self) -> List[Bet]:
        """Get all pending bets."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM bets WHERE result = 'pending' OR result IS NULL")
        rows = cursor.fetchall()
        conn.close()

        return self._rows_to_bets(rows)

    def get_bet_history(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Bet]:
        """Get bet history for date range."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if start_date and end_date:
            cursor.execute("""
                SELECT * FROM bets
                WHERE timestamp BETWEEN ? AND ?
                ORDER BY timestamp DESC
            """, (start_date.isoformat(), end_date.isoformat()))
        else:
            cursor.execute("SELECT * FROM bets ORDER BY timestamp DESC")

        rows = cursor.fetchall()
        conn.close()

        return self._rows_to_bets(rows)

    def _rows_to_bets(self, rows: List[tuple]) -> List[Bet]:
        """Convert database rows to Bet objects."""
        bets = []
        for row in rows:
            bets.append(Bet(
                bet_id=row[0],
                timestamp=datetime.fromisoformat(row[1]) if row[1] else None,
                game_id=row[2],
                book=row[3],
                market=row[4],
                selection=row[5],
                odds=row[6],
                stake=row[7],
                potential_payout=row[8],
                model_prob=row[9],
                model_edge=row[10],
                closing_odds=row[11],
                clv=row[12],
                result=row[13],
                profit=row[14]
            ))
        return bets

    def calculate_performance_metrics(self) -> Dict:
        """Calculate comprehensive performance metrics."""
        bets = self.get_bet_history()
        settled = [b for b in bets if b.result in ('win', 'loss')]

        if not settled:
            return {'error': 'No settled bets'}

        total_staked = sum(b.stake for b in settled)
        total_profit = sum(b.profit for b in settled if b.profit)
        wins = sum(1 for b in settled if b.result == 'win')

        # CLV metrics
        clv_bets = [b for b in settled if b.clv is not None]
        avg_clv = np.mean([b.clv for b in clv_bets]) if clv_bets else None
        positive_clv_rate = np.mean([b.clv > 0 for b in clv_bets]) if clv_bets else None

        return {
            'total_bets': len(settled),
            'wins': wins,
            'losses': len(settled) - wins,
            'win_rate': wins / len(settled),
            'total_staked': total_staked,
            'total_profit': total_profit,
            'roi': total_profit / total_staked if total_staked > 0 else 0,
            'avg_clv': avg_clv,
            'positive_clv_rate': positive_clv_rate,
            'current_bankroll': self.get_total_bankroll(),
            'initial_bankroll': self.initial_bankroll,
            'bankroll_growth': (self.get_total_bankroll() - self.initial_bankroll) / self.initial_bankroll
        }

    def print_daily_summary(self) -> None:
        """Print daily operations summary."""
        print("\n" + "=" * 70)
        print(f"DAILY SUMMARY - {datetime.now().strftime('%Y-%m-%d')}")
        print("=" * 70)

        # Account balances
        accounts = self.get_accounts()
        print("\nACCOUNT BALANCES:")
        total = 0
        for acc in accounts:
            status_indicator = "✓" if acc.status == 'active' else "⚠"
            print(f"  {status_indicator} {acc.book:20} ${acc.balance:>10,.2f}  [{acc.status}]")
            total += acc.balance
        print(f"  {'TOTAL':22} ${total:>10,.2f}")

        # Today's bets
        today_bets = [b for b in self.get_bet_history()
                      if b.timestamp and b.timestamp.date() == datetime.now().date()]

        print(f"\nTODAY'S BETS: {len(today_bets)}")
        pending = [b for b in today_bets if b.result in (None, 'pending')]
        settled = [b for b in today_bets if b.result in ('win', 'loss')]

        print(f"  Pending: {len(pending)}")
        print(f"  Settled: {len(settled)}")

        if settled:
            daily_profit = sum(b.profit for b in settled if b.profit)
            print(f"  Daily P&L: ${daily_profit:+,.2f}")

        # Exposure
        print(f"\nEXPOSURE:")
        print(f"  Daily exposure: ${self._get_daily_exposure():,.2f}")
        print(f"  Daily limit: ${total * self.limits.max_per_day_pct:,.2f}")

        print("=" * 70)
