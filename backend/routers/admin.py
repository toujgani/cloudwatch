"""
Admin Console Router — Full administration panel.
User management, RBAC, password management, branding, sessions, AI history.
Restricted to admin/subadmin roles with RBAC enforcement.
"""
import secrets
import string
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from ..database import get_db
from ..models import (
    User, RoleEnum, AuditLog, AuditActionEnum, Alert,
    LoginSession, BrandingConfig
)
from ..routers.auth import require_auth, hash_password
from .. import audit as audit_trail
from ..runtime_detection import runtime_info_dict

router = APIRouter(prefix="/admin", tags=["Administration"])

# Persistent storage for branding assets
BRANDING_DIR = Path(os.getenv("BRANDING_STORAGE_PATH", "/app/branding"))
BRANDING_DIR.mkdir(parents=True, exist_ok=True)


# ─── RBAC Dependencies ────────────────────────────────────────────────────────

def _require_admin(current_user: User = Depends(require_auth)) -> User:
    """Only admin can access full admin endpoints."""
    if current_user.role != RoleEnum.admin:
        raise HTTPException(status_code=403, detail="Administrator access required.")
    return current_user


def _require_admin_or_subadmin(current_user: User = Depends(require_auth)) -> User:
    """Admin and subadmin can access most admin endpoints (except user management)."""
    if current_user.role not in (RoleEnum.admin, RoleEnum.subadmin):
        raise HTTPException(status_code=403, detail="Admin or Sub-Admin access required.")
    return current_user


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


# ─── Runtime Detection ────────────────────────────────────────────────────────

@router.get("/runtime")
def get_runtime_info(admin: User = Depends(_require_admin_or_subadmin)):
    """Get current runtime environment detection info."""
    return runtime_info_dict()


# ─── User Management ─────────────────────────────────────────────────────────

@router.get("/users")
def list_users(admin: User = Depends(_require_admin_or_subadmin), db: Session = Depends(get_db)):
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
    admin: User = Depends(_require_admin_or_subadmin),
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


# ─── AI History ───────────────────────────────────────────────────────────────

@router.get("/ai-history")
def ai_execution_history(
    limit: int = 50,
    admin: User = Depends(_require_admin_or_subadmin),
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


# ─── Platform Stats ──────────────────────────────────────────────────────────

@router.get("/stats")
def admin_stats(admin: User = Depends(_require_admin_or_subadmin), db: Session = Depends(get_db)):
    """Platform-wide statistics for the admin dashboard."""
    total_users = db.query(User).count()
    active_users = db.query(User).filter(User.is_active == True).count()
    locked_users = db.query(User).filter(User.is_locked == True).count()
    total_alerts = db.query(Alert).count()
    total_remediations = db.query(Alert).filter(Alert.remediation_status == "applied").count()
    total_audit_entries = db.query(AuditLog).count()

    # Role distribution
    role_dist = {}
    for role in RoleEnum:
        role_dist[role.value] = db.query(User).filter(User.role == role).count()

    # AI stats
    ai_actions_24h = db.query(AuditLog).filter(
        AuditLog.action.in_([AuditActionEnum.remediation_applied, AuditActionEnum.remediation_blocked]),
        AuditLog.created_at >= datetime.utcnow().replace(hour=0, minute=0, second=0),
    ).count()

    # Active sessions
    active_sessions = db.query(LoginSession).filter(LoginSession.is_active == True).count()

    return {
        "users": {
            "total": total_users,
            "active": active_users,
            "locked": locked_users,
            "roles": role_dist,
        },
        "alerts": {"total": total_alerts, "remediations_applied": total_remediations},
        "audit": {"total_entries": total_audit_entries},
        "ai": {"actions_today": ai_actions_24h},
        "sessions": {"active": active_sessions},
        "runtime": runtime_info_dict(),
    }


# ─── Branding ─────────────────────────────────────────────────────────────────

@router.get("/branding")
def get_branding(db: Session = Depends(get_db)):
    """Get current branding configuration (public endpoint)."""
    config = db.query(BrandingConfig).first()
    if not config:
        return {
            "company_name": "CIRES Technologies",
            "app_name": "Cloud AI Monitor",
            "logo_url": None,
            "app_logo_url": None,
            "favicon_url": None,
            "background_url": None,
        }
    return {
        "company_name": config.company_name,
        "app_name": config.app_name,
        "logo_url": f"/api/admin/branding/files/{config.logo_path}" if config.logo_path else None,
        "app_logo_url": f"/api/admin/branding/files/{config.app_logo_path}" if config.app_logo_path else None,
        "favicon_url": f"/api/admin/branding/files/{config.favicon_path}" if config.favicon_path else None,
        "background_url": f"/api/admin/branding/files/{config.background_path}" if config.background_path else None,
    }


@router.put("/branding")
def update_branding_text(
    company_name: str = "CIRES Technologies",
    app_name: str = "Cloud AI Monitor",
    admin: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    """Update branding text fields."""
    config = db.query(BrandingConfig).first()
    if not config:
        config = BrandingConfig()
        db.add(config)
    config.company_name = company_name
    config.app_name = app_name
    config.updated_at = datetime.utcnow()
    db.commit()
    return {"status": "updated", "company_name": company_name, "app_name": app_name}


@router.post("/branding/upload/{asset_type}")
async def upload_branding_asset(
    asset_type: str,
    file: UploadFile = File(...),
    admin: User = Depends(_require_admin),
    db: Session = Depends(get_db),
):
    """Upload a branding asset (logo, app_logo, favicon, background)."""
    valid_types = ["logo", "app_logo", "favicon", "background"]
    if asset_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"Invalid asset type. Options: {valid_types}")

    # Validate file type
    allowed_extensions = {".png", ".jpg", ".jpeg", ".svg", ".ico", ".webp"}
    ext = Path(file.filename).suffix.lower() if file.filename else ""
    if ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail=f"Invalid file type. Allowed: {allowed_extensions}")

    # Save file
    filename = f"{asset_type}{ext}"
    filepath = BRANDING_DIR / filename
    content = await file.read()
    filepath.write_bytes(content)

    # Update database
    config = db.query(BrandingConfig).first()
    if not config:
        config = BrandingConfig()
        db.add(config)

    if asset_type == "logo":
        config.logo_path = filename
    elif asset_type == "app_logo":
        config.app_logo_path = filename
    elif asset_type == "favicon":
        config.favicon_path = filename
    elif asset_type == "background":
        config.background_path = filename

    config.updated_at = datetime.utcnow()
    db.commit()

    return {"status": "uploaded", "asset_type": asset_type, "filename": filename}


@router.get("/branding/files/{filename}")
def serve_branding_file(filename: str):
    """Serve a branding asset file."""
    from fastapi.responses import FileResponse
    filepath = BRANDING_DIR / filename
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="File not found.")
    return FileResponse(str(filepath))


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
