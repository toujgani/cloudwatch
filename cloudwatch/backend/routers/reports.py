import csv
import io
from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Alert, Pod, PodMetric, SeverityEnum, StatusEnum, VirtualMachine, VMMetric

router = APIRouter(prefix="/reports", tags=["Rapports"])


def _csv_response(filename: str, rows: list[dict]):
    buffer = io.StringIO()
    fieldnames = list(rows[0].keys()) if rows else ["message"]
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    if rows:
        writer.writerows(rows)
    else:
        writer.writerow({"message": "Aucune donnee"})

    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/summary")
def summary(hours: int = Query(default=24, ge=1, le=720), db: Session = Depends(get_db)):
    since = datetime.utcnow() - timedelta(hours=hours)

    vm_metrics = db.query(VMMetric).filter(VMMetric.collected_at >= since).all()
    pod_metrics = db.query(PodMetric).filter(PodMetric.collected_at >= since).all()
    active_alerts = db.query(Alert).filter(Alert.status == StatusEnum.active).all()
    period_alerts = db.query(Alert).filter(Alert.triggered_at >= since).all()

    avg_cpu = sum(m.cpu_percent or 0 for m in vm_metrics) / max(len(vm_metrics), 1)
    avg_ram = sum(m.ram_percent or 0 for m in vm_metrics) / max(len(vm_metrics), 1)
    avg_pod_ram = sum(m.ram_mb or 0 for m in pod_metrics) / max(len(pod_metrics), 1)

    return {
        "period_hours": hours,
        "generated_at": datetime.utcnow(),
        "inventory": {
            "vms": db.query(VirtualMachine).count(),
            "pods": db.query(Pod).count(),
        },
        "availability": {
            "active_vms": db.query(VirtualMachine).filter(VirtualMachine.status == "ACTIVE").count(),
            "running_pods": db.query(Pod).filter(Pod.status == "Running").count(),
            "failed_pods": db.query(Pod).filter(Pod.status.in_(["Failed", "Unknown"])).count(),
        },
        "metrics": {
            "avg_vm_cpu": round(avg_cpu, 1),
            "avg_vm_ram": round(avg_ram, 1),
            "avg_pod_ram_mb": round(avg_pod_ram, 1),
        },
        "alerts": {
            "active": len(active_alerts),
            "critical_active": sum(1 for a in active_alerts if a.severity == SeverityEnum.critical),
            "warning_active": sum(1 for a in active_alerts if a.severity == SeverityEnum.warning),
            "triggered_in_period": len(period_alerts),
            "acknowledged_active": sum(1 for a in active_alerts if a.acknowledged),
        },
    }


@router.get("/export/{kind}")
def export_csv(
    kind: Literal["alerts", "vms", "pods"] = "alerts",
    status: StatusEnum | None = Query(default=None),
    db: Session = Depends(get_db),
):
    if kind == "alerts":
        q = db.query(Alert)
        if status:
            q = q.filter(Alert.status == status)
        rows = [
            {
                "id": a.id,
                "severity": a.severity.value,
                "status": a.status.value,
                "title": a.title,
                "resource": a.vm_id or a.pod_id or "",
                "rule": a.rule_name or "",
                "metric_value": a.metric_value,
                "threshold": a.threshold,
                "acknowledged": a.acknowledged,
                "acknowledged_by": a.acknowledged_by or "",
                "operator_note": a.operator_note or "",
                "triggered_at": a.triggered_at.isoformat() if a.triggered_at else "",
                "resolved_at": a.resolved_at.isoformat() if a.resolved_at else "",
            }
            for a in q.order_by(desc(Alert.triggered_at)).all()
        ]
        return _csv_response("alerts.csv", rows)

    if kind == "vms":
        rows = []
        for vm in db.query(VirtualMachine).order_by(VirtualMachine.name).all():
            latest = (
                db.query(VMMetric)
                .filter(VMMetric.vm_id == vm.id)
                .order_by(desc(VMMetric.collected_at))
                .first()
            )
            rows.append({
                "id": vm.id,
                "name": vm.name,
                "status": vm.status,
                "flavor": vm.flavor or "",
                "host": vm.host or "",
                "cpu_percent": latest.cpu_percent if latest else "",
                "ram_percent": latest.ram_percent if latest else "",
                "updated_at": vm.updated_at.isoformat() if vm.updated_at else "",
            })
        return _csv_response("vms.csv", rows)

    rows = []
    for pod in db.query(Pod).order_by(Pod.namespace, Pod.name).all():
        latest = (
            db.query(PodMetric)
            .filter(PodMetric.pod_id == pod.id)
            .order_by(desc(PodMetric.collected_at))
            .first()
        )
        rows.append({
            "id": pod.id,
            "name": pod.name,
            "namespace": pod.namespace,
            "status": pod.status,
            "node": pod.node or "",
            "restart_count": pod.restart_count,
            "cpu_millicores": latest.cpu_millicores if latest else "",
            "ram_mb": latest.ram_mb if latest else "",
            "updated_at": pod.updated_at.isoformat() if pod.updated_at else "",
        })
    return _csv_response("pods.csv", rows)
