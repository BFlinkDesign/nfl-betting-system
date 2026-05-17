"""Advanced Copula Modeling for SGP Correlations

Implements multiple correlation modeling approaches:
1. Empirical Correlation (baseline)
2. Gaussian Copula (bivariate)
3. Multivariate Gaussian Copula (3+ legs)
4. Simplified Vine Copula structure

Used by sportsbooks for accurate SGP pricing.
"""

import numpy as np
from scipy.stats import norm, multivariate_normal, pearsonr, spearmanr
from typing import List, Dict, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class GaussianCopula:
    """
    Bivariate Gaussian Copula for 2-leg SGPs.

    The professional method sportsbooks use:
    1. Convert probabilities to normal distribution values (inverse CDF)
    2. Apply correlation in normal space
    3. Convert back to joint probability
    """

    @staticmethod
    def joint_probability(prob1: float, prob2: float, correlation: float) -> float:
        """
        Calculate joint probability using Gaussian Copula.

        Args:
            prob1: Probability of first event (e.g., QB over 250 passing yards)
            prob2: Probability of second event (e.g., WR over 80 receiving yards)
            correlation: Correlation between events (-1 to 1)

        Returns:
            Joint probability of both events occurring
        """
        # Bound inputs
        prob1 = np.clip(prob1, 0.001, 0.999)
        prob2 = np.clip(prob2, 0.001, 0.999)
        correlation = np.clip(correlation, -0.99, 0.99)

        # Step 1: Convert to standard normal (inverse CDF)
        z1 = norm.ppf(prob1)
        z2 = norm.ppf(prob2)

        # Step 2: Create covariance matrix
        cov = [[1, correlation], [correlation, 1]]

        # Step 3: Calculate joint probability using bivariate normal CDF
        joint_cdf = multivariate_normal.cdf([z1, z2], mean=[0, 0], cov=cov)

        return float(joint_cdf)

    @staticmethod
    def compare_methods(prob1: float, prob2: float, correlation: float) -> Dict[str, float]:
        """Compare different joint probability methods."""
        # Independent (no correlation)
        independent = prob1 * prob2

        # Simple linear adjustment
        simple = prob1 * prob2 + correlation * np.sqrt(
            prob1 * (1 - prob1) * prob2 * (1 - prob2)
        )

        # Gaussian Copula
        copula = GaussianCopula.joint_probability(prob1, prob2, correlation)

        return {
            'independent': independent,
            'simple_linear': simple,
            'gaussian_copula': copula,
            'copula_vs_independent': copula - independent,
            'copula_boost_pct': (copula / independent - 1) * 100 if independent > 0 else 0,
        }


class MultivariateGaussianCopula:
    """
    Multivariate Gaussian Copula for 3+ leg SGPs.

    Handles complex dependency structures across multiple props.
    """

    @staticmethod
    def joint_probability(
        probabilities: List[float],
        correlation_matrix: np.ndarray
    ) -> float:
        """
        Calculate joint probability for 3+ events.

        Args:
            probabilities: List of individual probabilities [p1, p2, p3, ...]
            correlation_matrix: Correlation matrix (must be positive semi-definite)

        Returns:
            Joint probability of all events occurring
        """
        n = len(probabilities)

        if n != correlation_matrix.shape[0]:
            raise ValueError("Probabilities and correlation matrix dimensions must match")

        # Bound probabilities
        probs = [np.clip(p, 0.001, 0.999) for p in probabilities]

        # Convert to standard normal variables
        z_values = [norm.ppf(p) for p in probs]

        # Ensure correlation matrix is valid
        corr_matrix = MultivariateGaussianCopula._ensure_positive_definite(correlation_matrix)

        # Calculate multivariate cumulative distribution
        joint_prob = multivariate_normal.cdf(
            x=z_values,
            mean=np.zeros(n),
            cov=corr_matrix
        )

        return float(joint_prob)

    @staticmethod
    def _ensure_positive_definite(matrix: np.ndarray) -> np.ndarray:
        """Ensure correlation matrix is positive semi-definite."""
        # Check if already valid
        try:
            np.linalg.cholesky(matrix)
            return matrix
        except np.linalg.LinAlgError:
            # Fix using eigenvalue decomposition
            eigenvalues, eigenvectors = np.linalg.eigh(matrix)
            eigenvalues = np.maximum(eigenvalues, 1e-6)
            fixed = eigenvectors @ np.diag(eigenvalues) @ eigenvectors.T
            # Normalize to correlation matrix
            d = np.sqrt(np.diag(fixed))
            fixed = fixed / np.outer(d, d)
            np.fill_diagonal(fixed, 1.0)
            return fixed

    @staticmethod
    def build_correlation_matrix(correlations: Dict[Tuple[int, int], float], n: int) -> np.ndarray:
        """
        Build correlation matrix from pairwise correlations.

        Args:
            correlations: Dict mapping (i, j) pairs to correlation values
            n: Number of variables

        Returns:
            n x n correlation matrix
        """
        matrix = np.eye(n)
        for (i, j), corr in correlations.items():
            matrix[i, j] = corr
            matrix[j, i] = corr
        return matrix


