import logging
import smtplib
from email.message import EmailMessage

from .config import settings
from .models import Alert

logger = logging.getLogger(__name__)


def _recipients() -> list[str]:
    return [email.strip() for email in settings.ALERT_EMAIL_TO.split(",") if email.strip()]


def email_alerts_configured() -> bool:
    return bool(
        settings.EMAIL_ALERTS_ENABLED
        and settings.SMTP_HOST
        and settings.SMTP_FROM
        and _recipients()
    )


def _send_email(subject: str, body: str):
    """Internal helper to send an email."""
    if not email_alerts_configured():
        return

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.SMTP_FROM
    message["To"] = ", ".join(_recipients())
    message.set_content(body)

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as smtp:
            if settings.SMTP_USE_TLS:
                smtp.starttls()
            if settings.SMTP_USERNAME:
                smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            smtp.send_message(message)
        logger.info("[EMAIL] Notification sent: %s", subject)
    except Exception as exc:
        logger.exception("[EMAIL] Failed to send notification: %s", exc)


def send_alert_email(alert: Alert):
    """Send an email notification for a newly-created alert."""
    if not email_alerts_configured():
        return

    resource = alert.vm_id or alert.pod_id or "unknown"
    subject = f"[Cloud AI Monitor] {alert.severity.value.upper()} — {alert.title}"
    body = f"""Nouvelle alerte Cloud AI Monitor

Severite: {alert.severity.value.upper()}
Titre: {alert.title}
Ressource: {resource}
Regle: {alert.rule_name or "-"}
Valeur: {alert.metric_value}
Seuil: {alert.threshold}
Date: {alert.triggered_at}

AI Score: {alert.ai_score or "N/A"}
AI Decision: {alert.ai_decision or "N/A"}
AI Recommendation: {alert.ai_recommendation or "N/A"}

Description:
{alert.description or "-"}
"""
    _send_email(subject, body)


def send_remediation_email(alert: Alert):
    """Send an email when the AI executes a remediation action."""
    if not email_alerts_configured():
        return

    resource = alert.vm_id or alert.pod_id or "unknown"
    subject = f"[Cloud AI Monitor] REMEDIATION — {alert.remediation_action} sur {resource}"
    body = f"""Action de remediation AI executee

Action: {alert.remediation_action}
Statut: {alert.remediation_status}
Ressource: {resource}
AI Score: {alert.ai_score}
AI Decision: {alert.ai_decision}

Alerte originale:
  Titre: {alert.title}
  Severite: {alert.severity.value.upper()}
  Regle: {alert.rule_name or "-"}

Message remediation:
{alert.remediation_message or "-"}

Vecteur anomalie: A = [{alert.anomaly_m or 0:.3f}, {alert.anomaly_l or 0:.3f}, {alert.anomaly_t or 0:.3f}]
Norme: |A| = {alert.anomaly_vector_norm or 0:.4f}

---
Cloud AI Monitor — CIRES Technologies / Tanger Med
"""
    _send_email(subject, body)
