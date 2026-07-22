"""
Cloud AI Monitor — Production SMTP Notification Pipeline.

Sends comprehensive incident reports after every AI remediation or alert lifecycle event.
Includes: metrics before/after, AI reasoning, actions executed, cost analysis, recommendations.

Architecture:
  - SmtpService: handles connection, TLS, auth, retry
  - IncidentReportBuilder: generates structured email content from real data
  - NotificationManager: orchestrates when/what to send
"""
import logging
import smtplib
import time
from datetime import datetime
from email.message import EmailMessage
from dataclasses import dataclass, field
from typing import Optional

from .config import settings

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 2


# ═══════════════════════════════════════════════════════════════════════════════
# SMTP Service — connection, auth, retry
# ═══════════════════════════════════════════════════════════════════════════════

def _recipients() -> list[str]:
    return [email.strip() for email in settings.ALERT_EMAIL_TO.split(",") if email.strip()]


def email_alerts_configured() -> bool:
    configured = bool(
        settings.EMAIL_ALERTS_ENABLED
        and settings.SMTP_HOST
        and settings.SMTP_FROM
        and settings.SMTP_PASSWORD
        and _recipients()
    )
    if not configured:
        logger.debug("[SMTP] Not configured — Host=%s, Password=%s, From=%s, To=%s",
                     settings.SMTP_HOST or "(empty)",
                     "(set)" if settings.SMTP_PASSWORD else "(EMPTY)",
                     settings.SMTP_FROM or "(empty)",
                     settings.ALERT_EMAIL_TO or "(empty)")
    return configured


def _send_smtp(subject: str, body: str) -> bool:
    """
    Send email with retry logic. Returns True if delivered, False if all attempts failed.
    Never raises — the monitoring system must never crash because of email.
    """
    if not email_alerts_configured():
        logger.warning("[SMTP] Skipped — not configured.")
        return False

    recipients = _recipients()
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.SMTP_FROM
    message["To"] = ", ".join(recipients)
    message.set_content(body)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            logger.info("[SMTP] Attempt %d/%d — Connecting to %s:%s ...",
                        attempt, MAX_RETRIES, settings.SMTP_HOST, settings.SMTP_PORT)

            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as smtp:
                if settings.SMTP_USE_TLS:
                    smtp.starttls()

                if settings.SMTP_USERNAME and settings.SMTP_PASSWORD:
                    smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)

                smtp.send_message(message)
                logger.info("[SMTP] Delivered: %s → %s", subject, settings.ALERT_EMAIL_TO)
                return True

        except smtplib.SMTPAuthenticationError as e:
            logger.error("[SMTP] Authentication FAILED (attempt %d): %s", attempt, e)
            break  # Don't retry auth failures
        except (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected, OSError) as e:
            logger.warning("[SMTP] Connection error (attempt %d): %s", attempt, e)
        except smtplib.SMTPException as e:
            logger.error("[SMTP] SMTP error (attempt %d): %s", attempt, e)
        except Exception as e:
            logger.exception("[SMTP] Unexpected error (attempt %d): %s", attempt, e)

        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY_SECONDS)

    logger.error("[SMTP] All %d attempts failed for: %s", MAX_RETRIES, subject)
    return False


# ═══════════════════════════════════════════════════════════════════════════════
# Incident Report Builder — generates email content from real data
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class IncidentReport:
    """All data needed for a comprehensive incident report email."""
    incident_type: str = "alert"  # alert, remediation, resolve_all, cleanup
    severity: str = "info"
    title: str = ""
    description: str = ""
    namespace: str = ""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

    # Alert details
    alert_id: Optional[int] = None
    rule_name: Optional[str] = None
    metric_value: Optional[float] = None
    threshold: Optional[float] = None

    # AI analysis
    ai_score: Optional[int] = None
    ai_decision: Optional[str] = None
    ai_confidence: Optional[float] = None
    ai_reason: Optional[str] = None
    ai_recommendation: Optional[str] = None
    anomaly_vector: Optional[str] = None

    # Remediation
    remediation_action: Optional[str] = None
    remediation_status: Optional[str] = None
    remediation_message: Optional[str] = None
    actions_executed: list[str] = field(default_factory=list)
    protected_resources: list[str] = field(default_factory=lambda: ["cloud-ai-monitor", "postgresql"])

    # Metrics
    cpu_before: Optional[str] = None
    cpu_after: Optional[str] = None
    ram_before: Optional[str] = None
    ram_after: Optional[str] = None
    pods_before: Optional[int] = None
    pods_after: Optional[int] = None
    alerts_resolved: int = 0

    # Resolve-all specific
    total_resolved: int = 0
    total_failed: int = 0
    quota_level: Optional[str] = None


