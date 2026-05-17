"""NFL Betting System - FastAPI Backend

Production-ready API for the NFL betting prediction system.

Features:
- RESTful endpoints for picks, props, parlays, performance
- WebSocket support for live updates
- CORS configuration for frontend integration
- Comprehensive error handling
- Health checks

Run with:
    uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

Or from the backend directory:
    uvicorn main:app --reload
"""

import sys
from pathlib import Path
from datetime import datetime
from typing import List, Optional
import asyncio
import logging

# Ensure project root is in path for imports
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.routers import (
    picks_router,
    props_router,
    parlays_router,
    performance_router,
    recreational_router,
)
from backend.services.data_service import get_data_service


# ==================== Logging Setup ====================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ==================== App Configuration ====================

app = FastAPI(
    title="NFL Betting System API",
    description="""
    Production API for NFL betting predictions and analysis.

    ## Features
    - **Picks**: High-accuracy picks based on documented 60%+ win rate angles
    - **Props**: Player prop projections with hit rate tracking
    - **Parlays**: Featured and custom parlay building
    - **Performance**: Self-verification tracking and feedback

    ## Authentication
    Currently open for development. Production will require API keys.

    ## Rate Limits
    None currently. Production will implement rate limiting.
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)


# ==================== CORS Configuration ====================

# Allow all origins in development - restrict in production
ALLOWED_ORIGINS = [
    "http://localhost:3000",      # React dev server
    "http://localhost:5173",      # Vite dev server
    "http://localhost:8080",      # Alternative dev
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:8080",
    # Add production domains here
    # "https://your-domain.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)


# ==================== Include Routers ====================

app.include_router(picks_router)
app.include_router(props_router)
app.include_router(parlays_router)
app.include_router(performance_router)
app.include_router(recreational_router)


# ==================== Health Check & Root ====================

@app.get("/", tags=["root"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": "NFL Betting System API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "health": "/health",
        "endpoints": {
            "picks": "/api/picks/weekly, /api/picks/today",
            "props": "/api/props/player/{player_id}, /api/props/trending",
            "parlays": "/api/parlays/featured, /api/parlays/custom",
            "performance": "/api/performance/stats, /api/performance/history",
        },
    }


@app.get("/health", tags=["health"])
async def health_check():
    """
    Health check endpoint for monitoring and load balancers.

    Returns system status and component health.
    """
    try:
        # Try to initialize data service to verify components
        service = get_data_service()

        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "components": {
                "api": "up",
                "data_service": "up",
                "picks_engine": "up",
                "props_engine": "up",
                "parlay_builder": "up",
            },
            "version": "1.0.0",
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
            }
        )


@app.get("/ready", tags=["health"])
async def readiness_check():
    """
    Readiness check - is the service ready to accept traffic?

    Used by Kubernetes/orchestrators to determine if service is ready.
    """
    try:
        service = get_data_service()
        # Try to fetch picks to verify full functionality
        picks = service.get_weekly_picks()

        return {
            "ready": True,
            "timestamp": datetime.now().isoformat(),
            "picks_loaded": len(picks) > 0,
        }
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={"ready": False, "error": str(e)}
        )


# ==================== WebSocket Support ====================

class ConnectionManager:
    """Manages WebSocket connections for live updates."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self._broadcast_task: Optional[asyncio.Task] = None

    async def connect(self, websocket: WebSocket):
        """Accept and track a new WebSocket connection."""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        """Remove a disconnected WebSocket."""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")

    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """Send a message to a specific client."""
        await websocket.send_json(message)

    async def broadcast(self, message: dict):
        """Broadcast a message to all connected clients."""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                disconnected.append(connection)

        # Clean up disconnected clients
        for conn in disconnected:
            self.disconnect(conn)

    async def start_periodic_broadcast(self, interval: int = 30):
        """Start periodic broadcast of live updates."""
        while True:
            if self.active_connections:
                try:
                    service = get_data_service()
                    update = service.get_live_update()
                    await self.broadcast(update)
                except Exception as e:
                    logger.error(f"Broadcast error: {e}")
            await asyncio.sleep(interval)


manager = ConnectionManager()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for live updates.

    Connect to receive:
    - Real-time pick updates
    - Live line movements
    - System status updates

    Message format:
    {
        "timestamp": "ISO datetime",
        "picks_count": int,
        "top_pick": {...} or null,
        "parlays_available": int,
        "status": "active"
    }
    """
    await manager.connect(websocket)

    # Send initial state
    try:
        service = get_data_service()
        initial = {
            "type": "connection_established",
            "timestamp": datetime.now().isoformat(),
            "message": "Connected to NFL Betting System live updates",
        }
        await manager.send_personal_message(initial, websocket)

        # Send current state
        update = service.get_live_update()
        update["type"] = "initial_state"
        await manager.send_personal_message(update, websocket)

    except Exception as e:
        logger.error(f"Error sending initial WebSocket state: {e}")

    # Listen for messages
    try:
        while True:
            data = await websocket.receive_text()

            # Handle client requests
            if data == "ping":
                await manager.send_personal_message(
                    {"type": "pong", "timestamp": datetime.now().isoformat()},
                    websocket
                )
            elif data == "get_picks":
                service = get_data_service()
                picks = service.get_weekly_picks()
                await manager.send_personal_message(
                    {"type": "picks", "data": picks},
                    websocket
                )
            elif data == "get_status":
                service = get_data_service()
                update = service.get_live_update()
                update["type"] = "status"
                await manager.send_personal_message(update, websocket)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)


# ==================== Error Handlers ====================

@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    """Handle HTTP exceptions with consistent format."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": True,
            "status_code": exc.status_code,
            "detail": exc.detail,
            "timestamp": datetime.now().isoformat(),
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Handle unexpected exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": True,
            "status_code": 500,
            "detail": "Internal server error",
            "timestamp": datetime.now().isoformat(),
        }
    )


# ==================== Startup / Shutdown ====================

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    logger.info("Starting NFL Betting System API...")

    # Initialize data service
    try:
        service = get_data_service()
        logger.info("Data service initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize data service: {e}")

    logger.info("NFL Betting System API started successfully")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down NFL Betting System API...")

    # Close all WebSocket connections
    for connection in manager.active_connections:
        try:
            await connection.close()
        except Exception:
            pass

    logger.info("NFL Betting System API shutdown complete")


# ==================== Run Server ====================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
