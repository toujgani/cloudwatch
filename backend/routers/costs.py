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
import random
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


# ─── Mock cost data generators ───────────────────────────────────────────────

def _mock_cost_summary(hours: int) -> dict:
    """Generate realistic mock cost summary for demos."""
    # Simulate a fleet: 8 pods, 7 VMs over the period
    active_pods = 8
    active_vms = 7
    avg_cpu_cores = round(random.uniform(1.8, 3.2), 4)
    avg_ram_gb = round(random.uniform(4.5, 8.0), 3)

    pod_cpu_cost = avg_cpu_cores * PRICING["cpu_per_core_hour"] * hours
    pod_ram_cost = avg_ram_gb * PRICING["ram_per_gb_hour"] * hours
    pod_scheduling_cost = active_pods * PRICING["pod_scheduling_hour"] * hours
    vm_base_cost = active_vms * PRICING["vm_base_hour"] * hours
    storage_gb = 50
    storage_cost = storage_gb * PRICING["storage_per_gb_month"] * (hours / 720)
    network_gb = active_pods * 0.05 * hours / 1024
    network_cost = network_gb * PRICING["network_per_gb"]

    total_cost = pod_cpu_cost + pod_ram_cost + pod_scheduling_cost + vm_base_cost + storage_cost + network_cost

    # AI savings — simulate 6 resolved incidents
    resolved_by_ai = 6
    total_alerts_period = 9
    incident_cost_avoided = resolved_by_ai * PRICING["incident_manual_cost"]
    downtime_minutes_avoided = resolved_by_ai * 5
    downtime_cost_avoided = downtime_minutes_avoided * PRICING["downtime_cost_per_minute"]
    total_savings = incident_cost_avoided + downtime_cost_avoided

    return {
        "period_hours": hours,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "pricing_model": PRICING,
        "metrics_source": {
            "pod_samples": hours * 12,  # ~12 samples/hour
            "vm_samples": hours * 8,
            "avg_cpu_cores": avg_cpu_cores,
            "avg_ram_gb": avg_ram_gb,
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


def _mock_cost_timeline(hours: int) -> dict:
    """Generate realistic mock hourly cost timeline for the graph."""
    now = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    timeline = []

    # Create a realistic cost curve: base load + daily pattern + some noise
    for i in range(hours):
        t = now - timedelta(hours=hours - i)
        hour_of_day = t.hour

        # Daily pattern: lower at night (0-6), ramp up morning, peak afternoon, taper evening
        if 0 <= hour_of_day < 6:
            load_factor = 0.4 + random.uniform(-0.05, 0.05)
        elif 6 <= hour_of_day < 9:
            load_factor = 0.6 + (hour_of_day - 6) * 0.1 + random.uniform(-0.05, 0.05)
        elif 9 <= hour_of_day < 18:
            load_factor = 0.85 + random.uniform(-0.1, 0.15)
        elif 18 <= hour_of_day < 22:
            load_factor = 0.7 - (hour_of_day - 18) * 0.05 + random.uniform(-0.05, 0.05)
        else:
            load_factor = 0.5 + random.uniform(-0.05, 0.05)

        # Base fleet: ~2.5 CPU cores, ~6 GB RAM, 8 pods
        cpu_cores = 2.5 * load_factor
        ram_gb = 6.0 * load_factor
        pods = 8

        cpu_cost = cpu_cores * PRICING["cpu_per_core_hour"]
        ram_cost = ram_gb * PRICING["ram_per_gb_hour"]
        sched_cost = pods * PRICING["pod_scheduling_hour"]
        hourly_cost = cpu_cost + ram_cost + sched_cost

        # Add VM costs spread across the hours
        vm_hourly = 7 * PRICING["vm_base_hour"] * load_factor
        hourly_cost += vm_hourly

        timeline.append({
            "time": t.isoformat(),
            "cost": round(hourly_cost, 4),
            "cpu_cost": round(cpu_cost, 4),
            "ram_cost": round(ram_cost, 4),
            "vm_cost": round(vm_hourly, 4),
            "pods": pods,
        })

    return {
        "period_hours": hours,
        "data_points": len(timeline),
        "timeline": timeline,
    }


def _is_mock_mode() -> bool:
    """Check if we're running in any mock mode (costs depend on pod/VM data)."""
    return settings.MOCK_OPENSTACK or settings.MOCK_KUBERNETES or settings.MOCK_OPENSHIFT


@router.get("/summary")
def cost_summary(hours: int = Query(default=720, ge=1, le=87600), db: Session = Depends(get_db)):
    """
    Calculate total infrastructure cost from real collected metrics.
    Uses actual CPU/RAM measurements stored in pod_metrics and vm_metrics tables.
    Falls back to mock data when mock mode is active and no real data exists.
    """
    since = datetime.utcnow() - timedelta(hours=hours)

    # Check if we have real data or should use mock
    real_sample_count = db.query(func.count(PodMetric.id)).filter(
        PodMetric.collected_at >= since
    ).scalar() or 0

    if _is_mock_mode() and real_sample_count < 10:
        return _mock_cost_summary(hours)

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
        namespace = settings.KUBE_NAMESPACE or "default"
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
    Falls back to mock data when mock mode is active and no real data exists.
    """
    since = datetime.utcnow() - timedelta(hours=hours)

    # Check if we have real data or should use mock
    real_sample_count = db.query(func.count(PodMetric.id)).filter(
        PodMetric.collected_at >= since
    ).scalar() or 0

    if _is_mock_mode() and real_sample_count < 10:
        return _mock_cost_timeline(hours)

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
