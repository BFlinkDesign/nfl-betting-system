"""
Start Autonomous Betting System

Main entry point for the autonomous system.
Starts all agents, swarms, and monitoring systems.
"""

import asyncio
import logging
import os
import signal
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from src.config.logging_config import setup_logging
from src.config.startup import startup_check
from src.utils.leader_lease import LeaderLease

setup_logging(
    level=os.environ.get("LOG_LEVEL", "INFO"),
    json_format=os.environ.get("LOG_FORMAT") == "json",
)
logger = logging.getLogger(__name__)

from agents.api_integrations import TheOddsAPI
from src.agents import (
    DataEngineeringAgent,
    MarketIntelligenceAgent,
    OrchestratorAgent,
    PerformanceAnalystAgent,
    RiskManagementAgent,
    StrategyAnalystAgent,
    agent_registry,
    message_bus,
)
from src.agents.worker_agents import (
    APIManagerAgent,
    DatabaseAgent,
    LoggingAgent,
    NotificationAgent,
    SelfHealingAgent,
)
from src.api.request_orchestrator import RequestOrchestrator
from src.audit import SystemConnectivityAuditor
from src.backtesting.ai_orchestrator import AIBacktestOrchestrator
from src.self_healing import AnomalyDetector, AutoRemediation, MonitoringLayer
from src.swarms import ConsensusSwarm, StrategyGenerationSwarm, ValidationSwarm
from src.utils.odds_cache import OddsCache


class AutonomousSystem:
    """Main autonomous system orchestrator."""

    def __init__(self):
        """Initialize autonomous system."""
        logger.info("Initializing Autonomous Betting System...")

        # Infrastructure
        self.cache = OddsCache()
        self.orchestrator = RequestOrchestrator(cache=self.cache)
        self.monitoring = MonitoringLayer()
        self.anomaly_detector = AnomalyDetector(self.monitoring)
        self.auto_remediation = AutoRemediation()
        self.connectivity_auditor = SystemConnectivityAuditor()

        # Agents
        self.orchestrator_agent = OrchestratorAgent()
        self.strategy_analyst = StrategyAnalystAgent()
        odds_api = TheOddsAPI(use_cache=True)
        self.market_intel = MarketIntelligenceAgent(odds_api=odds_api)
        self.data_eng = DataEngineeringAgent()
        self.risk_mgmt = RiskManagementAgent()
        self.perf_analyst = PerformanceAnalystAgent()

        # Worker agents
        self.api_manager = APIManagerAgent(self.orchestrator)
        self.database_agent = DatabaseAgent()
        self.notification_agent = NotificationAgent()
        self.logging_agent = LoggingAgent()
        self.self_healing_agent = SelfHealingAgent()

        # Register all agents
        all_agents = [
            self.orchestrator_agent,
            self.strategy_analyst,
            self.market_intel,
            self.data_eng,
            self.risk_mgmt,
            self.perf_analyst,
            self.api_manager,
            self.database_agent,
            self.notification_agent,
            self.logging_agent,
            self.self_healing_agent,
        ]

        for agent in all_agents:
            agent_registry.register(agent)
            message_bus.subscribe(agent)

        # Swarms
        strategy_agents = [self.strategy_analyst, self.market_intel, self.data_eng]
        validation_agents = [self.strategy_analyst, self.risk_mgmt, self.perf_analyst]
        consensus_agents = all_agents[:7]  # First 7 agents

        self.strategy_swarm = StrategyGenerationSwarm(strategy_agents)
        self.validation_swarm = ValidationSwarm(validation_agents)
        self.consensus_swarm = ConsensusSwarm(consensus_agents)

        # AI Backtest Orchestrator
        self.backtest_orchestrator = AIBacktestOrchestrator(
            strategy_agents, validation_agents
        )

        logger.info("Autonomous system initialized")

    async def start(self):
        """Start all components."""
        logger.info("Starting autonomous system...")

        # Start request orchestrator
        self.orchestrator.start()

        # Start all agents
        tasks = []
        for agent in agent_registry.get_all():
            tasks.append(asyncio.create_task(agent.start()))

        # Start monitoring
        tasks.append(asyncio.create_task(self._monitoring_loop()))

        # Start connectivity auditing
        tasks.append(asyncio.create_task(self.connectivity_auditor.run_continuous()))

        # Start backtesting cycles
        tasks.append(asyncio.create_task(self.backtest_orchestrator.run_continuous()))

        logger.info("Autonomous system started")

        # Wait for all tasks
        await asyncio.gather(*tasks)

    async def _monitoring_loop(self):
        """Continuous monitoring loop."""
        while True:
            try:
                # Collect metrics
                self.monitoring.collect_system_metrics()
                self.monitoring.collect_application_metrics()

                # Detect anomalies
                anomalies = self.anomaly_detector.detect_anomalies()

                # Remediate anomalies
                for anomaly in anomalies:
                    self.auto_remediation.remediate(anomaly)

                await asyncio.sleep(60)  # Check every minute

            except Exception as e:
                logger.error(f"Monitoring error: {e}")
                await asyncio.sleep(10)

    async def stop(self):
        """Stop all components."""
        logger.info("Stopping autonomous system...")

        # Stop agents
        for agent in agent_registry.get_all():
            await agent.stop()

        # Stop orchestrator
        self.orchestrator.stop()

        logger.info("Autonomous system stopped")


async def main():
    """Main entry point with startup validation, leader lease, and graceful shutdown."""
    if not startup_check():
        logger.error("Startup checks failed — aborting")
        sys.exit(1)

    lease = LeaderLease("autonomous_system", ttl_seconds=120)
    if not lease.acquire():
        logger.error("Another instance is running — aborting (lease held)")
        sys.exit(1)

    system = AutonomousSystem()
    shutdown_event = asyncio.Event()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, shutdown_event.set)

    async def _lease_renewer():
        while not shutdown_event.is_set():
            lease.renew()
            await asyncio.sleep(30)

    renew_task = asyncio.create_task(_lease_renewer())

    try:
        start_task = asyncio.create_task(system.start())
        shutdown_wait = asyncio.create_task(shutdown_event.wait())

        done, pending = await asyncio.wait(
            [start_task, shutdown_wait], return_when=asyncio.FIRST_COMPLETED
        )

        if shutdown_event.is_set():
            logger.info("Shutdown signal received — stopping gracefully")
    except Exception as e:
        logger.error("Unhandled error in main: %s", e, exc_info=True)
    finally:
        renew_task.cancel()
        await system.stop()
        lease.release()
        logger.info("Autonomous system exited cleanly")


if __name__ == "__main__":
    asyncio.run(main())
