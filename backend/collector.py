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
    """Collect VMs from real OpenStack or mock data if MOCK_OPENSTACK=true."""
    if settings.MOCK_OPENSTACK:
        from .mock_data import mock_openstack_vms
        logger.info("[Collector] OpenStack MOCK MODE — generating fake VMs")
        vms_data = mock_openstack_vms()
        for data in vms_data:
            vm = db.get(VirtualMachine, data["id"])
            if vm is None:
                vm = VirtualMachine(id=data["id"])
                db.add(vm)
            vm.name = data["name"]
            vm.status = data["status"]
            vm.flavor = data["flavor"]
            vm.host = data["host"]
            vm.tenant_id = data["tenant_id"]
            vm.updated_at = datetime.utcnow()
            metric = VMMetric(
                vm_id=data["id"], cpu_percent=data["cpu_percent"],
                ram_percent=data["ram_percent"], ram_used_mb=data["ram_used_mb"],
                ram_total_mb=data["ram_total_mb"], disk_read_mb=data["disk_read_mb"],
                disk_write_mb=data["disk_write_mb"], collected_at=datetime.utcnow(),
            )
            db.add(metric)
            alert_engine.evaluate_vm(db, vm, data["cpu_percent"], data["ram_percent"])
        db.commit()
        logger.info("[Collector] OpenStack MOCK — done (%d VMs)", len(vms_data))
        return

    if not settings.OS_AUTH_URL:
        return  # OpenStack not configured — skip without logging
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
    """
    Collect pods from real OpenShift or mock data if MOCK_OPENSHIFT=true.
    Real mode does FULL RECONCILIATION (deletes stale pods from DB).
    """
    if settings.MOCK_OPENSHIFT:
        from .mock_data import mock_openshift_pods
        logger.info("[Collector] OpenShift MOCK MODE — generating fake pods")
        pods_data = mock_openshift_pods()
        for data in pods_data:
            pod = db.get(Pod, data["id"])
            if pod is None:
                pod = Pod(id=data["id"])
                db.add(pod)
            pod.name = data["name"]
            pod.namespace = data["namespace"]
            pod.status = data["status"]
            pod.node = data["node"]
            pod.restart_count = data["restart_count"]
            pod.image = data["image"]
            pod.updated_at = datetime.utcnow()
            m = PodMetric(
                pod_id=data["id"], cpu_millicores=data["cpu_millicores"],
                ram_mb=data["ram_mb"], restart_count=data["restart_count"],
                collected_at=datetime.utcnow(),
            )
            db.add(m)
            alert_engine.evaluate_pod(db, pod, data["restart_count"])
        db.commit()
        logger.info("[Collector] OpenShift MOCK — done (%d pods)", len(pods_data))
        return

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

    # Track which pod IDs we see from the live API
    live_pod_ids: set[str] = set()

    for item in pods:
        data = k8s_client.parse_pod(item, metrics)
        live_pod_ids.add(data["id"])

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

    # ── RECONCILIATION: Remove pods from DB that no longer exist in Kubernetes ──
    db_pods = db.query(Pod).all()
    stale_pods = [p for p in db_pods if p.id not in live_pod_ids]

    if stale_pods:
        stale_count = len(stale_pods)
        for stale_pod in stale_pods:
            # Delete associated metrics first (cascade might handle this but be explicit)
            db.query(PodMetric).filter(PodMetric.pod_id == stale_pod.id).delete()
            db.delete(stale_pod)
        logger.info("[Collector] Reconciliation — removed %d stale pods from database", stale_count)

    db.commit()
    logger.info("[Collector] OpenShift — done (%d live pods, %d stale removed)",
                len(live_pod_ids), len(stale_pods))


# ─── Namespace Quota Check ────────────────────────────────────────────────────