class VineCopulaSimplified:
    """
    Simplified Vine Copula implementation.

    Vine Copulas are state-of-the-art for high-dimensional dependence.
    This is a simplified D-vine structure that's practical to implement.
    """

    # Different copula families for different dependency types
    COPULA_FAMILIES = {
        'gaussian': 'Symmetric dependence',
        'clayton': 'Lower tail dependence (both do poorly together)',
        'gumbel': 'Upper tail dependence (both do well together)',
        'frank': 'No tail dependence, symmetric',
    }

    @staticmethod
    def d_vine_probability(
        probabilities: List[float],
        pairwise_correlations: List[float],
    ) -> float:
        """
        Calculate joint probability using D-Vine structure.

        D-Vine connects variables in a chain: 1-2-3-4-...

        Args:
            probabilities: List of marginal probabilities
            pairwise_correlations: Correlations [r12, r23, r34, ...]

        Returns:
            Joint probability approximation
        """
        n = len(probabilities)

        if n < 2:
            return probabilities[0] if probabilities else 0.0

        # Start with first pair
        joint = GaussianCopula.joint_probability(
            probabilities[0],
            probabilities[1],
            pairwise_correlations[0] if pairwise_correlations else 0.0
        )

        # Add subsequent variables
        for i in range(2, n):
            corr = pairwise_correlations[i-1] if i-1 < len(pairwise_correlations) else 0.0

            # Conditional probability approximation
            conditional_prob = joint * probabilities[i]

            # Adjust for correlation
            adjustment = 1 + corr * (1 - joint) * (1 - probabilities[i])
            joint = conditional_prob * adjustment

            # Bound result
            joint = np.clip(joint, 0.001, 0.999)

        return float(joint)


class CorrelationDiscovery:
    """
    Discover hidden correlations from historical data.
    """

    @staticmethod
    def calculate_empirical_correlation(
        data1: np.ndarray,
        data2: np.ndarray,
        method: str = 'pearson'
    ) -> Tuple[float, float]:
        """
        Calculate empirical correlation with significance.

        Returns: (correlation, p_value)
        """
        # Remove NaN
        mask = ~(np.isnan(data1) | np.isnan(data2))
        d1, d2 = data1[mask], data2[mask]

        if len(d1) < 10:
            return 0.0, 1.0

        if method == 'pearson':
            return pearsonr(d1, d2)
        elif method == 'spearman':
            return spearmanr(d1, d2)
        else:
            raise ValueError(f"Unknown method: {method}")

    @staticmethod
    def discover_correlations(
        df,
        prop_columns: List[str],
        groupby: str = 'game_id',
        min_samples: int = 30,
    ) -> Dict[Tuple[str, str], Dict]:
        """
        Discover correlations between prop outcomes.

        Returns dict with correlation, p-value, sample size, and significance.
        """
        results = {}

        for i, col1 in enumerate(prop_columns):
            for col2 in prop_columns[i+1:]:
                # Get paired observations
                if col1 in df.columns and col2 in df.columns:
                    data1 = df[col1].values
                    data2 = df[col2].values

                    corr, pval = CorrelationDiscovery.calculate_empirical_correlation(
                        data1, data2
                    )

                    n_samples = (~(np.isnan(data1) | np.isnan(data2))).sum()

                    if n_samples >= min_samples:
                        results[(col1, col2)] = {
                            'correlation': corr,
                            'p_value': pval,
                            'n_samples': n_samples,
                            'significant': pval < 0.05,
                            'strength': 'high' if abs(corr) > 0.5 else 'moderate' if abs(corr) > 0.25 else 'low',
                        }

        return results


