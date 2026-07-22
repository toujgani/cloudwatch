from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Boolean, Text, ForeignKey, Enum
)
from sqlalchemy.orm import relationship
from .database import Base
import enum


class SeverityEnum(str, enum.Enum):
    info = "info"
    warning = "warning"
    critical = "critical"


class StatusEnum(str, enum.Enum):
    active = "active"
    acknowledged = "acknowledged"
    assigned = "assigned"
    resolved = "resolved"


class AuditActionEnum(str, enum.Enum):
    alert_created = "alert_created"
    alert_acknowledged = "alert_acknowledged"
    alert_assigned = "alert_assigned"
    alert_resolved = "alert_resolved"
    remediation_triggered = "remediation_triggered"
    remediation_applied = "remediation_applied"
    remediation_blocked = "remediation_blocked"
    ai_analysis = "ai_analysis"
    collector_error = "collector_error"
    login = "login"
    logout = "logout"
    settings_changed = "settings_changed"


# ─── VirtualMachine ───────────────────────────────────────────────────────────

class VirtualMachine(Base):
    __tablename__ = "virtual_machines"

    id          = Column(String, primary_key=True)   # OpenStack UUID
    name        = Column(String, nullable=False)
    status      = Column(String, nullable=False)      # ACTIVE / SHUTOFF / ERROR …
    flavor      = Column(String)
    host        = Column(String)
    tenant_id   = Column(String)
    created_at  = Column(DateTime, default=datetime.utcnow)
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    metrics     = relationship("VMMetric",   back_populates="vm",   cascade="all, delete")
    alerts      = relationship("Alert",      back_populates="vm")


class VMMetric(Base):
    __tablename__ = "vm_metrics"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    vm_id        = Column(String, ForeignKey("virtual_machines.id"), nullable=False)
    cpu_percent  = Column(Float)
    ram_percent  = Column(Float)
    ram_used_mb  = Column(Float)
    ram_total_mb = Column(Float)
    disk_read_mb = Column(Float)
    disk_write_mb= Column(Float)
    collected_at = Column(DateTime, default=datetime.utcnow, index=True)

    vm           = relationship("VirtualMachine", back_populates="metrics")


# ─── Pod (OpenShift) ──────────────────────────────────────────────────────────

class Pod(Base):
    __tablename__ = "pods"

    id           = Column(String, primary_key=True)   # namespace/name
    name         = Column(String, nullable=False)
    namespace    = Column(String, nullable=False)
    status       = Column(String, nullable=False)      # Running / Pending / Failed …
    node         = Column(String)
    restart_count= Column(Integer, default=0)
    image        = Column(String)
    created_at   = Column(DateTime, default=datetime.utcnow)
    updated_at   = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    metrics      = relationship("PodMetric", back_populates="pod", cascade="all, delete")
    alerts       = relationship("Alert",     back_populates="pod")


class PodMetric(Base):
    __tablename__ = "pod_metrics"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    pod_id       = Column(String, ForeignKey("pods.id"), nullable=False)
    cpu_millicores = Column(Float)
    ram_mb       = Column(Float)
    restart_count= Column(Integer, default=0)
    collected_at = Column(DateTime, default=datetime.utcnow, index=True)

    pod          = relationship("Pod", back_populates="metrics")


# ─── Alert ────────────────────────────────────────────────────────────────────

class Alert(Base):
    __tablename__ = "alerts"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    severity     = Column(Enum(SeverityEnum), nullable=False)
    status       = Column(Enum(StatusEnum), default=StatusEnum.active)
    title        = Column(String, nullable=False)
    description  = Column(Text)
    rule_name    = Column(String)               # which rule triggered this
    metric_value = Column(Float)                # the value that triggered
    threshold    = Column(Float)                # the threshold that was crossed
    acknowledged = Column(Boolean, default=False)
    acknowledged_by = Column(String, nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
    operator_note = Column(Text, nullable=True)
    ai_score = Column(Integer, nullable=True)
    ai_decision = Column(String, nullable=True)
    ai_category = Column(String, nullable=True)
    ai_reason = Column(Text, nullable=True)
    ai_recommendation = Column(Text, nullable=True)
    ai_confidence = Column(Float, nullable=True)
    ai_updated_at = Column(DateTime, nullable=True)
    remediation_action = Column(String, nullable=True)
    remediation_status = Column(String, nullable=True)
    remediation_message = Column(Text, nullable=True)
    remediation_updated_at = Column(DateTime, nullable=True)

    # Lifecycle
    assigned_to  = Column(String, nullable=True)
    assigned_at  = Column(DateTime, nullable=True)

    # Anomaly vector A = [m, l, t]  (metrics, logs, traces)
    anomaly_m    = Column(Float, nullable=True)   # metrics component  0-1
    anomaly_l    = Column(Float, nullable=True)   # logs component     0-1
    anomaly_t    = Column(Float, nullable=True)   # traces component   0-1
    anomaly_vector_norm = Column(Float, nullable=True)  # |A|

    vm_id        = Column(String, ForeignKey("virtual_machines.id"), nullable=True)
    pod_id       = Column(String, ForeignKey("pods.id"), nullable=True)

    triggered_at = Column(DateTime, default=datetime.utcnow, index=True)
    resolved_at  = Column(DateTime, nullable=True)

    vm           = relationship("VirtualMachine", back_populates="alerts")
    pod          = relationship("Pod",            back_populates="alerts")


# ─── AuditLog ─────────────────────────────────────────────────────────────────

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    action      = Column(Enum(AuditActionEnum), nullable=False, index=True)
    actor       = Column(String, nullable=False, default="system")   # who triggered it
    resource_type = Column(String, nullable=True)                    # "alert" | "vm" | "pod"
    resource_id = Column(String, nullable=True)                      # the affected resource id
    detail      = Column(Text, nullable=True)                        # human-readable detail
    extra       = Column(Text, nullable=True)                        # JSON blob for extra data
    created_at  = Column(DateTime, default=datetime.utcnow, index=True)


# ─── User ─────────────────────────────────────────────────────────────────────

class RoleEnum(str, enum.Enum):
    admin = "admin"
    subadmin = "subadmin"
    operator = "operator"
    viewer = "viewer"


class User(Base):
    __tablename__ = "users"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    username      = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    role          = Column(Enum(RoleEnum), nullable=False, default=RoleEnum.viewer)
    is_active     = Column(Boolean, default=True)
    created_at    = Column(DateTime, default=datetime.utcnow)

    sessions      = relationship("LoginSession", back_populates="user", cascade="all, delete")


class LoginSession(Base):
    __tablename__ = "login_sessions"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    user_id       = Column(Integer, ForeignKey("users.id"), nullable=False)
    ip_address    = Column(String, nullable=True)
    user_agent    = Column(String, nullable=True)
    login_at      = Column(DateTime, default=datetime.utcnow, index=True)
    last_activity = Column(DateTime, default=datetime.utcnow)
    is_active     = Column(Boolean, default=True)

    user          = relationship("User", back_populates="sessions")

