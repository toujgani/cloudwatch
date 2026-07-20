"""
Soft Quota Configuration System.

Soft quota = configurable percentage of actual sandbox quota.
This provides a safety buffer before hitting hard OpenShift ResourceQuota limits.

Actual sandbox limits:
  - CPU: 3000m requests
  - RAM: 30Gi requests

Thresholds (percentage of soft quota used):
  - 70%: normal
  - 80%: warning
  - 90%: critical
  - 95%: auto-remediate
"""
import logging
from dataclasses import dataclass
from sqlalchemy.orm import Session

from .config import settings
from .models import Pod, PodMetric

logger = logging.getLogger(__name__)

# Hard sandbox limits
SANDBOX_CPU_MILLICORES = 3000
SANDBOX_RAM_MB = 30 * 1024  # 30Gi in MB


@dataclass
class QuotaStatus:
    """Current namespace quota usage vs soft quota."""
    # Soft quota values
    soft_cpu_limit: float
    soft_ram_limit: float
    # Current usage
    total_cpu_used: float
    total_ram_used: float
    # Percentages of soft quota used
    cpu_usage_percent: float
    ram_usage_percent: float
    # Threshold level: "normal", "warning", "critical", "remediate"
    cpu_level: str
    ram_level: str
    # Overall level (worst of cpu/ram)
    level: str


def _compute_soft_limits() -> tuple[float, float]:
    """Compute soft quota limits from config percentages."""
    cpu_percent = settings.SOFT_QUOTA_CPU_PERCENT
    ram_percent = settings.SOFT_QUOTA_RAM_PERCENT
    soft_cpu = SANDBOX_CPU_MILLICORES * (cpu_percent / 100.0)
    soft_ram = SANDBOX_RAM_MB * (ram_percent / 100.0)
    return soft_cpu, soft_ram


def _determine_level(usage_percent: float) -> str:
    """Determine threshold level based on usage percentage of soft quota."""
    if usage_percent >= settings.QUOTA_THRESHOLD_REMEDIATE:
        return "remediate"
    elif usage_percent >= settings.QUOTA_THRESHOLD_CRITICAL:
        return "critical"
    elif usage_percent >= settings.QUOTA_THRESHOLD_WARNING:
        return "warning"
    return "normal"


def _worst_level(level_a: str, level_b: str) -> str:
    """Return the most severe of two threshold levels."""
    order = ["normal", "warning", "critical", "remediate"]
    idx_a = order.index(level_a) if level_a in order else 0
    idx_b = order.index(level_b) if level_b in order else 0
    return order[max(idx_a, idx_b)]


def get_quota_status(db: Session) -> QuotaStatus:
    """
    Compute current namespace resource usage vs soft quota.
    Returns a QuotaStatus with usage percentages and threshold levels.
    """
    soft_cpu, soft_ram = _compute_soft_limits()

    # Sum latest metrics for all pods
    pods = db.query(Pod).all()
    total_cpu = 0.0
    total_ram = 0.0

    for pod in pods:
        latest_metric = (
            db.query(PodMetric)
            .filter(PodMetric.pod_id == pod.id)
            .order_by(PodMetric.collected_at.desc())
            .first()
        )
        if latest_metric:
            total_cpu += latest_metric.cpu_millicores or 0
            total_ram += latest_metric.ram_mb or 0

    cpu_usage_pct = (total_cpu / soft_cpu * 100) if soft_cpu > 0 else 0
    ram_usage_pct = (total_ram / soft_ram * 100) if soft_ram > 0 else 0

    cpu_level = _determine_level(cpu_usage_pct)
    ram_level = _determine_level(ram_usage_pct)
    overall_level = _worst_level(cpu_level, ram_level)

    return QuotaStatus(
        soft_cpu_limit=soft_cpu,
        soft_ram_limit=soft_ram,
        total_cpu_used=total_cpu,
        total_ram_used=total_ram,
        cpu_usage_percent=round(cpu_usage_pct, 1),
        ram_usage_percent=round(ram_usage_pct, 1),
        cpu_level=cpu_level,
        ram_level=ram_level,
        level=overall_level,
    )


@dataclass
class ConsumerInfo:
    """Resource usage info for a single pod."""
    pod_id: str
    pod_name: str
    namespace: str
    cpu_millicores: float
    ram_mb: float


def get_top_consumers(db: Session) -> dict:
    """
    Return pods sorted by CPU and RAM usage (descending).
    Returns a dict with 'by_cpu' and 'by_ram' lists of ConsumerInfo.
    """
    pods = db.query(Pod).all()
    consumers: list[ConsumerInfo] = []

    for pod in pods:
        latest_metric = (
            db.query(PodMetric)
            .filter(PodMetric.pod_id == pod.id)
            .order_by(PodMetric.collected_at.desc())
            .first()
        )
        if latest_metric:
            consumers.append(ConsumerInfo(
                pod_id=pod.id,
                pod_name=pod.name,
                namespace=pod.namespace,
                cpu_millicores=latest_metric.cpu_millicores or 0,
                ram_mb=latest_metric.ram_mb or 0,
            ))

    by_cpu = sorted(consumers, key=lambda c: c.cpu_millicores, reverse=True)
    by_ram = sorted(consumers, key=lambda c: c.ram_mb, reverse=True)

    return {
        "by_cpu": by_cpu,
        "by_ram": by_ram,
    }
