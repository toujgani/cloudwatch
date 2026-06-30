from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import datetime, timedelta
from typing import Optional
from ..database import get_db
from ..models import Pod, PodMetric
from pydantic import BaseModel

router = APIRouter(prefix="/pods", tags=["Pods OpenShift"])


class PodOut(BaseModel):
    id: str
    name: str
    namespace: str
    status: str
    node: Optional[str]
    restart_count: int
    image: Optional[str]
    cpu_millicores: Optional[float]
    ram_mb: Optional[float]
    updated_at: Optional[datetime]

    model_config = {"from_attributes": True}


class PodMetricPoint(BaseModel):
    collected_at: datetime
    cpu_millicores: Optional[float]
    ram_mb: Optional[float]
    restart_count: int

    model_config = {"from_attributes": True}


@router.get("/", response_model=list[PodOut])
def list_pods(
    namespace: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    q = db.query(Pod)
    if namespace:
        q = q.filter(Pod.namespace == namespace)
    pods = q.order_by(Pod.namespace, Pod.name).all()

    result = []
    for pod in pods:
        latest = (
            db.query(PodMetric)
            .filter(PodMetric.pod_id == pod.id)
            .order_by(desc(PodMetric.collected_at))
            .first()
        )
        result.append(PodOut(
            id=pod.id, name=pod.name, namespace=pod.namespace,
            status=pod.status, node=pod.node,
            restart_count=pod.restart_count, image=pod.image,
            cpu_millicores = latest.cpu_millicores if latest else None,
            ram_mb         = latest.ram_mb         if latest else None,
            updated_at     = pod.updated_at,
        ))
    return result


@router.get("/summary/stats")
def pods_summary(db: Session = Depends(get_db)):
    pods = db.query(Pod).all()
    return {
        "total":     len(pods),
        "running":   sum(1 for p in pods if p.status == "Running"),
        "pending":   sum(1 for p in pods if p.status == "Pending"),
        "failed":    sum(1 for p in pods if p.status in ("Failed", "Unknown")),
        "namespaces": list({p.namespace for p in pods}),
    }


@router.get("/{pod_id:path}/metrics", response_model=list[PodMetricPoint])
def get_pod_metrics(
    pod_id: str,
    hours: int = Query(default=24, ge=1, le=168),
    db: Session = Depends(get_db),
):
    since = datetime.utcnow() - timedelta(hours=hours)
    return (
        db.query(PodMetric)
        .filter(PodMetric.pod_id == pod_id, PodMetric.collected_at >= since)
        .order_by(PodMetric.collected_at)
        .all()
    )
