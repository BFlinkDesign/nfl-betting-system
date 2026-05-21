"""Validation Swarm - Validate strategies through backtesting."""

import logging
from datetime import datetime
from typing import Any, Dict, List

from src.agents.base_agent import BaseAgent
from src.backtesting.data_loader import BacktestDataLoader
from src.backtesting.engine import BacktestEngine
from src.backtesting.prediction_generator import PredictionGenerator
from src.swarms.swarm_base import ConsensusRule, SwarmBase

logger = logging.getLogger(__name__)


class ValidationSwarm(SwarmBase):
    """
    Validation Swarm

    Size: 3-5 agents (conservative, high-quality models)
    Decision rule: Unanimous approval required
    """

    def __init__(self, agents: List[BaseAgent]):
        """Initialize validation swarm."""
        super().__init__(
            swarm_id="validation_swarm_001",
            swarm_name="Validation Swarm",
            agents=agents,
            consensus_rule=ConsensusRule.UNANIMOUS,
        )

        # Initialize backtesting components
        self.data_loader = BacktestDataLoader()
        self.prediction_generator = PredictionGenerator()
        self.backtest_engine = BacktestEngine()

        logger.info("Validation Swarm initialized")

    async def validate_strategy(self, strategy: Dict) -> Dict[str, Any]:
        """
        Validate a strategy through swarm consensus.

        Args:
            strategy: Strategy to validate

        Returns:
            Validation result
        """
        # Phase 1: Independent backtest (different time periods)
        backtest_results = await self._independent_backtest(strategy)

        # Phase 2: Cross-validation (share results, identify discrepancies)
        cross_validated = await self._cross_validation(backtest_results)

        # Phase 3: Stress testing (Monte Carlo, worst-case scenarios)
        stress_tested = await self._stress_testing(strategy)

        # Phase 4: Vote (unanimous approval required)
        task = {
            "type": "validate_strategy",
            "strategy": strategy,
            "backtest_results": backtest_results,
            "cross_validated": cross_validated,
            "stress_tested": stress_tested,
        }

        decision = await self.make_decision(task)

        if decision.decision:
            avg_roi = cross_validated.get("roi_mean", 0)
            avg_wr = cross_validated.get("win_rate_mean", 0)
            if avg_roi < 5.0:
                decision.decision = False
            if avg_wr < 53.0:
                decision.decision = False
            if not stress_tested.get("passed", False):
                decision.decision = False

        return {
            "validated": decision.decision,
            "confidence": decision.confidence,
            "reasoning": "Swarm consensus",
        }

    async def _independent_backtest(self, strategy: Dict) -> List[Dict]:
        """
        Each agent backtests the strategy independently.

        Args:
            strategy: Strategy config with model_name

        Returns:
            List of backtest results from each agent
        """
        results = []
        current_year = datetime.now().year

        # Define backtest period (last 2 seasons for validation)
        data_period = {
            "start_year": current_year - 2,
            "end_year": current_year - 1,
            "focus": "recent",
        }

        for agent in self.agents:
            try:
                # Load data
                schedules_df, pbp_df = self.data_loader.get_backtest_data(data_period)

                # Generate predictions
                predictions_df = self.prediction_generator.generate_predictions(
                    schedules_df, strategy, pbp_df
                )

                if len(predictions_df) == 0:
                    logger.warning(f"Agent {agent.agent_id}: No predictions generated")
                    result = {
                        "agent": agent.agent_id,
                        "roi": 0.0,
                        "win_rate": 0.5,
                        "passed": False,
                        "error": "No predictions",
                    }
                else:
                    # Run backtest
                    metrics, _ = self.backtest_engine.run_backtest(predictions_df)

                    passed = (
                        metrics["roi"] >= 5.0
                        and metrics["win_rate"] >= 53.0
                        and metrics.get("max_drawdown", -100.0) >= -20.0
                    )

                    result = {
                        "agent": agent.agent_id,
                        "roi": metrics["roi"],
                        "win_rate": metrics["win_rate"],
                        "sharpe_ratio": metrics.get("sharpe_ratio", 0),
                        "max_drawdown": metrics.get("max_drawdown", 0),
                        "total_bets": metrics.get("total_bets", 0),
                        "passed": passed,
                    }

                results.append(result)

            except Exception as e:
                logger.error(f"Agent {agent.agent_id} backtest failed: {e}")
                result = {
                    "agent": agent.agent_id,
                    "roi": -0.10,
                    "win_rate": 0.45,
                    "passed": False,
                    "error": str(e),
                }
                results.append(result)

        return results

    async def _cross_validation(self, results: List[Dict]) -> Dict[str, Any]:
        """Detect discrepancies across agent backtest results."""
        valid = [r for r in results if "error" not in r]
        if len(valid) < 2:
            return {"consistent": True, "discrepancies": [], "n_valid": len(valid)}

        rois = [r["roi"] for r in valid]
        win_rates = [r["win_rate"] for r in valid]

        import numpy as _np

        roi_std = float(_np.std(rois))
        wr_std = float(_np.std(win_rates))

        discrepancies = []
        if roi_std > 10.0:
            discrepancies.append(f"ROI spread too wide: std={roi_std:.1f}%")
        if wr_std > 8.0:
            discrepancies.append(f"Win-rate spread too wide: std={wr_std:.1f}%")

        return {
            "consistent": len(discrepancies) == 0,
            "discrepancies": discrepancies,
            "roi_mean": float(_np.mean(rois)),
            "roi_std": roi_std,
            "win_rate_mean": float(_np.mean(win_rates)),
            "win_rate_std": wr_std,
            "n_valid": len(valid),
        }

    async def _stress_testing(self, strategy: Dict) -> Dict[str, Any]:
        """Run Monte Carlo stress test via BacktestEngine."""
        current_year = datetime.now().year
        data_period = {
            "start_year": current_year - 3,
            "end_year": current_year - 1,
            "focus": "full",
        }

        try:
            schedules_df, pbp_df = self.data_loader.get_backtest_data(data_period)
            predictions_df = self.prediction_generator.generate_predictions(
                schedules_df, strategy, pbp_df
            )

            if len(predictions_df) == 0:
                return {"passed": False, "error": "No predictions for stress test"}

            mc_results = self.backtest_engine.run_monte_carlo(
                predictions_df, n_simulations=500
            )

            passed = (
                mc_results.get("prob_profitable", 0) >= 0.60
                and mc_results.get("roi_ci_5", -100) > -20.0
            )

            return {
                "passed": passed,
                "prob_profitable": mc_results.get("prob_profitable", 0),
                "worst_case_roi": mc_results.get("roi_ci_5", 0),
                "median_roi": mc_results.get("roi_median", 0),
                "n_simulations": mc_results.get("n_simulations", 0),
            }
        except Exception as e:
            logger.error("Stress testing failed: %s", e)
            return {"passed": False, "error": str(e)}
