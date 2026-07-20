from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import datetime, timedelta
from typing import Optional
from ..database import get_db
from ..models import VirtualMachine, VMMetric
from pydantic import BaseModel

router = APIRouter(prefix="/vms", tags=["Virtual Machines"])


# ─── Schemas ──────────────────────────────────────────────────────────────────

class VMOut(BaseModel):
    id: str
    name: str
    status: str
    flavor: Optional[str]
    host: Optional[str]
    cpu_percent: Optional[float]
    ram_percent: Optional[float]
    ram_used_mb: Optional[float]
    ram_total_mb: Optional[float]
    updated_at: Optional[datetime]

    model_config = {"from_attributes": True}


class MetricPoint(BaseModel):
    collected_at: datetime
    cpu_percent: Optional[float]
    ram_percent: Optional[float]
    disk_read_mb: Optional[float]
    disk_write_mb: Optional[float]

    model_config = {"from_attributes": True}


# ─── Routes ───────────────────────────────────────────────────────────────────

@router.get("/", response_model=list[VMOut])
def list_vms(db: Session = Depends(get_db)):
    """Liste toutes les VMs avec leur dernière métrique."""
    vms = db.query(VirtualMachine).order_by(VirtualMachine.name).all()
    result = []
    for vm in vms:
        latest = (
            db.query(VMMetric)
            .filter(VMMetric.vm_id == vm.id)
            .order_by(desc(VMMetric.collected_at))
            .first()
        )
        out = VMOut(
            id=vm.id, name=vm.name, status=vm.status,
            flavor=vm.flavor, host=vm.host,
            cpu_percent  = latest.cpu_percent   if latest else None,
            ram_percent  = latest.ram_percent   if latest else None,
            ram_used_mb  = latest.ram_used_mb   if latest else None,
            ram_total_mb = latest.ram_total_mb  if latest else None,
            updated_at   = vm.updated_at,
        )
        result.append(out)
    return result


@router.get("/{vm_id}", response_model=VMOut)
def get_vm(vm_id: str, db: Session = Depends(get_db)):
    vm = db.query(VirtualMachine).filter(VirtualMachine.id == vm_id).first()
    if not vm:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="VM not found")
    latest = (
        db.query(VMMetric)
        .filter(VMMetric.vm_id == vm_id)
        .order_by(desc(VMMetric.collected_at))
        .first()
    )
    return VMOut(
        id=vm.id, name=vm.name, status=vm.status,
        flavor=vm.flavor, host=vm.host,
        cpu_percent  = latest.cpu_percent   if latest else None,
        ram_percent  = latest.ram_percent   if latest else None,
        ram_used_mb  = latest.ram_used_mb   if latest else None,
        ram_total_mb = latest.ram_total_mb  if latest else None,
        updated_at   = vm.updated_at,
    )


@router.get("/{vm_id}/metrics", response_model=list[MetricPoint])
def get_vm_metrics(
    vm_id: str,
    hours: int = Query(default=24, ge=1, le=87600),
    db: Session = Depends(get_db),
):
    """Historique des métriques d'une VM sur N heures (défaut: 24h)."""
    since = datetime.utcnow() - timedelta(hours=hours)
    metrics = (
        db.query(VMMetric)
        .filter(VMMetric.vm_id == vm_id, VMMetric.collected_at >= since)
        .order_by(VMMetric.collected_at)
        .all()
    )
    return metrics


@router.get("/summary/stats")
def vms_summary(db: Session = Depends(get_db)):
    """KPI rapide: total, actives, erreurs."""
    vms = db.query(VirtualMachine).all()
    return {
        "total":   len(vms),
        "active":  sum(1 for v in vms if v.status == "ACTIVE"),
        "shutoff": sum(1 for v in vms if v.status == "SHUTOFF"),
        "error":   sum(1 for v in vms if v.status == "ERROR"),
    }
