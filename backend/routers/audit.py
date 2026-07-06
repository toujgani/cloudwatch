"""
Audit Log router — exposes the audit trail for the frontend.
"""
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc
from pydantic import BaseModel
from ..database import get_db
from ..models import AuditLog, AuditActionEnum

router = APIRouter(prefix="/audit", tags=["Audit Trail"])


class AuditLogOut(BaseModel):
    id: int
    action: AuditActionEnum
    actor: str
    resource_type: Optional[str]
    resource_id: Optional[str]
    detail: Optional[str]
    extra: Optional[str]
    created_at: datetime

    model_config = {"from_attributes": True}


@router.get("/", response_model=list[AuditLogOut])
def list_audit_logs(
    action: Optional[AuditActionEnum] = Query(default=None),
    actor: Optional[str] = Query(default=None),
    resource_type: Optional[str] = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    """List audit log entries, newest first. Filterable by action, actor, resource_type."""
    q = db.query(AuditLog)
    if action:
        q = q.filter(AuditLog.action == action)
    if actor:
        q = q.filter(AuditLog.actor.ilike(f"%{actor}%"))
    if resource_type:
        q = q.filter(AuditLog.resource_type == resource_type)
    return q.order_by(desc(AuditLog.created_at)).limit(limit).all()


@router.get("/stats")
def audit_stats(db: Session = Depends(get_db)):
    """Aggregate counts per action type."""
    from sqlalchemy import func
    rows = (
        db.query(AuditLog.action, func.count(AuditLog.id).label("count"))
        .group_by(AuditLog.action)
        .all()
    )
    return {row.action.value: row.count for row in rows}
