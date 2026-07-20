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


# ─── One-Click AI Resolve All ─────────────────────────────────────────────────

@router.post("/resolve-all")
def ai_resolve_all(db: Session = Depends(get_db)):
    """One-click: AI analyzes namespace, remediates all issues."""
    from ..soft_quota import get_quota_status
    from ..remediation_agent import execute_remediation

    actions_taken = []

    # 1. Get quota status
    quota_status = get_quota_status(db)
    actions_taken.append({
        "step": "quota_check",
        "level": quota_status.level,
        "cpu_usage_percent": quota_status.cpu_usage_percent,
        "ram_usage_percent": quota_status.ram_usage_percent,
    })

    # 2. If over warning threshold: run cleanup_namespace logic
    cleanup_result = None
    if quota_status.level in ("warning", "critical", "remediate"):
        # Create a synthetic alert to trigger cleanup
        cleanup_alert = Alert(
            severity=SeverityEnum.critical if quota_status.level in ("critical", "remediate") else SeverityEnum.warning,
            status=StatusEnum.active,
            title=f"Resolve-All: Quota {quota_status.level} — CPU {quota_status.cpu_usage_percent}% / RAM {quota_status.ram_usage_percent}%",
            description="Automated cleanup triggered by resolve-all endpoint.",
            rule_name="namespace.resolve_all",
            metric_value=quota_status.cpu_usage_percent,
            threshold=80.0,
            triggered_at=datetime.utcnow(),
        )
        db.add(cleanup_alert)
        db.flush()

        cleanup_alert = execute_remediation(db, cleanup_alert, operator="AI-ResolveAll", force=True)
        cleanup_result = {
            "action": cleanup_alert.remediation_action,
            "status": cleanup_alert.remediation_status,
            "message": cleanup_alert.remediation_message,
        }
        actions_taken.append({"step": "cleanup_namespace", "result": cleanup_result})

    # 3. Resolve all active alerts
    active_alerts = db.query(Alert).filter(
        Alert.status.in_([StatusEnum.active, StatusEnum.acknowledged])
    ).all()

    resolved_count = 0
    failed_count = 0
    reprocessed = []
    for alert in active_alerts:
        try:
            # Mark as resolved
            alert.status = StatusEnum.resolved
            alert.resolved_at = datetime.utcnow()
            alert.acknowledged = True
            alert.acknowledged_by = "AI-ResolveAll"
            alert.acknowledged_at = alert.acknowledged_at or datetime.utcnow()
            alert.operator_note = (alert.operator_note or "") + "\n[resolve-all] Resolved by AI-ResolveAll"
            resolved_count += 1
            reprocessed.append({
                "alert_id": alert.id,
                "title": alert.title,
                "status": "resolved",
            })
        except Exception as e:
            failed_count += 1
            reprocessed.append({
                "alert_id": alert.id,
                "title": alert.title,
                "error": str(e),
            })

    actions_taken.append({"step": "resolve_alerts", "resolved": resolved_count, "failed": failed_count})

    db.commit()

    # 4. Send email summary if email is configured
    from ..email_notifications import _send_email, email_alerts_configured
    if email_alerts_configured() and resolved_count > 0:
        _send_email(
            f"[Cloud AI Monitor] Tout resoudre — {resolved_count} alertes resolues",
            f"Resolve-All execute.\n\nAlertes resolues: {resolved_count}\nEchecs: {failed_count}\nQuota: {quota_status.level}\nCPU: {quota_status.cpu_usage_percent}%\nRAM: {quota_status.ram_usage_percent}%\n\nTimestamp: {datetime.utcnow().isoformat()}Z"
        )

    # 5. Return summary
    return {
        "status": "completed" if resolved_count > 0 else "nothing_to_resolve",
        "message": f"{resolved_count} alertes resolues, {failed_count} echecs." if resolved_count > 0 else "Aucune alerte active a resoudre.",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "resolved": resolved_count,
        "failed": failed_count,
        "quota_level": quota_status.level,
        "cleanup_performed": cleanup_result is not None,
        "actions": actions_taken,
    }


# ─── Chaos Engineering / Stress Test ──────────────────────────────────────────

class StressTestIn(BaseModel):
    """Configure a stress test to demonstrate AI self-healing."""
    mode: str = Field(default="cpu", description="cpu, ram, or both")
    duration_seconds: int = Field(default=120, ge=30, le=600)
    intensity: str = Field(default="medium", description="low, medium, high")


