"""FastAPI health endpoints.

Mount these into any FastAPI/uvicorn process to expose /health, /ready, /live.
Can also run standalone: `uvicorn src.health.api:app --port 8080`
"""

import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Dict

from fastapi import FastAPI
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

app = FastAPI(title="NFL Betting System Health", docs_url=None, redoc_url=None)

_start_time = time.monotonic()


def _check_database() -> Dict:
    """Verify SQLite databases are accessible."""
    issues = []
    for db_name in ["adaptive_learning.db", "odds_history.db", "events.db"]:
        db_path = Path("data") / db_name
        if db_path.exists():
            try:
                import sqlite3

                conn = sqlite3.connect(str(db_path), timeout=2)
                conn.execute("SELECT 1")
                conn.close()
            except Exception as e:
                issues.append(f"{db_name}: {e}")

    return {"ok": len(issues) == 0, "issues": issues}


def _check_models() -> Dict:
    """Check if at least one model is available."""
    models_dir = Path("models")
    if not models_dir.exists():
        return {"ok": True, "detail": "models/ not created yet (pre-training)"}
    pkls = list(models_dir.glob("*.pkl"))
    return {"ok": True, "count": len(pkls)}


def _check_config() -> Dict:
    """Validate critical config."""
    issues = []
    if not Path("config/config.yaml").exists():
        issues.append("config/config.yaml missing")
    return {"ok": len(issues) == 0, "issues": issues}


@app.get("/health")
async def health():
    """Full health check — returns 200 if healthy, 503 otherwise."""
    db = _check_database()
    models = _check_models()
    config = _check_config()

    all_ok = db["ok"] and config["ok"]
    status = "healthy" if all_ok else "unhealthy"

    body = {
        "status": status,
        "uptime_seconds": round(time.monotonic() - _start_time, 1),
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {"database": db, "models": models, "config": config},
    }

    return JSONResponse(body, status_code=200 if all_ok else 503)


@app.get("/ready")
async def ready():
    """Readiness probe — 200 if system can accept work."""
    config = _check_config()
    if not config["ok"]:
        return JSONResponse({"ready": False, "reason": "bad config"}, status_code=503)
    return {"ready": True}


@app.get("/live")
async def live():
    """Liveness probe — always 200."""
    return {"alive": True, "uptime_seconds": round(time.monotonic() - _start_time, 1)}
