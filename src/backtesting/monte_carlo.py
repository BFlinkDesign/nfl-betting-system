"""Monte Carlo simulation for variance analysis and risk management.

Provides:
- Bankroll path simulation
- Probability of ruin estimation
- Confidence intervals via bootstrap
- Statistical significance testing

Research basis:
- Kelly criterion optimality (Kelly 1956)
- Sports betting bankroll management (Miller & Davidow)
"""

import logging
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats

logger = logging.getLogger(__name__)


class MonteCarloSimulator:
    """
    Monte Carlo simulation for betting outcomes.

    Key questions answered:
    1. What's the probability of ruin at different Kelly fractions?
    2. What's the expected distribution of final bankroll?
    3. Are observed results statistically significant?
    """

    def __init__(self, random_state: int = 42):
        """
        Initialize simulator.

        Args:
            random_state: Random seed for reproducibility
        """
        self.rng = np.random.default_rng(random_state)

    def simulate_bankroll_paths(
        self,
        win_probability: float,
        odds: float,
        n_bets: int,
        initial_bankroll: float = 10000,
        kelly_fraction: float = 0.25,
        n_simulations: int = 10000,
        ruin_threshold: float = 0.1,
    ) -> Dict:
        """
        Simulate multiple bankroll trajectories.

        Args:
            win_probability: True probability of winning each bet
            odds: Decimal odds for each bet
            n_bets: Number of bets to simulate
            initial_bankroll: Starting bankroll
            kelly_fraction: Fraction of full Kelly to use
            n_simulations: Number of simulation runs
            ruin_threshold: Fraction of bankroll considered "ruin"

        Returns:
            Dict with simulation results
        """
        logger.info(f"Running {n_simulations} simulations of {n_bets} bets each...")

        # Calculate Kelly bet size
        edge = win_probability * odds - 1
        full_kelly = edge / (odds - 1) if odds > 1 else 0
        bet_fraction = full_kelly * kelly_fraction

        if bet_fraction <= 0:
            logger.warning("Negative edge - no bet should be placed")
            return {"error": "Negative edge"}

        # Run simulations
        final_bankrolls = np.zeros(n_simulations)
        ruin_count = 0
        max_drawdowns = np.zeros(n_simulations)
        paths = []

        for sim in range(n_simulations):
            bankroll = initial_bankroll
            peak = initial_bankroll
            max_dd = 0

            # Track first 100 paths for visualization
            if sim < 100:
                path = [bankroll]

            for _ in range(n_bets):
                bet_size = bankroll * bet_fraction

                # Simulate outcome
                if self.rng.random() < win_probability:
                    bankroll += bet_size * (odds - 1)
                else:
                    bankroll -= bet_size

                # Track drawdown
                if bankroll > peak:
                    peak = bankroll
                dd = (peak - bankroll) / peak
                max_dd = max(max_dd, dd)

                # Track path
                if sim < 100:
                    path.append(bankroll)

                # Check for ruin
                if bankroll < initial_bankroll * ruin_threshold:
                    ruin_count += 1
                    break

            final_bankrolls[sim] = bankroll
            max_drawdowns[sim] = max_dd

            if sim < 100:
                paths.append(path)

        # Calculate statistics
        probability_of_ruin = ruin_count / n_simulations
        median_final = np.median(final_bankrolls)
        mean_final = np.mean(final_bankrolls)

        # Percentiles
        percentiles = {
            'p5': np.percentile(final_bankrolls, 5),
            'p25': np.percentile(final_bankrolls, 25),
            'p50': np.percentile(final_bankrolls, 50),
            'p75': np.percentile(final_bankrolls, 75),
            'p95': np.percentile(final_bankrolls, 95),
        }

        # ROI distribution
        roi_distribution = (final_bankrolls - initial_bankroll) / initial_bankroll * 100

        results = {
            'n_simulations': n_simulations,
            'n_bets': n_bets,
            'win_probability': win_probability,
            'odds': odds,
            'edge': edge * 100,  # As percentage
            'kelly_fraction': kelly_fraction,
            'bet_fraction': bet_fraction * 100,

            # Risk metrics
            'probability_of_ruin': probability_of_ruin,
            'median_max_drawdown': np.median(max_drawdowns) * 100,
            'p95_max_drawdown': np.percentile(max_drawdowns, 95) * 100,

            # Return metrics
            'median_final_bankroll': median_final,
            'mean_final_bankroll': mean_final,
            'percentiles': percentiles,

            # ROI
            'median_roi': np.median(roi_distribution),
            'mean_roi': np.mean(roi_distribution),
            'roi_std': np.std(roi_distribution),

            # Paths for visualization
            'sample_paths': paths,
        }

        logger.info(f"Probability of ruin: {probability_of_ruin:.1%}")
        logger.info(f"Median final bankroll: ${median_final:,.0f}")
        logger.info(f"Median ROI: {results['median_roi']:.1f}%")

        return results

    def bootstrap_metrics(
        self,
        history_df: pd.DataFrame,
        n_bootstrap: int = 5000,
        confidence_level: float = 0.95,
    ) -> Dict:
        """
        Bootstrap confidence intervals for backtest metrics.

        Args:
            history_df: Backtest history with 'profit', 'clv', 'bet_size'
            n_bootstrap: Number of bootstrap samples
            confidence_level: Confidence level for intervals

        Returns:
            Dict with confidence intervals for key metrics
        """
        logger.info(f"Bootstrapping {n_bootstrap} samples...")

        n_bets = len(history_df)

        # Storage for bootstrap samples
        roi_samples = np.zeros(n_bootstrap)
        clv_samples = np.zeros(n_bootstrap)
        win_rate_samples = np.zeros(n_bootstrap)
        sharpe_samples = np.zeros(n_bootstrap)

        total_wagered = history_df['bet_size'].sum()
        total_profit = history_df['profit'].sum()

        for i in range(n_bootstrap):
            # Sample with replacement
            sample_idx = self.rng.choice(n_bets, size=n_bets, replace=True)
            sample = history_df.iloc[sample_idx]

            # Calculate metrics
            sample_profit = sample['profit'].sum()
            sample_wagered = sample['bet_size'].sum()

            roi_samples[i] = (sample_profit / sample_wagered) * 100 if sample_wagered > 0 else 0
            clv_samples[i] = sample['clv'].mean() * 100
            win_rate_samples[i] = (sample['profit'] > 0).mean() * 100

            # Sharpe
            returns = sample['profit'] / sample['bet_size']
            sharpe_samples[i] = (returns.mean() / returns.std() * np.sqrt(250)
                                 if returns.std() > 0 else 0)

        # Calculate confidence intervals
        alpha = 1 - confidence_level
        lower_pct = alpha / 2 * 100
        upper_pct = (1 - alpha / 2) * 100

        results = {
            'n_bootstrap': n_bootstrap,
            'confidence_level': confidence_level,

            'roi': {
                'point_estimate': total_profit / total_wagered * 100,
                'ci_lower': np.percentile(roi_samples, lower_pct),
                'ci_upper': np.percentile(roi_samples, upper_pct),
                'std': np.std(roi_samples),
            },
            'clv': {
                'point_estimate': history_df['clv'].mean() * 100,
                'ci_lower': np.percentile(clv_samples, lower_pct),
                'ci_upper': np.percentile(clv_samples, upper_pct),
                'std': np.std(clv_samples),
            },
            'win_rate': {
                'point_estimate': (history_df['profit'] > 0).mean() * 100,
                'ci_lower': np.percentile(win_rate_samples, lower_pct),
                'ci_upper': np.percentile(win_rate_samples, upper_pct),
                'std': np.std(win_rate_samples),
            },
            'sharpe': {
                'point_estimate': sharpe_samples.mean(),
                'ci_lower': np.percentile(sharpe_samples, lower_pct),
                'ci_upper': np.percentile(sharpe_samples, upper_pct),
                'std': np.std(sharpe_samples),
            },
        }

        # Statistical significance
        # CLV significantly > 0?
        clv_pvalue = (clv_samples < 0).mean() * 2  # Two-sided
        results['clv_significant'] = clv_pvalue < (1 - confidence_level)
        results['clv_pvalue'] = clv_pvalue

        logger.info(f"ROI 95% CI: [{results['roi']['ci_lower']:.2f}%, {results['roi']['ci_upper']:.2f}%]")
        logger.info(f"CLV 95% CI: [{results['clv']['ci_lower']:.2f}%, {results['clv']['ci_upper']:.2f}%]")
        logger.info(f"CLV significant: {results['clv_significant']} (p={clv_pvalue:.4f})")

        return results

    def optimal_kelly_search(
        self,
        win_probability: float,
        odds: float,
        n_bets: int = 500,
        initial_bankroll: float = 10000,
        n_simulations: int = 5000,
        max_ruin_probability: float = 0.05,
    ) -> Dict:
        """
        Find optimal Kelly fraction given risk tolerance.

        Searches for the Kelly fraction that maximizes median ROI
        while keeping probability of ruin below threshold.

        Args:
            win_probability: True win probability
            odds: Decimal odds
            n_bets: Number of bets in simulation
            initial_bankroll: Starting bankroll
            n_simulations: Simulations per Kelly fraction
            max_ruin_probability: Maximum acceptable ruin probability

        Returns:
            Dict with optimal Kelly and analysis
        """
        logger.info(f"Searching for optimal Kelly (max ruin prob: {max_ruin_probability:.1%})...")

        kelly_fractions = np.arange(0.05, 1.05, 0.05)
        results = []

        for kf in kelly_fractions:
            sim = self.simulate_bankroll_paths(
                win_probability=win_probability,
                odds=odds,
                n_bets=n_bets,
                initial_bankroll=initial_bankroll,
                kelly_fraction=kf,
                n_simulations=n_simulations,
            )

            results.append({
                'kelly_fraction': kf,
                'median_roi': sim['median_roi'],
                'p5_roi': (sim['percentiles']['p5'] - initial_bankroll) / initial_bankroll * 100,
                'probability_of_ruin': sim['probability_of_ruin'],
                'median_max_drawdown': sim['median_max_drawdown'],
            })

        results_df = pd.DataFrame(results)

        # Find optimal: max median ROI where ruin prob < threshold
        valid = results_df[results_df['probability_of_ruin'] <= max_ruin_probability]

        if len(valid) > 0:
            optimal_idx = valid['median_roi'].idxmax()
            optimal = results_df.loc[optimal_idx]
        else:
            # All have high ruin probability - use lowest
            optimal_idx = results_df['probability_of_ruin'].idxmin()
            optimal = results_df.loc[optimal_idx]
            logger.warning("No Kelly fraction meets ruin constraint - using safest")

        logger.info(f"Optimal Kelly fraction: {optimal['kelly_fraction']:.2f}")
        logger.info(f"  Median ROI: {optimal['median_roi']:.1f}%")
        logger.info(f"  P(Ruin): {optimal['probability_of_ruin']:.1%}")

        return {
            'optimal_kelly_fraction': optimal['kelly_fraction'],
            'optimal_median_roi': optimal['median_roi'],
            'optimal_ruin_probability': optimal['probability_of_ruin'],
            'all_results': results_df.to_dict('records'),
        }


