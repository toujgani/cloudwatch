"""
Prediction Engine — Architecture D data science layer.
Uses linear regression on historical metrics to predict:
  - Time to CPU saturation (100%)
  - Time to RAM saturation (100%)
  - Time to restart threshold breach
  - Trend direction (increasing / stable / decreasing)

No external ML libraries needed — pure Python + math.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta
from dataclasses import dataclass
from sqlalchemy.orm import Session
from sqlalchemy import desc

from .models import PodMetric, VMMetric


@dataclass
class Prediction:
    resource_id: str
    resource_type: str         # "pod" or "vm"
    metric: str                # "cpu" or "ram" or "restarts"
    current_value: float
    trend: str                 # "increasing" | "stable" | "decreasing"
    slope_per_hour: float      # rate of change per hour
    predicted_saturation: float | None    # hours until 100% (None = won't saturate)
    confidence: float          # 0-1
    data_points: int
    message: str


def _linear_regression(points: list[tuple[float, float]]) -> tuple[float, float, float]:
    """
    Simple least-squares linear regression.
    Returns (slope, intercept, r_squared).
    points = [(x, y), ...]
    """
    n = len(points)
    if n < 2:
        return 0.0, 0.0, 0.0

    sum_x = sum(p[0] for p in points)
    sum_y = sum(p[1] for p in points)
    sum_xy = sum(p[0] * p[1] for p in points)
    sum_x2 = sum(p[0] ** 2 for p in points)

    denom = n * sum_x2 - sum_x ** 2
    if denom == 0:
        return 0.0, sum_y / n, 0.0

    slope = (n * sum_xy - sum_x * sum_y) / denom
    intercept = (sum_y - slope * sum_x) / n

    # R² calculation
    mean_y = sum_y / n
    ss_tot = sum((p[1] - mean_y) ** 2 for p in points)
    ss_res = sum((p[1] - (slope * p[0] + intercept)) ** 2 for p in points)
    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0.0

    return slope, intercept, max(0.0, r_squared)


def predict_pod_metric(db: Session, pod_id: str, metric: str = "cpu", hours: int = 2) -> Prediction:
    """Predict saturation for a pod metric (cpu_millicores or ram_mb)."""
    since = datetime.utcnow() - timedelta(hours=hours)
    metrics = (
        db.query(PodMetric)
        .filter(PodMetric.pod_id == pod_id, PodMetric.collected_at >= since)
        .order_by(PodMetric.collected_at)
        .all()
    )

    if len(metrics) < 3:
        return Prediction(
            resource_id=pod_id, resource_type="pod", metric=metric,
            current_value=0, trend="stable", slope_per_hour=0,
            predicted_saturation=None, confidence=0, data_points=len(metrics),
            message="Insufficient data for prediction (need at least 3 points)."
        )

    # Build time series: x = hours since first point, y = value
    base_time = metrics[0].collected_at
    if metric == "cpu":
        points = [
            ((m.collected_at - base_time).total_seconds() / 3600, m.cpu_millicores or 0)
            for m in metrics if m.cpu_millicores is not None
        ]
        saturation_threshold = 1000.0  # 1000 millicores = 1 full core
    elif metric == "ram":
        points = [
            ((m.collected_at - base_time).total_seconds() / 3600, m.ram_mb or 0)
            for m in metrics if m.ram_mb is not None
        ]
        saturation_threshold = 512.0  # assume 512 MB limit
    elif metric == "restarts":
        points = [
            ((m.collected_at - base_time).total_seconds() / 3600, float(m.restart_count or 0))
            for m in metrics
        ]
        saturation_threshold = 20.0  # 20 restarts = critical
    else:
        points = []
        saturation_threshold = 100.0

    if len(points) < 3:
        return Prediction(
            resource_id=pod_id, resource_type="pod", metric=metric,
            current_value=0, trend="stable", slope_per_hour=0,
            predicted_saturation=None, confidence=0, data_points=len(points),
            message="Not enough valid data points."
        )

    slope, intercept, r_squared = _linear_regression(points)
    current_value = points[-1][1]
    current_time = points[-1][0]

    # Trend classification
    if slope > 0.5:
        trend = "increasing"
    elif slope < -0.5:
        trend = "decreasing"
    else:
        trend = "stable"

    # Time to saturation
    if slope > 0 and current_value < saturation_threshold:
        hours_to_sat = (saturation_threshold - current_value) / slope
        if hours_to_sat > 168:  # more than a week = effectively never
            predicted_saturation = None
            message = f"{metric.upper()} stable — no saturation predicted within 7 days."
        else:
            predicted_saturation = round(hours_to_sat, 1)
            message = (
                f"{metric.upper()} trending {trend} at {abs(slope):.1f}/hour. "
                f"Estimated saturation in {predicted_saturation:.1f}h."
            )
    else:
        predicted_saturation = None
        if trend == "decreasing":
            message = f"{metric.upper()} trending down — no saturation risk."
        else:
            message = f"{metric.upper()} stable — no saturation predicted."

    confidence = min(0.95, r_squared * 0.7 + min(len(points) / 20, 0.3))

    return Prediction(
        resource_id=pod_id,
        resource_type="pod",
        metric=metric,
        current_value=round(current_value, 2),
        trend=trend,
        slope_per_hour=round(slope, 3),
        predicted_saturation=predicted_saturation,
        confidence=round(confidence, 3),
        data_points=len(points),
        message=message,
    )


def predict_all_pods(db: Session, hours: int = 2) -> list[dict]:
    """Run predictions on all pods with recent metrics."""
    from .models import Pod
    pods = db.query(Pod).all()
    results = []

    for pod in pods:
        for metric in ("cpu", "ram", "restarts"):
            pred = predict_pod_metric(db, pod.id, metric, hours)
            if pred.data_points >= 3:
                results.append({
                    "resource_id": pred.resource_id,
                    "resource_type": pred.resource_type,
                    "metric": pred.metric,
                    "current_value": pred.current_value,
                    "trend": pred.trend,
                    "slope_per_hour": pred.slope_per_hour,
                    "predicted_saturation_hours": pred.predicted_saturation,
                    "confidence": pred.confidence,
                    "data_points": pred.data_points,
                    "message": pred.message,
                })

    # Sort by urgency: shortest saturation time first
    results.sort(key=lambda r: r["predicted_saturation_hours"] or 9999)
    return results