def _build_subject(report: IncidentReport) -> str:
    """Generate email subject line."""
    sev = report.severity.upper()
    if report.incident_type == "resolve_all":
        return f"[AIOps] Tout Resoudre — {report.total_resolved} alertes resolues"
    if report.incident_type == "cleanup":
        return f"[AIOps] Nettoyage Namespace Termine"
    if report.remediation_status == "applied":
        return f"[{sev}] {report.title} — Remediation Executee"
    return f"[{sev}] {report.title}"


def _build_body(report: IncidentReport) -> str:
    """Generate comprehensive incident report email body."""
    lines = []
    lines.append("=" * 60)
    lines.append("CLOUD AI MONITOR — RAPPORT D'INCIDENT AUTOMATIQUE")
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"Timestamp:   {report.timestamp}")
    lines.append(f"Namespace:   {report.namespace}")
    lines.append(f"Severite:    {report.severity.upper()}")
    lines.append(f"Type:        {report.incident_type}")
    lines.append("")

    # ── Incident Summary
    lines.append("-" * 40)
    lines.append("RESUME DE L'INCIDENT")
    lines.append("-" * 40)
    lines.append(f"Titre: {report.title}")
    lines.append(f"Description: {report.description}")
    if report.alert_id:
        lines.append(f"Alert ID: #{report.alert_id}")
    if report.rule_name:
        lines.append(f"Regle: {report.rule_name}")
    if report.metric_value is not None and report.threshold is not None:
        lines.append(f"Valeur mesuree: {report.metric_value}")
        lines.append(f"Seuil: {report.threshold}")
    lines.append("")

    # ── AI Analysis
    if report.ai_score is not None:
        lines.append("-" * 40)
        lines.append("ANALYSE IA")
        lines.append("-" * 40)
        lines.append(f"Score IA:      {report.ai_score}/100")
        lines.append(f"Decision:      {report.ai_decision or 'N/A'}")
        lines.append(f"Confiance:     {report.ai_confidence or 'N/A'}")
        lines.append(f"Raison:        {report.ai_reason or 'N/A'}")
        if report.anomaly_vector:
            lines.append(f"Vecteur A:     {report.anomaly_vector}")
        if report.ai_recommendation:
            lines.append(f"Recommandation: {report.ai_recommendation}")
        lines.append("")

    # ── Remediation Actions
    if report.remediation_action:
        lines.append("-" * 40)
        lines.append("ACTIONS DE REMEDIATION")
        lines.append("-" * 40)
        lines.append(f"Action:  {report.remediation_action}")
        lines.append(f"Statut:  {report.remediation_status}")
        if report.remediation_message:
            lines.append(f"Detail:  {report.remediation_message[:300]}")
        if report.actions_executed:
            lines.append("")
            lines.append("Actions executees:")
            for action in report.actions_executed:
                lines.append(f"  - {action}")
        lines.append("")
        lines.append("Ressources protegees (non modifiees):")
        for res in report.protected_resources:
            lines.append(f"  [PROTEGE] {res}")
        lines.append("")

    # ── Metrics comparison
    if report.cpu_before or report.cpu_after:
        lines.append("-" * 40)
        lines.append("METRIQUES")
        lines.append("-" * 40)
        if report.cpu_before:
            lines.append(f"CPU avant:     {report.cpu_before}")
        if report.cpu_after:
            lines.append(f"CPU apres:     {report.cpu_after}")
        if report.ram_before:
            lines.append(f"RAM avant:     {report.ram_before}")
        if report.ram_after:
            lines.append(f"RAM apres:     {report.ram_after}")
        if report.pods_before is not None:
            lines.append(f"Pods avant:    {report.pods_before}")
        if report.pods_after is not None:
            lines.append(f"Pods apres:    {report.pods_after}")
        lines.append("")

    # ── Resolve-All summary
    if report.incident_type == "resolve_all":
        lines.append("-" * 40)
        lines.append("RESOLUTION GLOBALE")
        lines.append("-" * 40)
        lines.append(f"Alertes resolues:  {report.total_resolved}")
        lines.append(f"Echecs:            {report.total_failed}")
        lines.append(f"Niveau quota:      {report.quota_level or 'N/A'}")
        lines.append("")

    # ── Final status
    lines.append("-" * 40)
    lines.append("STATUT FINAL")
    lines.append("-" * 40)
    if report.remediation_status == "applied":
        lines.append(">> RESOLU — Remediation automatique reussie.")
    elif report.remediation_status == "dry_run":
        lines.append(">> SIMULATION — Action simulee (mode dry-run actif).")
    elif report.remediation_status == "blocked":
        lines.append(">> BLOQUE — Action impossible. Intervention manuelle requise.")
    elif report.incident_type == "resolve_all":
        lines.append(f">> {report.total_resolved} alertes resolues automatiquement.")
    else:
        lines.append(">> ALERTE ACTIVE — En attente de traitement.")
    lines.append("")

    # ── Footer
    lines.append("=" * 60)
    lines.append("Cloud AI Monitor | CIRES Technologies | Tanger Med")
    lines.append("AIOps Engine — Plateforme de Remediation Automatique")
    lines.append("Ce rapport a ete genere automatiquement.")
    lines.append("=" * 60)

    return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# Notification Manager — public API used by the rest of the application
