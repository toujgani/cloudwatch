"""
Cost Analysis Router — calculates infrastructure costs from real collected metrics.
Uses actual pod CPU/RAM usage data stored in PostgreSQL to compute costs.

Pricing model based on CIRES Technologies internal cloud billing:
  - CPU: billed per vCPU-hour of actual usage
  - RAM: billed per GB-hour of actual usage
  - Storage: billed per GB-month provisioned
  - Network: estimated from pod count and activity
  - Incident response: cost of manual intervention avoided by AI
"""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..database import get_db
from ..config import settings
from ..models import PodMetric, VMMetric, Alert, StatusEnum, Pod, VirtualMachine

router = APIRouter(prefix="/costs", tags=["Cost Analysis"])

# CIRES internal pricing (per hour, realistic Moroccan cloud provider rates)
# Based on typical private cloud TCO: servers + power + cooling + admin
PRICING = {
    "cpu_per_core_hour": 0.045,       # €/vCPU-hour
    "ram_per_gb_hour": 0.006,         # €/GB-hour
    "storage_per_gb_month": 0.10,     # €/GB/month (SSD)
    "network_per_gb": 0.08,           # €/GB egress
    "pod_scheduling_hour": 0.003,     # €/pod-hour (orchestration overhead)
    "vm_base_hour": 0.12,             # €/VM-hour (hypervisor + host)
    "incident_manual_cost": 180.0,    # € per manual incident (30min engineer @ 360€/day)
    "downtime_cost_per_minute": 50.0, # € per minute of unplanned downtime
}


@router.get("/summary")
def cost_summary(hours: int = Query(default=720, ge=1, le=87600), db: Session = Depends(get_db)):
    """
    Calculate total infrastructure cost from real collected metrics.
    Uses actual CPU/RAM measurements stored in pod_metrics and vm_metrics tables.
    """
    since = datetime.utcnow() - timedelta(hours=hours)

    # ── Pod costs (from real metrics) ─────────────────────────────────────────
    pod_metrics = db.query(
        func.avg(PodMetric.cpu_millicores).label("avg_cpu_m"),
        func.avg(PodMetric.ram_mb).label("avg_ram_mb"),
        func.count(PodMetric.id).label("sample_count"),
    ).filter(PodMetric.collected_at >= since).first()

    avg_cpu_cores = (pod_metrics.avg_cpu_m or 0) / 1000
    avg_ram_gb = (pod_metrics.avg_ram_mb or 0) / 1024
    pod_sample_count = pod_metrics.sample_count or 0

    # Current pod count
    active_pods = db.query(Pod).count()

    # Pod compute costs
    pod_cpu_cost = avg_cpu_cores * PRICING["cpu_per_core_hour"] * hours
    pod_ram_cost = avg_ram_gb * PRICING["ram_per_gb_hour"] * hours
    pod_scheduling_cost = active_pods * PRICING["pod_scheduling_hour"] * hours

    # ── VM costs (from real metrics if OpenStack connected) ───────────────────
    vm_metrics = db.query(
        func.avg(VMMetric.cpu_percent).label("avg_cpu_pct"),
        func.avg(VMMetric.ram_percent).label("avg_ram_pct"),
        func.count(VMMetric.id).label("sample_count"),
    ).filter(VMMetric.collected_at >= since).first()

    active_vms = db.query(VirtualMachine).count()
    vm_base_cost = active_vms * PRICING["vm_base_hour"] * hours

    # ── Storage costs ─────────────────────────────────────────────────────────
    # Read from actual PVC usage via K8s API
    storage_gb = 0
    try:
        from .. import openshift_client as k8s
        namespace = settings.KUBE_NAMESPACE or "red1intheocean-dev"
        s = k8s._session()
        path = f"/api/v1/namespaces/{namespace}/persistentvolumeclaims"
        resp = s.get(k8s._url(path), timeout=10)
        if resp.status_code == 200:
            for pvc in resp.json().get("items", []):
                spec = pvc.get("spec", {}).get("resources", {}).get("requests", {})
                storage_str = spec.get("storage", "0")
                if storage_str.endswith("Gi"):
                    storage_gb += int(storage_str[:-2])
                elif storage_str.endswith("Mi"):
                    storage_gb += int(storage_str[:-2]) / 1024
    except Exception:
        storage_gb = 2  # fallback
    storage_cost = max(storage_gb, 1) * PRICING["storage_per_gb_month"] * (hours / 720)

    # ── Network (estimated from pod activity) ─────────────────────────────────
    # Estimate: each pod generates ~50MB/hour of network traffic
    network_gb = active_pods * 0.05 * hours / 1024
    network_cost = network_gb * PRICING["network_per_gb"]

    # ── AI savings ────────────────────────────────────────────────────────────
    resolved_by_ai = db.query(Alert).filter(
        Alert.status == StatusEnum.resolved,
        Alert.remediation_status.in_(["applied", "dry_run"]),
        Alert.resolved_at >= since,
    ).count()

    total_alerts_period = db.query(Alert).filter(
        Alert.triggered_at >= since,
    ).count()

    incident_cost_avoided = resolved_by_ai * PRICING["incident_manual_cost"]

    # Estimate downtime avoided: each AI remediation saves ~5 min of downtime
    downtime_minutes_avoided = resolved_by_ai * 5
    downtime_cost_avoided = downtime_minutes_avoided * PRICING["downtime_cost_per_minute"]

    total_savings = incident_cost_avoided + downtime_cost_avoided

    # ── Totals ────────────────────────────────────────────────────────────────
    total_cost = pod_cpu_cost + pod_ram_cost + pod_scheduling_cost + vm_base_cost + storage_cost + network_cost

    return {
        "period_hours": hours,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "pricing_model": PRICING,
        "metrics_source": {
            "pod_samples": pod_sample_count,
            "vm_samples": vm_metrics.sample_count or 0,
            "avg_cpu_cores": round(avg_cpu_cores, 4),
            "avg_ram_gb": round(avg_ram_gb, 3),
            "active_pods": active_pods,
            "active_vms": active_vms,
        },
        "costs": {
            "pod_cpu": round(pod_cpu_cost, 2),
            "pod_ram": round(pod_ram_cost, 2),
            "pod_scheduling": round(pod_scheduling_cost, 2),
            "vm_base": round(vm_base_cost, 2),
            "storage": round(storage_cost, 2),
            "network": round(network_cost, 2),
            "total": round(total_cost, 2),
        },
        "savings": {
            "incidents_resolved_by_ai": resolved_by_ai,
            "total_alerts_period": total_alerts_period,
            "incident_cost_avoided": round(incident_cost_avoided, 2),
            "downtime_minutes_avoided": downtime_minutes_avoided,
            "downtime_cost_avoided": round(downtime_cost_avoided, 2),
            "total_savings": round(total_savings, 2),
        },
        "projections": {
            "monthly_cost": round(total_cost / max(hours, 1) * 720, 2),
            "yearly_cost": round(total_cost / max(hours, 1) * 8760, 2),
            "monthly_savings": round(total_savings / max(hours, 1) * 720, 2),
            "yearly_savings": round(total_savings / max(hours, 1) * 8760, 2),
            "roi_percent": round((total_savings / max(total_cost, 0.01)) * 100, 1),
        },
    }


