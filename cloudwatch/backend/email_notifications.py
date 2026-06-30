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


def send_alert_email(alert: Alert):
    """Send an email notification for a newly-created alert."""
    if not email_alerts_configured():
        logger.info("[EMAIL] Alert email disabled or not configured.")
        return

    resource = alert.vm_id or alert.pod_id or "unknown"
    subject = f"[CloudWatch] {alert.severity.value.upper()} - {alert.title}"
    body = f"""Nouvelle alerte CloudWatch

Severite: {alert.severity.value.upper()}
Titre: {alert.title}
Ressource: {resource}
Regle: {alert.rule_name or "-"}
Valeur: {alert.metric_value}
Seuil: {alert.threshold}
Date: {alert.triggered_at}

Description:
{alert.description or "-"}

Dashboard: http://localhost:5173/alerts
"""

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
        logger.info("[EMAIL] Alert notification sent: %s", subject)
    except Exception as exc:
        logger.exception("[EMAIL] Failed to send alert notification: %s", exc)
