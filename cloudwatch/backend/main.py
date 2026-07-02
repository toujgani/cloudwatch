"""
CloudWatch — API principale FastAPI
Lance le collecteur APScheduler au démarrage.
"""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .database import init_db
from .collector import start_scheduler, stop_scheduler
from .routers import vms, pods, alerts, reports, observability

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──
    logger.info("CloudWatch API starting…")
    init_db()
    start_scheduler()
    yield
    # ── Shutdown ──
    stop_scheduler()
    logger.info("CloudWatch API stopped.")


app = FastAPI(
    title="CloudWatch — Supervision Infrastructure",
    description="API de supervision OpenStack & OpenShift pour Tanger Med",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — autorise le frontend React (localhost:5173 en dev)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──
app.include_router(vms.router,    prefix="/api")
app.include_router(pods.router,   prefix="/api")
app.include_router(alerts.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(observability.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"status": "ok", "service": "cloudwatch"}


@app.get("/api/dashboard/stats")
def dashboard_stats(
    vms_router=None,
):
    """
    Agrège les KPIs principaux pour la page d'accueil du dashboard.
    Délègue aux routers individuels via import direct.
    """
    from .database import SessionLocal
    from .models import VirtualMachine, Pod, Alert, StatusEnum
    db = SessionLocal()
    try:
        total_vms    = db.query(VirtualMachine).count()
        active_vms   = db.query(VirtualMachine).filter(VirtualMachine.status == "ACTIVE").count()
        total_pods   = db.query(Pod).count()
        running_pods = db.query(Pod).filter(Pod.status == "Running").count()
        failed_pods  = db.query(Pod).filter(Pod.status.in_(["Failed", "Unknown"])).count()
        active_alerts= db.query(Alert).filter(Alert.status == StatusEnum.active).count()
        crit_alerts  = db.query(Alert).filter(
            Alert.status == StatusEnum.active,
            Alert.severity == "critical"
        ).count()
        vm_availability = active_vms / max(total_vms, 1)
        pod_availability = running_pods / max(total_pods, 1)
        alert_penalty = min(45, crit_alerts * 12 + max(active_alerts - crit_alerts, 0) * 4)
        health_score = max(0, min(100, round(((vm_availability * 45) + (pod_availability * 35) + 20) - alert_penalty)))
        return {
            "vms":   {"total": total_vms, "active": active_vms},
            "pods":  {"total": total_pods, "running": running_pods, "failed": failed_pods},
            "alerts":{"total_active": active_alerts, "critical": crit_alerts},
            "health_score": health_score,
        }
    finally:
        db.close()
