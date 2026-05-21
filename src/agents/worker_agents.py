"""Worker Agents (Level 3) - API Manager, Database, Notification, Logging, Self-Healing."""

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from src.agents.base_agent import AgentCapability, AgentMessage, BaseAgent
from src.api.request_orchestrator import Priority, RequestOrchestrator

logger = logging.getLogger(__name__)


class APIManagerAgent(BaseAgent):
    """API Manager Agent - Rate limiting, caching, retries."""

    def __init__(self, orchestrator: RequestOrchestrator):
        super().__init__(
            agent_id="api_manager_001",
            agent_name="API Manager Agent",
            capabilities=[AgentCapability.TOOLS],
        )
        self.orchestrator = orchestrator
        self.register_tool("queue_request", self._queue_request, "Queue API request")

    async def run(self):
        while self.running:
            await asyncio.sleep(60)

    async def _queue_request(
        self, endpoint: str, params: Dict, priority: Priority = Priority.NORMAL
    ):
        from src.api.request_orchestrator import PriorityRequest

        request = PriorityRequest(
            endpoint=endpoint, params=params, priority=priority, callback=lambda x: None
        )
        return self.orchestrator.enqueue(request)


class DatabaseAgent(BaseAgent):
    """Database Agent - Schema-aware CRUD operations, query optimization."""

    def __init__(self):
        super().__init__(
            agent_id="database_001",
            agent_name="Database Agent",
            capabilities=[AgentCapability.TOOLS, AgentCapability.MEMORY],
        )
        self.db_path = Path("data/odds_history.db")
        self._conn = None
        self._query_builder = None

        # Register tools with schema-aware methods
        self.register_tool("query", self._query, "Query database")
        self.register_tool("store", self._store, "Store data")
        self.register_tool("get_odds", self._get_odds, "Get odds for game")
        self.register_tool(
            "get_line_movement", self._get_line_movement, "Get line movement"
        )
        self.register_tool(
            "store_prediction", self._store_prediction, "Store prediction"
        )
        self.register_tool("store_bet", self._store_bet, "Store bet")
        self.register_tool(
            "get_performance", self._get_performance, "Get performance metrics"
        )
        self.register_tool(
            "update_bet_result", self._update_bet_result, "Update bet result"
        )

    async def run(self):
        await self._initialize_database()
        while self.running:
            await asyncio.sleep(60)

    async def _initialize_database(self):
        """Initialize database with schemas."""
        import sqlite3

        from src.agents.database_schemas import DatabaseSchema
        from src.agents.query_builder import QueryBuilder

        # Create database if it doesn't exist
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            conn = sqlite3.connect(str(self.db_path))

            # Initialize all tables and indexes
            DatabaseSchema.initialize_database(conn)

            # Initialize query builder
            self._query_builder = QueryBuilder(conn)
            self._conn = conn

            logger.info("Database initialized with schema-aware tables")
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")

    def _get_connection(self):
        """Get database connection."""
        import sqlite3

        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path))
            from src.agents.query_builder import QueryBuilder

            self._query_builder = QueryBuilder(self._conn)

        return self._conn

    async def _get_odds(self, game_id: str, market_key: str = None) -> Dict[str, Any]:
        """Get odds for a game using schema-aware query."""
        try:
            self._get_connection()
            results = self._query_builder.get_odds_for_game(game_id, market_key)
            return {"results": results, "count": len(results)}
        except Exception as e:
            logger.error(f"Failed to get odds: {e}")
            return {"results": [], "count": 0, "error": str(e)}

    async def _get_line_movement(
        self, game_id: str, hours: int = 24, bookmaker: str = None
    ) -> Dict[str, Any]:
        """Get line movement history for a game."""
        try:
            self._get_connection()
            results = self._query_builder.get_line_movement(game_id, hours, bookmaker)
            return {"results": results, "count": len(results)}
        except Exception as e:
            logger.error(f"Failed to get line movement: {e}")
            return {"results": [], "count": 0, "error": str(e)}

    async def _store_prediction(self, prediction: Dict[str, Any]) -> Dict[str, Any]:
        """Store a model prediction using schema validation."""
        try:
            self._get_connection()
            success = self._query_builder.store_prediction(prediction)
            return {"stored": success}
        except Exception as e:
            logger.error(f"Failed to store prediction: {e}")
            return {"stored": False, "error": str(e)}

    async def _store_bet(self, bet: Dict[str, Any]) -> Dict[str, Any]:
        """Store a bet record using schema validation."""
        try:
            self._get_connection()
            success = self._query_builder.store_bet(bet)
            return {"stored": success}
        except Exception as e:
            logger.error(f"Failed to store bet: {e}")
            return {"stored": False, "error": str(e)}

    async def _get_performance(
        self, days: int = 7, period_type: str = "daily"
    ) -> Dict[str, Any]:
        """Get recent performance metrics."""
        try:
            self._get_connection()
            results = self._query_builder.get_recent_performance(days, period_type)
            return {"results": results, "count": len(results)}
        except Exception as e:
            logger.error(f"Failed to get performance: {e}")
            return {"results": [], "count": 0, "error": str(e)}

    async def _update_bet_result(
        self, bet_id: int, result: str, profit: float
    ) -> Dict[str, Any]:
        """Update bet result after settlement."""
        try:
            self._get_connection()
            success = self._query_builder.update_bet_result(bet_id, result, profit)
            return {"updated": success}
        except Exception as e:
            logger.error(f"Failed to update bet result: {e}")
            return {"updated": False, "error": str(e)}

    async def _query(self, query: str) -> Dict[str, Any]:
        """Execute raw SQL query (backward compatibility)."""
        import sqlite3

        if not self.db_path.exists():
            return {"results": [], "count": 0, "error": "Database not found"}

        try:
            conn = self._get_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(query)
            rows = [dict(row) for row in cursor.fetchall()]
            return {"results": rows, "count": len(rows)}
        except Exception as e:
            logger.error(f"Database query error: {e}")
            return {"results": [], "count": 0, "error": str(e)}

    async def _store(self, table: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Store data using schema-aware methods (backward compatibility)."""
        # Route to appropriate schema-aware method
        if table == "predictions":
            return await self._store_prediction(data)
        elif table == "bet_history":
            return await self._store_bet(data)
        elif table == "odds_snapshots":
            try:
                self._get_connection()
                success = self._query_builder.store_odds_snapshot(data)
                return {"stored": success}
            except Exception as e:
                logger.error(f"Failed to store odds snapshot: {e}")
                return {"stored": False, "error": str(e)}
        else:
            logger.warning(
                f"No schema-aware method for table {table}, using generic store"
            )
            return {"stored": False, "error": f"Unknown table: {table}"}


class NotificationAgent(BaseAgent):
    """Notification Agent - Alerts, reports, dashboards."""

    def __init__(self):
        super().__init__(
            agent_id="notification_001",
            agent_name="Notification Agent",
            capabilities=[AgentCapability.COMMUNICATION],
        )
        self.register_tool("send_alert", self._send_alert, "Send alert")
        self.register_tool("send_report", self._send_report, "Send report")

    async def run(self):
        while self.running:
            await asyncio.sleep(60)

    async def _send_alert(self, message: str, severity: str = "info"):
        logger.info(f"Alert [{severity}]: {message}")
        return {"sent": True}

    async def _send_report(self, report: Dict[str, Any]):
        logger.info(f"Report: {report.get('title', 'Untitled')}")
        return {"sent": True}


class LoggingAgent(BaseAgent):
    """Logging Agent - System health, debugging, audit trails."""

    def __init__(self):
        super().__init__(
            agent_id="logging_001",
            agent_name="Logging Agent",
            capabilities=[AgentCapability.MEMORY],
        )
        self.logs: List[Dict[str, Any]] = []
        self.register_tool("log", self._log, "Log event")
        self.register_tool("get_logs", self._get_logs, "Get logs")

    async def run(self):
        while self.running:
            await asyncio.sleep(60)

    async def _log(self, level: str, message: str, metadata: Dict = None):
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "message": message,
            "metadata": metadata or {},
        }
        self.logs.append(log_entry)
        logger.log(getattr(logging, level.upper(), logging.INFO), message)
        return {"logged": True}

    async def _get_logs(self, level: str = None, limit: int = 100) -> Dict[str, Any]:
        filtered = (
            self.logs
            if not level
            else [entry for entry in self.logs if entry["level"] == level]
        )
        return {"logs": filtered[-limit:], "count": len(filtered)}


class SelfHealingAgent(BaseAgent):
    """Self-Healing Agent — detects anomalies via MonitoringLayer and remediates."""

    def __init__(self):
        super().__init__(
            agent_id="self_healing_001",
            agent_name="Self-Healing Agent",
            capabilities=[AgentCapability.REASONING, AgentCapability.TOOLS],
        )
        self.register_tool("detect_issues", self._detect_issues, "Detect system issues")
        self.register_tool("fix_issue", self._fix_issue, "Fix an issue")

        self._monitoring = None
        self._anomaly_detector = None
        self._remediation = None

    def _ensure_deps(self):
        if self._monitoring is None:
            from src.self_healing import (
                AnomalyDetector,
                AutoRemediation,
                MonitoringLayer,
            )

            self._monitoring = MonitoringLayer()
            self._anomaly_detector = AnomalyDetector(self._monitoring)
            self._remediation = AutoRemediation()

    async def run(self):
        while self.running:
            try:
                issues = await self._detect_issues()
                for issue in issues:
                    result = await self._fix_issue(issue)
                    if not result.get("fixed"):
                        logger.warning(
                            "Self-healing could not fix: %s", issue.get("type")
                        )
                        await self.send_message_async(
                            AgentMessage(
                                receiver_id="orchestrator_001",
                                message_type="alert",
                                content={
                                    "alert": {
                                        "severity": "high",
                                        "message": f"Unresolved issue: {issue.get('type')}",
                                    }
                                },
                            )
                        )
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Self-Healing error: %s", e, exc_info=True)
                await asyncio.sleep(10)

    async def _detect_issues(self) -> List[Dict[str, Any]]:
        self._ensure_deps()
        try:
            self._monitoring.collect_system_metrics()
            anomalies = self._anomaly_detector.detect_anomalies()
            return anomalies if anomalies else []
        except Exception as e:
            logger.error("Anomaly detection failed: %s", e)
            return []

    async def _fix_issue(self, issue: Dict[str, Any]) -> Dict[str, Any]:
        self._ensure_deps()
        logger.info("Attempting to fix issue: %s", issue.get("type"))
        return self._remediation.remediate(issue)