@router.post("/chaos/deploy-stress")
def deploy_stress_test(payload: StressTestIn):
    """
    Deploy a stress-test pod in the namespace.
    This saturates CPU/RAM → triggers AI detection → AI remediates.
    Full self-healing demo loop.
    """
    from .. import openshift_client as k8s

    # Build stress command based on intensity
    cpu_workers = {"low": "1", "medium": "2", "high": "4"}[payload.intensity]
    ram_bytes = {"low": "200M", "medium": "400M", "high": "800M"}[payload.intensity]
    replicas = {"low": 1, "medium": 2, "high": 3}[payload.intensity]

    if payload.mode == "cpu":
        args = ["--cpu", cpu_workers, "--timeout", str(payload.duration_seconds)]
    elif payload.mode == "ram":
        args = ["--vm", "2", "--vm-bytes", ram_bytes, "--timeout", str(payload.duration_seconds)]
    else:
        args = ["--cpu", cpu_workers, "--vm", "2", "--vm-bytes", ram_bytes, "--timeout", str(payload.duration_seconds)]

    # Memory limit: set HIGH so pods don't OOMKill (we want them to STRESS, not crash)
    # CPU request: set HIGH to eat quota immediately
    cpu_request = {"low": "500m", "medium": "800m", "high": "950m"}[payload.intensity]
    mem_request = {"low": "256Mi", "medium": "512Mi", "high": "900Mi"}[payload.intensity]

    # Build the deployment manifest
    manifest = {
        "apiVersion": "apps/v1",
        "kind": "Deployment",
        "metadata": {
            "name": "stress-test",
            "namespace": "red1intheocean-dev",
            "labels": {"app": "stress-test"},
        },
        "spec": {
            "replicas": replicas,
            "selector": {"matchLabels": {"app": "stress-test"}},
            "template": {
                "metadata": {"labels": {"app": "stress-test"}},
                "spec": {
                    "containers": [{
                        "name": "stress",
                        "image": "docker.io/polinux/stress:latest",
                        "command": ["stress"],
                        "args": args,
                        "resources": {
                            "requests": {"memory": mem_request, "cpu": cpu_request},
                            "limits": {"memory": "1000Mi", "cpu": "1000m"},
                        },
                    }],
                },
            },
        },
    }

    # Apply via Kubernetes API
    import requests as http_requests
    path = "/apis/apps/v1/namespaces/red1intheocean-dev/deployments"
    s = k8s._session()
    s.headers.update({"Content-Type": "application/json"})

    # Delete existing if any
    del_resp = s.delete(k8s._url(f"{path}/stress-test"), timeout=10)
    # Ignore 404

    # Create new
    import time
    time.sleep(2)  # Wait for deletion to propagate
    resp = s.post(k8s._url(path), json=manifest, timeout=15)

    if resp.status_code in (200, 201):
        return {
            "status": "deployed",
            "mode": payload.mode,
            "intensity": payload.intensity,
            "duration_seconds": payload.duration_seconds,
            "message": f"Stress pod deployed. It will consume {payload.mode} for {payload.duration_seconds}s. "
                       f"Watch the Alerts and AIOps pages — AI should detect and remediate within 60-120s.",
        }
    else:
        return {
            "status": "error",
            "code": resp.status_code,
            "message": resp.text[:500],
        }


@router.delete("/chaos/cleanup")
def cleanup_stress_test(db: Session = Depends(get_db)):
    """
    Intelligent namespace cleanup.
    Scans live Kubernetes, identifies deletable resources, removes them.
    Never touches protected deployments (cloud-ai-monitor, postgresql).
    Returns detailed summary of what was cleaned.
    """
    from .. import openshift_client as k8s
    from ..models import Pod as PodModel, PodMetric as PodMetricModel

    PROTECTED = ["cloud-ai-monitor", "postgresql"]
    namespace = "red1intheocean-dev"

    deleted_pods = []
    deleted_deployments = []
    errors = []

    # 1. Delete stress-test deployments
    try:
        s = k8s._session()
        deploy_path = f"/apis/apps/v1/namespaces/{namespace}/deployments"
        resp = s.get(k8s._url(deploy_path), timeout=15)
        if resp.status_code == 200:
            for deploy in resp.json().get("items", []):
                name = deploy.get("metadata", {}).get("name", "")
                if "stress" in name and not any(p in name for p in PROTECTED):
                    del_resp = s.delete(k8s._url(f"{deploy_path}/{name}"), timeout=10)
                    if del_resp.status_code in (200, 202):
                        deleted_deployments.append(name)
    except Exception as e:
        errors.append(f"Deployment scan: {e}")

    # 2. Delete stress/completed/failed pods directly
    try:
        pods_path = f"/api/v1/namespaces/{namespace}/pods"
        resp = k8s._session().get(k8s._url(pods_path), timeout=15)
        if resp.status_code == 200:
            for pod_item in resp.json().get("items", []):
                pod_name = pod_item.get("metadata", {}).get("name", "")
                labels = pod_item.get("metadata", {}).get("labels", {})
                phase = pod_item.get("status", {}).get("phase", "")
                app_label = labels.get("app", "")

                # Skip protected
                if any(p in pod_name or p in app_label for p in PROTECTED):
                    continue

                # Delete if: stress-test, Failed, Succeeded, or Evicted
                should_delete = (
                    "stress" in pod_name or "stress" in app_label
                    or phase in ("Failed", "Succeeded")
                    or pod_item.get("status", {}).get("reason") == "Evicted"
                )

                if should_delete:
                    del_resp = k8s._session().delete(k8s._url(f"{pods_path}/{pod_name}"), timeout=10)
                    if del_resp.status_code in (200, 202):
                        deleted_pods.append(pod_name)
                        # Also clean from database
                        pod_id = f"{namespace}/{pod_name}"
                        db_pod = db.get(PodModel, pod_id)
                        if db_pod:
                            db.query(PodMetricModel).filter(PodMetricModel.pod_id == pod_id).delete()
                            db.delete(db_pod)
    except Exception as e:
        errors.append(f"Pod scan: {e}")

    db.commit()

    return {
        "status": "cleaned",
        "deleted_deployments": deleted_deployments,
        "deleted_pods": deleted_pods,
        "total_removed": len(deleted_deployments) + len(deleted_pods),
        "errors": errors if errors else None,
        "message": f"Nettoyage termine: {len(deleted_deployments)} deployments, {len(deleted_pods)} pods supprimes.",
    }
