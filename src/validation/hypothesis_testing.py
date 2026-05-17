"""Hypothesis Testing Framework - EDA Before ML

Implements the research-backed approach of validating edges through
statistical hypothesis testing BEFORE trusting ML model outputs.

Key principle from competitive intelligence:
"If your edge doesn't show up in a pivot table, your ML model is lying to you."

This module provides:
1. Situation-based ATS rate testing (chi-square, binomial)
2. Sample size validation (minimum N for statistical significance)
3. Multiple comparison correction (FDR control)
4. Confidence interval construction
5. Trend stability analysis

References:
- Sharp Football Analysis methodology
- Ben Baldwin's nflfastR analysis approach
- Statistical rigor standards from academic sports analytics
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)


@dataclass
class HypothesisResult:
    """Result of a hypothesis test for a betting edge."""
    edge_name: str
    sample_size: int
    successes: int  # Wins/covers
    observed_rate: float
    null_rate: float  # Usually 0.50 (market efficiency)
    p_value: float
    ci_lower: float
    ci_upper: float
    is_significant: bool
    effect_size: float  # Cohen's h
    verdict: str
    roi_estimate: float  # Assuming -110 standard juice


class EdgeHypothesisTester:
    """
    Tests whether observed betting edges are statistically significant.

    Uses binomial tests against null hypothesis of market efficiency (50%).
    Applies Benjamini-Hochberg correction for multiple comparisons.
    """

    # Minimum sample sizes for edge validation
    MIN_SAMPLE_EXPLORATORY = 30   # Minimum for exploratory analysis
    MIN_SAMPLE_ACTIONABLE = 100   # Minimum to consider betting on
    MIN_SAMPLE_CONFIDENT = 250    # High confidence threshold

    # Standard juice assumption for ROI calculations
    STANDARD_JUICE = -110

    def __init__(self, alpha: float = 0.05):
        """
        Initialize tester.

        Args:
            alpha: Significance level (default 0.05)
        """
        self.alpha = alpha
        self.results: List[HypothesisResult] = []

    def test_edge(
        self,
        edge_name: str,
        wins: int,
        losses: int,
        null_rate: float = 0.50,
    ) -> HypothesisResult:
        """
        Test if an edge is statistically significant.

        Args:
            edge_name: Descriptive name of the edge
            wins: Number of winning bets
            losses: Number of losing bets
            null_rate: Expected rate under null hypothesis (market efficiency)

        Returns:
            HypothesisResult with statistical analysis
        """
        n = wins + losses
        observed_rate = wins / n if n > 0 else 0

        # Binomial test (two-sided, then one-sided if favorable)
        if n > 0:
            # Two-sided test first
            p_value_two = stats.binomtest(wins, n, null_rate).pvalue

            # If observed > null, use one-sided test (we care about beating market)
            if observed_rate > null_rate:
                p_value = stats.binomtest(wins, n, null_rate, alternative='greater').pvalue
            else:
                p_value = p_value_two
        else:
            p_value = 1.0

        # Wilson score confidence interval (better than normal approx for proportions)
        ci_lower, ci_upper = self._wilson_ci(wins, n)

        # Effect size (Cohen's h)
        effect_size = self._cohens_h(observed_rate, null_rate)

        # Significance determination
        is_significant = p_value < self.alpha and n >= self.MIN_SAMPLE_EXPLORATORY

        # ROI estimate (assuming -110 juice)
        roi = self._calculate_roi(observed_rate)

        # Verdict
        verdict = self._get_verdict(
            n, observed_rate, p_value, is_significant, roi
        )

        result = HypothesisResult(
            edge_name=edge_name,
            sample_size=n,
            successes=wins,
            observed_rate=observed_rate,
            null_rate=null_rate,
            p_value=p_value,
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            is_significant=is_significant,
            effect_size=effect_size,
            verdict=verdict,
            roi_estimate=roi,
        )

        self.results.append(result)
        return result

    def _wilson_ci(self, successes: int, n: int, conf: float = 0.95) -> Tuple[float, float]:
        """Calculate Wilson score confidence interval."""
        if n == 0:
            return 0.0, 1.0

        z = stats.norm.ppf(1 - (1 - conf) / 2)
        p = successes / n

        denominator = 1 + z**2 / n
        center = (p + z**2 / (2 * n)) / denominator
        margin = z * np.sqrt((p * (1 - p) + z**2 / (4 * n)) / n) / denominator

        return max(0, center - margin), min(1, center + margin)

    def _cohens_h(self, p1: float, p2: float) -> float:
        """Calculate Cohen's h effect size for proportions."""
        phi1 = 2 * np.arcsin(np.sqrt(p1))
        phi2 = 2 * np.arcsin(np.sqrt(p2))
        return abs(phi1 - phi2)

    def _calculate_roi(self, win_rate: float) -> float:
        """Calculate ROI assuming standard -110 juice."""
        # At -110, need 52.38% to break even
        # ROI = (win_rate * 100 - (1-win_rate) * 110) / 110
        if win_rate <= 0:
            return -1.0
        return (win_rate * 100 - (1 - win_rate) * 110) / 110

    def _get_verdict(
        self,
        n: int,
        rate: float,
        p_value: float,
        is_significant: bool,
        roi: float,
    ) -> str:
        """Generate human-readable verdict."""
        if n < self.MIN_SAMPLE_EXPLORATORY:
            return f"INSUFFICIENT DATA ({n} < {self.MIN_SAMPLE_EXPLORATORY})"

        if not is_significant:
            if rate > 0.52:
                return "PROMISING but not significant (need more data)"
            else:
                return "NO EDGE DETECTED"

        # Significant result
        if n < self.MIN_SAMPLE_ACTIONABLE:
            return f"SIGNIFICANT but low sample ({n} games) - monitor"
        elif n < self.MIN_SAMPLE_CONFIDENT:
            return f"ACTIONABLE EDGE ({rate:.1%} over {n} games, ROI: {roi:+.1%})"
        else:
            return f"HIGH-CONFIDENCE EDGE ({rate:.1%} over {n} games, ROI: {roi:+.1%})"

    def test_from_dataframe(
        self,
        df: pd.DataFrame,
        edge_name: str,
        filter_col: str,
        filter_value,
        result_col: str = 'covered_spread',
    ) -> HypothesisResult:
        """
        Test an edge from a DataFrame.

        Args:
            df: DataFrame with game results
            edge_name: Name for this edge test
            filter_col: Column to filter on
            filter_value: Value to filter for
            result_col: Column with 0/1 results

        Returns:
            HypothesisResult
        """
        filtered = df[df[filter_col] == filter_value]
        wins = filtered[result_col].sum()
        losses = len(filtered) - wins

        return self.test_edge(edge_name, int(wins), int(losses))

    def test_pivot_edge(
        self,
        df: pd.DataFrame,
        edge_name: str,
        group_cols: List[str],
        result_col: str = 'covered_spread',
    ) -> pd.DataFrame:
        """
        Test edges across a pivot table of conditions.

        Args:
            df: DataFrame with game results
            edge_name: Base name for edges
            group_cols: Columns to group by
            result_col: Column with 0/1 results

        Returns:
            DataFrame with test results for each group
        """
        results = []

        grouped = df.groupby(group_cols)

        for name, group in grouped:
            if isinstance(name, tuple):
                group_name = f"{edge_name}: {' / '.join(str(n) for n in name)}"
            else:
                group_name = f"{edge_name}: {name}"

            wins = group[result_col].sum()
            losses = len(group) - wins

            result = self.test_edge(group_name, int(wins), int(losses))
            results.append({
                'group': name,
                'n': result.sample_size,
                'win_rate': result.observed_rate,
                'p_value': result.p_value,
                'ci_lower': result.ci_lower,
                'ci_upper': result.ci_upper,
                'significant': result.is_significant,
                'roi': result.roi_estimate,
                'verdict': result.verdict,
            })

        return pd.DataFrame(results)

    def apply_fdr_correction(self) -> List[HypothesisResult]:
        """
        Apply Benjamini-Hochberg FDR correction to all results.

        This controls the false discovery rate when testing multiple edges.

        Returns:
            List of results with adjusted significance
        """
        if not self.results:
            return []

        # Sort by p-value
        sorted_results = sorted(self.results, key=lambda x: x.p_value)
        n = len(sorted_results)

        # Calculate BH threshold for each
        adjusted_results = []
        for i, result in enumerate(sorted_results):
            rank = i + 1
            bh_threshold = (rank / n) * self.alpha

            # Adjust significance
            adjusted_significant = result.p_value <= bh_threshold

            # Create new result with adjusted significance
            adjusted = HypothesisResult(
                edge_name=result.edge_name,
                sample_size=result.sample_size,
                successes=result.successes,
                observed_rate=result.observed_rate,
                null_rate=result.null_rate,
                p_value=result.p_value,
                ci_lower=result.ci_lower,
                ci_upper=result.ci_upper,
                is_significant=adjusted_significant,
                effect_size=result.effect_size,
                verdict=result.verdict if adjusted_significant else "NOT SIGNIFICANT (FDR corrected)",
                roi_estimate=result.roi_estimate,
            )
            adjusted_results.append(adjusted)

        return adjusted_results

    def summary_report(self) -> str:
        """Generate summary report of all tested edges."""
        if not self.results:
            return "No edges tested yet."

        lines = []
        lines.append("=" * 80)
        lines.append("EDGE HYPOTHESIS TESTING SUMMARY")
        lines.append("=" * 80)

        # Apply FDR correction
        corrected = self.apply_fdr_correction()

        # Significant edges
        significant = [r for r in corrected if r.is_significant]
        lines.append(f"\nSignificant edges (FDR-corrected): {len(significant)}/{len(corrected)}")

        if significant:
            lines.append("\nACTIONABLE EDGES:")
            lines.append("-" * 60)
            for r in sorted(significant, key=lambda x: -x.roi_estimate):
                lines.append(f"\n{r.edge_name}")
                lines.append(f"  Rate: {r.observed_rate:.1%} ({r.successes}/{r.sample_size})")
                lines.append(f"  95% CI: [{r.ci_lower:.1%}, {r.ci_upper:.1%}]")
                lines.append(f"  p-value: {r.p_value:.4f}")
                lines.append(f"  ROI: {r.roi_estimate:+.1%}")
                lines.append(f"  Effect size (Cohen's h): {r.effect_size:.3f}")

        # Non-significant
        non_sig = [r for r in corrected if not r.is_significant]
        if non_sig:
            lines.append("\n\nNOT SIGNIFICANT (after FDR correction):")
            lines.append("-" * 60)
            for r in non_sig:
                lines.append(f"  {r.edge_name}: {r.observed_rate:.1%} (n={r.sample_size}, p={r.p_value:.3f})")

        lines.append("\n" + "=" * 80)
        lines.append("Note: Always combine statistical significance with practical significance.")
        lines.append("An edge with 55% rate may not be worth transaction costs and time.")
        lines.append("=" * 80)

        return "\n".join(lines)


