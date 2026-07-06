"""
Audit Trail — Architecture D requirement.
All significant platform actions are logged here: alert lifecycle,
remediation, AI decisions, authentication, and settings changes.
"""
from __future__ import annotations

import json
from datetime import datetime
from sqlalchemy.orm import Session

from .models import AuditLog, AuditActionEnum


def log(
    db: Session,
    action: AuditActionEnum,
    actor: str = "system",
    resource_type: str | None = None,
    resource_id: str | None = None,
    detail: str | None = None,
    extra: dict | None = None,
    commit: bool = False,
) -> AuditLog:
    """
    Write an audit entry. Does NOT commit by default — caller is responsible
    for committing the surrounding DB transaction so the audit entry is
    always atomic with the business operation.

    Set commit=True only when you want an isolated, standalone audit entry.
    """
    entry = AuditLog(
        action=action,
        actor=actor,
        resource_type=resource_type,
        resource_id=str(resource_id) if resource_id is not None else None,
        detail=detail,
        extra=json.dumps(extra, default=str) if extra else None,
        created_at=datetime.utcnow(),
    )
    db.add(entry)
    if commit:
        db.commit()
        db.refresh(entry)
    return entry