def check_namespace_quota(db: Session):
    """
    Check if total namespace resource usage exceeds soft quota.
    Uses configurable soft quota thresholds to trigger alerts at
    warning, critical, and auto-remediate levels.
    """
    from .models import SeverityEnum
    from .soft_quota import get_quota_status

    status = get_quota_status(db)

    # CPU soft quota alerts
    if status.cpu_level == "remediate" or status.cpu_level == "critical":
        alert_engine._create_alert(db,
            severity=SeverityEnum.critical,
            title=f"Quota CPU namespace depasse — {status.total_cpu_used:.0f}m / {status.soft_cpu_limit:.0f}m ({status.cpu_usage_percent:.0f}%)",
            description=f"L'utilisation CPU totale du namespace ({status.total_cpu_used:.0f}m) depasse le seuil {status.cpu_level} du soft quota ({status.soft_cpu_limit:.0f}m). Risque de throttling ou de rejet de nouveaux pods.",
            rule_name="namespace.cpu.quota.critical",
            metric_value=status.total_cpu_used,
            threshold=status.soft_cpu_limit * (settings.QUOTA_THRESHOLD_CRITICAL / 100),
        )
    elif status.cpu_level == "warning":
        alert_engine._create_alert(db,
            severity=SeverityEnum.warning,
            title=f"Quota CPU namespace eleve — {status.total_cpu_used:.0f}m / {status.soft_cpu_limit:.0f}m ({status.cpu_usage_percent:.0f}%)",
            description=f"L'utilisation CPU totale approche le soft quota. Envisager de reduire les workloads ou augmenter le quota.",
            rule_name="namespace.cpu.quota.warning",
            metric_value=status.total_cpu_used,
            threshold=status.soft_cpu_limit * (settings.QUOTA_THRESHOLD_WARNING / 100),
        )
    else:
        alert_engine._resolve_alert(db, "namespace.cpu.quota.critical")
        alert_engine._resolve_alert(db, "namespace.cpu.quota.warning")

    # RAM soft quota alerts
    if status.ram_level == "remediate" or status.ram_level == "critical":
        alert_engine._create_alert(db,
            severity=SeverityEnum.critical,
            title=f"Quota RAM namespace depasse — {status.total_ram_used:.0f}Mi / {status.soft_ram_limit:.0f}Mi ({status.ram_usage_percent:.0f}%)",
            description=f"L'utilisation memoire totale du namespace depasse le seuil {status.ram_level} du soft quota. Pods en danger d'eviction.",
            rule_name="namespace.ram.quota.critical",
            metric_value=status.total_ram_used,
            threshold=status.soft_ram_limit * (settings.QUOTA_THRESHOLD_CRITICAL / 100),
        )
    elif status.ram_level == "warning":
        alert_engine._create_alert(db,
            severity=SeverityEnum.warning,
            title=f"Quota RAM namespace eleve — {status.total_ram_used:.0f}Mi / {status.soft_ram_limit:.0f}Mi ({status.ram_usage_percent:.0f}%)",
            description=f"L'utilisation memoire approche le soft quota. Surveiller les workloads ou liberer des ressources.",
            rule_name="namespace.ram.quota.warning",
            metric_value=status.total_ram_used,
            threshold=status.soft_ram_limit * (settings.QUOTA_THRESHOLD_WARNING / 100),
        )
    else:
        alert_engine._resolve_alert(db, "namespace.ram.quota.critical")
        alert_engine._resolve_alert(db, "namespace.ram.quota.warning")

    db.commit()
    if status.level != "normal":
        logger.warning("[Quota] Level=%s | CPU: %.0f%% (%.0fm/%.0fm) | RAM: %.0f%% (%.0fMi/%.0fMi)",
                       status.level,
                       status.cpu_usage_percent, status.total_cpu_used, status.soft_cpu_limit,
                       status.ram_usage_percent, status.total_ram_used, status.soft_ram_limit)


# ─── Scheduled job ────────────────────────────────────────────────────────────

def collect_all():
    """Entrée principale du scheduler — collecte les deux sources."""
    db: Session = SessionLocal()
    try:
        collect_openstack(db)
        collect_openshift(db)
        check_namespace_quota(db)
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
