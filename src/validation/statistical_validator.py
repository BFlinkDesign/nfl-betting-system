"""Statistical validation module for professional betting operations.

Enforces industry-standard requirements before any real-money deployment:
- Sample size: 2,000+ bets for 95% confidence at 57% win rate
- CLV validation: +2% average minimum
- Walk-forward: 3+ seasons out-of-sample
- Statistical significance: p < 0.05

Sources:
- Sports Insights Statistical Significance
- Punter2Pro Sample Size Analysis
- BidCanvas Research Methodology
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of a validation check."""
    passed: bool
    metric_name: str
    actual_value: float
    required_value: float
    message: str
    confidence_level: Optional[float] = None
    p_value: Optional[float] = None


class ProfessionalValidator:
    """
    Validates betting model against professional standards.

    No real money should be deployed until all checks pass.
    """

    # Industry standards from research
    STANDARDS = {
        'min_sample_size': 300,           # Minimum for any signal
        'confident_sample_size': 2000,    # 95% confidence at 57% win rate
        'min_clv_pct': 2.0,               # +2% CLV minimum for profitability
        'min_positive_clv_rate': 0.50,    # >50% of bets should beat closing line
        'min_seasons_oos': 3,             # Minimum out-of-sample seasons
        'significance_level': 0.05,       # p < 0.05 required
        'min_win_rate_at_200': 0.60,      # 60%+ win rate needed at 200 bets
        'min_ece': 0.05,                  # ECE should be < 0.05
    }

    def __init__(self, history_df: Optional[pd.DataFrame] = None):
        """
        Initialize validator.

        Args:
            history_df: Betting history with columns:
                - bet_odds: Odds at time of bet
                - closing_odds: Final odds before game
                - result: 1 for win, 0 for loss
                - pred_prob: Model probability
                - season: Season identifier
        """
        self.history_df = history_df
        self.results: List[ValidationResult] = []

    def validate_all(self, history_df: Optional[pd.DataFrame] = None) -> Tuple[bool, List[ValidationResult]]:
        """
        Run all professional validation checks.

        Args:
            history_df: Betting history (uses stored if not provided)

        Returns:
            (all_passed, list of ValidationResults)
        """
        if history_df is not None:
            self.history_df = history_df

        if self.history_df is None or len(self.history_df) == 0:
            return False, [ValidationResult(
                passed=False,
                metric_name="data_available",
                actual_value=0,
                required_value=1,
                message="No betting history provided for validation"
            )]

        self.results = []

        # Run all checks
        self._check_sample_size()
        self._check_clv_average()
        self._check_clv_positive_rate()
        self._check_clv_significance()
        self._check_win_rate_significance()
        self._check_calibration()
        self._check_seasons_coverage()

        all_passed = all(r.passed for r in self.results)

        return all_passed, self.results

    def _check_sample_size(self) -> None:
        """Check minimum sample size requirements."""
        n_bets = len(self.history_df)

        # Basic minimum
        basic_passed = n_bets >= self.STANDARDS['min_sample_size']
        self.results.append(ValidationResult(
            passed=basic_passed,
            metric_name="sample_size_minimum",
            actual_value=n_bets,
            required_value=self.STANDARDS['min_sample_size'],
            message=f"Sample size: {n_bets} bets (minimum {self.STANDARDS['min_sample_size']})"
        ))

        # Confident sample size
        confident_passed = n_bets >= self.STANDARDS['confident_sample_size']
        self.results.append(ValidationResult(
            passed=confident_passed,
            metric_name="sample_size_confident",
            actual_value=n_bets,
            required_value=self.STANDARDS['confident_sample_size'],
            message=f"Sample size for 95% confidence: {n_bets} bets (need {self.STANDARDS['confident_sample_size']})"
        ))

    def _check_clv_average(self) -> None:
        """Check average CLV meets professional threshold."""
        if 'clv' not in self.history_df.columns:
            if 'bet_odds' in self.history_df.columns and 'closing_odds' in self.history_df.columns:
                self.history_df['clv'] = (
                    self.history_df['bet_odds'] / self.history_df['closing_odds']
                ) - 1
            else:
                self.results.append(ValidationResult(
                    passed=False,
                    metric_name="clv_average",
                    actual_value=0,
                    required_value=self.STANDARDS['min_clv_pct'],
                    message="Cannot calculate CLV: missing bet_odds or closing_odds columns"
                ))
                return

        avg_clv_pct = self.history_df['clv'].mean() * 100
        passed = avg_clv_pct >= self.STANDARDS['min_clv_pct']

        self.results.append(ValidationResult(
            passed=passed,
            metric_name="clv_average",
            actual_value=avg_clv_pct,
            required_value=self.STANDARDS['min_clv_pct'],
            message=f"Average CLV: {avg_clv_pct:.2f}% (need +{self.STANDARDS['min_clv_pct']}%)"
        ))

    def _check_clv_positive_rate(self) -> None:
        """Check percentage of bets beating closing line."""
        if 'clv' not in self.history_df.columns:
            return

        positive_rate = (self.history_df['clv'] > 0).mean()
        passed = positive_rate >= self.STANDARDS['min_positive_clv_rate']

        self.results.append(ValidationResult(
            passed=passed,
            metric_name="clv_positive_rate",
            actual_value=positive_rate * 100,
            required_value=self.STANDARDS['min_positive_clv_rate'] * 100,
            message=f"Positive CLV rate: {positive_rate:.1%} (need {self.STANDARDS['min_positive_clv_rate']:.0%})"
        ))

    def _check_clv_significance(self) -> None:
        """Check if CLV is statistically significant (p < 0.05)."""
        if 'clv' not in self.history_df.columns:
            return

        # One-sample t-test: is mean CLV significantly > 0?
        t_stat, p_value = stats.ttest_1samp(self.history_df['clv'], 0)

        # One-sided test (we care if CLV > 0)
        p_one_sided = p_value / 2 if t_stat > 0 else 1 - p_value / 2

        passed = p_one_sided < self.STANDARDS['significance_level'] and t_stat > 0

        self.results.append(ValidationResult(
            passed=passed,
            metric_name="clv_significance",
            actual_value=p_one_sided,
            required_value=self.STANDARDS['significance_level'],
            message=f"CLV significance: p={p_one_sided:.4f} (need p<{self.STANDARDS['significance_level']})",
            p_value=p_one_sided,
            confidence_level=1 - p_one_sided
        ))

    def _check_win_rate_significance(self) -> None:
        """Check if win rate is statistically significant."""
        if 'result' not in self.history_df.columns:
            return

        n = len(self.history_df)
        wins = self.history_df['result'].sum()
        win_rate = wins / n

        # Binomial test against 50% (break-even before vig)
        # Using normal approximation for large samples
        se = np.sqrt(0.5 * 0.5 / n)
        z = (win_rate - 0.5) / se
        p_value = 1 - stats.norm.cdf(z)

        passed = p_value < self.STANDARDS['significance_level'] and win_rate > 0.5

        # Calculate required win rate at current sample size
        z_critical = stats.norm.ppf(1 - self.STANDARDS['significance_level'])
        required_win_rate = 0.5 + z_critical * se

        self.results.append(ValidationResult(
            passed=passed,
            metric_name="win_rate_significance",
            actual_value=win_rate * 100,
            required_value=required_win_rate * 100,
            message=f"Win rate: {win_rate:.1%} (need {required_win_rate:.1%} at n={n} for significance)",
            p_value=p_value
        ))

    def _check_calibration(self) -> None:
        """Check model calibration (ECE)."""
        if 'pred_prob' not in self.history_df.columns or 'result' not in self.history_df.columns:
            return

        ece = self._calculate_ece(
            self.history_df['result'].values,
            self.history_df['pred_prob'].values
        )

        passed = ece < self.STANDARDS['min_ece']

        self.results.append(ValidationResult(
            passed=passed,
            metric_name="calibration_ece",
            actual_value=ece,
            required_value=self.STANDARDS['min_ece'],
            message=f"ECE: {ece:.4f} (need <{self.STANDARDS['min_ece']})"
        ))

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

    def _check_seasons_coverage(self) -> None:
        """Check out-of-sample seasons coverage."""
        if 'season' not in self.history_df.columns:
            return

        n_seasons = self.history_df['season'].nunique()
        passed = n_seasons >= self.STANDARDS['min_seasons_oos']

        self.results.append(ValidationResult(
            passed=passed,
            metric_name="seasons_coverage",
            actual_value=n_seasons,
            required_value=self.STANDARDS['min_seasons_oos'],
            message=f"Seasons covered: {n_seasons} (need {self.STANDARDS['min_seasons_oos']}+ OOS)"
        ))

    def print_report(self) -> bool:
        """Print formatted validation report."""
        print("\n" + "=" * 70)
        print("PROFESSIONAL VALIDATION REPORT")
        print("=" * 70)

        critical_checks = ['clv_average', 'clv_significance', 'sample_size_minimum']

        passed_count = 0
        failed_count = 0

        print("\nCRITICAL CHECKS:")
        print("-" * 70)
        for result in self.results:
            if result.metric_name in critical_checks:
                status = "✓ PASS" if result.passed else "✗ FAIL"
                print(f"  {status:12} {result.message}")
                if result.passed:
                    passed_count += 1
                else:
                    failed_count += 1

        print("\nADDITIONAL CHECKS:")
        print("-" * 70)
        for result in self.results:
            if result.metric_name not in critical_checks:
                status = "✓ PASS" if result.passed else "⚠ WARN"
                print(f"  {status:12} {result.message}")
                if result.passed:
                    passed_count += 1
                else:
                    failed_count += 1

        print("\n" + "=" * 70)
        all_critical_passed = all(
            r.passed for r in self.results
            if r.metric_name in critical_checks
        )

        if all_critical_passed:
            print("✓ VALIDATION PASSED - System ready for paper trading")
            print("  Next: Paper trade 100-300 bets before real money")
        else:
            print("✗ VALIDATION FAILED - DO NOT DEPLOY REAL MONEY")
            print("  Fix critical issues before proceeding")

        print("=" * 70)

        return all_critical_passed

    @staticmethod
    def required_sample_for_edge(
        expected_edge: float,
        confidence: float = 0.95,
        power: float = 0.80
    ) -> int:
        """
        Calculate required sample size to detect a given edge.

        Args:
            expected_edge: Expected CLV edge (e.g., 0.02 for 2%)
            confidence: Confidence level
            power: Statistical power

        Returns:
            Required number of bets
        """
        from scipy.stats import norm

        alpha = 1 - confidence
        z_alpha = norm.ppf(1 - alpha / 2)
        z_beta = norm.ppf(power)

        # Assume CLV std is roughly 5% (empirical)
        clv_std = 0.05
        effect_size = expected_edge / clv_std

        n = ((z_alpha + z_beta) / effect_size) ** 2

        return int(np.ceil(n))


def validate_before_deployment(history_df: pd.DataFrame) -> bool:
    """
    Convenience function to run full validation.

    Returns True if safe to proceed to paper trading.
    """
    validator = ProfessionalValidator(history_df)
    passed, results = validator.validate_all()
    return validator.print_report()
