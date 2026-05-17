"""Performance dashboard for professional betting operations.

Tracks all key metrics per professional standards:
- CLV as primary edge metric
- ROI with confidence intervals
- Calibration monitoring
- Account health

Sources:
- Bet-Analytix Closing Odds Ultimate Indicator
- Sports Insights Statistical Significance
- Professional syndicate practices
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)


@dataclass
class PerformanceSnapshot:
    """Point-in-time performance snapshot."""
    timestamp: datetime
    total_bets: int
    wins: int
    losses: int
    win_rate: float
    total_staked: float
    total_profit: float
    roi: float
    avg_clv: float
    positive_clv_rate: float
    clv_pvalue: float
    ece: float
    sharpe_ratio: float
    max_drawdown: float
    current_bankroll: float


class PerformanceDashboard:
    """
    Professional performance tracking and reporting.

    Primary metric: CLV (Closing Line Value)
    "Consistently beating the closing line is the best indicator of long-term betting skill"
    """

    # Professional thresholds
    THRESHOLDS = {
        'excellent_clv': 0.03,      # 3%+ CLV is excellent
        'good_clv': 0.02,           # 2%+ CLV is good
        'minimum_clv': 0.01,        # 1%+ CLV is breakeven after vig
        'target_positive_clv': 0.55,  # 55%+ bets should beat close
        'max_ece': 0.05,            # ECE should stay under 5%
        'min_sharpe': 0.5,          # Minimum risk-adjusted return
    }

    def __init__(self, position_tracker=None):
        """
        Initialize dashboard.

        Args:
            position_tracker: PositionTracker instance for data
        """
        self.position_tracker = position_tracker
        self.snapshots: List[PerformanceSnapshot] = []

    def calculate_metrics(self, bets: List) -> Dict:
        """
        Calculate comprehensive performance metrics.

        Args:
            bets: List of Bet objects

        Returns:
            Dict with all metrics
        """
        if not bets:
            return {'error': 'No bets to analyze'}

        settled = [b for b in bets if b.result in ('win', 'loss')]
        if not settled:
            return {'error': 'No settled bets'}

        # Basic metrics
        wins = sum(1 for b in settled if b.result == 'win')
        losses = len(settled) - wins
        win_rate = wins / len(settled)

        total_staked = sum(b.stake for b in settled)
        total_profit = sum(b.profit for b in settled if b.profit is not None)
        roi = total_profit / total_staked if total_staked > 0 else 0

        # CLV metrics (PRIMARY)
        clv_bets = [b for b in settled if b.clv is not None]
        if clv_bets:
            clv_values = [b.clv for b in clv_bets]
            avg_clv = np.mean(clv_values)
            clv_std = np.std(clv_values)
            positive_clv_rate = np.mean([c > 0 for c in clv_values])

            # Statistical significance
            t_stat, p_value = stats.ttest_1samp(clv_values, 0)
            clv_pvalue = p_value / 2 if t_stat > 0 else 1  # One-sided
        else:
            avg_clv = None
            clv_std = None
            positive_clv_rate = None
            clv_pvalue = 1.0

        # Calibration (ECE)
        prob_bets = [b for b in settled if b.model_prob is not None]
        if prob_bets:
            y_true = np.array([1 if b.result == 'win' else 0 for b in prob_bets])
            y_prob = np.array([b.model_prob for b in prob_bets])
            ece = self._calculate_ece(y_true, y_prob)
        else:
            ece = None

        # Risk metrics
        profits = [b.profit for b in settled if b.profit is not None]
        stakes = [b.stake for b in settled]

        if profits and stakes:
            returns = [p / s for p, s in zip(profits, stakes)]
            sharpe = (np.mean(returns) / np.std(returns) * np.sqrt(252)
                      if np.std(returns) > 0 else 0)

            # Drawdown
            cumulative = np.cumsum(profits)
            running_max = np.maximum.accumulate(cumulative)
            drawdown = cumulative - running_max
            max_drawdown = np.min(drawdown) if len(drawdown) > 0 else 0
        else:
            sharpe = 0
            max_drawdown = 0

        return {
            # Basic
            'total_bets': len(settled),
            'wins': wins,
            'losses': losses,
            'win_rate': win_rate,
            'total_staked': total_staked,
            'total_profit': total_profit,
            'roi': roi,

            # CLV (PRIMARY)
            'avg_clv': avg_clv,
            'clv_std': clv_std,
            'positive_clv_rate': positive_clv_rate,
            'clv_pvalue': clv_pvalue,
            'clv_significant': clv_pvalue < 0.05 if clv_pvalue else False,

            # Calibration
            'ece': ece,

            # Risk
            'sharpe_ratio': sharpe,
            'max_drawdown': max_drawdown,
        }

    def _calculate_ece(self, y_true: np.ndarray, y_prob: np.ndarray, n_bins: int = 10) -> float:
        """Calculate Expected Calibration Error."""
        bin_boundaries = np.linspace(0, 1, n_bins + 1)
        ece = 0.0

        for i in range(n_bins):
            in_bin = (y_prob > bin_boundaries[i]) & (y_prob <= bin_boundaries[i + 1])
            prop_in_bin = in_bin.sum() / len(y_true)

            if in_bin.sum() > 0:
                accuracy_in_bin = y_true[in_bin].mean()
                avg_confidence_in_bin = y_prob[in_bin].mean()
                ece += prop_in_bin * abs(accuracy_in_bin - avg_confidence_in_bin)

        return ece

    def assess_health(self, metrics: Dict) -> Tuple[str, List[str]]:
        """
        Assess overall system health.

        Returns:
            (status, list of issues)
            status: 'healthy', 'warning', 'critical'
        """
        issues = []
        status = 'healthy'

        # CLV checks (PRIMARY)
        if metrics.get('avg_clv') is not None:
            avg_clv = metrics['avg_clv']

            if avg_clv < 0:
                issues.append(f"CRITICAL: Negative CLV ({avg_clv:.2%}) - No edge detected")
                status = 'critical'
            elif avg_clv < self.THRESHOLDS['minimum_clv']:
                issues.append(f"WARNING: CLV below breakeven ({avg_clv:.2%} < {self.THRESHOLDS['minimum_clv']:.0%})")
                if status != 'critical':
                    status = 'warning'
            elif avg_clv >= self.THRESHOLDS['good_clv']:
                issues.append(f"GOOD: CLV at {avg_clv:.2%} (target: {self.THRESHOLDS['good_clv']:.0%}+)")

        # Positive CLV rate
        if metrics.get('positive_clv_rate') is not None:
            pos_rate = metrics['positive_clv_rate']
            if pos_rate < 0.50:
                issues.append(f"WARNING: Positive CLV rate below 50% ({pos_rate:.1%})")
                if status != 'critical':
                    status = 'warning'

        # Statistical significance
        if not metrics.get('clv_significant', False):
            issues.append("WARNING: CLV not statistically significant (need more bets or larger edge)")
            if status != 'critical':
                status = 'warning'

        # Calibration
        if metrics.get('ece') is not None:
            ece = metrics['ece']
            if ece > self.THRESHOLDS['max_ece']:
                issues.append(f"WARNING: Model poorly calibrated (ECE={ece:.3f} > {self.THRESHOLDS['max_ece']})")
                if status != 'critical':
                    status = 'warning'

        # Sample size
        if metrics.get('total_bets', 0) < 100:
            issues.append(f"INFO: Small sample size ({metrics.get('total_bets', 0)} bets) - results not reliable")

        return status, issues

    def print_dashboard(self, bets: Optional[List] = None) -> None:
        """Print formatted performance dashboard."""
        if bets is None and self.position_tracker:
            bets = self.position_tracker.get_bet_history()

        if not bets:
            print("No betting data available")
            return

        metrics = self.calculate_metrics(bets)
        status, issues = self.assess_health(metrics)

        print("\n" + "=" * 70)
        print("PERFORMANCE DASHBOARD")
        print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        print("=" * 70)

        # Status indicator
        status_colors = {'healthy': '✓', 'warning': '⚠', 'critical': '✗'}
        print(f"\nSYSTEM STATUS: {status_colors[status]} {status.upper()}")

        # Primary metric: CLV
        print("\n" + "-" * 70)
        print("PRIMARY METRIC: CLOSING LINE VALUE (CLV)")
        print("-" * 70)

        if metrics.get('avg_clv') is not None:
            clv_rating = self._rate_clv(metrics['avg_clv'])
            print(f"  Average CLV:        {metrics['avg_clv']:+.2%}  [{clv_rating}]")
            print(f"  CLV Std Dev:        {metrics.get('clv_std', 0):.2%}")
            print(f"  Positive CLV Rate:  {metrics.get('positive_clv_rate', 0):.1%}")
            print(f"  Statistical Sig:    {'Yes (p<0.05)' if metrics.get('clv_significant') else 'No'}")
            print(f"  p-value:            {metrics.get('clv_pvalue', 1):.4f}")
        else:
            print("  CLV data not available - need closing line tracking")

        # Secondary metrics
        print("\n" + "-" * 70)
        print("SECONDARY METRICS")
        print("-" * 70)

        print(f"  Total Bets:         {metrics.get('total_bets', 0)}")
        print(f"  Win Rate:           {metrics.get('win_rate', 0):.1%} ({metrics.get('wins', 0)}W - {metrics.get('losses', 0)}L)")
        print(f"  ROI:                {metrics.get('roi', 0):+.2%}")
        print(f"  Total Profit:       ${metrics.get('total_profit', 0):+,.2f}")
        print(f"  Sharpe Ratio:       {metrics.get('sharpe_ratio', 0):.2f}")
        print(f"  Max Drawdown:       ${metrics.get('max_drawdown', 0):,.2f}")

        # Calibration
        print("\n" + "-" * 70)
        print("MODEL CALIBRATION")
        print("-" * 70)

        if metrics.get('ece') is not None:
            ece_status = "Good" if metrics['ece'] < self.THRESHOLDS['max_ece'] else "Needs work"
            print(f"  ECE:                {metrics['ece']:.4f}  [{ece_status}]")
            print(f"  Target:             < {self.THRESHOLDS['max_ece']}")
        else:
            print("  ECE data not available")

        # Issues
        if issues:
            print("\n" + "-" * 70)
            print("ISSUES & RECOMMENDATIONS")
            print("-" * 70)
            for issue in issues:
                print(f"  • {issue}")

        # Action items based on status
        print("\n" + "-" * 70)
        print("ACTION ITEMS")
        print("-" * 70)

        if status == 'critical':
            print("  1. STOP BETTING - No demonstrable edge")
            print("  2. Review model and feature engineering")
            print("  3. Verify data quality and odds accuracy")
            print("  4. Consider paper trading until CLV positive")
        elif status == 'warning':
            print("  1. Reduce bet sizing until issues resolved")
            print("  2. Monitor CLV trend over next 50 bets")
            print("  3. Check for calibration drift")
        else:
            print("  1. Continue current strategy")
            print("  2. Consider increasing bet size if CLV sustained")
            print("  3. Weekly calibration check recommended")

        print("=" * 70)

    def _rate_clv(self, clv: float) -> str:
        """Rate CLV performance."""
        if clv >= self.THRESHOLDS['excellent_clv']:
            return "Excellent"
        elif clv >= self.THRESHOLDS['good_clv']:
            return "Good"
        elif clv >= self.THRESHOLDS['minimum_clv']:
            return "Breakeven"
        elif clv >= 0:
            return "Marginal"
        else:
            return "Losing"

    def generate_weekly_report(self, bets: List) -> str:
        """Generate weekly performance report."""
        # Filter to last 7 days
        week_ago = datetime.now() - timedelta(days=7)
        weekly_bets = [b for b in bets if b.timestamp and b.timestamp >= week_ago]

        metrics = self.calculate_metrics(weekly_bets)
        status, issues = self.assess_health(metrics)

        report = []
        report.append("=" * 70)
        report.append("WEEKLY PERFORMANCE REPORT")
        report.append(f"Period: {week_ago.strftime('%Y-%m-%d')} to {datetime.now().strftime('%Y-%m-%d')}")
        report.append("=" * 70)
        report.append("")
        report.append(f"Status: {status.upper()}")
        report.append(f"Bets: {metrics.get('total_bets', 0)}")
        report.append(f"Win Rate: {metrics.get('win_rate', 0):.1%}")
        report.append(f"ROI: {metrics.get('roi', 0):+.2%}")
        report.append(f"P&L: ${metrics.get('total_profit', 0):+,.2f}")
        report.append("")
        report.append("CLV ANALYSIS:")
        report.append(f"  Average CLV: {metrics.get('avg_clv', 0):+.2%}" if metrics.get('avg_clv') else "  Average CLV: N/A")
        report.append(f"  Positive CLV Rate: {metrics.get('positive_clv_rate', 0):.1%}" if metrics.get('positive_clv_rate') else "  Positive CLV Rate: N/A")
        report.append("")

        if issues:
            report.append("ISSUES:")
            for issue in issues:
                report.append(f"  • {issue}")

        report.append("=" * 70)

        return "\n".join(report)
