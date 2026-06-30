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
    resolved = "resolved"


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

    vm_id        = Column(String, ForeignKey("virtual_machines.id"), nullable=True)
    pod_id       = Column(String, ForeignKey("pods.id"), nullable=True)

    triggered_at = Column(DateTime, default=datetime.utcnow, index=True)
    resolved_at  = Column(DateTime, nullable=True)

    vm           = relationship("VirtualMachine", back_populates="alerts")
    pod          = relationship("Pod",            back_populates="alerts")