def run_copula_comparison():
    """Run comprehensive comparison of copula methods."""
    print("=" * 70)
    print("COPULA METHOD COMPARISON")
    print("=" * 70)

    # Test cases
    test_cases = [
        ("QB + WR (high corr)", 0.58, 0.55, 0.72),
        ("RB Rushing + Receiving", 0.60, 0.52, 0.40),
        ("Two WRs same team", 0.55, 0.50, 0.15),
        ("RB vs QB (negative)", 0.58, 0.55, -0.35),
        ("Low confidence props", 0.51, 0.51, 0.30),
    ]

    print("\n2-LEG SGP COMPARISONS:")
    print("-" * 70)

    for name, p1, p2, corr in test_cases:
        results = GaussianCopula.compare_methods(p1, p2, corr)
        print(f"\n{name}:")
        print(f"  P1={p1:.0%}, P2={p2:.0%}, Correlation={corr:+.2f}")
        print(f"  Independent:      {results['independent']:.2%}")
        print(f"  Simple Linear:    {results['simple_linear']:.2%}")
        print(f"  Gaussian Copula:  {results['gaussian_copula']:.2%}")
        print(f"  Copula Boost:     {results['copula_boost_pct']:+.1f}%")

    # 3-4 leg SGP comparison
    print("\n" + "=" * 70)
    print("MULTIVARIATE SGP COMPARISONS (3-4 legs)")
    print("-" * 70)

    # 3-leg example: QB + WR + TD
    probs_3 = [0.58, 0.55, 0.35]  # QB yards, WR yards, Anytime TD
    corr_3 = np.array([
        [1.00, 0.72, 0.45],
        [0.72, 1.00, 0.55],
        [0.45, 0.55, 1.00],
    ])

    independent_3 = np.prod(probs_3)
    copula_3 = MultivariateGaussianCopula.joint_probability(probs_3, corr_3)

    print(f"\n3-Leg SGP (QB Yards + WR Yards + Anytime TD):")
    print(f"  Probabilities: {[f'{p:.0%}' for p in probs_3]}")
    print(f"  Independent:        {independent_3:.3%}")
    print(f"  Multivariate Copula: {copula_3:.3%}")
    print(f"  Copula Boost:       {(copula_3/independent_3 - 1)*100:+.1f}%")

    # EV comparison
    payout_3 = 5.5  # Typical 3-leg payout
    ev_ind = (independent_3 * payout_3) - 1
    ev_cop = (copula_3 * payout_3) - 1
    print(f"  EV (independent):   {ev_ind:+.1%}")
    print(f"  EV (copula):        {ev_cop:+.1%}")

    # 4-leg example: QB + WR + RB + TD
    probs_4 = [0.58, 0.55, 0.60, 0.35]
    corr_4 = np.array([
        [1.00, 0.72, -0.35, 0.45],  # QB
        [0.72, 1.00, 0.28, 0.55],   # WR
        [-0.35, 0.28, 1.00, 0.42],  # RB
        [0.45, 0.55, 0.42, 1.00],   # TD
    ])

    independent_4 = np.prod(probs_4)
    copula_4 = MultivariateGaussianCopula.joint_probability(probs_4, corr_4)

    print(f"\n4-Leg SGP (QB + WR + RB + TD):")
    print(f"  Probabilities: {[f'{p:.0%}' for p in probs_4]}")
    print(f"  Independent:        {independent_4:.3%}")
    print(f"  Multivariate Copula: {copula_4:.3%}")
    print(f"  Copula Boost:       {(copula_4/independent_4 - 1)*100:+.1f}%")

    # Note the NEGATIVE correlation effect
    print(f"  Note: RB-QB negative correlation REDUCES joint prob")

    # Vine copula comparison
    print("\n" + "=" * 70)
    print("VINE COPULA COMPARISON")
    print("-" * 70)

    probs_vine = [0.58, 0.55, 0.60, 0.35]
    corrs_vine = [0.72, 0.28, 0.42]  # Chain: QB-WR-RB-TD

    vine_prob = VineCopulaSimplified.d_vine_probability(probs_vine, corrs_vine)

    print(f"\n4-Leg D-Vine (Chain: QB→WR→RB→TD):")
    print(f"  Vine Copula:        {vine_prob:.3%}")
    print(f"  vs Multivariate:    {copula_4:.3%}")
    print(f"  Difference:         {(vine_prob - copula_4)*100:+.2f}pp")


if __name__ == "__main__":
    run_copula_comparison()