def validate_historical_edges(games_df: pd.DataFrame) -> Dict[str, HypothesisResult]:
    """
    Validate claimed historical edges against actual data.

    Tests the edges we claim exist (divisional underdogs, etc.)
    against the provided historical data.

    Args:
        games_df: DataFrame with historical game results
            Must have: home_team, away_team, spread_line, home_score, away_score

    Returns:
        Dict of edge_name -> HypothesisResult
    """
    tester = EdgeHypothesisTester()

    # Prepare data
    df = games_df.copy()

    # Calculate if home covered spread
    # spread_line is from home perspective (negative = home favored)
    df['home_margin'] = df['home_score'] - df['away_score']
    df['covered_spread'] = (df['home_margin'] + df['spread_line'] > 0).astype(int)

    # Determine underdogs
    df['home_is_underdog'] = df['spread_line'] > 0

    # Divisional game flag
    def same_division(home, away):
        divisions = {
            'AFC East': ['BUF', 'MIA', 'NE', 'NYJ'],
            'AFC North': ['BAL', 'CIN', 'CLE', 'PIT'],
            'AFC South': ['HOU', 'IND', 'JAX', 'TEN'],
            'AFC West': ['DEN', 'KC', 'LAC', 'LV'],
            'NFC East': ['DAL', 'NYG', 'PHI', 'WAS'],
            'NFC North': ['CHI', 'DET', 'GB', 'MIN'],
            'NFC South': ['ATL', 'CAR', 'NO', 'TB'],
            'NFC West': ['ARI', 'LAR', 'SEA', 'SF'],
        }
        for teams in divisions.values():
            if home in teams and away in teams:
                return True
        return False

    df['is_divisional'] = df.apply(
        lambda x: same_division(x['home_team'], x['away_team']), axis=1
    )

    # Calculate underdog covered (from underdog perspective)
    df['underdog_covered'] = np.where(
        df['home_is_underdog'],
        df['covered_spread'],  # Home underdog covered when home covers
        1 - df['covered_spread']  # Away underdog covered when home doesn't cover
    )

    results = {}

    # Test 1: Divisional Underdogs (claimed 71% ATS)
    div_underdogs = df[df['is_divisional'] & (df['spread_line'].abs() >= 2.5)]
    if len(div_underdogs) > 0:
        wins = div_underdogs['underdog_covered'].sum()
        losses = len(div_underdogs) - wins
        results['divisional_underdog'] = tester.test_edge(
            "Divisional Underdog (+2.5 or more)",
            int(wins), int(losses)
        )

    # Test 2: Home Underdog in Division (claimed 56%)
    home_div_dogs = df[df['is_divisional'] & df['home_is_underdog']]
    if len(home_div_dogs) > 0:
        wins = home_div_dogs['covered_spread'].sum()
        losses = len(home_div_dogs) - wins
        results['home_underdog_division'] = tester.test_edge(
            "Home Underdog in Division",
            int(wins), int(losses)
        )

    # Test 3: Big underdogs (7+ points)
    big_dogs = df[df['spread_line'].abs() >= 7]
    if len(big_dogs) > 0:
        wins = big_dogs['underdog_covered'].sum()
        losses = len(big_dogs) - wins
        results['big_underdog'] = tester.test_edge(
            "Big Underdog (+7 or more)",
            int(wins), int(losses)
        )

    # Test 4: Home favorites laying 3-7 (market tends to overprice)
    home_mid_fav = df[(df['spread_line'] >= -7) & (df['spread_line'] <= -3)]
    if len(home_mid_fav) > 0:
        wins = home_mid_fav['covered_spread'].sum()
        losses = len(home_mid_fav) - wins
        results['home_favorite_3_to_7'] = tester.test_edge(
            "Home Favorite -3 to -7",
            int(wins), int(losses)
        )

    # Print summary
    print(tester.summary_report())

    return results


