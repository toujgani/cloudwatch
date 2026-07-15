"""
Cloud AI Monitor — FastAPI Production API
Architecture D: AI Agent + WebSocket gateway + Audit Trail
"""
import asyncio
import logging
import os
import signal
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from .database import init_db, SessionLocal
from .collector import start_scheduler, stop_scheduler
from .routers import vms, pods, alerts, reports, observability, kubernetes
from .routers import audit as audit_router
from .routers import aiops as aiops_router
from .routers import auth as auth_router
from .websocket_manager import manager, broadcast_loop
from .seed import seed_users

# ── Production Logging ────────────────────────────────────────────────────────
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


# ── Graceful Shutdown ─────────────────────────────────────────────────────────
_shutdown_event = asyncio.Event()


def _signal_handler(signum, frame):
    logger.info("Received signal %s, initiating graceful shutdown...", signum)
    _shutdown_event.set()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Cloud AI Monitor starting…")
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)

    init_db()
    # Seed default users on first boot
    db = SessionLocal()
    try:
        seed_users(db)
    finally:
        db.close()
    start_scheduler()
    # Start WebSocket broadcast loop as background task
    broadcast_task = asyncio.create_task(broadcast_loop(SessionLocal))
    yield
    # Graceful shutdown
    broadcast_task.cancel()
    stop_scheduler()
    logger.info("Cloud AI Monitor stopped gracefully.")


app = FastAPI(
    title="Cloud AI Monitor — Infrastructure Supervision",
    description="AIOps supervision platform for OpenStack & OpenShift — Architecture D",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# ── Middleware Stack ──────────────────────────────────────────────────────────

# GZip compression for responses > 500 bytes
app.add_middleware(GZipMiddleware, minimum_size=500)

# CORS — restrictive in production, permissive in development
_allowed_origins = os.getenv("CORS_ORIGINS", "").split(",")
_allowed_origins = [o.strip() for o in _allowed_origins if o.strip()]
if not _allowed_origins:
    # Default: allow same-origin (OpenShift route) + local dev
    _allowed_origins = ["http://localhost:5173", "http://localhost:3000", "http://localhost:8080"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["*"],
)


# Security headers middleware
@app.middleware("http")
async def security_headers(request: Request, call_next):
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response

# ── Serve React static build if available ─────────────────────────────────────
from pathlib import Path
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

_STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
_has_static = _STATIC_DIR.is_dir() and (_STATIC_DIR / "index.html").exists()

# ── REST Routers ──
app.include_router(auth_router.router,   prefix="/api")
app.include_router(vms.router,           prefix="/api")
app.include_router(pods.router,          prefix="/api")
app.include_router(alerts.router,        prefix="/api")
app.include_router(reports.router,       prefix="/api")
app.include_router(observability.router, prefix="/api")
app.include_router(kubernetes.router,    prefix="/api")
app.include_router(audit_router.router,  prefix="/api")
app.include_router(aiops_router.router,  prefix="/api")


# ── WebSocket endpoint ────────────────────────────────────────────────────────

@app.websocket("/ws/live")
async def websocket_live(websocket: WebSocket):
    """
    Real-time push endpoint.
    Broadcasts a full snapshot every WS_BROADCAST_INTERVAL_SECONDS to all
    connected clients. The frontend subscribes once and receives live KPIs,
    anomaly vectors and audit trail without polling.
    """
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive — client can also send pings
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception:
        await manager.disconnect(websocket)


# ── Health & Dashboard ────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "service": "cloudwatch",
        "version": "2.0.0",
        "ws_clients": manager.connected_count,
    }


@app.get("/api/dashboard/stats")
def dashboard_stats():
    from .database import SessionLocal
    from .models import VirtualMachine, Pod, Alert, StatusEnum, SeverityEnum
    db = SessionLocal()
    try:
        total_vms    = db.query(VirtualMachine).count()
        active_vms   = db.query(VirtualMachine).filter(VirtualMachine.status == "ACTIVE").count()
        total_pods   = db.query(Pod).count()
        running_pods = db.query(Pod).filter(Pod.status == "Running").count()
        failed_pods  = db.query(Pod).filter(Pod.status.in_(["Failed", "Unknown"])).count()
        active_alerts = db.query(Alert).filter(
            Alert.status.in_([StatusEnum.active, StatusEnum.acknowledged, StatusEnum.assigned])
        ).all()
        total_active = len(active_alerts)
        crit_alerts  = sum(1 for a in active_alerts if a.severity == SeverityEnum.critical)

        vm_availability  = active_vms / max(total_vms, 1)
        pod_availability = running_pods / max(total_pods, 1)
        alert_penalty    = min(45, crit_alerts * 12 + max(total_active - crit_alerts, 0) * 4)
        health_score     = max(0, min(100, round(
            (vm_availability * 45 + pod_availability * 35 + 20) - alert_penalty
        )))

        return {
            "vms":   {"total": total_vms, "active": active_vms},
            "pods":  {"total": total_pods, "running": running_pods, "failed": failed_pods},
            "alerts": {"total_active": total_active, "critical": crit_alerts},
            "health_score": health_score,
        }
    finally:
        db.close()


# ── Static files + SPA catch-all (only when built frontend exists) ────────────
if _has_static:
    # Serve /assets/*, /cireslogo.png, etc.
    app.mount("/assets", StaticFiles(directory=str(_STATIC_DIR / "assets")), name="static-assets")

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve React SPA — any non-API route returns index.html."""
        file_path = _STATIC_DIR / full_path
        if file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(_STATIC_DIR / "index.html"))
