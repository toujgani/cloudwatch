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
    pool_recycle=1800,  # Recycle connections every 30 minutes
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
    """Create all tables on startup."""
    from . import models  # noqa: F401 — ensure models are registered
    Base.metadata.create_all(bind=engine)
    _ensure_alert_operation_columns()


def _ensure_alert_operation_columns():
    """Add operational alert columns for databases created before this feature."""
    inspector = inspect(engine)
    if "alerts" not in inspector.get_table_names():
        return

    existing = {col["name"] for col in inspector.get_columns("alerts")}
    columns = {
        "acknowledged": "BOOLEAN DEFAULT 0",
        "acknowledged_by": "VARCHAR",
        "acknowledged_at": "DATETIME",
        "operator_note": "TEXT",
        "ai_score": "INTEGER",
        "ai_decision": "VARCHAR",
        "ai_category": "VARCHAR",
        "ai_reason": "TEXT",
        "ai_recommendation": "TEXT",
        "ai_confidence": "FLOAT",
        "ai_updated_at": "DATETIME",
        "remediation_action": "VARCHAR",
        "remediation_status": "VARCHAR",
        "remediation_message": "TEXT",
        "remediation_updated_at": "DATETIME",
        # Architecture D additions
        "assigned_to": "VARCHAR",
        "assigned_at": "DATETIME",
        "anomaly_m": "FLOAT",
        "anomaly_l": "FLOAT",
        "anomaly_t": "FLOAT",
        "anomaly_vector_norm": "FLOAT",
    }

    with engine.begin() as conn:
        for name, definition in columns.items():
            if name not in existing:
                conn.execute(text(f"ALTER TABLE alerts ADD COLUMN {name} {definition}"))
