"""
Admin Console Router — User management, sessions.
Restricted to admin role with RBAC enforcement.
"""
import secrets
import string
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import desc

from ..database import get_db
from ..models import (
    User, RoleEnum, AuditActionEnum,
    LoginSession,
)
from ..routers.auth import require_auth, hash_password
from .. import audit as audit_trail

router = APIRouter(prefix="/admin", tags=["Administration"])


# ─── RBAC Dependencies ────────────────────────────────────────────────────────

def _require_admin(current_user: User = Depends(require_auth)) -> User:
    """Only admin can access full admin endpoints."""
    if current_user.role != RoleEnum.admin:
        raise HTTPException(status_code=403, detail="Administrator access required.")
    return current_user


# ─── Schemas ──────────────────────────────────────────────────────────────────
# ─── Schemas ──────────────────────────────────────────────────────────────────

class CreateUserIn(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: Optional[str] = None  # If None, generates random
    role: str = "viewer"
    send_email: bool = False


class ChangePasswordIn(BaseModel):
    new_password: Optional[str] = None  # If None, generates random
    force_change: bool = True


class ChangeRoleIn(BaseModel):
    role: str


# ─── User Management ─────────────────────────────────────────────────────────

@router.get("/users")
def list_users(admin: User = Depends(_require_admin), db: Session = Depends(get_db)):
    """List all registered users with full details."""
    users = db.query(User).order_by(User.created_at).all()
    result = []
    for u in users:
        # Get last session info
        last_session = (
            db.query(LoginSession)
            .filter(LoginSession.user_id == u.id)
            .order_by(desc(LoginSession.login_at))
            .first()
        )
        # Get active session count
        active_sessions = (
            db.query(LoginSession)
            .filter(LoginSession.user_id == u.id, LoginSession.is_active == True)
            .count()
        )
        result.append({
            "id": u.id,
            "username": u.username,
            "role": u.role.value,
            "is_active": u.is_active,
            "is_locked": u.is_locked,
            "force_password_change": u.force_password_change,
            "failed_login_count": u.failed_login_count,
            "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
            "last_activity_at": u.last_activity_at.isoformat() if u.last_activity_at else None,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "active_sessions": active_sessions,
            "last_ip": last_session.ip_address if last_session else None,
            "last_browser": last_session.browser if last_session else None,
            "last_os": last_session.os if last_session else None,
        })
    return result


@router.post("/users")
def create_user(payload: CreateUserIn, admin: User = Depends(_require_admin), db: Session = Depends(get_db)):
    """Create a new user account. Only admin can create users (not subadmin)."""
    # Validate role
    valid_roles = ["viewer", "operator", "subadmin"]
    if payload.role not in valid_roles:
        raise HTTPException(status_code=400, detail=f"Invalid role. Options: {valid_roles}")

    # Check uniqueness
    existing = db.query(User).filter(User.username == payload.username).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Username '{payload.username}' already exists.")

    # Generate password if not provided
    password = payload.password
    if not password:
        password = _generate_random_password()

    user = User(
        username=payload.username,
        password_hash=hash_password(password),
        role=RoleEnum(payload.role),
        is_active=True,
        force_password_change=True,
    )
    db.add(user)
    db.flush()

    audit_trail.log(
        db,
        action=AuditActionEnum.user_created,
        actor=admin.username,
        resource_type="user",
        resource_id=str(user.id),
        detail=f"Created user '{payload.username}' with role '{payload.role}'",
    )
    db.commit()

    return {
        "status": "created",
        "user_id": user.id,
        "username": user.username,
        "role": payload.role,
        "temporary_password": password,
        "force_password_change": True,
        "login_url": "/",
    }


@router.delete("/users/{user_id}")
def delete_user(user_id: int, admin: User = Depends(_require_admin), db: Session = Depends(get_db)):
    """Delete a user account permanently. Cannot delete self or admin."""
    if admin.id == user_id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account.")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    if user.role == RoleEnum.admin:
        raise HTTPException(status_code=400, detail="Cannot delete the primary admin account.")

    username = user.username
    # Delete sessions first
    db.query(LoginSession).filter(LoginSession.user_id == user_id).delete()
    db.delete(user)

    audit_trail.log(
        db,
        action=AuditActionEnum.user_deleted,
        actor=admin.username,
        resource_type="user",
        resource_id=str(user_id),
        detail=f"Deleted user '{username}'",
    )
    db.commit()
    return {"status": "deleted", "username": username}


@router.patch("/users/{user_id}/disable")
def disable_user(user_id: int, admin: User = Depends(_require_admin), db: Session = Depends(get_db)):
    """Disable a user account."""
    if admin.id == user_id:
        raise HTTPException(status_code=400, detail="Cannot disable your own account.")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    if user.role == RoleEnum.admin:
        raise HTTPException(status_code=400, detail="Cannot disable the primary admin account.")

    user.is_active = False
    # Terminate all active sessions
    db.query(LoginSession).filter(
        LoginSession.user_id == user_id, LoginSession.is_active == True
    ).update({"is_active": False})

    audit_trail.log(
        db,
        action=AuditActionEnum.user_disabled,
        actor=admin.username,
        resource_type="user",
        resource_id=str(user_id),
        detail=f"Disabled user '{user.username}'",
    )
    db.commit()
    return {"status": "disabled", "username": user.username}


@router.patch("/users/{user_id}/enable")
def enable_user(user_id: int, admin: User = Depends(_require_admin), db: Session = Depends(get_db)):
    """Re-enable a disabled user account."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    user.is_active = True
    user.is_locked = False
    user.failed_login_count = 0

    audit_trail.log(
        db,
        action=AuditActionEnum.user_enabled,
        actor=admin.username,
        resource_type="user",
        resource_id=str(user_id),
        detail=f"Enabled user '{user.username}'",
    )
    db.commit()
    return {"status": "enabled", "username": user.username}


@router.patch("/users/{user_id}/unlock")
def unlock_user(user_id: int, admin: User = Depends(_require_admin), db: Session = Depends(get_db)):
    """Unlock a locked user account (reset failed login count)."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    user.is_locked = False
    user.failed_login_count = 0
    db.commit()
    return {"status": "unlocked", "username": user.username}


@router.patch("/users/{user_id}/role")
def change_user_role(user_id: int, payload: ChangeRoleIn, admin: User = Depends(_require_admin), db: Session = Depends(get_db)):
    """Change a user's role. Only admin can do this."""
    if admin.id == user_id:
        raise HTTPException(status_code=400, detail="Cannot change your own role.")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    if user.role == RoleEnum.admin:
        raise HTTPException(status_code=400, detail="Cannot change the primary admin role.")
    if payload.role == "admin":
        raise HTTPException(status_code=400, detail="Only one admin account is allowed.")
    if payload.role not in ("subadmin", "operator", "viewer"):
        raise HTTPException(status_code=400, detail="Invalid role. Options: subadmin, operator, viewer.")

    old_role = user.role.value
    user.role = RoleEnum(payload.role)

    audit_trail.log(
        db,
        action=AuditActionEnum.role_changed,
        actor=admin.username,
        resource_type="user",
        resource_id=str(user_id),
        detail=f"Changed role of '{user.username}': {old_role} -> {payload.role}",
    )
    db.commit()
    return {"status": "updated", "username": user.username, "old_role": old_role, "new_role": payload.role}


# ─── Password Management ─────────────────────────────────────────────────────

@router.patch("/users/{user_id}/password")
def change_user_password(
    user_id: int,
    payload: ChangePasswordIn,
    admin: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    """Change any user's password. Generates random if not provided."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    new_password = payload.new_password or _generate_random_password()
    user.password_hash = hash_password(new_password)
    user.force_password_change = payload.force_change
    user.is_locked = False
    user.failed_login_count = 0

    audit_trail.log(
        db,
        action=AuditActionEnum.password_changed,
        actor=admin.username,
        resource_type="user",
        resource_id=str(user_id),
        detail=f"Password changed for '{user.username}' (force_change={payload.force_change})",
    )
    db.commit()

    return {
        "status": "password_changed",
        "username": user.username,
        "temporary_password": new_password,
        "force_change_on_login": payload.force_change,
        "login_url": "/",
    }


@router.post("/users/{user_id}/force-password-change")
def force_password_change(user_id: int, admin: User = Depends(_require_admin), db: Session = Depends(get_db)):
    """Force a user to change their password on next login."""
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")
    user.force_password_change = True
    db.commit()
    return {"status": "forced", "username": user.username}


# ─── Session Management ──────────────────────────────────────────────────────

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
            "browser": s.browser,
            "os": s.os,
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


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _generate_random_password(length: int = 16) -> str:
    """Generate a secure random password."""
    chars = string.ascii_letters + string.digits + "!@#$%&*"
    # Ensure at least one of each type
    password = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice("!@#$%&*"),
    ]
    password += [secrets.choice(chars) for _ in range(length - 4)]
    # Shuffle
    import random
    random.shuffle(password)
    return "".join(password)
