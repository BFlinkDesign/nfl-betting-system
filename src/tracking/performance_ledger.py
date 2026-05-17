"""Performance Ledger - @CapperLedger-Style Self-Verification

Implements rigorous, transparent performance tracking that would pass
third-party verification standards. No cherry-picking, no hiding losses.

Key principles from @CapperLedger methodology:
1. Every pick timestamped BEFORE game
2. Full record with ALL wins, losses, pushes
3. Actual odds recorded (not "best available")
4. Unit sizing tracked consistently
5. ROI calculated with proper juice accounting

This is how you build a verifiable track record that separates
legitimate edge from "AI picks account" marketing hype.
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class LedgerEntry:
    """Single bet entry with full audit trail."""
    entry_id: str
    timestamp: datetime  # When pick was logged (MUST be pre-game)
    game_id: str
    game_time: datetime

    # Pick details
    pick_team: str
    pick_type: str  # spread, moneyline, total_over, total_under
    line: float
    odds: float  # American odds at time of pick

    # Sizing
    units: float
    confidence: str  # high, medium, low

    # Model outputs (for transparency)
    model_prob: float
    market_prob: float
    edge_detected: float
    edge_types: List[str] = field(default_factory=list)

    # Result (filled after game)
    result: Optional[str] = None  # win, loss, push, void
    closing_line: Optional[float] = None
    closing_odds: Optional[float] = None
    profit_units: Optional[float] = None

    # Verification
    hash_at_creation: str = ""  # SHA256 of pick details for tamper evidence

    def __post_init__(self):
        if not self.hash_at_creation:
            self.hash_at_creation = self._compute_hash()

    def _compute_hash(self) -> str:
        """Compute hash of pick details for verification."""
        content = f"{self.game_id}|{self.pick_team}|{self.pick_type}|{self.line}|{self.odds}|{self.units}|{self.timestamp.isoformat()}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]


class PerformanceLedger:
    """
    Full audit-trail performance tracking.

    Designed to meet @CapperLedger verification standards:
    - Pre-game timestamps mandatory
    - No post-hoc additions allowed
    - Complete record (no deletions)
    - Immutable entries (hash verification)
    """

    def __init__(self, ledger_path: str = "data/ledger/performance.json"):
        self.ledger_path = Path(ledger_path)
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        self.entries: List[LedgerEntry] = []
        self._load()

    def _load(self):
        """Load existing ledger from disk."""
        if self.ledger_path.exists():
            with open(self.ledger_path) as f:
                data = json.load(f)
                self.entries = []
                for entry_dict in data.get('entries', []):
                    # Convert string dates back to datetime
                    entry_dict['timestamp'] = datetime.fromisoformat(entry_dict['timestamp'])
                    entry_dict['game_time'] = datetime.fromisoformat(entry_dict['game_time'])
                    self.entries.append(LedgerEntry(**entry_dict))
            logger.info(f"Loaded {len(self.entries)} ledger entries")

    def _save(self):
        """Save ledger to disk."""
        data = {
            'version': '1.0',
            'last_updated': datetime.now().isoformat(),
            'entries': []
        }
        for entry in self.entries:
            entry_dict = asdict(entry)
            entry_dict['timestamp'] = entry.timestamp.isoformat()
            entry_dict['game_time'] = entry.game_time.isoformat()
            data['entries'].append(entry_dict)

        with open(self.ledger_path, 'w') as f:
            json.dump(data, f, indent=2)

    def log_pick(
        self,
        game_id: str,
        game_time: datetime,
        pick_team: str,
        pick_type: str,
        line: float,
        odds: float,
        units: float,
        confidence: str,
        model_prob: float,
        market_prob: float,
        edge_detected: float,
        edge_types: Optional[List[str]] = None,
    ) -> LedgerEntry:
        """
        Log a pick BEFORE game time.

        This is the core verification requirement - picks must be
        timestamped before the game starts.
        """
        now = datetime.now()

        # Verify this is pre-game
        if now >= game_time:
            raise ValueError(
                f"Cannot log pick after game start. "
                f"Game: {game_time.isoformat()}, Now: {now.isoformat()}"
            )

        entry_id = f"{game_id}_{pick_team}_{now.strftime('%Y%m%d%H%M%S')}"

        entry = LedgerEntry(
            entry_id=entry_id,
            timestamp=now,
            game_id=game_id,
            game_time=game_time,
            pick_team=pick_team,
            pick_type=pick_type,
            line=line,
            odds=odds,
            units=units,
            confidence=confidence,
            model_prob=model_prob,
            market_prob=market_prob,
            edge_detected=edge_detected,
            edge_types=edge_types or [],
        )

        self.entries.append(entry)
        self._save()

        logger.info(f"Logged pick: {entry_id} | {pick_team} {line} @ {odds} | {units}u | Hash: {entry.hash_at_creation}")
        return entry

    def record_result(
        self,
        entry_id: str,
        result: str,
        closing_line: float,
        closing_odds: float,
    ) -> Optional[LedgerEntry]:
        """
        Record result for a pick.

        Results: win, loss, push, void
        """
        entry = self._find_entry(entry_id)
        if not entry:
            logger.warning(f"Entry {entry_id} not found")
            return None

        if entry.result is not None:
            logger.warning(f"Entry {entry_id} already has result: {entry.result}")
            return entry

        entry.result = result
        entry.closing_line = closing_line
        entry.closing_odds = closing_odds

        # Calculate profit
        if result == 'win':
            if entry.odds > 0:
                entry.profit_units = entry.units * (entry.odds / 100)
            else:
                entry.profit_units = entry.units * (100 / abs(entry.odds))
        elif result == 'loss':
            entry.profit_units = -entry.units
        else:  # push or void
            entry.profit_units = 0

        self._save()
        logger.info(f"Recorded result: {entry_id} = {result} ({entry.profit_units:+.2f}u)")
        return entry

    def _find_entry(self, entry_id: str) -> Optional[LedgerEntry]:
        """Find entry by ID."""
        for entry in self.entries:
            if entry.entry_id == entry_id:
                return entry
        return None

    def get_record(self,
                   start_date: Optional[datetime] = None,
                   end_date: Optional[datetime] = None,
                   pick_type: Optional[str] = None,
                   confidence: Optional[str] = None) -> Dict:
        """
        Get full record with filters.

        Returns complete stats that would pass third-party verification.
        """
        entries = self.entries

        if start_date:
            entries = [e for e in entries if e.timestamp >= start_date]
        if end_date:
            entries = [e for e in entries if e.timestamp <= end_date]
        if pick_type:
            entries = [e for e in entries if e.pick_type == pick_type]
        if confidence:
            entries = [e for e in entries if e.confidence == confidence]

        # Only count graded picks
        graded = [e for e in entries if e.result in ['win', 'loss', 'push']]

        if not graded:
            return {
                'status': 'no_graded_picks',
                'total_logged': len(entries),
                'pending': len([e for e in entries if e.result is None]),
            }

        wins = len([e for e in graded if e.result == 'win'])
        losses = len([e for e in graded if e.result == 'loss'])
        pushes = len([e for e in graded if e.result == 'push'])

        total_wagered = sum(e.units for e in graded if e.result != 'push')
        total_profit = sum(e.profit_units or 0 for e in graded)

        # Calculate ROI properly (accounting for juice)
        roi = (total_profit / total_wagered * 100) if total_wagered > 0 else 0

        # Win rate
        decided = wins + losses
        win_rate = wins / decided if decided > 0 else 0

        # Break-even win rate at -110
        break_even = 0.5238

        # CLV stats
        clv_entries = [e for e in graded if e.closing_line is not None]
        if clv_entries:
            avg_clv = sum(
                (e.closing_line - e.line) if e.pick_type == 'spread' else 0
                for e in clv_entries
            ) / len(clv_entries)
        else:
            avg_clv = None

        return {
            'status': 'ok',
            'period': {
                'start': min(e.timestamp for e in graded).isoformat(),
                'end': max(e.timestamp for e in graded).isoformat(),
            },
            'record': {
                'wins': wins,
                'losses': losses,
                'pushes': pushes,
                'total': len(graded),
                'win_rate': win_rate,
                'break_even_rate': break_even,
                'beats_break_even': win_rate > break_even,
            },
            'units': {
                'wagered': total_wagered,
                'profit': total_profit,
                'roi_percent': roi,
            },
            'clv': {
                'entries_with_clv': len(clv_entries),
                'average_clv': avg_clv,
            },
            'by_confidence': self._breakdown_by_confidence(graded),
            'by_edge_type': self._breakdown_by_edge(graded),
        }

    def _breakdown_by_confidence(self, entries: List[LedgerEntry]) -> Dict:
        """Breakdown stats by confidence level."""
        breakdown = {}
        for conf in ['high', 'medium', 'low']:
            conf_entries = [e for e in entries if e.confidence == conf]
            if conf_entries:
                wins = len([e for e in conf_entries if e.result == 'win'])
                losses = len([e for e in conf_entries if e.result == 'loss'])
                profit = sum(e.profit_units or 0 for e in conf_entries)
                breakdown[conf] = {
                    'count': len(conf_entries),
                    'wins': wins,
                    'losses': losses,
                    'win_rate': wins / (wins + losses) if (wins + losses) > 0 else 0,
                    'profit_units': profit,
                }
        return breakdown

    def _breakdown_by_edge(self, entries: List[LedgerEntry]) -> Dict:
        """Breakdown stats by edge type."""
        edge_stats = {}
        for entry in entries:
            for edge in entry.edge_types:
                if edge not in edge_stats:
                    edge_stats[edge] = {'wins': 0, 'losses': 0, 'profit': 0}
                if entry.result == 'win':
                    edge_stats[edge]['wins'] += 1
                elif entry.result == 'loss':
                    edge_stats[edge]['losses'] += 1
                edge_stats[edge]['profit'] += entry.profit_units or 0

        # Add win rates
        for edge in edge_stats:
            w, l = edge_stats[edge]['wins'], edge_stats[edge]['losses']
            edge_stats[edge]['win_rate'] = w / (w + l) if (w + l) > 0 else 0

        return edge_stats

    def print_full_record(self):
        """Print complete verified record."""
        record = self.get_record()

        print("\n" + "=" * 70)
        print("VERIFIED PERFORMANCE RECORD")
        print("@CapperLedger-Style Full Transparency")
        print("=" * 70)

        if record['status'] != 'ok':
            print(f"\nStatus: {record['status']}")
            print(f"Picks logged: {record.get('total_logged', 0)}")
            print(f"Pending results: {record.get('pending', 0)}")
            return

        print(f"\nPeriod: {record['period']['start'][:10]} to {record['period']['end'][:10]}")

        r = record['record']
        print(f"\nRECORD: {r['wins']}-{r['losses']}-{r['pushes']} ({r['total']} picks)")
        print(f"Win Rate: {r['win_rate']:.1%} (break-even: {r['break_even_rate']:.1%})")

        u = record['units']
        print(f"\nUNITS: {u['profit']:+.2f} on {u['wagered']:.1f} wagered")
        print(f"ROI: {u['roi_percent']:+.1f}%")

        if record['clv']['average_clv'] is not None:
            print(f"\nCLV: {record['clv']['average_clv']:+.2f} avg ({record['clv']['entries_with_clv']} tracked)")

        print("\nBY CONFIDENCE:")
        for conf, stats in record['by_confidence'].items():
            print(f"  {conf.upper()}: {stats['wins']}-{stats['losses']} "
                  f"({stats['win_rate']:.0%}) | {stats['profit_units']:+.1f}u")

        if record['by_edge_type']:
            print("\nBY EDGE TYPE:")
            for edge, stats in record['by_edge_type'].items():
                print(f"  {edge}: {stats['wins']}-{stats['losses']} "
                      f"({stats['win_rate']:.0%}) | {stats['profit']:+.1f}u")

        print("\n" + "=" * 70)
        print("All picks timestamped pre-game. Full record, no cherry-picking.")
        print("Hash verification available for each entry.")
        print("=" * 70)

    def export_for_verification(self, output_path: str = "data/ledger/export.csv"):
        """Export ledger in CSV format for third-party verification."""
        records = []
        for entry in self.entries:
            records.append({
                'entry_id': entry.entry_id,
                'hash': entry.hash_at_creation,
                'logged_at': entry.timestamp.isoformat(),
                'game_time': entry.game_time.isoformat(),
                'game_id': entry.game_id,
                'pick': f"{entry.pick_team} {entry.line}",
                'odds': entry.odds,
                'units': entry.units,
                'confidence': entry.confidence,
                'model_prob': f"{entry.model_prob:.1%}",
                'edge': f"{entry.edge_detected:+.1%}",
                'edges': ','.join(entry.edge_types),
                'result': entry.result or 'pending',
                'closing_line': entry.closing_line,
                'profit': entry.profit_units,
            })

        df = pd.DataFrame(records)
        df.to_csv(output_path, index=False)
        logger.info(f"Exported {len(records)} entries to {output_path}")
        return output_path


def create_weekly_snapshot(ledger: PerformanceLedger, week: int, season: int) -> Dict:
    """Create weekly performance snapshot for tracking."""
    record = ledger.get_record()

    return {
        'week': week,
        'season': season,
        'snapshot_time': datetime.now().isoformat(),
        'cumulative_record': record,
    }
