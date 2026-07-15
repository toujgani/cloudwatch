"""
Collecteur principal — tourne toutes les N secondes via APScheduler.
1. Appelle OpenStack → liste VMs + diagnostics
2. Appelle OpenShift → liste pods + métriques
3. Persiste en base PostgreSQL
4. Évalue les règles d'alertes

No mock mode — if a source is unreachable, it logs the error and skips.
The dashboard shows empty/no data for that source.
"""
import logging
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from sqlalchemy.orm import Session
from .database import SessionLocal
from .models import VirtualMachine, VMMetric, Pod, PodMetric
from .config import settings
from . import openstack_client as os_client
from . import openshift_client as k8s_client
from . import alerts as alert_engine

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()


# ─── OpenStack Collect ────────────────────────────────────────────────────────

def collect_openstack(db: Session):
    """Collect VMs from real OpenStack. If unreachable, skip silently."""
    logger.info("[Collector] OpenStack — attempting real connection")
    try:
        servers = os_client.list_servers()
    except Exception as e:
        logger.warning("[Collector] OpenStack unavailable — no VM data. (%s)", e)
        return

    for server in servers:
        try:
            diag = os_client.get_server_diagnostics(server["id"])
        except Exception:
            diag = {}

        data = os_client.parse_vm(server, diag)

        vm = db.get(VirtualMachine, data["id"])
        if vm is None:
            vm = VirtualMachine(id=data["id"])
            db.add(vm)

        vm.name      = data["name"]
        vm.status    = data["status"]
        vm.flavor    = data["flavor"]
        vm.host      = data["host"]
        vm.tenant_id = data["tenant_id"]
        vm.updated_at = datetime.utcnow()

        metric = VMMetric(
            vm_id        = data["id"],
            cpu_percent  = data["cpu_percent"],
            ram_percent  = data["ram_percent"],
            ram_used_mb  = data["ram_used_mb"],
            ram_total_mb = data["ram_total_mb"],
            disk_read_mb = data["disk_read_mb"],
            disk_write_mb= data["disk_write_mb"],
            collected_at = datetime.utcnow(),
        )
        db.add(metric)
        alert_engine.evaluate_vm(db, vm, data["cpu_percent"], data["ram_percent"])

    db.commit()
    logger.info("[Collector] OpenStack — done (%d VMs)", len(servers))


# ─── OpenShift Collect ────────────────────────────────────────────────────────

def collect_openshift(db: Session):
    """Collect pods from real OpenShift. If unreachable, skip silently."""
    logger.info("[Collector] OpenShift — attempting real connection")
    try:
        namespace = settings.KUBE_NAMESPACE or ""
        pods = k8s_client.list_pods(namespace=namespace)
    except Exception as e:
        logger.warning("[Collector] OpenShift unavailable — no pod data. (%s)", e)
        return

    # Metrics are optional — sandbox may block cluster-wide metrics endpoint
    try:
        metrics = k8s_client.list_pod_metrics()
    except Exception as e:
        logger.warning("[Collector] OpenShift metrics unavailable — using pods without CPU/RAM. (%s)", e)
        metrics = {}

    for item in pods:
        data = k8s_client.parse_pod(item, metrics)

        pod = db.get(Pod, data["id"])
        if pod is None:
            pod = Pod(id=data["id"])
            db.add(pod)

        pod.name          = data["name"]
        pod.namespace     = data["namespace"]
        pod.status        = data["status"]
        pod.node          = data["node"]
        pod.restart_count = data["restart_count"]
        pod.image         = data["image"]
        pod.updated_at    = datetime.utcnow()

        m = PodMetric(
            pod_id         = data["id"],
            cpu_millicores = data["cpu_millicores"],
            ram_mb         = data["ram_mb"],
            restart_count  = data["restart_count"],
            collected_at   = datetime.utcnow(),
        )
        db.add(m)
        alert_engine.evaluate_pod(db, pod, data["restart_count"])

    db.commit()
    logger.info("[Collector] OpenShift — done (%d pods)", len(pods))


# ─── Scheduled job ────────────────────────────────────────────────────────────

def collect_all():
    """Entrée principale du scheduler — collecte les deux sources."""
    db: Session = SessionLocal()
    try:
        collect_openstack(db)
        collect_openshift(db)
    except Exception as e:
        logger.exception("[Collector] Unexpected error: %s", e)
        db.rollback()
    finally:
        db.close()


def start_scheduler():
    scheduler.add_job(
        collect_all,
        trigger="interval",
        seconds=settings.COLLECT_INTERVAL_SECONDS,
        id="collect_all",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.start()
    logger.info("[Scheduler] Started — interval %ds", settings.COLLECT_INTERVAL_SECONDS)
    collect_all()


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
