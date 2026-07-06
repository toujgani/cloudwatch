"""
WebSocket Gateway — Architecture D real-time push layer.
Broadcasts a live snapshot every WS_BROADCAST_INTERVAL_SECONDS to all
connected clients. The snapshot includes:
  - Dashboard KPIs (VMs, pods, alert counts, health score)
  - Active alert list with AI vector data
  - Last audit log entries
  - Anomaly vector summary for the AIOps simulator
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

WS_BROADCAST_INTERVAL_SECONDS = 3


class ConnectionManager:
    def __init__(self):
        self._connections: list[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        async with self._lock:
            self._connections.append(ws)
        logger.info("[WS] Client connected — total: %d", len(self._connections))

    async def disconnect(self, ws: WebSocket):
        async with self._lock:
            self._connections = [c for c in self._connections if c is not ws]
        logger.info("[WS] Client disconnected — total: %d", len(self._connections))

    async def broadcast(self, payload: dict[str, Any]):
        message = json.dumps(payload, default=str)
        dead: list[WebSocket] = []
        async with self._lock:
            targets = list(self._connections)

        for ws in targets:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)

        if dead:
            async with self._lock:
                for ws in dead:
                    self._connections = [c for c in self._connections if c is not ws]

    @property
    def connected_count(self) -> int:
        return len(self._connections)


manager = ConnectionManager()


def _build_snapshot(db_session_factory) -> dict[str, Any]:
    """Build the broadcast payload from the database. Called in a thread pool."""
    from .models import VirtualMachine, VMMetric, Pod, Alert, AuditLog, StatusEnum, SeverityEnum
    from sqlalchemy.orm import Session
    from sqlalchemy import desc

    db: Session = db_session_factory()
    try:
        # ── Dashboard KPIs ────────────────────────────────────────────────────
        total_vms  = db.query(VirtualMachine).count()
        active_vms = db.query(VirtualMachine).filter(VirtualMachine.status == "ACTIVE").count()
        total_pods   = db.query(Pod).count()
        running_pods = db.query(Pod).filter(Pod.status == "Running").count()
        failed_pods  = db.query(Pod).filter(Pod.status.in_(["Failed", "Unknown"])).count()

        active_alerts = db.query(Alert).filter(
            Alert.status.in_([StatusEnum.active, StatusEnum.acknowledged, StatusEnum.assigned])
        ).all()
        crit_count = sum(1 for a in active_alerts if a.severity == SeverityEnum.critical)

        # Health score
        vm_avail  = active_vms / max(total_vms, 1)
        pod_avail = running_pods / max(total_pods, 1)
        penalty   = min(45, crit_count * 12 + max(len(active_alerts) - crit_count, 0) * 4)
        health_score = max(0, min(100, round((vm_avail * 45 + pod_avail * 35 + 20) - penalty)))

        # ── Active alerts with AI vector data ─────────────────────────────────
        top_alerts = (
            db.query(Alert)
            .filter(Alert.status.in_([StatusEnum.active, StatusEnum.acknowledged, StatusEnum.assigned]))
            .order_by(desc(Alert.ai_score), desc(Alert.triggered_at))
            .limit(10)
            .all()
        )
        alerts_payload = [
            {
                "id": a.id,
                "severity": a.severity.value,
                "status": a.status.value,
                "title": a.title,
                "ai_score": a.ai_score,
                "ai_decision": a.ai_decision,
                "ai_recommendation": a.ai_recommendation,
                "ai_confidence": a.ai_confidence,
                "anomaly_m": a.anomaly_m,
                "anomaly_l": a.anomaly_l,
                "anomaly_t": a.anomaly_t,
                "anomaly_vector_norm": a.anomaly_vector_norm,
                "remediation_status": a.remediation_status,
                "triggered_at": a.triggered_at.isoformat() if a.triggered_at else None,
            }
            for a in top_alerts
        ]

        # ── Anomaly vector aggregate ──────────────────────────────────────────
        vectors = [
            (a.anomaly_m or 0, a.anomaly_l or 0, a.anomaly_t or 0)
            for a in active_alerts
            if a.anomaly_m is not None
        ]
        if vectors:
            avg_m = round(sum(v[0] for v in vectors) / len(vectors), 4)
            avg_l = round(sum(v[1] for v in vectors) / len(vectors), 4)
            avg_t = round(sum(v[2] for v in vectors) / len(vectors), 4)
        else:
            avg_m = avg_l = avg_t = 0.0

        # ── Recent audit log ──────────────────────────────────────────────────
        recent_audit = (
            db.query(AuditLog)
            .order_by(desc(AuditLog.created_at))
            .limit(5)
            .all()
        )
        audit_payload = [
            {
                "id": e.id,
                "action": e.action.value,
                "actor": e.actor,
                "resource_type": e.resource_type,
                "resource_id": e.resource_id,
                "detail": e.detail,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in recent_audit
        ]

        return {
            "type": "snapshot",
            "ts": datetime.utcnow().isoformat() + "Z",
            "kpis": {
                "vms": {"total": total_vms, "active": active_vms},
                "pods": {"total": total_pods, "running": running_pods, "failed": failed_pods},
                "alerts": {"total_active": len(active_alerts), "critical": crit_count},
                "health_score": health_score,
            },
            "anomaly_aggregate": {"m": avg_m, "l": avg_l, "t": avg_t},
            "top_alerts": alerts_payload,
            "recent_audit": audit_payload,
        }
    finally:
        db.close()


async def broadcast_loop(db_session_factory):
    """Long-running coroutine started from main.py lifespan."""
    import asyncio
    loop = asyncio.get_event_loop()
    while True:
        try:
            if manager.connected_count > 0:
                snapshot = await loop.run_in_executor(
                    None, _build_snapshot, db_session_factory
                )
                await manager.broadcast(snapshot)
        except Exception as exc:
            logger.exception("[WS] Broadcast error: %s", exc)
        await asyncio.sleep(WS_BROADCAST_INTERVAL_SECONDS)
