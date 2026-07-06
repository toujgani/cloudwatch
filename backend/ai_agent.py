"""
Agent de decision NOC.

Il filtre le bruit, priorise les alertes utiles et fournit une action conseillee
avec des regles explicables. Cette couche peut ensuite etre remplacee par un
modele ML/LLM sans changer l'API exposee au frontend.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from .models import Alert, SeverityEnum, StatusEnum, VirtualMachine, Pod


@dataclass
class AlertDecision:
    score: int
    decision: str
    category: str
    reason: str
    recommendation: str
    confidence: float


def analyze_alert(db: Session, alert: Alert) -> AlertDecision:
    score = 20
    reasons: list[str] = []
    category = "infrastructure"

    if alert.severity == SeverityEnum.critical:
        score += 45
        reasons.append("severite critique")
    elif alert.severity == SeverityEnum.warning:
        score += 25
        reasons.append("severite warning")
    else:
        score += 8
        reasons.append("severite informative")

    if alert.metric_value is not None and alert.threshold not in (None, 0):
        ratio = alert.metric_value / alert.threshold
        if ratio >= 1.25:
            score += 15
            reasons.append("depassement fort du seuil")
        elif ratio >= 1.0:
            score += 8
            reasons.append("seuil depasse")

    if alert.rule_name:
        if alert.rule_name.startswith("vm."):
            category = "compute"
        if alert.rule_name.startswith("pod."):
            category = "container"
        if "status" in alert.rule_name:
            score += 10
            reasons.append("ressource en etat anormal")
        if "restarts" in alert.rule_name:
            score += 8
            reasons.append("redemarrages repetes")

    if alert.vm_id:
        vm = db.get(VirtualMachine, alert.vm_id)
        if vm and vm.status == "ERROR":
            score += 12
            reasons.append("VM en erreur OpenStack")
    if alert.pod_id:
        pod = db.get(Pod, alert.pod_id)
        if pod and pod.status in ("Failed", "Unknown"):
            score += 12
            reasons.append("pod indisponible")

    since = datetime.utcnow() - timedelta(hours=1)
    repeated = db.query(Alert).filter(
        Alert.rule_name == alert.rule_name,
        Alert.status == StatusEnum.active,
        Alert.triggered_at >= since,
    ).count()
    if repeated >= 3:
        score += 10
        reasons.append(f"{repeated} alertes similaires sur 1h")

    if alert.acknowledged:
        score -= 8
        reasons.append("deja acquittee")

    score = max(0, min(100, score))

    if score >= 80:
        decision = "escalate"
        recommendation = "Declencher une intervention rapide controlee, puis escalader au N2/N3 si la saturation persiste."
    elif score >= 55:
        decision = "investigate"
        recommendation = "Analyser les metriques recentes, logs applicatifs et dependances avant escalation."
    elif score >= 35:
        decision = "watch"
        recommendation = "Surveiller pendant le prochain cycle et acquitter avec commentaire si l'alerte est connue."
    else:
        decision = "suppress"
        recommendation = "Filtrer comme bruit probable si aucune recurrence ni impact service n'est observe."

    confidence = 0.72
    if alert.metric_value is not None and alert.threshold is not None:
        confidence += 0.12
    if alert.vm_id or alert.pod_id:
        confidence += 0.08

    return AlertDecision(
        score=score,
        decision=decision,
        category=category,
        reason=", ".join(reasons) or "signal faible",
        recommendation=recommendation,
        confidence=min(confidence, 0.95),
    )


def apply_decision(db: Session, alert: Alert) -> Alert:
    decision = analyze_alert(db, alert)
    alert.ai_score = decision.score
    alert.ai_decision = decision.decision
    alert.ai_category = decision.category
    alert.ai_reason = decision.reason
    alert.ai_recommendation = decision.recommendation
    alert.ai_confidence = decision.confidence
    alert.ai_updated_at = datetime.utcnow()
    return alert
