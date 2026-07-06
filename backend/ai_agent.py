"""
Architecture D — AI Agent Core Engine
======================================
Implements the three-pillar AIOps pipeline described in the project spec:

  1. Anomaly Detection & Correlation
     Cross-references multi-source telemetry: metrics (m), logs (l), traces (t).
     Builds anomaly vector A = [m, l, t] and computes its Euclidean norm.

  2. Dynamic Health Scoring
     Multi-variable decay model:
       H = 100 * exp(-λ * |A|²)   clamped to [0, 100]
     where λ is tuned per severity so critical anomalies decay faster.

  3. Decision Engine
     Maps |A| → decision tier, attaches recommendation and confidence.
     Returns a fully populated AlertDecision ready for the remediation agent.

The engine is stateless and replaceable: swap analyze_alert() with an LLM
call and the rest of the pipeline remains unchanged.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from .models import Alert, SeverityEnum, StatusEnum, VirtualMachine, Pod


# ─── Knowledge base ───────────────────────────────────────────────────────────

# Anomaly signatures: pattern → (log_weight, trace_weight, extra_score, label)
_KNOWLEDGE_BASE: list[tuple[str, float, float, int, str]] = [
    # (keyword,          log_w, trace_w, bonus, label)
    ("cpu",              0.30,  0.20,    5,  "cpu_saturation"),
    ("ram",              0.30,  0.15,    5,  "memory_pressure"),
    ("memory",           0.30,  0.15,    5,  "memory_pressure"),
    ("disk",             0.25,  0.10,    4,  "storage_pressure"),
    ("storage",          0.25,  0.10,    4,  "storage_pressure"),
    ("restarts",         0.50,  0.30,    8,  "crashloop"),
    ("crashloop",        0.55,  0.35,    10, "crashloop"),
    ("status",           0.40,  0.20,    6,  "resource_unavailable"),
    ("error",            0.45,  0.25,    7,  "application_error"),
    ("timeout",          0.35,  0.40,    8,  "latency_spike"),
    ("latency",          0.30,  0.45,    8,  "latency_spike"),
    ("oom",              0.60,  0.30,    12, "oom_kill"),
    ("blocked",          0.40,  0.20,    6,  "deadlock"),
    ("network",          0.20,  0.55,    7,  "network_degradation"),
    ("replica",          0.35,  0.25,    5,  "replication_lag"),
    ("backup",           0.15,  0.10,    3,  "backup_failure"),
]

# Decay constants per severity — higher λ = faster health drop
_LAMBDA: dict[str, float] = {
    "critical": 2.8,
    "warning":  1.4,
    "info":     0.5,
}


# ─── Data structures ──────────────────────────────────────────────────────────

@dataclass
class AnomalyVector:
    m: float          # metrics component  [0, 1]
    l: float          # logs    component  [0, 1]
    t: float          # traces  component  [0, 1]

    @property
    def norm(self) -> float:
        """Euclidean norm |A| = sqrt(m² + l² + t²), normalised to [0, 1]."""
        raw = math.sqrt(self.m ** 2 + self.l ** 2 + self.t ** 2)
        return min(raw / math.sqrt(3), 1.0)   # max possible = sqrt(3)

    def decay_health(self, severity: str) -> float:
        """H = 100 · exp(−λ · |A|²), clamped [0, 100]."""
        lam = _LAMBDA.get(severity, 1.0)
        return max(0.0, min(100.0, 100.0 * math.exp(-lam * self.norm ** 2)))


@dataclass
class AlertDecision:
    score: int
    decision: str
    category: str
    reason: str
    recommendation: str
    confidence: float
    # Anomaly vector components stored for traceability
    anomaly_m: float = 0.0
    anomaly_l: float = 0.0
    anomaly_t: float = 0.0
    anomaly_norm: float = 0.0
    health_impact: float = 100.0


# ─── Anomaly vector computation ───────────────────────────────────────────────

def _build_anomaly_vector(alert: Alert, db: Session) -> AnomalyVector:
    """
    Ingestion layer: aggregates signal from three telemetry sources.

    Metrics component (m):
      - Severity base + threshold breach ratio
      - Resource state (VM ERROR, Pod Failed)
      - Recurrence in sliding window

    Logs component (l):
      - Keyword matching against knowledge base
      - Repeated similar alerts → log signal amplified

    Traces component (t):
      - Keyword matching (timeout, latency, network)
      - Severity amplification for critical traces
    """
    text = " ".join(filter(None, [
        alert.rule_name or "",
        alert.title or "",
        alert.description or "",
    ])).lower()

    # ── Metrics component (m) ────────────────────────────────────────────────
    m = 0.0

    # Severity base
    if alert.severity == SeverityEnum.critical:
        m += 0.55
    elif alert.severity == SeverityEnum.warning:
        m += 0.30
    else:
        m += 0.10

    # Threshold breach ratio
    if alert.metric_value is not None and alert.threshold and alert.threshold > 0:
        ratio = alert.metric_value / alert.threshold
        if ratio >= 1.5:
            m += 0.30
        elif ratio >= 1.25:
            m += 0.20
        elif ratio >= 1.0:
            m += 0.10

    # Resource state
    if alert.vm_id:
        vm = db.get(VirtualMachine, alert.vm_id)
        if vm and vm.status == "ERROR":
            m += 0.15
    if alert.pod_id:
        pod = db.get(Pod, alert.pod_id)
        if pod and pod.status in ("Failed", "Unknown"):
            m += 0.15
        elif pod and pod.restart_count and pod.restart_count >= 5:
            m += 0.10

    # Recurrence in 1h window
    since = datetime.utcnow() - timedelta(hours=1)
    recurrence = db.query(Alert).filter(
        Alert.rule_name == alert.rule_name,
        Alert.status.in_([StatusEnum.active, StatusEnum.acknowledged]),
        Alert.triggered_at >= since,
    ).count()
    if recurrence >= 5:
        m += 0.20
    elif recurrence >= 3:
        m += 0.12
    elif recurrence >= 2:
        m += 0.06

    m = min(m, 1.0)

    # ── Logs component (l) + Traces component (t) ─────────────────────────
    l_val = 0.0
    t_val = 0.0

    for keyword, log_w, trace_w, _bonus, _label in _KNOWLEDGE_BASE:
        if keyword in text:
            l_val += log_w
            t_val += trace_w

    # Severity amplifier for logs
    if alert.severity == SeverityEnum.critical:
        l_val *= 1.4
        t_val *= 1.3
    elif alert.severity == SeverityEnum.warning:
        l_val *= 1.1
        t_val *= 1.1

    l_val = min(l_val, 1.0)
    t_val = min(t_val, 1.0)

    return AnomalyVector(m=round(m, 4), l=round(l_val, 4), t=round(t_val, 4))


# ─── Decision engine ──────────────────────────────────────────────────────────

def _match_knowledge_base(text: str) -> tuple[str, int]:
    """Return (category, bonus_score) from the best-matching KB entry."""
    best_label = "infrastructure"
    best_bonus = 0
    for keyword, _lw, _tw, bonus, label in _KNOWLEDGE_BASE:
        if keyword in text and bonus > best_bonus:
            best_label = label
            best_bonus = bonus
    return best_label, best_bonus


def _build_reason(alert: Alert, vec: AnomalyVector, recurrence: int) -> str:
    reasons: list[str] = []

    if alert.severity == SeverityEnum.critical:
        reasons.append("sévérité critique")
    elif alert.severity == SeverityEnum.warning:
        reasons.append("sévérité warning")
    else:
        reasons.append("signal informatif")

    if alert.metric_value is not None and alert.threshold and alert.threshold > 0:
        ratio = alert.metric_value / alert.threshold
        if ratio >= 1.5:
            reasons.append(f"dépassement fort ({ratio:.1f}x le seuil)")
        elif ratio >= 1.0:
            reasons.append("seuil dépassé")

    if vec.m >= 0.7:
        reasons.append("forte pression métriques")
    if vec.l >= 0.5:
        reasons.append("corrélation logs détectée")
    if vec.t >= 0.4:
        reasons.append("signal traces détecté")

    if recurrence >= 5:
        reasons.append(f"récurrence élevée ({recurrence} alertes/1h)")
    elif recurrence >= 3:
        reasons.append(f"récurrence modérée ({recurrence} alertes/1h)")

    if alert.acknowledged:
        reasons.append("déjà acquittée")

    return ", ".join(reasons) if reasons else "signal faible"


def _recommendation_for(decision: str, category: str, resource_id: str | None) -> str:
    resource = resource_id or "la ressource"

    if decision == "escalate":
        return (
            f"[ESCALADE] Déclencher immédiatement une intervention N2/N3 sur {resource}. "
            "Vérifier les dépendances et préparer un plan de bascule si la saturation persiste."
        )
    if decision == "investigate":
        return (
            f"[INVESTIGATION] Analyser les métriques, logs et traces des 30 dernières minutes sur {resource}. "
            f"Catégorie détectée: {category}. Vérifier les services en aval avant escalade."
        )
    if decision == "watch":
        return (
            f"[SURVEILLANCE] Monitorer {resource} sur le prochain cycle de collecte. "
            "Acquitter avec commentaire si l'alerte est connue et non bloquante."
        )
    return (
        f"[FILTRAGE] Probable bruit — aucune récurrence ni impact service détecté sur {resource}. "
        "Supprimer si l'anomalie ne se manifeste pas dans les 15 prochaines minutes."
    )


# ─── Public API ───────────────────────────────────────────────────────────────

def analyze_alert(db: Session, alert: Alert) -> AlertDecision:
    """
    Full AI Agent pipeline:
      1. Build anomaly vector A = [m, l, t]
      2. Compute dynamic health impact via decay model
      3. Map |A| → score (0-100) and decision tier
      4. Return enriched AlertDecision
    """
    vec = _build_anomaly_vector(alert, db)
    severity_str = alert.severity.value if alert.severity else "info"
    health_impact = vec.decay_health(severity_str)

    # Score = 100 - health_impact, amplified by severity
    base_score = int(round(100 - health_impact))

    text = " ".join(filter(None, [
        alert.rule_name or "",
        alert.title or "",
        alert.description or "",
    ])).lower()

    category, kb_bonus = _match_knowledge_base(text)

    # Map rule prefix to category
    if (alert.rule_name or "").startswith("vm."):
        category = category if category != "infrastructure" else "compute"
    elif (alert.rule_name or "").startswith("pod."):
        category = category if category != "infrastructure" else "container"

    score = min(100, base_score + kb_bonus)

    # Acknowledged penalty
    if alert.acknowledged:
        score = max(0, score - 8)

    # Recurrence window for reason
    since = datetime.utcnow() - timedelta(hours=1)
    recurrence = db.query(Alert).filter(
        Alert.rule_name == alert.rule_name,
        Alert.status.in_([StatusEnum.active, StatusEnum.acknowledged]),
        Alert.triggered_at >= since,
    ).count()

    # Decision tier
    if score >= 78:
        decision = "escalate"
    elif score >= 52:
        decision = "investigate"
    elif score >= 32:
        decision = "watch"
    else:
        decision = "suppress"

    resource_id = alert.vm_id or alert.pod_id
    reason = _build_reason(alert, vec, recurrence)
    recommendation = _recommendation_for(decision, category, resource_id)

    # Confidence: base + bonus for each populated telemetry dimension
    confidence = 0.60
    if alert.metric_value is not None and alert.threshold is not None:
        confidence += 0.12
    if vec.l > 0.1:
        confidence += 0.10
    if vec.t > 0.1:
        confidence += 0.08
    if recurrence >= 2:
        confidence += 0.05
    confidence = round(min(confidence, 0.97), 3)

    return AlertDecision(
        score=score,
        decision=decision,
        category=category,
        reason=reason,
        recommendation=recommendation,
        confidence=confidence,
        anomaly_m=vec.m,
        anomaly_l=vec.l,
        anomaly_t=vec.t,
        anomaly_norm=round(vec.norm, 4),
        health_impact=round(health_impact, 2),
    )


def apply_decision(db: Session, alert: Alert) -> Alert:
    """Persist the AI decision onto the alert model."""
    decision = analyze_alert(db, alert)
    alert.ai_score          = decision.score
    alert.ai_decision       = decision.decision
    alert.ai_category       = decision.category
    alert.ai_reason         = decision.reason
    alert.ai_recommendation = decision.recommendation
    alert.ai_confidence     = decision.confidence
    alert.ai_updated_at     = datetime.utcnow()
    # Anomaly vector fields
    alert.anomaly_m           = decision.anomaly_m
    alert.anomaly_l           = decision.anomaly_l
    alert.anomaly_t           = decision.anomaly_t
    alert.anomaly_vector_norm = decision.anomaly_norm
    return alert