def quick_pivot_analysis(
    games_df: pd.DataFrame,
    pivot_cols: List[str] = ['is_divisional', 'home_is_underdog'],
    result_col: str = 'covered_spread',
) -> pd.DataFrame:
    """
    Quick pivot table analysis for edge exploration.

    "If it doesn't show up in the pivot table, your ML model is lying."

    Args:
        games_df: DataFrame with game data
        pivot_cols: Columns to pivot on
        result_col: Result column (0/1)

    Returns:
        Pivot table with rates and counts
    """
    df = games_df.copy()

    # Build pivot
    pivot = df.groupby(pivot_cols).agg({
        result_col: ['sum', 'count', 'mean']
    }).round(3)

    pivot.columns = ['wins', 'total', 'rate']
    pivot['losses'] = pivot['total'] - pivot['wins']

    # Add Wilson CI
    pivot['ci_lower'] = pivot.apply(
        lambda x: _wilson_ci_lower(int(x['wins']), int(x['total'])), axis=1
    )
    pivot['ci_upper'] = pivot.apply(
        lambda x: _wilson_ci_upper(int(x['wins']), int(x['total'])), axis=1
    )

    # Add significance flag
    pivot['beats_market'] = pivot['ci_lower'] > 0.50

    return pivot


def _wilson_ci_lower(k: int, n: int) -> float:
    """Wilson CI lower bound."""
    if n == 0:
        return 0.0
    z = 1.96
    p = k / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    margin = z * np.sqrt((p * (1 - p) + z**2 / (4 * n)) / n) / denom
    return max(0, center - margin)


def _wilson_ci_upper(k: int, n: int) -> float:
    """Wilson CI upper bound."""
    if n == 0:
        return 1.0
    z = 1.96
    p = k / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    margin = z * np.sqrt((p * (1 - p) + z**2 / (4 * n)) / n) / denom
    return min(1, center + margin)