def required_sample_size(
    expected_clv: float,
    clv_std: float,
    confidence: float = 0.95,
    power: float = 0.80,
) -> int:
    """
    Calculate required sample size to detect CLV edge.

    Based on power analysis for one-sample t-test.

    Args:
        expected_clv: Expected average CLV (as decimal, e.g., 0.02 for 2%)
        clv_std: Standard deviation of CLV
        confidence: Confidence level (1 - alpha)
        power: Statistical power (1 - beta)

    Returns:
        Required number of bets
    """
    from scipy.stats import norm

    alpha = 1 - confidence
    beta = 1 - power

    z_alpha = norm.ppf(1 - alpha / 2)
    z_beta = norm.ppf(power)

    effect_size = expected_clv / clv_std

    n = ((z_alpha + z_beta) / effect_size) ** 2

    return int(np.ceil(n))


def print_simulation_report(results: Dict) -> None:
    """Print formatted simulation report."""
    print("\n" + "=" * 70)
    print("MONTE CARLO SIMULATION REPORT")
    print("=" * 70)

    print(f"\nSimulation Parameters:")
    print(f"  Simulations:     {results['n_simulations']:,}")
    print(f"  Bets per sim:    {results['n_bets']:,}")
    print(f"  Win Probability: {results['win_probability']:.1%}")
    print(f"  Odds:            {results['odds']:.2f}")
    print(f"  Edge:            {results['edge']:.2f}%")
    print(f"  Kelly Fraction:  {results['kelly_fraction']:.0%}")
    print(f"  Bet Size:        {results['bet_fraction']:.2f}% of bankroll")

    print(f"\nRisk Metrics:")
    print(f"  P(Ruin):         {results['probability_of_ruin']:.1%}")
    print(f"  Median Max DD:   {results['median_max_drawdown']:.1f}%")
    print(f"  95th pct Max DD: {results['p95_max_drawdown']:.1f}%")

    print(f"\nReturn Metrics:")
    print(f"  Median ROI:      {results['median_roi']:.1f}%")
    print(f"  Mean ROI:        {results['mean_roi']:.1f}%")
    print(f"  ROI Std Dev:     {results['roi_std']:.1f}%")

    print(f"\nFinal Bankroll Distribution (from $10,000):")
    p = results['percentiles']
    print(f"   5th percentile: ${p['p5']:,.0f}")
    print(f"  25th percentile: ${p['p25']:,.0f}")
    print(f"  50th percentile: ${p['p50']:,.0f}")
    print(f"  75th percentile: ${p['p75']:,.0f}")
    print(f"  95th percentile: ${p['p95']:,.0f}")

    print("=" * 70)
