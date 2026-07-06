"""
Alert Engine — rule-based evaluation with AI enrichment and audit trail.
"""
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from .models import Alert, VirtualMachine, Pod, SeverityEnum, StatusEnum, AuditActionEnum
from .config import settings
from .email_notifications import send_alert_email
from .ai_agent import apply_decision
from .remediation_agent import auto_remediate_if_needed
from . import audit

logger = logging.getLogger(__name__)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _find_active(db: Session, rule_name: str, vm_id: str = None, pod_id: str = None) -> Alert | None:
    q = db.query(Alert).filter(
        Alert.rule_name == rule_name,
        Alert.status.in_([StatusEnum.active, StatusEnum.acknowledged, StatusEnum.assigned]),
    )
    if vm_id:
        q = q.filter(Alert.vm_id == vm_id)
    if pod_id:
        q = q.filter(Alert.pod_id == pod_id)
    return q.first()


def _create_alert(db: Session, *, severity: SeverityEnum, title: str, description: str,
                  rule_name: str, metric_value: float, threshold: float,
                  vm_id: str = None, pod_id: str = None):
    existing = _find_active(db, rule_name, vm_id=vm_id, pod_id=pod_id)
    if existing:
        return

    alert = Alert(
        severity=severity, status=StatusEnum.active,
        title=title, description=description,
        rule_name=rule_name, metric_value=metric_value, threshold=threshold,
        vm_id=vm_id, pod_id=pod_id,
        triggered_at=datetime.utcnow(),
    )
    apply_decision(db, alert)
    auto_remediate_if_needed(db, alert)
    db.add(alert)

    # Flush to get the id before writing the audit entry
    db.flush()
    audit.log(
        db,
        action=AuditActionEnum.alert_created,
        actor="alert-engine",
        resource_type="alert",
        resource_id=str(alert.id),
        detail=f"{severity.value.upper()}: {title}",
        extra={"rule": rule_name, "metric_value": metric_value, "threshold": threshold,
               "vm_id": vm_id, "pod_id": pod_id},
    )

    logger.warning("[ALERT] %s — %s", severity.value.upper(), title)
    send_alert_email(alert)


def _resolve_alert(db: Session, rule_name: str, vm_id: str = None, pod_id: str = None):
    alert = _find_active(db, rule_name, vm_id=vm_id, pod_id=pod_id)
    if alert:
        alert.status = StatusEnum.resolved
        alert.resolved_at = datetime.utcnow()
        apply_decision(db, alert)
        audit.log(
            db,
            action=AuditActionEnum.alert_resolved,
            actor="alert-engine",
            resource_type="alert",
            resource_id=str(alert.id),
            detail=f"Auto-resolved: {rule_name}",
        )
        logger.info("[RESOLVED] %s", rule_name)


# ─── VM evaluation ────────────────────────────────────────────────────────────

def evaluate_vm(db: Session, vm: VirtualMachine, cpu: float | None, ram: float | None):

    rule = "vm.cpu.critical"
    if cpu is not None and cpu >= settings.ALERT_CPU_CRITICAL:
        _create_alert(db,
            severity=SeverityEnum.critical,
            title=f"CPU critique — {vm.name}",
            description=f"CPU à {cpu:.1f}% sur la VM '{vm.name}' (seuil: {settings.ALERT_CPU_CRITICAL}%)",
            rule_name=rule, metric_value=cpu, threshold=settings.ALERT_CPU_CRITICAL,
            vm_id=vm.id,
        )
    else:
        _resolve_alert(db, rule, vm_id=vm.id)

    rule = "vm.cpu.warning"
    if cpu is not None and settings.ALERT_CPU_WARNING <= cpu < settings.ALERT_CPU_CRITICAL:
        _create_alert(db,
            severity=SeverityEnum.warning,
            title=f"CPU élevé — {vm.name}",
            description=f"CPU à {cpu:.1f}% sur '{vm.name}' (seuil warning: {settings.ALERT_CPU_WARNING}%)",
            rule_name=rule, metric_value=cpu, threshold=settings.ALERT_CPU_WARNING,
            vm_id=vm.id,
        )
    else:
        _resolve_alert(db, rule, vm_id=vm.id)

    rule = "vm.ram.critical"
    if ram is not None and ram >= settings.ALERT_RAM_CRITICAL:
        _create_alert(db,
            severity=SeverityEnum.critical,
            title=f"RAM critique — {vm.name}",
            description=f"RAM à {ram:.1f}% sur '{vm.name}' (seuil: {settings.ALERT_RAM_CRITICAL}%)",
            rule_name=rule, metric_value=ram, threshold=settings.ALERT_RAM_CRITICAL,
            vm_id=vm.id,
        )
    else:
        _resolve_alert(db, rule, vm_id=vm.id)

    rule = "vm.ram.warning"
    if ram is not None and settings.ALERT_RAM_WARNING <= ram < settings.ALERT_RAM_CRITICAL:
        _create_alert(db,
            severity=SeverityEnum.warning,
            title=f"RAM élevée — {vm.name}",
            description=f"RAM à {ram:.1f}% sur '{vm.name}' (seuil warning: {settings.ALERT_RAM_WARNING}%)",
            rule_name=rule, metric_value=ram, threshold=settings.ALERT_RAM_WARNING,
            vm_id=vm.id,
        )
    else:
        _resolve_alert(db, rule, vm_id=vm.id)

    rule = "vm.status.error"
    if vm.status == "ERROR":
        _create_alert(db,
            severity=SeverityEnum.critical,
            title=f"VM en erreur — {vm.name}",
            description=f"La VM '{vm.name}' est en statut ERROR dans OpenStack.",
            rule_name=rule, metric_value=0, threshold=0,
            vm_id=vm.id,
        )
    else:
        _resolve_alert(db, rule, vm_id=vm.id)


# ─── Pod evaluation ───────────────────────────────────────────────────────────

def evaluate_pod(db: Session, pod: Pod, restart_count: int):

    rule = "pod.status.failed"
    if pod.status in ("Failed", "Unknown"):
        _create_alert(db,
            severity=SeverityEnum.critical,
            title=f"Pod en erreur — {pod.namespace}/{pod.name}",
            description=f"Le pod '{pod.name}' (ns: {pod.namespace}) est en statut {pod.status}.",
            rule_name=rule, metric_value=0, threshold=0,
            pod_id=pod.id,
        )
    else:
        _resolve_alert(db, rule, pod_id=pod.id)

    rule = "pod.restarts.high"
    if restart_count >= 5:
        _create_alert(db,
            severity=SeverityEnum.warning,
            title=f"Redémarrages répétés — {pod.name}",
            description=f"Le pod '{pod.name}' a redémarré {restart_count} fois. Possible CrashLoopBackOff.",
            rule_name=rule, metric_value=restart_count, threshold=5,
            pod_id=pod.id,
        )
    else:
        _resolve_alert(db, rule, pod_id=pod.id)
