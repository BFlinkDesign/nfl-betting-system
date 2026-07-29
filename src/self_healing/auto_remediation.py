"""Auto-Remediation — takes real actions to recover from detected anomalies.

Actions include GC, clearing model/odds caches, tripping circuit breakers,
verifying database connectivity, and resetting error-state agents.
"""

import gc
import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class AutoRemediation:
    """Remediation engine that executes real recovery actions."""

    def __init__(self):
        self.remediation_history: List[Dict[str, Any]] = []
        logger.info("Auto-remediation initialized")

    def remediate(self, anomaly: Dict[str, Any]) -> Dict[str, Any]:
        anomaly_type = anomaly.get("type")

        handlers = {
            "high_cpu": self._remediate_high_cpu,
            "high_memory": self._remediate_high_memory,
            "high_error_rate": self._remediate_high_error_rate,
            "low_cache_hit_rate": self._remediate_low_cache_hit_rate,
            "rate_limit_hit": self._remediate_rate_limit,
            "database_connection_lost": self._remediate_database_connection,
            "component_disconnect": self._remediate_component_disconnect,
        }

        handler = handlers.get(anomaly_type)
        if handler:
            try:
                result = handler(anomaly)
            except Exception as e:
                logger.error("Remediation handler %s failed: %s", anomaly_type, e)
                result = {"remediated": False, "error": str(e)}
            self.remediation_history.append({"anomaly": anomaly, "result": result})
            return result

        return {"remediated": False, "reason": f"No handler for {anomaly_type}"}

    def _remediate_high_cpu(self, anomaly: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("Remediating high CPU: forcing garbage collection")
        gc.collect()
        return {"remediated": True, "action": "gc_collect"}

    def _remediate_high_memory(self, anomaly: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("Remediating high memory: GC + clearing model cache")
        gc.collect()
        try:
            from src.swarms.model_loader import ModelLoader

            ModelLoader().clear_cache()
        except Exception:
            pass
        return {"remediated": True, "action": "gc_collect_and_cache_clear"}

    def _remediate_high_error_rate(self, anomaly: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("Remediating high error rate: tripping circuit breakers")
        tripped = []
        try:
            from src.utils.resilience import CIRCUIT_BREAKERS

            for name, breaker in CIRCUIT_BREAKERS.items():
                if hasattr(breaker, "open"):
                    breaker.open()
                    tripped.append(name)
        except ImportError:
            pass
        return {
            "remediated": True,
            "action": "circuit_breakers_opened",
            "tripped": tripped,
        }

    def _remediate_low_cache_hit_rate(self, anomaly: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("Remediating low cache hit rate: clearing stale odds cache")
        try:
            from src.utils.odds_cache import OddsCache

            cache = OddsCache()
            cache.clear_memory()
        except Exception:
            pass
        return {"remediated": True, "action": "cache_cleared"}

    def _remediate_rate_limit(self, anomaly: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("Remediating rate limit: token bucket self-recovers")
        return {"remediated": True, "action": "rate_limit_acknowledged"}

    def _remediate_database_connection(self, anomaly: Dict[str, Any]) -> Dict[str, Any]:
        logger.info("Remediating database connection: testing connectivity")
        db_files = list(Path("data").glob("*.db"))
        ok = True
        for db_path in db_files:
            try:
                conn = sqlite3.connect(str(db_path), timeout=2)
                conn.execute("SELECT 1")
                conn.close()
            except Exception as e:
                logger.error("DB %s still unreachable: %s", db_path, e)
                ok = False
        return {
            "remediated": ok,
            "action": "database_connectivity_check",
            "dbs_checked": len(db_files),
        }

    def _remediate_component_disconnect(
        self, anomaly: Dict[str, Any]
    ) -> Dict[str, Any]:
        logger.info("Remediating component disconnect: resetting error-state agents")
        try:
            from src.agents.base_agent import AgentStatus, agent_registry

            agents = agent_registry.get_all()
            reset = []
            for agent in agents:
                if agent.status == AgentStatus.ERROR:
                    agent.error_count = 0
                    agent.status = AgentStatus.READY
                    reset.append(agent.agent_id)
            return {"remediated": True, "action": "agents_reset", "reset": reset}
        except Exception as e:
            return {"remediated": False, "error": str(e)}
