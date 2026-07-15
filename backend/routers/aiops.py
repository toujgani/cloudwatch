"""
AIOps Simulator router — Architecture D interactive demonstration.
Allows injecting anomalies, adjusting thresholds, and observing
the AI Agent's real-time reasoning and remediation workflow.
"""
from __future__ import annotations

import math
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Alert, SeverityEnum, StatusEnum, AuditActionEnum
from ..ai_agent import analyze_alert, AnomalyVector, _KNOWLEDGE_BASE, _LAMBDA
from ..remediation_agent import build_plan, choose_action
from .. import audit as audit_trail

router = APIRouter(prefix="/aiops", tags=["AIOps Simulator"])


# ─── Schemas ──────────────────────────────────────────────────────────────────

class AnomalyInjectionIn(BaseModel):
    """Manual anomaly injection payload for the simulator."""
    title: str = "Anomalie simulée"
    description: str = "Injected by AIOps simulator"
    severity: SeverityEnum = SeverityEnum.warning
    rule_name: str = "sim.anomaly"
    metric_value: float = 75.0
    threshold: float = 70.0
    vm_id: Optional[str] = None
    pod_id: Optional[str] = None
    # Override anomaly vector components directly (0–1)
    override_m: Optional[float] = Field(default=None, ge=0, le=1)
    override_l: Optional[float] = Field(default=None, ge=0, le=1)
    override_t: Optional[float] = Field(default=None, ge=0, le=1)


class ThresholdConfig(BaseModel):
    """Simulate a configuration change on alert thresholds."""
    cpu_warning: float = Field(default=70.0, ge=0, le=100)
    cpu_critical: float = Field(default=90.0, ge=0, le=100)
    ram_warning: float = Field(default=75.0, ge=0, le=100)
    ram_critical: float = Field(default=90.0, ge=0, le=100)
    auto_remediation_min_score: int = Field(default=55, ge=0, le=100)


class VectorSimIn(BaseModel):
    """Raw vector simulation — compute health score without touching the DB."""
    m: float = Field(..., ge=0, le=1, description="Metrics anomaly component")
    l: float = Field(..., ge=0, le=1, description="Logs anomaly component")
    t: float = Field(..., ge=0, le=1, description="Traces anomaly component")
    severity: SeverityEnum = SeverityEnum.warning


class AlertOut(BaseModel):
    id: int
    severity: str
    status: str
    title: str
    ai_score: Optional[int]
    ai_decision: Optional[str]
    ai_category: Optional[str]
    ai_reason: Optional[str]
    ai_recommendation: Optional[str]
    ai_confidence: Optional[float]
    anomaly_m: Optional[float]
    anomaly_l: Optional[float]
    anomaly_t: Optional[float]
    anomaly_vector_norm: Optional[float]
    remediation_action: Optional[str]
    remediation_status: Optional[str]
    remediation_message: Optional[str]
    triggered_at: datetime

    model_config = {"from_attributes": True}


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/simulate/vector")
def simulate_vector(payload: VectorSimIn):
    """
    Pure math endpoint — no DB touch.
    Given A = [m, l, t], compute norm, decay health score, and decision tier.
    Useful for the frontend interactive slider demo.
    """
    vec = AnomalyVector(m=payload.m, l=payload.l, t=payload.t)
    severity_str = payload.severity.value
    lam = _LAMBDA.get(severity_str, 1.0)
    norm = vec.norm
    health = vec.decay_health(severity_str)
    score = int(round(100 - health))

    if score >= 78:
        decision = "escalate"
    elif score >= 52:
        decision = "investigate"
    elif score >= 32:
        decision = "watch"
    else:
        decision = "suppress"

    return {
        "vector": {"m": payload.m, "l": payload.l, "t": payload.t},
        "norm": round(norm, 4),
        "lambda": lam,
        "health_score": round(health, 2),
        "ai_score": score,
        "decision": decision,
        "formula": f"H = 100 · exp(−{lam} · {round(norm, 4)}²) = {round(health, 2)}",
        "decay_curve": [
            {
                "norm": round(n / 20, 2),
                "health": round(100 * math.exp(-lam * (n / 20) ** 2), 2),
            }
            for n in range(0, 21)
        ],
    }


