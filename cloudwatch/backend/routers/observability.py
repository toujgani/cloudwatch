from typing import Optional, Any
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


@router.get("/logs")
def logs(
    selector: str = Query(default="{job=~\".+\"}"),
    hours: int = Query(default=1, ge=1, le=24),
    limit: int = Query(default=100, ge=1, le=1000),
    client: GrafanaClient = Depends(_client),
):
    if not (client.configured and settings.GRAFANA_LOGS_DATASOURCE_UID):
        return {"source": "none", "message": "Grafana logs datasource not configured", "logs": []}
    start, end = hours_range_ms(hours)
    queries = [{"refId": "logs", "expr": selector, "queryType": "range", "maxLines": limit, "datasource": {"uid": settings.GRAFANA_LOGS_DATASOURCE_UID}}]
    try:
        return {"source": "grafana", "data": client.query_datasource(settings.GRAFANA_LOGS_DATASOURCE_UID, queries, start, end)}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Grafana logs query failed: {exc}") from exc


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
