"""Research-only risk agent with no wagering authority."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional

from src.agents.base_agent import AgentCapability, BaseAgent
from src.betting.decision_contracts import PAPER_AUTHORITY
from src.betting.kelly import KellyCriterion

logger = logging.getLogger(__name__)


class RiskManagementAgent(BaseAgent):
    """Analyze paper fractions and exposure without returning a dollar stake."""

    def __init__(self) -> None:
        super().__init__(
            agent_id="risk_mgmt_001",
            agent_name="Risk Management Agent",
            capabilities=[AgentCapability.REASONING, AgentCapability.TOOLS],
        )
        self.kelly = KellyCriterion(deployment_mode="paper")
        self.register_tool(
            "calculate_bet_size",
            self._calculate_bet_size,
            "Return a blocked zero-stake receipt and optional paper fraction",
        )
        self.register_tool(
            "check_exposure", self._check_exposure, "Report paper exposure"
        )

    async def run(self) -> None:
        while self.running:
            try:
                await self._monitor_risk()
                await asyncio.sleep(300)
            except Exception as exc:
                logger.error("Risk Management error: %s", exc)
                await asyncio.sleep(10)

    async def _calculate_bet_size(
        self,
        bankroll: float,
        edge: float,
        prob: float,
        odds: Optional[float] = None,
        probability_lower_bound: Optional[float] = None,
        evidence_status: str = "unverified",
    ) -> Dict[str, Any]:
        paper_fraction = 0.0
        blockers = ["dollar_sizing_not_authorized"]
        if odds is not None and probability_lower_bound is not None:
            paper_fraction = self.kelly.calculate_fraction(
                prob,
                odds,
                probability_lower_bound=probability_lower_bound,
                evidence_status=evidence_status,
            )
            if paper_fraction == 0.0:
                blockers.append("evidence_or_lower_bound_edge_not_qualified")
        else:
            blockers.append("odds_and_probability_lower_bound_required")

        return {
            "bet_size": 0.0,
            "paper_fraction": paper_fraction,
            "kelly_fraction": self.kelly.kelly_fraction,
            "blocked": True,
            "blockers": blockers,
            "authority": PAPER_AUTHORITY,
            "live_wagers_authorized": False,
            "bankroll_observed": bankroll,
            "point_edge_observed": edge,
        }

    async def _check_exposure(
        self, current_bets: list[Dict[str, Any]], max_paper_exposure: float = 0.0
    ) -> Dict[str, Any]:
        total_exposure = sum(float(item.get("amount", 0.0)) for item in current_bets)
        return {
            "total_paper_exposure": total_exposure,
            "max_paper_exposure": max_paper_exposure,
            "within_limits": total_exposure <= max_paper_exposure,
            "authority": PAPER_AUTHORITY,
            "live_wagers_authorized": False,
        }

    async def _monitor_risk(self) -> None:
        logger.debug("Research-only risk monitor active")