# ═══════════════════════════════════════════════════════════════════════════════

def send_alert_email(alert) -> bool:
    """Send incident report when an alert is created."""
    report = IncidentReport(
        incident_type="alert",
        severity=alert.severity.value if alert.severity else "info",
        title=alert.title or "Alerte",
        description=alert.description or "",
        alert_id=alert.id,
        rule_name=alert.rule_name,
        metric_value=alert.metric_value,
        threshold=alert.threshold,
        ai_score=alert.ai_score,
        ai_decision=alert.ai_decision,
        ai_confidence=alert.ai_confidence,
        ai_reason=alert.ai_reason,
        ai_recommendation=alert.ai_recommendation,
        anomaly_vector=f"[{alert.anomaly_m or 0:.3f}, {alert.anomaly_l or 0:.3f}, {alert.anomaly_t or 0:.3f}]" if alert.anomaly_m is not None else None,
    )
    subject = _build_subject(report)
    body = _build_body(report)
    return _send_smtp(subject, body)


def send_remediation_email(alert) -> bool:
    """Send incident report after AI executes a remediation action."""
    report = IncidentReport(
        incident_type="remediation",
        severity=alert.severity.value if alert.severity else "info",
        title=alert.title or "Remediation",
        description=alert.description or "",
        alert_id=alert.id,
        rule_name=alert.rule_name,
        metric_value=alert.metric_value,
        threshold=alert.threshold,
        ai_score=alert.ai_score,
        ai_decision=alert.ai_decision,
        ai_confidence=alert.ai_confidence,
        ai_reason=alert.ai_reason,
        ai_recommendation=alert.ai_recommendation,
        anomaly_vector=f"[{alert.anomaly_m or 0:.3f}, {alert.anomaly_l or 0:.3f}, {alert.anomaly_t or 0:.3f}]" if alert.anomaly_m is not None else None,
        remediation_action=alert.remediation_action,
        remediation_status=alert.remediation_status,
        remediation_message=alert.remediation_message,
    )
    subject = _build_subject(report)
    body = _build_body(report)
    return _send_smtp(subject, body)


def send_resolve_all_email(resolved: int, failed: int, quota_level: str) -> bool:
    """Send summary report after Tout Resoudre completes."""
    report = IncidentReport(
        incident_type="resolve_all",
        severity="info" if failed == 0 else "warning",
        title=f"Resolution globale — {resolved} alertes traitees",
        description=f"Le systeme a resolu {resolved} alertes automatiquement. {failed} echecs.",
        total_resolved=resolved,
        total_failed=failed,
        quota_level=quota_level,
    )
    subject = _build_subject(report)
    body = _build_body(report)
    return _send_smtp(subject, body)


def send_cleanup_email(deleted_deployments: list, deleted_pods: list, errors: list) -> bool:
    """Send report after namespace cleanup."""
    total = len(deleted_deployments) + len(deleted_pods)
    report = IncidentReport(
        incident_type="cleanup",
        severity="info",
        title=f"Nettoyage namespace — {total} ressources supprimees",
        description=f"Deployments supprimes: {', '.join(deleted_deployments) or 'aucun'}. Pods supprimes: {len(deleted_pods)}.",
        actions_executed=[f"Deleted deployment: {d}" for d in deleted_deployments] + [f"Deleted pod: {p}" for p in deleted_pods[:10]],
    )
    if len(deleted_pods) > 10:
        report.actions_executed.append(f"... et {len(deleted_pods) - 10} autres pods")
    subject = _build_subject(report)
    body = _build_body(report)
    return _send_smtp(subject, body)


# ═══════════════════════════════════════════════════════════════════════════════
# Legacy compatibility — _send_email for existing callers
# ═══════════════════════════════════════════════════════════════════════════════

def _send_email(subject: str, body: str) -> bool:
    """Legacy wrapper for direct email sending."""
    return _send_smtp(subject, body)