@router.get("/timeline")
def cost_timeline(hours: int = Query(default=168, ge=1, le=8760), db: Session = Depends(get_db)):
    """
    Cost over time — returns hourly cost data points for graphing.
    Groups pod metrics by hour and calculates cost for each hour.
    """
    since = datetime.utcnow() - timedelta(hours=hours)

    # Get hourly aggregated metrics
    # Group by hour
    results = db.query(
        func.date_trunc('hour', PodMetric.collected_at).label("hour"),
        func.avg(PodMetric.cpu_millicores).label("avg_cpu"),
        func.avg(PodMetric.ram_mb).label("avg_ram"),
        func.count(func.distinct(PodMetric.pod_id)).label("pod_count"),
    ).filter(
        PodMetric.collected_at >= since,
    ).group_by(
        func.date_trunc('hour', PodMetric.collected_at),
    ).order_by(
        func.date_trunc('hour', PodMetric.collected_at),
    ).all()

    timeline = []
    for row in results:
        cpu_cores = (row.avg_cpu or 0) / 1000
        ram_gb = (row.avg_ram or 0) / 1024
        pods = row.pod_count or 0

        hourly_cost = (
            cpu_cores * PRICING["cpu_per_core_hour"]
            + ram_gb * PRICING["ram_per_gb_hour"]
            + pods * PRICING["pod_scheduling_hour"]
        )

        timeline.append({
            "time": row.hour.isoformat() if row.hour else None,
            "cost": round(hourly_cost, 4),
            "cpu_cost": round(cpu_cores * PRICING["cpu_per_core_hour"], 4),
            "ram_cost": round(ram_gb * PRICING["ram_per_gb_hour"], 4),
            "pods": pods,
        })

    return {
        "period_hours": hours,
        "data_points": len(timeline),
        "timeline": timeline,
    }
