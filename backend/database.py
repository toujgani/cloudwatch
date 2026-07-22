import logging
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .config import settings

logger = logging.getLogger(__name__)

# Production-grade connection pool settings
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    pool_recycle=1800,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """FastAPI dependency — yields a DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Create all tables on startup and run migrations."""
    from . import models  # noqa: F401 — ensure models are registered
    Base.metadata.create_all(bind=engine)
    _run_migrations()


def _run_migrations():
    """Add columns for databases created before this version."""
    inspector = inspect(engine)
    table_names = inspector.get_table_names()

    # ── Alert table migrations ────────────────────────────────────────────────
    if "alerts" in table_names:
        existing = {col["name"] for col in inspector.get_columns("alerts")}
        alert_columns = {
            "acknowledged": "BOOLEAN DEFAULT false",
            "acknowledged_by": "VARCHAR",
            "acknowledged_at": "TIMESTAMP",
            "operator_note": "TEXT",
            "ai_score": "INTEGER",
            "ai_decision": "VARCHAR",
            "ai_category": "VARCHAR",
            "ai_reason": "TEXT",
            "ai_recommendation": "TEXT",
            "ai_confidence": "FLOAT",
            "ai_updated_at": "TIMESTAMP",
            "remediation_action": "VARCHAR",
            "remediation_status": "VARCHAR",
            "remediation_message": "TEXT",
            "remediation_updated_at": "TIMESTAMP",
            "assigned_to": "VARCHAR",
            "assigned_at": "TIMESTAMP",
            "anomaly_m": "FLOAT",
            "anomaly_l": "FLOAT",
            "anomaly_t": "FLOAT",
            "anomaly_vector_norm": "FLOAT",
        }
        with engine.begin() as conn:
            for name, definition in alert_columns.items():
                if name not in existing:
                    try:
                        conn.execute(text(f"ALTER TABLE alerts ADD COLUMN {name} {definition}"))
                    except Exception:
                        pass  # Column might already exist

    # ── User table migrations ─────────────────────────────────────────────────
    if "users" in table_names:
        existing = {col["name"] for col in inspector.get_columns("users")}
        user_columns = {
            "is_locked": "BOOLEAN DEFAULT false",
            "force_password_change": "BOOLEAN DEFAULT false",
            "failed_login_count": "INTEGER DEFAULT 0",
            "last_login_at": "TIMESTAMP",
            "last_activity_at": "TIMESTAMP",
        }
        with engine.begin() as conn:
            for name, definition in user_columns.items():
                if name not in existing:
                    try:
                        conn.execute(text(f"ALTER TABLE users ADD COLUMN {name} {definition}"))
                    except Exception:
                        pass

    # ── Login sessions migrations ─────────────────────────────────────────────
    if "login_sessions" in table_names:
        existing = {col["name"] for col in inspector.get_columns("login_sessions")}
        session_columns = {
            "browser": "VARCHAR",
            "os": "VARCHAR",
        }
        with engine.begin() as conn:
            for name, definition in session_columns.items():
                if name not in existing:
                    try:
                        conn.execute(text(f"ALTER TABLE login_sessions ADD COLUMN {name} {definition}"))
                    except Exception:
                        pass

    logger.info("[DB] Migrations completed.")