@router.post("/simulate/inject", response_model=AlertOut)
def inject_anomaly(payload: AnomalyInjectionIn, db: Session = Depends(get_db)):
    """
    Inject a simulated anomaly into the live alert pipeline.
    The AI Agent processes it immediately and returns the enriched alert
    with the anomaly vector, health impact, and remediation plan.
    """
    from ..remediation_agent import execute_remediation

    alert = Alert(
        severity=payload.severity,
        status=StatusEnum.active,
        title=payload.title,
        description=payload.description,
        rule_name=payload.rule_name,
        metric_value=payload.metric_value,
        threshold=payload.threshold,
        vm_id=payload.vm_id,
        pod_id=payload.pod_id,
        triggered_at=datetime.utcnow(),
    )

    # Override vector components if provided
    if payload.override_m is not None:
        alert.anomaly_m = payload.override_m
    if payload.override_l is not None:
        alert.anomaly_l = payload.override_l
    if payload.override_t is not None:
        alert.anomaly_t = payload.override_t

    db.add(alert)
    db.flush()  # get id

    from ..ai_agent import apply_decision, AnomalyVector, _LAMBDA
    import math

    # If overrides provided, compute score from override vector
    if any(v is not None for v in [payload.override_m, payload.override_l, payload.override_t]):
        m = payload.override_m if payload.override_m is not None else 0.0
        l = payload.override_l if payload.override_l is not None else 0.0
        t = payload.override_t if payload.override_t is not None else 0.0
        vec = AnomalyVector(m=m, l=l, t=t)
        sev = payload.severity.value
        lam = _LAMBDA.get(sev, 1.0)
        health = 100.0 * math.exp(-lam * vec.norm ** 2)
        score = int(round(min(100, 100 - health)))
        if score >= 78:
            decision = "escalate"
        elif score >= 52:
            decision = "investigate"
        elif score >= 32:
            decision = "watch"
        else:
            decision = "suppress"
        alert.ai_score = score
        alert.ai_decision = decision
        alert.ai_category = "simulated"
        alert.ai_reason = f"Injected vector: m={m}, l={l}, t={t}"
        alert.ai_recommendation = f"Simulated {decision} — vector norm {round(vec.norm, 4)}"
        alert.ai_confidence = 0.85
        alert.anomaly_m = vec.m
        alert.anomaly_l = vec.l
        alert.anomaly_t = vec.t
        alert.anomaly_vector_norm = round(vec.norm, 4)
        alert.ai_updated_at = datetime.utcnow()
    else:
        apply_decision(db, alert)

    # Build remediation plan
    execute_remediation(db, alert, operator="AIOps-Simulator")

    audit_trail.log(
        db,
        action=AuditActionEnum.ai_analysis,
        actor="aiops-simulator",
        resource_type="alert",
        resource_id=str(alert.id),
        detail=f"Injected anomaly: {payload.title} — score={alert.ai_score}, decision={alert.ai_decision}",
        extra={
            "anomaly_m": alert.anomaly_m,
            "anomaly_l": alert.anomaly_l,
            "anomaly_t": alert.anomaly_t,
            "norm": alert.anomaly_vector_norm,
        },
    )

    db.commit()
    db.refresh(alert)
    return alert


@router.post("/simulate/thresholds")
def simulate_thresholds(payload: ThresholdConfig, db: Session = Depends(get_db)):
    """
    Simulate a threshold change: shows how many currently active alerts
    would change decision tier under the new configuration, without
    persisting anything to the DB.
    """
    from ..models import Alert as AlertModel
    active = db.query(AlertModel).filter(
        AlertModel.status.in_([StatusEnum.active, StatusEnum.acknowledged])
    ).all()

    results = []
    for a in active:
        old_decision = a.ai_decision
        old_score = a.ai_score or 0

        # Recompute with simulated thresholds
        sim_alert = type("SimAlert", (), {
            "severity": a.severity,
            "metric_value": a.metric_value,
            "threshold": (
                payload.cpu_critical if "cpu" in (a.rule_name or "") and "critical" in (a.rule_name or "") else
                payload.cpu_warning  if "cpu" in (a.rule_name or "") else
                payload.ram_critical if "ram" in (a.rule_name or "") and "critical" in (a.rule_name or "") else
                payload.ram_warning  if "ram" in (a.rule_name or "") else
                a.threshold
            ),
            "rule_name": a.rule_name,
            "title": a.title,
            "description": a.description,
            "vm_id": a.vm_id,
            "pod_id": a.pod_id,
            "acknowledged": a.acknowledged,
            "id": a.id,
        })()

        # Patch the real alert temporarily to run analyze
        orig_threshold = a.threshold
        a.threshold = sim_alert.threshold
        new_decision_obj = analyze_alert(db, a)
        a.threshold = orig_threshold  # restore

        results.append({
            "alert_id": a.id,
            "title": a.title,
            "old_score": old_score,
            "new_score": new_decision_obj.score,
            "old_decision": old_decision,
            "new_decision": new_decision_obj.decision,
            "changed": old_decision != new_decision_obj.decision,
        })

    changed = sum(1 for r in results if r["changed"])
    return {
        "simulated_config": payload.model_dump(),
        "total_alerts_evaluated": len(results),
        "decisions_changed": changed,
        "details": results,
    }


