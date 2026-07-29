"""Research-only strategy analyst.

The historical agent generated a generic strategy, returned fabricated backtest
metrics, and then marked its own output validated. That self-certification path
is removed. The agent may register hypotheses and blockers, but it cannot create
performance evidence or promote a strategy.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List

from src.agents.base_agent import AgentCapability, BaseAgent
from src.betting.decision_contracts import PAPER_AUTHORITY

logger = logging.getLogger(__name__)


class StrategyAnalystAgent(BaseAgent):
    """Maintain research hypotheses without self-validation authority."""

    def __init__(self) -> None:
        super().__init__(
            agent_id="strategy_analyst_001",
            agent_name="Strategy Analyst Agent",
            capabilities=[
                AgentCapability.REASONING,
                AgentCapability.MEMORY,
                AgentCapability.TOOLS,
                AgentCapability.LEARNING,
            ],
        )
        self.strategies: Dict[str, Dict[str, Any]] = {}
        self.backtest_results: Dict[str, Dict[str, Any]] = {}
        self.register_tool(
            "backtest",
            self._backtest_strategy,
            "Return evidence requirements for an external deterministic backtest",
        )
        self.register_tool(
            "analyze_patterns", self._analyze_patterns, "Register research patterns"
        )
        self.register_tool(
            "calculate_metrics",
            self._calculate_metrics,
            "Read qualified metrics without promoting a strategy",
        )

    async def run(self) -> None:
        logger.info("Strategy Analyst Agent running in research-only mode")
        while self.running:
            await asyncio.sleep(300)

    async def _generate_strategies(self) -> List[Dict[str, Any]]:
        logger.debug("Automatic strategy generation disabled")
        return []

    async def _validate_strategies(self) -> None:
        for strategy in self.strategies.values():
            if strategy.get("status") == "pending_validation":
                strategy["status"] = "research_only"
                strategy["promotion_blockers"] = [
                    "immutable_dataset_and_price_ledger_required",
                    "independent_temporal_holdout_required",
                    "forward_paper_tracking_required",
                ]

    async def _analyze_performance(self) -> None:
        return None

    async def _backtest_strategy(self, strategy: Dict[str, Any]) -> Dict[str, Any]:
        result = {
            "status": "UNVERIFIED",
            "evidence_status": "research_only",
            "roi": None,
            "win_rate": None,
            "sharpe_ratio": None,
            "max_drawdown": None,
            "total_bets": 0,
            "blockers": [
                "no_external_deterministic_backtest_receipt",
                "no_immutable_price_ledger",
                "no_independent_validation",
            ],
            "authority": PAPER_AUTHORITY,
        }
        strategy_id = str(strategy.get("id", "unknown"))
        self.backtest_results[strategy_id] = result
        return result

    async def _analyze_patterns(self, data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "patterns_found": [],
            "confidence": 0.0,
            "evidence_status": "research_only",
            "authority": PAPER_AUTHORITY,
        }

    async def _calculate_metrics(self, strategy: Dict[str, Any]) -> Dict[str, Any]:
        result = strategy.get("backtest_result")
        if not isinstance(result, dict):
            return {
                "status": "UNAVAILABLE",
                "blockers": ["qualified_backtest_result_required"],
                "authority": PAPER_AUTHORITY,
            }
        return {
            "status": result.get("status", "UNVERIFIED"),
            "evidence_status": result.get("evidence_status", "unverified"),
            "roi": result.get("roi"),
            "win_rate": result.get("win_rate"),
            "sharpe_ratio": result.get("sharpe_ratio"),
            "max_drawdown": result.get("max_drawdown"),
            "authority": PAPER_AUTHORITY,
        }
