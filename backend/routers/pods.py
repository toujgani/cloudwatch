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


@router.delete("/{pod_id:path}")
def delete_pod_endpoint(pod_id: str, db: Session = Depends(get_db)):
    """
    Delete a pod via the Kubernetes API.
    If the pod no longer exists (404), remove it from the database anyway.
    This handles stale entries gracefully.
    """
    from .. import openshift_client
    from ..models import PodMetric as PodMetricModel

    # Try to delete from Kubernetes
    k8s_success = False
    k8s_gone = False
    try:
        openshift_client.delete_pod(pod_id)
        k8s_success = True
    except Exception as e:
        error_str = str(e)
        # If 404, pod doesn't exist in K8s anymore — that's fine, just clean DB
        if "404" in error_str or "Not Found" in error_str:
            k8s_gone = True
        else:
            # Real error (permission, network, etc.)
            from fastapi import HTTPException
            raise HTTPException(status_code=500, detail=f"Erreur Kubernetes: {error_str}")

    # Always clean from database
    db_pod = db.get(Pod, pod_id)
    if db_pod:
        db.query(PodMetricModel).filter(PodMetricModel.pod_id == pod_id).delete()
        db.delete(db_pod)
        db.commit()

    if k8s_success:
        return {"status": "deleted", "pod_id": pod_id, "message": f"Pod {pod_id} supprime de Kubernetes et de la base."}
    elif k8s_gone:
        return {"status": "cleaned", "pod_id": pod_id, "message": f"Pod {pod_id} n'existait plus dans Kubernetes. Entree base de donnees nettoyee."}
