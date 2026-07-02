"""
Agent de remediation rapide.

Par defaut, il fonctionne en dry-run: il choisit l'action et journalise ce qui
serait fait. Les actions reelles doivent etre activees explicitement dans .env.
"""
from dataclasses import dataclass
from datetime import datetime
from sqlalchemy.orm import Session
from .config import settings
from .models import Alert, StatusEnum
from .ai_agent import apply_decision


@dataclass
class RemediationResult:
    action: str
    status: str
    message: str


def choose_action(alert: Alert) -> str:
    rule = alert.rule_name or ""
    title = (alert.title or "").lower()
    description = (alert.description or "").lower()
    text = f"{rule} {title} {description}"

    if "disk" in text or "stockage" in text or "storage" in text or "espace" in text:
        return "extend_storage"
    if "ram" in text or "memory" in text or "memoire" in text:
        return "scale_memory"
    if "cpu" in text:
        return "scale_compute"
    if "restarts" in rule or "crashloop" in text:
        return "restart_workload"
    if "status" in rule and alert.pod_id:
        return "isolate_workload"
    if "status" in rule and alert.vm_id:
        return "quarantine_vm"
    return "open_incident"


def describe_action(action: str, alert: Alert) -> str:
    resource = alert.vm_id or alert.pod_id or "ressource inconnue"
    if action == "extend_storage":
        return f"Ajouter {settings.REMEDIATION_STORAGE_INCREMENT_GB} GB de stockage a {resource}."
    if action == "scale_memory":
        return f"Augmenter la memoire de {settings.REMEDIATION_MEMORY_SCALE_PERCENT}% pour {resource}."
    if action == "scale_compute":
        return f"Ajouter de la capacite CPU/vCPU ou migrer {resource} vers un flavor plus grand."
    if action == "restart_workload":
        return f"Redemarrer le workload {resource} apres verification des logs."
    if action == "isolate_workload":
        return f"Isoler le workload {resource} pour bloquer l'impact urgent."
    if action == "quarantine_vm":
        return f"Quarantainer la VM {resource} et bloquer le trafic dangereux si l'incident est critique."
    return f"Ouvrir un incident prioritaire pour {resource}."


def execute_remediation(db: Session, alert: Alert, operator: str = "AI-Agent", force: bool = False) -> Alert:
    apply_decision(db, alert)
    action = choose_action(alert)
    message = describe_action(action, alert)

    allowed = force or (
        settings.AUTO_REMEDIATION_ENABLED
        and (alert.ai_score or 0) >= settings.AUTO_REMEDIATION_MIN_SCORE
        and alert.status == StatusEnum.active
    )

    if not allowed:
        result = RemediationResult(
            action=action,
            status="recommended",
            message=f"Action recommandee, execution automatique non autorisee. {message}",
        )
    elif settings.AUTO_REMEDIATION_DRY_RUN:
        result = RemediationResult(
            action=action,
            status="dry_run",
            message=f"Simulation executee par {operator}. {message}",
        )
    else:
        result = RemediationResult(
            action=action,
            status="blocked",
            message=(
                "Execution reelle bloquee: connecteur d'action infra non configure. "
                f"Action cible: {message}"
            ),
        )

    alert.remediation_action = result.action
    alert.remediation_status = result.status
    alert.remediation_message = result.message
    alert.remediation_updated_at = datetime.utcnow()

    if result.status in ("dry_run", "blocked"):
        alert.acknowledged = True
        alert.acknowledged_by = operator.strip() or "AI-Agent"
        alert.acknowledged_at = alert.acknowledged_at or datetime.utcnow()
        alert.operator_note = (alert.operator_note or "") + f"\n[{result.status}] {result.message}"

    return alert


def auto_remediate_if_needed(db: Session, alert: Alert) -> Alert:
    if not settings.AUTO_REMEDIATION_ENABLED:
        alert.remediation_action = choose_action(alert)
        alert.remediation_status = "recommended"
        alert.remediation_message = describe_action(alert.remediation_action, alert)
        alert.remediation_updated_at = datetime.utcnow()
        return alert

    if (alert.ai_score or 0) >= settings.AUTO_REMEDIATION_MIN_SCORE:
        return execute_remediation(db, alert, operator="AI-Agent")

    return alert
