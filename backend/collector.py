"""
Collecteur principal — tourne toutes les N secondes via APScheduler.
1. Appelle OpenStack → liste VMs + diagnostics
2. Appelle OpenShift → liste pods + métriques
3. Persiste en base PostgreSQL
4. Évalue les règles d'alertes

Mode mock: MOCK_MODE=true dans .env → données simulées sans vraies APIs.
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
from . import mock_data

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()


# ─── OpenStack Collect ────────────────────────────────────────────────────────

def collect_openstack(db: Session):
    logger.info("[Collector] OpenStack — start (mock=%s)", settings.MOCK_OPENSTACK or settings.MOCK_MODE)

    # ── Mode mock ──
    if settings.MOCK_OPENSTACK or settings.MOCK_MODE:
        vms_data = mock_data.get_mock_vms()
        for data in vms_data:
            vm = db.get(VirtualMachine, data["id"])
            if vm is None:
                vm = VirtualMachine(id=data["id"])
                db.add(vm)
            vm.name = data["name"]; vm.status = data["status"]
            vm.flavor = data["flavor"]; vm.host = data["host"]
            vm.tenant_id = data["tenant_id"]; vm.updated_at = datetime.utcnow()
            db.add(VMMetric(
                vm_id=data["id"], cpu_percent=data["cpu_percent"],
                ram_percent=data["ram_percent"], ram_used_mb=data["ram_used_mb"],
                ram_total_mb=data["ram_total_mb"], disk_read_mb=data["disk_read_mb"],
                disk_write_mb=data["disk_write_mb"], collected_at=datetime.utcnow(),
            ))
            alert_engine.evaluate_vm(db, vm, data["cpu_percent"], data["ram_percent"])
        db.commit()
        logger.info("[Collector] OpenStack mock — done (%d VMs)", len(vms_data))
        return

    # ── Mode réel ──
    try:
        servers = os_client.list_servers()
    except Exception as e:
        logger.error("[Collector] OpenStack list_servers failed: %s", e)
        return

    for server in servers:
        try:
            diag = os_client.get_server_diagnostics(server["id"])
        except Exception:
            diag = {}

        data = os_client.parse_vm(server, diag)

        # Upsert VM
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

        # Metric row
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

        # Alert evaluation
        alert_engine.evaluate_vm(db, vm, data["cpu_percent"], data["ram_percent"])

    db.commit()
    logger.info("[Collector] OpenStack — done (%d VMs)", len(servers))


# ─── OpenShift Collect ────────────────────────────────────────────────────────

def collect_openshift(db: Session):
    logger.info("[Collector] OpenShift — start (mock=%s)", settings.MOCK_OPENSHIFT or settings.MOCK_MODE)

    # ── Mode mock ──
    if settings.MOCK_OPENSHIFT or settings.MOCK_MODE:
        pods_data = mock_data.get_mock_pods()
        for data in pods_data:
            pod = db.get(Pod, data["id"])
            if pod is None:
                pod = Pod(id=data["id"])
                db.add(pod)
            pod.name = data["name"]; pod.namespace = data["namespace"]
            pod.status = data["status"]; pod.node = data["node"]
            pod.restart_count = data["restart_count"]; pod.image = data["image"]
            pod.updated_at = datetime.utcnow()
            db.add(PodMetric(
                pod_id=data["id"], cpu_millicores=data["cpu_millicores"],
                ram_mb=data["ram_mb"], restart_count=data["restart_count"],
                collected_at=datetime.utcnow(),
            ))
            alert_engine.evaluate_pod(db, pod, data["restart_count"])
        db.commit()
        logger.info("[Collector] OpenShift mock — done (%d pods)", len(pods_data))
        return

    # ── Mode réel ──
    try:
        pods    = k8s_client.list_pods()
        metrics = k8s_client.list_pod_metrics()
    except Exception as e:
        logger.error("[Collector] OpenShift failed: %s", e)
        return

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
    # Run once immediately on startup
    collect_all()


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
