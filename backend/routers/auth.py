"""
Authentication Router — JWT-based server-side auth with RBAC enforcement.
Users are stored in PostgreSQL with bcrypt-hashed passwords.
Supports: login tracking, account locking, user agent parsing.
"""
import re
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..models import User, RoleEnum, LoginSession

router = APIRouter(prefix="/auth", tags=["Authentication"])

# ── Security setup ────────────────────────────────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

ALGORITHM = "HS256"
MAX_FAILED_LOGINS = 5


# ── Schemas ───────────────────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str


# ── Helpers ───────────────────────────────────────────────────────────────────

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User | None:
    """Decode JWT and return User. Returns None if no token."""
    if not token:
        return None
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
    except JWTError:
        return None
    user = db.query(User).filter(User.username == username).first()
    if user and not user.is_active:
        return None
    return user


def require_auth(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    """Strict auth dependency — raises 401 if not authenticated."""
    user = get_current_user(token, db)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def require_role(*roles: RoleEnum):
    """Factory for role-based access control dependency."""
    def dependency(current_user: User = Depends(require_auth)) -> User:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {[r.value for r in roles]}",
            )
        return current_user
    return dependency


def _parse_user_agent(ua: str) -> tuple[str, str]:
    """Parse user agent string to extract browser and OS."""
    browser = "Unknown"
    os_name = "Unknown"

    # Browser detection
    if "Firefox/" in ua:
        browser = "Firefox"
    elif "Edg/" in ua:
        browser = "Edge"
    elif "Chrome/" in ua:
        browser = "Chrome"
    elif "Safari/" in ua:
        browser = "Safari"
    elif "Opera" in ua or "OPR/" in ua:
        browser = "Opera"

    # OS detection
    if "Windows NT 10" in ua:
        os_name = "Windows 10/11"
    elif "Windows NT" in ua:
        os_name = "Windows"
    elif "Mac OS X" in ua:
        os_name = "macOS"
    elif "Linux" in ua:
        os_name = "Linux"
    elif "Android" in ua:
        os_name = "Android"
    elif "iPhone" in ua or "iPad" in ua:
        os_name = "iOS"

    return browser, os_name


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Authenticate user and return JWT token. Records login session."""
    user = db.query(User).filter(User.username == form_data.username).first()

    # Check if user exists
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nom d'utilisateur ou mot de passe incorrect.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Check if account is locked
    if user.is_locked:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Compte verrouillé. Contactez l'administrateur.",
        )

    # Check if account is disabled
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Compte désactivé.",
        )

    # Verify password
    if not verify_password(form_data.password, user.password_hash):
        # Increment failed login count
        user.failed_login_count = (user.failed_login_count or 0) + 1
        if user.failed_login_count >= MAX_FAILED_LOGINS:
            user.is_locked = True
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nom d'utilisateur ou mot de passe incorrect.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Reset failed login count on successful login
    user.failed_login_count = 0
    user.last_login_at = datetime.utcnow()
    user.last_activity_at = datetime.utcnow()

    # Record login session
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "unknown")
    user_agent = request.headers.get("user-agent", "unknown")
    browser, os_name = _parse_user_agent(user_agent)

    session = LoginSession(
        user_id=user.id,
        ip_address=ip.split(",")[0].strip() if ip else "unknown",
        user_agent=user_agent[:500],
        browser=browser,
        os=os_name,
        is_active=True,
    )
    db.add(session)
    db.commit()

    token = create_access_token({"sub": user.username, "role": user.role.value})
    return TokenResponse(
        access_token=token,
        user={
            "name": user.username,
            "role": user.role.value,
            "baseRole": user.role.value,
            "force_password_change": user.force_password_change,
        },
    )


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(require_auth)):
    """Return current authenticated user info."""
    return UserOut(
        id=current_user.id,
        username=current_user.username,
        role=current_user.role.value,
        is_active=current_user.is_active,
    )


@router.post("/change-password")
def change_own_password(
    payload: ChangePasswordIn,
    current_user: User = Depends(require_auth),
    db: Session = Depends(get_db),
):
    """Allow user to change their own password."""
    if not verify_password(payload.current_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")
    if len(payload.new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters.")

    current_user.password_hash = hash_password(payload.new_password)
    current_user.force_password_change = False
    db.commit()
    return {"status": "password_changed"}
