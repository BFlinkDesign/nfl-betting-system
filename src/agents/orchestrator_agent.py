"""
Orchestrator Agent (Level 1)

Strategic planning and coordination agent with authority over all other agents.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List

from src.agents.base_agent import AgentCapability, AgentMessage, BaseAgent
from src.agents.message_bus import message_bus

logger = logging.getLogger(__name__)


class OrchestratorAgent(BaseAgent):
    """
    Orchestrator Agent - Level 1

    Responsibilities:
    - Strategic planning (season-level decisions)
    - Agent coordination & conflict resolution
    - Performance monitoring & agent promotion/demotion
    - Resource allocation across agents
    - Meta-learning (improve system itself)

    Authority: Can override any agent decision
    """

    def __init__(self):
        """Initialize orchestrator agent."""
        super().__init__(
            agent_id="orchestrator_001",
            agent_name="Orchestrator Agent",
            capabilities=[
                AgentCapability.REASONING,
                AgentCapability.MEMORY,
                AgentCapability.COMMUNICATION,
                AgentCapability.LEARNING,
            ],
        )

        # Strategic state
        self.season_plan: Dict[str, Any] = {}
        self.agent_performance: Dict[str, Dict[str, Any]] = {}
        self.resource_allocation: Dict[str, float] = {}

        # Decision history
        self.decisions: List[Dict[str, Any]] = []

        logger.info("Orchestrator Agent initialized")

    async def run(self):
        """Main orchestrator loop."""
        logger.info("Orchestrator Agent started")

        while self.running:
            try:
                # Strategic planning cycle
                await self._strategic_planning()

                # Monitor agent performance
                await self._monitor_agents()

                # Resolve conflicts
                await self._resolve_conflicts()

                # Meta-learning
                await self._meta_learning()

                # Wait before next cycle
                await asyncio.sleep(60)  # 1 minute cycles

            except Exception as e:
                logger.error(f"Orchestrator error: {e}")
                await asyncio.sleep(10)

    async def _strategic_planning(self):
        """Perform strategic planning."""
        logger.debug("Orchestrator: Strategic planning")

        # Update season plan
        current_week = datetime.now().isocalendar()[1]
        self.season_plan["current_week"] = current_week
        self.season_plan["last_updated"] = datetime.now().isoformat()

        # Strategic decisions would go here
        # For now, just log
        self.update_memory("last_strategic_plan", datetime.now().isoformat())

    async def _monitor_agents(self):
        """Monitor performance of all agents."""
        logger.debug("Orchestrator: Monitoring agents")

        # Send heartbeat to all agents
        heartbeat = AgentMessage(
            sender_id=self.agent_id,
            receiver_id="*",
            message_type="heartbeat",
            content={"request_status": True},
        )
        await message_bus.broadcast(heartbeat)

        # Collect performance metrics
        # In real implementation, would query agent registry

    async def _resolve_conflicts(self):
        """Resolve conflicts between agents."""
        logger.debug("Orchestrator: Resolving conflicts")

        # Check for conflicting decisions
        # In real implementation, would analyze message history

    async def _meta_learning(self):
        """Learn and improve the system."""
        logger.debug("Orchestrator: Meta-learning")

        # Analyze decision outcomes
        # Update strategies based on results
        # In real implementation, would use ML/analytics

    async def handle_message(self, message: AgentMessage):
        """Handle messages (override base)."""
        await super().handle_message(message)

        if message.message_type == "proposal":
            # Evaluate proposal from another agent
            await self._evaluate_proposal(message)

        elif message.message_type == "alert":
            # Handle alerts
            await self._handle_alert(message)

        elif message.message_type == "request":
            # Handle requests for authority
            await self._handle_authority_request(message)

    async def _evaluate_proposal(self, message: AgentMessage):
        """Evaluate a proposal — reject if missing required fields."""
        proposal = message.content.get("proposal", {})
        proposal_type = proposal.get("type", "unknown")
        logger.info(
            "Evaluating proposal from %s: %s", message.sender_id, proposal_type
        )

        approved = True
        reason = "Approved"

        if not proposal.get("type"):
            approved = False
            reason = "Rejected: missing proposal type"

        metrics = proposal.get("metrics", {})
        if metrics.get("roi", 100) < 0:
            approved = False
            reason = f"Rejected: negative ROI ({metrics.get('roi')})"

        self.decisions.append(
            {
                "timestamp": datetime.now().isoformat(),
                "type": "proposal_review",
                "source_agent": message.sender_id,
                "approved": approved,
                "reason": reason,
            }
        )

        response = AgentMessage(
            sender_id=self.agent_id,
            receiver_id=message.sender_id,
            message_type="response",
            content={"approved": approved, "reason": reason},
            parent_id=message.message_id,
        )
        await message_bus.send(response)

    async def _handle_alert(self, message: AgentMessage):
        """Handle alert — log and escalate critical alerts."""
        alert = message.content.get("alert", {})
        severity = alert.get("severity", "info")
        alert_msg = alert.get("message", "Unknown")

        if severity == "critical":
            logger.critical(
                "CRITICAL alert from %s: %s", message.sender_id, alert_msg
            )
            pause_cmd = AgentMessage(
                sender_id=self.agent_id,
                receiver_id=message.sender_id,
                message_type="command",
                content={"action": "pause", "reason": f"Critical alert: {alert_msg}"},
            )
            await message_bus.send(pause_cmd)
        else:
            logger.warning("Alert from %s: %s", message.sender_id, alert_msg)

    async def _handle_authority_request(self, message: AgentMessage):
        """Handle request for authority override — grant standard only."""
        response = AgentMessage(
            sender_id=self.agent_id,
            receiver_id=message.sender_id,
            message_type="command",
            content={"authorized": True, "authority_level": "standard"},
            parent_id=message.message_id,
        )
        await message_bus.send(response)

    async def override_decision(self, agent_id: str, decision: Dict[str, Any]):
        """Override an agent's decision (orchestrator authority)."""
        command = AgentMessage(
            sender_id=self.agent_id,
            receiver_id=agent_id,
            message_type="command",
            content={"action": "override", "decision": decision},
        )
        await message_bus.send(command)

        logger.info("Orchestrator overriding decision from %s", agent_id)

        self.decisions.append(
            {
                "timestamp": datetime.now().isoformat(),
                "type": "override",
                "target_agent": agent_id,
                "decision": decision,
            }
        )
