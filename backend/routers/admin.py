"""
Admin Console Router — user management, sessions, audit, AI execution history.
Restricted to admin role.
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from ..database import get_db
from ..models import User, RoleEnum, AuditLog, AuditActionEnum, Alert, LoginSession
from ..routers.auth import require_auth

router = APIRouter(prefix="/admin", tags=["Administration"])


def _require_admin(current_user: User = Depends(require_auth)) -> User:
    """Dependency: only admins can access admin endpoints."""
    if current_user.role != RoleEnum.admin:
        raise HTTPException(status_code=403, detail="Admin access required.")
    return current_user


@router.get("/users")
def list_users(admin: User = Depends(_require_admin), db: Session = Depends(get_db)):
    """List all registered users with their roles and status."""
    users = db.query(User).all()
    return [
        {
            "id": u.id,
            "username": u.username,
            "role": u.role.value,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        }
        for u in users
    ]


@router.patch("/users/{user_id}/role")
def change_user_role(user_id: int, role: str, admin: User = Depends(_require_admin), db: Session = Depends(get_db)):
    """Change a user's role. Cannot demote yourself."""
    if admin.id == user_id:
        raise HTTPException(status_code=400, detail="Impossible de modifier votre propre role.")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    if role not in ("admin", "operator", "viewer"):
        raise HTTPException(status_code=400, detail="Invalid role.")
    user.role = RoleEnum(role)
    db.commit()
    return {"status": "updated", "username": user.username, "new_role": role}


@router.patch("/users/{user_id}/disable")
def disable_user(user_id: int, admin: User = Depends(_require_admin), db: Session = Depends(get_db)):
    """Disable a user account. Cannot disable yourself."""
    if admin.id == user_id:
        raise HTTPException(status_code=400, detail="Impossible de desactiver votre propre compte.")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    user.is_active = False
    db.commit()
    return {"status": "disabled", "username": user.username}


@router.patch("/users/{user_id}/enable")
def enable_user(user_id: int, admin: User = Depends(_require_admin), db: Session = Depends(get_db)):
    """Re-enable a disabled user account."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    user.is_active = True
    db.commit()
    return {"status": "enabled", "username": user.username}


@router.get("/audit")
def admin_audit_log(
    limit: int = 100,
    action: str = None,
    admin: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    """Full audit log with filtering."""
    q = db.query(AuditLog).order_by(desc(AuditLog.created_at))
    if action:
        q = q.filter(AuditLog.action == action)
    entries = q.limit(limit).all()
    return [
        {
            "id": e.id,
            "action": e.action.value,
            "actor": e.actor,
            "resource_type": e.resource_type,
            "resource_id": e.resource_id,
            "detail": e.detail,
            "extra": e.extra,
            "created_at": e.created_at.isoformat() if e.created_at else None,
        }
        for e in entries
    ]


@router.get("/ai-history")
def ai_execution_history(
    limit: int = 50,
    admin: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    """AI remediation execution history."""
    alerts = (
        db.query(Alert)
        .filter(Alert.remediation_action.isnot(None))
        .order_by(desc(Alert.remediation_updated_at))
        .limit(limit)
        .all()
    )
    return [
        {
            "alert_id": a.id,
            "title": a.title,
            "severity": a.severity.value,
            "ai_score": a.ai_score,
            "ai_decision": a.ai_decision,
            "ai_confidence": a.ai_confidence,
            "remediation_action": a.remediation_action,
            "remediation_status": a.remediation_status,
            "remediation_message": a.remediation_message[:200] if a.remediation_message else None,
            "executed_at": a.remediation_updated_at.isoformat() if a.remediation_updated_at else None,
        }
        for a in alerts
    ]


@router.get("/stats")
def admin_stats(admin: User = Depends(_require_admin), db: Session = Depends(get_db)):
    """Platform-wide statistics for the admin dashboard."""
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active == True).count()
    total_alerts = db.query(Alert).count()
    total_remediations = db.query(Alert).filter(Alert.remediation_status == "applied").count()
    total_audit_entries = db.query(AuditLog).count()

    # AI stats
    ai_actions_24h = db.query(AuditLog).filter(
        AuditLog.action.in_([AuditActionEnum.remediation_applied, AuditActionEnum.remediation_blocked]),
        AuditLog.created_at >= datetime.utcnow().replace(hour=0, minute=0, second=0),
    ).count()

    return {
        "users": {"total": total_users, "active": active_users},
        "alerts": {"total": total_alerts, "remediations_applied": total_remediations},
        "audit": {"total_entries": total_audit_entries},
        "ai": {"actions_today": ai_actions_24h},
    }


@router.get("/sessions")
def list_sessions(
    limit: int = 50,
    admin: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    """List all login sessions with IP, user agent, and timestamps."""
    sessions = (
        db.query(LoginSession)
        .order_by(desc(LoginSession.login_at))
        .limit(limit)
        .all()
    )
    result = []
    for s in sessions:
        user = db.get(User, s.user_id)
        result.append({
            "id": s.id,
            "username": user.username if user else "unknown",
            "role": user.role.value if user else "unknown",
            "ip_address": s.ip_address,
            "user_agent": s.user_agent,
            "login_at": s.login_at.isoformat() if s.login_at else None,
            "last_activity": s.last_activity.isoformat() if s.last_activity else None,
            "is_active": s.is_active,
        })
    return result


@router.delete("/sessions/{session_id}")
def terminate_session(session_id: int, admin: User = Depends(_require_admin), db: Session = Depends(get_db)):
    """Terminate a specific login session."""
    session = db.get(LoginSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")
    session.is_active = False
    db.commit()
    return {"status": "terminated", "session_id": session_id}
