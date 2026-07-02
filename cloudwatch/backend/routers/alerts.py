from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from datetime import datetime
from typing import Optional
from ..database import get_db
from ..models import Alert, SeverityEnum, StatusEnum
from ..ai_agent import apply_decision
from ..remediation_agent import execute_remediation
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
    ai_score: Optional[int]
    ai_decision: Optional[str]
    ai_category: Optional[str]
    ai_reason: Optional[str]
    ai_recommendation: Optional[str]
    ai_confidence: Optional[float]
    ai_updated_at: Optional[datetime]
    remediation_action: Optional[str]
    remediation_status: Optional[str]
    remediation_message: Optional[str]
    remediation_updated_at: Optional[datetime]
    vm_id: Optional[str]
    pod_id: Optional[str]
    triggered_at: datetime
    resolved_at: Optional[datetime]

    model_config = {"from_attributes": True}


class AlertActionIn(BaseModel):
    operator: str = "operator"
    note: Optional[str] = None


class RemediationIn(BaseModel):
    operator: str = "AI-Agent"
    force: bool = False


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


@router.post("/agent/reprocess", response_model=list[AlertOut])
def reprocess_active_alerts(db: Session = Depends(get_db)):
    """Recalcule les decisions IA pour toutes les alertes actives."""
    alerts = db.query(Alert).filter(Alert.status == StatusEnum.active).all()
    for alert in alerts:
        apply_decision(db, alert)
    db.commit()
    for alert in alerts:
        db.refresh(alert)
    return alerts


@router.post("/{alert_id}/agent", response_model=AlertOut)
def reprocess_alert(alert_id: int, db: Session = Depends(get_db)):
    """Recalcule la decision IA d'une alerte."""
    alert = db.get(Alert, alert_id)
    if not alert:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Alert not found")
    apply_decision(db, alert)
    db.commit()
    db.refresh(alert)
    return alert


@router.post("/{alert_id}/remediate", response_model=AlertOut)
def remediate_alert(alert_id: int, payload: RemediationIn, db: Session = Depends(get_db)):
    """Lance une intervention rapide controlee pour une alerte."""
    alert = db.get(Alert, alert_id)
    if not alert:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Alert not found")
    execute_remediation(db, alert, operator=payload.operator, force=payload.force)
    db.commit()
    db.refresh(alert)
    return alert


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
    apply_decision(db, alert)
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
    apply_decision(db, alert)
    db.commit()
    db.refresh(alert)
    return alert
