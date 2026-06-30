from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import datetime
from typing import Optional
from ..database import get_db
from ..models import Alert, SeverityEnum, StatusEnum
from pydantic import BaseModel

router = APIRouter(prefix="/alerts", tags=["Alertes"])


class AlertOut(BaseModel):
    id: int
    severity: SeverityEnum
    status: StatusEnum
    title: str
    description: Optional[str]
    rule_name: Optional[str]
    metric_value: Optional[float]
    threshold: Optional[float]
    acknowledged: bool = False
    acknowledged_by: Optional[str]
    acknowledged_at: Optional[datetime]
    operator_note: Optional[str]
    vm_id: Optional[str]
    pod_id: Optional[str]
    triggered_at: datetime
    resolved_at: Optional[datetime]

    model_config = {"from_attributes": True}


class AlertActionIn(BaseModel):
    operator: str = "operator"
    note: Optional[str] = None


@router.get("/", response_model=list[AlertOut])
def list_alerts(
    status: Optional[StatusEnum] = Query(default=None),
    severity: Optional[SeverityEnum] = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Liste les alertes, filtrables par statut et sévérité."""
    q = db.query(Alert)
    if status:
        q = q.filter(Alert.status == status)
    if severity:
        q = q.filter(Alert.severity == severity)
    return q.order_by(desc(Alert.triggered_at)).limit(limit).all()


@router.get("/summary/stats")
def alerts_summary(db: Session = Depends(get_db)):
    active = db.query(Alert).filter(Alert.status == StatusEnum.active).all()
    return {
        "total_active": len(active),
        "critical": sum(1 for a in active if a.severity == SeverityEnum.critical),
        "warning":  sum(1 for a in active if a.severity == SeverityEnum.warning),
        "info":     sum(1 for a in active if a.severity == SeverityEnum.info),
        "acknowledged": sum(1 for a in active if a.acknowledged),
    }


@router.patch("/{alert_id}/acknowledge", response_model=AlertOut)
def acknowledge_alert(alert_id: int, payload: AlertActionIn, db: Session = Depends(get_db)):
    """Acquitter une alerte et garder une trace operateur."""
    alert = db.get(Alert, alert_id)
    if not alert:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.acknowledged = True
    alert.acknowledged_by = payload.operator.strip() or "operator"
    alert.acknowledged_at = datetime.utcnow()
    if payload.note:
        alert.operator_note = payload.note
    db.commit()
    db.refresh(alert)
    return alert


@router.patch("/{alert_id}/resolve", response_model=AlertOut)
def resolve_alert(alert_id: int, payload: AlertActionIn | None = None, db: Session = Depends(get_db)):
    """Résoudre manuellement une alerte."""
    alert = db.get(Alert, alert_id)
    if not alert:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Alert not found")
    alert.status = StatusEnum.resolved
    alert.resolved_at = datetime.utcnow()
    if payload:
        alert.acknowledged = True
        alert.acknowledged_by = payload.operator.strip() or "operator"
        alert.acknowledged_at = alert.acknowledged_at or datetime.utcnow()
        if payload.note:
            alert.operator_note = payload.note
    db.commit()
    db.refresh(alert)
    return alert
