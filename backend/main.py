"""
CloudWatch — API principale FastAPI
Architecture D: AI Agent + WebSocket gateway + Audit Trail
"""
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .database import init_db, SessionLocal
from .collector import start_scheduler, stop_scheduler
from .routers import vms, pods, alerts, reports, observability, kubernetes
from .routers import audit as audit_router
from .routers import aiops as aiops_router
from .websocket_manager import manager, broadcast_loop

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("CloudWatch API starting…")
    init_db()
    start_scheduler()
    # Start WebSocket broadcast loop as background task
    broadcast_task = asyncio.create_task(broadcast_loop(SessionLocal))
    yield
    broadcast_task.cancel()
    stop_scheduler()
    logger.info("CloudWatch API stopped.")


app = FastAPI(
    title="CloudWatch — Supervision Infrastructure",
    description="API de supervision OpenStack & OpenShift pour Tanger Med — Architecture D",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── REST Routers ──
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
