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
    """Collect VMs from real OpenStack. If unreachable or unconfigured, skip silently."""
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


# ─── Namespace Quota Check ────────────────────────────────────────────────────

def check_namespace_quota(db: Session):
    """
    Check if total namespace resource usage exceeds quota.
    Triggers alerts when CPU or RAM usage surpasses configured limits.
    """
    from .models import Alert, SeverityEnum, StatusEnum

    # Sum all pod metrics from the latest collection
    total_cpu = db.query(Pod).with_entities(
        db.query(PodMetric.cpu_millicores)
        .filter(PodMetric.pod_id == Pod.id)
        .order_by(PodMetric.collected_at.desc())
        .limit(1)
        .correlate(Pod)
        .scalar_subquery()
    ).all()

    # Simpler approach: sum from pods table directly using latest metrics
    pods = db.query(Pod).all()
    total_cpu_m = 0.0
    total_ram_mb = 0.0

    for pod in pods:
        latest_metric = db.query(PodMetric).filter(
            PodMetric.pod_id == pod.id
        ).order_by(PodMetric.collected_at.desc()).first()
        if latest_metric:
            total_cpu_m += latest_metric.cpu_millicores or 0
            total_ram_mb += latest_metric.ram_mb or 0

    # Quota limits (from ResourceQuota: requests.cpu = 3000m, requests.memory = 30Gi)
    cpu_quota = 3000  # millicores
    ram_quota = 30 * 1024  # 30Gi in MB

    cpu_usage_pct = (total_cpu_m / cpu_quota) * 100 if cpu_quota > 0 else 0
    ram_usage_pct = (total_ram_mb / ram_quota) * 100 if ram_quota > 0 else 0

    # CPU quota breach
    if cpu_usage_pct >= 90:
        alert_engine._create_alert(db,
            severity=SeverityEnum.critical,
            title=f"Quota CPU namespace depasse — {total_cpu_m:.0f}m / {cpu_quota}m ({cpu_usage_pct:.0f}%)",
            description=f"L'utilisation CPU totale du namespace ({total_cpu_m:.0f}m) depasse 90% du quota ({cpu_quota}m). Risque de throttling ou de rejet de nouveaux pods.",
            rule_name="namespace.cpu.quota.critical",
            metric_value=total_cpu_m,
            threshold=cpu_quota * 0.9,
        )
    elif cpu_usage_pct >= 75:
        alert_engine._create_alert(db,
            severity=SeverityEnum.warning,
            title=f"Quota CPU namespace eleve — {total_cpu_m:.0f}m / {cpu_quota}m ({cpu_usage_pct:.0f}%)",
            description=f"L'utilisation CPU totale approche le quota. Envisager de reduire les workloads ou augmenter le quota.",
            rule_name="namespace.cpu.quota.warning",
            metric_value=total_cpu_m,
            threshold=cpu_quota * 0.75,
        )
    else:
        alert_engine._resolve_alert(db, "namespace.cpu.quota.critical")
        alert_engine._resolve_alert(db, "namespace.cpu.quota.warning")

    # RAM quota breach
    if ram_usage_pct >= 90:
        alert_engine._create_alert(db,
            severity=SeverityEnum.critical,
            title=f"Quota RAM namespace depasse — {total_ram_mb:.0f}Mi / {ram_quota}Mi ({ram_usage_pct:.0f}%)",
            description=f"L'utilisation memoire totale du namespace depasse 90% du quota. Pods en danger d'eviction.",
            rule_name="namespace.ram.quota.critical",
            metric_value=total_ram_mb,
            threshold=ram_quota * 0.9,
        )
    elif ram_usage_pct >= 75:
        alert_engine._create_alert(db,
            severity=SeverityEnum.warning,
            title=f"Quota RAM namespace eleve — {total_ram_mb:.0f}Mi / {ram_quota}Mi ({ram_usage_pct:.0f}%)",
            description=f"L'utilisation memoire approche le quota. Surveiller les workloads ou liberer des ressources.",
            rule_name="namespace.ram.quota.warning",
            metric_value=total_ram_mb,
            threshold=ram_quota * 0.75,
        )
    else:
        alert_engine._resolve_alert(db, "namespace.ram.quota.critical")
        alert_engine._resolve_alert(db, "namespace.ram.quota.warning")

    db.commit()
    if cpu_usage_pct >= 75 or ram_usage_pct >= 75:
        logger.warning("[Quota] CPU: %.0f%% (%0.fm/%dm) | RAM: %.0f%% (%.0fMi/%dMi)",
                       cpu_usage_pct, total_cpu_m, cpu_quota, ram_usage_pct, total_ram_mb, ram_quota)


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
