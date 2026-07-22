"""
Authentication Router — JWT-based server-side auth.
Users are stored in PostgreSQL with bcrypt-hashed passwords.
"""
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
    """Decode JWT and return User. Returns None if no token (allows unauthenticated access where needed)."""
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


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Authenticate user and return JWT token. Records login session."""
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nom d'utilisateur ou mot de passe incorrect.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Compte désactivé.")

    # Record login session
    ip = request.headers.get("x-forwarded-for", request.client.host if request.client else "unknown")
    user_agent = request.headers.get("user-agent", "unknown")
    session = LoginSession(
        user_id=user.id,
        ip_address=ip.split(",")[0].strip() if ip else "unknown",
        user_agent=user_agent[:500],
        is_active=True,
    )
    db.add(session)
    db.commit()

    token = create_access_token({"sub": user.username, "role": user.role.value})
    return TokenResponse(
        access_token=token,
        user={"name": user.username, "role": user.role.value, "baseRole": user.role.value},
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