@router.get("/knowledge-base")
def get_knowledge_base():
    """Expose the AI knowledge base for the frontend simulator."""
    return [
        {
            "keyword": kw,
            "log_weight": lw,
            "trace_weight": tw,
            "score_bonus": bonus,
            "category": label,
        }
        for kw, lw, tw, bonus, label in _KNOWLEDGE_BASE
    ]


@router.get("/pipeline/status")
def pipeline_status(db: Session = Depends(get_db)):
    """Real-time status of the AI pipeline — used by the frontend live panel."""
    from ..models import Alert as AlertModel, AuditLog
    from sqlalchemy import desc

    active_alerts = db.query(AlertModel).filter(
        AlertModel.status.in_([StatusEnum.active, StatusEnum.acknowledged, StatusEnum.assigned])
    ).all()

    scored = [a for a in active_alerts if a.ai_score is not None]
    avg_score = round(sum(a.ai_score for a in scored) / max(len(scored), 1), 1)
    avg_norm  = round(sum(a.anomaly_vector_norm or 0 for a in scored) / max(len(scored), 1), 4)

    decision_dist: dict[str, int] = {}
    for a in scored:
        d = a.ai_decision or "unknown"
        decision_dist[d] = decision_dist.get(d, 0) + 1

    remediation_stats: dict[str, int] = {}
    for a in active_alerts:
        s = a.remediation_status or "none"
        remediation_stats[s] = remediation_stats.get(s, 0) + 1

    last_audit = (
        db.query(AuditLog)
        .order_by(desc(AuditLog.created_at))
        .first()
    )

    return {
        "pipeline": "active",
        "ts": datetime.utcnow().isoformat() + "Z",
        "active_alerts": len(active_alerts),
        "ai_scored": len(scored),
        "avg_ai_score": avg_score,
        "avg_anomaly_norm": avg_norm,
        "decision_distribution": decision_dist,
        "remediation_stats": remediation_stats,
        "last_audit_action": last_audit.action.value if last_audit else None,
        "last_audit_ts": last_audit.created_at.isoformat() if last_audit else None,
        "lambda_config": _LAMBDA,
    }


@router.get("/predictions")
def get_predictions(hours: int = 2, db: Session = Depends(get_db)):
    """
    Data science predictions — linear regression on pod metrics.
    Returns time-to-saturation estimates for CPU, RAM, and restarts.
    """
    from ..predictions import predict_all_pods
    return {
        "analysis_window_hours": hours,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "predictions": predict_all_pods(db, hours),
    }


@router.get("/predictions/{pod_id:path}")
def get_pod_prediction(pod_id: str, metric: str = "cpu", hours: int = 2, db: Session = Depends(get_db)):
    """Prediction for a specific pod + metric."""
    from ..predictions import predict_pod_metric
    pred = predict_pod_metric(db, pod_id, metric, hours)
    return {
        "resource_id": pred.resource_id,
        "metric": pred.metric,
        "current_value": pred.current_value,
        "trend": pred.trend,
        "slope_per_hour": pred.slope_per_hour,
        "predicted_saturation_hours": pred.predicted_saturation,
        "confidence": pred.confidence,
        "data_points": pred.data_points,
        "message": pred.message,
    }
