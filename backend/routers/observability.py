from typing import Optional, Any
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from ..config import settings
from ..database import get_db
from ..grafana_client import GrafanaClient, hours_range_ms
from ..models import VirtualMachine, Pod

router = APIRouter(prefix="/observability", tags=["Observabilite Grafana"])


class GrafanaQueryIn(BaseModel):
    datasource_uid: str
    queries: list[dict[str, Any]]
    from_ms: int = Field(alias="from")
    to_ms: int = Field(alias="to")


def _client() -> GrafanaClient:
    return GrafanaClient()


def _mock_logs(limit: int, level: Optional[str] = None, service: Optional[str] = None) -> list[dict]:
    now = datetime.utcnow()
    items = [
        ("error", "production/api-gateway", "worker-01", "upstream timeout while calling auth-service", "request_id=req-92fa latency=5100ms"),
        ("warning", "production/auth-service", "worker-01", "high authentication latency detected", "p95=980ms threshold=750ms"),
        ("info", "production/payment-service", "worker-02", "payment batch completed", "processed=182 status=ok"),
        ("critical", "data/etl-pipeline", "worker-04", "container failed after repeated restart", "exit_code=137 reason=OOMKilled"),
        ("warning", "infra/log-aggregator", "worker-02", "loki push retry after temporary failure", "retry=3 status=429"),
        ("error", "staging/db-test", "worker-05", "database readiness probe failed", "connection refused"),
        ("info", "vm-prod-web-01", "compute-01", "nginx access log shipped", "status=200 path=/health"),
        ("warning", "vm-prod-api-01", "compute-02", "cpu saturation observed by agent", "cpu=88 threshold=70"),
        ("error", "vm-db-primary", "compute-03", "slow query threshold exceeded", "duration=12.4s query=orders_report"),
        ("info", "infra/prometheus", "worker-01", "scrape cycle completed", "targets=42 failed=0"),
    ]
    logs = []
    for idx, (lvl, svc, location, message, context) in enumerate(items * max(1, (limit // len(items)) + 1)):
        if level and lvl != level:
            continue
        if service and service.lower() not in svc.lower():
            continue
        logs.append({
            "timestamp": (now - timedelta(minutes=idx * 3)).isoformat() + "Z",
            "level": lvl,
            "service": svc,
            "location": location,
            "message": message,
            "context": context,
            "source": "mock",
        })
        if len(logs) >= limit:
            break
    return logs


def _mock_visualizations(hours: int) -> dict:
    now = datetime.utcnow()
    points = []
    count = min(max(hours * 2, 12), 96)
    for idx in range(count):
        ts = now - timedelta(minutes=(count - idx - 1) * 30)
        wave = (idx % 8) * 3
        points.append({
            "time": ts.isoformat() + "Z",
            "cpu": min(96, 42 + wave + (12 if idx > count * 0.65 else 0)),
            "memory": min(94, 55 + (idx % 7) * 2 + (10 if idx > count * 0.72 else 0)),
            "disk": min(91, 48 + idx * 0.45),
            "containers": 128 + (idx % 9) * 3,
            "network_in": 220 + (idx % 6) * 18,
            "network_out": 175 + (idx % 5) * 15,
        })

    return {
        "source": "mock",
        "message": "Grafana metrics datasource not configured; returning demo visualization data",
        "period_hours": hours,
        "series": points,
        "latest": points[-1] if points else {},
        "distribution": [
            {"name": "VMs actives", "value": 9},
            {"name": "Pods running", "value": 13},
            {"name": "Pods en erreur", "value": 2},
            {"name": "Nodes pression", "value": 2},
        ],
        "capacity": [
            {"name": "CPU", "used": points[-1]["cpu"], "free": max(0, 100 - points[-1]["cpu"])},
            {"name": "RAM", "used": points[-1]["memory"], "free": max(0, 100 - points[-1]["memory"])},
            {"name": "Disque", "used": points[-1]["disk"], "free": max(0, 100 - points[-1]["disk"])},
            {"name": "Pods", "used": 61, "free": 39},
        ],
    }


def _extract_first_series(response: Any, ref_id: str) -> list[dict]:
    results = response.get("results", {}) if isinstance(response, dict) else {}
    frames = results.get(ref_id, {}).get("frames", [])
    if not frames:
        return []

    frame = frames[0]
    fields = frame.get("schema", {}).get("fields", [])
    values = frame.get("data", {}).get("values", [])
    if len(values) < 2:
        return []

    time_index = 0
    value_index = 1
    for idx, field in enumerate(fields):
        if field.get("type") == "time":
            time_index = idx
        if field.get("type") == "number":
            value_index = idx

    times = values[time_index] if len(values) > time_index else []
    numbers = values[value_index] if len(values) > value_index else []
    return [{"time": t, "value": round(float(v or 0), 2)} for t, v in zip(times, numbers)]


def _merge_series(series_by_key: dict[str, list[dict]]) -> list[dict]:
    merged: dict[str, dict] = {}
    for key, points in series_by_key.items():
        for point in points:
            ts = str(point["time"])
            merged.setdefault(ts, {"time": ts})
            merged[ts][key] = point["value"]
    return [merged[k] for k in sorted(merged.keys())]


@router.get("/grafana/health")
def grafana_health(client: GrafanaClient = Depends(_client)):
    try:
        return {"configured": client.configured, "grafana": client.health() if client.configured else None}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Grafana unavailable: {exc}") from exc


@router.post("/grafana/query")
def grafana_query(payload: GrafanaQueryIn, client: GrafanaClient = Depends(_client)):
    try:
        return client.query_datasource(payload.datasource_uid, payload.queries, payload.from_ms, payload.to_ms)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Grafana query failed: {exc}") from exc


@router.get("/metrics/infra")
def infrastructure_metrics(
    hours: int = Query(default=1, ge=1, le=168),
    db: Session = Depends(get_db),
    client: GrafanaClient = Depends(_client),
):
    local = {
        "vms": db.query(VirtualMachine).count(),
        "containers": db.query(Pod).count(),
        "clusters": len({p.namespace for p in db.query(Pod).all()}),
    }
    if not (client.configured and settings.GRAFANA_METRICS_DATASOURCE_UID):
        return {"source": "local", "message": "Grafana metrics datasource not configured", "summary": local}

    start, end = hours_range_ms(hours)
    queries = [
        {"refId": "vcpu", "expr": "sum(openstack_nova_vcpus_used)", "format": "time_series", "intervalMs": 30000, "maxDataPoints": 600},
        {"refId": "memory", "expr": "sum(node_memory_MemTotal_bytes - node_memory_MemAvailable_bytes)", "format": "time_series", "intervalMs": 30000, "maxDataPoints": 600},
        {"refId": "disk", "expr": "sum(node_filesystem_size_bytes - node_filesystem_free_bytes)", "format": "time_series", "intervalMs": 30000, "maxDataPoints": 600},
        {"refId": "containers", "expr": "count(kube_pod_container_info)", "format": "time_series", "intervalMs": 30000, "maxDataPoints": 600},
        {"refId": "clusters", "expr": "count(count by (cluster) (up))", "format": "time_series", "intervalMs": 30000, "maxDataPoints": 600},
    ]
    try:
        return {"source": "grafana", "summary": local, "data": client.query_datasource(settings.GRAFANA_METRICS_DATASOURCE_UID, queries, start, end)}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Grafana metrics query failed: {exc}") from exc


@router.get("/visualizations/main")
def main_visualizations(
    hours: int = Query(default=24, ge=1, le=168),
    client: GrafanaClient = Depends(_client),
):
    datasource_uid = (settings.GRAFANA_METRICS_DATASOURCE_UID or "").strip()
    if not (client.configured and datasource_uid and datasource_uid != "..."):
        return _mock_visualizations(hours)

    start, end = hours_range_ms(hours)
    queries = [
        {"refId": "cpu", "expr": "100 - (avg(rate(node_cpu_seconds_total{mode=\"idle\"}[5m])) * 100)", "format": "time_series", "intervalMs": 30000, "maxDataPoints": 600},
        {"refId": "memory", "expr": "100 * (1 - (sum(node_memory_MemAvailable_bytes) / sum(node_memory_MemTotal_bytes)))", "format": "time_series", "intervalMs": 30000, "maxDataPoints": 600},
        {"refId": "disk", "expr": "100 * (1 - (sum(node_filesystem_free_bytes{fstype!=\"tmpfs\"}) / sum(node_filesystem_size_bytes{fstype!=\"tmpfs\"})))", "format": "time_series", "intervalMs": 30000, "maxDataPoints": 600},
        {"refId": "containers", "expr": "count(kube_pod_container_info)", "format": "time_series", "intervalMs": 30000, "maxDataPoints": 600},
        {"refId": "network_in", "expr": "sum(rate(node_network_receive_bytes_total[5m])) / 1024 / 1024", "format": "time_series", "intervalMs": 30000, "maxDataPoints": 600},
        {"refId": "network_out", "expr": "sum(rate(node_network_transmit_bytes_total[5m])) / 1024 / 1024", "format": "time_series", "intervalMs": 30000, "maxDataPoints": 600},
    ]

    try:
        response = client.query_datasource(datasource_uid, queries, start, end)
        series = _merge_series({
            "cpu": _extract_first_series(response, "cpu"),
            "memory": _extract_first_series(response, "memory"),
            "disk": _extract_first_series(response, "disk"),
            "containers": _extract_first_series(response, "containers"),
            "network_in": _extract_first_series(response, "network_in"),
            "network_out": _extract_first_series(response, "network_out"),
        })
        latest = series[-1] if series else {}
        return {
            "source": "grafana",
            "period_hours": hours,
            "series": series,
            "latest": latest,
            "distribution": [],
            "capacity": [
                {"name": "CPU", "used": latest.get("cpu", 0), "free": max(0, 100 - latest.get("cpu", 0))},
                {"name": "RAM", "used": latest.get("memory", 0), "free": max(0, 100 - latest.get("memory", 0))},
                {"name": "Disque", "used": latest.get("disk", 0), "free": max(0, 100 - latest.get("disk", 0))},
            ],
        }
    except Exception:
        return _mock_visualizations(hours)


@router.get("/logs")
def logs(
    selector: str = Query(default="{job=~\".+\"}"),
    hours: int = Query(default=1, ge=1, le=24),
    limit: int = Query(default=100, ge=1, le=1000),
    level: Optional[str] = Query(default=None),
    service: Optional[str] = Query(default=None),
    client: GrafanaClient = Depends(_client),
):
    datasource_uid = (settings.GRAFANA_LOGS_DATASOURCE_UID or "").strip()
    if not (client.configured and datasource_uid and datasource_uid != "..."):
        return {
            "source": "mock",
            "message": "Grafana logs datasource not configured; returning demo logs",
            "logs": _mock_logs(limit, level=level, service=service),
        }
    start, end = hours_range_ms(hours)
    queries = [{"refId": "logs", "expr": selector, "queryType": "range", "maxLines": limit, "datasource": {"uid": datasource_uid}}]
    try:
        return {"source": "grafana", "data": client.query_datasource(datasource_uid, queries, start, end)}
    except Exception:
        return {
            "source": "mock",
            "message": "Grafana logs query failed; returning demo logs",
            "logs": _mock_logs(limit, level=level, service=service),
        }


@router.get("/traces")
def traces(
    service: Optional[str] = Query(default=None),
    hours: int = Query(default=1, ge=1, le=24),
    limit: int = Query(default=20, ge=1, le=100),
    client: GrafanaClient = Depends(_client),
):
    if not (client.configured and settings.GRAFANA_TRACES_DATASOURCE_UID):
        return {"source": "none", "message": "Grafana traces datasource not configured", "traces": []}
    start, end = hours_range_ms(hours)
    query = f'{{ resource.service.name = "{service}" }}' if service else "{}"
    queries = [{"refId": "traces", "query": query, "queryType": "traceqlSearch", "limit": limit, "datasource": {"uid": settings.GRAFANA_TRACES_DATASOURCE_UID}}]
    try:
        return {"source": "grafana", "data": client.query_datasource(settings.GRAFANA_TRACES_DATASOURCE_UID, queries, start, end)}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Grafana traces query failed: {exc}") from exc
